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

Shared executable `worker/**` source belongs to Ubuntu Worker/relay unless a more-specific archival rule applies. Changes spanning VPS and Ubuntu are `MIXED`. Windows Worker is retired from production; historical evidence remains readable audit history.

GitHub `main` is the source of truth. Runtime hosts are not editable source stores.

## Development control plane

GitHub Issues are the canonical backlog, source-authorization and task-history record. The single active orchestration role is **Sea Speed Delivery Orchestrator**.

Normal source lifecycle:

```text
request / Issue recovery
-> read-only Task Intake
-> Outcome Contract + visible Implementation Scope Check
-> OUTCOME APPROVED
-> fresh branch + implementation + SDD
-> integrity gate
-> PR Validation + Quality integration
-> exact-green-head merge
-> exact-main Quality
-> standing production policy evaluation when runtime applies
-> protected VPS/Ubuntu execution when allowed
-> runtime acceptance
-> DONE / BLOCKED / HUMAN DECISION REQUIRED
```

`OUTCOME APPROVED` authorizes bounded source lifecycle only. It does not itself grant production execution.

Canonical project rules:

- `AGENTS.md`
- `contracts/SEA_SPEED_GOVERNANCE.md`
- `contracts/SEA_SPEED_DELIVERY_POLICY.md`
- `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`
- `contracts/runtime/RELEASE_READINESS_GATE.md`
- `contracts/branches/project-manager.md`
- `docs/architecture/sea-speed-control-plane.md`
- `specs/README.md`

## Resumable delivery

Sea Speed distinguishes **Repository/product truth**, **Delivery-control truth**, and **Transient interaction state**. `main` remains repository/product truth; the canonical Issue stores the admitted Outcome, source-authorization receipt, and compact `Sea Speed Delivery Checkpoint v1`; the live chat is only where a new visible Scope and immediately-following `OUTCOME APPROVED` are initially admitted.

For an existing task with a valid checkpoint, recovery uses a bounded **Resume Probe** rather than full project recovery. Context compaction, session restart, or Connector truncation do not by themselves return an admitted task to `DISCUSSION` or require another `OUTCOME APPROVED`. Material scope/protected-boundary changes still require fresh source authorization.

Connector recovery is progressive: `known object -> metadata -> targeted detail -> failure fragment`. Equivalent repeated reads with the same evidence identity and question are not admissible unless a canonical gate requires a fresh read.

## Production authority

Production uses an independently administered standing delegation in trusted GitHub `production` environment state. Repository policy can narrow that delegation but cannot widen it. Missing or mismatched delegation denies before runtime transport.

GitHub Issues, PRs, comments, README text, commit messages, copied policy hashes and decision IDs are not production authority. Historical per-release approval text remains audit history only.

A successful `Quality integration gate` run for `push` on `main` feeds `.github/workflows/deploy-runtime-autonomous.yml`. The router evaluates exact merged release metadata plus standing delegation. Each protected VPS/Ubuntu workflow independently re-evaluates the same policy before transport.

Standing delegation covers only `deploy` and `rollback`. IAM, secret management, environment/settings administration and arbitrary infrastructure mutation remain outside agent authority. Standing delegation setup/change is a rare human administrator settings action, not a per-release approval.

## Quality integration gate

The merge-facing context is:

```text
Quality integration gate / quality-integration
```

It aggregates independent static/security, reliability, exact-artifact and release/deployment-evidence domains. Significant PRs must link one valid feature specification. Workflow presence does not prove branch-protection settings.

## Release contours and provenance

- `api/**`, `frontend/**`, `deploy/vps/**`: normally VPS.
- `deploy/worker/ubuntu/**`, `worker/ubuntu_*`, shared executable `worker/**`: Ubuntu Worker/relay.
- Windows-specific `.ps1`/`.cmd`, `worker/windows/**` and helper docs: deprecated non-production archival/control-plane tooling.
- contracts/docs/SDD/control tooling: no runtime release.

New deployable releases use `sea_speed_release_manifest_v3`, binding canonical Issue/PR, exact source/base, Outcome/Change Contract hashes, approved versus actual files, exact artifacts/quality evidence and standing-policy decision/delegation identity. Historical v1/v2 and Windows records remain readable for audit/rollback compatibility.

## Secrets policy

Never commit tokens, passwords, camera credentials, `.env`, SSH keys, TOTP material, runtime logs, event media, model binaries, local virtual environments or generated runtime data.
