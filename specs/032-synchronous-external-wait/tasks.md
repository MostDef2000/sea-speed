# Tasks: Synchronous External Wait

- Specification: specs/032-synchronous-external-wait/spec.md
- Plan: specs/032-synchronous-external-wait/plan.md
- Issue: #248

## Delivery tasks

- [x] T001 Record DR-007.
- [x] T002 Define synchronous session dispositions across approved active contracts/docs.
- [x] T003 Add Checkpoint v2 schema, validator, replay, and v1 upgrade.
- [x] T004 Add executable unittest behavioral and convergence coverage for the original non-CI wait/replay semantics.
- [x] T005 Resolve the v1-only Task Intake entrypoint under expanded source authorization.
- [x] T006 Validate exact scope, SDD, contracts, and full tests.
- [x] T007 Revise active contracts and SDD so a known `queued`/`in_progress` GitHub Actions run/check stays `ACTIVE` with foreground rate-limited exact-cursor observation and `WAITING_EXTERNAL` is reserved for non-CI external conditions and historical replay.
- [x] T008 Update 032 spec/plan/tasks NFR/risk/test/traceability and link Issue #337 authorization base `bb3ae2a9c7499d3a136416c106aae89bad816ac6`.
- [x] T009 Update 017 Scenario 7/FR-017/acceptance/NFR to make CI-pending non-terminal continuation explicit.
- [x] T010 Extend checkpoint disposition, contract-validator, terminal/resume and convergence tests for queued/running CI remaining `ACTIVE`, deterministic historical upgrade and failed-CI narrowing.
- [ ] T011 Open exact Change Contract PR and obtain final-head CI.
- [ ] T012 Merge exact green head, verify exact-main Quality, and record Issue evidence.

## Requirements traceability

- AC-001 | Task: T002 | Evidence: contract convergence tests | Coverage: COVERED
- AC-002 | Task: T003,T004 | Evidence: schema and invalid-combination tests | Coverage: COVERED
- AC-003 | Task: T004 | Evidence: pending and precedence tests | Coverage: COVERED
- AC-004 | Task: T004 | Evidence: replay transition tests | Coverage: COVERED
- AC-005 | Task: T004 | Evidence: terminal-condition tests | Coverage: COVERED
- AC-006 | Task: T003,T004 | Evidence: realistic v1 upgrade test | Coverage: COVERED
- AC-007 | Task: T006,T011,T012 | Evidence: local validation and CI | Coverage: COVERED
- AC-008 | Task: T007,T008,T009,T010 | Evidence: contract review and state-machine tests | Coverage: COVERED
- AC-009 | Task: T010 | Evidence: historical CI/non-CI replay state-machine tests | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] CI-pending semantics revised across active contracts and SDD
- [x] Issue #337 and authorization base linked
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
- [x] Spec, plan and tasks match implemented behavior.
- [ ] Required CI is green.
- [ ] Exact-green-head merge evidence is recorded in continuation Issue #337; original Issue #248 remains historical feature evidence.
- [x] Deployment/runtime acceptance is NOT REQUIRED.
