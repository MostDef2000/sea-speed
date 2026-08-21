# Implementation Plan: Resumable Delivery Orchestration

- Specification: specs/031-resumable-delivery-orchestration/spec.md
- Issue: #240
- Status: Active

## Architecture

Keep one Delivery Orchestrator and add a compact durable execution cursor rather than another workflow engine. Repository/product truth stays in protected `main`; delivery-control truth stays in the canonical Issue; initial authorization still originates in the transient adjacent Scope/approval interaction. A `Sea Speed Delivery Checkpoint v1` is written at meaningful lifecycle/evidence transitions. Recovery of a known task performs a bounded Resume Probe against current `main`, the canonical Issue checkpoint, and only the exact referenced PR/head/status evidence that may have changed.

Connector reads are progressive and evidence-cursor based. Equivalent reads of the same object/question/evidence identity are not admissible unless a canonical gate explicitly requires a fresh read.

## Decisions

### D-001 - Durable Issue checkpoint, not a second state store

- Decision: Persist resumable delivery-control state as a compact checkpoint in the canonical Issue.
- Reason: Issues are already canonical task/source-authorization history and survive chat context loss without creating another source of truth.
- Alternatives rejected: chat transcript only is not durable; a separate external database/plugin would create another control plane and violate current tool routing.

### D-002 - Admission receipt differs from authority creation

- Decision: Preserve visible-Scope adjacency as the only initial source-admission path; use the durable receipt solely to continue the same exact admitted scope.
- Reason: Resumability must not weaken fail-closed source authorization.
- Alternatives rejected: requiring adjacency on every resume causes repeat-approval loops; treating any Issue text as authority permits self-issued expansion.

### D-003 - Monotonic phase plus explicit invalidation

- Decision: Context loss cannot move lifecycle state backwards. Backward/source-reauthorization transitions require a recorded material invalidation reason.
- Reason: A model-memory failure is not a product/scope state change.
- Alternatives rejected: implicit re-bootstrap on uncertainty repeats intake and increases Connector/context pressure.

### D-004 - Progressive Connector retrieval

- Decision: Use `known object -> metadata -> targeted detail -> failure fragment`, guarded by evidence cursors and repeated-equivalent-read prohibition.
- Reason: Minimize context amplification while still allowing mandatory fresh merge/release gates.
- Alternatives rejected: broad repository/Issue/PR/log traversal on every recovery.

## Affected contours

- Repository: governance/runtime contracts, bootstrap/control-plane docs, SDD and deterministic contract tests only.
- VPS: NONE
- Ubuntu worker/relay: NONE
- Windows worker/AI: NONE; retired production contour remains unchanged.
- Public interfaces: NONE

## Validation

- Static/CI: `tests/test_delivery_resume_contract.py`, `tests/test_delivery_terminal_states.py`, `tests/test_delivery_contract_convergence.py`, `scripts/ci/validate_contracts.py`, repository SDD/Change Contract validation, PR Validation, aggregate Quality.
- Integration: exact 19-path diff and exact-head PR/merge checks.
- Runtime acceptance: NOT REQUIRED; control-plane-only source change.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: distinguish initial authorization creation from durable continuation receipt; assert checkpoint cannot widen source or production authority | Validation: tests/test_delivery_resume_contract.py | Residual risk: LOW after fail-closed assertions and unchanged material-reauthorization rule | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: monotonic phase rule, explicit invalidation reasons, evidence cursors and bounded Resume Probe | Validation: tests/test_delivery_resume_contract.py and convergence tests | Residual risk: LOW; external tool implementations may still truncate but recovery semantics remain deterministic | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002,AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_delivery_resume_contract.py truth classes, authorization receipt and checkpoint schema assertions
- TEST-002 | Covers: AC-004,AC-005,AC-006 | Level: unit | Priority: P0 | Evidence: tests/test_delivery_resume_contract.py resume-probe, context-loss and monotonic-transition assertions
- TEST-003 | Covers: AC-007 | Level: unit | Priority: P0 | Evidence: tests/test_delivery_resume_contract.py progressive retrieval and equivalent-read guard assertions
- TEST-004 | Covers: AC-008 | Level: integration | Priority: P1 | Evidence: tests/test_delivery_terminal_states.py plus tests/test_delivery_contract_convergence.py
- TEST-005 | Covers: AC-009 | Level: end-to-end | Priority: P1 | Evidence: exact-head PR Validation, aggregate Quality, expected-head merge and exact-main Quality

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

Not required: no `deploy/**`, `scripts/release/**`, deployment workflow, runtime deployment requirement, or `PRODUCTION_LEARNING` change is in scope.

## Rollout and rollback

- Rollout: merge the governance/control-plane contract change after exact-head validation; future Delivery Orchestrator sessions adopt resume semantics from current `main`.
- Rollback: revert the governance commit through normal protected source lifecycle if the contract creates an unintended admission/recovery regression; no runtime rollback is required.

## Runtime feedback

- Actual architecture after acceptance: PENDING exact-main integration
- Differences from plan: NONE YET
- Deferred cleanup: NONE YET
