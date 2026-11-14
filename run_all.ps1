# Runs the whole pipeline (BUILD_SPEC 13.1). -Quick uses small N (smoke-quality numbers).
param([switch]$Quick)
Set-Location $PSScriptRoot
$py = ".\.venv\Scripts\python.exe"
$n = if ($Quick) { 20 } else { 200 }
$nTest = if ($Quick) { 30 } else { 300 }
$suite = if ($Quick) { "quick" } else { "full" }
$steps = @(
    @("setup-check"),
    @("PYTEST"),
    @("synth", "--split", "cal", "--n", "$n", "--kinds", "normal,normal,normal,normal,normal,normal,normal,damage,damage,damage"),
    @("synth", "--split", "arb", "--n", "$n", "--kinds", "normal"),
    @("synth", "--split", "test", "--n", "$nTest", "--kinds", "normal"),
    @("synth", "--split", "demo", "--n", "10", "--kinds", "normal"),
    @("calibrate", "--n-cal", "$(if ($Quick) { 40 } else { 200 })"),
    @("train-arbiter", "--n", "$n"),
    @("demo-bundles"),
    @("eval", "--suite", $suite),
    @("figures"),
    @("report")
)
foreach ($s in $steps) {
    Write-Host "`n=== $($s -join ' ') ===" -ForegroundColor Cyan
    if ($s[0] -eq "PYTEST") { & $py -m pytest } else { & $py -m lightaudit.cli @s }
    if ($LASTEXITCODE -ne 0) { Write-Host "step failed: $($s -join ' ') (continuing)" -ForegroundColor Yellow }
}
Write-Host "`nDone. Start the viewer:  $py -m lightaudit.cli serve   then open http://127.0.0.1:8000"
