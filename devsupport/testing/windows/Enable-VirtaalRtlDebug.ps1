<#
.SYNOPSIS
Compiles devsupport/testing/rtl-debug.po (a synthetic RTL translation of
Virtaal's own UI catalog - see that file's own header for what it is and
why) and installs it into a built/installed virtaal.exe's own directory,
so the app can be launched under it to check whether the whole UI chrome
(menus, toolbar, status bar - not just editor text) actually mirrors
under a right-to-left language. Doesn't launch Virtaal itself - that's
a manual step, since judging "does this look correctly mirrored" needs
a human looking at it, not something this battery's usual title-bar/
log-content checks can verify.

Windows specifically (not macOS/Linux): virtaal/common/pan_app.py only
calls fix_libintl() - the piece that binds GLib/GTK's own C-level
gettext lookup to this app's own share/locale directory, which is what
.ui-file-defined widget translations (and, more importantly here, GTK's
own RTL direction detection) actually depend on - when
`os.name == 'nt' and getattr(sys, 'frozen', False)`. A frozen Windows
build is the only place this mechanism is actually wired up and
exercised; reproducing this on a raw dev checkout on another platform
would be fighting unrelated, unexercised complexity.

.PARAMETER ExePath
Path to an already-built/installed virtaal.exe (e.g.
.\dist\virtaal\virtaal.exe, or wherever Install-Virtaal put it) whose
own directory this installs the debug catalog next to.

.EXAMPLE
.\devsupport\testing\windows\Enable-VirtaalRtlDebug.ps1 -ExePath .\dist\virtaal\virtaal.exe
# then, manually:
$env:LANG = "fa_IR.UTF-8"
$env:LANGUAGE = "fa"
& .\dist\virtaal\virtaal.exe devsupport\testfiles\checks.po
#>
param(
    [Parameter(Mandatory)][string]$ExePath
)

$ErrorActionPreference = "Stop"
$RepoRoot = (git rev-parse --show-toplevel)
Set-Location $RepoRoot

if (-not (Test-Path $ExePath)) {
    Write-Host "::error::$ExePath not found - build or install Virtaal first"
    exit 1
}

$exeDir = Split-Path -Parent (Resolve-Path $ExePath)
$targetDir = Join-Path $exeDir "share\locale\fa\LC_MESSAGES"
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
$targetMo = Join-Path $targetDir "virtaal.mo"

# Same pure-Python compiler setup.py's own mo-compile step uses
# (translate.tools.pocompile.convertmo) - no external msgfmt.exe needed,
# guaranteed available anywhere Virtaal itself can run since
# translate-toolkit is already a hard dependency.
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py -c @"
from translate.tools.pocompile import convertmo
with open('devsupport/testing/rtl-debug.po', encoding='utf-8') as inf, open(r'$targetMo', 'w') as outf:
    convertmo(inf, outf, None)
print('Compiled', len(open(r'$targetMo', 'rb').read()), 'bytes to', r'$targetMo')
"@
if ($LASTEXITCODE -ne 0) {
    Write-Host "::error::Compiling rtl-debug.po failed - see above"
    exit 1
}

Write-Host ""
Write-Host "Installed the synthetic RTL debug catalog at:"
Write-Host "  $targetMo"
Write-Host ""
Write-Host "To actually see it, launch manually (not automated - this needs a human looking at the result):"
Write-Host "  `$env:LANG = `"fa_IR.UTF-8`""
Write-Host "  `$env:LANGUAGE = `"fa`""
Write-Host "  & `"$ExePath`" devsupport\testfiles\checks.po"
Write-Host ""
Write-Host "Compare against a normal English launch side by side - does the whole window mirror (menu/toolbar/status-bar placement), not just the visibly-flipped text inside it?"
