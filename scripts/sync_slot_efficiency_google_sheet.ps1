param(
    [string]$SheetId = "1JEW2j1kRDo5P0sIEJQxXlGgk9Ao3NaHc_6B9eMhBAxM"
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$reportRoot = Split-Path -Parent $repo
$python = "C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$tempDir = Join-Path $reportRoot "temp"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$download = Join-Path $tempDir ("slot_efficiency_google_sheet_{0}.xlsx" -f $stamp)
$backupDir = Join-Path $tempDir ("slot_efficiency_backup_{0}" -f $stamp)
$exportUrl = "https://docs.google.com/spreadsheets/d/$SheetId/export?format=xlsx"

New-Item -ItemType Directory -Force -Path $tempDir, $backupDir | Out-Null
$targets = @(
    Get-ChildItem -LiteralPath (Join-Path $repo "data") -File |
        Where-Object { $_.Name -match '^monthly-dashboard-20\d{2}-\d{2}\.json$' }
)
$targets += Get-Item -LiteralPath (Join-Path $repo "data\monthly-dashboard-latest.json")
foreach ($target in $targets) {
    Copy-Item -LiteralPath $target.FullName -Destination (Join-Path $backupDir $target.Name) -Force
}
try {
    Write-Host "Downloading slot efficiency Google Sheet..."
    Invoke-WebRequest -Uri $exportUrl -OutFile $download
    $file = Get-Item -LiteralPath $download
    if ($file.Length -lt 10000) {
        throw "Downloaded Google Sheet is unexpectedly small: $($file.Length) bytes"
    }

    & $python (Join-Path $repo "scripts\apply_slot_efficiency_analysis.py") $download
    if ($LASTEXITCODE -ne 0) {
        throw "Slot efficiency analysis apply failed"
    }
    Write-Host ("Slot efficiency Google Sheet sync completed: {0:N0} bytes" -f $file.Length)
} catch {
    foreach ($target in $targets) {
        $backup = Join-Path $backupDir $target.Name
        if (Test-Path -LiteralPath $backup) {
            Copy-Item -LiteralPath $backup -Destination $target.FullName -Force
        }
    }
    throw
} finally {
    if (Test-Path -LiteralPath $download) {
        Remove-Item -LiteralPath $download -Force
    }
    if (Test-Path -LiteralPath $backupDir) {
        Remove-Item -LiteralPath $backupDir -Recurse -Force
    }
}
