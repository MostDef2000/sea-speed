# Plan: ROI persistence and measured fresh-frame detection cadence

- Issue: #299
- Specification: specs/052-roi-persistence-detection-cadence/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-052-001 | Category: TECH | Probability: 4 | Impact: 3 | Score: 12 | Mitigation: split frontend draft/persisted ROI state, verify POST with subsequent GET before Saved, keep draft with explicit unsaved marker on failure | Validation: frontend contract + persistence roundtrip tests | Residual risk: 1 | Owner: frontend | Status: MITIGATED
- RISK-052-002 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: make ROI load independent of speed-config/speed-lines loads and distinguish corrupt JSON from absent ROI without silent disabled fallback | Validation: load-independence + malformed-file tests | Residual risk: 1 | Owner: api/frontend | Status: MITIGATED
- RISK-052-003 | Category: TECH | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: point VPS migration at the real production data path, fix heredoc syntax and global-counter side effect, migrate per-file with atomic replacement | Validation: executed migration harness + atomicity test | Residual risk: 1 | Owner: deploy/vps | Status: MITIGATED
- RISK-052-004 | Category: TECH | Probability: 4 | Impact: 4 | Score: 16 | Mitigation: replace partial-read frame drain with verified complete-frame latest-slot primitive, enforce backlog bounds with deterministic drop accounting | Validation: queue-level unit tests including partial/corrupt frame and staleness cases | Residual risk: 2 | Owner: worker | Status: MITIGATED
- RISK-052-005 | Category: TECH | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: redesign telemetry to count decoded/inferred/published separately, fix double-counted effective_fps and non-sourced age | Validation: deterministic timing harness tests | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-052-006 | Category: TECH | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: keep outbound publication off ordered inference loop, preserve frame/metadata/crossing snapshot consistency, bound JPEG work | Validation: critical-path isolation tests + snapshot immutability tests | Residual risk: 2 | Owner: worker | Status: MITIGATED
- RISK-052-007 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: isolate Road cadence configuration from Water preserved config and validate bounded 1..15 FPS range | Validation: profile/config tests including preserved-value scenarios | Residual risk: 1 | Owner: worker/deploy | Status: MITIGATED
- RISK-052-008 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: document honest benchmark handling when sustained ≥10 FPS is not achievable on the current GPU/load profile | Validation: runtime benchmark report review | Residual risk: 1 | Owner: docs/runtime | Status: MITIGATED

## Architecture

### Stage 1 — ROI persistence

- `frontend/sea-speed/road/index.html` — introduce `draftRoiPoints` vs `persistedRoiPoints`, explicit UI states, `saveRoi()` must perform POST then reload verification before transitioning to Saved, failed save retains Draft with visible unsaved indicator. Config loads for ROI, speed factor and speed lines become independent; `Promise.all` failure in one section must not suppress successful ROI response. No localStorage persistence.
- `api/app/main.py` — ensure ROI write path is atomic `tmp + os.replace`, keep normalized geometry primary, expose distinct error signaling for malformed JSON vs absent file, preserve compatibility for normalized and legacy absolute coordinates.
- `deploy/vps/deploy.sh` — correct migration base path to `/opt/sea-speed-api/data`, repair embedded Python migration (`_migrate_normalized_points` heredoc and string termination), replace global `migrated` accumulation with per-file tracking, preserve atomic file semantics and verify with execution tests against production layout.
- `worker/hls_motion_yolo_worker_events.py` + `worker/ubuntu_worker_entrypoint.py` + `deploy/worker/ubuntu/configure-analytics-profiles.py` — verify derived Road ROI fetch URL (`SEA_SPEED_API_URL` → `/roi`) and polling cadence without introducing production secrets.

### Stage 2 — cadence foundation

- `worker/ubuntu_worker_entrypoint.py` — replace current `select` + partial-read drain with a verified complete-frame latest-slot primitive that blocks until exactly one logical frame is available, swaps only complete frames, supports deterministic drop/coalesce counters and preserves source ingest time/PTS.
- `worker/detection_performance.py` — stop double-counting `record_frame`/`record_inference` on the same FPS bucket, use the correct `ingest_mono` timestamp, add stage timers and expose separate decoded/inferred/processed/published counters plus source age.
- `worker/ubuntu_worker_entrypoint.py` + `worker/ubuntu_ai_inference_worker.py` + `worker/hls_motion_yolo_worker_events.py` — ensure JPEG generation and outbound state/event/crossing HTTP are not synchronous blockers on the ordered inference traversal; maintain one consistent per-frame snapshot for frame + detections + crossings + metadata.
- `worker/hls_motion_yolo_worker_events.py` — cache ROI mask by ROI signature and avoid redundant full-HD mask allocation on unchanged ROI; decouple publish interval semantics from per-frame inference encoding where appropriate.
- `worker/analytics_profiles.py` + `deploy/worker/ubuntu/configure-analytics-profiles.py` + `deploy/worker/ubuntu/road-worker.env.example` — keep Road cadence configuration owned by Road protected values, validate 1..15 FPS explicitly, do not silently inherit Water preserved `SAMPLE_FPS`/`YOLO_HALF`/class-filter values.
- `schemas/telemetry.schema.json` + `deploy/worker/ubuntu/observed-worker-runner.py` + `deploy/worker/ubuntu/check-worker-health.py` — surface corrected stage/telemetry fields so quality and health evidence can actually report them.

### Common

- Strictly no change to YOLO model/weights, `imgsz`, confidence thresholds, class allowlist semantics, ByteTrack/crossing/calibration/speed formulas, or API object/event schema.

## Decisions

- D1: ROI Saved is a verified server fact, not a local browser draft.
- D2: ROI loads are independent; one failed Road config section must not prevent another section from applying.
- D3: VPS migration correctness is part of this MIXED change because prior migration had production-path and syntax defects distinct from normal save flow.
- D4: One logical frame at a time replaces the variable-length raw-bytes drain loop.
- D5: Telemetry correctness precedes any tuning; no optimization claim depends on broken FPS/age counters.
- D6: Keep outbound transport off the ordered inference critical path, but never publish partial or snapshot-inconsistent state.

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: REQUIRED

## Validation

- Unit: ROI roundtrip + draft/error + independent-load tests, migration execution tests, frame-queue correctness tests, telemetry counter tests, critical-path isolation tests, cadence config tests.
- Integration: API file/contract tests, telemetry/health contract tests, tracker/overlay lineage tests at unit level.
- Runtime-manual: VPS ROI reload + restart + worker propagation check; Ubuntu fresh-frame + benchmark reporting check; browser reload check.

## Test design

- TEST-052-001 | Covers: AC-001, AC-002, R1 | Level: unit | Priority: P0 | Evidence: `test_frontend_contract` + `test_api_contract` — draft vs persisted states, POST→GET verification, unsaved indicator, failed save retains draft | Coverage: COVERED
- TEST-052-002 | Covers: AC-002, R2 | Level: unit | Priority: P0 | Evidence: `test_frontend_contract` — ROI loads even when speed-config/speed-lines GET fails | Coverage: COVERED
- TEST-052-003 | Covers: AC-003, R3 | Level: unit | Priority: P0 | Evidence: `test_roi_normalization` / `test_api_contract` — malformed JSON distinct from absent ROI | Coverage: COVERED
- TEST-052-004 | Covers: AC-004, R4 | Level: unit | Priority: P0 | Evidence: `test_vps_deploy_transaction` — migration targets `/opt/sea-speed-api/data`, per-file atomic behavior, normalized-file preservation | Coverage: COVERED
- TEST-052-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: worker poll / restart propagation test + VPS→Worker runtime check | Coverage: COVERED
- TEST-052-006 | Covers: AC-006, R6, NFR-052-004 | Level: unit | Priority: P0 | Evidence: `test_detection_runtime_optimization` — verified complete-frame latest slot, no partial consumption, bounded backlog, deterministic drops | Coverage: COVERED
- TEST-052-007 | Covers: AC-007, R7 | Level: unit | Priority: P0 | Evidence: `test_detection_runtime_optimization` + `test_ubuntu_worker_observability` + `test_telemetry_contract` — split decoded/inferred/published FPS without double counting | Coverage: COVERED
- TEST-052-008 | Covers: AC-008, R8 | Level: unit | Priority: P0 | Evidence: `test_detection_runtime_optimization` + `test_worker_tracking_overlay` — JPEG/HTTP off critical ordered path while snapshot consistency holds | Coverage: COVERED
- TEST-052-009 | Covers: AC-009, R9 | Level: unit | Priority: P0 | Evidence: `test_analytics_profiles` + `test_ubuntu_worker_ai_supervision` — Road cadence independent of preserved Water config | Coverage: COVERED
- TEST-052-010 | Covers: AC-010, R10 | Level: runtime-manual | Priority: P1 | Evidence: protected runtime benchmark Road-only and Water+Road at 5/10/15 FPS with honest ceiling | Coverage: RUNTIME-MANUAL | Reason: protected hardware benchmark
- TEST-052-011 | Covers: AC-011 | Level: unit | Priority: P0 | Evidence: full discovery + validators + MIXED deployment manifests/health | Coverage: COVERED

## Correct-course check

- Adjacent-stage review: COMPLETE — frontend ROI persistence, API durable storage, VPS migration execution path, Worker frame ingress/telemetry/critical-path, protected cadence configuration, benchmark scope.
- Trigger: NONE
- Issue impact: repairs Road ROI persistence, honest FPS/age/queue telemetry and fresh-frame cadence foundation without promising 25–30 FPS inference.
- Specification impact: introduces draft/persisted ROI semantics, explicit production-path migration execution, latest-slot transport and separated telemetry semantics.
- Plan impact: adds MIXED transaction footprint with pre-mutation/mutation/verification separation for ROI vs pipeline stages.
- Tasks impact: traceability AC-001..AC-011 → TASK-052-01..TASK-052-05.
- Authorization impact: NONE — this is the initial SDD for src-auth-052.
- Follow-up: keep stage 3 metadata overlay and optional performance follow-ons separate.

## Runtime feedback

- None yet for this feature.

## Deployment transaction audit

Required: runtime deployment REQUIRED (MIXED).

- TX-052-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-052-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-052-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous VPS/Worker serving | Retry: rerun contour | Rollback: redeploy 696e5e3 | Evidence: deployment-manifest MIXED runtime_verified
- TX-052-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: 696e5e3 | Evidence: manifest + ROI reload + freshness checks
- TX-052-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-052-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-052-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-052-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy 696e5e3 | Rollback: itself | Evidence: rollbackTarget hash
