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
  - Machine-readable v2 keys: "generation", "approved_scope_identity", "authorization_base_main", "current_phase", "branch", "pr", "exact_working_head", "completed_gates", "evidence_cursors", "next_admissible_action", "session_disposition", "external_wait", "state_invalidation_reason"
  - Terminal: DONE, BLOCKED, HUMAN DECISION REQUIRED — WAITING_EXTERNAL is not a lifecycle phase, terminal interaction state — PR created, CI running, while a safe authorized next action is executable now
  - Session disposition: ACTIVE/WAITING_EXTERNAL/TERMINAL, Terminal interaction state: NONE/DONE/BLOCKED/HUMAN DECISION REQUIRED, safe authorized action executable now = NO, terminal interaction state = NONE when ACTIVE
  - Lifecycle is monotonic with explicit material invalidation: MATERIAL_SCOPE_CHANGE, PROTECTED_BOUNDARY_CHANGE, USER_CHANGED_OUTCOME, MATERIAL_MAIN_DIVERGENCE, EVIDENCE_CONTRADICTION — CONTEXT_LOSS is intentionally not a valid reason

Principle: *Derived state should not be persisted unless expensive/impossible to reconstruct.*

## Single quality gate
`Quality integration gate / quality-integration` with `classify` job `scripts/ci/classify_change.py` → `lane`/`runtime_required`. `exact-artifact-e2e` and `release-deployment-evidence` run only when `runtime_required=true` (VPS/UBUNTU_WORKER per `data/contracts/change-control-policy-v1.json`). Adapter workflows no longer forbid `paths` on aggregate gate via conditional `needs.classify`.

## Production
Standing delegation `SEA_SPEED_PRODUCTION_DELEGATION_V1` in `production` environment + `verify_source_protection.py` (`quality-integration` only after S1) → `evaluate_production_policy.py` → `deploy-vps/ubuntu-worker` restricted transport. Issue/PR text not authority.

Adapters `AGENTS.md`, `SEA_SPEED_GOVERNANCE.md`, `SEA_SPEED_DELIVERY_POLICY.md`, `SEA_SPEED_TASK_RUNTIME.md`, `RELEASE_READINESS_GATE.md`, `task-intake.md`, `project-manager.md`, `PM_BOOTSTRAP.md`, `sea-speed-control-plane.md` reference this canonical file; they must not duplicate its semantics.

## Compatibility notes for thin adapters
Context compaction, session restart, connector truncation do not invalidate source authorization and do not return to DISCUSSION. Remediable internal failures (remedi) automatically continue via CI, not a blocker. While a safe authorized next action is executable now, do not return terminal WAITING_EXTERNAL. PR created, CI running, merge ready are not terminal. Checkpoint updates at meaningful transitions, not after every tool call. Terminal states are DONE, BLOCKED, HUMAN DECISION REQUIRED; `FAILED` is not a terminal interaction state but an internal event. Generation and delivery checkpoint semantics are preserved for v2 compat. External blocker requires evidence and unblock condition and next admissible action. Human decision required is structured and resumable with authorization and exact resume. Progress only statuses PR created, CI running are not terminal while a safe authorized next action is executable now. Waiting external is nonterminal and requires no executable work, no background polling, unchanged generation, one bounded observe. Checkpoint update is not a terminal handoff. Context loss is not a blocker or human decision. Sea Speed Delivery Checkpoint v2 machine-readable keys include generation and full project recovery. `CONTEXT_LOSS` is intentionally not a valid reason. Connector reads are mandatory fresh read when gate requires.
