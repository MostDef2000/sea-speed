# Feature Specification: Synchronous External Wait

- Feature: 032-synchronous-external-wait
- Issue: #248
- Status: Active
- Owner outcome: A synchronous Delivery Orchestrator can stop safely for an exact non-CI external transition, while known queued/running GitHub Actions remains active and continues automatically without background-work claims, tight polling, or planning loops.

## Product outcome

Sea Speed delivery distinguishes work executable in the current invocation from progress that depends only on external machine-observable evidence. For non-CI external conditions the Orchestrator persists a structured wait predicate, returns control as nonterminal `WAITING_EXTERNAL`, and performs one bounded evidence observation on a later invocation. Unchanged evidence preserves the wait without replanning; changed evidence produces valid `ACTIVE` state and resumes execution.

A known GitHub Actions run or check that is `queued` or `in_progress` is never represented as `WAITING_EXTERNAL`. The invocation remains `ACTIVE`, foreground-waits, and re-observes only the exact run/check cursor through the official Connector at least 30 seconds after the previous equivalent status observation, with no observation count or deadline that itself hands control back, no busy/tight polling, and no checkpoint-generation churn per observation. Success continues automatically to the next gate; failure immediately narrows to failed job/log remediation. A Connector/provider capability outage that prevents this observation is `BLOCKED` or `HUMAN DECISION REQUIRED`, not CI pending.

## User scenarios

### Scenario 1 - Exact-head CI remains pending

Given all immediate work is complete and exact-head CI is queued or running, when no other safe action is executable, then the invocation remains `ACTIVE`, the Orchestrator foreground-waits on the exact run/check cursor, and observes again only after at least 30 seconds have passed since the previous equivalent status observation; success continues automatically to the next gate and failure immediately narrows to failed job/log remediation. The Orchestrator does not return `WAITING_EXTERNAL` merely because CI is pending.

### Scenario 2 - Non-CI external condition remains pending

Given all immediate work is complete and the sole remaining prerequisite is a non-CI machine-observable external transition, when no safe action is executable, then the Orchestrator records the exact evidence cursor and returns `WAITING_EXTERNAL` without claiming background execution.

### Scenario 3 - Resume with unchanged evidence

Given a valid non-CI wait checkpoint, when a later invocation observes the same cursor, then it preserves the wait and generation without full recovery or replanning.

### Scenario 4 - Resume after external completion

Given a valid non-CI wait checkpoint, when the exact cursor changes, then the Orchestrator increments generation, updates evidence, produces valid `ACTIVE` state, and executes the recorded action.

### Scenario 5 - Preserve terminal semantics

Given completion, a concrete blocker, or a protected human decision, when the invocation is classified, then it uses `DONE`, `BLOCKED`, or `HUMAN DECISION REQUIRED`; none is represented as `WAITING_EXTERNAL`.

## Requirements

- FR-001: Session disposition MUST be separate from lifecycle phase and terminal interaction state.
- FR-002: Session dispositions MUST be `ACTIVE`, `WAITING_EXTERNAL`, and `TERMINAL`.
- FR-003: `WAITING_EXTERNAL` MUST be nonterminal and MUST NOT imply background work.
- FR-004: Waiting MUST require no safe action executable now plus one named non-CI machine-observable condition; a known GitHub Actions run/check that is `queued` or `in_progress` MUST NOT satisfy this condition.
- FR-005: Checkpoint v2 MUST record action executability, disposition, external condition, resume trigger, and exact cursor.
- FR-006: Resume MUST permit one bounded observation of the exact non-CI wait cursor.
- FR-007: Unchanged evidence MUST preserve wait and generation without equivalent rereads or replanning.
- FR-008: Changed evidence MUST produce a valid new `ACTIVE` checkpoint and resume the recorded action.
- FR-009: Executable work MUST take precedence over waiting and MUST NOT coexist with a terminal condition.
- FR-010: `DONE`, `BLOCKED`, and `HUMAN DECISION REQUIRED` MUST remain the only terminal interaction states.
- FR-011: Persisted v1 checkpoints MUST remain readable and upgrade behaviorally without repeated authorization.
- FR-012: A known GitHub Actions run or check that is `queued` or `in_progress` MUST keep the invocation `ACTIVE`, foreground-wait on the exact run/check cursor, and re-observe only after at least 30 seconds since the previous equivalent status observation, with no observation count or deadline that hands control back, no busy/tight polling, and no checkpoint-generation churn per observation.
- FR-013: A Connector/provider capability outage that prevents GitHub Actions observation MUST be classified as `BLOCKED` or `HUMAN DECISION REQUIRED`, not as CI pending or `WAITING_EXTERNAL`.
- FR-014: A persisted pre-amendment CI `WAITING_EXTERNAL` checkpoint MUST upgrade to `ACTIVE` after one Resume Probe observation even when the exact run remains queued/in-progress, then continue foreground observation without repeated authorization.

## Acceptance criteria

- AC-001: Active contracts consistently define and distinguish session dispositions.
- AC-002: Schema and validator reject inconsistent action/wait/terminal combinations.
- AC-003: Replay proves pending non-CI work maps to waiting only after executable work is exhausted.
- AC-004: Replay proves unchanged evidence preserves generation and changed evidence yields valid active state.
- AC-005: Completion, blocker, and human-decision paths remain distinct.
- AC-006: A realistic v1 Markdown checkpoint upgrades to a valid same-scope v2 checkpoint.
- AC-007: Contract, repository, SDD, behavioral, PR Validation, and Quality checks pass on exact heads.
- AC-008: Active contracts explicitly state that a known `queued`/`in_progress` GitHub Actions run/check remains `ACTIVE` with foreground rate-limited exact-cursor observation, never returns `WAITING_EXTERNAL`, and treats Connector/provider capability outage as `BLOCKED` or `HUMAN DECISION REQUIRED`.
- AC-009: State-machine replay proves an unchanged historical CI wait cursor upgrades to `ACTIVE`, while an unchanged non-CI wait cursor preserves `WAITING_EXTERNAL` and generation.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: Same-cursor non-CI waits produce zero replanning loops and zero generation churn | Validation: deterministic replay tests | Evidence: tests/test_delivery_checkpoint_state_machine.py | Status: PASS
- NFR-002 | Area: OPERABILITY | Target: Every non-CI wait names a condition, trigger, unique cursor and next action | Validation: schema and validator | Evidence: schemas/delivery-checkpoint-v2.schema.json, scripts/ci/validate_delivery_checkpoint.py | Status: PASS
- NFR-003 | Area: SECURITY | Target: Wait cannot replace human authorization, protected input, or a blocker; a newly validated queued/in_progress GitHub Actions run/check cannot be represented as `WAITING_EXTERNAL`, while pre-amendment CI waits remain readable only for deterministic upgrade | Validation: state-machine and terminal tests | Evidence: tests/test_delivery_checkpoint_state_machine.py, tests/test_delivery_terminal_states.py | Status: PASS
- NFR-004 | Area: RELIABILITY | Target: CI pending is foreground-waited with at least 30 seconds between equivalent status observations, no observation-count/deadline that hands control back, no busy/tight polling, and no checkpoint-generation churn per observation | Validation: contract review and state-machine tests | Evidence: `AGENTS.md`, `contracts/SEA_SPEED_GOVERNANCE.md`, `contracts/SEA_SPEED_DELIVERY_POLICY.md`, `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`, `contracts/runtime/RELEASE_READINESS_GATE.md`, `contracts/branches/project-manager.md`, `tests/test_delivery_checkpoint_state_machine.py` | Status: PASS

## Compatibility and boundaries

- Stable interfaces: `OUTCOME APPROVED`, lifecycle phases, three terminal interaction states, Issue/PR/CI lifecycle.
- Compatibility: persisted v1 checkpoints upgrade through tested repository tooling.
- Out of scope: production delegation, secrets, branch settings, deployment workflows, product/runtime behavior, rewriting #240, and merging #247.
- Runtime impact: CONTROL_PLANE only; deployment and runtime acceptance are not required.

## Runtime feedback

- Runtime acceptance: NOT REQUIRED
- Accepted production behavior: NOT APPLICABLE; CONTROL_PLANE only
- Source authorization continuation: Issue #337, authorization base `bb3ae2a9c7499d3a136416c106aae89bad816ac6`.
- Regressions/learning: NONE YET
- Follow-up work: NONE YET
