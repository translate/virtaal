# Runs one of Virtaal's modules in a built Windows bundle and outputs
# what it wrote:
#   run_module.ps1 dist\virtaal virtaal.support.gettextpo [-TimeoutSeconds 60]
#
# virtaal.exe has no console, so the module writes to a file.

param(
    [Parameter(Mandatory = $true)][string]$Bundle,
    [Parameter(Mandatory = $true)][string]$Module,
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

$out = Join-Path ([System.IO.Path]::GetTempPath()) "$Module.txt"
$stacks = "$out.stacks"
Remove-Item $out, $stacks -ErrorAction SilentlyContinue
$env:VIRTAAL_STACK_DUMP = "$($TimeoutSeconds - 10):$stacks"
# Not Start-Process -Wait: that also waits for any process virtaal.exe
# leaves running.
$p = Start-Process -PassThru -FilePath (Join-Path $Bundle "virtaal.exe") -ArgumentList "--run-module", $Module, $out
$exited = $p.WaitForExit($TimeoutSeconds * 1000)
foreach ($child in Get-CimInstance Win32_Process -Filter "ParentProcessId = $($p.Id)") {
    Write-Host "::warning::virtaal.exe left $($child.Name) running: $($child.CommandLine)"
}
if (-not $exited) {
    $p.Refresh()
    Write-Host "Window: $($p.MainWindowTitle)"
    foreach ($log in $stacks, "$env:APPDATA\Virtaal\stdout_virtaal.log", "$env:APPDATA\Virtaal\stderr_virtaal.log") {
        Write-Host "--- $log ---"
        Get-Content $log -Tail 60 -ErrorAction SilentlyContinue | Write-Host
    }
    Stop-Process -Id $p.Id -Force
    Write-Host "::error::virtaal.exe --run-module $Module didn't exit in $TimeoutSeconds s (output written: $(Test-Path $out))"
    exit 1
}
Get-Content $out -Encoding utf8
exit 0
