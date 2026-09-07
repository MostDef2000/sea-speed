# Implementation Plan: VPS HLS master fallback

- Specification: specs/079-vps-hls-master-fallback/spec.md
- Issue: #335
- Status: Source implementation

## Architecture

Helper/watchdog fetch HLS via curl -L. fmp4 master has #EXTM3U and STREAM-INF but no MEDIA-SEQUENCE. Fix returns 0 for #EXTM3U present, and advancing returns True for 0,0.

## Decisions

- D-001: Return 0 for #EXTM3U without MEDIA-SEQUENCE; advancing 0,0 => True.

## Affected contours

- Production impact: VPS — touches deploy/vps/**, VPS REQUIRED, Production safety envelope REQUIRED.
- VPS execution capability: CONNECTOR.
- Operator actions expected: 0.
- Ubuntu Worker/relay: NOT REQUIRED.

## Validation

py_compile, validate_repo, validate_sdd, manual curl master PASS.

## Risk profile

- Risk profile: NOT REQUIRED

Single fallback, no host mutation.

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: master returns 0
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: media returns sequence
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: py_compile PASS
- TEST-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: PR Change Contract

## Correct-course check

- Trigger: MATERIAL_SCOPE_CHANGE
- Issue impact: #335 follow-up.
- Specification impact: master handling.
- Plan impact: minimal.
- Tasks impact: fix.
- Authorization impact: bounded.
- Follow-up: PR VPS REQUIRED.

## Deployment transaction audit

Touches deploy/vps/**, VPS REQUIRED.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: PR not merged | Retry: re-run PR Validation | Rollback: N/A | Evidence: Change Contract
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: CI blocked | Retry: rerun | Rollback: N/A | Evidence: PR Validation + Quality gates
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: prior VPS retained | Retry: rerun deploy-vps.yml | Rollback: prior manifest | Evidence: deploy-vps.yml --require-allow
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: alert | Retry: re-verify | Rollback: prior manifest | Evidence: post-deploy health checks
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: manifest pending | Retry: re-commit | Rollback: prior manifest | Evidence: release manifest v3
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: artifacts retained | Retry: cleanup | Rollback: N/A | Evidence: artifact store
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence incomplete | Retry: regenerate | Rollback: N/A | Evidence: exact-artifacts.json
- TX-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: prior restored | Retry: re-rollback | Rollback: prior manifest | Evidence: execution audit v1

## Runtime feedback

- Master without MEDIA-SEQUENCE caused helper to fail; 0 fallback and 0,0 advancing => True fixes.
