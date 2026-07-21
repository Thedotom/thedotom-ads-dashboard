$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$reportRoot = Split-Path -Parent $repo
$python = "C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$fetcher = "C:\Users\user\Documents\New project 4\scripts\fetch_naver_ads_raw.py"
$rawDir = Join-Path $reportRoot "raw"
$logDir = Join-Path $reportRoot "logs"
$today = Get-Date
$until = $today.AddDays(-1).ToString("yyyy-MM-dd")
$month = $today.ToString("yyyy-MM")
$since = "$month-01"
$raw = Join-Path $rawDir ("naver_ads_{0}_{1}_daily_raw.xlsx" -f $since.Replace("-", "_"), $until.Substring(8, 2))
$log = Join-Path $logDir ("daily_ad_routine_{0}.log" -f $today.ToString("yyyyMMdd_HHmmss"))
$dataTargets = @(
    "data/monthly-dashboard-$month.json",
    "data/monthly-dashboard-latest.json",
    "data/naver-bid-snapshot.json"
)

New-Item -ItemType Directory -Force -Path $rawDir, $logDir | Out-Null
Start-Transcript -Path $log -Append
try {
    $targetChanges = git -C $repo status --porcelain -- $dataTargets
    if ($LASTEXITCODE -ne 0) { throw "git status failed" }
    if ($targetChanges) {
        throw "Dashboard data files have local changes. Commit or restore only these files before retrying: $($dataTargets -join ', ')"
    }

    git -C $repo fetch origin main
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }

    $behindCount = [int](git -C $repo rev-list --count HEAD..origin/main)
    if ($LASTEXITCODE -ne 0) { throw "git revision check failed" }
    if ($behindCount -gt 0) {
        $worktreeChanges = git -C $repo status --porcelain
        if ($LASTEXITCODE -ne 0) { throw "git status failed" }
        if ($worktreeChanges) {
            throw "origin/main is ahead by $behindCount commit(s), and unrelated local changes prevent a safe rebase. Commit those changes before retrying."
        }
        git -C $repo rebase origin/main
        if ($LASTEXITCODE -ne 0) { throw "git rebase failed" }
    } else {
        Write-Host "Repository is current; unrelated local changes will be left untouched."
    }

    & $python $fetcher --since $since --until $until --output $raw
    if ($LASTEXITCODE -ne 0) { throw "Naver performance fetch failed" }

    & $python (Join-Path $repo "scripts\apply_naver_ads_month.py") --month $month --raw $raw --data-dir (Join-Path $repo "data")
    if ($LASTEXITCODE -ne 0) { throw "Dashboard performance apply failed" }

    Copy-Item -LiteralPath (Join-Path $repo "data\monthly-dashboard-$month.json") -Destination (Join-Path $repo "data\monthly-dashboard-latest.json") -Force
    & $python (Join-Path $repo "scripts\update_naver_bid_snapshot.py")
    if ($LASTEXITCODE -ne 0) { throw "Bid snapshot update failed" }

    git -C $repo add $dataTargets
    $changes = git -C $repo diff --cached --name-only
    if ($changes) {
        git -C $repo commit -m ("Daily ads and bids update {0}" -f $today.ToString("yyyy-MM-dd"))
        if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
        git -C $repo push origin main
        if ($LASTEXITCODE -ne 0) { throw "git push failed" }
    } else {
        Write-Host "No dashboard changes to deploy."
    }
} catch {
    Write-Error $_
    exit 1
} finally {
    Stop-Transcript
}
