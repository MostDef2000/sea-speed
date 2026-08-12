# Quickstart: Validate Camera Live Pipeline

- Specification: specs/001-camera-live-pipeline/spec.md

## Product check

1. Open the Sea Speed page on mostdef.ru.
2. Confirm LIVE CAMERA shows the new physical Camera 1.
3. Confirm the image advances rather than remaining frozen.
4. Confirm live viewing still works while the AI worker is inactive.

## Architecture check

The accepted browser path is the H.264 compatibility output routed through the stable Camera 1 public identity. Do not reinsert VPS MediaMTX into the Camera 1 browser path without a new feature decision and runtime reason.

## Future camera rule

A future camera should reuse the same separation of concerns: private acquisition, browser compatibility normalization when necessary, and a stable public identity. The goal is declarative onboarding, not per-camera frontend troubleshooting.
