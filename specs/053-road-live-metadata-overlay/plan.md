# Plan: Road live metadata overlay (Stage 3) + detector frequency research kit (Stage 4 prep)

- Issue: #301
- Specification: specs/053-road-live-metadata-overlay/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-053-001 | Category: TECH | Probability: 4 | Impact: 4 | Score: 16 | Mitigation: normalized envelope with generation/timestamp, immutable deepcopy, SSE bounded deque, canvas content-box transform | Validation: overlay + SSE + schema tests | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-053-002 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: additive state, no URL/secret leak, Authentik-scoped SSE, exact private peer checks | Validation: contract tests | Residual risk: 1 | Owner: api | Status: MITIGATED
- RISK-053-003 | Category: TECH | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: deterministic benchmark kit with guards, redaction, stop rules | Validation: detector frequency tests | Residual risk: 1 | Owner: worker | Status: MITIGATED

## Architecture

- Frontend: clean HLS video + dedicated overlay canvas, SSE client, generation-aware interpolation TTL 1s, object-fit content-box math.
- API: /api/analytics/road1/live SSE, bounded deque (120), worker POST /internal/road1/live, validation via telemetry schema.
- Worker: immutable envelope builder, generation from start mono, publishes via queue, worker commit injected.
- Research kit: schemes + scripts/worker benchmark + matrix json, no runtime mutation.

## Decisions

- D1: SSE not WebSocket; stays within existing Authentik HTTP contract.
- D2: Absolute Honest observed_mono, not camera PTS (truthful).
- D3: Stage4 stays research artifact, no production cadence change.

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: REQUIRED

## Validation

- Unit: frontend transform/interpolation/TTL, API SSE contract, worker envelope immutability, schema.
- Integration: SSE live, generation bump.
- Runtime-manual: smooth overlay, staleness, resize/fullscreen, 8 env/s at 10 FPS.

## Test design

- TEST-053-001 | Covers: R1,R3 | Level: unit | Priority: P0 | Evidence: test_frontend_contract | Coverage: COVERED
- TEST-053-002 | Covers: R2 | Level: unit | Priority: P0 | Evidence: test_api_contract | Coverage: COVERED
- TEST-053-003 | Covers: R1,R4 | Level: unit | Priority: P0 | Evidence: test_worker_tracking_overlay + test_detection_runtime_optimization | Coverage: COVERED
- TEST-053-004 | Covers: R1,R4 | Level: unit | Priority: P0 | Evidence: test_telemetry_contract + telemetry.schema | Coverage: COVERED
- TEST-053-005 | Covers: R5 | Level: unit | Priority: P0 | Evidence: test_detector_frequency_benchmark | Coverage: COVERED
- TEST-053-006 | Covers: runtime | Level: runtime-manual | Priority: P1 | Evidence: MIXED manifests + manual overlay | Coverage: RUNTIME-MANUAL | Reason: protected hardware check

## Correct-course check

- Trigger: NONE
- Issue impact: additive live overlay and research kit, no model change
- Specification impact: new envelope/SSE/browser alignment and benchmark schema
- Plan impact: adds MIXED SSE path and research harness
- Tasks impact: AC-001..AC-004 → TASK-053-01..TASK-053-05
- Authorization impact: NONE — initial SDD for src-auth-053
- Follow-up: keep Stage4 production frequency bump separate

## Runtime feedback

- None yet for this feature.

## Deployment transaction audit

- TX-053-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-053-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-053-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous serving | Retry: rerun contour | Rollback: redeploy 5bda18f | Evidence: deployment-manifest MIXED runtime_verified
- TX-053-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: 5bda18f | Evidence: manifest + overlay checks
- TX-053-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-053-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-053-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-053-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy 5bda18f | Rollback: itself | Evidence: rollbackTarget hash
