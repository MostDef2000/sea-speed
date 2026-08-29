# Feature Specification: Water detection recall evidence

- Feature: 074-water-detection-recall-evidence
- Issue: #346
- Status: Active - Task 3A production accepted; Task 3B evidence interpretation authorized
- Owner outcome: collect bounded, decision-neutral Water detector evidence so missed or unstable vessels can be diagnosed before any recall tuning.
- Task 3A remediation authorization: `issue-346-task3a-ubuntu-diagnostic-ipc-remediation-v1` from protected main `7b9902adca65d43151de629d15e526a5f79d3899`.
- Task 3B authorization: `issue-346-task3b-water-recall-evidence-interpretation-v1` from protected main `ea6f1e9d15252840d27721f004817ba35f11d0c6`.
- Task 3B repository scope: this spec, plan and tasks only; Ubuntu production observation is read-only; deployment is not required.

## Product outcome

When Water traffic is available, operators and maintainers can distinguish where a candidate was lost in the current detection pipeline: detector output after the configured confidence threshold, profile class mapping, ROI center filtering, or tracker assignment. The evidence is bounded, secret-free and does not change which detections enter Water live/passage semantics.

Task 3A created and production-accepted the observability path. Task 3B interprets representative production evidence and reconciles the durable SDD with completed Task 3A delivery evidence. Neither stage authorizes recall tuning.

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

### Scenario 6 - Interpret representative runtime evidence

Given representative real vessels are visible while the accepted Ubuntu Worker is running, when a bounded sample of `WATER_RECALL_DIAGNOSTIC` records is reviewed, then the dominant observed loss stage is classified as post-threshold detector visibility, class mapping, ROI center filtering or tracker continuity. If the available evidence cannot distinguish a dominant stage, the result is recorded as `INCONCLUSIVE` rather than tuning production blindly.

## Requirements

- FR-001: The Worker MUST expose post-threshold model class, confidence, bbox geometry/size, tracker assignment and profile class-mapping outcome through an optional diagnostic sink without changing the returned detections.
- FR-002: Water diagnostics MUST record whether each class-mapped candidate is inside the existing ROI by the existing bbox-center predicate and whether it survived the existing ROI filter.
- FR-003: Diagnostics MUST record the active non-secret detector configuration needed to interpret evidence: model name, image size, confidence threshold and tracker name.
- FR-004: Diagnostics MUST identify whether ROI preprocessing is `masked_before_inference` or `full_frame`, the ROI point count, and the current post-filter strategy `bbox_center`.
- FR-005: Diagnostics MUST be bounded by an emission interval and a capped record count and MUST NOT execute an additional detector/tracker inference pass.
- FR-006: Diagnostics MUST NOT contain camera/media URLs, API tokens, Basic Auth values, credentials, image crops or raw frames.
- FR-007: Task 3A and Task 3B MUST NOT modify YOLO model/weights, `YOLO_CONFIDENCE`, `YOLO_IMAGE_SIZE`, ByteTrack configuration/state, profile class mapping, ROI geometry/masking/filtering decisions, Water speed/PassageEngine semantics, frontend/API storage contracts or Road runtime semantics.
- FR-008: The evidence semantics MUST state that `post_threshold_raw` is the output visible from the existing `model.track(..., conf=...)` call and therefore cannot prove the existence of candidates rejected below that configured confidence threshold.
- FR-009: The Ubuntu inference child MUST serialize accepted detections with the same fields/values as before remediation and MUST expose class-map rejected post-threshold boxes only through a separate diagnostics field in the same response.
- FR-010: The Ubuntu parent supervisor MUST validate the diagnostics field as a list of mappings, preserve the existing 4 MiB framed-response bound, and accept an optional diagnostic sink without changing two-argument callers.
- FR-011: Task 3B production observation MUST be read-only and bounded to existing secret-free diagnostic output from accepted source `ea6f1e9d15252840d27721f004817ba35f11d0c6`; it MUST NOT deploy, restart, retune or otherwise mutate production solely to obtain evidence.
- FR-012: Task 3B MUST record either a stage-supported interpretation from representative accepted plus missed/unstable examples or the explicit result `INCONCLUSIVE`. Any later behavior change requires a new six-field Scope and fresh literal `OUTCOME APPROVED`.

## Acceptance criteria

- AC-001: A deterministic detector test proves that adding a diagnostics sink leaves the returned detection list byte-for-structure equivalent for the same model result.
- AC-002: A deterministic diagnostic test records model class, confidence, bbox dimensions/area, track assignment, class-mapping acceptance, ROI-center relation and final ROI acceptance.
- AC-003: Diagnostic output records current model name, image size, confidence threshold, tracker, ROI preprocessing mode and bbox-center post-filter strategy without including protected URL/token environment names or values.
- AC-004: Diagnostic emission is rate-bounded and record-bounded; repeated calls inside the configured interval emit nothing and records above the configured cap are truncated with an explicit flag.
- AC-005: Exact changed-file review confirms zero diff to detector settings, tracker configuration, ROI decision code, Water speed/PassageEngine, API/frontend and Road behavior outside the separately authorized Task 3A implementation paths.
- AC-006: Task 3A exact PR head passes Repository validation and `quality-integration`, is merged only at that green head, and exact protected main passes the same required quality gates.
- AC-007: Task 3A exact-main Ubuntu Worker release is deployed through the protected connector path with VPS skipped and reaches `frame_and_state_progression=PASS`.
- AC-008: No recall threshold, class-map, ROI or tracker tuning is authorized by Task 3A or Task 3B; any later recall change must cite collected evidence and receive its own bounded authorization.
- AC-009: `tests/test_water_recall_ubuntu_ipc.py` proves accepted child detections are unchanged, class-map rejects are diagnostic-only, the child source contains one `model.track()` call, the parent accepts `diagnostics=None`, and IPC remains bounded and secret-free.
- AC-010: SDD 074 records the completed Task 3A exact-head, merge, exact-main and Ubuntu runtime evidence rather than leaving those gates pending.
- AC-011: Representative Task 3B evidence is sufficient to classify the dominant observed loss stage, or the durable result is explicitly `INCONCLUSIVE`; no tuning is performed inside Task 3B.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: diagnostics-on and diagnostics-off return identical detector decisions for identical model output | Validation: deterministic equality tests in in-process and Ubuntu child paths | Evidence: `test_recall_diagnostics_sink_does_not_change_detector_result`; `test_child_side_channel_preserves_accepted_detection_semantics` | Status: PASS
- NFR-002 | Area: PERFORMANCE | Target: zero extra `model.track` calls; diagnostic logging no more than once per 10 seconds by default with at most 12 records per emission | Validation: source contract plus bounded-emission test | Evidence: `maybe_emit_water_recall_diagnostics`; `tests/test_water_recall_ubuntu_ipc.py` | Status: PASS
- NFR-003 | Area: SECURITY | Target: diagnostic payload contains no camera/media URL, API token, Basic Auth value, credential, frame or image crop | Validation: fixed payload allowlist and child source regression assertions | Evidence: `tests/test_worker_tracking_overlay.py`; `tests/test_water_recall_ubuntu_ipc.py` | Status: PASS
- NFR-004 | Area: OPERABILITY | Target: one JSON object per emitted line with stable schema `sea_speed_water_recall_diagnostic_v1`; Ubuntu framed child response remains <=4 MiB | Validation: deterministic JSON parsing test plus parent response-size guard | Evidence: Worker diagnostics tests and `BoundedYoloSupervisor._roundtrip` | Status: PASS

## Compatibility and boundaries

- Stable public interfaces: Water live/passage API envelopes, frontend behavior, Road runtime, operator Worker controls and deployment topology remain unchanged.
- Internal compatibility: Ubuntu child/parent framed IPC carries an optional `diagnostics` response field; this is not a public API/storage schema and does not alter accepted detection semantics.
- Task 3B source boundary: only `specs/074-water-detection-recall-evidence/{spec,plan,tasks}.md` may change.
- Out of scope: detector threshold/resolution changes; alternate accepted classes; ByteTrack tuning; ROI processing/filter changes; speed changes; shadow inference; API schema/storage; frontend visualization; deployment/runtime tooling changes.
- Security constraints: diagnostic payload is an allowlisted local Worker log structure only; no secret-bearing environment values, media URLs, frames or crops are serialized.

## Runtime feedback

- First Task 3A deployment of source `7b9902adca65d43151de629d15e526a5f79d3899`: FAILED twice at `no_exact_running_baseline` after AI self-test; updater automatically restored accepted production Worker `739947c11471c746e74af0dfee4d9a5edd0d7bac` both times.
- Root cause: Ubuntu entrypoint monkey-patched `detect_vehicles(_model, frame)` while Water called `detect_vehicles(..., diagnostics=...)`; additionally the child discarded class-map rejects before parent diagnostics could observe them.
- Remediation PR #358 carried accepted detections plus diagnostic records through the existing single-pass child IPC and made the parent monkey-patch diagnostics-compatible.
- Exact remediation PR head `dd341242e54f4e01382e2322e9571ec407cd295a`: PR Validation run `33251179588` PASS; quality-integration run `33251179586` PASS.
- Exact-green-head merge produced protected main `ea6f1e9d15252840d27721f004817ba35f11d0c6`.
- Exact-main Repository validation run `33251243227` PASS; exact-main quality-integration run `33251243310` PASS.
- Autonomous production deployment run `33251264466`: Ubuntu Worker REQUIRED/executed/PASS; VPS SKIPPED; standing delegation/source protection and production policy PASS.
- Runtime progression: baseline frame sequence `17`, state posts `4`, AI inference successes `29`; accepted progression frame sequence `33`, state posts `9`, AI inference successes `54`; `frame_and_state_progression=PASS`; `sea-speed-worker.service` active; Road desired state remained stopped.
- Accepted production Worker source is `ea6f1e9d15252840d27721f004817ba35f11d0c6`. Ubuntu artifact `sea-speed-ubuntu-worker-ea6f1e9d15252840d27721f004817ba35f11d0c6.tar.gz` has sha256 `c6d06ecffb35485a0551efc282d1c4b7784bbacf9810f52e6079a1025f770b1e`; deployment evidence artifact ID `9714438874`, ZIP digest `sha256:66556adea96476163403a1440fd7bdb1aa3c24a07945dce02ab36699e708c1e5`.
- Task 3A source/deployment/runtime acceptance is COMPLETE.
- Task 3B evidence status: PENDING representative bounded `WATER_RECALL_DIAGNOSTIC` sampling. The accepted deployment Actions log proves runtime progression but does not export the `sea-speed-worker.service` journal; absence of diagnostic lines in that Actions log is an evidence gap, not evidence of zero candidates.
- Regressions/learning: diagnostics begin after the configured `model.track` confidence threshold; candidates below that threshold remain unobservable without a separately authorized experiment.
- Follow-up work: review representative evidence and classify detector/class-map/ROI/tracker loss stage or `INCONCLUSIVE`. Recall tuning remains separately authorized work.
