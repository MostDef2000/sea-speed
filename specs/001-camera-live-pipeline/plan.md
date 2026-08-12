# Implementation Plan: Camera Live Pipeline

- Specification: specs/001-camera-live-pipeline/spec.md
- Issue: #87
- Status: Accepted in production; browser security identity updated by Issue #115

## Architecture

Canonical media path after Issue #115:

```text
physical camera
-> Ubuntu private RTSP relay
-> VPS FFmpeg compatibility conversion
-> H.264 fMP4 HLS on loopback
-> nginx exact Camera 1 route
-> protected /sea-speed/media/cam1/index.m3u8
-> authenticated browser HLS player
```

The live path is independent of the AI worker. VPS MediaMTX may remain installed for other purposes, but it is not a required Camera 1 browser-path dependency.

## Decisions

### D-001 - Convert camera media before browser delivery

Normalize Camera 1 to H.264 1280x720 / 15fps HLS on the VPS because the camera/relay source is HEVC and the browser path failed when an HEVC `hvc1` manifest reached the player.

### D-002 - Bypass VPS MediaMTX in the Camera 1 browser path

Nginx routes the exact Camera 1 HLS prefix to the proven compatibility output rather than the generic MediaMTX HLS upstream. This accepted media decision is unchanged by Auth v1.

### D-003 - Protected Camera 1 browser identity

Issue #115 intentionally supersedes the former public `/cams/hls/cam1/index.m3u8` compatibility decision. The canonical browser identity is now `/sea-speed/media/cam1/index.m3u8` and is covered by the same Authentik Forward Auth boundary as the rest of `/sea-speed/**`.

## Affected contours

- Repository: camera relay/deployment logic, HLS compatibility conversion, nginx Camera 1 routing and browser playback handling.
- VPS: compatibility conversion and protected HLS routing.
- Ubuntu worker/relay: private relay from physical camera to VPS, unchanged.
- Windows worker/AI: no dependency for live viewing; no source/package change from Issue #115.
- Browser interface: protected Camera 1 URL defined above.

## Validation

- Static/CI: repository and behavioral tests for deployment/routing logic.
- Integration: prove local compatibility HLS contains advancing H.264 video before browser cutover.
- Security: prove old `/cams/**` path exposes no camera content and anonymous `/sea-speed/media/cam1/**` is denied/redirected.
- Runtime acceptance: authenticated operator visibly sees moving new Camera 1 video while AI can remain inactive.

## Rollout and rollback

- Original media rollout: private relay -> compatibility output -> Camera 1 route -> browser acceptance.
- Auth v1 migration: Authentik preflight -> combined protected Camera 1 + auth nginx candidate -> exact-SHA activation -> authenticated browser acceptance.
- Rollback after Auth v1 is fail-closed; do not automatically restore the retired public `/cams/**` route.

## Runtime feedback

The accepted H.264 compatibility architecture remains valid. Issue #115 changes only the browser-facing identity/security boundary. VPS MediaMTX remains excluded from the accepted Camera 1 browser path unless a future separately approved product decision changes it.
