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
$VerifyScript = Join-Path $ProjectRoot "scripts\verify_build.py"
$IconFile = Join-Path $ProjectRoot "resources\app_icon.ico"
$OutputExe = Join-Path $ProjectRoot "dist\LocalFileConverter\LocalFileConverter.exe"

function Stop-Build($Message) {
    Write-Error $Message
    exit 1
}

if (-not (Test-Path (Join-Path $ProjectRoot ".venv"))) { Stop-Build "Nedostaje .venv mapa." }
if (-not (Test-Path $PythonExe)) { Stop-Build "Nedostaje .venv\Scripts\python.exe." }
if (-not (Test-Path $MainFile)) { Stop-Build "Nedostaje main.py." }
if (-not (Test-Path $SpecFile)) { Stop-Build "Nedostaje LocalFileConverter.spec." }
if (-not (Test-Path $VersionScript)) { Stop-Build "Nedostaje generator version info datoteke." }

& $PythonExe -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Stop-Build "PyInstaller nije instaliran. Pokreni: .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
}

if (-not (Test-Path $IconFile)) {
    Write-Warning "resources\app_icon.ico nije pronaden; build ce koristiti fallback ikonu."
}

if (-not $SkipTests) {
    & $PythonExe -m pytest -q
    if ($LASTEXITCODE -ne 0) { Stop-Build "Testovi ne prolaze; release build je zaustavljen." }
}

& $PythonExe $VersionScript
if ($LASTEXITCODE -ne 0) { Stop-Build "Generiranje Windows version info datoteke nije uspjelo." }

$env:LFC_BUILD_MODE = "release"
$env:LFC_BUILD_TARGET = "onedir"
& $PythonExe -m PyInstaller --clean --noconfirm $SpecFile
$buildExitCode = $LASTEXITCODE
Remove-Item Env:\LFC_BUILD_MODE -ErrorAction SilentlyContinue
Remove-Item Env:\LFC_BUILD_TARGET -ErrorAction SilentlyContinue

if ($buildExitCode -ne 0) { Stop-Build "PyInstaller release build nije uspio." }
if (-not (Test-Path $OutputExe)) { Stop-Build "Ocekivani EXE nije pronaden: $OutputExe" }

& $PythonExe $VerifyScript --bundle (Join-Path $ProjectRoot "dist\LocalFileConverter") --name "LocalFileConverter"
if ($LASTEXITCODE -ne 0) { Stop-Build "Build verification nije prosao." }

Write-Host "Release build je spreman: $OutputExe"
