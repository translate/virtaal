# Builds dist\installer\virtaal-<version>-setup.exe from the standalone
# bundle build_standalone.ps1 produces - run that first.
#
# Needs Inno Setup's command-line compiler (iscc.exe) on PATH - install via
# https://jrsoftware.org/isdl.php or `choco install innosetup` (verified
# still actively maintained: 7.1.0 released August 2026, not a stale
# dependency to be wary of).

$ErrorActionPreference = "Stop"

$RepoRoot = (git rev-parse --show-toplevel)
Set-Location $RepoRoot

if (-not (Test-Path "dist\virtaal\virtaal.exe")) {
    Write-Error "dist\virtaal\virtaal.exe not found - run build_standalone.ps1 first."
    exit 1
}

$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    Write-Error "iscc.exe not found on PATH - install Inno Setup (https://jrsoftware.org/isdl.php) first."
    exit 1
}

$version = & python -c "from virtaal.__version__ import ver; print(ver)"

New-Item -ItemType Directory -Force -Path dist\installer | Out-Null

& iscc "/DMyAppVersion=$version" devsupport\packaging\windows\virtaal.iss

Write-Host "Built dist\installer\virtaal-$version-setup.exe"
