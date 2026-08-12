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

## Safety rule

Do not activate `nginx_cam1_direct_h264.py` output by itself in production. The media renderer intentionally contains no legacy Basic Auth and is an intermediate candidate. The combined Auth v1 cutover renders the media location first and then the authentication/security configuration before nginx validation and reload.

This ordering guarantees that `/sea-speed/media/cam1/` is not introduced as an unauthenticated browser route.

## Acceptance

After the separately authorized Auth v1 production cutover:

- anonymous `/cams/hls/cam1/index.m3u8` exposes no camera content;
- anonymous `/sea-speed/media/cam1/index.m3u8` is denied/redirected through Authentik;
- an authenticated Sea Speed user sees advancing H264 Camera 1 video;
- the browser upstream remains `127.0.0.1:18889/cam1/`;
- VPS MediaMTX is not reintroduced into the accepted Camera 1 browser path;
- live viewing remains independent of the AI worker;
- no camera credential is exposed in browser URLs or repository content.

Production mutation still requires an exact merged `main` SHA and separate `PRODUCTION APPROVED` authorization.
