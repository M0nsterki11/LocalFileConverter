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
$IconFile = Join-Path $ProjectRoot "resources\app_icon.ico"
$OutputExe = Join-Path $ProjectRoot "dist\LocalFileConverterOnefile.exe"

function Stop-Build($Message) {
    Write-Error $Message
    exit 1
}

if (-not (Test-Path (Join-Path $ProjectRoot ".venv"))) { Stop-Build "Nedostaje .venv mapa." }
if (-not (Test-Path $PythonExe)) { Stop-Build "Nedostaje .venv\Scripts\python.exe." }
if (-not (Test-Path $MainFile)) { Stop-Build "Nedostaje main.py." }
if (-not (Test-Path $SpecFile)) { Stop-Build "Nedostaje LocalFileConverter.spec." }
if (-not (Test-Path $IconFile)) { Stop-Build "Nedostaje resources\app_icon.ico; ikona je obavezna za onefile build." }
if ((Get-Item $IconFile).Length -le 0) { Stop-Build "resources\app_icon.ico je prazan." }

& $PythonExe -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Stop-Build "PyInstaller nije instaliran. Pokreni: .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
}

if (-not $SkipTests) {
    & $PythonExe -m pytest -q
    if ($LASTEXITCODE -ne 0) { Stop-Build "Testovi ne prolaze; onefile build je zaustavljen." }
}

& $PythonExe $VersionScript
if ($LASTEXITCODE -ne 0) { Stop-Build "Generiranje Windows version info datoteke nije uspjelo." }

$env:LFC_BUILD_MODE = "release"
$env:LFC_BUILD_TARGET = "onefile"
& $PythonExe -m PyInstaller --clean --noconfirm $SpecFile
$buildExitCode = $LASTEXITCODE
Remove-Item Env:\LFC_BUILD_MODE -ErrorAction SilentlyContinue
Remove-Item Env:\LFC_BUILD_TARGET -ErrorAction SilentlyContinue

if ($buildExitCode -ne 0) { Stop-Build "PyInstaller onefile build nije uspio." }
if (-not (Test-Path $OutputExe)) { Stop-Build "Ocekivani onefile EXE nije pronaden: $OutputExe" }
if ((Get-Item $OutputExe).Length -le 0) { Stop-Build "Onefile EXE je prazan: $OutputExe" }

Write-Host "Eksperimentalni onefile build je spreman: $OutputExe"
