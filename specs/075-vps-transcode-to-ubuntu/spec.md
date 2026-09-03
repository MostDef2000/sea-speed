# Spec: Move Camera 1 HEVC→H264 Transcode from VPS to Ubuntu Worker

- Spec ID: 075-vps-transcode-to-ubuntu
- Issue: #335
- Canonical Issue: #335
- Status: ACTIVE (implementation authorized via OUTCOME APPROVED on six-field Scope)
- Runtime contours: MIXED (VPS + Ubuntu Worker/relay)
- Deployment Transaction Audit: REQUIRED (8 stages)
- Linked Change Contract: VPS REQUIRED, Ubuntu REQUIRED, production safety envelope REQUIRED

## Product outcome

Offload the Camera 1 HEVC→H264 transcode from the CPU-constrained VPS single-vCPU host to the
Ubuntu Worker, which has sufficient CPU headroom for one 720p15 software libx264 encode. The browser
HLS endpoint at `http://127.0.0.1:18889/cam1/index.m3u8` must remain served and advancing, with nginx
config unchanged (`UPSTREAM` stays 18889). The VPS becomes a pure H264→HLS packager; Ubuntu becomes the
transcode producer.

Two hardware/software options were evaluated:

- Option 2 (VAAPI/QSV on Ubuntu): **REJECTED** — verified unavailable. `ffmpeg -vaapi_device
  /dev/dri/renderD128 ... -c h264_vaapi` failed with `Failed to initialise VAAPI connection: -1
  (unknown libva error). Device creation failed: -5. Failed to set value '/dev/dri/renderD128'
  for option 'vaapi_device': Input/output error`. Intel VA-API userspace driver is not installed.
- Option 3 (software libx264 on Ubuntu): **SELECTED** — CPU headroom on Ubuntu is sufficient for
  one 720p15 H264 encode.

Decision recorded on Issue #335 (variant A / Option 3). This spec covers Option 3 only.

### Current topology (pre-migration)

```
physical camera (HEVC RTSP)
  -> Ubuntu private RTSP relay cam1 (10.123.239.102:8554/cam1, HEVC)
  -> VPS sea-speed-camera1-h264.service (ffmpeg HEVC->H264, EXTERNAL, not in repo)
  -> sea-speed-camera1-hls-http.service (HLS HTTP @127.0.0.1:18889/cam1, EXTERNAL, not in repo)
  -> nginx (/sea-speed/media/cam1/ -> 127.0.0.1:18889/cam1/)
  -> Authentik -> browser
```

VPS MediaMTX `cam1` (HEVC, sourced from Ubuntu relay) produces HLS at `:8888` but is NOT consumed
by the browser path (AI worker reads the camera directly via `HLS_URL`; browser uses 18889).

### Target topology (post-migration)

```
physical camera (HEVC RTSP)
  -> Ubuntu private RTSP relay cam1 (10.123.239.102:8554/cam1, HEVC)            [unchanged]
  -> Ubuntu sea-speed-camera1-h264.service (NEW, repo-managed:
       ffmpeg HEVC->H264 -> publish RTSP H264 rtsp://127.0.0.1:8554/cam1-h264)  [NEW]
  -> VPS MediaMTX cam1 (sources rtsp://10.123.239.102:8554/cam1-h264, H264)      [changed source]
  -> VPS MediaMTX HLS @ :8889 (repo-managed hls-http reverse-proxy 8888->18889)  [repo-managed]
  -> nginx (/sea-speed/media/cam1/ -> 127.0.0.1:18889/cam1/)                     [unchanged]
  -> Authentik -> browser
```

External VPS units `sea-speed-camera1-h264.service` and `sea-speed-camera1-hls-http.service` are
disabled at cutover (rollback re-enables them). VPS MediaMTX global `hlsAddress` is changed to `:18889`
so the canonical HLS is served directly by MediaMTX; the external hls-http unit is disabled instead of
replaced.

## User scenarios

- SC-001: A viewer opens the authenticated Camera 1 page and sees advancing H264 HLS with no change in
  URL or auth behavior.
- SC-002: The VPS operator observes reduced steady CPU (no ffmpeg encode) while Ubuntu runs the transcode.
- SC-003: On an Ubuntu transcode stall, the Ubuntu freshness watchdog restarts the local transcode and
  the browser stream recovers automatically.
- SC-004: On a VPS MediaMTX `cam1` source stall, the VPS freshness watchdog re-sources `cam1` via the
  MediaMTX REST API (no mediamtx/nginx restart), preserving the FR-008 blast-radius boundary.
- SC-005: A rollback re-enables the external VPS transcode + hls-http units and reverts the VPS MediaMTX
  `cam1` source to the HEVC relay.

## Requirements

- FR-001: Ubuntu MUST run a repo-managed systemd service that decodes the Ubuntu relay `cam1`
  (HEVC, RTSP `rtsp://10.123.239.102:8554/cam1`, TCP) and publishes H264 RTSP to
  `rtsp://127.0.0.1:8554/cam1-h264` on Ubuntu MediaMTX, with `Restart=always`.
- FR-002: The Ubuntu transcode MUST use software libx264 (`-an -vf fps=15,scale=-2:720 -c:v
  libx264 -preset veryfast -tune zerolatency`), no hardware accelerator.
- FR-003: VPS MediaMTX `cam1` MUST source `rtsp://10.123.239.102:8554/cam1-h264` (H264) instead
  of the HEVC relay, configured via the generalized `camera-source-switch.sh --relay-path
  cam1-h264 --hls-address :18889 --retire-external`.
- FR-004: The browser HLS endpoint `http://127.0.0.1:18889/cam1/index.m3u8` MUST remain served and
  advance (video frames progress), with nginx config unchanged (`UPSTREAM` stays 18889).
- FR-005: VPS MediaMTX global `hlsAddress` MUST be set to `:18889` at cutover (canonical HLS served
  directly by MediaMTX); the external `sea-speed-camera1-hls-http.service` MUST be disabled.
- FR-006: VPS `camera-source-switch.sh` MUST generalize the relay path (currently hardcoded `/cam1`)
  via `--relay-path`, and `mediamtx_path_config.py vps-switch` MUST accept the same; a new
  `vps-set-hls-address` subcommand MUST set the global `hlsAddress`.
- FR-007: Ubuntu reader auth (`ensure_internal_reader_rule`) MUST allow the VPS IP to read
  `cam1-h264` (credential-free relay path), mirroring the existing `cam1` rule; the Ubuntu transcode
  IP MUST be allowed to publish `cam1-h264`.
- FR-008: VPS freshness recovery MUST NOT restart `mediamtx.service`, `nginx.service`, or
  `sea-speed-camera1-hls-http.service` (preserve existing blast-radius boundary). On stall it MUST
  re-source VPS MediaMTX `cam1` via the MediaMTX REST API PATCH (no full service restart).
- FR-009: Ubuntu freshness supervision MUST monitor the produced `cam1-h264` stream and restart the
  Ubuntu transcode service on stall (local, allowed).
- FR-010: AI worker path MUST be unchanged (reads camera directly via `HLS_URL`); no SDD/code change
  required for AI.
- FR-011: External VPS units `sea-speed-camera1-h264.service` and `sea-speed-camera1-hls-http.service`
  MUST be disabled at cutover with a documented rollback that re-enables them and reverts
  `camera-source-switch.sh` to `cam1`.

### Non-functional requirements

- NFR-001 (CPU offload): VPS steady ffmpeg encode load MUST be removed; Ubuntu encodes instead.
- NFR-002 (Latency): end-to-end browser latency MUST stay within the existing Camera 1 budget
  (transcode + HLS segmenting); regression bounded by freshness supervision.
- NFR-003 (Reliability): Ubuntu transcode `Restart=always` + Ubuntu freshness watchdog; VPS
  freshness watchdog unchanged URL (18889) with API re-source recovery.
- NFR-004 (Security): relay path `cam1-h264` stays credential-free; reader auth restricts it to the
  VPS IP only (no public publish/reader). No secrets in repo.
- NFR-005 (Rollback): cutover is reversible: re-enable external VPS transcode + hls-http, revert
  `camera-source-switch.sh` to `cam1`, stop Ubuntu transcode.
- NFR-006 (Observability): freshness watchdog logs + Change Contract evidence MUST reflect the new
  topology (18889 served by MediaMTX).

## Acceptance criteria

- A-001: `systemctl is-active sea-speed-camera1-h264.service` on Ubuntu == active; process is ffmpeg
  publishing H264 to `rtsp://127.0.0.1:8554/cam1-h264`.
- A-002: VPS MediaMTX `cam1` source == `rtsp://10.123.239.102:8554/cam1-h264` (H264); HLS at
  `http://127.0.0.1:18889/cam1/index.m3u8` advances (media sequence increments across samples).
- A-003: browser path `/sea-speed/media/cam1/` serves advancing H264 HLS (authenticated).
- A-004: external VPS `sea-speed-camera1-h264.service` and `sea-speed-camera1-hls-http.service`
  (if present) are disabled; VPS MediaMTX `hlsAddress` == `:18889`.
- A-005: `python -m unittest discover` green; `scripts/ci/validate_*.py` + `scripts/quality/*.py`
  green; PR Change Contract matches diff.
- A-006: rollback procedure verified (re-enable external units, revert relay path to `cam1`).

## Runtime feedback

- The Ubuntu transcode publishes to `cam1-h264` on Ubuntu MediaMTX; the VPS reads it as the `cam1`
  source. The VPS HLS is served at `:18889` by MediaMTX directly (global `hlsAddress`).
- The Ubuntu freshness watchdog queries the MediaMTX REST API for `cam1-h264` state and restarts the
  local transcode on stall.
- The VPS freshness watchdog and privileged helper re-source `cam1` via the MediaMTX REST API PATCH on
  stall, never restarting `mediamtx.service`/`nginx.service` (FR-008).
- Out-of-scope siblings: #362 (RTP loss on cam1 relay), #363 (TIME-WAIT on 18889) remain separate tasks.

## Out of scope

- Issue #362 (RTP packet loss / invalid fragmentation unit on camera→Ubuntu relay `cam1`): separate
  reliability task, not changed by this migration.
- Issue #363 (750 TIME-WAIT on 127.0.0.1:18889): API↔local-HLS short-connection exhaustion; separate
  task, not changed by this migration.
- VAAPI/QSV enablement on Ubuntu (Option 2): deferred, requires driver install + separate spec.
- AI worker inference changes: none.
