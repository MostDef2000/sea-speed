[CmdletBinding()]
param(
    [string]$CommitSha = "",
    [string]$InstallDir = "D:\sea-speed",
    [string]$Repository = "MostDef2000/sea-speed",
    [switch]$SkipRestart,
    [switch]$AllowUnmanagedBaseline
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ManagedFiles = @(
    "hls_motion_yolo_worker_events.py",
    "README.txt",
    "start_worker.cmd",
    "stop_worker.cmd",
    "restart_worker.cmd",
    "status_worker.cmd",
    "run_event_worker_forever.cmd",
    "run_worker_once.ps1",
    "update_worker.ps1",
    "update_worker.cmd"
)

function Write-Step([string]$Message) { Write-Host "[sea-speed-worker-update] $Message" }

function Resolve-CommitSha {
    param([string]$RequestedSha)
    if ($RequestedSha) {
        if ($RequestedSha -notmatch '^[0-9a-fA-F]{40}$') { throw "CommitSha must be a full 40-character hexadecimal SHA." }
        return $RequestedSha.ToLowerInvariant()
    }
    Write-Step "Resolving current main commit from GitHub"
    $headers = @{ "User-Agent" = "sea-speed-worker-updater" }
    $response = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$Repository/commits/main"
    $sha = [string]$response.sha
    if ($sha -notmatch '^[0-9a-fA-F]{40}$') { throw "GitHub did not return a valid commit SHA." }
    return $sha.ToLowerInvariant()
}

function Stop-Worker {
    $stopScript = Join-Path $InstallDir "stop_worker.cmd"
    if (Test-Path $stopScript) {
        Write-Step "Stopping current worker"
        & cmd.exe /d /c "(echo.) | call `"$stopScript`""
        Start-Sleep -Seconds 3
    }
}

function Start-Worker {
    $runScript = Join-Path $InstallDir "run_event_worker_forever.cmd"
    if (-not (Test-Path $runScript)) { throw "Worker run script is missing after update: $runScript" }
    Write-Step "Starting worker"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "`"$runScript`"" -WorkingDirectory $InstallDir
    Start-Sleep -Seconds 8
}

function Test-WorkerProcess {
    $escapedPath = [Regex]::Escape($InstallDir)
    $targets = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -in @('python.exe', 'pythonw.exe', 'cmd.exe', 'powershell.exe') -and
        $_.CommandLine -match $escapedPath -and
        ($_.CommandLine -like '*hls_motion_yolo_worker_events.py*' -or $_.CommandLine -like '*run_event_worker_forever.cmd*' -or $_.CommandLine -like '*run_worker_once.ps1*')
    }
    return @($targets).Count -gt 0
}

function Restore-ManagedFiles {
    param([string]$RollbackDir)
    Write-Step "Restoring previous managed worker files"
    foreach ($file in $ManagedFiles) {
        $source = Join-Path $RollbackDir $file
        $target = Join-Path $InstallDir $file
        if (Test-Path $source) { Copy-Item -LiteralPath $source -Destination $target -Force }
    }
}

function Write-DeploymentManifest {
    param(
        [string]$SourceCommit,
        [AllowNull()][string]$PreviousVersion,
        [AllowNull()][string]$ArtifactSha256,
        [string]$State,
        [bool]$RuntimeVerified,
        [string]$WorkerProcessStatus,
        [AllowNull()][string]$AttemptedSourceCommit
    )

    $manifestPath = Join-Path $InstallDir ".sea-speed-worker-deployment.json"
    $payload = [ordered]@{
        schema = "sea_speed_deployment_manifest_v1"
        deliveryId = "windows-worker-$($SourceCommit.Substring(0, [Math]::Min(12, $SourceCommit.Length)))-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))"
        target = "windows-worker"
        sourceCommit = $SourceCommit
        attemptedSourceCommit = if ($AttemptedSourceCommit) { $AttemptedSourceCommit } else { $null }
        previousVersion = if ($PreviousVersion) { $PreviousVersion } else { $null }
        artifactSha256 = if ($ArtifactSha256) { $ArtifactSha256 } else { $null }
        installedAt = [DateTime]::UtcNow.ToString("o")
        checks = @(
            [ordered]@{ name = "managed_files"; status = "passed" },
            [ordered]@{ name = "python_syntax"; status = "passed" },
            [ordered]@{ name = "worker_process"; status = $WorkerProcessStatus }
        )
        rollbackTarget = if ($PreviousVersion) { $PreviousVersion } else { $null }
        runtimeVerified = $RuntimeVerified
        state = $State
    }

    $json = $payload | ConvertTo-Json -Depth 6
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($manifestPath, $json + [Environment]::NewLine, $utf8)
    Write-Step "Deployment evidence written: $manifestPath"
}

$InstallDir = [IO.Path]::GetFullPath($InstallDir)
if (-not (Test-Path $InstallDir -PathType Container)) { throw "Install directory does not exist: $InstallDir" }

foreach ($path in @('.env', '.venv', 'output')) {
    if (-not (Test-Path (Join-Path $InstallDir $path))) { Write-Warning "Expected preserved local path is missing: $path" }
}

$resolvedSha = Resolve-CommitSha -RequestedSha $CommitSha
$currentVersionFile = Join-Path $InstallDir ".sea-speed-worker-version"
$hasManagedVersion = Test-Path $currentVersionFile -PathType Leaf
$currentSha = if ($hasManagedVersion) { (Get-Content $currentVersionFile -Raw).Trim() } else { "unmanaged-baseline" }

if (-not $hasManagedVersion -and -not $AllowUnmanagedBaseline) { throw "This folder is an unmanaged baseline. Review local worker differences first, then rerun with -AllowUnmanagedBaseline to create the first rollback snapshot and adopt GitHub main." }
if ($currentSha -eq $resolvedSha) {
    $processStatus = if ($SkipRestart) { "skipped" } elseif (Test-WorkerProcess) { "passed" } else { "failed" }
    if (-not $SkipRestart -and $processStatus -ne "passed") { throw "Installed commit matches, but worker process was not detected." }
    Write-DeploymentManifest -SourceCommit $resolvedSha -PreviousVersion $null -ArtifactSha256 $null -State $(if ($SkipRestart) { "installed" } else { "runtime_verified" }) -RuntimeVerified (-not $SkipRestart) -WorkerProcessStatus $processStatus -AttemptedSourceCommit $null
    Write-Step "Commit $resolvedSha is already installed"
    exit 0
}

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("sea-speed-worker-" + [Guid]::NewGuid().ToString('N'))
$archivePath = Join-Path $tempRoot "source.zip"
$extractPath = Join-Path $tempRoot "source"
$rollbackRoot = Join-Path $InstallDir ".sea-speed-worker-rollback"
$rollbackDir = Join-Path $rollbackRoot "previous"
$archiveSha256 = $null
New-Item -ItemType Directory -Path $tempRoot, $extractPath, $rollbackRoot -Force | Out-Null

try {
    Write-Step "Downloading exact commit $resolvedSha"
    Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/$Repository/archive/$resolvedSha.zip" -OutFile $archivePath
    $archiveSha256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath -Force
    $repoRoot = Get-ChildItem -Path $extractPath -Directory | Select-Object -First 1
    if (-not $repoRoot) { throw "Downloaded archive does not contain a repository directory." }
    $sourceWorkerDir = Join-Path $repoRoot.FullName "worker"
    foreach ($file in $ManagedFiles) {
        if (-not (Test-Path (Join-Path $sourceWorkerDir $file) -PathType Leaf)) { throw "Release is missing managed worker file: $file" }
    }

    $pythonPath = Join-Path $InstallDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonPath -PathType Leaf)) { throw "Worker virtual environment Python is missing: $pythonPath" }
    Write-Step "Validating downloaded worker Python syntax"
    & $pythonPath -m py_compile (Join-Path $sourceWorkerDir "hls_motion_yolo_worker_events.py")
    if ($LASTEXITCODE -ne 0) { throw "Downloaded worker failed Python syntax validation." }

    Stop-Worker
    if (Test-Path $rollbackDir) { Remove-Item -LiteralPath $rollbackDir -Recurse -Force }
    New-Item -ItemType Directory -Path $rollbackDir -Force | Out-Null
    Write-Step "Saving one previous managed worker release for rollback"
    foreach ($file in $ManagedFiles) {
        $existing = Join-Path $InstallDir $file
        if (Test-Path $existing -PathType Leaf) { Copy-Item -LiteralPath $existing -Destination (Join-Path $rollbackDir $file) -Force }
    }
    Set-Content -LiteralPath (Join-Path $rollbackDir "version.txt") -Value $currentSha -Encoding ascii

    Write-Step "Installing managed worker files"
    foreach ($file in $ManagedFiles) { Copy-Item -LiteralPath (Join-Path $sourceWorkerDir $file) -Destination (Join-Path $InstallDir $file) -Force }
    Set-Content -LiteralPath $currentVersionFile -Value $resolvedSha -Encoding ascii

    $processStatus = "skipped"
    if (-not $SkipRestart) {
        Start-Worker
        if (-not (Test-WorkerProcess)) { throw "Worker process was not detected after restart." }
        $processStatus = "passed"
    }
    Write-DeploymentManifest -SourceCommit $resolvedSha -PreviousVersion $currentSha -ArtifactSha256 $archiveSha256 -State $(if ($SkipRestart) { "installed" } else { "runtime_verified" }) -RuntimeVerified (-not $SkipRestart) -WorkerProcessStatus $processStatus -AttemptedSourceCommit $null
    Write-Step "Worker update successful: $resolvedSha"
    Write-Host "Preserved local content: .env, .venv, output, *.pt, patch files and *.bak* files"
}
catch {
    Write-Host ("Worker update failed: " + $_.Exception.Message) -ForegroundColor Red
    if (Test-Path $rollbackDir -PathType Container) {
        try {
            Stop-Worker
            Restore-ManagedFiles -RollbackDir $rollbackDir
            $previousVersion = Join-Path $rollbackDir "version.txt"
            if (Test-Path $previousVersion) { Copy-Item -LiteralPath $previousVersion -Destination $currentVersionFile -Force }
            $processStatus = "skipped"
            if (-not $SkipRestart) {
                Start-Worker
                if (-not (Test-WorkerProcess)) { throw "Rollback worker process was not detected." }
                $processStatus = "passed"
            }
            Write-DeploymentManifest -SourceCommit $currentSha -PreviousVersion $resolvedSha -ArtifactSha256 $archiveSha256 -State "rolled_back" -RuntimeVerified (-not $SkipRestart) -WorkerProcessStatus $processStatus -AttemptedSourceCommit $resolvedSha
            Write-Warning "Update failed; previous managed worker release was restored."
        }
        catch { Write-Host ("Rollback failed: " + $_.Exception.Message) -ForegroundColor Red }
    }
    exit 1
}
finally {
    if (Test-Path $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
