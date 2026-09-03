# Tasks: Move Camera 1 HEVC→H264 Transcode from VPS to Ubuntu Worker

- Spec: 075-vps-transcode-to-ubuntu
- Specification: specs/075-vps-transcode-to-ubuntu/spec.md
- Canonical Issue: #335
- Traceability: FR-xxx from spec.md; DoD per task.

## Delivery tasks

### T-001 — Ubuntu transcode service (FR-001, FR-002)
- Add `deploy/worker/ubuntu/camera1-h264-transcode.sh`: ffmpeg `-rtsp_transport tcp -i
  rtsp://10.123.239.102:8554/cam1 -an -vf fps=15,scale=-2:720 -c:v libx264 -preset veryfast -tune
  zerolatency -f rtsp rtsp://127.0.0.1:8554/cam1-h264`.
- Add `deploy/worker/ubuntu/sea-speed-camera1-h264.service` (systemd, `Restart=always`,
  `NoNewPrivileges`, `After=network-online.target`).
- DoD: unit renders; command verified by T-3; `Restart=always` present. [DONE]

### T-002 — Ubuntu reader auth for cam1-h264 (FR-007)
- Extend `scripts/operations/mediamtx_path_config.py::ensure_internal_reader_rule` to add `cam1-h264`
  reader for VPS IP (credential-free relay path, VPS-only reader) and publisher for Ubuntu transcode IP.
- DoD: T-2 green; idempotent; VPS IP can read `cam1-h264`, public cannot publish/read. [DONE]

### T-003 — Ubuntu freshness watchdog (FR-009)
- Add `deploy/worker/ubuntu/sea-speed-camera1-h264-freshness.service` + `.timer` that samples the
  produced `cam1-h264` stream via the MediaMTX REST API and restarts the Ubuntu transcode service on stall.
- Wire into `deploy/worker/ubuntu/camera1-h264-transcode.sh activate`.
- DoD: watchdog unit renders; restart-on-stall logic covered by tests. [DONE]

### T-004 — Generalize VPS camera-source-switch (FR-003, FR-006)
- `deploy/vps/camera-source-switch.sh`: add `--relay-path` (default `cam1`); `verify_cam1_contract`
  accepts `/cam1-h264`; add `--hls-address` and `--retire-external` options; recovery re-sources cam1.
- `scripts/operations/mediamtx_path_config.py vps-switch`: accept `--relay-path`; add `vps-set-hls-address`.
- DoD: T-1 green; default `cam1` behavior unchanged; `cam1-h264` path validated. [DONE]

### T-005 — VPS hlsAddress :18889 (FR-004, FR-005)
- Change VPS MediaMTX global `hlsAddress` to `:18889` via `camera-source-switch.sh --hls-address :18889`
  (canonical HLS served directly by MediaMTX); disable external `sea-speed-camera1-hls-http.service`.
- DoD: `http://127.0.0.1:18889/cam1/index.m3u8` served and advances; nginx `UPSTREAM` unchanged (18889). [DONE]

### T-006 — Redesign VPS freshness recovery (FR-008)
- `deploy/vps/camera1-h264-freshness-watchdog.py`: recovery action = MediaMTX REST API PATCH re-source
  (not restart of retired transcode / `mediamtx.service`).
- `deploy/vps/sea-speed-auth-privileged-helper.py::run_camera1_h264_recovery`: same re-source action.
- `deploy/vps/sea-speed-camera1-h264-freshness.service`: `After=` remove `sea-speed-camera1-hls-http.service`
  dependency (use `mediamtx.service` or none).
- DoD: T-4, T-5 green; forbidden-restart boundary preserved; `CAMERA1_LOCAL_HLS` unchanged (18889). [DONE]

### T-007 — Disable external VPS units at cutover (FR-011, NFR-005)
- Cutover step disables external `sea-speed-camera1-h264.service` + `sea-speed-camera1-hls-http.service`
  (if present); records state for rollback.
- DoD: A-004; rollback re-enables and reverts relay path to `cam1`. [DONE]

### T-008 — Tests + validation (A-005)
- Update `tests/test_camera1_h264_freshness_watchdog.py`, `tests/test_vps_auth_privilege_boundary.py`;
  add `tests/test_vps_transcode_to_ubuntu.py`.
- Run `scripts/ci/validate_*.py`, `scripts/quality/*.py`, `python -m unittest discover -s tests -p test_*.py -v`.
- DoD: all green locally. [DONE]

### T-009 — Docs + Change Contract (A-006)
- Update `docs/operations/CAMERA1_DIRECT_H264_CUTOVER.md`, `docs/operations/SEA_SPEED_AUTH_V1.md`.
- PR Change Contract: VPS REQUIRED, Ubuntu REQUIRED, production safety envelope REQUIRED, execution
  capability CONNECTOR, operator actions 0.
- DoD: Change Contract matches diff; PR created; CI green. [IN PROGRESS]

### T-010 — Merge + protected deploy + runtime acceptance (DONE gate)
- Exact-green-head merge; protected VPS + Ubuntu deploy (`--require-allow`); runtime acceptance
  A-001..A-006; Checkpoint v2 -> DONE with evidence cursors.
- DoD: terminal DONE with all evidence. [PENDING]

## Requirements traceability

| FR/NFR | Task | Evidence |
|--------|------|----------|
| FR-001 | T-001 | `camera1-h264-transcode.sh`, `sea-speed-camera1-h264.service` |
| FR-002 | T-001 | ffmpeg libx264 args in transcode script |
| FR-003 | T-004 | `camera-source-switch.sh --relay-path cam1-h264` |
| FR-004 | T-005 | nginx `UPSTREAM` unchanged; 18889 advances |
| FR-005 | T-005 | `vps-set-hls-address :18889`; external hls-http disabled |
| FR-006 | T-004 | `--relay-path` + `vps-set-hls-address` |
| FR-007 | T-002 | `ensure_internal_reader_rule` cam1-h264 combined rule |
| FR-008 | T-006 | watchdog/helper API PATCH re-source; no mediamtx restart |
| FR-009 | T-003 | Ubuntu freshness watchdog restarts transcode |
| FR-010 | — | AI reads camera directly; no change |
| FR-011 | T-007 | cutover disables external units; rollback documented |
| NFR-001 | T-001 | VPS encode removed |
| NFR-003 | T-003,T-006 | both watchdogs |
| NFR-004 | T-002 | reader auth VPS-only |
| NFR-005 | T-007 | rollback documented |
| NFR-006 | T-006 | watchdog logs reflect new topology |

## Definition of Done

- All significant tasks T-001..T-010 complete with DoD met.
- `python -m unittest discover` green; `scripts/ci/validate_*.py` + `scripts/quality/*.py` green.
- PR Change Contract matches exact diff; required CI green; exact-green-head merge.
- Protected VPS + Ubuntu deploy (`--require-allow`) succeeds; runtime acceptance A-001..A-006 verified.
- Checkpoint v2 updated to DONE with evidence cursors.

## Completion gate

- Exact-green-head merge on `main`.
- Protected VPS + Ubuntu deploy with `SEA_SPEED_PRODUCTION_DELEGATION_V1` ALLOW.
- Runtime acceptance: `http://127.0.0.1:18889/cam1/index.m3u8` advances; Ubuntu transcode active; external
  VPS units disabled; rollback verified reversible.
- Terminal `DONE` recorded on Issue #335 with evidence cursors.
