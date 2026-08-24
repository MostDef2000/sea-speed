# Plan: Road live metadata overlay (Stage 3) + detector frequency research kit (Stage 4 prep)

- Issue: #301
- Specification: specs/053-road-live-metadata-overlay/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-053-001 | Category: TECH | Probability: 4 | Impact: 4 | Score: 16 | Mitigation: normalized envelope with generation/timestamp, immutable deepcopy, SSE bounded deque, canvas content-box transform | Validation: overlay + SSE + schema tests | Residual: 1 | Status: MITIGATED
- RISK-053-002 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: additive state, no URL/secret leak, Authentik-scoped SSE, exact private peer checks | Validation: contract tests | Residual: 1 | Status: MITIGATED
- RISK-053-003 | Category: TECH | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: deterministic benchmark kit with guards, redaction, stop rules | Validation: detector frequency tests | Residual: 1 | Status: MITIGATED

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

- TEST-053-001 | Covers: R1,R3 | Level: unit | Evidence: test_frontend_contract | COVERED
- TEST-053-002 | Covers: R2 | Level: unit | Evidence: test_api_contract | COVERED
- TEST-053-003 | Covers: R1,R4 | Level: unit | Evidence: test_worker_tracking_overlay + test_detection_runtime_optimization | COVERED
- TEST-053-004 | Covers: R1,R4 | Level: unit | Evidence: test_telemetry_contract + telemetry.schema | COVERED
- TEST-053-005 | Covers: R5 | Level: unit | Evidence: test_detector_frequency_benchmark | COVERED
- TEST-053-006 | Covers: runtime | Level: runtime-manual | Evidence: MIXED manifests + manual overlay | RUNTIME-MANUAL

## Correct-course check

- Trigger: NONE
- Impact: additive metadata overlay without changing model formulas.

## Runtime feedback

- None yet for this feature.

## Deployment transaction audit

- TX-053-001 ADMISSION FATAL no transport — autonomous log
- TX-053-002 PRE-MUTATION FATAL verify_source_protection fails
- TX-053-003 MUTATION CONDITIONAL previous serving — rerun — redeploy 5bda18f
- TX-053-004 VERIFICATION BEST-EFFORT runtime_verified false blocks DONE
- TX-053-005 STATE-COMMIT BEST-EFFORT exact-artifacts
- TX-053-006 HOUSEKEEPING BEST-EFFORT tmp stale
- TX-053-007 EVIDENCE FATAL audit missing blocks DONE
- TX-053-008 ROLLBACK FATAL failed rollback → BLOCKED
