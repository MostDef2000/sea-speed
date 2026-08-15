# Sea Speed production baseline evidence

Status: Active operational procedure
Issue: #22
Auth security migration parent: Issue #115
Secrets: prohibited in captured output

## Purpose

Record exact non-secret source/runtime identity and health for each production contour before/after a protected release. A repository merge does not prove runtime state.

## Repository baseline

```text
Repository main SHA:
Canonical Issue / merged PR:
Observed at UTC:
Exact push/main Quality integration:
Branch protection verified: YES/NO/UNKNOWN
```

Do not infer GitHub settings from source workflows.

## VPS baseline

Known production FastAPI origin from accepted runtime evidence is `127.0.0.1:8010`.

```bash
cat /opt/sea-speed-deploy/state/current-release
systemctl is-active sea-speed-api
curl --fail --silent --show-error http://127.0.0.1:8010/api/health
```

After Auth v1, public `/sea-speed/**` health is an authentication-boundary smoke, not origin-health proof. Record current/previous release, API health/source commit, root/protected-route smoke and active reviewed nginx identity where applicable. Never print environment/Auth/TOTP/cookie/token material.

## Ubuntu Worker/relay baseline

Record only non-secret facts required by the current outcome, for example:

```text
Ubuntu installed source commit:
Runtime ID / package identity when applicable:
Service active:
ExecStart exact source/runtime binding:
frame/state/AI or relay freshness:
Rollback source/runtime:
Observed at UTC:
```

Do not print protected worker env, camera URLs/credentials, model contents or private media.

## Windows AI Worker baseline

For Windows-specific tasks record exact installed/package source identity, managed process state, freshness/telemetry and rollback version. Historical paths such as `D:\sea-speed\...` remain task/runtime-specific; do not treat them as the Ubuntu contour.

## Auth v1 accepted boundary

Issue #122 runtime acceptance established worker-hosted Authentik/private origin, VPS public ingress, protected `/sea-speed/**`, retired `/cams/**`, exact-peer private M2M and fail-closed dependency behavior. Parent Issue #115 remains an open audit/backlog record; do not infer that its GitHub state is closed.

## Verdicts

- `BASELINE_CONFIRMED`
- `PARTIAL_EVIDENCE`
- `BASELINE_MISMATCH`
- `EVIDENCE_FAILED`
