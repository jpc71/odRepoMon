param(
    [string]$SourcePath = "",
    [string]$ConfigPath = "",
    [switch]$EnableStartup,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-PythonCommand {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @("py", "-3")
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @($python.Source)
    }

    throw "Python was not found. Install Python 3.10+ and re-run this installer."
}

    function Invoke-Python {
        param(
            [Parameter(Mandatory = $true)][string[]]$Command,
            [Parameter(Mandatory = $true)][string[]]$Arguments
        )

        if ($Command.Length -gt 1) {
            & $Command[0] $Command[1..($Command.Length - 1)] @Arguments
            return
        }
        & $Command[0] @Arguments
    }

function New-ShortcutFile {
    param(
        [Parameter(Mandatory = $true)][string]$ShortcutPath,
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [string]$IconLocation = ""
    )

    $shortcutDirectory = Split-Path -Parent $ShortcutPath
    if (-not (Test-Path -LiteralPath $shortcutDirectory)) {
        New-Item -ItemType Directory -Path $shortcutDirectory -Force | Out-Null
    }

    $wsh = New-Object -ComObject WScript.Shell
    $shortcut = $wsh.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $TargetPath
    $shortcut.WorkingDirectory = $WorkingDirectory
    if ($IconLocation) {
        $shortcut.IconLocation = $IconLocation
    }
    $shortcut.Save()
}

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $SourcePath) {
    $SourcePath = Resolve-Path (Join-Path $scriptDirectory "..\..")
}
$resolvedSourcePath = (Resolve-Path $SourcePath).Path

$installRoot = Join-Path $env:LOCALAPPDATA "odRepoMon"
$venvPath = Join-Path $installRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvPythonw = Join-Path $venvPath "Scripts\pythonw.exe"
$launcherPath = Join-Path $installRoot "Launch-odRepoMon-Agent.cmd"

if (-not $ConfigPath) {
    $ConfigPath = Join-Path $installRoot "mirror-config.yaml"
}

if (-not (Test-Path -LiteralPath $installRoot)) {
    New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
}

$existingInstall = (Test-Path -LiteralPath $venvPython) -or (Test-Path -LiteralPath $launcherPath)
if ($existingInstall -and (-not $Force)) {
    $answer = Read-Host "Existing user install detected at $installRoot. Continue and refresh launcher/environment? (y/N)"
    if ($answer -notin @("y", "Y", "yes", "YES")) {
        Write-Host "Install cancelled."
        exit 0
    }
}

$pythonCommand = Resolve-PythonCommand
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating user virtual environment at $venvPath"
    Invoke-Python -Command $pythonCommand -Arguments @("-m", "venv", $venvPath)
}

Write-Host "Installing odRepoMon into user environment"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip in user environment (exit code: $LASTEXITCODE)."
}
& $venvPython -m pip install --upgrade $resolvedSourcePath
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install odRepoMon from source path '$resolvedSourcePath' (exit code: $LASTEXITCODE)."
}

$sourceConfig = Join-Path $resolvedSourcePath "mirror-config.yaml"
if ((-not (Test-Path -LiteralPath $ConfigPath)) -and (Test-Path -LiteralPath $sourceConfig)) {
    Copy-Item -Path $sourceConfig -Destination $ConfigPath -Force
}

$launcherContent = @"
@echo off
setlocal
set ODR_CONFIG=$ConfigPath
if not exist "%ODR_CONFIG%" (
  echo Config file not found: %ODR_CONFIG%
  pause
  exit /b 1
)
echo Starting odRepoMon Agent...
echo Look for the tray icon in your notification area (bottom-right taskbar)
timeout /t 2 /nobreak >nul
start "odRepoMon Agent" "$venvPythonw" -m odrepomon.cli agent --config "%ODR_CONFIG%"
"@
$launcherContent | Set-Content -Path $launcherPath -Encoding ASCII

$programsDir = [Environment]::GetFolderPath("Programs")
$startMenuShortcut = Join-Path $programsDir "odRepoMon Agent.lnk"

New-ShortcutFile -ShortcutPath $startMenuShortcut -TargetPath $launcherPath -WorkingDirectory $installRoot -IconLocation "$env:SystemRoot\System32\shell32.dll,44"

$taskName = "odRepoMon Agent - Startup"
$taskExists = $false
try {
    $null = schtasks /query /tn "$taskName" 2>&1
    if ($LASTEXITCODE -eq 0) {
        $taskExists = $true
    }
} catch {
    $taskExists = $false
}

if ($EnableStartup) {
    if ($taskExists) {
        $null = schtasks /delete /tn "$taskName" /f 2>&1
    }
    
    $null = schtasks /create /tn "$taskName" /tr "`"$launcherPath`"" /sc onlogon /rl limited /f 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Created logon task: $taskName"
    } else {
        Write-Warning "Failed to create logon task (exit code: $LASTEXITCODE)"
    }
} else {
    if ($taskExists) {
        $null = schtasks /delete /tn "$taskName" /f 2>&1
    }
}

Write-Host ""
Write-Host "odRepoMon user install complete."
Write-Host "Launcher: $launcherPath"
Write-Host "Start Menu: $startMenuShortcut"
Write-Host "Config: $ConfigPath"
if ($EnableStartup) {
    Write-Host "Logon task: enabled"
} else {
    Write-Host "Logon task: disabled"
}