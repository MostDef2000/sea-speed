# Sea Speed production baseline evidence

Status: Active operational procedure  
Issue: #22  
Auth security migration: Issue #115  
Secrets: prohibited in captured output

## Purpose

Record the exact source revision installed on each runtime contour before and after a release. The evidence is read-only and must not expose `.env`, tokens, camera credentials, Authentik secrets/session values, TOTP material, private keys, model contents, videos, overlays or event snapshots.

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
curl --fail --silent --show-error http://127.0.0.1:8000/api/health
```

After Sea Speed Auth v1 is active, the public private-health URL is an authentication-boundary check rather than the API health proof:

```bash
curl --silent --show-error --output /dev/null --write-out '%{http_code}\n' \
  https://mostdef.ru/sea-speed/api/health
```

Expected after Auth v1: authentication redirect/deny (`302`, `401` or `403` according to the active Authentik/nginx flow), not anonymous application data.

Record:

```text
VPS installed commit:
API process active:
Loopback API health passed:
Public Sea Speed auth boundary observed:
Root frontend smoke passed:
Previous release marker:
Observed at UTC:
```

Do not print environment files, service environment values, Authentik data or SSH configuration.

## Worker baseline

Read the installed worker revision and process state using the runtime-appropriate worker procedure. For the existing Windows-style install this can include:

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

After Issue #115, do not query private runtime state anonymously through `https://mostdef.ru/sea-speed/api/...`. Browser-facing Sea Speed API is Authentik-protected. Worker machine-to-machine state/config traffic uses the exact private VPS listener documented in `docs/operations/SEA_SPEED_AUTH_V1.md`, restricted to the approved private worker peer. Do not print the private Bearer token or Authorization header while checking it.

Record only non-secret evidence:

```text
Worker installed commit:
Worker process present:
Private M2M route reachable from approved worker peer:
worker_online:
updated_at:
frame_no:
Observed at UTC:
```

## Auth v1 baseline additions

When Issue #115 is deployed, also record sanitized state:

```text
Authentik server healthy: YES/NO
Authentik worker healthy: YES/NO
Authentik PostgreSQL healthy: YES/NO
auth.mostdef.ru HTTPS ready: YES/NO
/cams/** exposes no camera content: YES/NO
anonymous /sea-speed/** denied/redirected: YES/NO
Camera 1 authenticated H264 playback accepted: YES/NO
private worker listener bound to private VPS interface only: YES/NO
```

Never capture user passwords, invitation tokens, recovery links, TOTP seeds/codes, Authentik cookies or SMTP secrets as baseline evidence.

## Evidence verdict

Use exactly one:

- `BASELINE_CONFIRMED` — installed revisions and required health/security fields are known;
- `PARTIAL_EVIDENCE` — one contour or one required field is unknown;
- `BASELINE_MISMATCH` — installed revision differs from the expected revision;
- `EVIDENCE_FAILED` — a read-only evidence command failed.

A green GitHub workflow does not prove that a runtime contour is installed, authenticated correctly or healthy.
