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
$TranslationsScript = Join-Path $ProjectRoot "scripts\build_translations.ps1"
$VerifyBuildScript = Join-Path $ProjectRoot "scripts\verify_build.py"
$VersionScript = Join-Path $ProjectRoot "scripts\generate_installer_version.py"
$VerifyInstallerScript = Join-Path $ProjectRoot "scripts\verify_installer.py"
$InstallerScript = Join-Path $ProjectRoot "packaging\LocalFileConverter.iss"
$LibreOfficeConfig = Join-Path $ProjectRoot "packaging\libreoffice_dependency.json"
$LibreOfficeInclude = Join-Path $ProjectRoot "packaging\generated_libreoffice_dependency.iss"
$OnedirBundle = Join-Path $ProjectRoot "dist\LocalFileConverter"
$OnedirExe = Join-Path $OnedirBundle "LocalFileConverter.exe"
$InstallerOutput = Join-Path $ProjectRoot "installer_output"
$IconFile = Join-Path $ProjectRoot "resources\app_icon.ico"
$TranslationFile = Join-Path $ProjectRoot "translations\local_file_converter_hr.qm"

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

function ConvertTo-IssString($Value) {
    return ([string]$Value).Replace('"', '""')
}

function Validate-LibreOfficeConfig {
    if (-not (Test-Path $LibreOfficeConfig)) {
        Stop-Build "packaging\libreoffice_dependency.json is missing."
    }

    $Config = Get-Content $LibreOfficeConfig -Raw | ConvertFrom-Json

    if ($Config.ENABLED -eq $true) {
        foreach ($Field in @("VERSION", "ARCHITECTURE", "FILENAME", "DOWNLOAD_URL", "SHA256", "EXPECTED_FILE_SIZE", "EXPECTED_SOFFICE_PATH")) {
            if (-not ($Config.$Field) -or [string]::IsNullOrWhiteSpace([string]$Config.$Field)) {
                Stop-Build "LibreOffice ENABLED=true, but $Field is missing."
            }
        }

        if ($Config.VERSION -ne "26.2.4") {
            Stop-Build "LibreOffice VERSION must be pinned to 26.2.4."
        }

        if ($Config.ARCHITECTURE -ne "x64") {
            Stop-Build "LibreOffice ARCHITECTURE must be x64."
        }

        if ($Config.FILENAME -ne "LibreOffice_26.2.4_Win_x86-64.msi") {
            Stop-Build "LibreOffice FILENAME does not match the pinned MSI file."
        }

        if ([string]$Config.DOWNLOAD_URL -notmatch '^https://download\.documentfoundation\.org/libreoffice/stable/26\.2\.4/win/x86_64/LibreOffice_26\.2\.4_Win_x86-64\.msi$') {
            Stop-Build "LibreOffice DOWNLOAD_URL must be the exact official HTTPS pinned URL."
        }

        if ([string]$Config.SHA256 -notmatch '^[0-9a-fA-F]{64}$') {
            Stop-Build "LibreOffice SHA256 must contain 64 hexadecimal characters."
        }

        if ([string]$Config.SHA256 -ne "202f26cda071c5aa4996a5a28412fddceb3891dceb0366982c62650456c0730f") {
            Stop-Build "LibreOffice SHA256 does not match the pinned value."
        }

        if ([int64]$Config.EXPECTED_FILE_SIZE -ne 372539392) {
            Stop-Build "LibreOffice EXPECTED_FILE_SIZE does not match the pinned value."
        }
    }

    $EnabledLiteral = if ($Config.ENABLED -eq $true) { "True" } else { "False" }
    $ExpectedFileSize = if ($Config.EXPECTED_FILE_SIZE) { [int64]$Config.EXPECTED_FILE_SIZE } else { 0 }
    $Lines = @(
        "#define LibreOfficeEnabled $EnabledLiteral",
        "#define LibreOfficeVersion ""$(ConvertTo-IssString $Config.VERSION)""",
        "#define LibreOfficeArchitecture ""$(ConvertTo-IssString $Config.ARCHITECTURE)""",
        "#define LibreOfficeFilename ""$(ConvertTo-IssString $Config.FILENAME)""",
        "#define LibreOfficeDownloadUrl ""$(ConvertTo-IssString $Config.DOWNLOAD_URL)""",
        "#define LibreOfficeSHA256 ""$(ConvertTo-IssString $Config.SHA256)""",
        "#define LibreOfficeExpectedFileSize $ExpectedFileSize",
        "#define LibreOfficeExpectedSofficePath ""$(ConvertTo-IssString $Config.EXPECTED_SOFFICE_PATH)"""
    )
    Set-Content -Path $LibreOfficeInclude -Value $Lines -Encoding UTF8
}

if (-not (Test-Path (Join-Path $ProjectRoot ".venv"))) { Stop-Build "The .venv folder is missing." }
if (-not (Test-Path $PythonExe)) { Stop-Build ".venv\Scripts\python.exe is missing." }
if (-not (Test-Path $ReleaseBuildScript)) { Stop-Build "scripts\build_release.ps1 is missing." }
if (-not (Test-Path $TranslationsScript)) { Stop-Build "scripts\build_translations.ps1 is missing." }
if (-not (Test-Path $VerifyBuildScript)) { Stop-Build "scripts\verify_build.py is missing." }
if (-not (Test-Path $VersionScript)) { Stop-Build "scripts\generate_installer_version.py is missing." }
if (-not (Test-Path $VerifyInstallerScript)) { Stop-Build "scripts\verify_installer.py is missing." }
if (-not (Test-Path $InstallerScript)) { Stop-Build "packaging\LocalFileConverter.iss is missing." }

$Iscc = Find-Iscc
if (-not $Iscc) {
    Stop-Build "ISCC.exe was not found. Install Inno Setup 6 or set INNO_SETUP_ISCC to the full path to ISCC.exe."
}

if (-not (Test-Path $IconFile)) { Stop-Build "resources\app_icon.ico is missing; the icon is required for installer builds." }
if ((Get-Item $IconFile).Length -le 0) { Stop-Build "resources\app_icon.ico is empty." }

& powershell -NoProfile -ExecutionPolicy Bypass -File $TranslationsScript
if ($LASTEXITCODE -ne 0) { Stop-Build "Translation compilation failed." }
if (-not (Test-Path $TranslationFile)) { Stop-Build "The compiled Croatian translation is missing: $TranslationFile" }

if (-not $SkipTests) {
    & $PythonExe -m pytest -q
    if ($LASTEXITCODE -ne 0) { Stop-Build "Tests failed; the installer build was stopped." }
}

if (-not $SkipAppBuild) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $ReleaseBuildScript -SkipTests
    if ($LASTEXITCODE -ne 0) { Stop-Build "The release ONEDIR build failed." }
}

if (-not (Test-Path $OnedirExe)) {
    Stop-Build "$OnedirExe is missing. Run without -SkipAppBuild or create a release ONEDIR build."
}

& $PythonExe $VerifyBuildScript --bundle $OnedirBundle --name "LocalFileConverter"
if ($LASTEXITCODE -ne 0) { Stop-Build "verify_build.py failed." }

$BundleIconCandidates = @(
    (Join-Path $OnedirBundle "_internal\resources\app_icon.ico"),
    (Join-Path $OnedirBundle "resources\app_icon.ico")
)
$BundleIcon = $BundleIconCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $BundleIcon) { Stop-Build "app_icon.ico is not included in the release ONEDIR bundle." }
if ((Get-Item $BundleIcon).Length -le 0) { Stop-Build "app_icon.ico in the release ONEDIR bundle is empty." }

& $PythonExe $VersionScript
if ($LASTEXITCODE -ne 0) { Stop-Build "Generating the installer version include file failed." }

Validate-LibreOfficeConfig

if ((Test-Path $InstallerOutput) -or $Clean) {
    Remove-Item -LiteralPath $InstallerOutput -Recurse -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $InstallerOutput | Out-Null

& $Iscc $InstallerScript
if ($LASTEXITCODE -ne 0) { Stop-Build "Inno Setup compilation failed." }

$VersionLine = Select-String -Path (Join-Path $ProjectRoot "packaging\generated_version.iss") -Pattern 'AppVersion "([^"]+)"'
$AppVersion = $VersionLine.Matches[0].Groups[1].Value
$SetupExe = Join-Path $InstallerOutput "LocalFileConverter_Setup_${AppVersion}_x64.exe"

if (-not (Test-Path $SetupExe)) { Stop-Build "The expected installer was not found: $SetupExe" }

if ($env:LFC_SIGNTOOL_PATH -and $env:LFC_SIGN_CERT_SHA1) {
    $TimestampUrl = if ($env:LFC_TIMESTAMP_URL) { $env:LFC_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }
    & $env:LFC_SIGNTOOL_PATH sign /fd SHA256 /sha1 $env:LFC_SIGN_CERT_SHA1 /tr $TimestampUrl /td SHA256 $SetupExe
    if ($LASTEXITCODE -ne 0) { Stop-Build "Installer signing failed." }
    Write-Host "Installer is digitally signed."
} else {
    Write-Host "Installer is not digitally signed; LFC_SIGNTOOL_PATH/LFC_SIGN_CERT_SHA1 are not set."
}

& $PythonExe $VerifyInstallerScript --installer $SetupExe
if ($LASTEXITCODE -ne 0) { Stop-Build "verify_installer.py failed." }

$InputSizeMb = [math]::Round((Get-DirectorySize $OnedirBundle) / 1MB, 1)
$InstallerSizeMb = [math]::Round((Get-Item $SetupExe).Length / 1MB, 1)

Write-Host "ONEDIR input size: $InputSizeMb MB"
Write-Host "Installer size: $InstallerSizeMb MB"
Write-Host "Installer output: $SetupExe"
