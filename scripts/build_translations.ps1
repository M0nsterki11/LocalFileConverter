param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$LReleaseExe = Join-Path $ProjectRoot ".venv\Scripts\pyside6-lrelease.exe"
$TranslationSource = Join-Path $ProjectRoot "translations\local_file_converter_hr.ts"
$TranslationOutput = Join-Path $ProjectRoot "translations\local_file_converter_hr.qm"

function Stop-Build($Message) {
    Write-Error $Message
    exit 1
}

if (-not (Test-Path (Join-Path $ProjectRoot ".venv"))) {
    Stop-Build "The .venv folder is missing."
}

if (-not (Test-Path $LReleaseExe)) {
    Stop-Build "pyside6-lrelease.exe was not found in .venv\Scripts."
}

if (-not (Test-Path $TranslationSource)) {
    Stop-Build "The Croatian translation source is missing: $TranslationSource"
}

& $LReleaseExe $TranslationSource -qm $TranslationOutput
if ($LASTEXITCODE -ne 0) {
    Stop-Build "Translation compilation failed."
}

if (-not (Test-Path $TranslationOutput)) {
    Stop-Build "The compiled Croatian translation was not created: $TranslationOutput"
}

if ((Get-Item $TranslationOutput).Length -le 0) {
    Stop-Build "The compiled Croatian translation is empty: $TranslationOutput"
}

Write-Host "Translations compiled: $TranslationOutput"
