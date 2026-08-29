# Feature Specification: Water detection recall evidence

- Feature: 074-water-detection-recall-evidence
- Issue: #346
- Status: Active
- Owner outcome: collect bounded, decision-neutral Water detector evidence so missed or unstable vessels can be diagnosed before any recall tuning.
- Remediation authorization: `issue-346-task3a-ubuntu-diagnostic-ipc-remediation-v1` from protected main `7b9902adca65d43151de629d15e526a5f79d3899`.

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

### Scenario 5 - Preserve Ubuntu supervised inference behavior

Given production Ubuntu executes YOLO in the bounded child process, when the child returns one `model.track()` result, then the existing accepted detection list and an optional diagnostics list travel in the same bounded framed response. The parent supervisor accepts `diagnostics=None` for two-argument Road compatibility and fills the Water diagnostic sink when supplied.

## Requirements

- FR-001: The Worker MUST expose post-threshold model class, confidence, bbox geometry/size, tracker assignment and profile class-mapping outcome through an optional diagnostic sink without changing the returned detections.
- FR-002: Water diagnostics MUST record whether each class-mapped candidate is inside the existing ROI by the existing bbox-center predicate and whether it survived the existing ROI filter.
- FR-003: Diagnostics MUST record the active non-secret detector configuration needed to interpret evidence: model name, image size, confidence threshold and tracker name.
- FR-004: Diagnostics MUST identify whether ROI preprocessing is `masked_before_inference` or `full_frame`, the ROI point count, and the current post-filter strategy `bbox_center`.
- FR-005: Diagnostics MUST be bounded by an emission interval and a capped record count and MUST NOT execute an additional detector/tracker inference pass.
- FR-006: Diagnostics MUST NOT contain camera/media URLs, API tokens, Basic Auth values, credentials, image crops or raw frames.
- FR-007: Task 3A MUST NOT modify YOLO model/weights, `YOLO_CONFIDENCE`, `YOLO_IMAGE_SIZE`, ByteTrack configuration, profile class mapping, ROI geometry/masking/filtering decisions, Water speed/PassageEngine semantics, frontend/API storage contracts, or Road runtime semantics.
- FR-008: The evidence semantics MUST state that `post_threshold_raw` is the output visible from the existing `model.track(..., conf=...)` call and therefore cannot prove the existence of candidates rejected below that configured confidence threshold.
- FR-009: The Ubuntu inference child MUST serialize accepted detections with the same fields/values as before remediation and MUST expose class-map rejected post-threshold boxes only through a separate diagnostics field in the same response.
- FR-010: The Ubuntu parent supervisor MUST validate the diagnostics field as a list of mappings, preserve the existing 4 MiB framed-response bound, and accept an optional diagnostic sink without changing two-argument callers.

## Acceptance criteria

- AC-001: A deterministic detector test proves that adding a diagnostics sink leaves the returned detection list byte-for-structure equivalent for the same model result.
- AC-002: A deterministic diagnostic test records model class, confidence, bbox dimensions/area, track assignment, class-mapping acceptance, ROI-center relation and final ROI acceptance.
- AC-003: Diagnostic output records current model name, image size, confidence threshold, tracker, ROI preprocessing mode and bbox-center post-filter strategy without including protected URL/token environment names or values.
- AC-004: Diagnostic emission is rate-bounded and record-bounded; repeated calls inside the configured interval emit nothing and records above the configured cap are truncated with an explicit flag.
- AC-005: Exact changed-file review confirms zero diff to `worker/analytics_profiles.py`, detector thresholds/model settings, tracker config, ROI decision code, Water speed/PassageEngine, API/frontend and Road behavior except the separately authorized Ubuntu diagnostic IPC remediation paths.
- AC-006: Exact PR head passes Repository validation and `quality-integration`, is merged only at that green head, and exact protected main passes the same required quality gates.
- AC-007: The exact-main Ubuntu Worker release is deployed through the protected connector path with VPS skipped and reaches `frame_and_state_progression=PASS`; real-vessel diagnostic sampling remains explicitly deferrable until traffic is available.
- AC-008: No recall threshold, class-map, ROI or tracker tuning is authorized by Task 3A; any later recall change must cite collected evidence and receive its own bounded authorization.
- AC-009: `tests/test_water_recall_ubuntu_ipc.py` proves accepted child detections are unchanged, class-map rejects are diagnostic-only, the child source contains one `model.track()` call, the parent accepts `diagnostics=None`, and the IPC remains bounded and secret-free.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: diagnostics-on and diagnostics-off return identical detector decisions for identical model output | Validation: deterministic equality tests in in-process and Ubuntu child paths | Evidence: `test_recall_diagnostics_sink_does_not_change_detector_result`; `test_child_side_channel_preserves_accepted_detection_semantics` | Status: PASS
- NFR-002 | Area: PERFORMANCE | Target: zero extra `model.track` calls; diagnostic logging no more than once per 10 seconds by default with at most 12 records per emission | Validation: source contract plus bounded-emission test | Evidence: `maybe_emit_water_recall_diagnostics`; `tests/test_water_recall_ubuntu_ipc.py` | Status: PASS
- NFR-003 | Area: SECURITY | Target: diagnostic payload contains no camera/media URL, API token, Basic Auth value, credential, frame or image crop | Validation: fixed payload allowlist and child source regression assertions | Evidence: `tests/test_worker_tracking_overlay.py`; `tests/test_water_recall_ubuntu_ipc.py` | Status: PASS
- NFR-004 | Area: OPERABILITY | Target: one JSON object per emitted line with stable schema `sea_speed_water_recall_diagnostic_v1`; Ubuntu framed child response remains <=4 MiB | Validation: deterministic JSON parsing test plus parent response-size guard | Evidence: Worker diagnostics tests and `BoundedYoloSupervisor._roundtrip` | Status: PASS

## Compatibility and boundaries

- Stable public interfaces: Water live/passage API envelopes, frontend behavior, Road runtime, operator Worker controls and deployment topology remain unchanged.
- Internal compatibility: Ubuntu child/parent framed IPC adds an optional `diagnostics` response field; this is not a public API/storage schema and does not alter accepted detection semantics.
- Out of scope: detector threshold/resolution changes; alternate accepted classes; ByteTrack tuning; ROI processing/filter changes; speed changes; shadow inference; API schema/storage; frontend visualization; automatic interpretation of daytime evidence.
- Security constraints: diagnostic payload is an allowlisted local Worker log structure only; no secret-bearing environment values, media URLs, frames or crops are serialized.

## Runtime feedback

- First deployment of source `7b9902adca65d43151de629d15e526a5f79d3899`: FAILED twice at `no_exact_running_baseline` after AI self-test; updater automatically restored accepted production Worker `739947c11471c746e74af0dfee4d9a5edd0d7bac` both times.
- Root cause: Ubuntu entrypoint monkey-patched `detect_vehicles(_model, frame)` while Water called `detect_vehicles(..., diagnostics=...)`; additionally the child discarded class-map rejects before parent diagnostics could observe them.
- Remediation: carry accepted detections plus diagnostic records through the existing single-pass child IPC and make the parent monkey-patch diagnostics-compatible.
- Runtime acceptance: PENDING remediation exact-main Ubuntu Worker deployment; real-vessel evidence explicitly may be deferred until daytime traffic.
- Accepted production behavior: current production remains the restored `739947c11471c746e74af0dfee4d9a5edd0d7bac` Worker until remediation passes the runtime gate.
- Regressions/learning: diagnostics begin after the configured `model.track` confidence threshold; candidates below that threshold remain unobservable without a separately authorized experiment.
- Follow-up work: Task 3 evidence-based recall tuning remains separate and requires a new bounded Outcome Contract after representative evidence is collected.
