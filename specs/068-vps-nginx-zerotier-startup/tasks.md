# Tasks: VPS nginx ZeroTier startup resilience

- Specification: specs/068-vps-nginx-zerotier-startup/spec.md
- Plan: specs/068-vps-nginx-zerotier-startup/plan.md
- Issue: #327

## Delivery tasks

- [x] T001 Record production failure evidence, fresh Scope, authorization receipt and Checkpoint generation 8.
- [x] T002 Create SDD 068 with NFRs, full risk profile, test design and eight-stage deployment transaction audit.
- [x] T003 Add the fixed no-argument bounded ZeroTier address wait helper.
- [x] T004 Add the nginx systemd drop-in with `Wants`/`After`, pre-preflight condition and controlled retry.
- [x] T005 Extend the exact-source privilege installer with transactional asset/state install, activation and rollback.
- [x] T006 Bind both assets into deterministic VPS exact artifacts and documentation.
- [x] T007 Add P0 helper/systemd/installer/artifact tests including injected rollback.
- [x] T008 Run full local validation, independent review, exact scope and secret/runtime-artifact checks.
- [ ] T009 Create one bounded PR, pass exact-head required CI, merge exact green head and verify exact-main Quality.
- [ ] T010 Execute exact-source root bootstrap, protected VPS deployment and typed runtime evidence.
- [ ] T011 Verify public root, protected Auth flow and authenticated Road module/canvas acceptance; record final DONE checkpoint.

## Requirements traceability

- AC-001 | Task: T003,T007 | Evidence: TEST-068-001 / helper subprocess tests | Coverage: COVERED
- AC-002 | Task: T004,T007 | Evidence: TEST-068-002 / systemd section and syntax checks | Coverage: COVERED
- AC-003 | Task: T005,T007 | Evidence: TEST-068-003 / test-root install and injected rollback | Coverage: COVERED
- AC-004 | Task: T006,T007 | Evidence: TEST-068-004 / deterministic exact artifact build and validation | Coverage: COVERED
- AC-005 | Task: T008,T009 | Evidence: TEST-068-004 | Coverage: COVERED
- AC-006 | Task: T010,T011 | Evidence: TEST-068-005 | Coverage: COVERED
- AC-007 | Task: T010,T011 | Evidence: TEST-068-006 | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current for the admitted outcome.
- [x] Exact changed-file scope verified: eleven approved paths only.
- [x] Required local tests and validators pass: 588 tests OK (skipped=3), repository/SDD/contracts/quality/workflow validators PASS, exact artifacts PASS.
- [x] Independent review has no unresolved blocking finding; runtime restart semantics remain an explicit acceptance item.
- [ ] Exact-head required CI is green and exact green head is merged.
- [ ] Exact-main Quality and protected-source policy evidence pass.
- [ ] Exact-source privilege bootstrap and VPS deployment are runtime verified.
- [ ] Public root and protected-route acceptance pass.
- [ ] Authenticated Road loads the shared module and displays detection boxes.
- [x] Deferred work recorded: process separation only if this bounded remediation is insufficient.
- [ ] Risks resolved or explicitly accepted.
- [x] Waivers resolved or current: NOT REQUIRED.

## Completion gate

- [x] Requirements are mapped to bounded tasks and evidence levels.
- [x] Implementation and tests match the fixed-address/no-widening design.
- [ ] Full source, quality, deployment and runtime evidence is durable.
- [ ] Final Issue checkpoint disposition is DONE.
