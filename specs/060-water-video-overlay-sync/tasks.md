# Tasks: Water video overlay sync — clean HLS + timestamped AI canvas

- Issue: #316
- Specification: specs/060-water-video-overlay-sync/spec.md
- Plan: specs/060-water-video-overlay-sync/plan.md

## Requirements traceability

- AC-001 | Task: TASK-060-01 | Evidence: tests/test_worker_tracking_overlay.py, tests/test_road_overlay_sync.py | Coverage: COVERED
- AC-002 | Task: TASK-060-02 | Evidence: tests/test_api_contract.py, tests/test_sea_speed_auth_v1.py, tests/test_camera_preview_gallery.py | Coverage: COVERED
- AC-003 | Task: TASK-060-03 | Evidence: tests/test_frontend_contract.py, tests/test_road_overlay_sync.py | Coverage: COVERED

## Delivery tasks

1. Worker honest timing + water live envelope v2
2. API water live broker + HLS PDT + private ingress
3. Frontend Water sync polish + tests/schema
4. Validators + PR + CI + MIXED deploy + visual acceptance

## Task records

- TASK-060-01 | Worker honest timing + water v2 envelope — latest-complete-frame slot reuse, deep-immutable `sea_speed_water_live_v2` | AC-001 | Evidence: worker/ubuntu_worker_entrypoint.py, worker/hls_motion_yolo_worker_events.py, schemas/telemetry.schema.json | Status: PENDING
- TASK-060-02 | API water time binding + private ingress — exact POST /api/cam1/live, bearer, schema/size, sequence, SSE id/replay, rollover-proof + nginx allowlist | AC-002 | Evidence: api/app/main.py, scripts/operations/nginx_sea_speed_auth.py, tests/test_api_contract.py, tests/test_sea_speed_auth_v1.py | Status: PENDING
- TASK-060-03 | Frontend Water sync — PDT mapping, bounded history, requestVideoFrameCallback bracket-only, lag median, cleanPreviewVideo, stable passages | AC-003 | Evidence: frontend/sea-speed/index.html, tests/test_frontend_contract.py, tests/test_road_overlay_sync.py | Status: PENDING
- TASK-060-04 | Validation + deploy + acceptance — validators, CI and MIXED runtime | AC-001..AC-003 | Evidence: scripts/ci/validate_*.py, exact-artifacts, HLS PDT, p95/max skew | Status: PENDING

## Completion gate

- [ ] All tasks COMPLETE or RUNTIME-MANUAL
- [ ] Exact-head CI green
- [ ] Exact-main Quality green
- [ ] MIXED runtime_verified (p95 ≤150ms, max ≤250ms)

## Definition of Done

- [ ] Issue/spec/plan/tasks current and linked
- [ ] Exact changed-file scope verified and matches Change Contract
- [ ] Required tests and evidence complete
- [ ] Required CI green (Repository validation + quality-integration)
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (VPS+Ubuntu runtime_verified)
- [ ] Runtime acceptance resolved (Water synchronized clean HLS + AI canvas, stable passages)
- [ ] Deferred work recorded (none)
- [ ] Risks resolved or explicitly accepted (REQUIRED documented)
- [ ] Waivers resolved or current (none expected)
