# Feature Specification: Water detection recall evidence

- Feature: 074-water-detection-recall-evidence
- Issue: #346
- Status: Active - Task 3A production accepted; Task 3B evidence classified; Task 3C Water-only threshold tuning authorized
- Owner outcome: improve Water vessel recall from production evidence without widening class-map, ROI, tracker, speed, API, frontend, Road, or deployment semantics.
- Task 3A remediation authorization: `issue-346-task3a-ubuntu-diagnostic-ipc-remediation-v1` from protected main `7b9902adca65d43151de629d15e526a5f79d3899`.
- Task 3B authorization: `issue-346-task3b-water-recall-evidence-interpretation-v1` from protected main `ea6f1e9d15252840d27721f004817ba35f11d0c6`.
- Task 3C authorization: `issue-346-task3c-water-low-confidence-recall-tuning-v1` from protected main `b5555c82d0c97fff4542de6776496fb57d7b57ad`.

## Product outcome

Task 3A created and production-accepted bounded Water recall diagnostics. Task 3B used representative production traffic to identify the dominant observed loss stage. Task 3C performs one minimum evidence-backed behavior change: lower only the `water-v1` detector confidence from `0.15` to `0.10`, while keeping `road-v1` at `0.15` and leaving tracker, class map, ROI, model, image size, speed and public interfaces unchanged.

The production evidence supporting Task 3C is asymmetric and stage-specific:

- healthy passage `P-20260829T231340-5d4b1ffb` produced `boat` detections around confidence `0.82-0.83`, passed class mapping and ROI, and held stable `track_id=4183`;
- unstable passage `P-20260829T232107-c5dcf174` produced intermittent detections, including a `boat` candidate at confidence `0.1781` with bbox `20x8`, accepted by class mapping and ROI but with no track assignment, surrounded by long runs of `detections=0`;
- therefore class-map and ROI rejection are not supported as the dominant cause; tracker non-assignment is observed downstream of weak/intermittent detector visibility;
- diagnostics begin after the active `model.track(..., conf=...)` threshold and cannot show candidates rejected below that threshold.

Task 3B classification is `DETECTOR_POST_THRESHOLD_VISIBILITY_INSTABILITY`, with `TRACKER_NON_ASSIGNMENT` as a secondary consequence rather than the primary tuning target.

## User scenarios

### Scenario 1 - Explain an accepted vessel

Given Water Worker inference produces a model result that maps to `vessel`, bounded diagnostics record model class, confidence, bbox dimensions/area, track assignment, ROI center relation and final ROI acceptance.

### Scenario 2 - Explain a post-threshold rejection

Given Water inference produces a post-threshold model result outside the `water-v1` class map, diagnostics record that model class and confidence with `class_mapping_accepted=false` without admitting the object to Water detections.

### Scenario 3 - Preserve production decisions during observability

Given the same model result and runtime configuration, diagnostics collection itself does not change returned detections or ROI acceptance decisions.

### Scenario 4 - Interpret representative traffic

Given real Water vessel traffic, accepted and unstable examples are compared across detector visibility, class mapping, ROI filtering and tracker continuity before any tuning is proposed.

### Scenario 5 - Tune only the evidence-supported stage

Given Task 3B evidence points to weak/intermittent post-threshold detector visibility, Task 3C changes only the Water confidence default from `0.15` to `0.10`. Road confidence remains `0.15`. No simultaneous tracker, class-map, ROI or image-size tuning is permitted.

### Scenario 6 - Fail safely on false positives or no improvement

Given the lower Water threshold is deployed, representative traffic must show improved small/distant vessel continuity without uncontrolled false positives. If continuity does not improve or false positives materially increase, the Water confidence is restored to `0.15` under the authorized rollback boundary.

## Requirements

- FR-001: Water diagnostics MUST expose post-threshold model class, confidence, bbox geometry/size, tracker assignment and profile class-mapping outcome without changing returned detections.
- FR-002: Water diagnostics MUST record the existing ROI-center relation and final ROI acceptance.
- FR-003: Diagnostics MUST remain bounded, secret-free and single-pass; no second detector/tracker inference is allowed.
- FR-004: Task 3B evidence MUST distinguish detector visibility, class mapping, ROI and tracker stages or record `INCONCLUSIVE`.
- FR-005: Task 3B evidence MUST state that `post_threshold_raw` cannot expose boxes rejected below configured confidence.
- FR-006: Task 3C MUST set `water-v1.confidence` to `0.10`.
- FR-007: Task 3C MUST keep `road-v1.confidence` at `0.15`.
- FR-008: Task 3C MUST NOT change model/weights, `YOLO_IMAGE_SIZE`, device/FP16, ByteTrack config/state, class mapping, ROI geometry/pre-mask/post-filter, Water speed/PassageEngine, API/storage/frontend, Road behavior, camera/media/auth topology or deployment tooling.
- FR-009: Ubuntu Worker MUST consume the selected analytics profile confidence through the existing supervised inference path; no alternate or shadow inference path is introduced.
- FR-010: Task 3C MUST pass exact-head and exact-main required checks before protected Ubuntu deployment.
- FR-011: Task 3C production acceptance MUST compare representative small/distant-vessel detection/track continuity against the Task 3B evidence and observe false-positive behavior.
- FR-012: If Task 3C does not improve continuity or produces materially uncontrolled false positives, Water confidence MUST return to `0.15`; no tracker/imgsz/ROI/class-map tuning is authorized by this scope.

## Acceptance criteria

- AC-001: Deterministic tests prove `water-v1.confidence == 0.10` and `road-v1.confidence == 0.15`.
- AC-002: Exact changed-file review contains only the authorized five repository paths.
- AC-003: No diff changes model/weights, image size, tracker, class map, ROI, speed, API/storage/frontend, Road runtime behavior or deployment tooling.
- AC-004: Exact PR head passes `Repository validation` and `quality-integration`.
- AC-005: Fresh merge probe confirms unchanged protected main assumptions, exact authorized diff and no blocking review threads before merge.
- AC-006: Exact merged main passes `Repository validation` and `quality-integration`.
- AC-007: Protected Ubuntu Worker deployment of exact main passes runtime safety/progression gates; VPS is skipped.
- AC-008: Representative real Water traffic after deployment shows improved detection continuity and, where geometry permits, stable track assignment for small/distant vessels relative to the unstable Task 3B example.
- AC-009: Representative traffic does not show materially uncontrolled false positives. If it does, acceptance fails and Water confidence is restored to `0.15`.
- AC-010: Road remains at confidence `0.15` with no Road behavior/source changes outside the shared profile table value assertion.
- AC-011: No further detector/tracker/ROI/class-map tuning occurs under Task 3C authorization.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: one-variable Water-only experiment | Validation: exact diff + profile tests | Status: PENDING CI
- NFR-002 | Area: PERFORMANCE | Target: no additional inference pass and unchanged `imgsz=960`/sample cadence | Validation: protected-path review and existing worker architecture | Status: PENDING CI
- NFR-003 | Area: SECURITY | Target: no secret/media/auth surface change | Validation: exact diff | Status: PENDING CI
- NFR-004 | Area: OPERABILITY | Target: rollback is one Water profile value `0.10 -> 0.15`; protected deployment remains transactional | Validation: deployment evidence | Status: PENDING RUNTIME

## Compatibility and boundaries

Stable public interfaces remain unchanged: Water live/passage API envelopes, storage schema, frontend behavior, operator controls and Road runtime semantics.

Task 3C repository scope is limited to:

- `worker/analytics_profiles.py`
- `tests/test_analytics_profiles.py`
- `specs/074-water-detection-recall-evidence/spec.md`
- `specs/074-water-detection-recall-evidence/plan.md`
- `specs/074-water-detection-recall-evidence/tasks.md`

Protected/out of scope: model binaries and weights; image size; device/FP16; ByteTrack config/state; accepted classes; ROI geometry/masking/filtering; Water speed/PassageEngine; API/storage/frontend; Road confidence/behavior; deployment/runtime verifier/systemd; camera/HLS/MediaMTX/nginx/Auth/ZeroTier; second/shadow inference.

## Runtime feedback

### Task 3A

- First Task 3A candidate failed Ubuntu runtime progression and automatically restored the prior accepted Worker.
- PR #358 remediated Ubuntu child/parent diagnostic IPC without changing accepted detection semantics.
- Exact remediation head `dd341242e54f4e01382e2322e9571ec407cd295a` passed PR Validation `33251179588` and quality-integration `33251179586`.
- Protected main `ea6f1e9d15252840d27721f004817ba35f11d0c6` passed exact-main runs `33251243227` and `33251243310`.
- Deployment run `33251264466` passed; Ubuntu REQUIRED/executed, VPS SKIPPED; `frame_and_state_progression=PASS`.

### Task 3B

- SDD reconciliation PR #359 merged to protected main `b5555c82d0c97fff4542de6776496fb57d7b57ad`; exact-main Repository validation `33255091247` and quality-integration `33255091254` passed.
- Representative journal evidence overlapped real passages.
- Healthy passage `P-20260829T231340-5d4b1ffb`: diagnostic frames showed `post_threshold_raw=1`, `class_mapping_accepted=1`, `track_assigned=1`, `accepted_after_roi=1`; `boat` confidence `0.8212/0.8326`, stable track `4183`.
- Unstable passage `P-20260829T232107-c5dcf174`: one diagnostic candidate was `boat`, confidence `0.1781`, bbox `20x8`, class-map accepted, ROI-center accepted, `track_id=null`; surrounding inference repeatedly alternated between one detection and zero detections, with diagnostic frames returning `post_threshold_raw=0`.
- Dominant classification: `DETECTOR_POST_THRESHOLD_VISIBILITY_INSTABILITY`; secondary consequence: `TRACKER_NON_ASSIGNMENT`.
- Evidence does not support class-map or ROI rejection as the dominant cause.

### Task 3C

- Authorization `OUTCOME APPROVED` recorded against exact protected main `b5555c82d0c97fff4542de6776496fb57d7b57ad`.
- Authorized experiment: Water confidence `0.15 -> 0.10` only; Road remains `0.15`.
- Production acceptance is pending exact-head CI, exact-main CI, protected Ubuntu deployment and representative post-deploy traffic evidence.
