# Tasks: Camera 1 Runtime Freshness Supervision

- Feature: 035-camera1-runtime-freshness-supervision
- Specification: specs/035-camera1-runtime-freshness-supervision/spec.md
- Plan: specs/035-camera1-runtime-freshness-supervision/plan.md
- Issue: #255
- Status: Source implementation / PR admission

## Delivery tasks

### Source implementation

- [x] T001 Add no-argument fixed-topology Camera 1 H264 freshness watchdog.
- [x] T002 Add root oneshot systemd service for the fixed watchdog.
- [x] T003 Add bounded recurring systemd timer.
- [x] T004 Extend exact-source privilege-boundary installer to install/activate/rollback watchdog assets and timer state.
- [x] T005 Preserve Issue #226 privileged reconcile path without widening helper request/action surface.
- [x] T006 Add focused tests for no-op, stale recovery, relay failure, cooldown, failed post-restart recovery and fixed command topology.
- [x] T007 Add unit/timer/installer contract assertions.
- [x] T008 Document lifetime supervision and its distinction from deploy-time recovery.
- [x] T009 Complete Deployment Transaction Audit.

### Quality / integration

- [ ] T010 Run repository validation and focused local tests against final proposed bytes.
- [ ] T011 Open one bounded PR whose actual diff is a subset of Issue #255 authorization.
- [ ] T012 Require Repository validation + quality-integration on exact final head.
- [ ] T013 Fresh pre-merge base/head/scope verification and expected-head merge.
- [ ] T014 Require exact-main push Quality before runtime policy evaluation.

### Runtime / acceptance

- [ ] T015 Evaluate standing production delegation and exact merged Change Contract for VPS REQUIRED.
- [ ] T016 Execute exactly one repository-owned exact-source root bootstrap when canonical transport requires it; verify watchdog timer active.
- [ ] T017 Run canonical VPS deployment for exact current-main release.
- [ ] T018 Prove healthy watchdog execution is no-op.
- [ ] T019 Prove autonomous stale-HLS recovery with healthy relay: exactly one H264 restart and advancing HLS/authenticated video within <=90 seconds.
- [ ] T020 Verify no nginx/HLS-HTTP/MediaMTX/Water/Road restart attributable to watchdog.
- [ ] T021 Persist terminal evidence in Issue #255 and close only after runtime acceptance.

## Requirements traceability

- AC-001 | Task: T001, T006 | Evidence: advancing-HLS no-op unit test asserts zero relay probes and zero restarts | Coverage: COVERED
- AC-002 | Task: T001, T006 | Evidence: static-HLS + healthy-relay test asserts exact FFmpeg argv, exactly one fixed-service restart, post-restart progression | Coverage: COVERED
- AC-003 | Task: T001, T006 | Evidence: relay-failure no-restart unit test | Coverage: COVERED
- AC-004 | Task: T001, T006 | Evidence: cooldown suppression unit test | Coverage: COVERED
- AC-005 | Task: T001, T006 | Evidence: post-restart static-HLS failure test retaining cooldown evidence | Coverage: COVERED
- AC-006 | Task: T001, T007 | Evidence: static analysis/no-selectable-topology assertions over the runtime entry point | Coverage: COVERED
- AC-007 | Task: T002, T003, T007 | Evidence: unit-file tests prove root oneshot fixed ExecStart and automatic bounded-cadence timer | Coverage: COVERED
- AC-008 | Task: T004, T007 | Evidence: installer contract tests prove exact-source ownership of only watchdog assets plus prior-state rollback | Coverage: COVERED
- AC-009 | Task: T010, T011 | Evidence: final PR diff asserted subset of Issue #255 authorized paths; secret/media absence check | Coverage: COVERED
- AC-010 | Task: T012 | Evidence: required Repository validation + quality-integration success on exact final PR head | Coverage: COVERED
- AC-011 | Task: T013, T014 | Evidence: expected-head merge plus exact-main push Quality status success | Coverage: COVERED
- AC-012 | Task: T015, T016 | Evidence: production bootstrap markers CAMERA1_FRESHNESS_WATCHDOG=INSTALLED, CAMERA1_FRESHNESS_TIMER=ACTIVE | Coverage: RUNTIME-MANUAL | Reason: requires protected VPS bootstrap observation under standing delegation after merge
- AC-013 | Task: T017, T018, T019, T020, T021 | Evidence: autonomous <=90s recovery demonstration with sanitized media-sequence evidence in Issue #255 | Coverage: RUNTIME-MANUAL | Reason: requires live production stale-output condition and authenticated Camera 1 observation

## Completion gate

- [x] Exact scope verified against Issue #255 authorization
- [x] SDD artifacts current (spec/plan/tasks)
- [x] Focused local tests PASS
- [ ] Required CI green on exact head
- [ ] Runtime acceptance complete before Issue closure

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [x] Deferred work recorded (relay-side HEVC decoder robustness out of scope)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (none required)

Done requires all source tests and required CI green on one exact head, expected-head merge, exact-main Quality, production policy allow, exact-source watchdog bootstrap, canonical VPS runtime evidence, and demonstrated autonomous freshness recovery. A merged PR alone is not Done.
