# Spec: Water camera RTSP 461 — configurable transport and credentials out of argv

- Issue: #384
- Status: ACTIVE
- Specification: specs/384-water-rtsp-udp/spec.md
- Runtime contour: Ubuntu Worker/relay (`deploy/worker/ubuntu/**`, `worker/ubuntu_worker_entrypoint.py`); VPS NOT APPLICABLE

## Product outcome

The water camera (192.168.88.20:554 channel 101) stopped accepting TCP-interleaved
RTSP (SETUP → 461 Unsupported Transport) around 2026-08-23 while UDP delivery keeps
working (verified 2026-09-11 from the Worker: ffmpeg udp EXIT=0, tcp → 461; TCP 554
open on all 33 pool cameras, OPTIONS → 200 OK; control road camera 88.44 tcp OK).
Sea Speed readers hardcode `-rtsp_transport tcp`, so the water stream is dead: the
transcode service crash-loops (restart counter 19), the worker freshness watchdog
fails probing the dead `cam1` relay leg, the analytics worker burns ~44% CPU on
retries, and dashboard cam20/cam16+ frames are frozen.

Outcome: direct readers of the water camera honor one configurable transport
(`CAMERA1_RTSP_TRANSPORT`, default `udp` for credential-bearing direct camera reads;
`tcp` unchanged for private-relay reads and the local MediaMTX probe), camera
credentials no longer appear in `/proc/*/cmdline` (ffmpeg reads the credential URL
from a 0600 ffconcat file in PrivateTmp), the transcode crash-loop and watchdog
false failures stop, and dashboard cam20/cam16+ frames update again.

## User scenarios

- Owner opens the dashboard: cam20/cam16+ frames update again after the autonomous deploy.
- Owner someday restores TCP in the camera web UI: setting `CAMERA1_RTSP_TRANSPORT=tcp`
  in the protected worker.env flips direct readers back without code changes.
- Local user runs `ps` on the Worker: no camera password in any Sea Speed ffmpeg command line.
- Road camera 88.44 and its preview relay keep working exactly as before (tcp).

## Requirements

- R1: `camera1-h264-transcode.sh run` selects the RTSP transport from
  `CAMERA1_RTSP_TRANSPORT` (values `udp|tcp|automatic`, default `udp`), validates it,
  and never places the credential-bearing HLS_URL in ffmpeg argv: the camera URL is
  embedded in a 0600 ffconcat file (`option rtsp_transport <transport>`) created in
  the service PrivateTmp /tmp after stale-file cleanup.
- R2: `ubuntu_worker_entrypoint.py` `_spawn_rtsp_ffmpeg` uses `CAMERA1_RTSP_TRANSPORT`
  (default `udp`) for credential-bearing RTSP inputs via the same ffconcat mechanism
  (0600 file, O_NOFOLLOW|O_EXCL, per-profile fixed name) and keeps the existing
  `-rtsp_transport tcp` argv for non-credential private-relay inputs.
- R3: `camera1-h264-freshness-watchdog.py` (worker copy) probes the product path
  `rtsp://10.123.239.102:8554/cam1-h264` instead of the dead `cam1` relay leg,
  keeping the fixed no-argument, no-environment-override contract.
- R4: No change to the other 32 cameras, road camera 88.44 handling, MediaMTX path
  rendering (`scripts/operations/mediamtx_path_config.py`), deploy workflows,
  reader consolidation (deferred step 2), protected worker.env values, VPS, or the
  public site.

## NFR assessment

- NFR-384-001 | Area: reliability | Target: water stream restores over UDP; transcode service stops crash-looping; watchdog recovery targets the product path | Validation: unit tests for transport selection + ffconcat construction + watchdog source pin; runtime acceptance on Worker (journal without 461, service active, no restart growth) | Evidence: tests, deploy evidence | Status: PASS
- NFR-384-002 | Area: security | Target: camera credentials absent from /proc/*/cmdline for all Sea Speed ffmpeg processes; ffconcat file 0600 with O_NOFOLLOW|O_EXCL in PrivateTmp; stale files removed; secrets never printed | Validation: unit tests assert ffconcat argv construction and file contract; existing log-hygiene tests stay green | Evidence: tests | Status: PASS
- NFR-384-003 | Area: compatibility | Target: tcp readers unchanged (private relay, road, local probe); out-of-scope contracts intact (test_worker_rtsp_media_security passes unchanged) | Validation: full unittest suite green without modifying out-of-scope tests | Evidence: unittest | Status: PASS
- NFR-384-004 | Area: operability | Target: one env knob with strict validation; invalid value fails fast with a clear error before any ffmpeg start | Validation: unit test for invalid transport rejection | Evidence: tests | Status: PASS

## Acceptance criteria

- AC-001: After the autonomous Ubuntu deploy, `sea-speed-camera1-h264` is active with
  no restart growth and no `461 Unsupported Transport` in its journal; the freshness
  timer run exits 0.
- AC-002: ffprobe from the VPS reads `rtsp://10.123.239.102:8554/cam1-h264`
  successfully; dashboard cam20/cam16+ frames update.
- AC-003: No camera credentials appear in Sea Speed ffmpeg `/proc/*/cmdline` on the Worker.
- AC-004: Unit tests cover transport selection/defaults, ffconcat construction, and
  the watchdog source pin; the full local CI suite is green.

## Runtime feedback

- Prior behaviour: readers hardcoded `-rtsp_transport tcp`; the camera's TCP broke
  ~2026-08-23 → crash-loop + frozen dashboard; camera credentials visible in
  `/proc/*/cmdline` (owner consciously deferred password rotation; the ffconcat
  mechanism removes the exposure without requiring a password change).
