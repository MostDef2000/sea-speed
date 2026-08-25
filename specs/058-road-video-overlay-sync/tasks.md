# Tasks: Road video overlay sync — clean HLS + timestamped AI canvas

- Issue: #312
- Specification: specs/058-road-video-overlay-sync/spec.md
- Plan: specs/058-road-video-overlay-sync/plan.md

## Requirements traceability

- AC-001 | Task: TASK-058-01, TASK-058-02 | Evidence: tests/test_worker_tracking_overlay.py, tests/test_detection_runtime_optimization.py, tests/test_telemetry_contract.py | Coverage: COVERED
- AC-002 | Task: TASK-058-03 | Evidence: tests/test_api_contract.py, tests/test_sea_speed_auth_v1.py | Coverage: COVERED
- AC-003 | Task: TASK-058-03 | Evidence: tests/test_api_contract.py, tests/test_sea_speed_auth_v1.py, tests/test_camera_preview_gallery.py | Coverage: COVERED
- AC-004 | Task: TASK-058-04 | Evidence: tests/test_road_overlay_sync.py, tests/test_frontend_contract.py | Coverage: COVERED

## Delivery tasks

1. Worker honest frame timing + live envelope v2
2. API authenticated bounded SSE + HLS program_date_time
3. Private nginx exact-path live ingress
4. Browser timestamp-synchronized canvas + tests/schema
5. Validators + PR + CI + MIXED deploy + runtime visual acceptance

## Task records

- TASK-058-01 | Worker honest timing + v2 envelope — latest-complete-frame slot with capture_time_unix_ms, deep-immutable `sea_speed_road_live_v2` | AC-001 | Evidence: worker/ubuntu_worker_entrypoint.py, worker/hls_motion_yolo_worker_events.py, worker/analytics_profiles.py, schemas/telemetry.schema.json, tests/test_worker_tracking_overlay.py | Status: PENDING
- TASK-058-02 | API HLS time binding — preview FFmpeg program_date_time, no encode change | AC-003 | Evidence: api/app/main.py, tests/test_camera_preview_gallery.py | Status: PENDING
- TASK-058-03 | API live broker + auth + private ingress — exact POST, bearer, schema/size, sequence, SSE id/replay, rollover-proof + nginx allowlist | AC-002, AC-003 | Evidence: api/app/main.py, scripts/operations/nginx_sea_speed_auth.py, tests/test_api_contract.py, tests/test_sea_speed_auth_v1.py | Status: PENDING
- TASK-058-04 | Browser synchronized overlay — PDT mapping, bounded history, requestVideoFrameCallback bracket-only interpolation, fail-closed, ±1px | AC-004 | Evidence: frontend/sea-speed/road/index.html, tests/test_frontend_contract.py, tests/test_road_overlay_sync.py | Status: PENDING
- TASK-058-05 | Validation + deploy + acceptance — validators, CI and MIXED runtime | AC-001..AC-004 | Evidence: scripts/ci/validate_*.py, scripts/quality/*.py, exact-artifacts, HLS PDT, p95/max skew metrics | Status: PENDING

## Completion gate

- [ ] All tasks COMPLETE or RUNTIME-MANUAL
- [ ] Exact-head CI green
- [ ] Exact-main Quality green
- [ ] MIXED runtime_verified (p95 ≤150ms, max ≤250ms)

## Definition of Done

- [ ] Issue/spec/plan/tasks current and linked
- [ ] Exact changed-file scope verified and matches Change Contract
- [ ] Required tests and evidence complete (including test_road_overlay_sync Node-backed sync math)
- [ ] Required CI green (Repository validation + quality-integration)
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (VPS+Ubuntu runtime_verified)
- [ ] Runtime acceptance resolved (synchronized clean HLS + AI canvas, no duplicate, ±1px, stale-clear)
- [ ] Deferred work recorded (detector frequency benchmark separate)
- [ ] Risks resolved or explicitly accepted (REQUIRED documented)
- [ ] Waivers resolved or current (none expected)
