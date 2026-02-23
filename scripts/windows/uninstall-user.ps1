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
$startupDir = [Environment]::GetFolderPath("Startup")

$startMenuShortcut = Join-Path $programsDir "odRepoMon Agent.lnk"
$startupShortcut = Join-Path $startupDir "odRepoMon Agent.lnk"

if (Test-Path -LiteralPath $startMenuShortcut) {
    Remove-Item -LiteralPath $startMenuShortcut -Force
}

if (Test-Path -LiteralPath $startupShortcut) {
    Remove-Item -LiteralPath $startupShortcut -Force
}

if (Test-Path -LiteralPath $installRoot) {
    Remove-Item -LiteralPath $installRoot -Recurse -Force
}

Write-Host "odRepoMon user uninstall complete."
Write-Host "Removed user shortcuts and installation at: $installRoot"