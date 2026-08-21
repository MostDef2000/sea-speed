# Tasks: Synchronous External Wait

- Specification: specs/032-synchronous-external-wait/spec.md
- Plan: specs/032-synchronous-external-wait/plan.md
- Issue: #248

## Delivery tasks

- [x] T001 Record DR-007.
- [x] T002 Define synchronous session dispositions across approved active contracts/docs.
- [x] T003 Add Checkpoint v2 schema, validator, replay, and v1 upgrade.
- [x] T004 Add executable unittest behavioral and convergence coverage.
- [x] T005 Resolve the v1-only Task Intake entrypoint under expanded source authorization.
- [x] T006 Validate exact scope, SDD, contracts, and full tests.
- [ ] T007 Open exact Change Contract PR and obtain final-head CI.
- [ ] T008 Merge exact green head, verify exact-main Quality, and record Issue evidence.

## Requirements traceability

- AC-001 | Task: T002 | Evidence: contract convergence tests | Coverage: COVERED
- AC-002 | Task: T003,T004 | Evidence: schema and invalid-combination tests | Coverage: COVERED
- AC-003 | Task: T004 | Evidence: pending and precedence tests | Coverage: COVERED
- AC-004 | Task: T004 | Evidence: replay transition tests | Coverage: COVERED
- AC-005 | Task: T004 | Evidence: terminal-condition tests | Coverage: COVERED
- AC-006 | Task: T003,T004 | Evidence: realistic v1 upgrade test | Coverage: COVERED
- AC-007 | Task: T006,T007,T008 | Evidence: local validation and CI | Coverage: PENDING

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and local evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [x] Deployment state resolved: NOT REQUIRED
- [x] Runtime acceptance resolved: NOT REQUIRED
- [x] Risks resolved or explicitly accepted

## Completion gate

- [x] Requirements are covered by tasks and traceability.
- [x] Spec, plan and tasks match implemented behavior.
- [ ] Required CI is green.
- [ ] Exact-green-head merge evidence is recorded in #248.
- [x] Deployment/runtime acceptance is NOT REQUIRED.
