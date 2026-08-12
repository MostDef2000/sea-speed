# Tasks: Camera Live Pipeline

- Specification: specs/001-camera-live-pipeline/spec.md
- Plan: specs/001-camera-live-pipeline/plan.md
- Issue: #87
- Status: Production milestone accepted

## Delivery tasks

- [x] T001 Establish a credential-free private Ubuntu relay path for the new physical Camera 1.
- [x] T002 Prove the new camera media advances from Ubuntu to the VPS.
- [x] T003 Prepare a browser-compatible H.264 HLS output on the VPS.
- [x] T004 Preserve the existing public Camera 1 URL and browser identity.
- [x] T005 Route the exact Camera 1 browser path to the proven H.264 output, bypassing VPS MediaMTX for Camera 1 playback.
- [x] T006 Keep AI inactive and prove live viewing does not depend on it.
- [x] T007 Obtain operator visual acceptance on mostdef.ru.
- [x] T008 Capture the accepted architecture and troubleshooting learning as SDD artifacts.

## Completion gate

- [x] Product outcome achieved: new Camera 1 is visibly playing on mostdef.ru.
- [x] Public Camera 1 identity preserved.
- [x] Accepted runtime architecture recorded in spec and plan.
- [x] Original MediaMTX browser-path assumption explicitly superseded rather than silently forgotten.
- [x] AI remains out of scope for this milestone.
- [ ] Generic one-setting camera onboarding is implemented; this is follow-up work and not required for the accepted Camera 1 milestone.
