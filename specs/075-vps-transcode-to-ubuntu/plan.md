# Plan: Move Camera 1 HEVC→H264 Transcode from VPS to Ubuntu Worker

- Spec: 075-vps-transcode-to-ubuntu
- Specification: specs/075-vps-transcode-to-ubuntu/spec.md
- Canonical Issue: #335
- Deployment Transaction Audit: REQUIRED (8 stages)

## Architecture

- Ubuntu Worker runs a new repo-managed transcode service `sea-speed-camera1-h264.service` that reads
  the Ubuntu relay `cam1` (HEVC) and publishes H264 RTSP to `rtsp://127.0.0.1:8554/cam1-h264` on Ubuntu
  MediaMTX.
- VPS MediaMTX `cam1` sources `rtsp://10.123.239.102:8554/cam1-h264` (H264). VPS MediaMTX global
  `hlsAddress` is set to `:18889` so the canonical HLS is served directly by MediaMTX; the external
  `sea-speed-camera1-hls-http.service` is disabled (no reverse-proxy unit needed).
- nginx `UPSTREAM` stays `http://127.0.0.1:18889/cam1/` (unchanged).
- Ubuntu reader auth allows the VPS IP to read `cam1-h264` and the Ubuntu transcode IP to publish it.
- Ubuntu freshness watchdog queries the MediaMTX REST API for `cam1-h264` and restarts the local
  transcode on stall. VPS freshness watchdog and privileged helper re-source `cam1` via the MediaMTX
  REST API PATCH on stall (no `mediamtx.service`/`nginx.service` restart — FR-008).

## Decisions

- Option 3 (software libx264) selected over Option 2 (VAAPI) because VAAPI is unavailable on Ubuntu.
- VPS HLS served at `:18889` via MediaMTX global `hlsAddress` change (simpler than a repo-managed
  reverse-proxy); external hls-http unit disabled.
- Ubuntu transcode reads the camera relay `cam1` directly (not the VPS `cam1` relay) to avoid the
  `validate_reader_ip` loopback constraint and keep the camera pull count unchanged (AI direct + transcode
  direct = 2 conns, same as today).
- `camera-source-switch.sh` generalized with `--relay-path` (default `cam1`) and `--hls-address` /
  `--retire-external` options; `mediamtx_path_config.py` gains `vps-set-hls-address`.

## Affected contours

- VPS: `deploy/vps/camera-source-switch.sh`, `sea-speed-camera1-h264-freshness-watchdog.py`,
  `sea-speed-auth-privileged-helper.py`, `sea-speed-camera1-h264-freshness.service`, MediaMTX config.
- Ubuntu Worker/relay: `deploy/worker/ubuntu/camera1-h264-transcode.sh` (new),
  `sea-speed-camera1-h264.service` (new), `sea-speed-camera1-h264-freshness.service` + `.timer` (new),
  `mediamtx_path_config.py` reader auth for `cam1-h264`.
- MIXED: both active contours; no Windows/control-plane change.

## Validation

- Unit: `camera-source-switch.sh --relay-path cam1-h264` writes correct VPS MediaMTX `cam1` source and
  validates the private relay URL allows `/cam1-h264`; default `cam1` unchanged.
- Unit: `mediamtx_path_config.py vps-switch` accepts `--relay-path`; `ensure_internal_reader_rule`
  adds `cam1-h264` reader for VPS IP and is idempotent; `vps-set-hls-address` sets global `hlsAddress`.
- Unit: Ubuntu transcode script builds the correct ffmpeg command (HEVC input, libx264, publish to
  `cam1-h264`); systemd unit renders with `Restart=always`.
- Unit: VPS freshness watchdog + privileged helper recovery re-sources cam1 via MediaMTX API PATCH (no
  forbidden-service restart); `CAMERA1_LOCAL_HLS` stays `http://127.0.0.1:18889/cam1/index.m3u8`.
- Unit: Ubuntu freshness watchdog restarts the local transcode on stale `cam1-h264`.
- Contract: `validate_change_contract.py` — diff matches declared VPS+Ubuntu paths; no protected-boundary
  change; no secrets.
- Integration (local, best-effort): simulate topology — Ubuntu producer publishes H264 to `cam1-h264`;
  VPS MediaMTX `cam1` sources it; watchdog sees advancing playlist. Full e2e requires runtime.

## Runtime feedback

- The Ubuntu transcode publishes to `cam1-h264`; the VPS reads it as the `cam1` source. The VPS HLS is
  served at `:18889` by MediaMTX directly.
- The Ubuntu freshness watchdog queries the MediaMTX REST API for `cam1-h264` state and restarts the
  local transcode on stall.
- The VPS freshness watchdog and privileged helper re-source `cam1` via the MediaMTX REST API PATCH on
  stall, never restarting `mediamtx.service`/`nginx.service` (FR-008).
- Out-of-scope siblings: #362 (RTP loss on cam1 relay), #363 (TIME-WAIT on 18889) remain separate tasks.

## Risk profile

- Risk profile: REQUIRED
- RISK-1 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: disable with systemctl disable --now; verify 18889 free before hlsAddress change; documented rollback re-enables | Validation: port check before mutation; rollback rehearsed | Residual risk: LOW | Owner: orchestrator | Status: MITIGATED
- RISK-2 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: PRIMARY MediaMTX hlsAddress :18889; FALLBACK repo-managed hls-http reverse-proxy 8888->18889 | Validation: hlsAddress set + 18889 serves; fallback path documented | Residual risk: LOW | Owner: orchestrator | Status: MITIGATED
- RISK-3 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: add --relay-path arg default cam1; keep default behavior; unit tests both paths | Validation: T-001/T-002 unit tests | Residual risk: LOW | Owner: orchestrator | Status: MITIGATED
- RISK-4 | Category: SEC | Probability: 4 | Impact: 4 | Score: 16 | Mitigation: recovery re-sources cam1 via MediaMTX REST API PATCH, not full restart; forbidden-restart tests updated | Validation: T-004/T-005 tests assert no mediamtx/nginx restart | Residual risk: LOW | Owner: orchestrator | Status: MITIGATED
- RISK-5 | Category: PERF | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: -preset veryfast -tune zerolatency, single stream; monitor Ubuntu CPU | Validation: Ubuntu headroom; runtime observe | Residual risk: LOW | Owner: orchestrator | Status: MITIGATED
- RISK-6 | Category: SEC | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: extend ensure_internal_reader_rule for cam1-h264 (VPS IP); unit test | Validation: T-002 test | Residual risk: LOW | Owner: orchestrator | Status: MITIGATED
- RISK-7 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: AI reads camera directly via HLS_URL; no change; verified in investigation | Validation: investigation note | Residual risk: LOW | Owner: orchestrator | Status: MITIGATED
- RISK-8 | Category: OPS | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: update sea-speed-camera1-h264-freshness.service After= to mediamtx.service (remove hls-http dep) | Validation: unit render check | Residual risk: LOW | Owner: orchestrator | Status: MITIGATED

## Test design

- TEST-1 | Covers: FR-003,FR-006 | Level: unit | Priority: P0 | Evidence: camera-source-switch.sh --relay-path cam1-h264 writes correct VPS MediaMTX cam1 source; default cam1 unchanged
- TEST-2 | Covers: FR-007 | Level: unit | Priority: P0 | Evidence: ensure_internal_reader_rule adds cam1-h264 reader for VPS IP; idempotent; vps-set-hls-address sets global hlsAddress
- TEST-3 | Covers: FR-001,FR-002 | Level: unit | Priority: P0 | Evidence: Ubuntu transcode script builds correct ffmpeg command; systemd unit renders Restart=always
- TEST-4 | Covers: FR-008 | Level: unit | Priority: P0 | Evidence: VPS freshness watchdog + privileged helper recovery re-sources cam1 via MediaMTX API PATCH; no forbidden-service restart
- TEST-5 | Covers: FR-008 | Level: unit | Priority: P0 | Evidence: sea-speed-auth-privileged-helper run_camera1_h264_recovery re-sources via API; forbidden-restart list enforced
- TEST-6 | Covers: FR-009 | Level: unit | Priority: P1 | Evidence: Ubuntu freshness watchdog restarts local transcode on stale cam1-h264
- TEST-7 | Covers: change contract | Level: unit | Priority: P1 | Evidence: validate_change_contract.py diff matches declared VPS+Ubuntu paths; no protected-boundary change; no secrets

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-1 | Stage: ADMISSION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: admission unchanged | Retry: NONE | Rollback: NONE | Evidence: Issue #335 IMPLEMENTING; OUTCOME APPROVED six-field Scope; Checkpoint v2 gen 1
- TX-2 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: pre-mutation snapshot retained | Retry: NONE | Rollback: NONE | Evidence: snapshot external VPS unit state; record relay path cam1; record MediaMTX cam1 source; freeze rollback plan
- TX-3 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: partial mutation; external units may be disabled | Retry: re-run camera-source-switch with corrected args | Rollback: re-enable external VPS units + revert relay path to cam1 + stop Ubuntu transcode | Evidence: install Ubuntu transcode + reader auth + freshness watchdog; set hlsAddress :18889; disable external VPS units; run camera-source-switch --relay-path cam1-h264 --hls-address :18889 --retire-external
- TX-4 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verification evidence incomplete | Retry: re-run acceptance probes | Rollback: if AC-001..AC-006 not met, execute TX-8 | Evidence: AC-001..AC-006 (18889 advances, browser path works, units active/disabled as expected)
- TX-5 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: merge not completed | Retry: re-merge exact-green-head | Rollback: revert merge via main protection | Evidence: exact-green-head merge; protected VPS + Ubuntu deploy; runtime acceptance
- TX-6 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: docs stale | Retry: update docs | Rollback: NONE | Evidence: update docs CAMERA1_DIRECT_H264_CUTOVER.md, SEA_SPEED_AUTH_V1.md to reflect new topology
- TX-7 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence incomplete | Retry: regenerate artifacts | Rollback: NONE | Evidence: exact-artifacts.json, quality-evidence.json, release-manifest v3, deployment-manifest, execution-audit v1; Checkpoint v2 DONE with cursors
- TX-8 | Stage: ROLLBACK | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: rollback incomplete | Retry: re-run rollback steps | Rollback: NONE | Evidence: re-enable external VPS units + revert relay path to cam1 + stop Ubuntu transcode; verified reversible

## Implementation file map

Ubuntu (new / changed):
- `deploy/worker/ubuntu/camera1-h264-transcode.sh` (new): ffmpeg HEVC->H264 publish to `cam1-h264`.
- `deploy/worker/ubuntu/sea-speed-camera1-h264.service` (new): systemd unit, `Restart=always`.
- `deploy/worker/ubuntu/sea-speed-camera1-h264-freshness.service` + `.timer` (new): Ubuntu freshness watchdog.
- `scripts/operations/mediamtx_path_config.py` (changed): `ensure_internal_reader_rule` for `cam1-h264`;
  `vps-switch --relay-path`; `vps-set-hls-address`.

VPS (changed):
- `deploy/vps/camera-source-switch.sh` (changed): `--relay-path`; `--hls-address`; `--retire-external`.
- `deploy/vps/sea-speed-camera1-h264-freshness-watchdog.py` (changed): recovery = API PATCH re-source.
- `deploy/vps/sea-speed-auth-privileged-helper.py` (changed): `run_camera1_h264_recovery` re-sources cam1.
- `deploy/vps/sea-speed-camera1-h264-freshness.service` (changed): `After=` remove hls-http dep.

Tests (changed):
- `tests/test_camera1_h264_freshness_watchdog.py`: recovery action + service constant.
- `tests/test_vps_auth_privilege_boundary.py`: forbidden-restart list + recovery semantics.
- `tests/test_vps_transcode_to_ubuntu.py` (new): generalization + reader auth + topology.

Docs (changed):
- `docs/operations/CAMERA1_DIRECT_H264_CUTOVER.md`, `docs/operations/SEA_SPEED_AUTH_V1.md`: topology note.
