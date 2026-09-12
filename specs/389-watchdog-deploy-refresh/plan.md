# Plan: Refresh stale camera1-h264 watchdog copy during Ubuntu deploy transaction

- Specification: specs/389-watchdog-deploy-refresh/spec.md

## Architecture

The Ubuntu deploy transaction (`deploy/worker/ubuntu/update-exact.sh`) already
prepares the exact release and installs the three managed units
(`sea-speed-worker.service`, `sea-speed-road.service`,
`sea-speed-camera1-h264-freshness.{service,timer}`). This change adds a watchdog
refresh step in the activation section, immediately after the existing unit
installation, so the watchdog copy is delivered from the verified release source
on every deploy.

## Decisions

- DEC-1: Refresh the watchdog copy inside `update-exact.sh` activation rather than
  relying on a separate out-of-band step, so it cannot be skipped.
- DEC-2: Keep the watchdog logic unchanged; only its delivery is corrected.
- DEC-3: Guard every refresh step with `abort_activation` (fail-closed), matching
  the existing transaction semantics.

## Affected contours

- Ubuntu Worker (10.123.239.102) only.
- No VPS, no other camera, no web-UI/firmware, no worker reader change.

## Validation

- `bash -n deploy/worker/ubuntu/update-exact.sh` (already in suite).
- `test_ubuntu_worker_exact_updater.py::test_watchdog_copy_is_refreshed_from_release_source`
  (marker assertion on the refresh block).
- Full suite `python -m unittest discover -s tests -p test_*.py -v` stays green.
- `scripts/ci/validate_*.py` and `scripts/quality/*.py` pass.
- Post-merge autonomous deploy; post-deploy operator check of installed copy and
  service health.

## Runtime feedback

- RF-001: Operator actions expected: 0; deploy is autonomous (CONNECTOR).
- RF-002: Post-deploy evidence: installed watchdog copy matches release source;
  `sea-speed-camera1-h264-freshness.service` healthy (no 401).

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: R-1,R-3 | Level: unit | Priority: P1 | Evidence: test_watchdog_copy_is_refreshed_from_release_source marker assertion
- TEST-002 | Covers: R-2 | Level: unit | Priority: P1 | Evidence: marker assertion for timer enable in refresh block
- TEST-003 | Covers: R-1,R-2,R-3,R-4 | Level: unit | Priority: P0 | Evidence: bash -n in suite
- TEST-004 | Covers: R-1,R-2,R-5 | Level: runtime-manual | Priority: P2 | Evidence: post-deploy operator check of installed copy and service health

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: Issue #389 checkpoint + receipt
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: PR exact-head green; policy ALLOW
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: previous release restored | Retry: NO | Rollback: automatic via abort_activation | Evidence: deployment manifest
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: alarm may persist | Retry: NO | Rollback: NONE | Evidence: operator systemctl status
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: active-source-commit marker
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging may remain | Retry: NO | Rollback: NONE | Evidence: cleanup trap
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: execution-audit v1
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh | Evidence: rollback manifest
