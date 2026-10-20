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

# virtaal.exe has no console, so it writes to a file.
$out = Join-Path ([System.IO.Path]::GetTempPath()) "fontcoverage.txt"
Start-Process -Wait -FilePath (Join-Path $Bundle "virtaal.exe") -ArgumentList "--run-module", "virtaal.support.fontcoverage", $out
$result = Get-Content $out -Encoding utf8
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
