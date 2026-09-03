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

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| R-1 | External VPS units `sea-speed-camera1-h264.service` / `sea-speed-camera1-hls-http.service` are not repo-managed; disabling them may leave orphaned state or port conflict on 18889 | Med | High | Disable with `systemctl disable --now`; verify 18889 free before MediaMTX hlsAddress change; documented rollback re-enables them |
| R-2 | 18889 serving mechanism: chosen MediaMTX global `hlsAddress` :18889; verify no other VPS path needs 8888 | Med | High | PRIMARY: MediaMTX hlsAddress :18889. FALLBACK: repo-managed hls-http reverse-proxy 8888->18889 |
| R-3 | `camera-source-switch.sh` / `mediamtx_path_config.py vps-switch` hardcode `/cam1`; generalization may break existing `cam1` switch | Med | Med | Add `--relay-path` arg with default `cam1`; keep default behavior unchanged; unit tests for both paths |
| R-4 | FR-008 forbids recovery restart of `mediamtx.service`; redesign must not violate it | High | High | Recovery re-sources cam1 via MediaMTX REST API PATCH, not full restart; update forbidden-restart tests accordingly |
| R-5 | Ubuntu transcode adds CPU load; libx264 720p15 may saturate Ubuntu | Low | Med | `-preset veryfast -tune zerolatency`, single stream; monitor; Ubuntu has headroom |
| R-6 | Reader auth for `cam1-h264` missing -> VPS cannot read Ubuntu H264 | Med | High | Extend `ensure_internal_reader_rule` for `cam1-h264` (VPS IP); test |
| R-7 | AI worker accidentally pointed at relay `cam1-h264` | Low | Low | AI reads camera directly via `HLS_URL`; no change; verified in investigation |
| R-8 | Freshness watchdog `After=sea-speed-camera1-hls-http.service` breaks when external unit disabled | Med | Med | Update `sea-speed-camera1-h264-freshness.service` `After=` to `mediamtx.service` (or remove hls-http dep) |

## Test design

- T-1 (unit): `camera-source-switch.sh --relay-path cam1-h264` writes correct VPS MediaMTX `cam1`
  source and validates the private relay URL allows `/cam1-h264`; default `cam1` unchanged.
- T-2 (unit): `mediamtx_path_config.py vps-switch` accepts `--relay-path`; `ensure_internal_reader_rule`
  adds `cam1-h264` reader for VPS IP and is idempotent; `vps-set-hls-address` sets global `hlsAddress`.
- T-3 (unit): Ubuntu transcode script builds the correct ffmpeg command (HEVC input, libx264,
  publish to `cam1-h264`); systemd unit template renders with `Restart=always`.
- T-4 (unit): `camera1-h264-freshness-watchdog.py` recovery action is MediaMTX API PATCH re-source (not
  restart of retired transcode / mediamtx); `CAMERA1_LOCAL_HLS` stays `http://127.0.0.1:18889/cam1/index.m3u8`.
- T-5 (unit): `sea-speed-auth-privileged-helper.py run_camera1_h264_recovery` re-sources cam1 via API
  (no forbidden-service restart); forbidden-restart list still enforced.
- T-6 (unit): Ubuntu freshness watchdog restarts local transcode on stale `cam1-h264`.
- T-7 (contract): `validate_change_contract.py` — diff matches declared VPS+Ubuntu paths; no
  protected-boundary change; no secrets.

## Correct-course check

- If Ubuntu transcode fails at runtime: stop Ubuntu service, re-enable external VPS transcode +
  hls-http, revert `camera-source-switch.sh` to `cam1`, re-run switch. VPS MediaMTX `cam1` returns to
  HEVC relay; browser path restored via external units.
- If 18889 conflict: prefer FALLBACK (repo-managed hls-http reverse-proxy 8888->18889) and keep external
  hls-http disabled, or revert hlsAddress to :8888 and re-enable external hls-http.
- If reader auth blocks VPS: add `cam1-h264` reader rule; re-run `ensure_internal_reader_rule`.

## Deployment Transaction Audit (8 stages)

- ADMISSION: Issue #335 IMPLEMENTING; OUTCOME APPROVED six-field Scope; this SDD; Checkpoint v2 gen 1.
- PRE-MUTATION: snapshot external VPS unit state (`systemctl is-active` both); record current
  `camera-source-switch.sh` relay path (`cam1`); record MediaMTX `cam1` source; freeze rollback plan.
- MUTATION: (Ubuntu) install transcode service + reader auth + freshness watchdog; (VPS) generalize
  `camera-source-switch.sh` + `mediamtx_path_config.py`; set MediaMTX hlsAddress :18889; update watchdog +
  privileged helper recovery; disable external VPS transcode + hls-http; run `camera-source-switch.sh
  --relay-path cam1-h264 --hls-address :18889 --retire-external`.
- VERIFICATION: A-001..A-006 (18889 advances, browser path works, units active/disabled as expected).
- STATE-COMMIT: merge exact-green-head; protected VPS + Ubuntu deploy; runtime acceptance.
- HOUSEKEEPING: remove stashed/unused external-unit references from repo-managed scripts where safe;
  update docs (CAMERA1_DIRECT_H264_CUTOVER.md, SEA_SPEED_AUTH_V1.md) to reflect new topology.
- EVIDENCE: exact-artifacts.json, quality-evidence.json, release-manifest v3, deployment-manifest,
  execution-audit v1; Checkpoint v2 updated to DONE with evidence cursors.
- ROLLBACK: documented re-enable of external VPS units + revert relay path to `cam1` + stop Ubuntu
  transcode; verified reversible.

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
