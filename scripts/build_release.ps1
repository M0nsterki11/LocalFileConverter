param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$SpecFile = Join-Path $ProjectRoot "LocalFileConverter.spec"
$MainFile = Join-Path $ProjectRoot "main.py"
$BuildHelpers = Join-Path $ProjectRoot "scripts\build_helpers.ps1"
$VersionScript = Join-Path $ProjectRoot "scripts\generate_windows_version_info.py"
$TranslationsScript = Join-Path $ProjectRoot "scripts\build_translations.ps1"
$VerifyScript = Join-Path $ProjectRoot "scripts\verify_build.py"
$IconFile = Join-Path $ProjectRoot "resources\app_icon.ico"
$OutputExe = Join-Path $ProjectRoot "dist\LocalFileConverter\LocalFileConverter.exe"

function Stop-Build($Message) {
    Write-Error $Message
    exit 1
}

if (-not (Test-Path (Join-Path $ProjectRoot ".venv"))) { Stop-Build "The .venv folder is missing." }
if (-not (Test-Path $PythonExe)) { Stop-Build ".venv\Scripts\python.exe is missing." }
if (-not (Test-Path $MainFile)) { Stop-Build "main.py is missing." }
if (-not (Test-Path $SpecFile)) { Stop-Build "LocalFileConverter.spec is missing." }
if (-not (Test-Path $BuildHelpers)) { Stop-Build "scripts\build_helpers.ps1 is missing." }
if (-not (Test-Path $VersionScript)) { Stop-Build "The Windows version info generator is missing." }
if (-not (Test-Path $TranslationsScript)) { Stop-Build "The translation build script is missing." }

. $BuildHelpers

& $PythonExe -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Stop-Build "PyInstaller is not installed. Run: .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
}

if (-not (Test-Path $IconFile)) { Stop-Build "resources\app_icon.ico is missing; the icon is required for release builds." }
if ((Get-Item $IconFile).Length -le 0) { Stop-Build "resources\app_icon.ico is empty." }

if (-not $SkipTests) {
    Invoke-ProjectPytest -PythonExe $PythonExe -ProjectRoot $ProjectRoot -PytestArgs @("-q")
    if ($LASTEXITCODE -ne 0) { Stop-Build "Tests failed; the release build was stopped." }
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $TranslationsScript
if ($LASTEXITCODE -ne 0) { Stop-Build "Translation compilation failed." }

& $PythonExe $VersionScript
if ($LASTEXITCODE -ne 0) { Stop-Build "Generating Windows version info failed." }

$env:LFC_BUILD_MODE = "release"
$env:LFC_BUILD_TARGET = "onedir"
& $PythonExe -m PyInstaller --clean --noconfirm $SpecFile
$buildExitCode = $LASTEXITCODE
Remove-Item Env:\LFC_BUILD_MODE -ErrorAction SilentlyContinue
Remove-Item Env:\LFC_BUILD_TARGET -ErrorAction SilentlyContinue

if ($buildExitCode -ne 0) { Stop-Build "The PyInstaller release build failed." }
if (-not (Test-Path $OutputExe)) { Stop-Build "The expected EXE was not found: $OutputExe" }

& $PythonExe $VerifyScript --bundle (Join-Path $ProjectRoot "dist\LocalFileConverter") --name "LocalFileConverter"
if ($LASTEXITCODE -ne 0) { Stop-Build "Build verification failed." }

Write-Host "Release build is ready: $OutputExe"
