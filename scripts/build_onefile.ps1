param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$SpecFile = Join-Path $ProjectRoot "LocalFileConverter.spec"
$MainFile = Join-Path $ProjectRoot "main.py"
$VersionScript = Join-Path $ProjectRoot "scripts\generate_windows_version_info.py"
$TranslationsScript = Join-Path $ProjectRoot "scripts\build_translations.ps1"
$IconFile = Join-Path $ProjectRoot "resources\app_icon.ico"
$OutputExe = Join-Path $ProjectRoot "dist\LocalFileConverterOnefile.exe"

function Stop-Build($Message) {
    Write-Error $Message
    exit 1
}

if (-not (Test-Path (Join-Path $ProjectRoot ".venv"))) { Stop-Build "The .venv folder is missing." }
if (-not (Test-Path $PythonExe)) { Stop-Build ".venv\Scripts\python.exe is missing." }
if (-not (Test-Path $MainFile)) { Stop-Build "main.py is missing." }
if (-not (Test-Path $SpecFile)) { Stop-Build "LocalFileConverter.spec is missing." }
if (-not (Test-Path $TranslationsScript)) { Stop-Build "The translation build script is missing." }
if (-not (Test-Path $IconFile)) { Stop-Build "resources\app_icon.ico is missing; the icon is required for onefile builds." }
if ((Get-Item $IconFile).Length -le 0) { Stop-Build "resources\app_icon.ico is empty." }

& $PythonExe -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Stop-Build "PyInstaller is not installed. Run: .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
}

if (-not $SkipTests) {
    & $PythonExe -m pytest -q
    if ($LASTEXITCODE -ne 0) { Stop-Build "Tests failed; the onefile build was stopped." }
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $TranslationsScript
if ($LASTEXITCODE -ne 0) { Stop-Build "Translation compilation failed." }

& $PythonExe $VersionScript
if ($LASTEXITCODE -ne 0) { Stop-Build "Generating Windows version info failed." }

$env:LFC_BUILD_MODE = "release"
$env:LFC_BUILD_TARGET = "onefile"
& $PythonExe -m PyInstaller --clean --noconfirm $SpecFile
$buildExitCode = $LASTEXITCODE
Remove-Item Env:\LFC_BUILD_MODE -ErrorAction SilentlyContinue
Remove-Item Env:\LFC_BUILD_TARGET -ErrorAction SilentlyContinue

if ($buildExitCode -ne 0) { Stop-Build "The PyInstaller onefile build failed." }
if (-not (Test-Path $OutputExe)) { Stop-Build "The expected onefile EXE was not found: $OutputExe" }
if ((Get-Item $OutputExe).Length -le 0) { Stop-Build "The onefile EXE is empty: $OutputExe" }

Write-Host "Experimental onefile build is ready: $OutputExe"
