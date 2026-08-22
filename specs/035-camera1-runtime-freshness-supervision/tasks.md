# Tasks: Camera 1 Runtime Freshness Supervision

- Feature: 035-camera1-runtime-freshness-supervision
- Issue: #255

## Source implementation

- [x] T001 Add no-argument fixed-topology Camera 1 H264 freshness watchdog.
- [x] T002 Add root oneshot systemd service for the fixed watchdog.
- [x] T003 Add bounded recurring systemd timer.
- [x] T004 Extend exact-source privilege-boundary installer to install/activate/rollback watchdog assets and timer state.
- [x] T005 Preserve Issue #226 privileged reconcile path without widening helper request/action surface.
- [x] T006 Add focused tests for no-op, stale recovery, relay failure, cooldown, failed post-restart recovery and fixed command topology.
- [x] T007 Add unit/timer/installer contract assertions.
- [x] T008 Document lifetime supervision and its distinction from deploy-time recovery.
- [x] T009 Complete Deployment Transaction Audit.

## Quality / integration

- [ ] T010 Run repository validation and focused local tests against final proposed bytes.
- [ ] T011 Open one bounded PR whose actual diff is a subset of Issue #255 authorization.
- [ ] T012 Require Repository validation + quality-integration on exact final head.
- [ ] T013 Fresh pre-merge base/head/scope verification and expected-head merge.
- [ ] T014 Require exact-main push Quality before runtime policy evaluation.

## Runtime / acceptance

- [ ] T015 Evaluate standing production delegation and exact merged Change Contract for VPS REQUIRED.
- [ ] T016 Execute exactly one repository-owned exact-source root bootstrap when canonical transport requires it; verify watchdog timer active.
- [ ] T017 Run canonical VPS deployment for exact current-main release.
- [ ] T018 Prove healthy watchdog execution is no-op.
- [ ] T019 Prove autonomous stale-HLS recovery with healthy relay: exactly one H264 restart and advancing HLS/authenticated video within <=90 seconds.
- [ ] T020 Verify no nginx/HLS-HTTP/MediaMTX/Water/Road restart attributable to watchdog.
- [ ] T021 Persist terminal evidence in Issue #255 and close only after runtime acceptance.

## Definition of Done

Done requires all source tests and required CI green on one exact head, expected-head merge, exact-main Quality, production policy allow, exact-source watchdog bootstrap, canonical VPS runtime evidence, and demonstrated autonomous freshness recovery. A merged PR alone is not Done.
