# Reusable PowerShell helpers for installing and uninstalling Virtaal's
# real Inno Setup package (dist\installer\*.exe / a downloaded
# Virtaal-windows-installer artifact) on a Windows box - as opposed to
# devsupport\testing\windows\virtaal_ui_test_helpers.ps1, which drives
# the raw, unpacked PyInstaller bundle (dist\virtaal\virtaal.exe) that
# CI's build-windows-installer job tests directly. Neither CI nor that
# helpers file ever exercises the actual installer/uninstaller - which
# matters, because at least one real report ("the unsaved marker seems
# to persist between reinstalls") was specifically about behaviour
# across an install/uninstall/reinstall cycle, something a bundle-only
# check structurally cannot catch. Built so that cycle can be driven
# reliably and repeatably on a real Windows machine instead of by hand
# each time.
#
# Usage: dot-source this file, then call the functions below.
#   . .\devsupport\testing\windows\virtaal_install_helpers.ps1
#   Uninstall-Virtaal | Out-Null                      # clean slate, idempotent
#   $install = Install-Virtaal                         # auto-discovers dist\installer\*.exe
#   if (-not $install) { exit 1 }                       # already logged why
#   # ... drive $install.ExePath with virtaal_ui_test_helpers.ps1 ...
#   Uninstall-Virtaal | Out-Null                        # tear down again

# Must match virtaal.iss's [Setup] AppId exactly (with the outer {{ }}
# un-escaped back to a single pair of braces - Inno's .iss syntax uses
# {{ to write a literal { into AppId, so the GUID Inno actually writes
# into the registry key name is just {B3B6...}, not {{B3B6...}}).
$script:VirtaalAppId = '{B3B6E6A0-6E8B-4B6C-9C7E-3C6F6E6E6E6E}'

function Find-VirtaalUninstallEntry {
    <#
    .SYNOPSIS
    Looks up Virtaal's Inno Setup uninstall registry entry by AppId,
    checking both the per-user location (PrivilegesRequired=lowest in
    virtaal.iss means a plain install lands in HKCU, not HKLM) and the
    machine-wide locations (in case the installer's "install for all
    users" option was used instead) - rather than assuming one location,
    so this works regardless of which the tester chose. Returns $null if
    Virtaal isn't currently installed at all.
    #>
    $keyName = "$($script:VirtaalAppId)_is1"
    $candidates = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$keyName",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$keyName",
        "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\$keyName"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) {
            $props = Get-ItemProperty -Path $path -ErrorAction SilentlyContinue
            if ($props -and $props.UninstallString) {
                return [PSCustomObject]@{
                    RegistryPath    = $path
                    UninstallString = $props.UninstallString
                    InstallLocation = $props.InstallLocation
                    DisplayVersion  = $props.DisplayVersion
                }
            }
        }
    }
    return $null
}

function Get-VirtaalInstallInfo {
    <#
    .SYNOPSIS
    Read-only status check: is Virtaal currently installed, from where,
    and what version - without side effects. Thin wrapper so callers
    don't need to know the registry-lookup details of
    Find-VirtaalUninstallEntry.
    #>
    $entry = Find-VirtaalUninstallEntry
    if (-not $entry) {
        return [PSCustomObject]@{ Installed = $false }
    }
    return [PSCustomObject]@{
        Installed       = $true
        ExePath         = Join-Path $entry.InstallLocation "virtaal.exe"
        InstallLocation = $entry.InstallLocation
        Version         = $entry.DisplayVersion
    }
}

function Uninstall-Virtaal {
    <#
    .SYNOPSIS
    Silently and idempotently uninstalls Virtaal. Returns $true if
    Virtaal ends up not installed (whether or not it was installed to
    begin with) and $false if an uninstall was attempted but didn't
    complete within the timeout - callers should treat that as a hard
    failure, not proceed to install on top of a half-removed copy.
    #>
    param([int]$TimeoutSeconds = 60)

    $entry = Find-VirtaalUninstallEntry
    if (-not $entry) {
        Write-Host "Virtaal is not currently installed - nothing to uninstall."
        return $true
    }

    # An uninstall can't remove a locked virtaal.exe, and /VERYSILENT
    # would otherwise just fail quietly rather than prompt to close it.
    Get-Process -Name virtaal -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

    $uninstExe = $entry.UninstallString.Trim('"')
    if (-not (Test-Path $uninstExe)) {
        Write-Host "::error::Uninstall registry entry points at a missing file: $uninstExe (a previous uninstall may have been interrupted). Remove $($entry.RegistryPath) by hand and retry."
        return $false
    }

    Write-Host "Uninstalling Virtaal $($entry.DisplayVersion) via $uninstExe ..."
    Start-Process -FilePath $uninstExe -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -Wait -ErrorAction SilentlyContinue

    # Inno Setup's uninstaller relaunches a copy of itself out of a temp
    # dir so it can delete the original unins000.exe, then exits - so the
    # process -Wait above returns before that copy has necessarily
    # finished deleting files and removing the registry key. Poll for the
    # registry key's actual removal (the last thing Inno's uninstaller
    # does) instead of trusting -Wait alone.
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Find-VirtaalUninstallEntry)) {
            Write-Host "Uninstall confirmed (registry entry gone)."
            return $true
        }
        Start-Sleep -Milliseconds 500
    }

    Write-Host "::error::Uninstall did not complete within ${TimeoutSeconds}s - registry entry still present at $($entry.RegistryPath)"
    return $false
}

function Install-Virtaal {
    <#
    .SYNOPSIS
    Silently installs Virtaal from an Inno Setup installer .exe. With no
    -InstallerPath, auto-discovers the newest .exe under dist\installer
    (devsupport\packaging\windows\build_installer.ps1's own output dir),
    dist\Virtaal-windows-installer (only if you deliberately downloaded a
    CI artifact into a same-named subfolder), or a flat dist\*.exe -
    `gh run download <run> -n Virtaal-windows-installer -D dist` (the
    README's own documented example) doesn't create a
    Virtaal-windows-installer subfolder at all, it extracts straight
    into dist\ - the artifact's upload path was
    dist\installer\*.exe on the CI side, but actions/upload-artifact
    doesn't preserve that directory structure, so gh run download's -D
    is the *only* directory involved, not -D plus the artifact name.
    Both patterns are kept (rather than fixing just the flat one) so a
    deliberately-organised download into a same-named subfolder still
    works too. Defaults -Tasks to disabling both optional installer
    tasks (desktop icon, file associations) so repeated test-cycle
    installs don't spam a real desktop or overwrite real file
    associations on a tester's own machine - pass an explicit -Tasks to
    opt back in.

    Returns $null (with an ::error:: already written) on any failure, or
    a PSCustomObject with ExePath/InstallLocation/Version/LogPath on
    success - pass .ExePath straight to virtaal_ui_test_helpers.ps1's
    Start-VirtaalTest -ExePath.
    #>
    param(
        [string]$InstallerPath,
        [string]$Tasks = "!desktopicon,!fileassoc",
        [int]$TimeoutSeconds = 120
    )

    if (-not $InstallerPath) {
        $candidates = @(Get-ChildItem -Path "dist\installer\*.exe", "dist\Virtaal-windows-installer\*.exe", "dist\*.exe" -ErrorAction SilentlyContinue) |
            Sort-Object LastWriteTime -Descending
        if (-not $candidates) {
            Write-Host "::error::No installer .exe found under dist\installer, dist\Virtaal-windows-installer, or flat under dist - build one (devsupport\packaging\windows\build_installer.ps1) or download a Virtaal-windows-installer CI artifact first (gh run download <run> -n Virtaal-windows-installer -D dist), or pass -InstallerPath explicitly."
            return $null
        }
        $InstallerPath = $candidates[0].FullName
    }
    if (-not (Test-Path $InstallerPath)) {
        Write-Host "::error::Installer not found at $InstallerPath"
        return $null
    }

    $logPath = Join-Path $env:TEMP "virtaal-install-$(Get-Date -Format 'yyyyMMddHHmmss').log"
    Write-Host "Installing $InstallerPath (log: $logPath) ..."
    $proc = Start-Process -FilePath $InstallerPath `
        -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/TASKS=`"$Tasks`"", "/LOG=`"$logPath`"" `
        -PassThru -Wait

    if ($proc.ExitCode -ne 0) {
        Write-Host "::error::Installer exited with code $($proc.ExitCode)"
        if (Test-Path $logPath) { Get-Content $logPath }
        return $null
    }

    $entry = Find-VirtaalUninstallEntry
    if (-not $entry) {
        Write-Host "::error::Installer reported success (exit 0) but no uninstall registry entry was found afterwards"
        if (Test-Path $logPath) { Get-Content $logPath }
        return $null
    }
    $exePath = Join-Path $entry.InstallLocation "virtaal.exe"
    if (-not (Test-Path $exePath)) {
        Write-Host "::error::virtaal.exe not found at expected install location $exePath"
        return $null
    }

    Write-Host "Installed Virtaal $($entry.DisplayVersion) at $exePath"
    return [PSCustomObject]@{
        ExePath         = $exePath
        InstallLocation = $entry.InstallLocation
        Version         = $entry.DisplayVersion
        LogPath         = $logPath
    }
}
