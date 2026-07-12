# Sea Speed Windows Worker Update

## Scope

The worker is installed in:

```text
D:\sea-speed
```

The updater replaces only these managed files:

```text
hls_motion_yolo_worker_events.py
README.txt
start_worker.cmd
stop_worker.cmd
restart_worker.cmd
status_worker.cmd
run_event_worker_forever.cmd
update_worker.ps1
update_worker.cmd
```

It does not delete, move or overwrite:

```text
.env
.venv\
output\
*.pt
*.bak*
patch_*.py
sea-speed-baseline-vps\
other local notes and files
```

## Release source

`update_worker.ps1` resolves the current `main` commit through the GitHub API unless a full commit SHA is supplied. It downloads the exact repository archive for that commit and installs only the managed worker files.

GitHub Actions also creates a versioned ZIP artifact for every worker change reaching `main` and for manual workflow runs.

## First installation

Download the updater files into the existing worker directory:

```powershell
Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/MostDef2000/sea-speed/main/worker/update_worker.ps1" `
  -OutFile "D:\sea-speed\update_worker.ps1"

Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/MostDef2000/sea-speed/main/worker/update_worker.cmd" `
  -OutFile "D:\sea-speed\update_worker.cmd"
```

The current laptop folder predates managed releases and may contain local changes. The first update therefore refuses to continue without explicit adoption:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "D:\sea-speed\update_worker.ps1" `
  -AllowUnmanagedBaseline
```

Before using `-AllowUnmanagedBaseline`, review whether the live `hls_motion_yolo_worker_events.py` contains changes that are not yet in GitHub. The updater preserves that file in the rollback directory before replacing it, but GitHub should remain the source of truth for future development.

## Normal update

Double-click:

```text
D:\sea-speed\update_worker.cmd
```

or run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "D:\sea-speed\update_worker.ps1"
```

To install one exact commit:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "D:\sea-speed\update_worker.ps1" `
  -CommitSha FULL_40_CHARACTER_SHA
```

## Update sequence

```text
resolve exact commit
→ download repository ZIP
→ validate required managed files
→ validate worker Python syntax with local .venv
→ stop worker
→ replace the single previous rollback snapshot
→ install managed files
→ write .sea-speed-worker-version
→ start worker
→ verify worker process exists
```

## Rollback

Only one previous managed worker release is retained:

```text
D:\sea-speed\.sea-speed-worker-rollback\previous\
```

If installation or process verification fails, the updater automatically restores those files and starts the previous worker.

The update system does not create repeated full-folder backups. Existing user-created `.bak*` files are left unchanged.

## Files created by the updater

```text
D:\sea-speed\.sea-speed-worker-version
D:\sea-speed\.sea-speed-worker-rollback\previous\
```

## Verification

After an update:

```powershell
Get-Content "D:\sea-speed\.sea-speed-worker-version"
Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -like '*D:\sea-speed*' -and
    ($_.CommandLine -like '*hls_motion_yolo_worker_events.py*' -or
     $_.CommandLine -like '*run_event_worker_forever.cmd*')
  } |
  Select-Object ProcessId, Name, CommandLine

Invoke-RestMethod "https://mostdef.ru/sea-speed/api/cam1/state"
```

The API state should update and report `worker_online = true` after the worker starts posting state.

## Skip restart

For file installation without restarting the worker:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "D:\sea-speed\update_worker.ps1" `
  -SkipRestart
```

Use this only for diagnostics or a controlled manual restart.
