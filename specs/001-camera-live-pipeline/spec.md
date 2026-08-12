# Feature Specification: Camera Live Pipeline

- Feature: 001-camera-live-pipeline
- Issue: #87
- Status: Accepted in production
- Runtime acceptance: 2026-08-12 - operator confirmed the new physical Camera 1 is visibly playing on mostdef.ru.

## Product outcome

An operator can open the existing Camera 1 view on mostdef.ru and reliably see the new physical camera. Live viewing works independently of the AI worker. Adding a future camera should require identifying the camera and its source, not rebuilding a chain of browser-specific fixes.

## User scenarios

### Scenario 1 - View Camera 1

Given the new physical Camera 1 is online, when the operator opens the Sea Speed page, then the LIVE CAMERA area shows advancing video from that camera through the existing Camera 1 identity.

### Scenario 2 - Live view while AI is off

Given the AI worker is stopped, when the operator opens Camera 1, then live video remains available because live delivery and AI processing are independent concerns.

### Scenario 3 - Add a future camera

Given a supported camera source and a new camera identifier, when the camera is configured, then the system prepares a browser-compatible live stream and exposes it through that camera's stable public identity without requiring a new media architecture.

## Requirements

- FR-001: The public Camera 1 identity MUST remain `/cams/hls/cam1/index.m3u8` unless a separately approved product change replaces it.
- FR-002: The live stream MUST originate from the new physical camera through the Ubuntu-side private relay path.
- FR-003: The VPS MUST prepare a browser-compatible stream when the camera's native format is not broadly browser-compatible.
- FR-004: Browser playback MUST NOT depend on VPS MediaMTX being in the Camera 1 browser delivery path.
- FR-005: Live viewing MUST remain available while the AI worker is stopped.
- FR-006: The browser-facing Camera 1 path MUST use the proven H.264 HLS output rather than exposing the camera's native HEVC manifest.
- FR-007: Future camera onboarding SHOULD converge on a small configuration surface: camera identifier plus protected source/relay configuration, with browser output prepared automatically.
- FR-008: Camera credentials MUST NOT be placed in frontend source, public URLs or repository files.

## Acceptance criteria

- AC-001: An operator visibly sees advancing new Camera 1 video on mostdef.ru.
- AC-002: The public Camera 1 URL remains unchanged.
- AC-003: The browser receives a compatible H.264 live path and no longer fails on an HEVC-only `hvc1` manifest.
- AC-004: AI remains inactive without interrupting live viewing.
- AC-005: The working browser path bypasses VPS MediaMTX for Camera 1.
- AC-006: A future camera can reuse the same pattern without repeating the Camera 1 troubleshooting sequence.

## Compatibility and boundaries

- Stable public interface: `/cams/hls/cam1/index.m3u8`.
- Stable product identity: Camera 1 remains Camera 1; no Camera 2 is introduced by this feature.
- Out of scope: AI Start/Stop controls, generic camera management UI, Camera 2, recording, analytics and large-scale multi-camera capacity planning.
- Security constraints: existing protected source handling remains; security hardening may evolve separately but credentials are not made public.

## Runtime feedback

- Runtime acceptance: ACCEPTED on 2026-08-12 by direct operator observation of moving new Camera 1 video on mostdef.ru.
- Accepted production behavior: physical camera -> Ubuntu private relay -> VPS conversion to H.264 -> HLS -> nginx Camera 1 public route -> browser.
- Superseded assumption from Issue #87: VPS MediaMTX is NOT required in the accepted Camera 1 browser path. The original Issue remains historical evidence of the earlier design.
- Learning: the browser failures were caused by receiving an incompatible HEVC `hvc1` manifest through the old browser path, while the separately prepared H.264 stream was already healthy.
- Follow-up work: generalize camera onboarding so future cameras are configured through a small declarative interface; separately address AI controls and optional cleanup of legacy media components.
