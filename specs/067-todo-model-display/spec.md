# Feature Specification: Todo model display

- Feature: 067-todo-model-display
- Issue: #333
- Status: ACTIVE
- Owner outcome: Every Sea Speed startup, wait, blocker and terminal block displays the active orchestrator and worker model under todo.

## Product outcome

Make the AI model serving the current todo visible: every Sea Speed status block shows `Model / orchestrator` and `Model / active worker` directly under the three todo lines, distinguishing the session primary from any transient specialist delegation.

## User scenarios

### Scenario 1 - Startup visibility

Given a new or resumed delivery, when the startup Sea Speed Task Runtime block is shown, then the three todo lines are followed by the orchestrator model and the active worker model or `none`.

### Scenario 2 - Waiting with delegation

Given a delegated specialist is active when `WAITING_EXTERNAL` is recorded, when the wait block is rendered, then `Model / active worker` shows the worker model and role, otherwise `none`.

### Scenario 3 - Resume probe consistency

Given a valid checkpoint, when Resume Probe reconstructs todo, then the model lines are reconstructed from the current assignment cache without claiming durable delivery-control truth.

## Requirements

- R1: Every startup and user-visible wait, blocker, decision and terminal result MUST show `Model / orchestrator:` and `Model / active worker:` immediately after the todo triad.
- R2: `Model / active worker` MUST be `none` when no specialist is delegated and `model (role)` when one is, sourced from the health-aware assignment cache at render time.
- R3: The seven canonical entrypoints MUST define the same two model lines as part of the todo projection contract.
- R4: Todo remains transient projection; model display MUST NOT create source, merge or runtime authority nor widen approved scope.
- R5: No transient model ID is hardcoded in Sea Speed source; global `~/.cache/opencode/model-assignment.json` remains the owner.

## Acceptance criteria

- AC-001: Startup block displays orchestrator and worker model lines.
- AC-002: `WAITING_EXTERNAL`/`BLOCKED`/`HUMAN DECISION REQUIRED` blocks display both model lines with `none` or the exact worker model.
- AC-003: All seven canonical entrypoints contain both model line markers and the update timing rule.
- AC-004: Contract tests assert the two model lines and reject a missing line.
- AC-005: Full local delivery runner and exact allowlist remain green.

## NFR assessment

- NFR-067-001 | Area: SECURITY | Target: zero credential or transient model ID hardcoded in repository; model display sourced at render time | Validation: static contract tests and changed-file review | Evidence: tests/test_delivery_todo_contract.py and contracts | Status: PASS
- NFR-067-002 | Area: USABILITY | Target: every status/terminal output exposes current todo and both model lines concisely | Validation: contract assertions and manual block review | Evidence: contracts/runtime/SEA_SPEED_TASK_RUNTIME.md | Status: PASS
- NFR-067-003 | Area: RELIABILITY | Target: todo and model lines cannot imply durable truth when checkpoint disagrees | Validation: existing Resume Probe contract tests | Evidence: tests/test_delivery_todo_contract.py | Status: PASS

## Compatibility and boundaries

- Stable public interfaces: existing application URLs/APIs and runtime contours unchanged.
- Out of scope: production policy, standing delegation, secrets, GitHub settings, deployment workflows, runtime transport, application source, global assignment generation and health-check implementation.
- Security constraints: deny-by-default routing; FREE workers receive no secrets.

## Runtime feedback

- Runtime acceptance: CONTROL_PLANE restart verification after exact-main Quality.
- Accepted production behavior: PENDING.
- Regressions/learning: NONE YET.
- Follow-up work: NONE YET.
