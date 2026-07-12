[CmdletBinding()]
param(
    [string]$InstallDir = "D:\sea-speed",
    [string]$EnvFile = "",
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Import-DotEnv {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Worker environment file is missing: $Path"
    }

    $lineNumber = 0
    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $lineNumber++
        $line = $rawLine.Trim()

        if (-not $line -or $line.StartsWith('#')) {
            continue
        }

        $separator = $line.IndexOf('=')
        if ($separator -le 0) {
            throw "Invalid .env entry at line $lineNumber. Expected NAME=value."
        }

        $name = $line.Substring(0, $separator).Trim()
        $value = $line.Substring($separator + 1)

        if ($name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
            throw "Invalid environment variable name '$name' at line $lineNumber."
        }

        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            if ($value.Length -ge 2) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}

$InstallDir = [IO.Path]::GetFullPath($InstallDir)
if (-not $EnvFile) {
    $EnvFile = Join-Path $InstallDir '.env'
}

Import-DotEnv -Path $EnvFile

$required = @('HLS_URL', 'HLS_BASIC_AUTH_BASE64', 'SEA_SPEED_API_TOKEN')
$missing = @()
foreach ($name in $required) {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) {
        $missing += $name
    }
}

if ($missing.Count -gt 0) {
    throw ('Required worker environment variables are missing: ' + ($missing -join ', '))
}

if ($ValidateOnly) {
    Write-Host '[sea-speed-worker] .env loaded and required variables are present.'
    exit 0
}

$pythonPath = Join-Path $InstallDir '.venv\Scripts\python.exe'
$workerPath = Join-Path $InstallDir 'hls_motion_yolo_worker_events.py'

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Worker Python is missing: $pythonPath"
}
if (-not (Test-Path -LiteralPath $workerPath -PathType Leaf)) {
    throw "Worker entrypoint is missing: $workerPath"
}

Set-Location -LiteralPath $InstallDir
& $pythonPath $workerPath
exit $LASTEXITCODE
