# Implementation Plan: Mandatory visible delivery todo contract

- Specification: specs/056-delivery-todo-contract/spec.md
- Issue: #308
- Status: Active

## Architecture

Keep the canonical Issue `Sea Speed Delivery Checkpoint v2` as durable delivery-control truth and use `todowrite` only as a transient operational projection. The projection mirrors current phase, completed gates, disposition and `Next admissible action`, is replaced on task switch, and is reconstructed through bounded Resume Probe. Required status and wait/terminal output expose current, newly completed and pending/waiting work.

## Decisions

### D-001 - Projection, not another state store

- Decision: Todo is transient presentation state and never authorization, authority, evidence or durable continuation.
- Reason: A second durable task cursor could contradict the canonical Issue and weaken fail-closed admission.
- Alternatives rejected: chat-only implicit progress is invisible; todo as authority creates an uncontrolled fourth truth class.

### D-002 - One truthful current concern

- Decision: Keep exactly one current todo concern while work remains, executable under `ACTIVE` and explicitly non-executable for waits, blockers and decisions.
- Reason: This makes synchronous execution legible without promising background work.
- Alternatives rejected: several simultaneous in-progress items obscure the next action; no current item hides delivery state.

### D-003 - Connector-only GitHub API lifecycle

- Decision: Remove the local prompt's contradictory `gh` PR fallback and retain Connector-only Issue/PR/API routing.
- Reason: Availability cannot widen the deny-by-default allowlist.
- Alternatives rejected: `gh` or bash API publication bypasses the canonical Connector route.

## Affected contours

- Repository: governance/runtime contracts, compatibility bootstrap paths, local agent prompt, SDD and deterministic contract test.
- VPS: NONE
- Ubuntu worker/relay: NONE
- Windows worker/AI: NONE; retired contour unchanged
- Public interfaces: NONE

## Validation

- Unit: `python3 -m unittest tests.test_delivery_todo_contract -v`.
- Integration: canonical SDD, repository, contract and quality validators plus full unittest discovery.
- End-to-end: exact-head PR Validation, Quality integration, expected-head merge and exact-main Quality.
- Runtime acceptance: NOT REQUIRED; control-plane-only source change.

## Risk profile

- Risk profile: REQUIRED
- RISK-056-001 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: define todo as transient projection and preserve Issue checkpoint as durable truth | Validation: tests/test_delivery_todo_contract.py | Residual risk: LOW after cross-file assertions | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-056-002 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: require immediate updates at meaningful transitions and checkpoint-based reconstruction | Validation: tests/test_delivery_todo_contract.py | Residual risk: LOW after runtime contract assertions | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-056-003 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: deny todo authority and remove contradictory gh fallback | Validation: tests/test_delivery_todo_contract.py | Residual risk: LOW after routing assertions | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-056-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_delivery_todo_contract.py canonical-entrypoint assertions
- TEST-056-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_delivery_todo_contract.py visible status-field assertions
- TEST-056-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_delivery_todo_contract.py Connector-only routing assertions
- TEST-056-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: canonical validators and full unittest discovery

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

Not required: no `deploy/**`, `scripts/release/**`, deployment workflow, runtime deployment requirement or `PRODUCTION_LEARNING` change is in scope.

## Rollout and rollback

- Rollout: merge the synchronized contracts after exact-head validation; future Delivery Orchestrator sessions adopt the todo projection from current `main`.
- Rollback: revert the source commit through the protected lifecycle if the contract introduces a delivery-control regression; no runtime rollback is required.

## Runtime feedback

- Actual architecture after acceptance: PENDING exact-main integration
- Differences from plan: NONE YET
- Deferred cleanup: NONE YET
