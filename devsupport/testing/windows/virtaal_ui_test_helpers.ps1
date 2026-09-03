# Reusable PowerShell helpers for driving the packaged Windows
# virtaal.exe from CI (or a local Windows/VM session): launch, get a
# real window handle via Win32, read its geometry/title, send
# keystrokes via SendKeys, detect and drive popup dialogs (file choosers,
# Preferences, ...), simulate a mouse click, save a screenshot, read the
# frozen-build log files, and clean up.
#
# Pulled out into its own file so Windows-side regression checks - menu
# navigation, keyboard shortcuts, dialogs, anything else that needs to
# actually drive the running app rather than just confirm it launched -
# don't need to reinvent Win32 P/Invoke boilerplate each time.
#
# Usage: dot-source this file, then call the functions below.
#   . .\devsupport\testing\windows\virtaal_ui_test_helpers.ps1
#   $t = Start-VirtaalTest -ExePath .\dist\virtaal\virtaal.exe -Arguments "po\af.po"
#   if (-not $t) { exit 1 }  # Start-VirtaalTest already logged why
#   $widthBefore = Get-VirtaalWidth $t
#   Send-VirtaalKeys $t "{ENTER}"
#   $widthAfter = Get-VirtaalWidth $t
#   Stop-VirtaalTest $t

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# GetForegroundWindow: a GTK dialog on Windows takes the foreground
# when it opens, so comparing this against the main Instance.Hwnd after
# sending a key that should open one is enough to detect it and read
# its title - simpler than EnumWindows-plus-delegate-marshaling.
#
# A .NET type, once compiled via Add-Type in a process, can never be
# redefined in that same process - re-dot-sourcing this file in the
# same PowerShell window throws "Cannot add type. The type name
# 'VirtaalWin32' already exists." without a guard. A plain existence
# guard isn't enough though: it would let a stale, already-loaded older
# version of this type keep "succeeding" while silently missing newer
# methods, producing confusing "does not contain a method named '...'"
# failures instead of one clear error. Checking for the specific
# methods this version needs, not just type existence, makes a stale
# session fail fast with an actionable message - it still can't fix a
# stale session (no guard can redefine an already-compiled type), only
# make the failure obvious.
$existingVirtaalWin32 = ([System.Management.Automation.PSTypeName]'VirtaalWin32').Type
if ($existingVirtaalWin32) {
    $requiredMethods = @('GetWindowRect', 'SetForegroundWindow', 'GetForegroundWindow', 'GetWindowTextLength', 'GetWindowText', 'SetCursorPos', 'mouse_event')
    $existingMethodNames = @($existingVirtaalWin32.GetMethods() | ForEach-Object { $_.Name })
    $missingMethods = @($requiredMethods | Where-Object { $existingMethodNames -notcontains $_ })
    if ($missingMethods) {
        throw "This PowerShell session already has an older VirtaalWin32 type loaded (missing: $($missingMethods -join ', ')) from before virtaal_ui_test_helpers.ps1 was last updated - a .NET type can't be redefined in the same process once compiled, so this session can't recover on its own. Close this PowerShell window, open a new one, and re-run."
    }
} else {
    Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; using System.Text; public class VirtaalWin32 { [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect); [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow(); [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd); [DllImport("user32.dll", CharSet = CharSet.Auto)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount); [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y); [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo); public struct RECT { public int Left; public int Top; public int Right; public int Bottom; } }'
}

# Runs fast (no extra pauses) by default - everything here already has
# its own short, tuned settle delays. Set via Set-VirtaalHumanDelay for
# a human who wants to actually *watch* a run rather than just read its
# transcript afterward - dialogs that open and close within a few
# hundred milliseconds are real, but too fast to see. One switch
# instead of threading a parameter through every call site: applied
# inside Send-VirtaalKeys, Send-VirtaalPopupKeys, Send-VirtaalClick,
# and right after Wait-VirtaalPopup finds a dialog.
$script:VirtaalHumanDelayMs = 0
function Set-VirtaalHumanDelay {
    param([Parameter(Mandatory)][int]$Milliseconds)
    $script:VirtaalHumanDelayMs = $Milliseconds
}

# Enables Virtaal's own -D/--debug flag (bin/virtaal) for every check
# launched after this is called, and relaxes Assert-VirtaalLogsClean's
# default allowlist to match: without it, the app's logging module is
# never configured at all (bin/virtaal only calls logging.basicConfig()
# when -D/--log is passed), so every logging.debug()/logging.info() call
# already in the codebase (mode changes, search match counts, which unit
# a match actually selected - see searchmode.py) is silently discarded,
# not just hidden - there was nothing to look at either way. Off by
# default, same reasoning as -HumanDelayMs: full battery runs should stay
# exactly as strict as they've always been (any unexpected line is a real
# problem), this is for deliberately turning up the detail on a -RunTest
# drill-down where "why didn't this happen" is exactly the question.
$script:VirtaalAppDebugLog = $false
function Set-VirtaalAppDebugLog {
    $script:VirtaalAppDebugLog = $true
}
function Wait-VirtaalForHuman {
    if ($script:VirtaalHumanDelayMs -gt 0) { Start-Sleep -Milliseconds $script:VirtaalHumanDelayMs }
}

function Start-VirtaalTest {
    <#
    .SYNOPSIS
    Launches the packaged virtaal.exe and waits for a real window handle.
    Returns $null (and writes a ::error:: line) if no window ever appears
    - callers should check for that rather than assume success.
    #>
    param(
        [string]$ExePath = ".\dist\virtaal\virtaal.exe",
        [string]$Arguments = "",
        [int]$WaitSeconds = 8,
        [int]$HandleTimeoutSeconds = 10,
        # Per-call opt-in, independent of -AppDebugLog/Set-VirtaalAppDebugLog:
        # a check that needs to read back e.g. modecontroller.py's own
        # "Mode selected: X" INFO line to verify its own outcome shouldn't
        # have to turn on debug logging (and Assert-VirtaalLogsClean's
        # matching allowlist relaxation) for every *other* check in the
        # same run too - that global switch is script-scoped and would
        # otherwise leak forward into every check launched after it.
        [switch]$DebugLog
    )

    # See Set-VirtaalAppDebugLog above - -D/--debug is a plain argparse
    # flag (bin/virtaal), order relative to the file argument doesn't
    # matter, so it's safe to just prepend it here regardless of what
    # $Arguments already is.
    if ($script:VirtaalAppDebugLog -or $DebugLog) {
        $Arguments = if ($Arguments) { "--debug $Arguments" } else { "--debug" }
    }

    # Windows PowerShell 5.1's Start-Process rejects -ArgumentList "" -
    # "Cannot validate argument on parameter 'ArgumentList'. The
    # argument is null or empty", a terminating error. Only pass
    # -ArgumentList at all when there's something non-empty to pass.
    $startProcessArgs = @{ FilePath = $ExePath; PassThru = $true }
    if ($Arguments) { $startProcessArgs['ArgumentList'] = $Arguments }
    $proc = Start-Process @startProcessArgs
    Start-Sleep -Seconds $WaitSeconds

    $stillRunning = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if (-not $stillRunning) {
        Write-Host "::error::$ExePath exited within ${WaitSeconds}s of launch"
        Write-VirtaalLogs
        return $null
    }

    $hwnd = [IntPtr]::Zero
    $deadline = (Get-Date).AddSeconds($HandleTimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $proc.Refresh()
        if ($proc.MainWindowHandle -ne [IntPtr]::Zero) {
            $hwnd = $proc.MainWindowHandle
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if ($hwnd -eq [IntPtr]::Zero) {
        Write-Host "::error::Never got a main window handle for $ExePath"
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        return $null
    }

    $instance = [PSCustomObject]@{ Process = $proc; Hwnd = $hwnd; OpenScreenshot = $null }
    if ($Arguments) {
        # Captured unconditionally for every launch that opens a file
        # (not the bare Welcome screen, where there's no treeview/
        # editor layout yet) - real evidence of this moment for every
        # check, not just ones instrumented for it individually.
        $instance.OpenScreenshot = Save-VirtaalScreenshot $instance
    }
    return $instance
}

function Get-VirtaalRect {
    param([Parameter(Mandatory)]$Instance)
    $rect = New-Object VirtaalWin32+RECT
    [VirtaalWin32]::GetWindowRect($Instance.Hwnd, [ref]$rect) | Out-Null
    return $rect
}

function Get-VirtaalWidth {
    param([Parameter(Mandatory)]$Instance)
    $rect = Get-VirtaalRect $Instance
    return $rect.Right - $rect.Left
}

function Get-VirtaalHeight {
    param([Parameter(Mandatory)]$Instance)
    $rect = Get-VirtaalRect $Instance
    return $rect.Bottom - $rect.Top
}

function Get-VirtaalWindowText {
    <#
    .SYNOPSIS
    Low-level: reads any window's title text via Win32 GetWindowText,
    given a raw HWND (not a Start-VirtaalTest instance) - the primitive
    Get-VirtaalTitle and the popup-dialog checks (Ctrl+P Preferences,
    etc.) both build on.
    #>
    param([Parameter(Mandatory)][IntPtr]$Hwnd)
    $len = [VirtaalWin32]::GetWindowTextLength($Hwnd)
    if ($len -eq 0) { return "" }
    $sb = New-Object System.Text.StringBuilder ($len + 1)
    [VirtaalWin32]::GetWindowText($Hwnd, $sb, $sb.Capacity) | Out-Null
    return $sb.ToString()
}

function Get-VirtaalTitle {
    <#
    .SYNOPSIS
    Reads the instance's window title via Win32 GetWindowText - not the
    same as $Instance.Process.MainWindowTitle, which is a one-time
    snapshot .NET took right after the process's main window first
    appeared and does *not* update as the title changes afterwards
    (e.g. the "*" modified-marker mainview.py's set_saveable()
    prepends). Needed for any check that has to observe the modified
    marker rather than just
    whether the app is alive.
    #>
    param([Parameter(Mandatory)]$Instance)
    return Get-VirtaalWindowText $Instance.Hwnd
}

function Wait-VirtaalPopup {
    <#
    .SYNOPSIS
    Waits for a *different* top-level window than the instance's main
    one to take the foreground (e.g. after Ctrl+P for Preferences, or
    any other action that opens a dialog) - GTK dialogs on Windows take
    the foreground when they open, so this is simpler and more reliable
    than enumerating all of a process's top-level windows. Returns the
    popup's HWND, or $null if nothing new appeared within the timeout
    (the caller's action didn't open a dialog, or it failed to).
    #>
    param([Parameter(Mandatory)]$Instance, [int]$TimeoutSeconds = 5)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $fg = [VirtaalWin32]::GetForegroundWindow()
        if ($fg -ne [IntPtr]::Zero -and $fg -ne $Instance.Hwnd) {
            # Extra pause here specifically (not just at the end of every
            # Send-* call) so a human watching with Set-VirtaalHumanDelay
            # on actually gets to see the dialog appear before whatever
            # the calling check does next (usually closing it).
            Wait-VirtaalForHuman
            return $fg
        }
        Start-Sleep -Milliseconds 200
    }
    return $null
}

function Send-VirtaalPopupKeys {
    <#
    .SYNOPSIS
    Like Send-VirtaalKeys, but activates an arbitrary HWND (typically one
    from Wait-VirtaalPopup - a file-open dialog, Preferences, ...)
    instead of always the instance's main window. Send-VirtaalKeys itself
    can't be reused for this: it unconditionally forces the *main*
    window to the foreground first, which would steal focus back off a
    dialog that's supposed to be receiving these keys instead.
    #>
    param([Parameter(Mandatory)][IntPtr]$Hwnd, [Parameter(Mandatory)][string]$Keys, [int]$SettleMs = 300)
    [VirtaalWin32]::SetForegroundWindow($Hwnd) | Out-Null
    Start-Sleep -Milliseconds 300
    [System.Windows.Forms.SendKeys]::SendWait($Keys)
    Start-Sleep -Milliseconds $SettleMs
    Wait-VirtaalForHuman
}

function Close-VirtaalPopup {
    <#
    .SYNOPSIS
    Closes a popup/dialog window found via Wait-VirtaalPopup by
    activating it and sending Escape, then gives focus back to the
    instance's main window so subsequent Send-VirtaalKeys calls land in
    the right place again.
    #>
    param([Parameter(Mandatory)]$Instance, [Parameter(Mandatory)][IntPtr]$PopupHwnd)
    Send-VirtaalPopupKeys $PopupHwnd "{ESC}"
    [VirtaalWin32]::SetForegroundWindow($Instance.Hwnd) | Out-Null
    Start-Sleep -Milliseconds 200
}

function Send-VirtaalClick {
    <#
    .SYNOPSIS
    Simulates a real left mouse click at a position within the
    instance's window, given as fractions (0.0-1.0) of its current
    width/height rather than absolute pixels, so it at least scales with
    the window's own size instead of assuming a fixed one. This is
    inherently best-effort: there's no UI Automation tree here to ask
    "where is the treeview's second row", so a click check's coordinates
    are a guess based on Virtaal's general layout (menu/toolbar at top,
    the unit list as a strip below that, the source/target editor
    filling most of the rest) - use Save-VirtaalScreenshot right after a
    click to confirm/tune where it actually landed if a click-based
    check isn't behaving as expected.
    #>
    param([Parameter(Mandatory)]$Instance, [Parameter(Mandatory)][double]$XFraction, [Parameter(Mandatory)][double]$YFraction, [int]$SettleMs = 300)
    [VirtaalWin32]::SetForegroundWindow($Instance.Hwnd) | Out-Null
    Start-Sleep -Milliseconds 300
    $rect = Get-VirtaalRect $Instance
    $x = [int]($rect.Left + ($rect.Right - $rect.Left) * $XFraction)
    $y = [int]($rect.Top + ($rect.Bottom - $rect.Top) * $YFraction)
    [VirtaalWin32]::SetCursorPos($x, $y) | Out-Null
    Start-Sleep -Milliseconds 50
    [VirtaalWin32]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero) # MOUSEEVENTF_LEFTDOWN
    Start-Sleep -Milliseconds 50
    [VirtaalWin32]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero) # MOUSEEVENTF_LEFTUP
    Start-Sleep -Milliseconds $SettleMs
    Wait-VirtaalForHuman
}

function Get-VirtaalScreenshotPath {
    # $PSScriptRoot, not $MyInvocation.MyCommand.Path - the latter is
    # empty inside a function (confirmed locally: only reliable at a
    # script's own top level, not from a function it defines, even
    # though the function itself is still defined by, and dot-sourced
    # from, this same .ps1 file).
    $dir = Join-Path $PSScriptRoot ".local-test-runs"
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    # Millisecond precision, not just yyyyMMdd-HHmmss - a check that
    # takes a before/after pair (or two checks running back to back) can
    # easily land in the same second otherwise, and two Saves racing for
    # the same filename is a plausible contributor to the GDI+ error
    # Save-RectToScreenshot works around below.
    return Join-Path $dir "screenshot-$(Get-Date -Format 'yyyyMMdd-HHmmss-fff').png"
}

function Save-RectToScreenshot {
    <#
    .SYNOPSIS
    Captures an arbitrary screen rectangle (a VirtaalWin32+RECT or a
    System.Drawing.Rectangle - anything with Left/Top and either
    Right/Bottom or Width/Height) to a PNG. The shared primitive behind
    Save-VirtaalScreenshot (a window's own rect) and
    Save-VirtaalFullScreenScreenshot (the whole virtual desktop).
    #>
    param([Parameter(Mandatory)]$Rect, [string]$Path)
    if (-not $Path) { $Path = Get-VirtaalScreenshotPath }
    if ($Rect.PSObject.Properties.Name -contains 'Right') {
        $left = $Rect.Left; $top = $Rect.Top
        $width = $Rect.Right - $Rect.Left
        $height = $Rect.Bottom - $Rect.Top
    } else {
        $left = $Rect.X; $top = $Rect.Y
        $width = $Rect.Width; $height = $Rect.Height
    }
    if ($width -le 0 -or $height -le 0) { return $null }
    $bmp = New-Object System.Drawing.Bitmap $width, $height
    try {
        $graphics = [System.Drawing.Graphics]::FromImage($bmp)
        try {
            $graphics.CopyFromScreen($left, $top, 0, 0, $bmp.Size)
        } finally {
            $graphics.Dispose()
        }
        # Bitmap.Save throwing a bare "A generic error occurred in
        # GDI+" is a known-flaky .NET pattern - gives no detail on why,
        # but a transient lock on a freshly-written file (e.g.
        # antivirus real-time scanning) is a typical cause. A short
        # retry is cheap insurance against that.
        $saved = $false
        $lastError = $null
        for ($attempt = 1; $attempt -le 3 -and -not $saved; $attempt++) {
            try {
                $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
                $saved = $true
            } catch {
                $lastError = $_
                Start-Sleep -Milliseconds 300
            }
        }
        if (-not $saved) { throw $lastError }
    } finally {
        $bmp.Dispose()
    }
    return $Path
}

function Save-VirtaalScreenshot {
    <#
    .SYNOPSIS
    Captures the instance's window to a PNG - something to actually
    look at when a check's result needs visual confirmation (most
    usefully, tuning Send-VirtaalClick's coordinates). Defaults to
    landing under devsupport\testing\windows\.local-test-runs\, the
    same location Invoke-VirtaalLocalTestPass.ps1's transcript uses.
    #>
    param([Parameter(Mandatory)]$Instance, [string]$Path)
    return Save-RectToScreenshot -Rect (Get-VirtaalRect $Instance) -Path $Path
}

function Save-VirtaalFullScreenScreenshot {
    <#
    .SYNOPSIS
    Captures the *entire* virtual desktop (all monitors), not just the
    instance's own window rect. A GTK popup menu (PopupMenuButton, e.g.
    the status-bar check-type/language-pair selectors) is a separate
    top-level window that isn't guaranteed to stay within its parent
    window's bounding rect, especially one anchored near a window edge
    (POS_SW_NW-style positioning, popupmenubutton.py) - a window-rect-
    only screenshot can miss an open menu entirely even though the
    click itself landed correctly.
    #>
    param([string]$Path)
    return Save-RectToScreenshot -Rect ([System.Windows.Forms.SystemInformation]::VirtualScreen) -Path $Path
}

function Send-VirtaalKeys {
    <#
    .SYNOPSIS
    Activates the instance's window, then sends a SendKeys string to it
    (e.g. "{ENTER}", "{DOWN}", "^z" for Ctrl+Z, "%{F4}" for Alt+F4 - see
    .NET's SendKeys documentation for the full syntax). SendKeys always
    goes to whatever window is frontmost at the OS level regardless of
    which handle you have, so activating first isn't optional.
    #>
    param([Parameter(Mandatory)]$Instance, [Parameter(Mandatory)][string]$Keys, [int]$SettleMs = 200)
    [VirtaalWin32]::SetForegroundWindow($Instance.Hwnd) | Out-Null
    Start-Sleep -Milliseconds 300
    [System.Windows.Forms.SendKeys]::SendWait($Keys)
    Start-Sleep -Milliseconds $SettleMs
    Wait-VirtaalForHuman
}

function Get-VirtaalLogs {
    <#
    .SYNOPSIS
    Reads the frozen build's log files. pan_app.py redirects stdout/
    stderr here for packaged builds only (not process-level redirection)
    - this is where a real traceback ends up, not wherever PowerShell
    would otherwise capture output from Start-Process.
    #>
    $stdout = @(Get-Content "$env:APPDATA\Virtaal\stdout_virtaal.log" -ErrorAction SilentlyContinue)
    $stderr = @(Get-Content "$env:APPDATA\Virtaal\stderr_virtaal.log" -ErrorAction SilentlyContinue)
    return [PSCustomObject]@{ Stdout = $stdout; Stderr = $stderr }
}

function Write-VirtaalLogs {
    <#
    .SYNOPSIS
    Displays the frozen build's log files to the host/transcript.
    #>
    $logs = Get-VirtaalLogs
    Write-Host "--- stdout log ---"
    # Explicit Write-Host per line, not a bare "$logs.Stdout" expression:
    # a bare expression statement in PowerShell doesn't just *display*
    # to the host, it also becomes part of this function's own output
    # stream (its "return value"). Assert-VirtaalLogsClean calls this
    # right before its own `return $false` - a bare expression here
    # would turn that into a multi-element array (leaked lines plus
    # $false) instead, and PowerShell treats any non-empty array as
    # truthy regardless of contents, silently passing checks that
    # should have failed.
    $logs.Stdout | ForEach-Object { Write-Host $_ }
    Write-Host "--- stderr log ---"
    $logs.Stderr | ForEach-Object { Write-Host $_ }
}

function Assert-VirtaalLogsClean {
    <#
    .SYNOPSIS
    Same allowlist-of-lines shape as the "Verify the bundle actually
    runs" step in ci.yml: fails (writes ::error:: and returns $false) if
    either log file contains a line not covered by $AllowlistPatterns
    (an array of regex strings). Starts with no allowlist by default -
    the known-clean baseline for this frozen build is empty logs.
    #>
    param([string[]]$AllowlistPatterns = @(), [switch]$AllowDebugLog)
    if ($script:VirtaalAppDebugLog -or $AllowDebugLog) {
        # bin\virtaal's -D/--debug format is '%(levelname)7s
        # %(module)s...' - levelname right-justified to 7 chars, so
        # DEBUG/INFO lines have 2/3 leading spaces before the level
        # name. Only matches those two levels deliberately - WARNING
        # (exactly 7 chars, no leading space) and ERROR/CRITICAL still
        # fail this check as real unexpected output, same as always;
        # this only tolerates the *expected* extra noise from turning
        # -D on, not genuine problems.
        $AllowlistPatterns = $AllowlistPatterns + '^\s*(DEBUG|INFO)\s'
    }
    $logs = Get-VirtaalLogs
    $lines = @($logs.Stdout + $logs.Stderr) | Where-Object { $_ }
    $unexpected = $lines | Where-Object {
        $line = $_
        -not ($AllowlistPatterns | Where-Object { $line -match $_ })
    }
    if ($unexpected) {
        Write-Host "::error::Unexpected output in the bundle's log"
        Write-VirtaalLogs
        return $false
    }
    return $true
}

function Stop-VirtaalTest {
    param($Instance)
    if ($Instance -and $Instance.Process) {
        Stop-Process -Id $Instance.Process.Id -Force -ErrorAction SilentlyContinue
    }
    # Belt-and-suspenders, same as ci.yml's existing steps: catches any
    # child/renamed process Stop-Process on the original PID missed.
    Get-Process -Name virtaal -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    # Stop-Process -Force requests termination but returns before the
    # process (and its window) has actually finished going away - the
    # next check's Start-VirtaalTest could launch a fresh instance
    # while the previous one's window is still tearing down, leaving
    # two live windows on screen at once and a later action landing on
    # the wrong one. Poll for "virtaal" to actually disappear from the
    # process list instead of trusting Stop-Process's return to mean
    # "gone" - bounded, so a genuinely stuck process can't hang the
    # whole battery.
    $deadline = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Name virtaal -ErrorAction SilentlyContinue)) { return }
        Start-Sleep -Milliseconds 200
    }
    Write-Host "::warning::virtaal.exe still running 10s after Stop-VirtaalTest - a later check may see a stale window"
}
