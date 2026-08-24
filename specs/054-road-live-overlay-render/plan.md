# Plan: Stage 3 visual finish — live canvas rendering from SSE

- Issue: #303
- Specification: specs/054-road-live-overlay-render/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-054-001 | Category: TECH | Probability: 4 | Impact: 4 | Score: 16 | Mitigation: immutable envelope, bounded SSE deque, content-box math, TTL/generation discard | Validation: overlay + SSE tests | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-054-002 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: Authentik SSE, no secret leak, additive state | Validation: contract tests | Residual risk: 1 | Owner: api | Status: MITIGATED
- RISK-054-003 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: interpolation only between fresh, fallback overlay.jpg | Validation: frontend contract | Residual risk: 1 | Owner: frontend | Status: MITIGATED

## Architecture

- Worker: build_road_live_envelope deepcopied, generation from monotonic, publish via queue POST to API live endpoint, no blocking.
- API: deque 120, validate envelope, SSE stream with reconnection, no disk write.
- Frontend: liveOverlayCanvas, EventSource, content-box transform, interpolate, TTL 1s, generation/out-of-order discard, fallback.

## Decisions

- D1: SSE not WS, stays in Authentik HTTP.
- D2: Absolute honest observed_mono.
- D3: Interpolation only, no prediction.

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: REQUIRED

## Validation

- Unit: envelope immutability, SSE contract, canvas transform/TTL, telemetry schema.
- Integration: live SSE generation bump.
- Runtime-manual: smooth overlay, stale clear, resize/fullscreen, 8 env/s.

## Test design

- TEST-054-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: test_worker_tracking_overlay | Coverage: COVERED
- TEST-054-002 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: test_api_contract | Coverage: COVERED
- TEST-054-003 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: test_frontend_contract | Coverage: COVERED
- TEST-054-004 | Covers: AC-001, AC-003 | Level: unit | Priority: P0 | Evidence: test_telemetry_contract | Coverage: COVERED
- TEST-054-005 | Covers: AC-002 | Level: runtime-manual | Priority: P1 | Evidence: MIXED manifests + manual overlay | Coverage: RUNTIME-MANUAL | Reason: protected hardware visual

## Correct-course check

- Trigger: NONE
- Issue impact: wires live path to visible smooth overlay
- Specification impact: adds live envelope/SSE/canvas semantics
- Plan impact: adds MIXED live streaming footprint
- Tasks impact: AC-001..AC-003 → TASK-054-01..TASK-054-03
- Authorization impact: NONE — initial for src-auth-054
- Follow-up: Stage4 frequency benchmark separate

## Runtime feedback

- None yet for this feature.

## Deployment transaction audit

- TX-054-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-054-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-054-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous serving | Retry: rerun contour | Rollback: redeploy 9eebc5c | Evidence: deployment-manifest MIXED runtime_verified
- TX-054-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: 9eebc5c | Evidence: manifest + overlay checks
- TX-054-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-054-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-054-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-054-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy 9eebc5c | Rollback: itself | Evidence: rollbackTarget hash
