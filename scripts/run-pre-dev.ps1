$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$AppDir = Join-Path $RootDir "web_app"
$RequirementsPath = Join-Path $AppDir "requirements.txt"
$VenvDir = Join-Path $AppDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Find-Python312 {
    $candidates = @(
        @{ Command = "py"; Args = @("-3.12") },
        @{ Command = (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"); Args = @() },
        @{ Command = "python"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        try {
            $versionArgs = @($candidate.Args + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"))
            $version = & $candidate.Command @versionArgs 2>$null
            if ($LASTEXITCODE -eq 0 -and "$version".Trim() -eq "3.12") {
                return $candidate
            }
        } catch {
            continue
        }
    }

    throw "Python 3.12 was not found. Install Python 3.12.10 for Windows, then run this file again."
}

if (!(Test-Path $AppDir)) {
    throw "Cannot find web_app directory at $AppDir"
}

if (!(Test-Path $RequirementsPath)) {
    throw "Cannot find requirements.txt at $RequirementsPath"
}

$Python312 = Find-Python312
Write-Host "Using Python 3.12:" $Python312.Command ($Python312.Args -join " ")

if (!(Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment at $VenvDir"
    $venvArgs = @($Python312.Args + @("-m", "venv", $VenvDir))
    & $Python312.Command @venvArgs
}

$VenvVersion = & $VenvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ("$VenvVersion".Trim() -ne "3.12") {
    throw "Existing venv uses Python $VenvVersion, not 3.12. Delete web_app\.venv and run this again."
}

Write-Host "Installing Python packages from web_app\requirements.txt"
& $VenvPython -m pip install --upgrade pip setuptools wheel
& $VenvPython -m pip install -r $RequirementsPath

try {
    & ffmpeg -version *> $null
} catch {
    Write-Warning "ffmpeg was not found on PATH. Speaking audio may fail to decode until ffmpeg is installed."
}

Write-Host "Development environment is ready. Start the app with scripts\run-dev.bat or scripts\run-dev.ps1."
