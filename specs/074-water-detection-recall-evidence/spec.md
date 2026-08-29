# Feature Specification: Water detection recall evidence

- Feature: 074-water-detection-recall-evidence
- Issue: #346
- Status: Active
- Owner outcome: collect bounded, decision-neutral Water detector evidence so missed or unstable vessels can be diagnosed before any recall tuning.

## Product outcome

When Water traffic is available, operators and maintainers can distinguish where a candidate was lost in the current detection pipeline: detector output after the configured confidence threshold, profile class mapping, ROI center filtering, or tracker assignment. The evidence is bounded, secret-free and does not change which detections enter Water live/passage semantics.

This stage intentionally does not tune recall. It creates trustworthy production evidence for the later evidence-based Task 3 decision.

## User scenarios

### Scenario 1 - Explain an accepted vessel

Given Water Worker inference produces a model result that maps to `vessel`, when bounded diagnostics are emitted, then the evidence records model class, confidence, bbox dimensions/area, track assignment, ROI center relation and whether the detection survived the existing ROI filter.

### Scenario 2 - Explain a post-threshold rejection

Given Water Worker inference produces a post-threshold model result outside the `water-v1` class map, when diagnostics are emitted, then the evidence records that model class and confidence with `class_mapping_accepted=false` without admitting the object to Water detections.

### Scenario 3 - Preserve production decisions

Given the same model result and runtime configuration, when diagnostics collection is enabled or disabled, then `detect_vehicles` returns the same detection list and existing ROI filtering makes the same acceptance decision.

### Scenario 4 - Keep observability bounded

Given continuous Water inference, when diagnostics are enabled, then at most one structured diagnostic record is emitted per configured interval and the per-frame record list is capped; no second inference pass, image crop, camera URL or credential is emitted.

## Requirements

- FR-001: The Worker MUST expose post-threshold model class, confidence, bbox geometry/size, tracker assignment and profile class-mapping outcome through an optional diagnostic sink without changing the returned detections.
- FR-002: Water diagnostics MUST record whether each class-mapped candidate is inside the existing ROI by the existing bbox-center predicate and whether it survived the existing ROI filter.
- FR-003: Diagnostics MUST record the active non-secret detector configuration needed to interpret evidence: model name, image size, confidence threshold and tracker name.
- FR-004: Diagnostics MUST identify whether ROI preprocessing is `masked_before_inference` or `full_frame`, the ROI point count, and the current post-filter strategy `bbox_center`.
- FR-005: Diagnostics MUST be bounded by an emission interval and a capped record count and MUST NOT execute an additional detector/tracker inference pass.
- FR-006: Diagnostics MUST NOT contain camera/media URLs, API tokens, Basic Auth values, credentials, image crops or raw frames.
- FR-007: Task 3A MUST NOT modify YOLO model/weights, `YOLO_CONFIDENCE`, `YOLO_IMAGE_SIZE`, ByteTrack configuration, profile class mapping, ROI geometry/masking/filtering decisions, Water speed/PassageEngine semantics, frontend/API storage contracts, or Road runtime semantics.
- FR-008: The evidence semantics MUST state that `post_threshold_raw` is the output visible from the existing `model.track(..., conf=...)` call and therefore cannot prove the existence of candidates rejected below that configured confidence threshold.

## Acceptance criteria

- AC-001: A deterministic detector test proves that adding a diagnostics sink leaves the returned detection list byte-for-structure equivalent for the same model result.
- AC-002: A deterministic diagnostic test records model class, confidence, bbox dimensions/area, track assignment, class-mapping acceptance, ROI-center relation and final ROI acceptance.
- AC-003: Diagnostic output records current model name, image size, confidence threshold, tracker, ROI preprocessing mode and bbox-center post-filter strategy without including protected URL/token environment names or values.
- AC-004: Diagnostic emission is rate-bounded and record-bounded; repeated calls inside the configured interval emit nothing and records above the configured cap are truncated with an explicit flag.
- AC-005: Exact changed-file review confirms zero diff to `worker/analytics_profiles.py`, detector thresholds/model settings, tracker config, ROI decision code, Water speed/PassageEngine, API/frontend and Road behavior unless a separately authorized remediation is required.
- AC-006: Exact PR head passes Repository validation and `quality-integration`, is merged only at that green head, and exact protected main passes the same required quality gates.
- AC-007: The exact-main Ubuntu Worker release is deployed through the protected connector path with VPS skipped; installation/activation evidence is accepted even when operator desired state is stopped, while real-vessel diagnostic sampling remains explicitly deferred until traffic is available.
- AC-008: No recall threshold, class-map, ROI or tracker tuning is authorized by Task 3A; any later recall change must cite collected evidence and receive its own bounded authorization.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: diagnostics-on and diagnostics-off return identical detector decisions for identical model output | Validation: deterministic equality test | Evidence: `tests/test_worker_tracking_overlay.py::test_recall_diagnostics_sink_does_not_change_detector_result` | Status: PASS
- NFR-002 | Area: PERFORMANCE | Target: zero extra `model.track` calls; diagnostic logging no more than once per 10 seconds by default with at most 12 records per emission | Validation: source contract plus bounded-emission test | Evidence: `maybe_emit_water_recall_diagnostics`; `tests/test_worker_tracking_overlay.py::test_water_recall_diagnostics_are_bounded_and_stage_explicit` | Status: PASS
- NFR-003 | Area: SECURITY | Target: diagnostic payload contains no camera/media URL, API token, Basic Auth value, credential, frame or image crop | Validation: fixed payload allowlist and secret-name regression assertions | Evidence: `tests/test_worker_tracking_overlay.py::test_water_recall_diagnostics_are_bounded_and_stage_explicit` | Status: PASS
- NFR-004 | Area: OPERABILITY | Target: one JSON object per emitted line with stable schema `sea_speed_water_recall_diagnostic_v1` and explicit stage counts | Validation: deterministic JSON parsing test | Evidence: `tests/test_worker_tracking_overlay.py::test_water_recall_diagnostics_are_bounded_and_stage_explicit` | Status: PASS

## Compatibility and boundaries

- Stable public interfaces: Water live/passage API envelopes, frontend behavior, Road runtime, operator Worker controls and deployment topology remain unchanged.
- Out of scope: detector threshold/resolution changes; alternate accepted classes; ByteTrack tuning; ROI processing/filter changes; speed changes; shadow inference; API schema/storage; frontend visualization; automatic interpretation of daytime evidence.
- Security constraints: diagnostic payload is an allowlisted local Worker log structure only; no secret-bearing environment values, media URLs, frames or crops are serialized.

## Runtime feedback

- Runtime acceptance: PENDING exact-main Ubuntu Worker deployment; real-vessel evidence explicitly may be deferred until daytime traffic.
- Accepted production behavior: PENDING
- Regressions/learning: current detector diagnostics begin after the configured `model.track` confidence threshold; candidates below that threshold are not observable without a separately authorized experiment.
- Follow-up work: Task 3 evidence-based recall tuning remains separate and requires a new bounded Outcome Contract after representative evidence is collected.
