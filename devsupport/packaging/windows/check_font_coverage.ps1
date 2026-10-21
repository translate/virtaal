# Checks that every shipped interface language displays in a built
# Windows bundle's fonts (#4421):
#   check_font_coverage.ps1 dist\virtaal [-Strict]
#
# Fails on a gap not in KNOWN_GAPS (virtaal/support/fontcoverage.py).
# A known gap that displays now is a warning, or with -Strict (the
# weekly run) a failure, so its entry is removed once fixed.

param(
    [Parameter(Mandatory = $true)][string]$Bundle,
    [switch]$Strict
)

$ErrorActionPreference = "Stop"

$result = & (Join-Path $PSScriptRoot "run_module.ps1") $Bundle virtaal.support.fontcoverage -TimeoutSeconds 240
if ($LASTEXITCODE) { exit 1 }
$result
$filled = @($result | Where-Object { $_ -match 'displays now' })
$filled | ForEach-Object { Write-Output "::warning::$_" }
if (-not ($result -match '^new: 0$')) {
    Write-Output "::error::Characters with no glyph, not in KNOWN_GAPS; see above"
    exit 1
}
if ($Strict -and $filled.Count) {
    Write-Output "::error::Known gaps display now; remove them from KNOWN_GAPS"
    exit 1
}
