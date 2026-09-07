# Implementation Plan: VPS HLS helper watchdog

- Specification: specs/078-vps-hls-helper-watchdog/spec.md
- Issue: #335
- Status: Source implementation

## Architecture

Helper and watchdog verify HLS via curl to 127.0.0.1:18889/cam1/index.m3u8. MediaMTX now returns 302 to ?cookieCheck=1. Fix adds -L to curl in both. No host mutation; VPS contour REQUIRED.

## Decisions

- D-001: Add -L to curl in helper _camera1_hls_sequence and watchdog _hls_sequence.

## Affected contours

- Production impact: VPS — touches deploy/vps/**, VPS REQUIRED, Production safety envelope REQUIRED.
- VPS execution capability: CONNECTOR.
- Operator actions expected: 0.
- Ubuntu Worker/relay: NOT REQUIRED.

## Validation

python -m py_compile, validate_repo, validate_sdd, manual VPS curl -L PASS. PR Validation and Quality integration must pass.

## Risk profile

- Risk profile: NOT REQUIRED

Single flag per file, no host mutation.

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: curl -L finds EXT-X-MEDIA-SEQUENCE
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: py_compile PASS
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: validate_repo PASS
- TEST-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: PR Change Contract

## Correct-course check

- Trigger: MATERIAL_SCOPE_CHANGE
- Issue impact: #335 still DONE, follow-up for helper/watchdog.
- Specification impact: curl -L.
- Plan impact: minimal.
- Tasks impact: fix + validation.
- Authorization impact: bounded source task.
- Follow-up: PR VPS REQUIRED.

## Deployment transaction audit

Change touches deploy/vps/**, VPS REQUIRED.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: PR not merged | Retry: re-run PR Validation | Rollback: N/A | Evidence: Change Contract
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: CI blocked | Retry: rerun workflow | Rollback: N/A | Evidence: PR Validation + Quality gates
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: prior VPS state retained | Retry: rerun deploy-vps.yml | Rollback: prior release manifest | Evidence: deploy-vps.yml --require-allow
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: alert | Retry: re-verify | Rollback: prior release manifest | Evidence: post-deploy health checks
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: manifest pending | Retry: re-commit | Rollback: prior release manifest | Evidence: release manifest v3
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: artifacts retained | Retry: cleanup | Rollback: N/A | Evidence: artifact store
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence incomplete | Retry: regenerate | Rollback: N/A | Evidence: exact-artifacts.json
- TX-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: prior restored | Retry: re-rollback | Rollback: prior release manifest | Evidence: execution audit v1

## Runtime feedback

- VPS HLS healthy but bare curl 302 0 bytes caused helper "has no media sequence" and deploy rollback. curl -L fixes.
