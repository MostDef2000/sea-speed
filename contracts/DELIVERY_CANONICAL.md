# Sea Speed Canonical Delivery Contract

Version: 1.0.0
Status: Active
Replaces duplication across 9 documents: see `scripts/ci/validate_contracts.py`

## Truth classes
- **Repository/product truth**: `main`, committed source/contracts/specs
- **Delivery-control truth**: canonical Issue `OUTCOME APPROVED` receipt + `Sea Speed Delivery Checkpoint v3` (or v2 compat)
- **Transient**: live chat for initial `Scope` → immediately-following `OUTCOME APPROVED`

## Source admission
Visible six-field Scope must immediately precede `OUTCOME APPROVED`. Before first repo write require `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, `SOURCE_AUTHORIZATION_ADMISSION=OPEN`. Receipt continues only **same exact admitted scope**; never creates/widens production authority.

## Resumable delivery
Known task with valid checkpoint → bounded **Resume Probe**: current `main`, Issue checkpoint, exact PR/head/status cursor, `Next admissible action`. Full recovery only if checkpoint absent/invalid/contradicted. Context loss does not invalidate authorization. `CONTEXT_LOSS` is not an invalidation reason. Valid invalidation: `MATERIAL_SCOPE_CHANGE`, `PROTECTED_BOUNDARY_CHANGE`, `USER_CHANGED_OUTCOME`, `MATERIAL_MAIN_DIVERGENCE`, `EVIDENCE_CONTRADICTION`.

Lifecycle monotonic. Checkpoint updates at meaningful transitions only, with `Next admissible action`.

Connector reads: `known object -> metadata -> targeted detail -> failure fragment`. Equivalent repeat with same evidence identity is forbidden unless gate requires fresh read.

## Synchronous external wait
`WAITING_EXTERNAL` is nonterminal, synchronous, no background polling. Valid only when no safe action executable now and one machine-observable external condition pending. Checkpoint v3 records `waiting_on`, v2 records `external_wait` + `evidence_cursor`. Unchanged cursor preserves wait without generation bump; changed cursor → `ACTIVE`.

Persisted v1/v2 checkpoints remain readable; validator upgrades v1→v2 compat at next transition without re-authorization.

## Delivery Checkpoint
- **v3** canonical (10 required fields in `schemas/delivery-checkpoint-v3.schema.json`): `schema`, `task`, `scope_hash`, `authorized`, `lane`, `phase`, `pr`, `head`, `next`, `waiting_on`
  - `lane` = `FAST` (docs/control-plane, no runtime), `STANDARD` (product code, single contour), `PRODUCTION` (deploy/security/MIXED)
  - `phase` = `PLANNING`, `IMPLEMENTING`, `PR`, `MERGED`, `DEPLOYING`, `VERIFYING`, `DONE`, `BLOCKED`, `HUMAN_DECISION_REQUIRED`
  - `waiting_on` = `null` | `ci` | `human` | `external` (GitHub Actions, etc.) — `BLOCKED` phase requires `waiting_on=external` with blocker evidence, `HUMAN_DECISION_REQUIRED` requires `waiting_on=human`
  - Derived state (branch resolved from PR, gates from CI, generation from Git history) is **not** persisted; reconstruct from GitHub.
- **v2** readable compat — Delivery Checkpoint v2: `schemas/delivery-checkpoint-v2.schema.json` (15 fields) with `generation`, `approved_scope_identity`, `authorization_receipt`, `authorization_base_main`, `current_phase` (9 values), `branch`, `pr`, `exact_working_head`, `completed_gates`, `evidence_cursors[5]`, `next_admissible_action{kind,description,executable_now}`, `session_disposition`, `external_wait`, `state_invalidation_reason`, `terminal_interaction_state`.

Principle: *Derived state should not be persisted unless expensive/impossible to reconstruct.*

## Single quality gate
`Quality integration gate / quality-integration` with `classify` job `scripts/ci/classify_change.py` → `lane`/`runtime_required`. `exact-artifact-e2e` and `release-deployment-evidence` run only when `runtime_required=true` (VPS/UBUNTU_WORKER per `data/contracts/change-control-policy-v1.json`). Adapter workflows no longer forbid `paths` on aggregate gate via conditional `needs.classify`.

## Production
Standing delegation `SEA_SPEED_PRODUCTION_DELEGATION_V1` in `production` environment + `verify_source_protection.py` (`quality-integration` only after S1) → `evaluate_production_policy.py` → `deploy-vps/ubuntu-worker` restricted transport. Issue/PR text not authority.

Adapters `AGENTS.md`, `SEA_SPEED_GOVERNANCE.md`, `SEA_SPEED_DELIVERY_POLICY.md`, `SEA_SPEED_TASK_RUNTIME.md`, `RELEASE_READINESS_GATE.md`, `task-intake.md`, `project-manager.md`, `PM_BOOTSTRAP.md`, `sea-speed-control-plane.md` reference this canonical file; they must not duplicate its semantics.
