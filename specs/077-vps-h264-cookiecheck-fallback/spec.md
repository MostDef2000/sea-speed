# Feature Specification: VPS H264 cookieCheck fallback

- Feature: 077-vps-h264-cookiecheck-fallback
- Issue: #335
- Status: Source implementation
- Owner outcome: VPS Auth v1 deployment correctly verifies local H264 HLS even when MediaMTX HLS returns 302 ?cookieCheck=1 redirect, so check_h264 does not fail on healthy H264 stream and Road private M2M Auth v1 prepare succeeds.

## Product outcome

`deploy/vps/sea-speed-auth-cutover.sh` check_h264 used `curl` without `-L` on `http://127.0.0.1:18889/cam1/index.m3u8`. After mediamtx-compatibility remediation, MediaMTX HLS returns `302 Found Location: /cam1/index.m3u8?cookieCheck=1` with `Server: mediamtx` and `Set-Cookie: cookieCheck=1` for the bare index, requiring `?cookieCheck=1` or redirect following. The bare curl therefore got `0` bytes and `grep ^#EXTM3U` failed with `LOCAL_H264_FALLBACK=FAIL` (rc=21) even though `ffprobe -rtsp_transport tcp rtsp://10.123.239.102:8554/cam1-h264` and `curl ?cookieCheck=1` correctly returned `h264` / `#EXTM3U`. The live hosts already have healthy H264 (ffprobe tcp PASS, curl ?cookieCheck=1 PASS).

Fix adds `-L` to curl in check_h264 so the 302 is followed to the real playlist. No host mutation, no API/frontend change. Change touches `deploy/vps/**`, so VPS contour is REQUIRED per policy; this PR performs no deployment itself.

## User scenarios

### Scenario 1 - Local H264 check follows redirect

Given MediaMTX HLS returns 302 to `?cookieCheck=1` for bare `/cam1/index.m3u8`, when check_h264 runs `curl -L http://127.0.0.1:18889/cam1/index.m3u8`, then it follows redirect to `?cookieCheck=1` and grep finds `^#EXTM3U`.

### Scenario 2 - Road private M2M prepare succeeds

Given HLS is healthy H264, when deploy reconciles Road private M2M Auth v1 boundary, then prepare does not exit 21 and deployment proceeds without rollback.

## Requirements

- FR-001: check_h264 MUST follow HTTP redirects when fetching `$local_h264` so `302 ?cookieCheck=1` does not cause false FAIL.
- FR-002: ffprobe codec check MUST remain `h264` (no change; ffprobe already follows redirect).
- FR-003: Change touches `deploy/vps/**`, so PR MUST declare VPS deployment REQUIRED and Production safety envelope REQUIRED; Ubuntu Worker/relay update NOT REQUIRED.

## Acceptance criteria

- AC-001: `curl -L http://127.0.0.1:18889/cam1/index.m3u8` on VPS with healthy H264 returns `#EXTM3U` and grep PASS.
- AC-002: `curl "http://127.0.0.1:18889/cam1/index.m3u8?cookieCheck=1" | grep ^#EXTM3U` PASS (existing behavior preserved).
- AC-003: `bash -n deploy/vps/sea-speed-auth-cutover.sh` passes.
- AC-004: `scripts/ci/validate_repo.py` passes.
- AC-005: PR Change Contract declares VPS REQUIRED, Ubuntu NOT REQUIRED, production safety envelope REQUIRED, VPS execution capability CONNECTOR, Ubuntu NOT APPLICABLE, operator actions 0.

## NFR assessment

- NFR-001 | Area: Reliability | Target: Auth v1 prepare does not false-fail on MediaMTX cookieCheck redirect | Validation: check_h264 uses curl -L to follow 302 to ?cookieCheck=1 playlist and grep #EXTM3U | Evidence: manual VPS curl -L PASS; ffprobe tcp h264 PASS | Status: PASS

## Runtime feedback

- VPS HLS is healthy H264 (ffprobe tcp PASS, curl ?cookieCheck=1 PASS) but bare curl without -L got 302 0 bytes and check_h264 returned LOCAL_H264_FALLBACK=FAIL, causing deploy rollback to 3866220. Fix is single -L flag on curl.
