# Implementation Plan: Ubuntu RTP TCP pin

- Specification: specs/080-ubuntu-rtp-tcp-pin/spec.md
- Issue: #362
- Status: Source implementation

## Architecture

Ubuntu mediamtx path cam1 pulls physical camera RTSP. It used rtspTransport automatic (UDP) and emitted RTP loss / invalid fragmentation. VPS cam1 already pins to tcp. Fix makes scripts/operations/mediamtx_path_config.py render_ubuntu_relay pass rtsp_transport="tcp" to set_path_source, aligning Ubuntu relay with VPS contract. No host mutation in PR; runtime verification via journalctl on Ubuntu.

## Decisions

- D-001: In render_ubuntu_relay, call set_path_source with rtsp_transport="tcp" for cam1, matching VPS.

## Affected contours

- Production impact: UBUNTU_WORKER — change touches deploy/worker/ubuntu via mediamtx_path_config.py; Ubuntu Worker/relay update REQUIRED, VPS NOT REQUIRED (HLS consumer only).
- VPS execution capability: NOT APPLICABLE.
- Ubuntu execution capability: CONNECTOR.
- Operator actions expected: 0.

## Validation

py_compile / bash -n on changed files, validate_repo, validate_sdd, unit tests test_camera1_live_replacement.py and test_mediamtx_compatibility_remediation.py (23 tests PASS), runtime journalctl on Ubuntu without RTP loss.

## Risk profile

- Risk profile: NOT REQUIRED

Single transport flag, no host mutation, preserves fail-closed, reuses existing helper.

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: render_ubuntu_relay output contains rtspTransport: tcp
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: bash -n / py_compile PASS
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: validate_repo and validate_sdd PASS
- TEST-004 | Covers: AC-004 | Level: runtime-manual | Priority: P0 | Evidence: journalctl without RTP loss for 10+ min
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: PR Change Contract declares Ubuntu REQUIRED

## Correct-course check

- Trigger: MATERIAL_SCOPE_CHANGE
- Issue impact: #362 remains DISCUSSION until this fix proves sustained relay without loss.
- Specification impact: Ubuntu cam1 pinned to tcp.
- Plan impact: minimal, aligns Ubuntu with VPS.
- Tasks impact: fix + tests + runtime verification.
- Authorization impact: bounded source task under OUTCOME APPROVED for #362.
- Follow-up: PR Ubuntu REQUIRED, then Ubuntu deploy and runtime journalctl verification.

## Deployment transaction audit

Change touches deploy/worker/ubuntu via mediamtx_path_config.py, Ubuntu REQUIRED.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: PR not merged | Retry: re-run PR Validation | Rollback: N/A | Evidence: Change Contract
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: CI blocked | Retry: rerun workflow | Rollback: N/A | Evidence: PR Validation + Quality gates
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: prior Ubuntu state retained | Retry: rerun deploy-ubuntu-worker | Rollback: prior release manifest | Evidence: deploy-ubuntu-worker.yml --require-allow
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: alert | Retry: re-verify | Rollback: prior manifest | Evidence: journalctl without RTP loss, HLS freshness
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: manifest pending | Retry: re-commit | Rollback: prior manifest | Evidence: release manifest v3
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: artifacts retained | Retry: cleanup | Rollback: N/A | Evidence: artifact store
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence incomplete | Retry: regenerate | Rollback: N/A | Evidence: exact-artifacts.json
- TX-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: prior restored | Retry: re-rollback | Rollback: prior manifest | Evidence: execution audit v1

## Runtime feedback

- RTP loss and invalid fragmentation are on ingress from camera to Ubuntu, upstream of transcode; pinning to tcp is the direct fix, as VPS already does.
