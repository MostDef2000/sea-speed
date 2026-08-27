# Tasks: Todo model display

- Specification: specs/067-todo-model-display/spec.md
- Plan: specs/067-todo-model-display/plan.md
- Issue: #333

## Delivery tasks

- [x] T001 Record Issue #333 Outcome, authorization receipt and Checkpoint v2.
- [x] T002 Create SDD 067 with NFR, risk/test design, correct-course and traceability.
- [x] T003 Extend the seven canonical entrypoints with the two model lines under the todo triad.
- [x] T004 Update the exact contract test to require both model lines.
- [x] T005 Run full local validation and resolve findings.
- [x] T006 Verify exact changed-file scope and synchronize SDD evidence.
- [ ] T007 Open one bounded Change Contract PR and obtain exact-head required CI.
- [ ] T008 Merge exact green head, verify exact-main Quality and restart OpenCode for control-plane acceptance.

## Requirements traceability

- AC-001 | Task: T003,T004 | Evidence: TEST-067-001 / tests/test_delivery_todo_contract.py | Coverage: COVERED
- AC-002 | Task: T003,T004 | Evidence: TEST-067-001 / contract status blocks | Coverage: COVERED
- AC-003 | Task: T003,T004 | Evidence: TEST-067-001 / seven entrypoints | Coverage: COVERED
- AC-004 | Task: T004,T005 | Evidence: TEST-067-002 / contract test + validators | Coverage: COVERED
- AC-005 | Task: T005,T006 | Evidence: TEST-067-002 / delivery runner and exact scope | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current.
- [x] Exact changed-file scope verified: eleven approved paths only.
- [x] Required local tests and evidence complete: contract tests, validators, 571 unittest, quality gates green.
- [ ] Required CI green.
- [ ] Exact-green-head merge complete.
- [x] Deployment state resolved: NOT REQUIRED.
- [ ] Runtime acceptance resolved: post-restart control-plane verification pending.
- [x] Deferred work recorded: NONE.
- [x] Risks resolved or explicitly accepted.
- [x] Waivers resolved or current: NOT REQUIRED.

## Completion gate

- [x] Requirements are covered by tasks and traceability.
- [x] Spec, plan and tasks match the intended implementation.
- [ ] Required local and GitHub CI evidence is green.
- [ ] Exact-main source and Quality evidence is recorded in Issue #333.
- [ ] Post-restart default-agent, worker and model-display evidence is recorded.
