# Implementation Plan: Synchronous External Wait

- Specification: specs/032-synchronous-external-wait/spec.md
- Issue: #248
- Status: Active

## Architecture

Keep lifecycle phases and three terminal interaction states. Add an orthogonal synchronous session-disposition state machine. Delivery Checkpoint v2 is JSON in the canonical Issue. Its schema encodes disposition shape, while a dependency-free validator enforces cross-object invariants, parses persisted v1 Markdown, and applies deterministic replay transitions.

## Decisions

### D-001 - Wait is a session disposition

- Decision: Model `WAITING_EXTERNAL` outside lifecycle and terminal state.
- Reason: A pending non-CI external transition may pause an invocation without moving delivery backwards or finishing the task; known queued/running GitHub Actions remains `ACTIVE` under D-005.

### D-002 - Exact predicate, no scheduler fiction

- Decision: Record condition, trigger, unique cursor, and non-executable next action; perform no background polling.
- Reason: The agent has synchronous invocations only.

### D-003 - One-observation replay

- Decision: Same cursor preserves the checkpoint; changed cursor increments generation and returns a valid active checkpoint.
- Reason: This discovers progress without equivalent-read amplification.

### D-004 - Behavioral v1 compatibility

- Decision: Parse existing v1 Markdown and upgrade it at a meaningful transition while preserving authorization evidence.
- Reason: v1 records are persisted audit/control evidence and cannot be discarded or rewritten.

### D-005 - CI pending stays ACTIVE

- Decision: A known GitHub Actions run or check that is `queued` or `in_progress` is never represented as `WAITING_EXTERNAL`; the invocation remains `ACTIVE` and foreground-waits with rate-limited exact-cursor observation.
- Reason: CI pending is a deterministic transient state that the official Connector can observe directly; returning `WAITING_EXTERNAL` would hand control back unnecessarily and create a resume gap for a condition that should resolve within the same synchronous invocation.

## Affected contours

- Repository: governance/runtime contracts, control-plane docs, schema, CI validator, tests, and SDD.
- VPS: NONE
- Ubuntu Worker/relay: NONE
- Production deployment: NOT REQUIRED

## Validation

- Behavioral: pending non-CI wait, queued/running CI remains active, executable precedence, unchanged, changed, terminal conflict, unique cursor, v1 upgrade.
- Static: JSON/Python syntax, contract/SDD/repository validators.
- CI: PR Validation and aggregate Quality on exact head; exact-main Quality after merge.
- Runtime acceptance: NOT REQUIRED.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: explicit action executability and valid replay transitions | Validation: tests/test_delivery_checkpoint_state_machine.py | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: reject terminal conditions with executable work and preserve authorization evidence during v1 upgrade | Validation: behavioral tests | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: RELIABILITY | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: explicit exclusion of CI pending from `WAITING_EXTERNAL`, minimum 30-second interval between equivalent observations, no observation-count/deadline that hands control back, and no checkpoint-generation churn per observation | Validation: contract review and state-machine tests | Residual risk: LOW | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: resume, terminal, convergence tests
- TEST-002 | Covers: AC-002,AC-003 | Level: unit | Priority: P0 | Evidence: invalid combination and precedence tests
- TEST-003 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: unchanged/changed replay tests
- TEST-004 | Covers: AC-005,AC-006 | Level: unit | Priority: P0 | Evidence: terminal and v1 migration tests
- TEST-005 | Covers: AC-007 | Level: integration | Priority: P1 | Evidence: local suite and GitHub CI
- TEST-006 | Covers: AC-008,AC-009 | Level: unit | Priority: P0 | Evidence: CI-pending remains ACTIVE, historical CI wait upgrades, non-CI unchanged replay remains waiting, rate-limit interval, no generation churn, failure narrows to job/log remediation

## Correct-course check

- Trigger: NONE
- Issue impact: #337; semantics of CI-pending vs `WAITING_EXTERNAL` clarified.
- Specification impact: Added CI-pending foreground-wait semantics: known `queued`/`in_progress` GitHub Actions run/check stays `ACTIVE` with rate-limited exact-cursor observation and is never represented as `WAITING_EXTERNAL`; Connector/provider outage is `BLOCKED` or `HUMAN DECISION REQUIRED`.
- Plan impact: Added decision D-005, risk RISK-003, and test TEST-006 for CI-pending behavior.
- Tasks impact: Existing implementation tasks unchanged; validation broadened.
- Authorization impact: NONE; revision remains inside Issue #337 authorized scope.
- Follow-up: NONE.

## Deployment transaction audit

Not required: no deployment or runtime source changes.

## Rollout and rollback

- Rollout: merge the exact validated control-plane head; new checkpoints use v2 and active v1 evidence upgrades at meaningful transitions.
- Rollback: revert through protected source lifecycle; no runtime rollback required.

## Runtime feedback

- Actual architecture after acceptance: PENDING exact-main integration
- Differences from plan: Review strengthened schema, replay, terminal conflict, and v1 migration behavior.
- Deferred cleanup: NONE
