$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$AppDir = Join-Path $RootDir "web_app"
$VenvDir = Join-Path $AppDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (!(Test-Path $AppDir)) {
    throw "Cannot find web_app directory at $AppDir"
}

if (!(Test-Path $VenvPython)) {
    throw "Virtual environment was not found at $VenvDir. Run scripts\run-pre-dev.bat or scripts\run-pre-dev.ps1 first."
}

$VenvVersion = & $VenvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ("$VenvVersion".Trim() -ne "3.12") {
    throw "Existing venv uses Python $VenvVersion, not 3.12. Delete web_app\.venv and run this again."
}

try {
    & ffmpeg -version *> $null
} catch {
    Write-Warning "ffmpeg was not found on PATH. Speaking audio may fail to decode until ffmpeg is installed."
}

Write-Host "Starting Flask dev server..."
Push-Location $AppDir
try {
    & $VenvPython app.py
} finally {
    Pop-Location
}
