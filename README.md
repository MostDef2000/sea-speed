# Sea Speed

Camera-based vehicle/vessel detection and speed-estimation project.

## Runtime architecture

Current production has three explicit execution contours:

```text
Ubuntu Worker/relay
  -> camera/private relay and Linux worker services when applicable

Windows AI Worker
  -> Windows-specific AI worker packaging/runtime when applicable

VPS
  -> FastAPI, public nginx/TLS, protected Sea Speed UI/API/media
```

Shared `worker/**` source may affect both Worker contours. Runtime applicability is derived from exact paths; `MIXED` never replaces the exact VPS/Ubuntu/Windows declarations.

GitHub `main` is the source of truth. Runtime hosts are not places for manual source edits.

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
-> COMPLETE / BLOCKED / FAILED
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
- Windows-specific `worker/*.ps1`, `worker/*.cmd`, `worker/windows/**`: Windows AI Worker.
- shared `worker/**`: Ubuntu + Windows unless a more-specific rule applies.
- control-plane/docs/SDD work: no runtime release.

Every runtime contour requires a separate production safety envelope. Production is never implied by source authorization, push or merge.

## Provenance

New deployable releases use `sea_speed_release_manifest_v2`, binding canonical Issue/merged PR, exact source/base commits, Outcome and Change Contract hashes, approved vs actual files, exact artifacts and quality evidence. Deployment manifests identify the installed contour and rollback target. Persisted v1 evidence remains readable for rollback compatibility.

## Secrets policy

Never commit tokens, passwords, camera credentials, `.env`, SSH keys, TOTP material, runtime logs, event media, model binaries, local virtual environments or generated runtime data.
