# Tasks: Camera Live Pipeline

- Specification: specs/001-camera-live-pipeline/spec.md
- Plan: specs/001-camera-live-pipeline/plan.md
- Issue: #87
- Status: Production milestone accepted; browser security identity updated by Issue #115

## Delivery tasks

- [x] T001 Establish a credential-free private Ubuntu relay path for the new physical Camera 1.
- [x] T002 Prove the new camera media advances from Ubuntu to the VPS.
- [x] T003 Prepare a browser-compatible H.264 HLS output on the VPS.
- [x] T004 Preserve the then-existing Camera 1 browser identity for the original #87 milestone.
- [x] T005 Route the exact Camera 1 browser path to the proven H.264 output, bypassing VPS MediaMTX for Camera 1 playback.
- [x] T006 Keep AI inactive and prove live viewing does not depend on it.
- [x] T007 Obtain operator visual acceptance on mostdef.ru.
- [x] T008 Capture the accepted architecture and troubleshooting learning as SDD artifacts.
- [x] T009 Record Issue #115 as the separately approved replacement of the old public browser identity with protected `/sea-speed/media/cam1/index.m3u8`; private media behavior remains unchanged.

## Completion gate

- [x] Product media outcome achieved: new Camera 1 visibly plays on mostdef.ru.
- [x] Browser media remains H.264 and independent of VPS MediaMTX/AI.
- [x] Accepted runtime architecture recorded in spec and plan.
- [x] Original MediaMTX browser-path assumption explicitly superseded rather than silently forgotten.
- [x] Public `/cams/hls/cam1/index.m3u8` compatibility is explicitly superseded by Issue #115 rather than silently retained.
- [ ] Generic one-setting camera onboarding is implemented; this is follow-up work and not required for the accepted Camera 1 milestone.
