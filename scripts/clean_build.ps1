$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")

$Targets = @(
    (Join-Path $ProjectRoot "build"),
    (Join-Path $ProjectRoot "dist")
)

foreach ($Target in $Targets) {
    if (Test-Path $Target) {
        Remove-Item -LiteralPath $Target -Recurse -Force
        Write-Host "Removed $Target"
    }
}

Write-Host "Build artifacts cleaned."
