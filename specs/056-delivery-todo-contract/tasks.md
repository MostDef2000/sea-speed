# Tasks: Mandatory visible delivery todo contract

- Specification: specs/056-delivery-todo-contract/spec.md
- Plan: specs/056-delivery-todo-contract/plan.md
- Issue: #308

## Delivery tasks

- [x] T001 Create SDD 056 with NFR assessment, risk/test design and traceability.
- [x] T002 Synchronize todo truth boundary, lifecycle and visible status across approved canonical entrypoints.
- [x] T003 Update the local Delivery Orchestrator prompt and remove the contradictory `gh` PR fallback.
- [x] T004 Add deterministic static contract coverage.
- [x] T005 Verify exact scope and run all required local validators/tests.
- [x] T006 Admit only the canonical agent path in repository validation with deterministic rejection of other `.opencode` paths.
- [ ] T007 Open the exact Change Contract PR and obtain exact-head required CI.
- [ ] T008 Merge exact green head, verify exact-main Quality and record terminal Issue evidence.

## Requirements traceability

- AC-001 | Task: T002 | Evidence: TEST-056-001 / tests/test_delivery_todo_contract.py | Coverage: COVERED
- AC-002 | Task: T002 | Evidence: TEST-056-002 / tests/test_delivery_todo_contract.py | Coverage: COVERED
- AC-003 | Task: T003 | Evidence: TEST-056-003 / tests/test_delivery_todo_contract.py | Coverage: COVERED
- AC-004 | Task: T005,T007,T008 | Evidence: TEST-056-004 / local validation + GitHub required checks | Coverage: COVERED
- AC-005 | Task: T006 | Evidence: TEST-056-005 / tests/test_delivery_todo_contract.py + scripts/ci/validate_repo.py | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [x] Deployment state resolved: NOT REQUIRED
- [x] Runtime acceptance resolved: NOT REQUIRED
- [x] Deferred work recorded: Issue #305 resume after this task
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current: NOT REQUIRED

## Completion gate

- [x] Requirements are covered by tasks and traceability.
- [x] Spec, plan and tasks match the implemented behavior.
- [ ] Required CI is green.
- [ ] Exact-green-head merge evidence is recorded in the canonical Issue.
- [x] Applicable deployment/runtime acceptance is complete, or explicitly NOT REQUIRED.
- [x] Runtime learning and deferred work are recorded.
