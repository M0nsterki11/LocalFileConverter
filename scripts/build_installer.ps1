param(
    [switch]$SkipTests,
    [switch]$SkipAppBuild,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ReleaseBuildScript = Join-Path $ProjectRoot "scripts\build_release.ps1"
$VerifyBuildScript = Join-Path $ProjectRoot "scripts\verify_build.py"
$VersionScript = Join-Path $ProjectRoot "scripts\generate_installer_version.py"
$VerifyInstallerScript = Join-Path $ProjectRoot "scripts\verify_installer.py"
$InstallerScript = Join-Path $ProjectRoot "packaging\LocalFileConverter.iss"
$LibreOfficeConfig = Join-Path $ProjectRoot "packaging\libreoffice_dependency.json"
$OnedirBundle = Join-Path $ProjectRoot "dist\LocalFileConverter"
$OnedirExe = Join-Path $OnedirBundle "LocalFileConverter.exe"
$InstallerOutput = Join-Path $ProjectRoot "installer_output"
$IconFile = Join-Path $ProjectRoot "resources\app_icon.ico"

function Stop-Build($Message) {
    Write-Error $Message
    exit 1
}

function Get-DirectorySize($Path) {
    if (-not (Test-Path $Path)) { return 0 }
    return (Get-ChildItem -LiteralPath $Path -Recurse -File | Measure-Object -Property Length -Sum).Sum
}

function Find-Iscc {
    $Candidates = @()

    if ($env:INNO_SETUP_ISCC) {
        $Candidates += $env:INNO_SETUP_ISCC
    }

    $Candidates += @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )

    $PathCommand = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($PathCommand) {
        $Candidates += $PathCommand.Source
    }

    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path $Candidate)) {
            return (Resolve-Path $Candidate).Path
        }
    }

    return $null
}

function Validate-LibreOfficeConfig {
    if (-not (Test-Path $LibreOfficeConfig)) {
        Stop-Build "Nedostaje packaging\libreoffice_dependency.json."
    }

    $Config = Get-Content $LibreOfficeConfig -Raw | ConvertFrom-Json

    if ($Config.ENABLED -eq $true) {
        foreach ($Field in @("VERSION", "DOWNLOAD_URL", "SHA256", "EXPECTED_SOFFICE_PATH")) {
            if (-not ($Config.$Field) -or [string]::IsNullOrWhiteSpace([string]$Config.$Field)) {
                Stop-Build "LibreOffice ENABLED=true, ali nedostaje $Field."
            }
        }
    }
}

if (-not (Test-Path (Join-Path $ProjectRoot ".venv"))) { Stop-Build "Nedostaje .venv mapa." }
if (-not (Test-Path $PythonExe)) { Stop-Build "Nedostaje .venv\Scripts\python.exe." }
if (-not (Test-Path $ReleaseBuildScript)) { Stop-Build "Nedostaje scripts\build_release.ps1." }
if (-not (Test-Path $VerifyBuildScript)) { Stop-Build "Nedostaje scripts\verify_build.py." }
if (-not (Test-Path $VersionScript)) { Stop-Build "Nedostaje scripts\generate_installer_version.py." }
if (-not (Test-Path $VerifyInstallerScript)) { Stop-Build "Nedostaje scripts\verify_installer.py." }
if (-not (Test-Path $InstallerScript)) { Stop-Build "Nedostaje packaging\LocalFileConverter.iss." }

$Iscc = Find-Iscc
if (-not $Iscc) {
    Stop-Build "ISCC.exe nije pronaden. Instaliraj Inno Setup 6 ili postavi INNO_SETUP_ISCC na punu putanju do ISCC.exe."
}

if (-not (Test-Path $IconFile)) { Stop-Build "Nedostaje resources\app_icon.ico; ikona je obavezna za installer build." }
if ((Get-Item $IconFile).Length -le 0) { Stop-Build "resources\app_icon.ico je prazan." }

if (-not $SkipTests) {
    & $PythonExe -m pytest -q
    if ($LASTEXITCODE -ne 0) { Stop-Build "Testovi ne prolaze; installer build je zaustavljen." }
}

if (-not $SkipAppBuild) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $ReleaseBuildScript -SkipTests
    if ($LASTEXITCODE -ne 0) { Stop-Build "Release ONEDIR build nije uspio." }
}

if (-not (Test-Path $OnedirExe)) {
    Stop-Build "Nedostaje $OnedirExe. Pokreni build bez -SkipAppBuild ili napravi release ONEDIR build."
}

& $PythonExe $VerifyBuildScript --bundle $OnedirBundle --name "LocalFileConverter"
if ($LASTEXITCODE -ne 0) { Stop-Build "verify_build.py nije prosao." }

$BundleIconCandidates = @(
    (Join-Path $OnedirBundle "_internal\resources\app_icon.ico"),
    (Join-Path $OnedirBundle "resources\app_icon.ico")
)
$BundleIcon = $BundleIconCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $BundleIcon) { Stop-Build "app_icon.ico nije ukljucen u release ONEDIR bundle." }
if ((Get-Item $BundleIcon).Length -le 0) { Stop-Build "app_icon.ico u release ONEDIR bundleu je prazan." }

& $PythonExe $VersionScript
if ($LASTEXITCODE -ne 0) { Stop-Build "Generiranje installer version include datoteke nije uspjelo." }

Validate-LibreOfficeConfig

if ((Test-Path $InstallerOutput) -or $Clean) {
    Remove-Item -LiteralPath $InstallerOutput -Recurse -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $InstallerOutput | Out-Null

& $Iscc $InstallerScript
if ($LASTEXITCODE -ne 0) { Stop-Build "Inno Setup kompilacija nije uspjela." }

$VersionLine = Select-String -Path (Join-Path $ProjectRoot "packaging\generated_version.iss") -Pattern 'AppVersion "([^"]+)"'
$AppVersion = $VersionLine.Matches[0].Groups[1].Value
$SetupExe = Join-Path $InstallerOutput "LocalFileConverter_Setup_${AppVersion}_x64.exe"

if (-not (Test-Path $SetupExe)) { Stop-Build "Ocekivani installer nije pronaden: $SetupExe" }

if ($env:LFC_SIGNTOOL_PATH -and $env:LFC_SIGN_CERT_SHA1) {
    $TimestampUrl = if ($env:LFC_TIMESTAMP_URL) { $env:LFC_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }
    & $env:LFC_SIGNTOOL_PATH sign /fd SHA256 /sha1 $env:LFC_SIGN_CERT_SHA1 /tr $TimestampUrl /td SHA256 $SetupExe
    if ($LASTEXITCODE -ne 0) { Stop-Build "Potpisivanje installera nije uspjelo." }
    Write-Host "Installer je digitalno potpisan."
} else {
    Write-Host "Installer nije digitalno potpisan; LFC_SIGNTOOL_PATH/LFC_SIGN_CERT_SHA1 nisu postavljeni."
}

& $PythonExe $VerifyInstallerScript --installer $SetupExe
if ($LASTEXITCODE -ne 0) { Stop-Build "verify_installer.py nije prosao." }

$InputSizeMb = [math]::Round((Get-DirectorySize $OnedirBundle) / 1MB, 1)
$InstallerSizeMb = [math]::Round((Get-Item $SetupExe).Length / 1MB, 1)

Write-Host "ONEDIR input size: $InputSizeMb MB"
Write-Host "Installer size: $InstallerSizeMb MB"
Write-Host "Installer output: $SetupExe"
