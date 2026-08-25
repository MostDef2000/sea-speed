# Plan: Road video overlay sync — clean HLS + timestamped AI canvas

- Issue: #312
- Specification: specs/058-road-video-overlay-sync/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-058-001 | Category: TECH | Probability: 4 | Impact: 4 | Score: 16 | Mitigation: honest worker-receive timestamp at FFmpeg reader boundary, latest-complete-frame slot (producer drains partial bytes), immutable v2 envelope, sequence-aware SSE | Validation: worker frame-slot + envelope immutability tests | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-058-002 | Category: TECH | Probability: 4 | Impact: 4 | Score: 16 | Mitigation: private exact-path `POST /api/analytics/road1/live` allowlist + `require_auth()` + full schema/size validation + bounded `deque(maxlen=120)` + monotonic `live_seq` | Validation: api/auth contract tests, size/generation tests | Residual risk: 1 | Owner: api | Status: MITIGATED
- RISK-058-003 | Category: TECH | Probability: 4 | Impact: 4 | Score: 16 | Mitigation: VPS preview FFmpeg adds `program_date_time` without changing encode, internal `/api/.../stream` route consistent with nginx `proxy_pass /sea-speed/api/ -> /api/` contract, SSE `id:` replay survives deque rollover | Validation: HLS PDT + SSE rollover tests | Residual risk: 1 | Owner: vps | Status: MITIGATED
- RISK-058-004 | Category: TECH | Probability: 4 | Impact: 4 | Score: 16 | Mitigation: browser PDT→media-UTC mapping (`hls.playingDate`/`getStartDate`), bounded >15s history, `requestVideoFrameCallback` bracket-only interpolation same-generation same-track, fail-closed clear | Validation: Node-backed overlay sync math tests + synthetic jitter/worker-restart scenarios | Residual risk: 1 | Owner: frontend | Status: MITIGATED
- RISK-058-005 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: clean HLS remains sole media stream, no second encoder/relay, canvas fallback preserves state JPEG when no video | Validation: frontend/roi/preview integration tests | Residual risk: 1 | Owner: frontend | Status: MITIGATED

## Architecture

- Worker: `ubuntu_worker_entrypoint.py` — reader thread + max-size-one latest complete-frame slot with `capture_time_unix_ms`/`ingest_monotonic`; `hls_motion_yolo_worker_events.py` — carry capture time through inference, build `sea_speed_road_live_v2` deep-immutable, queue(1) coalesce, bearer POST to `SEA_SPEED_LIVE_API_URL` or derived `/live`.
- API: `api/app/main.py` — `POST /api/analytics/road1/live` (exact private, bearer), validated, receipt timestamp + live_seq; `GET /api/analytics/road1/live/stream` internal SSE with `id:` + keepalive + bounded replay; preview FFmpeg `+program_date_time` keeps GOP/fMP4/TTL.
- Frontend: `frontend/sea-speed/road/index.html` — `liveOverlayCanvas` buffers by media UTC, `hls.js@1.5.7` pinned, `playingDate` mapping, `requestVideoFrameCallback` bracket search + bounded-gap interpolation, ±1px content-box, stale/TTL fail-closed.
- Boundary: `scripts/operations/nginx_sea_speed_auth.py` — add only exact `POST /api/analytics/road1/live` to `WORKER_PRIVATE_ENDPOINTS`, keep `limit_except`, `proxy_set_header Authorization`, global deny-all fallback.
- Schema: `schemas/telemetry.schema.json` + `scripts/ci/validate_telemetry.py` — add v2 timing/schema contract.

## Decisions

- D1: Retain one existing clean HLS stream; do not introduce annotated video stream (scope/minimal jitter).
- D2: Honest `worker_receive_utc` (worker receipt/decode), not camera exposure PTS — truthful and measurable.
- D3: Browser is synchronization authority via PDT media timeline, not arrival time; never extrapolate.
- D4: SSE uses monotonic sequence, not `len(deque)`, to survive rollover.

## Affected contours

- VPS: REQUIRED (API live broker/auth, HLS PDT, frontend sync, private nginx reconciliation)
- Ubuntu Worker/relay: REQUIRED (frame slot timing + v2 envelope, Road worker restart)
- MediaMTX relay: NOT REQUIRED (existing clean `preview_road1` preserved)

## Validation

- Unit: worker frame-slot/complete-frame, envelope immutability, auth exact-path, SSE sequence/rollover, HLS PDT flag, frontend bracket/TTL/alignment.
- Integration: synthetic Road source with burned UTC counter, deterministic moving box, jitter/SSE-reconnect/HLS-reconnect/worker-restart/queue-rollover injection.
- Runtime-manual: MIXED deployment, visual p95/max skew, resize/fullscreen/DPR, worker-stop clears canvas, preview-stop unchanged, Water unchanged.

## Test design

- TEST-058-001 | Covers: R1,R2 | Level: unit | Priority: P0 | Evidence: tests/test_worker_tracking_overlay.py, tests/test_detection_runtime_optimization.py | Coverage: COVERED
- TEST-058-002 | Covers: R3 | Level: unit | Priority: P0 | Evidence: tests/test_api_contract.py | Coverage: COVERED
- TEST-058-003 | Covers: R3,R4 | Level: unit | Priority: P0 | Evidence: tests/test_sea_speed_auth_v1.py | Coverage: COVERED
- TEST-058-004 | Covers: R2,R5,R6 | Level: unit | Priority: P0 | Evidence: tests/test_road_overlay_sync.py (Node 22) | Coverage: COVERED
- TEST-058-005 | Covers: R2,R6 | Level: unit | Priority: P0 | Evidence: tests/test_telemetry_contract.py, schemas/telemetry.schema.json | Coverage: COVERED
- TEST-058-006 | Covers: R5,R6 | Level: unit | Priority: P0 | Evidence: tests/test_frontend_contract.py | Coverage: COVERED
- TEST-058-007 | Covers: runtime | Level: runtime-manual | Priority: P1 | Evidence: MIXED manifests + manual overlay sync + p95/max metrics | Coverage: RUNTIME-MANUAL | Reason: protected hardware/media clocks

## Correct-course check

- Trigger: NONE
- Issue impact: additive Road live overlay sync without second stream
- Specification impact: new v2 envelope/HLS PDT/browser PDT-bracket contract
- Plan impact: adds MIXED timestamp-bound rendering + exact private ingress
- Tasks impact: AC-001..AC-004 → TASK-058-01..TASK-058-05
- Authorization impact: NONE — initial SDD for src-auth-058
- Follow-up: keep detector frequency benchmark separate

## Runtime feedback

- Prior: #305 MIXED runtime_verified proves clean HLS + relay deploy; overlay acceptance failed due to live 404 and arrival-time interpolation.

## Deployment transaction audit

- TX-058-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-058-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-058-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous serving | Retry: rerun contour | Rollback: redeploy f7a5ecc | Evidence: deployment-manifest MIXED runtime_verified
- TX-058-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: f7a5ecc | Evidence: manifest + HLS PDT + SSE sequence + canvas skew metrics
- TX-058-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-058-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-058-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-058-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy f7a5ecc | Rollback: itself | Evidence: rollbackTarget hash
