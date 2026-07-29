$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = "C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$target = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
$month = $target.Substring(0, 7)
$logDir = Join-Path (Split-Path -Parent $repo) "logs"
$log = Join-Path $logDir ("daily_complete_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path $log -Append
try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo "scripts\run_daily_ad_routine.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Daily ads and sales routine failed" }

    & $python (Join-Path $repo "scripts\run_cafe24_product_performance_safe.py") $target
    if ($LASTEXITCODE -ne 0) { throw "Cafe24 product performance fetch failed" }

    $targets = @(
        "data/monthly-dashboard-$month.json"
        "data/monthly-dashboard-latest.json"
    )
    git -C $repo add $targets
    $changes = git -C $repo diff --cached --name-only
    if ($changes) {
        git -C $repo commit -m ("Daily Cafe24 product performance {0}" -f $target)
        if ($LASTEXITCODE -ne 0) { throw "Cafe24 product commit failed" }
        git -C $repo push origin main
        if ($LASTEXITCODE -ne 0) { throw "Cafe24 product push failed" }
    } else {
        Write-Host "No Cafe24 product changes to deploy."
    }
} catch {
    Write-Error $_
    exit 1
} finally {
    Stop-Transcript
}
