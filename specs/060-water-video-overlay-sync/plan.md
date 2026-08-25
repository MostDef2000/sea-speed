# Plan: Water video overlay sync — clean HLS + timestamped AI canvas

- Issue: #316
- Specification: specs/060-water-video-overlay-sync/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-060-001 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: water honest capture_time via same FIONREAD drain, v2 envelope, median lag compensation 0..600ms, fail-closed | Validation: sync math unit tests | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-060-002 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: exact private POST /api/cam1/live allowlist + Bearer auth + schema validation | Validation: auth contract tests | Residual risk: 1 | Owner: api | Status: MITIGATED
- RISK-060-003 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: water frontend duplicate HLS instance + PDT bracket interpolation + stable passages | Validation: frontend contract tests | Residual risk: 1 | Owner: frontend | Status: MITIGATED

## Architecture

- Worker: same `ubuntu_worker_entrypoint` FIONREAD drain, `hls_motion_yolo_worker_events` adds `sea_speed_water_live_v2` for water domain (capture_time/process_time) alongside road, queue(1) coalesce, bearer POST to `/api/cam1/live` derived or `SEA_SPEED_LIVE_API_URL` override
- API: `POST /api/cam1/live` exact private, Bearer, schema/size, `live_seq`, SSE `id:` replay, HLS `program_date_time` already present for cam1 preview (reuse)
- Frontend: `frontend/sea-speed/index.html` mirrors Road 059 polish: 15s buffer, playingDate/requestVideoFrameCallback, median lag, cleanPreviewVideo duplicate, passages stable from hi
- Boundary: `scripts/operations/nginx_sea_speed_auth.py` add exact `POST /api/cam1/live` to `WORKER_PRIVATE_ENDPOINTS`
- Schema: `schemas/telemetry.schema.json` add waterLiveEnvelope v2 + `validate_telemetry --kind water_live`

## Decisions

- D1: Reuse Road 058/059 pattern for Water — same honest timestamp, same PDT sync, no second encode
- D2: Separate live streams for road (`/api/analytics/road1/live`) and water (`/api/cam1/live`) to keep domains isolated
- D3: Frontend-only lag compensation clamped 0..600ms, fail-closed

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: REQUIRED

## Validation

- Unit: water frame-slot, envelope immutability, auth exact-path, SSE rollover, frontend bracket/lag/cleanPreview/passages
- Runtime-manual: Water main p95/max skew, clean preview both cards, Battery: Road no regression

## Test design

- TEST-060-001 | Covers: R1 | Level: unit | Priority: P0 | Evidence: tests/test_worker_tracking_overlay.py | Coverage: COVERED
- TEST-060-002 | Covers: R2 | Level: unit | Priority: P0 | Evidence: tests/test_api_contract.py, tests/test_sea_speed_auth_v1.py | Coverage: COVERED
- TEST-060-003 | Covers: R3 | Level: unit | Priority: P0 | Evidence: tests/test_road_overlay_sync.py, tests/test_frontend_contract.py | Coverage: COVERED
- TEST-060-004 | Covers: runtime | Level: runtime-manual | Priority: P1 | Evidence: MIXED manifests + visual | Coverage: RUNTIME-MANUAL | Reason: protected hardware/media clocks

## Correct-course check

- Trigger: NONE
- Issue impact: additive Water sync without affecting Road DONE 9312544
- Specification impact: new water v2 envelope + HLS PDT + PDT-bracket contract
- Plan impact: adds MIXED Water rendering + exact private ingress
- Tasks impact: AC-001..AC-003 → TASK-060-01..03
- Authorization impact: NONE — initial SDD for src-auth-060
- Follow-up: keep detector frequency benchmark separate

## Runtime feedback

- Road 058/059 MIXED verified; Water needs same transfer.

## Deployment transaction audit

- TX-060-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-060-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-060-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous serving | Retry: rerun contour | Rollback: redeploy 9312544 | Evidence: deployment-manifest MIXED runtime_verified
- TX-060-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: 9312544 | Evidence: manifest + HLS PDT + SSE + canvas skew
- TX-060-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-060-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-060-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-060-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy 9312544 | Rollback: itself | Evidence: rollbackTarget hash
