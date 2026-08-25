# Spec: Mandatory visible delivery todo contract

- Issue: #308
- Status: ACTIVE
- Runtime contour: NONE / CONTROL_PLANE

## Product outcome

Make the execution todo list a mandatory, current and visible transient projection of the canonical Issue `Sea Speed Delivery Checkpoint v2`, while preserving the Issue as durable delivery-control truth and removing contradictory GitHub routing from the local Delivery Orchestrator prompt.

## User scenarios

### Scenario 1 - Visible active execution

Given significant or multi-step delivery, when the Orchestrator starts or changes lifecycle phase, then the operator sees exactly one current todo concern plus newly completed and pending work.

### Scenario 2 - Honest external wait

Given no safe action is executable and one external cursor is pending, when the Orchestrator returns `WAITING_EXTERNAL`, then todo names that exact non-executable prerequisite and does not imply background work.

### Scenario 3 - Resume after task switch or context loss

Given a valid canonical Issue checkpoint, when delivery resumes, then the todo projection is reconstructed from that checkpoint without becoming authority or repeating Task Intake.

## Requirements

- R1: Significant or multi-step delivery creates a todo plan before execution and updates it immediately when instructions, lifecycle state, evidence cursor, blocker or next action changes.
- R2: `ACTIVE` work has exactly one current `in_progress` item while work remains; completed work is marked only after evidence exists.
- R3: `WAITING_EXTERNAL`, `BLOCKED`, `HUMAN DECISION REQUIRED` and terminal results keep todo state truthful and never imply background work.
- R4: Resume Probe reconstructs the transient todo projection from the durable Checkpoint without repeating Task Intake.
- R5: Startup/status and user-visible wait/terminal results expose a concise todo summary: current, newly completed and remaining/waiting work.
- R6: Todo never becomes source authorization, production authority or durable delivery-control truth.
- R7: GitHub routing is unambiguous: Issue/PR/API lifecycle uses Connector only; `gh` is not a fallback.

## NFR assessment

- NFR-056-001 | Area: reliability | Target: todo and checkpoint cannot materially contradict at a user-visible transition | Validation: static contract test + canonical contract review | Evidence: tests/test_delivery_todo_contract.py | Status: PASS
- NFR-056-002 | Area: usability | Target: every startup, wait and terminal response exposes current and remaining work concisely | Validation: required status/todo fields | Evidence: contracts/runtime/SEA_SPEED_TASK_RUNTIME.md | Status: PASS
- NFR-056-003 | Area: security | Target: todo cannot create source/runtime authority and no forbidden GitHub fallback is advertised | Validation: static contract test | Evidence: tests/test_delivery_todo_contract.py | Status: PASS

## Acceptance criteria

- AC-001: Canonical governance, policy, runtime and compatibility paths define the same todo truth class and update rules.
- AC-002: Required status output includes current todo, newly completed work and pending/waiting work.
- AC-003: The local Delivery Orchestrator prompt requires todo lifecycle updates and contains no `gh` PR fallback contradiction.
- AC-004: Static contract test, SDD/repository/contract/quality validators and full unittest discovery pass.

## Out of scope

Application/runtime behavior, deployment workflows, production settings, Docker credentials, `opencode.json`, Issue #305 implementation and PR #307 source are unchanged.

## Runtime feedback

- Runtime acceptance: NOT REQUIRED
- Accepted production behavior: NOT APPLICABLE; CONTROL_PLANE only
- Regressions/learning: NONE YET
- Follow-up work: resume Issue #305 from its persisted PR #307 cursor after this task
