# Quickstart: Validate Camera Live Pipeline

- Specification: specs/001-camera-live-pipeline/spec.md
- Security migration: Issue #115 / `specs/004-sea-speed-auth-v1/spec.md`

## Product check

1. Authenticate to Sea Speed.
2. Open the Sea Speed page on mostdef.ru.
3. Confirm LIVE CAMERA shows the new physical Camera 1 through `/sea-speed/media/cam1/index.m3u8`.
4. Confirm the image advances rather than remaining frozen.
5. Confirm live viewing still works while the AI worker is inactive.

## Security check

- anonymous `/cams/hls/cam1/index.m3u8` exposes no camera content;
- anonymous `/sea-speed/media/cam1/index.m3u8` is Authentik-gated;
- authenticated Camera 1 HLS plays normally.

## Architecture check

The accepted browser media remains the H.264 compatibility output and must not reinsert VPS MediaMTX into the Camera 1 browser path without a new feature decision and runtime reason. Issue #115 changes only the browser-facing security namespace.

## Future camera rule

A future camera should reuse the same separation of concerns: private acquisition, browser compatibility normalization when necessary, and a stable protected identity under the authenticated Sea Speed contour.
