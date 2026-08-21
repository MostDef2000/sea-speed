# Tasks: Resumable Delivery Orchestration

- Specification: specs/031-resumable-delivery-orchestration/spec.md
- Plan: specs/031-resumable-delivery-orchestration/plan.md
- Issue: #240

## Delivery tasks

- [x] T001 Record DR-006 and canonical truth-class / authorization-continuity model.
- [x] T002 Add Delivery Checkpoint v1, Resume Probe, monotonic transition and progressive Connector retrieval contracts across active entry points.
- [x] T003 Add deterministic resume-contract tests and extend convergence/terminal validation.
- [ ] T004 Verify exact 19-path diff and all local/repository contract tests.
- [ ] T005 Open exact Change Contract PR and obtain PR Validation + aggregate Quality on final head.
- [ ] T006 Merge exact green head and verify exact-main Quality; record terminal Issue evidence.

## Requirements traceability

- AC-001 | Task: T001 | Evidence: TEST-001 / tests/test_delivery_resume_contract.py | Coverage: COVERED
- AC-002 | Task: T001 | Evidence: TEST-001 / tests/test_delivery_resume_contract.py | Coverage: COVERED
- AC-003 | Task: T002 | Evidence: TEST-001 / tests/test_delivery_resume_contract.py | Coverage: COVERED
- AC-004 | Task: T002 | Evidence: TEST-002 / tests/test_delivery_resume_contract.py | Coverage: COVERED
- AC-005 | Task: T002 | Evidence: TEST-002 / tests/test_delivery_resume_contract.py | Coverage: COVERED
- AC-006 | Task: T002 | Evidence: TEST-002 / tests/test_delivery_resume_contract.py | Coverage: COVERED
- AC-007 | Task: T002 | Evidence: TEST-003 / tests/test_delivery_resume_contract.py | Coverage: COVERED
- AC-008 | Task: T003 | Evidence: TEST-004 / tests/test_delivery_terminal_states.py + tests/test_delivery_contract_convergence.py | Coverage: COVERED
- AC-009 | Task: T006 | Evidence: TEST-005 / GitHub PR Validation + aggregate Quality + exact-main Quality | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [x] Deployment state resolved: NOT REQUIRED
- [x] Runtime acceptance resolved: NOT REQUIRED
- [x] Deferred work recorded: NONE
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current: NOT REQUIRED

## Completion gate

- [x] Requirements are covered by tasks and traceability.
- [ ] Spec, plan and tasks match the implemented behavior.
- [ ] Required CI is green.
- [ ] Exact-green-head merge evidence is recorded in the canonical Issue.
- [x] Applicable deployment/runtime acceptance is complete, or explicitly NOT REQUIRED.
- [x] Runtime learning and deferred work are written back to the feature artifacts or recorded as approved follow-up.
