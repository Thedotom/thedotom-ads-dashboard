$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$reportRoot = Split-Path -Parent $repo
$python = "C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$target = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
$logDir = Join-Path $reportRoot "logs"
$log = Join-Path $logDir ("smartstore_product_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
$studioFile = Join-Path $reportRoot ("data\smartstore_sales\smartstore_product_sales_thedotom_{0}.xlsx" -f $target)
$muraFile = Join-Path $reportRoot ("data\smartstore_sales\smartstore_product_sales_mura_{0}.xlsx" -f $target)
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path $log -Append
try {
    & $python (Join-Path $repo "scripts\fetch_smartstore_product_performance_browser.py") --date $target --store all --headless
    if ($LASTEXITCODE -ne 0) { throw "SmartStore browser download failed" }
    & $python (Join-Path $repo "scripts\apply_studio_product_performance_20260710.py") $studioFile
    if ($LASTEXITCODE -ne 0) { throw "Studio product apply failed" }
    & $python (Join-Path $repo "scripts\apply_mura_product_performance.py") $muraFile
    if ($LASTEXITCODE -ne 0) { throw "Mura product apply failed" }
    $month = $target.Substring(0, 7)
    $targets = @("data/monthly-dashboard-$month.json", "data/monthly-dashboard-latest.json")
    git -C $repo add $targets
    $changes = git -C $repo diff --cached --name-only
    if ($changes) {
        git -C $repo commit -m ("Daily SmartStore product performance {0}" -f $target)
        if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
        git -C $repo push origin main
        if ($LASTEXITCODE -ne 0) { throw "git push failed" }
    }
} catch {
    Write-Error $_
    exit 1
} finally {
    Stop-Transcript
}
