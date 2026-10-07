# Tasks: Ubuntu Camera 1 H264 freshness watchdog for MediaMTX v1.19.1 REST API

- Specification: specs/410-worker-watchdog-mediamtx-v1191/spec.md

## Delivery tasks

- T-410-001: Rework `_path_ready` to the v1.19.1 contract: GET
  /v3/paths/get/{name}, two samples with injectable sleeper, ready/available
  gates and inboundBytes-growth freshness; update both `run_once` call sites;
  drop the dead `STALE_SECONDS` consumer; update the module docstring
- T-410-002: Add the MediaMTX v1.19.1 test fixture and pins (route PASS/NOOP,
  fail-closed cooldown, recovery growth verification, no-growth, direct
  fail-closed variants, source pins) to
  `tests/test_camera1_h264_freshness_watchdog.py` without touching VPS-module
  tests
- T-410-003: Document the Ubuntu Worker relay API profile (loopback-only `api`
  enablement as a deliberate exception) in
  `docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md`
- T-410-004: Confirm exact changed-file scope and scope isolation (no VPS,
  transcode/relay, installer, workflow or credential changes)
- T-410-005: Open PR with SDD linkage, reach exact-green-head and merge
- T-410-006: Autonomous deploy to the Ubuntu Worker and runtime acceptance of
  the installed watchdog
- T-410-007: Add the fail-closed top-level-object guard in `_path_ready`
  (non-object JSON bodies fail closed to not-ready in both sample positions)
  with RED-anchored regression tests, including an end-to-end recovery run

## Completion gate

- [ ] T-410-001
- [ ] T-410-002
- [ ] T-410-003
- [ ] T-410-004
- [ ] T-410-005
- [ ] T-410-006
- [x] T-410-007

## Requirements traceability

- AC-001 | Task: T-410-001,T-410-002 | Evidence: curl argv route pins in UbuntuWatchdogMediaMTXV1191Tests plus RED-anchor replay against the base script | Coverage: COVERED
- AC-002 | Task: T-410-001,T-410-002 | Evidence: test_growing_inbound_bytes_is_pass_noop returns PASS/NOOP | Coverage: COVERED
- AC-003 | Task: T-410-002,T-410-007 | Evidence: fail-closed tests: curl 404 within cooldown, no-growth recovery, direct _path_ready variants incl. non-object bodies in both sample positions, end-to-end recovery run | Coverage: COVERED
- AC-004 | Task: T-410-004 | Evidence: git diff scope review against the admitted scope per the issue #410 receipt (watchdog script, the two test files, docs file, this SDD trio) | Coverage: COVERED
- AC-005 | Task: T-410-003 | Evidence: remediation doc section Ubuntu Worker relay API profile | Coverage: COVERED
- AC-006 | Task: T-410-006 | Evidence: post-deploy watchdog run on the worker | Coverage: RUNTIME-MANUAL | Reason: live v1.19.1 acceptance requires the deployed worker host after merge

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [x] Required CI green — auto-synced on merge to main (fe758a3b)
- [x] Exact-green-head merge complete — auto-synced on merge to main (fe758a3b)
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [ ] Deferred work recorded
- [ ] Risks resolved or explicitly accepted
- [ ] Waivers resolved or current
