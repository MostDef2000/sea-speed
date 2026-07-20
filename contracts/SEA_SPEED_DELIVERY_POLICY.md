# Sea Speed Delivery Policy

Version: 1.1.0
Status: Active

## 1. Purpose

Define release applicability, rollout ordering and completion evidence for the independent VPS and Windows worker runtime contours.

## 2. Applicability

| Changed paths | VPS deployment | Windows worker update | Default rollout |
|---|---:|---:|---|
| `api/**` | YES | NO unless compatibility requires it | VPS, then API acceptance |
| `frontend/**` | YES | NO | VPS, then browser smoke |
| `worker/**` | NO | YES | worker package/update, then fresh-state acceptance |
| API contract plus worker consumer | YES | YES | backward-compatible VPS first, verify API, then worker |
| `deploy/vps/**` | YES | NO | VPS release gate |
| `deploy/windows/**` | NO | YES | worker release gate |
| other `deploy/**` | according to affected target | according to affected target | declare explicitly |
| `.github/workflows/**` | according to workflow scope | according to workflow scope | declare explicitly |
| `contracts/**`, `docs/**`, `skills/**`, README-only | NO | NO | PR validation and merge only |

Mixed runtime changes require both release paths unless the approved scope proves one contour is unaffected.

## 3. Pull request behavior

PR checks validate only. They must not deploy production runtime. Deployment is allowed only after approved changes reach `main` and the applicable release gate passes.

## 4. Mixed-contour rollout

Before merging a mixed API/worker change, document:

- whether old worker/new API is supported;
- whether new worker/old API is supported;
- schema or behavior migration requirements;
- deployment order;
- acceptance checks after each step;
- rollback order and compatibility window.

The default safe order is a backward-compatible VPS/API deployment, API verification, Windows worker update, then worker freshness and event verification. A different order requires explicit rationale and approval.

## 5. VPS release evidence

A VPS release is complete only when applicable evidence confirms:

- deployed source corresponds to the approved merge commit;
- API process is running when API changed;
- health endpoint succeeds;
- frontend smoke check succeeds when frontend changed;
- storage/config compatibility is preserved;
- rollback target is known;
- no secret is printed or committed.

## 6. Windows worker release evidence

A worker release is complete only when applicable evidence confirms:

- released worker corresponds to the approved merge commit or version;
- local `.env`, model, `.venv`, output and runtime data remain untouched;
- worker restarts successfully;
- VPS receives fresh state and `updated_at` advances;
- `worker_online` is true when that signal exists;
- frame or heartbeat progress advances when available;
- overlay/events work when affected;
- rollback package or prior commit is available.

## 7. Compatibility

API schema, event schema, worker state schema, or storage schema changes require explicit approval and a declared rollout order. During transition, document whether old worker/new API and new worker/old API combinations are supported.

## 8. Manual fallback

Manual deployment or worker update is fallback-only when automation is unavailable. Provide the exact target, commit, commands or UI path, health checks, rollback steps and expected result.

## 9. Documentation-only changes

Governance and documentation-only tasks complete after PR validation and merge. They must not claim a VPS or worker release and must report both as `NOT REQUIRED`.