# Implementation Plan: Camera Live Pipeline

- Specification: specs/001-camera-live-pipeline/spec.md
- Issue: #87
- Status: Accepted in production

## Architecture

Canonical accepted path:

```text
physical camera
-> Ubuntu private RTSP relay
-> VPS FFmpeg compatibility conversion
-> H.264 fMP4 HLS on loopback
-> nginx exact Camera 1 route
-> existing public /cams/hls/cam1/index.m3u8
-> browser HLS player
```

The live path is independent of the AI worker. VPS MediaMTX may remain installed for other purposes, but it is not a required Camera 1 browser-path dependency.

## Decisions

### D-001 - Convert camera media before browser delivery

- Decision: normalize Camera 1 to H.264 1280x720 / 15fps HLS on the VPS.
- Reason: the camera/relay source is HEVC and the browser path failed when an HEVC `hvc1` manifest reached the player.
- Alternatives rejected: rely on browser HEVC support; continue tuning frontend recovery around an incompatible manifest.

### D-002 - Bypass VPS MediaMTX in the Camera 1 browser path

- Decision: nginx routes the exact Camera 1 HLS prefix to the proven compatibility output rather than the generic MediaMTX HLS upstream.
- Reason: the compatibility output was healthy and advancing, while the generic path still exposed the incompatible stream. Removing the unnecessary hop made the product work and reduced ambiguity.
- Alternatives rejected: further MediaMTX compatibility debugging for this milestone.

### D-003 - Preserve public Camera 1 identity

- Decision: keep `/cams/hls/cam1/index.m3u8` stable.
- Reason: the frontend and operator workflow should not change merely because the camera source/encoding changed.

## Affected contours

- Repository: camera relay/deployment logic, HLS compatibility conversion, nginx Camera 1 routing and browser playback handling.
- VPS: compatibility conversion and public HLS routing.
- Ubuntu worker/relay: private relay from physical camera to VPS.
- Windows worker/AI: no dependency for live viewing; AI remains inactive for this milestone.
- Public interfaces: Camera 1 URL preserved.

## Validation

- Static/CI: repository and behavioral tests for deployment/routing logic.
- Integration: prove local compatibility HLS contains advancing H.264 video before public cutover.
- Runtime acceptance: operator visibly sees moving new Camera 1 video on mostdef.ru while AI is inactive.

## Rollout and rollback

- Rollout: prove private relay -> prove compatibility output -> route exact Camera 1 public path -> browser hard refresh -> visual acceptance.
- Rollback: protected nginx/service backups are retained; rollback is never automatic and requires an explicit decision.

## Runtime feedback

- Actual architecture after acceptance: matches the canonical path above.
- Differences from original Issue plan: VPS MediaMTX was removed as a mandatory Camera 1 browser-path hop after repeated incompatibility evidence.
- Deferred cleanup: legacy MediaMTX-related mappings/services may be reviewed separately; do not disturb the working live path merely for cleanup.
