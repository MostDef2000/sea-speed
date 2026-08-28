# Specification: Two-intent delivery automation

- Issue: #178
- Active governance continuation: #195
- Status: In implementation

## Product outcome

Sea Speed delivery requires only genuinely protected decisions. Deterministic branch, PR, CI, merge and deployment stages remain repository-owned and fail closed. Source authorization is immediately preceded by visible exact Scope, and the Orchestrator retains execution ownership until a valid terminal interaction boundary.

## User scenarios

### Scenario 1 - Scope is visible before source approval
The complete six-field Scope is the last substantive assistant content before the immediately following `OUTCOME APPROVED`.

### Scenario 2 - Source delivery continues after one approval
After valid source admission, branch, implementation, metadata repair, in-scope CI remediation and exact-green-head merge continue without another routine source approval.

### Scenario 3 - Production authority remains separate
Production execution is governed by independently administered standing delegation intersected with repository policy; repository comments and hashes are not authority.

### Scenario 4 - Ubuntu deployment is one transaction
Protected Ubuntu delivery owns preparation, activation, verification, evidence and rollback as one target-side transaction.

### Scenario 5 - Missing execution capability fails closed
A required runtime contour cannot be admitted with missing execution capability.

### Scenario 6 - Misordered source approval fails closed
A bare, stale or non-adjacent approval cannot authorize writes and requires a newly displayed Scope followed by fresh approval.

### Scenario 7 - Orchestrator returns control only at a real terminal interaction boundary
After authorization, every safe deterministic action continues. PR creation, remediable source/test/metadata/CI failure, merge readiness, packaging or deployment start cannot end the invocation. A known GitHub Actions run/check that is `queued` or `in_progress` remains `ACTIVE`, foreground-waits on only the exact Connector cursor, and is re-observed at least 30 seconds after the previous equivalent observation, with no observation count or deadline that hands control back, no busy/tight polling, and no checkpoint-generation churn per observation. Success continues automatically; failure immediately narrows to failed job/log remediation. Control returns only as `DONE`, `BLOCKED`, or `HUMAN DECISION REQUIRED`.

## Requirements

- FR-001: One admitted `OUTCOME APPROVED` authorizes deterministic reversible source lifecycle within exact scope.
- FR-002: Material outcome/path/protected-boundary change requires fresh authorization.
- FR-003: Source authority and production authority remain separate.
- FR-004: Runtime routing is deterministic and fail closed.
- FR-005: Required contours declare valid execution capability.
- FR-006: Exact-main quality and provenance precede runtime transport.
- FR-007: Existing security, provenance, rollback, media and algorithm boundaries are not weakened.
- FR-008: Every approval request is preceded by complete visible Scope.
- FR-009: Admission requires `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, and `SOURCE_AUTHORIZATION_ADMISSION=OPEN`.
- FR-010: Only `DONE`, `BLOCKED`, and `HUMAN DECISION REQUIRED` are terminal interaction states; `FAILED` is an internal event.
- FR-011: A known GitHub Actions run/check that is `queued` or `in_progress` keeps the invocation `ACTIVE` with foreground exact-cursor observation and is never represented as `WAITING_EXTERNAL`.

## Acceptance criteria

- AC-001: One source authorization covers the exact deterministic source lifecycle.
- AC-002: In-scope CI remediation does not require another approval.
- AC-003: Runtime capability and provenance validation remain fail closed.
- AC-004: Existing protected boundaries remain unchanged.
- AC-005: Scope-before-approval ordering and fail-closed admission converge across active contracts.
- AC-006: Three terminal states and automatic continuation converge across active contracts and tests.
- AC-007: The six canonical contracts state that queued/in-progress CI stays `ACTIVE`, is observed through the exact Connector cursor at least 30 seconds apart, does not justify `WAITING_EXTERNAL`, and treats Connector/provider capability outage as `BLOCKED` or `HUMAN DECISION REQUIRED`.

## NFR assessment

- NFR-001 | Area: Operator UX | Target: one source decision and zero intermediate deterministic confirmations | Validation: canonical contracts | Evidence: `AGENTS.md`, `contracts/**` | Status: PASS
- NFR-002 | Area: Security | Target: source and runtime authority remain separate and fail closed | Validation: policy tests | Evidence: `scripts/quality/validate_workflow_policy.py` | Status: PASS
- NFR-003 | Area: Reliability | Target: active work continues until a valid terminal interaction boundary | Validation: terminal-state tests | Evidence: `tests/test_delivery_terminal_states.py` | Status: PASS
- NFR-004 | Area: Orchestration reliability | Target: queued/in-progress CI remains `ACTIVE` with rate-limited exact-cursor foreground observation and never becomes `WAITING_EXTERNAL` | Validation: convergence/state-machine tests | Evidence: `tests/test_delivery_checkpoint_state_machine.py`, `tests/test_delivery_contract_convergence.py` | Status: PASS

## Runtime feedback

- Runtime acceptance for this control-plane continuation: NOT REQUIRED.
- Production mutation: NONE.
