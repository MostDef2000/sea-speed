# Implementation Plan: VPS H264 cookieCheck fallback

- Specification: specs/077-vps-h264-cookiecheck-fallback/spec.md
- Issue: #335
- Status: Source implementation

## Architecture

check_h264 in deploy/vps/sea-speed-auth-cutover.sh verifies local HLS `http://127.0.0.1:18889/cam1/index.m3u8` by `curl | grep ^#EXTM3U` and `ffprobe codec == h264`. After mediamtx-compatibility remediation, bare HLS returns `302 Found Location: /cam1/index.m3u8?cookieCheck=1` (Server: mediamtx) and needs redirect following. Fix adds `-L` to curl. ffprobe already follows redirect (verified manual ffprobe PASS). No host mutation; VPS contour REQUIRED per policy because change touches deploy/vps/**.

## Decisions

- D-001: Add `-L` to curl in check_h264 to follow MediaMTX cookieCheck 302 to real playlist, matching remediation's ?cookieCheck=1 handling.

## Affected contours

- Production impact (policy-derived): VPS — change touches deploy/vps/**, so VPS deployment REQUIRED, Production safety envelope REQUIRED.
- VPS execution capability: CONNECTOR.
- Operator actions expected: 0.
- Ubuntu Worker/relay: NOT REQUIRED.

## Validation

bash -n on deploy/vps/sea-speed-auth-cutover.sh, scripts/ci/validate_repo.py, scripts/ci/validate_sdd.py, manual VPS curl -L PASS. PR Validation and Quality integration must pass on one exact head; exact-main Quality after merge.

## Risk profile

- Risk profile: NOT REQUIRED

Single curl flag, no host mutation, preserves fail-closed behavior, reuses existing verification.

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: curl -L bare HLS follows 302 and grep ^#EXTM3U PASS
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: curl ?cookieCheck=1 PASS preserved
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: bash -n deploy/vps/sea-speed-auth-cutover.sh passes
- TEST-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: scripts/ci/validate_repo.py passes
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: PR Change Contract declares VPS REQUIRED etc.

## Correct-course check

- Trigger: MATERIAL_SCOPE_CHANGE
- Issue impact: Issue #335 remains DONE; this is follow-up to make Auth v1 prepare succeed on healthy H264.
- Specification impact: check_h264 follows redirect.
- Plan impact: minimal.
- Tasks impact: fix + validation.
- Authorization impact: bounded source task under its own OUTCOME APPROVED.
- Follow-up: open PR with Change Contract VPS REQUIRED.

## Deployment transaction audit

This PR changes deploy/vps/sea-speed-auth-cutover.sh, so VPS contour REQUIRED per policy; deployment is post-merge autonomous.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: PR not merged; source unchanged | Retry: re-run PR Validation | Rollback: N/A | Evidence: Change Contract admission under OUTCOME APPROVED
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: CI blocked; no deploy | Retry: rerun workflow | Rollback: N/A | Evidence: PR Validation + Quality integration gates
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous known-good VPS state retained | Retry: rerun deploy-vps.yml | Rollback: prior release manifest | Evidence: deploy-vps.yml run with --require-allow
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: alert raised; prior state intact | Retry: re-verify health | Rollback: prior release manifest | Evidence: post-deploy health/smoke checks
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: manifest pending | Retry: re-commit manifest | Rollback: prior release manifest | Evidence: sea_speed_release_manifest_v3
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: transient artifacts retained | Retry: cleanup rerun | Rollback: N/A | Evidence: artifact store
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence incomplete | Retry: regenerate evidence | Rollback: N/A | Evidence: exact-artifacts.json, quality-evidence.json
- TX-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: prior state restored | Retry: re-rollback | Rollback: prior release manifest | Evidence: sea_speed_production_execution_audit_v1

## Runtime feedback

- Manual VPS: curl bare 302 0 bytes FAIL, curl -L PASS, curl ?cookieCheck=1 PASS, ffprobe tcp h264 PASS. Deploy failed rc=21 LOCAL_H264_FALLBACK=FAIL with healthy HLS. Single -L fixes.
