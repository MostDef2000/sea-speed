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

- [x] Issue/spec/plan/tasks current — Issue #327 and SDD 068 define the approved VPS startup-resilience Outcome.
- [x] Exact changed-file scope verified — eleven approved VPS paths only; no API/frontend/worker/Authentik/route changes.
- [ ] Required tests and evidence complete — 588 local tests pass; exact-head CI and merged-main evidence remain pending.
- [ ] Required CI green — exact-head PR Validation and aggregate Quality remain pending.
- [ ] Exact-green-head merge complete — task branch is not yet merged.
- [ ] Deployment state resolved — exact-source privilege bootstrap and protected VPS deployment remain pending.
- [ ] Runtime acceptance resolved — public root, protected Auth flow and authenticated Road acceptance remain pending.
- [x] Deferred work recorded — private-listener process separation only if this bounded remediation is insufficient.
- [x] Risks resolved or explicitly accepted — full risk profile in plan.md; RISK-068-002 remains OPEN with bounded-retry mitigation.
- [x] Waivers resolved or current — no waiver is active (Quality verdict CONCERNS, not WAIVED).

## Completion gate

- [x] Requirements are mapped to bounded tasks and evidence levels.
- [x] Implementation and tests match the fixed-address/no-widening design.
- [ ] Full source, quality, deployment and runtime evidence is durable.
- [ ] Final Issue checkpoint disposition is DONE.
