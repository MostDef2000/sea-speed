# Tasks

Specification: specs/046-native-frame-quality/spec.md

## Delivery tasks

- [x] T001 Extend AnalyticsProfile with frame_width/frame_height and validate defaults via tests — AC-001, AC-002
- [x] T002 Make HLS reader frame size profile-aware (FRAME_WIDTH/HEIGHT env override) — AC-003
- [x] T003 Update ubuntu_worker_entrypoint to propagate frame size from profile/env — AC-003
- [x] T004 Extend passage best-frame logic with sharpness (Laplacian variance) — AC-004, AC-005
- [x] T005 Update worker.env.example defaults to 1920x1080 — AC-006
- [x] T006 Add/extend unit tests (analytics_profiles, frame quality, sharpness) — AC-001..AC-007
- [x] T007 Validate full test suite and SDD linkage — AC-007

## Requirements traceability

- AC-001 | Task: T001, T006 | Evidence: tests/test_analytics_profiles.py frame_width assertions for water-v1 | Coverage: COVERED
- AC-002 | Task: T001, T006 | Evidence: tests/test_analytics_profiles.py frame_width assertions for road-v1 | Coverage: COVERED
- AC-003 | Task: T002, T003, T006 | Evidence: tests/test_frame_quality.py FFmpeg scale filter construction via helper | Coverage: COVERED
- AC-004 | Task: T002, T004, T006 | Evidence: tests/test_frame_quality.py snapshots from HD frames | Coverage: COVERED
- AC-005 | Task: T004, T006 | Evidence: tests/test_frame_quality.py Laplacian variance synthetic sharp vs blur | Coverage: COVERED
- AC-006 | Task: T005, T006 | Evidence: tests/test_frame_quality.py worker.env.example assertion | Coverage: COVERED
- AC-007 | Task: T006, T007 | Evidence: existing passage/event tests still green at new resolution | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [x] Required CI green
- [x] Exact-green-head merge complete
- [x] Deployment state resolved
- [x] Runtime acceptance resolved
- [x] Deferred work recorded
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current

## Completion gate

- [x] Done

## Runtime feedback

To be recorded after Ubuntu Worker/relay deployment acceptance.
