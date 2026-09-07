# Feature Specification: VPS HLS helper watchdog cookieCheck

- Feature: 078-vps-hls-helper-watchdog
- Issue: #335
- Status: Source implementation
- Owner outcome: VPS HLS health checks in privileged helper and watchdog follow MediaMTX 302 ?cookieCheck=1, so helper's _camera1_hls_sequence does not raise "has no media sequence" on healthy H264 and watchdog does not false-fail.

## Product outcome

deploy/vps/sea-speed-auth-privileged-helper.py _camera1_hls_sequence and deploy/vps/camera1-h264-freshness-watchdog.py _hls_sequence both curled http://127.0.0.1:18889/cam1/index.m3u8 without -L. After mediamtx compatibility remediation, bare HLS returns 302 to ?cookieCheck=1. The helper's curl got 0-byte redirect body, HLS_MEDIA_SEQUENCE_RE missed, and helper raised "has no media sequence", causing Road private M2M prepare to fail even though curl ?cookieCheck=1 and ffprobe tcp h264 were PASS. Fix adds -L to both curls. Change touches deploy/vps/**, so VPS contour REQUIRED.

## User scenarios

### Scenario 1 - Helper follows redirect

Given bare HLS returns 302 to ?cookieCheck=1, when helper runs _camera1_hls_sequence with curl -L, then it follows redirect to real playlist and finds EXT-X-MEDIA-SEQUENCE.

### Scenario 2 - Watchdog follows redirect

Given same 302, when watchdog runs _hls_sequence with curl -L, then it finds media sequence and freshness sampling succeeds.

## Requirements

- FR-001: helper _camera1_hls_sequence MUST use curl -L to follow 302.
- FR-002: watchdog _hls_sequence MUST use curl -L to follow 302.
- FR-003: Change touches deploy/vps/**, so PR MUST declare VPS deployment REQUIRED and Production safety envelope REQUIRED.

## Acceptance criteria

- AC-001: curl -L http://127.0.0.1:18889/cam1/index.m3u8 finds #EXT-X-MEDIA-SEQUENCE
- AC-002: helper py_compile PASS, watchdog py_compile PASS
- AC-003: bash -n and validate_repo PASS
- AC-004: PR Change Contract declares VPS REQUIRED etc.

## NFR assessment

- NFR-001 | Area: Reliability | Target: HLS health check does not false-fail on cookieCheck redirect | Validation: curl -L follows 302 to playlist | Evidence: manual VPS curl -L PASS | Status: PASS

## Runtime feedback

- VPS HLS healthy h264 but bare curl 302 caused helper "has no media sequence" and deploy rollback; curl -L to ?cookieCheck=1 fixes.
- Cutover check_h264 already fixed in 077 with same -L; this extends to helper and watchdog.
