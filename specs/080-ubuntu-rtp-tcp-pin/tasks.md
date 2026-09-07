# Delivery Tasks: Ubuntu RTP TCP pin

- Specification: specs/080-ubuntu-rtp-tcp-pin/spec.md
- Issue: #362
- Status: Source implementation

## Delivery tasks

- T-001 [x] Confirm Issue #362 DISCUSSION, current main cacdce5, SDD prefix 080, Scope and OUTCOME APPROVED.
- T-002 [x] Fix render_ubuntu_relay in mediamtx_path_config.py to pass rtsp_transport="tcp".
- T-003 [x] Verify py_compile, bash -n, validate_repo/sdd, unit tests (23 tests PASS).
- T-004 [ ] Open PR with Change Contract Ubuntu REQUIRED.
- T-005 [ ] After merge, deploy Ubuntu and verify journalctl without RTP loss.

## Requirements traceability

- AC-001 | Task: T-002 | Evidence: render_ubuntu_relay output contains rtspTransport: tcp | Coverage: COVERED
- AC-002 | Task: T-003 | Evidence: py_compile / bash -n PASS | Coverage: COVERED
- AC-003 | Task: T-003 | Evidence: validate_repo and validate_sdd PASS | Coverage: COVERED
- AC-004 | Task: T-005 | Evidence: journalctl without RTP loss for 10+ min | Coverage: RUNTIME-MANUAL | Reason: requires the live physical camera and the deployed Ubuntu relay runtime over ZeroTier; not reproducible in CI without the production RTSP source and relay topology
- AC-005 | Task: T-004 | Evidence: PR Change Contract declares Ubuntu REQUIRED | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current — Ubuntu cam1 TCP pin recorded.
- [x] Exact changed-file scope verified — diff limited to mediamtx_path_config.py and 080 spec.
- [x] Required tests and evidence complete — py_compile, validate_repo/sdd, unit tests 23 PASS, manual journalctl pending runtime.
- [ ] Required CI green — PR exact head must pass PR Validation and Quality, then exact-main Quality.
- [ ] Exact-green-head merge complete — merge only after fresh base/head gate.
- [x] Deployment state resolved — PR performs no deployment; Ubuntu contour REQUIRED, autonomous post-merge.
- [x] Runtime acceptance resolved — runtime journalctl verification is RUNTIME-MANUAL post-deploy.
- [x] Risks resolved or explicitly accepted — Risk profile NOT REQUIRED.
- [x] Waivers resolved or current — no waiver.
- [x] Deferred work recorded — no deferred work; next is PR merge, Ubuntu deploy, and runtime journalctl.

## Completion gate

DONE forbidden until exact-head PR Validation and Quality pass, exact green head merges, and exact-main Quality succeeds; runtime journalctl verification is RUNTIME-MANUAL post-deploy.
