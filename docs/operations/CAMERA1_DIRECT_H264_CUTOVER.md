# Camera 1 protected H264 browser route

Issue #115 supersedes the earlier public Camera 1 browser identity. Camera acquisition and browser-compatibility conversion remain unchanged, but the browser-facing route is now part of the authenticated Sea Speed namespace.

Canonical media path after Auth v1:

```text
new camera
-> Ubuntu private RTSP relay
-> VPS FFmpeg H264 compatibility output
-> 127.0.0.1:18889/cam1/
-> nginx
-> /sea-speed/media/cam1/index.m3u8
-> Authentik-protected browser session
```

The retired `/cams/hls/cam1/index.m3u8` route is not a compatibility requirement after Issue #115 and must not be recreated.

## Repository components

- `scripts/operations/nginx_cam1_direct_h264.py` renders/verifies only the protected Camera 1 H264 media location.
- `scripts/operations/nginx_sea_speed_auth.py` subsequently applies the Authentik Forward Auth boundary to every `/sea-speed/**` location and retires all `/cams/**` locations.
- `deploy/vps/sea-speed-auth-cutover.sh` is the only production activation path for this route after Auth v1.
- `deploy/vps/camera1-direct-h264-cutover.sh` is retained as a read-only compatibility status helper. Its standalone `activate` mode is deliberately retired.
- `deploy/vps/sea-speed-auth-privileged-helper.py` owns the fixed no-argument privileged recovery boundary used by the canonical VPS deployment transaction. After Auth v1 reconcile succeeds, it also verifies that the local Camera 1 HLS media sequence advances. If the playlist is valid but static, it first decodes one frame from the fixed credential-free Ubuntu relay `rtsp://10.123.239.102:8554/cam1`, then restarts only `sea-speed-camera1-h264.service`, and requires a newly advancing local HLS sequence before returning success.

## H264 freshness recovery

Issue #226 adds a bounded recovery path for the observed failure mode where the Ubuntu private relay is live but the VPS H264 compatibility producer remains stuck on an old HLS playlist. The recovery is part of the existing exact-source-bound privileged `reconcile` transaction, so the ordinary VPS deployment cannot reach accepted `runtime_verified` state if Camera 1 HLS freshness fails.

The fixed recovery contract is:

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
- a still-static HLS playlist after the fixed restart causes deployment failure;
- the helper does not restart nginx, `sea-speed-camera1-hls-http.service`, MediaMTX, `sea-speed-worker.service`, or `sea-speed-road-worker.service`;
- no caller-provided service name, media URL, shell command, or root argument is accepted;
- the browser URL remains `/sea-speed/media/cam1/index.m3u8` and the camera/relay/Auth topology is unchanged.

Because the privileged helper bundle is exact-source-bound, any release that changes this helper requires the repository-owned `install-auth-privilege-boundary.sh` bootstrap for that exact approved source before the canonical VPS deployment can use the new recovery logic.

## Safety rule

Do not activate `nginx_cam1_direct_h264.py` output by itself in production. The media renderer intentionally contains no legacy Basic Auth and is an intermediate candidate. The combined Auth v1 cutover renders the media location first and then the authentication/security configuration before nginx validation and reload.

This ordering guarantees that `/sea-speed/media/cam1/` is not introduced as an unauthenticated browser route.

## Acceptance

After the separately authorized Auth v1 / Issue #226 production deployment:

- anonymous `/cams/hls/cam1/index.m3u8` exposes no camera content;
- anonymous `/sea-speed/media/cam1/index.m3u8` is denied/redirected through Authentik;
- an authenticated Sea Speed user sees advancing H264 Camera 1 video;
- the browser upstream remains `127.0.0.1:18889/cam1/`;
- VPS MediaMTX is not reintroduced into the accepted Camera 1 browser path;
- live viewing remains independent of the AI worker;
- stale HLS recovery is a no-op when the playlist already advances;
- stale HLS recovery restarts only `sea-speed-camera1-h264.service` after a successful fixed private-relay frame probe;
- no camera credential is exposed in browser URLs or repository content.

Production mutation still requires an exact merged `main` SHA and separate `PRODUCTION APPROVED` authorization.
