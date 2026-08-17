# Sea Speed

Camera-based vehicle/vessel detection and speed-estimation project.

## Runtime architecture

Current production has exactly two execution contours:

```text
Ubuntu Worker/relay
  -> camera/private relay and Linux analytics worker services

VPS
  -> FastAPI, public nginx/TLS, protected Sea Speed UI/API/media
```

Shared executable `worker/**` source is part of the Ubuntu Worker/relay contour unless a more-specific archival rule applies. Changes spanning VPS and Ubuntu may be classified `MIXED`; the exact VPS/Ubuntu declarations remain authoritative.

Windows Worker is retired from production. Existing `worker/*.cmd`, `worker/*.ps1`, `worker/windows/**`, `worker/README.txt`, and `worker/UPDATE.md` are deprecated non-production local/archive tooling only. Historical Windows Issues, PRs and release/deployment evidence remain audit history and are not rewritten.

GitHub `main` is the source of truth. Runtime hosts are not editable source stores.

## Development control plane

GitHub Issues are the canonical backlog, authorization and task-history record. Read-only Task Intake converts an unstructured request into a Task Brief. The single active orchestration role is **Sea Speed Delivery Orchestrator**.

Normal source lifecycle:

```text
request / Issue recovery
-> read-only Task Intake
-> Outcome Contract + Implementation Scope Check
-> OUTCOME APPROVED
-> capability preflight
-> fresh branch from current main
-> implementation + SDD
-> integrity gate
-> pull request
-> PR Validation + Quality integration
-> fresh base/head/scope/review check
-> expected-head merge
-> post-merge exact-main verification
-> separately authorized runtime delivery when applicable
-> runtime acceptance
-> DONE / BLOCKED / HUMAN DECISION REQUIRED
```

`OUTCOME APPROVED` is the active source-authorization model for new tasks. Historical `COMMIT APPROVED` / `MERGE APPROVED` records remain audit history but are not accepted in new Change Contracts.

Canonical project rules:

- `AGENTS.md`
- `contracts/SEA_SPEED_GOVERNANCE.md`
- `contracts/SEA_SPEED_DELIVERY_POLICY.md`
- `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`
- `contracts/runtime/RELEASE_READINESS_GATE.md`
- `contracts/branches/task-intake.md`
- `contracts/branches/project-manager.md` (compatibility path for Delivery Orchestrator)
- `docs/architecture/sea-speed-control-plane.md`
- `specs/README.md`

Domain files under `contracts/branches/`, including `core-release.md`, are on-demand review lenses/checklists. They do not require autonomous-agent handoffs.

## Quality integration gate

The merge-facing context is:

```text
Quality integration gate / quality-integration
```

It aggregates independent static/security, reliability, exact-artifact and release/deployment-evidence domains. Significant PRs must link one valid feature specification. Workflow presence does not prove branch-protection settings.

## Release contours

- `api/**`, `frontend/**`, `deploy/vps/**`: normally VPS.
- `deploy/worker/ubuntu/**`, `worker/ubuntu_*`: Ubuntu Worker/relay.
- shared executable `worker/**`: Ubuntu Worker/relay.
- Windows-specific `.ps1`/`.cmd`, `worker/windows/**`, and Windows helper documentation: deprecated non-production archival/control-plane tooling.
- contracts/docs/SDD/control tooling: no runtime release.

Every active runtime contour requires a production safety envelope. Production is never implied by source authorization, push or merge.

## Provenance

New deployable releases use `sea_speed_release_manifest_v2`, binding canonical Issue/merged PR, exact source/base commits, Outcome and Change Contract hashes, approved versus actual files, exact artifacts and quality evidence. New production release creation targets VPS, Ubuntu Worker/relay, or mixed VPS+Ubuntu only. Persisted historical manifests, including Windows records, remain readable for audit/rollback compatibility.

## Secrets policy

Never commit tokens, passwords, camera credentials, `.env`, SSH keys, TOTP material, runtime logs, event media, model binaries, local virtual environments or generated runtime data.
