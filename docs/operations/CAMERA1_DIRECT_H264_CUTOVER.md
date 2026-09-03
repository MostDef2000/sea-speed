# Camera 1 protected H264 browser route

Issue #115 supersedes the earlier public Camera 1 browser identity. Camera acquisition and browser-compatibility conversion remain unchanged, but the browser-facing route is now part of the authenticated Sea Speed namespace.

Canonical media path after Auth v1:

```text
new camera
-> Ubuntu private RTSP relay (cam1, HEVC)
-> Ubuntu Worker FFmpeg H264 transcode -> rtsp://127.0.0.1:8554/cam1-h264
-> VPS MediaMTX sources cam1-h264
-> 127.0.0.1:18889/cam1/
-> nginx
-> /sea-speed/media/cam1/index.m3u8
-> Authentik-protected browser session
```

The retired `/cams/hls/cam1/index.m3u8` route is not a compatibility requirement after Issue #115 and must not be recreated.

## Issue #335 — VPS→Ubuntu transcode relocation

Issue #335 moves the Camera 1 HEVC→H264 compatibility transcode off the VPS single vCPU onto the Ubuntu Worker. The VPS no longer runs an FFmpeg transcode process for Camera 1; it becomes a pure H264→HLS packager that sources the Ubuntu-published `cam1-h264` RTSP stream and serves HLS directly at `127.0.0.1:18889/cam1/`.

New transcode topology:

```text
camera (HEVC)
-> Ubuntu private RTSP relay cam1
-> Ubuntu Worker FFmpeg transcode (libx264, veryfast, zerolatency)
     publishes rtsp://127.0.0.1:8554/cam1-h264
-> VPS MediaMTX sources cam1-h264 (reader auth: VPS read + Ubuntu publish)
-> VPS MediaMTX HLS at 127.0.0.1:18889/cam1/
-> nginx UPSTREAM 127.0.0.1:18889/cam1/
-> /sea-speed/media/cam1/index.m3u8
```

Repository components after #335:

- `deploy/worker/ubuntu/camera1-h264-transcode.sh` + `sea-speed-camera1-h264.service` (Ubuntu) run the transcode and publish `cam1-h264`.
- `deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py` + `sea-speed-camera1-h264-freshness.service`/`.timer` (Ubuntu) supervise the produced `cam1-h264` stream and restart the Ubuntu transcode on stall.
- `deploy/vps/camera-source-switch.sh` performs the cutover: sets VPS MediaMTX `hlsAddress` to `:18889`, points `cam1` at `cam1-h264`, and disables the external VPS `sea-speed-camera1-h264.service` + `sea-speed-camera1-hls-http.service` (recorded for rollback).
- `scripts/operations/mediamtx_path_config.py` adds the `cam1-h264` reader rule for the VPS IP and the publisher rule for the Ubuntu transcode IP (combined credential-free relay path; VPS-only reader, public cannot publish/read).
- `deploy/vps/camera1-h264-freshness-watchdog.py` and `deploy/vps/sea-speed-auth-privileged-helper.py` recovery now re-source `cam1` via the MediaMTX REST API PATCH (FR-008). They MUST NOT restart `mediamtx.service`, `nginx`, or the retired external VPS transcode/hls-http units.

Cutover and rollback:

- Cutover: `deploy/vps/camera-source-switch.sh --relay-path cam1-h264 --hls-address :18889 --retire-external` on VPS, then the protected Ubuntu deploy enables the Ubuntu transcode service + freshness watchdog.
- Rollback: re-enable the external VPS `sea-speed-camera1-h264.service` + `sea-speed-camera1-hls-http.service`, revert the VPS relay path to `cam1`, and disable the Ubuntu transcode service. The Ubuntu transcode is additive and removable; the VPS path is restored to the pre-#335 behavior.

## Repository components

- `scripts/operations/nginx_cam1_direct_h264.py` renders/verifies only the protected Camera 1 H264 media location.
- `scripts/operations/nginx_sea_speed_auth.py` subsequently applies the Authentik Forward Auth boundary to every `/sea-speed/**` location and retires all `/cams/**` locations.
- `deploy/vps/sea-speed-auth-cutover.sh` is the only production activation path for this route after Auth v1.
- `deploy/vps/camera1-direct-h264-cutover.sh` is retained as a read-only compatibility status helper. Its standalone `activate` mode is deliberately retired.
- `deploy/vps/sea-speed-auth-privileged-helper.py` owns the fixed no-argument privileged recovery boundary used by the canonical VPS deployment transaction. After Auth v1 reconcile succeeds, it also verifies that the local Camera 1 HLS media sequence advances. If the playlist is valid but static, it first decodes one frame from the fixed credential-free Ubuntu relay `rtsp://10.123.239.102:8554/cam1`, then restarts only `sea-speed-camera1-h264.service`, and requires a newly advancing local HLS sequence before returning success.
- `deploy/vps/camera1-h264-freshness-watchdog.py` is the continuous runtime supervisor added by Issue #255. It uses the same fixed freshness predicate and relay-before-restart ordering between deployments, with a five-minute restart-attempt cooldown and no caller-selectable topology.
- `deploy/vps/sea-speed-camera1-h264-freshness.service` and `.timer` run that watchdog as a root oneshot on a bounded recurring cadence.

## H264 freshness recovery

Issue #226 adds a bounded recovery path for the observed failure mode where the Ubuntu private relay is live but the VPS H264 compatibility producer remains stuck on an old HLS playlist. That recovery is part of the existing exact-source-bound privileged `reconcile` transaction, so an ordinary VPS deployment cannot reach accepted `runtime_verified` state if Camera 1 HLS freshness fails.

The fixed deployment-time recovery contract is:

```text
local http://127.0.0.1:18889/cam1/index.m3u8 advances
  -> no-op

local HLS is valid but does not advance
  -> decode one frame from rtsp://10.123.239.102:8554/cam1
  -> restart only sea-speed-camera1-h264.service
  -> require the local HLS media sequence to advance
```

Fail-closed rules:

- an unavailable or malformed local HLS playlist is not treated as proof of a stale H264 producer and causes failure without a restart;
- an unreadable Ubuntu private relay causes failure before any restart;
- failure to restart or activate `sea-speed-camera1-h264.service` causes failure;
- a still-static HLS playlist after the fixed restart causes failure;
- neither recovery path restarts nginx, `sea-speed-camera1-hls-http.service`, MediaMTX, `sea-speed-worker.service`, or `sea-speed-road-worker.service`;
- no caller-provided service name, media URL, shell command, or root argument is accepted;
- the browser URL remains `/sea-speed/media/cam1/index.m3u8` and the camera/relay/Auth topology is unchanged.

## Continuous runtime freshness supervision

The 2026-08-22 incident demonstrated the remaining lifetime gap: `sea-speed-camera1-h264.service` stayed `active` while `#EXT-X-MEDIA-SEQUENCE` remained frozen for hours. The local HLS HTTP server continued returning `200` and old fMP4 segments, so browsers could loop old video even though systemd saw a live FFmpeg process. A simultaneous private-relay frame probe passed, proving the current upstream relay was healthy.

Issue #255 closes that gap with a persistent supervisor independent of deployment. The timer activates the fixed watchdog, which samples local HLS twice across three seconds. Advancing HLS is a no-op. Static HLS outside cooldown triggers one fixed private-relay frame probe; only a successful probe permits exactly one restart of `sea-speed-camera1-h264.service`. The watchdog then requires post-restart HLS progression.

The supervisor records each restart attempt before the restart and suppresses another attempt for 300 seconds. This prevents a persistent codec/upstream fault from creating a restart storm. An unreadable relay is never treated as a reason to restart the VPS producer. A root-private non-blocking lock prevents overlapping watchdog transactions.

Runtime entry point and topology are deliberately non-parameterized:

```text
HLS:     http://127.0.0.1:18889/cam1/index.m3u8
relay:   rtsp://10.123.239.102:8554/cam1
restart: sea-speed-camera1-h264.service only
state:   /var/lib/sea-speed-camera1-freshness
```

`install-auth-privilege-boundary.sh` remains the exact-source root bootstrap. In addition to the existing helper bundle it installs the watchdog executable and service/timer units, reloads systemd and enables/starts only `sea-speed-camera1-h264-freshness.timer`. The installer captures prior watchdog files and prior timer enabled/active state; a failed bootstrap restores those values before reporting rollback.

Issue #226 deployment-time recovery remains intentionally present. It is the release acceptance gate; Issue #255 is the 24/7 runtime liveness control.

## Safety rule

Do not activate `nginx_cam1_direct_h264.py` output by itself in production. The media renderer intentionally contains no legacy Basic Auth and is an intermediate candidate. The combined Auth v1 cutover renders the media location first and then the authentication/security configuration before nginx validation and reload.

This ordering guarantees that `/sea-speed/media/cam1/` is not introduced as an unauthenticated browser route.

## Acceptance

After the canonical exact-main production transaction:

- anonymous `/cams/hls/cam1/index.m3u8` exposes no camera content;
- anonymous `/sea-speed/media/cam1/index.m3u8` is denied/redirected through Authentik;
- an authenticated Sea Speed user sees current advancing H264 Camera 1 video;
- the browser upstream remains `127.0.0.1:18889/cam1/`;
- VPS MediaMTX is not reintroduced into the accepted Camera 1 browser path;
- live viewing remains independent of the AI worker;
- healthy HLS watchdog runs are no-op;
- static HLS with a healthy fixed relay causes exactly one bounded H264 producer restart and post-restart progression;
- static HLS with an unavailable relay causes no restart;
- cooldown prevents restart storms;
- production evidence demonstrates autonomous recovery to advancing authenticated video within 90 seconds;
- no camera credential is exposed in browser URLs or repository content.

Production execution requires the exact merged current-main release, exact push/main Quality, trusted standing production delegation and repository production-policy allow. Issue/PR comments are evidence only and are not runtime authority.
