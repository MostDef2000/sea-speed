# Sea Speed production baseline evidence

Status: Active operational procedure  
Issue: #22  
Secrets: prohibited in captured output

## Purpose

Record the exact source revision installed on each runtime contour before and after a release. The evidence is read-only and must not expose `.env`, tokens, camera credentials, private keys, model contents, videos, overlays or event snapshots.

## Repository baseline

Record:

```text
Repository main SHA:
PR or Issue:
Observed at UTC:
Required CI checks:
Branch protection verified: YES/NO/UNKNOWN
```

Repository settings that cannot be read through connected automation remain `UNKNOWN`; do not infer that protection is active.

## VPS baseline

Run only commands that print non-secret code provenance and health:

```bash
cat /opt/sea-speed-deploy/state/current-release
systemctl is-active sea-speed-api
curl --fail --silent --show-error https://mostdef.ru/sea-speed/api/health
```

Record:

```text
VPS installed commit:
API process active:
Health endpoint passed:
Frontend smoke passed:
Previous release marker:
Observed at UTC:
```

Do not print environment files, service environment values or SSH configuration.

## Windows worker baseline

Run in PowerShell:

```powershell
Get-Content "D:\sea-speed\.sea-speed-worker-version"
Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -like '*D:\sea-speed*' -and
    ($_.CommandLine -like '*hls_motion_yolo_worker_events.py*' -or
     $_.CommandLine -like '*run_event_worker_forever.cmd*')
  } |
  Select-Object ProcessId, Name
```

Then query the public runtime state without credentials:

```powershell
Invoke-RestMethod "https://mostdef.ru/sea-speed/api/cam1/state"
```

Record only:

```text
Worker installed commit:
Worker process present:
worker_online:
updated_at:
frame_no:
Observed at UTC:
```

## Evidence verdict

Use exactly one:

- `BASELINE_CONFIRMED` — both installed revisions and required health fields are known;
- `PARTIAL_EVIDENCE` — one contour or one required field is unknown;
- `BASELINE_MISMATCH` — installed revision differs from the expected revision;
- `EVIDENCE_FAILED` — a read-only evidence command failed.

A green GitHub workflow does not prove that either runtime contour is installed or healthy.
