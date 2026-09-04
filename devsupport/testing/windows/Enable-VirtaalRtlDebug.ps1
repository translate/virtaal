<#
.SYNOPSIS
Generates the synthetic RTL debug catalog (devsupport/pseudo-
translation/generate_pseudo_translation.py's "fa" locale - see that
script's own docstring for what it is and why) directly into a
built/installed virtaal.exe's own directory, so the app can be
launched under it to check whether the whole UI chrome (menus,
toolbar, status bar - not just editor text) actually mirrors under a
right-to-left language. Doesn't launch Virtaal itself - that's a
manual step, since judging "does this look correctly mirrored" needs
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
$localeDir = Join-Path $exeDir "share\locale"

# Same generator bin/virtaal --pseudo-translation/--pseudo-translation-bidi
# use for a dev checkout - --localedir points it at the frozen bundle's
# own directory instead. Also (harmlessly) writes the pseudo/pseudo-bidi
# locales alongside "fa" - a small bonus, not a cost.
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py devsupport\pseudo-translation\generate_pseudo_translation.py --localedir $localeDir
if ($LASTEXITCODE -ne 0) {
    Write-Host "::error::generate_pseudo_translation.py failed - see above"
    exit 1
}

Write-Host ""
Write-Host "Installed the synthetic RTL debug catalog under:"
Write-Host "  $localeDir\fa\LC_MESSAGES\virtaal.mo"
Write-Host ""
Write-Host "To actually see it, launch manually (not automated - this needs a human looking at the result):"
Write-Host "  `$env:LANG = `"fa_IR.UTF-8`""
Write-Host "  `$env:LANGUAGE = `"fa`""
Write-Host "  & `"$ExePath`" devsupport\testfiles\checks.po"
Write-Host ""
Write-Host "Compare against a normal English launch side by side - does the whole window mirror (menu/toolbar/status-bar placement), not just the visibly-flipped text inside it?"
