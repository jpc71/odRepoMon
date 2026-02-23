param(
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $Force) {
    $answer = Read-Host "Remove odRepoMon user install and shortcuts? (y/N)"
    if ($answer -notin @("y", "Y", "yes", "YES")) {
        Write-Host "Uninstall cancelled."
        exit 0
    }
}

$installRoot = Join-Path $env:LOCALAPPDATA "odRepoMon"
$programsDir = [Environment]::GetFolderPath("Programs")

$startMenuShortcut = Join-Path $programsDir "odRepoMon Agent.lnk"
$taskName = "odRepoMon Agent - Startup"

if (Test-Path -LiteralPath $startMenuShortcut) {
    Remove-Item -LiteralPath $startMenuShortcut -Force
}

$taskExists = $false
try {
    $null = schtasks /query /tn "$taskName" 2>&1
    if ($LASTEXITCODE -eq 0) {
        $taskExists = $true
    }
} catch {
    $taskExists = $false
}

if ($taskExists) {
    $null = schtasks /delete /tn "$taskName" /f 2>&1
}

if (Test-Path -LiteralPath $installRoot) {
    Remove-Item -LiteralPath $installRoot -Recurse -Force
}

Write-Host "odRepoMon user uninstall complete."
Write-Host "Removed shortcuts, scheduled task, and installation at: $installRoot"