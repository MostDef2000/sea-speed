# Sea Speed Delivery Policy

Version: 1.0.0
Status: Active

## 1. Purpose

Define release applicability and evidence for the independent VPS and Windows worker runtime contours.

## 2. Applicability

| Changed paths | VPS deployment | Windows worker update |
|---|---:|---:|
| `api/**` | YES | NO unless compatibility requires it |
| `frontend/**` | YES | NO |
| `worker/**` | NO | YES |
| `deploy/**` | according to affected target | according to affected target |
| `.github/workflows/**` | according to workflow scope | according to workflow scope |
| `contracts/**`, `docs/**`, `skills/**`, README-only | NO | NO |

Mixed runtime changes may require both release paths.

## 3. Pull request behavior

PR checks validate only. They must not deploy production runtime. Deployment is allowed only after approved changes reach `main` and the applicable release gate passes.

## 4. VPS release evidence

A VPS release is complete only when applicable evidence confirms:

- deployed source corresponds to the approved merge commit;
- API process is running when API changed;
- health endpoint succeeds;
- frontend smoke check succeeds when frontend changed;
- storage/config compatibility is preserved;
- rollback target is known;
- no secret is printed or committed.

## 5. Windows worker release evidence

A worker release is complete only when applicable evidence confirms:

- released worker corresponds to the approved merge commit or version;
- local `.env`, model, `.venv`, output and runtime data remain untouched;
- worker restarts successfully;
- VPS receives fresh state;
- overlay/events work when affected;
- rollback package or prior commit is available.

## 6. Compatibility

API schema, event schema, worker state schema, or storage schema changes require explicit approval and a declared rollout order. During transition, document whether old worker/new API and new worker/old API combinations are supported.

## 7. Manual fallback

Manual deployment or worker update is fallback-only when automation is unavailable. Provide the exact target, commit, commands/UI path, health checks, rollback steps and expected result.

## 8. Documentation-only changes

Governance and documentation-only tasks complete after PR validation and merge. They must not claim a VPS or worker release and must report both as `NOT REQUIRED`.