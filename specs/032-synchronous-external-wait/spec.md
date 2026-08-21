# Feature Specification: Synchronous External Wait

- Feature: 032-synchronous-external-wait
- Issue: #248
- Status: Active
- Owner outcome: A synchronous Delivery Orchestrator can stop safely for an exact external transition and later resume without background-work claims, repeated polling, or planning loops.

## Product outcome

Sea Speed delivery distinguishes work executable in the current invocation from progress that depends only on external machine-observable evidence. The Orchestrator persists a structured wait predicate, returns control as nonterminal `WAITING_EXTERNAL`, and performs one bounded evidence observation on a later invocation. Unchanged evidence preserves the wait without replanning; changed evidence produces valid `ACTIVE` state and resumes execution.

## User scenarios

### Scenario 1 - Exact-head CI remains pending

Given all immediate work is complete and exact-head CI is queued or running, when no other safe action is executable, then the Orchestrator records the exact run cursor and returns `WAITING_EXTERNAL` without claiming background execution.

### Scenario 2 - Resume with unchanged evidence

Given a valid wait checkpoint, when a later invocation observes the same cursor, then it preserves the wait and generation without full recovery or replanning.

### Scenario 3 - Resume after external completion

Given a valid wait checkpoint, when the exact cursor changes, then the Orchestrator increments generation, updates evidence, produces valid `ACTIVE` state, and executes the recorded action.

### Scenario 4 - Preserve terminal semantics

Given completion, a concrete blocker, or a protected human decision, when the invocation is classified, then it uses `DONE`, `BLOCKED`, or `HUMAN DECISION REQUIRED`; none is represented as `WAITING_EXTERNAL`.

## Requirements

- FR-001: Session disposition MUST be separate from lifecycle phase and terminal interaction state.
- FR-002: Session dispositions MUST be `ACTIVE`, `WAITING_EXTERNAL`, and `TERMINAL`.
- FR-003: `WAITING_EXTERNAL` MUST be nonterminal and MUST NOT imply background work.
- FR-004: Waiting MUST require no safe action executable now plus one named machine-observable condition.
- FR-005: Checkpoint v2 MUST record action executability, disposition, external condition, resume trigger, and exact cursor.
- FR-006: Resume MUST permit one bounded observation of the exact cursor.
- FR-007: Unchanged evidence MUST preserve wait and generation without equivalent rereads or replanning.
- FR-008: Changed evidence MUST produce a valid new `ACTIVE` checkpoint and resume the recorded action.
- FR-009: Executable work MUST take precedence over waiting and MUST NOT coexist with a terminal condition.
- FR-010: `DONE`, `BLOCKED`, and `HUMAN DECISION REQUIRED` MUST remain the only terminal interaction states.
- FR-011: Persisted v1 checkpoints MUST remain readable and upgrade behaviorally without repeated authorization.

## Acceptance criteria

- AC-001: Active contracts consistently define and distinguish session dispositions.
- AC-002: Schema and validator reject inconsistent action/wait/terminal combinations.
- AC-003: Replay proves pending work maps to waiting only after executable work is exhausted.
- AC-004: Replay proves unchanged evidence preserves generation and changed evidence yields valid active state.
- AC-005: Completion, blocker, and human-decision paths remain distinct.
- AC-006: A realistic v1 Markdown checkpoint upgrades to a valid same-scope v2 checkpoint.
- AC-007: Contract, repository, SDD, behavioral, PR Validation, and Quality checks pass on exact heads.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: Same-cursor waits produce zero replanning loops and zero generation churn | Validation: deterministic replay tests | Evidence: tests/test_delivery_checkpoint_state_machine.py | Status: PASS
- NFR-002 | Area: OPERABILITY | Target: Every wait names a condition, trigger, unique cursor and next action | Validation: schema and validator | Evidence: schemas/delivery-checkpoint-v2.schema.json, scripts/ci/validate_delivery_checkpoint.py | Status: PASS
- NFR-003 | Area: SECURITY | Target: Wait cannot replace human authorization, protected input, or a blocker | Validation: state-machine and terminal tests | Evidence: tests/test_delivery_checkpoint_state_machine.py, tests/test_delivery_terminal_states.py | Status: PASS

## Compatibility and boundaries

- Stable interfaces: `OUTCOME APPROVED`, lifecycle phases, three terminal interaction states, Issue/PR/CI lifecycle.
- Compatibility: persisted v1 checkpoints upgrade through tested repository tooling.
- Out of scope: production delegation, secrets, branch settings, deployment workflows, product/runtime behavior, rewriting #240, and merging #247.
- Runtime impact: CONTROL_PLANE only; deployment and runtime acceptance are not required.

## Runtime feedback

- Runtime acceptance: NOT REQUIRED
- Accepted production behavior: NOT APPLICABLE; CONTROL_PLANE only
- Regressions/learning: NONE YET
- Follow-up work: NONE YET
