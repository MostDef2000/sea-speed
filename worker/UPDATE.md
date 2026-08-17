# Sea Speed Windows local updater — deprecated

## Status

**NON-PRODUCTION / ARCHIVAL LOCAL TOOLING.** Windows Worker is retired from the active Sea Speed production architecture. The supported analytics runtime is Ubuntu Worker/relay.

The historical scripts in `worker/*.ps1` and `worker/*.cmd` remain in Git so older local installations and audit records are understandable, but they no longer define a production contour, release package, deployment requirement, authorization field or acceptance gate.

## Historical local path

Older installations used:

```text
D:\sea-speed
```

The historical updater preserved local `.env`, `.venv`, output, models and local backups while replacing a bounded managed file set. That behavior is retained only for optional local/historical use.

## Canonical production path

Current production Worker source is delivered only through the Ubuntu Worker/relay contour:

- `deploy/worker/ubuntu/deploy-authorized.sh`
- `deploy/worker/ubuntu/update-exact.sh`
- `deploy/worker/ubuntu/rollback-exact.sh`
- `.github/workflows/deploy-ubuntu-worker.yml`

Production Worker deployment requires the canonical exact-SHA authorization/evidence flow described by `contracts/SEA_SPEED_DELIVERY_POLICY.md`.

## No Windows production packaging

`.github/workflows/package-worker.yml` is intentionally removed. New exact artifacts and release manifests must not include or create a Windows Worker production package. New Change Contracts do not contain Windows deployment/execution fields.

Historical release/deployment manifests and immutable Issue/PR evidence that mention Windows remain readable audit history and are not rewritten.

## Local use warning

Running `update_worker.ps1`, `update_worker.cmd`, BAT/CMD launchers or other retained Windows helpers is outside the supported production lifecycle. Their success does not prove deployment, runtime identity, freshness, rollback readiness or product acceptance.

Generic Python source may remain portable by design. Portability alone does not reactivate Windows as a supported runtime target.
