function Invoke-ProjectPytest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe,

        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,

        [string[]]$PytestArgs = @("-q")
    )

    $PytestTempRoot = Join-Path $ProjectRoot ".pytest_tmp"
    $ProcessId = [System.Diagnostics.Process]::GetCurrentProcess().Id
    $RunId = [guid]::NewGuid().ToString("N")
    $RunTempDirectory = Join-Path $PytestTempRoot "build-$ProcessId-$RunId"
    $PytestBaseTemp = Join-Path $RunTempDirectory "pytest-basetemp"
    $ProcessTemp = Join-Path $RunTempDirectory "temp"
    $PreviousTemp = $env:TEMP
    $PreviousTmp = $env:TMP
    $TestExitCode = 1

    try {
        New-Item -ItemType Directory -Force -Path $PytestBaseTemp | Out-Null
        New-Item -ItemType Directory -Force -Path $ProcessTemp | Out-Null

        $env:TEMP = $ProcessTemp
        $env:TMP = $ProcessTemp

        & $PythonExe -m pytest "--basetemp=$PytestBaseTemp" @PytestArgs
        $TestExitCode = $LASTEXITCODE
    }
    finally {
        if ($null -eq $PreviousTemp) {
            Remove-Item Env:\TEMP -ErrorAction SilentlyContinue
        } else {
            $env:TEMP = $PreviousTemp
        }

        if ($null -eq $PreviousTmp) {
            Remove-Item Env:\TMP -ErrorAction SilentlyContinue
        } else {
            $env:TMP = $PreviousTmp
        }

        if (Test-Path $RunTempDirectory) {
            try {
                Remove-Item -LiteralPath $RunTempDirectory -Recurse -Force -ErrorAction Stop
            }
            catch {
                Write-Warning (
                    "Could not remove pytest temporary directory '$RunTempDirectory'. " +
                    "It was left under .pytest_tmp for later cleanup. " +
                    "Reason: $($_.Exception.Message)"
                )
            }
        }

        $global:LASTEXITCODE = $TestExitCode
    }
}
