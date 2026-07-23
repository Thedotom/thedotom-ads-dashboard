$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$reportRoot = Split-Path -Parent $repo
$logDir = Join-Path $reportRoot "logs"
$today = Get-Date
$log = Join-Path $logDir ("slot_efficiency_daily_{0}.log" -f $today.ToString("yyyyMMdd_HHmmss"))
$monthlyTargets = @(
    Get-ChildItem -LiteralPath (Join-Path $repo "data") -File |
        Where-Object { $_.Name -match '^monthly-dashboard-20\d{2}-\d{2}\.json$' } |
        ForEach-Object { "data/$($_.Name)" }
)
$dataTargets = @(
    $monthlyTargets
    "data/monthly-dashboard-latest.json"
    "data/powerlink-creative-config.json"
) | Select-Object -Unique

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path $log -Append
try {
    $targetChanges = git -C $repo status --porcelain -- $dataTargets
    if ($LASTEXITCODE -ne 0) { throw "git status failed" }
    if ($targetChanges) {
        throw "Slot dashboard data files have local changes. Commit or restore them before retrying."
    }

    git -C $repo fetch origin main
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }

    $behindCount = [int](git -C $repo rev-list --count HEAD..origin/main)
    if ($LASTEXITCODE -ne 0) { throw "git revision check failed" }
    if ($behindCount -gt 0) {
        $worktreeChanges = git -C $repo status --porcelain
        if ($LASTEXITCODE -ne 0) { throw "git status failed" }
        if ($worktreeChanges) {
            throw "origin/main is ahead by $behindCount commit(s), and local changes prevent a safe rebase."
        }
        git -C $repo rebase origin/main
        if ($LASTEXITCODE -ne 0) { throw "git rebase failed" }
    }

    & python (Join-Path $repo "scripts\sync_powerlink_creative_config.py")
    if ($LASTEXITCODE -ne 0) { throw "Powerlink creative configuration sync failed" }

    & (Join-Path $repo "scripts\sync_slot_efficiency_google_sheet.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Slot efficiency Google Sheet sync failed" }

    git -C $repo add $dataTargets
    $changes = git -C $repo diff --cached --name-only
    if ($changes) {
        git -C $repo commit -m ("Daily slot efficiency update {0}" -f $today.ToString("yyyy-MM-dd"))
        if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
        git -C $repo push origin main
        if ($LASTEXITCODE -ne 0) { throw "git push failed" }
    } else {
        Write-Host "No slot efficiency changes to deploy."
    }
} catch {
    Write-Error $_
    exit 1
} finally {
    Stop-Transcript
}
