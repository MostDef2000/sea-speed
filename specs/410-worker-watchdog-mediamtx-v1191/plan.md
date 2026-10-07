# Plan: Ubuntu Camera 1 H264 freshness watchdog for MediaMTX v1.19.1 REST API

- Specification: specs/410-worker-watchdog-mediamtx-v1191/spec.md

## Architecture

The ubuntu watchdog keeps its single-process, fixed-topology shape: `run_once`
takes the exclusive lock, observes the local MediaMTX path, and only on a
not-ready verdict falls through to the unchanged cooldown/source-probe/restart
flow. `_path_ready` becomes a two-sample observer: it issues
`GET {MEDIAMTX_API}/v3/paths/get/{CAMERA1_H264_PATH}` twice with
`sleeper(SAMPLE_SECONDS)` between samples and gates readiness on
`ready`/`available` plus a strictly increasing `inboundBytes` counter, replacing
the pre-v1.19.1 `state`/`lastFrameTime` age check. `run_once` passes its
injectable sleeper into both `_path_ready` call sites (initial check and
post-restart verification).

## Decisions

- DEC-1: Prove freshness by `inboundBytes` growth between two samples rather
  than any timestamp field: the operator-verified oracle shows `inboundBytes`
  strictly grows while the producer publishes, `readyTime` is the path start
  time (not frame age), and v1.19.1 exposes no `lastFrameTime`.
- DEC-2: Keep the route/format gate fail-closed: non-zero curl, unparseable
  JSON, missing `ready`/`available` and missing/invalid `inboundBytes` are all
  not-ready; a boolean `inboundBytes` is rejected even though it is an `int`
  subclass in Python.
- DEC-3: Keep `SAMPLE_SECONDS` and `COOLDOWN_SECONDS` semantics and the injected
  `sleeper`/`clock` seams unchanged so the cooldown discipline and test seams
  stay identical; only the dead `STALE_SECONDS` path is removed.
- DEC-4: Pin the route in tests at the argv level (every curl argv contains
  `/v3/paths/get/cam1-h264`, none contains `/v3/paths/cam1-h264`), which is
  demonstrated RED against the base script and GREEN after the change.

## Affected contours

- Ubuntu Worker/relay only (`deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py`
  plus its test and the remediation document).
- No VPS change, no transcode/relay script change, no installer, no workflow, no
  other camera, no credential material.

## Validation

- `python3 -m py_compile deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py`.
- `python3 -m pytest tests/test_camera1_h264_freshness_watchdog.py -q` — all
  green including the pre-existing VPS-module tests in the same file.
- Full suite `python -W error::ResourceWarning -m unittest discover -s tests
  -p 'test_*.py'` green (see checkpoint for the known out-of-scope pin noted to
  the orchestrator).
- `ruff check .` (0.16.10) clean, including with `--config scripts/quality/ruff.toml`.
- `scripts/ci/validate_sdd.py`, `validate_repo.py`, `validate_contracts.py`,
  `validate_quality_contracts.py`, `validate_workflow_policy.py` green.
- Post-merge autonomous deploy; worker service journal shows
  `CAMERA1_H264_FRESHNESS=PASS`.

## Runtime feedback

- RF-001: Operator actions expected: 0; deploy and timer re-enable are handled by
  the autonomous transaction after merge.
- RF-002: Post-deploy evidence: watchdog run reports
  `CAMERA1_H264_FRESHNESS=PASS` with the v1.19.1 route.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: fail-closed sample gates, unchanged cooldown/restart boundary, verbatim v1.19.1 fixture tests, RED-anchor route pins, single-file scope | Validation: full unittest suite, ruff, SDD validators green locally | Residual risk: live API behaviour re-verified only after production deploy | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: R-1,R-2 | Level: unit | Priority: P0 | Evidence: test_growing_inbound_bytes_is_pass_noop with argv route pins (RED vs base, GREEN after change)
- TEST-002 | Covers: R-3 | Level: unit | Priority: P0 | Evidence: test_curl_failure_within_cooldown_is_stale_without_restart plus direct _path_ready fail-closed variants (curl rc, invalid JSON, ready false, missing available, non-int/negative/bool bytes, no growth)
- TEST-003 | Covers: R-2,R-3 | Level: unit | Priority: P1 | Evidence: no-growth identical bytes recovers via restart; 404 without state restarts and verifies post-restart growth
- TEST-004 | Covers: R-4 | Level: unit | Priority: P1 | Evidence: test_v1191_source_pins (route literal present, legacy route, lastFrameTime and STALE_SECONDS absent)
- TEST-005 | Covers: R-1,R-2,R-3,R-4,R-5 | Level: integration | Priority: P1 | Evidence: full unittest discover suite, ruff, py_compile and SDD validators green
- TEST-006 | Covers: R-6 | Level: runtime-manual | Priority: P2 | Evidence: post-deploy watchdog run on the worker shows CAMERA1_H264_FRESHNESS=PASS

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: Issue #410 checkpoint + authorization receipt
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: PR exact-head green; standing policy ALLOW
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: previous release restored for the deploy-managed units, but the watchdog refresh step (installed copy, unit and timer install, daemon-reload, unconditional systemctl enable --now sea-speed-camera1-h264-freshness.timer) is not covered by restore_previous()/abort_activation(), so an activation failure after that step retains the new watchdog artifacts and may leave the timer enabled (pre-existing delivery gap tracked in issue #412; compensating controls: the fail-closed guard with the 300s cooldown bounds restart behavior and the fixed watchdog on the live healthy stream produces PASS no-op ticks) | Retry: NO | Rollback: rollback-exact.sh covers the managed units only; watchdog artifacts roll back manually via systemctl disable --now sea-speed-camera1-h264-freshness.timer and reinstalling the previous installed watchdog copy from release history | Evidence: deployment manifest
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: stale verdict may persist | Retry: NO | Rollback: NONE | Evidence: worker journal CAMERA1_H264_FRESHNESS=PASS
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: active-source-commit marker
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging may remain | Retry: NO | Rollback: NONE | Evidence: cleanup trap
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: execution-audit v1
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh | Evidence: rollback manifest
