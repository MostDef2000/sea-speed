# Sea Speed

Camera-based vehicle detection and speed-estimation project.

## Runtime architecture

```text
camera / HLS stream
→ Windows AI worker
→ VPS FastAPI backend and storage
→ operator web UI
```

GitHub `main` is the source of truth. The VPS and Windows laptop are runtime environments, not places for manual source edits.

## Repository layout

```text
worker/      Windows AI worker source and runtime scripts
api/         FastAPI backend
frontend/    Operator web UI
deploy/      VPS and Windows delivery helpers
contracts/   canonical governance, runtime and branch contracts
docs/        architecture, decisions, operations and diagnostics
skills/      compatibility entrypoints that route to contracts
```

## Development control plane

Every task follows:

```text
state recovery
→ scope lock
→ explicit approval
→ fresh branch from current main
→ implementation
→ post-write integrity gate
→ pull request and CI
→ merge into main
→ applicable VPS deployment and/or Windows worker update
→ runtime verification
→ COMPLETE / BLOCKED / FAILED
```

Canonical project rules:

- `contracts/SEA_SPEED_GOVERNANCE.md`
- `contracts/SEA_SPEED_DELIVERY_POLICY.md`
- `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`
- `contracts/runtime/RELEASE_READINESS_GATE.md`
- `contracts/branches/project-manager.md`
- `docs/architecture/sea-speed-control-plane.md`

Repository writes require `COMMIT APPROVED` or an approved equivalent. Changes under `skills/**` additionally require `SKILL UPDATE APPROVED`.

## Release contours

- `api/**` and `frontend/**`: normally require VPS deployment.
- `worker/**`: normally requires Windows worker update.
- mixed or schema-changing work may require both and an explicit rollout order.
- contracts/docs/skills/README-only work requires no runtime release.

Merge is not deployment. Deployment is not runtime acceptance.

## Secrets policy

Never commit tokens, passwords, camera credentials, `.env`, SSH keys, runtime logs, event snapshots, overlays, videos, model binaries, local virtual environments or other runtime data.

## Current baseline note

The historical runtime baseline remains in `agent/migrate-baseline-v0` until it is separately reviewed and integrated. This governance change does not merge or modify that runtime baseline.