# Feature Specification: Resumable Delivery Orchestration

- Feature: 031-resumable-delivery-orchestration
- Issue: #240
- Status: Active
- Owner outcome: Delivery Orchestrator resumes an already-authorized task from durable bounded evidence instead of repeating bootstrap, intake, or equivalent Connector reads after context loss.

## Product outcome

Sea Speed delivery remains autonomous across context compaction, session restart, Connector truncation, and similar working-context loss. Once a source scope has passed the existing visible-Scope -> immediately-following `OUTCOME APPROVED` admission gate, the Orchestrator persists a compact Delivery Checkpoint in the canonical Issue and can resume the same exact scope from a bounded Resume Probe without asking the operator to repeat authorization or reconstructing the whole repository state.

## User scenarios

### Scenario 1 - Resume after context loss

Given an admitted Outcome with a valid canonical Issue checkpoint, when the Orchestrator loses transient conversational context, then it reads only the bounded resume evidence, preserves the current phase, and continues from `Next admissible action`.

### Scenario 2 - Preserve fail-closed authorization

Given a valid checkpoint for an exact approved scope, when a material outcome/path/security/protected-boundary/destructive change is discovered, then the checkpoint is invalidated for source continuation and a fresh visible Scope plus immediately-following `OUTCOME APPROVED` is required before the expanded write.

### Scenario 3 - Prevent Connector amplification

Given a known Issue/PR/head/evidence cursor, when the Orchestrator needs more evidence, then retrieval advances from known object metadata to only the targeted changed detail or failure fragment and does not repeat an equivalent read with unchanged evidence identity.

## Requirements

- FR-001: The control plane MUST distinguish repository/product truth, durable delivery-control truth, and transient interaction state.
- FR-002: A valid initial source admission MUST be durably receipted in the canonical Issue without turning Issue text into new source authority or production authority.
- FR-003: `Sea Speed Delivery Checkpoint v1` MUST record task identity, checkpoint generation, approved-scope identity, authorization base main, current phase, branch/PR/head when present, completed gates, evidence cursors, next admissible action, and state invalidation reason.
- FR-004: Recovery of a known task with a valid checkpoint MUST use a bounded Resume Probe before any full project recovery.
- FR-005: Context compaction, session restart, response/Connector truncation, or loss of transient model state MUST NOT invalidate source authorization, return an admitted task to `DISCUSSION`, or require repeated Task Intake by themselves.
- FR-006: Lifecycle transitions MUST be monotonic unless a concrete material invalidation reason is recorded.
- FR-007: Fresh source authorization MUST remain mandatory for material scope/protected-boundary changes.
- FR-008: Connector retrieval MUST be progressive and cursor-bound and MUST forbid equivalent repeated reads when the evidence identity and question are unchanged, except mandatory fresh-read gates.
- FR-009: Checkpoint persistence MUST be event-driven at meaningful phase/evidence transitions, not after every tool call.
- FR-010: `DONE`, `BLOCKED`, and `HUMAN DECISION REQUIRED` MUST remain the only terminal interaction states.

## Acceptance criteria

- AC-001: Active contracts explicitly define the three truth classes and make canonical Issue checkpoint evidence the durable continuation cursor while keeping `main` the repository/product source of truth.
- AC-002: Active contracts explicitly state that initial Scope/approval adjacency is an admission condition and that a durable receipt may only continue the same exact admitted scope.
- AC-003: The canonical checkpoint schema includes phase, approved-scope identity, authorization base, branch/PR/head, completed gates, evidence cursors, next admissible action, invalidation reason, task identity, and generation.
- AC-004: Bootstrap/recovery rules require Resume Probe for a known valid checkpoint and permit full project recovery only when the checkpoint is absent, unresolved, invalid, or materially contradicted.
- AC-005: Contracts explicitly state that context/session/Connector loss alone does not return the task to `DISCUSSION` or require another `OUTCOME APPROVED`.
- AC-006: Contracts define monotonic transitions plus concrete material invalidation reasons for backward/source-reauthorization paths.
- AC-007: Contracts define progressive `known object -> metadata -> targeted detail -> failure fragment` retrieval and a repeated-equivalent-read prohibition with mandatory-gate exception.
- AC-008: Deterministic resume/convergence/terminal tests enforce the new invariants while preserving the existing three terminal interaction states.
- AC-009: Exact 19-path implementation scope passes PR Validation, aggregate Quality, expected-head merge, and exact-main Quality with runtime deployment not required.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: Known valid checkpoint recovery requires no repeated Task Intake and no equivalent repeated Connector read with unchanged evidence identity | Validation: contract regression tests | Evidence: tests/test_delivery_resume_contract.py | Status: PASS
- NFR-002 | Area: SECURITY | Target: Durable receipt cannot create or widen source authority and never grants production authority | Validation: contract assertions across governance/delivery/runtime/bootstrap documents | Evidence: tests/test_delivery_resume_contract.py | Status: PASS
- NFR-003 | Area: OPERABILITY | Target: Resume state contains one explicit next admissible action and bounded evidence cursors | Validation: schema-marker tests | Evidence: tests/test_delivery_resume_contract.py | Status: PASS

## Compatibility and boundaries

- Stable public interfaces: existing `OUTCOME APPROVED` source-admission phrase, GitHub Issue/PR lifecycle, CI/merge/runtime authority model.
- Out of scope: `skills/**`, API/frontend/Worker/Water/Road/Camera behavior, production delegation, branch protection, secrets, deployment transport, release provenance, runtime acceptance behavior, historical Issue/PR/DR rewrites.
- Security constraints: checkpoint/Issue evidence proves continuation only; it never creates source or production authority. Material scope/protected-boundary changes still require fresh source authorization.

## Runtime feedback

- Runtime acceptance: NOT REQUIRED
- Accepted production behavior: NOT APPLICABLE; CONTROL_PLANE only
- Regressions/learning: NONE YET
- Follow-up work: NONE YET
