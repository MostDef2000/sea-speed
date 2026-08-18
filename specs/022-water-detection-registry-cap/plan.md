# Implementation Plan: Water detection activation and registry cap

- Specification: specs/022-water-detection-registry-cap/spec.md
- Issue: #212
- Status: Implementing

## Architecture

The shared Worker remains one executable path with explicit analytics profiles. The remediation introduces a profile-aware admission point inside `worker/hls_motion_yolo_worker_events.py`:

- `water-v1`: run YOLO on every sampled ROI-bounded frame at the existing 5 FPS; retain motion computation only for telemetry; do not use motion boxes as a Water detection filter.
- `road-v1`: preserve the existing motion-active gate, motion-box overlap filter, speed calculation and event readiness logic.

Water event admission becomes track-oriented rather than speed-oriented. A normalized `vessel` with a ByteTrack ID is eligible once per active track. The existing `_track_states[event_posted]` state is reused; successful transport marks the track posted, while failed transport leaves it retryable. Speed data may still be attached to Water events when available but is not an admission prerequisite.

No API, storage, camera source, model binary, ROI editor or deployment implementation changes are required. The resulting executable source release applies to the Ubuntu Worker/relay contour only.

## Decisions

- D-001: Branch policy by `profile.domain`, because `water-v1` and `road-v1` already expose stable domain identity and no profile-schema change is necessary.
- D-002: Keep the current ROI-masked processing frame as the single inference input for both profiles so continuous Water inference cannot expand outside the configured ROI.
- D-003: Keep `MotionDetector.process()` unchanged. Water still reports `motion_now`/`motion_area`, while motion no longer controls Water inference or Water detection acceptance.
- D-004: Keep Road code on the existing legacy path, including `filter_detections_by_motion`, speed-line readiness and minimum pixel-speed/cooldown behavior.
- D-005: Require a non-null ByteTrack ID before Water event emission; do not generate event identity for an untracked detection.
- D-006: Reuse the existing per-track `event_posted` state to enforce one successful Water event per active track.
- D-007: Preserve YOLO26x weights, `conf=0.15`, `imgsz=960`, `bytetrack.yaml`, `SAMPLE_FPS=5.0` and `boat -> vessel` semantics unchanged.
- D-008: Treat continuous 5-FPS Water inference as a production performance risk requiring post-merge exact-SHA Ubuntu acceptance on the RTX 5070.
- D-009: The old production authorization for `9e0cd96...` does not authorize this remediation release. A new exact merged SHA requires a new production safety envelope.

## Affected contours

- VPS: NOT REQUIRED — no `api/**`, `frontend/**` or `deploy/vps/**` path changes are authorized.
- Ubuntu Worker/relay: REQUIRED — `worker/hls_motion_yolo_worker_events.py` is executable Ubuntu Worker source and changes Water inference/event admission behavior.
- Windows Worker: retired; NOT APPLICABLE.
- Runtime execution capability: Ubuntu remains `ONE_COMMAND_FALLBACK` unless current governance independently proves restricted Connector transport at release time.
- Operator actions expected: 1 when Ubuntu remains `ONE_COMMAND_FALLBACK`.

## Validation

Source validation requires exact six-path scope against authorization base `f3febcd6d9ae6a57e052f6b4a50bf3ec9f75fdf1`, deterministic focused Water/Road tests, existing analytics/ROI/API contract suites, SDD validation, PR Validation and aggregate Quality on one exact head, fresh base/head/scope/review admission, expected-head merge and exact-main post-merge Quality.

No runtime mutation is part of source validation. After a separate exact-SHA production decision, Ubuntu acceptance must prove exact source/profile/model identity, running Water service, advancing frames/state, continuous AI activity at the configured sample cadence, acceptable GPU/service health, preserved Road desired state, and a real naturally occurring vessel producing Water detections/tracks plus one persisted `vessel` event.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: isolate continuous inference to `profile.domain == water`; keep Road on the unchanged motion branch; add focused profile-policy tests | Validation: `tests/test_water_detection_pipeline.py` plus existing Road/ROI tests | Residual risk: shared Worker refactoring could accidentally couple profile branches | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: PERF | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: retain existing 5 FPS sample rate and exact YOLO parameters; require sustained RTX 5070 runtime acceptance before DONE | Validation: Ubuntu service/GPU/telemetry evidence under separately authorized release | Residual risk: scene complexity may increase per-frame inference load | Owner: Delivery Orchestrator | Status: OPEN
- RISK-003 | Category: BUS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: require ByteTrack ID and one successful event per active Water track | Validation: deterministic event-candidate tests and live natural-vessel acceptance | Residual risk: tracker ID churn can create a later distinct event for the same physical vessel | Owner: Delivery Orchestrator | Status: ACCEPTED
- RISK-004 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: fresh exact-SHA production authorization, exact-release deployment, rollback to prior accepted Worker release, preserve Road desired state | Validation: production admission plus deployment/runtime evidence | Residual risk: runtime rollback cannot retroactively remove a legitimate event already stored | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: unit | Priority: P0 | Evidence: `tests/test_water_detection_pipeline.py` continuous Water inference and no-motion-filter tests
- TEST-002 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: existing `tests/test_worker_roi_pipeline.py`
- TEST-003 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: `tests/test_water_detection_pipeline.py` Road inactive/active motion policy test
- TEST-004 | Covers: AC-005,AC-006 | Level: unit | Priority: P0 | Evidence: `tests/test_water_detection_pipeline.py` tracked-vessel event candidate tests
- TEST-005 | Covers: AC-007 | Level: unit | Priority: P0 | Evidence: `tests/test_analytics_profiles.py`
- TEST-006 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: existing `tests/test_api_contract.py`
- TEST-007 | Covers: AC-009,AC-010 | Level: integration | Priority: P0 | Evidence: GitHub exact diff, PR Validation, aggregate Quality, merge and post-main Quality
- TEST-008 | Covers: AC-011,AC-012 | Level: runtime-manual | Priority: P0 | Evidence: separately authorized Ubuntu exact-release and real-vessel production acceptance in Issue #212

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #212 was reopened because fresh production observation invalidated the previous functional Water acceptance conclusion while preserving earlier infrastructure/provenance evidence.
- Specification impact: Water detection/event requirements now explicitly remove motion/speed admission gates for `water-v1` and add real-vessel acceptance.
- Plan impact: Worker policy is split by profile domain; continuous Water GPU duty and exact-SHA Ubuntu rollout are explicit risks and validation requirements.
- Tasks impact: New bounded source/test/SDD integration, CI/merge and separately authorized Ubuntu acceptance tasks are added after the previously completed registry-cap work.
- Authorization impact: RESOLVED — fresh six-path source authorization is durably recorded in Issue #212 comment `5323802105`; production remains unauthorized for the future merged SHA.
- Follow-up: Complete exact six-path source lifecycle; then request a fresh production safety envelope for the merged executable SHA and run Ubuntu acceptance against a naturally occurring vessel.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: Water inference in runtime `9e0cd96...` was admitted only while the legacy motion detector was active, and accepted YOLO detections were then filtered against current motion boxes. Small/distant vessel motion can therefore fail before YOLO and again after YOLO; speed-oriented event readiness can independently prevent a detected Water vessel from entering events.
- Production-learning adjacent-stage findings: ROI masking and ByteTrack/model/profile configuration remain valid; API/storage registry cap and private M2M are not causal; the remediation needs Ubuntu Worker executable source only; source integration can be completed without production mutation; the later runtime transaction must preserve exact-source admission, Road desired state, rollback capability and real-vessel evidence.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on the prior accepted Worker release and no runtime action occurs | Retry: only after exact merged SHA has successful exact-main Quality and a matching fresh production authorization | Rollback: not applicable before mutation | Evidence: merged SHA, Quality result, Issue #212 production authorization fingerprint
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: prior Worker release and service state remain unchanged | Retry: resolve exact-release/model/runtime/preflight mismatch before any install or service switch | Rollback: not applicable because candidate activation has not started | Evidence: exact checkout/release identity, shared runtime readiness, model digest/CUDA preflight, current Road desired state
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate is not accepted; prior exact Worker release must remain or be restored | Retry: only after mutation failure root cause is resolved for the same authorized SHA | Rollback: repository-owned exact Worker rollback to previous accepted release | Evidence: Ubuntu deployment/update transaction markers and exact source/runtime IDs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: unverified Water candidate is not accepted even if service started | Retry: resolve failed service/frame/AI/GPU/real-vessel evidence and reverify the same authorized release | Rollback: restore previous exact Worker release if health or functional acceptance fails | Evidence: service state, advancing frame/state telemetry, AI activity, GPU health, real-vessel detection/track/event, Road state
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: candidate must not become durable accepted release without successful verification | Retry: repeat commit only after exact verification evidence is complete | Rollback: restore previous release marker/unit binding if state commit is inconsistent | Evidence: current-release/manifest or equivalent exact source/runtime state markers
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified active runtime remains accepted while cleanup may remain pending | Retry: cleanup may be retried without changing active source | Rollback: none for housekeeping-only failure | Evidence: cleanup output and retained current/previous exact release identities
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: Outcome cannot reach DONE without durable sanitized source/runtime/functional evidence | Retry: re-read machine-observable state and persist evidence without redeploying solely for documentation | Rollback: not applicable to evidence recording | Evidence: Issue #212 comments, workflow run IDs, exact runtime state and real-vessel acceptance record
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: previous exact Worker release and intended Road state are restored or an unresolved production state is recorded fail-closed | Retry: prohibited until actual source/service/runtime state and rollback result are verified | Rollback: repository-owned exact Ubuntu Worker rollback path | Evidence: rollback markers, previous source/runtime identity, Water/Road service state and protected health checks

## Runtime feedback

- Current source-control main at authorization is `f3febcd6d9ae6a57e052f6b4a50bf3ec9f75fdf1`; current deployed executable evidence remains bound to `9e0cd96aa2f790f1ba806299c3dd4019e5572899`.
- Fresh production evidence on #212 shows a real moving in-ROI vessel with `MOTION idle`, `AI idle`, `DETECTIONS 0`, `TRACKS 0`; exact-source inspection ties this to the legacy motion gate/filter and invalidates prior functional acceptance.
- Source authorization comment `5323802105` permits exactly `worker/hls_motion_yolo_worker_events.py`, `tests/test_water_detection_pipeline.py`, `tests/test_analytics_profiles.py` and this SDD triplet. No other path is admissible without fresh scope authorization.
- Production remains a separate human decision after merge; no production mutation is authorized by `OUTCOME APPROVED`.
