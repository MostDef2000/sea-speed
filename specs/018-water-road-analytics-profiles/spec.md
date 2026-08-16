# Specification: Water and road analytics profiles

- Issue: #197
- Status: In implementation

## Product outcome

Sea Speed MUST run one profile-driven analytics implementation across two isolated operator domains. The existing main operator contour becomes `water-v1`, using a locally staged `yolo26x.pt` baseline and normalizing model-native `boat` into canonical maritime object type `vessel`. A new authenticated `/sea-speed/road/` contour runs `road-v1` against logical camera `road1`, with separate worker process, tracking state, configuration, event/state files and overlay/output state. Both Ubuntu analytics workers reuse the same immutable Python runtime and shared read-only model store. Protected runtime configuration resolves `road1` to its private camera source without exposing source credentials or the physical source through Git/frontend/API.

Because canonical delivery policy classifies shared `worker/**` runtime source as applicable to both Ubuntu and Windows workers, this Outcome also carries a Windows compatibility/update contour. No Windows-specific Road feature, UI or service is introduced; Windows must consume the changed shared worker source without regression under its existing package/runtime contract.

## User scenarios

### Scenario 1 - Water analytics produces maritime semantics

When Camera 1 detects model class `boat`, the water profile accepts it and emits `analytics_profile=water-v1`, `domain=water`, `object_type=vessel`, `model_class=boat`, and canonical `class_name=vessel`. Road-native model classes do not become water events.

### Scenario 2 - Road analytics is isolated

The road service runs profile `road-v1` for logical `road1`. `car`, `truck`, `bus`, `motorcycle` and `bicycle` are accepted with road semantics; `boat` is rejected. Its ByteTrack persistence, ROI, speed calibration, events, state, heartbeat and overlay/output are separate from Camera 1.

### Scenario 3 - Operators use a dedicated Road page

An authenticated operator opens `/sea-speed/road/` from the same navigation used by the main operator, Objects Registry and Cameras pages. The page shows road worker/AI/detection/track state, AI overlay, road ROI and speed calibration, recent road events, and an on-demand clean preview for logical `road1`. The page does not expose arbitrary service control or camera source details.

### Scenario 4 - Objects Registry spans both domains

The registry retains historical records and can list/filter objects across cameras and domains. Existing Camera 1 object APIs remain compatible while additive generic APIs keep `cam1` and `road1` state/events/configuration isolated.

### Scenario 5 - YOLO26x activation is fail closed

The model binary is supplied only as protected local runtime input. A bounded preparation helper verifies the operator-supplied SHA-256, stages `yolo26x.pt` into the shared model store, and performs an exact runtime CUDA/Ultralytics inference self-test. No model binary enters Git/artifacts and no smaller model is selected silently if validation fails.

### Scenario 6 - Shared worker source remains Windows-compatible

The final shared worker source is packaged through the existing Windows Worker pipeline. Windows receives no Road-specific service/configuration surface; acceptance proves exact package/source identity, preserved protected local state, process restart/freshness and applicable telemetry after separately authorized production execution.

## Requirements

- FR-001: The analytics profile registry MUST define exactly `water-v1` and `road-v1` with defaults `models/yolo26x.pt`, image size 960, confidence 0.15, ByteTrack and target sampling 5 FPS.
- FR-002: `water-v1` MUST accept model class `boat` only from the baseline mapping and normalize it to canonical `vessel` semantics; road classes MUST NOT become water detections/events.
- FR-003: `road-v1` MUST accept `car`, `truck`, `bus`, `motorcycle`, `bicycle`; `boat` MUST NOT become a road detection/event.
- FR-004: Detections/events MUST carry `analytics_profile`, `domain`, `object_type`, `model_class`; `class_name` MUST remain the canonical object type for registry compatibility.
- FR-005: The Worker media, tracking, speed and event pipeline MUST remain profile-agnostic after class normalization and MUST preserve existing ROI/motion/tracking/speed/event ordering.
- FR-006: The Ubuntu AI child MUST receive the selected analytics profile and apply the same class normalization/filtering as in-process inference.
- FR-007: Main worker protected config MUST select `water-v1`/`cam1`; road worker protected config MUST select `road-v1`/`road1` and use a separate systemd service and state/output contour.
- FR-008: `sea-speed-road-worker.service` MUST reuse the exact source release, immutable runtime and shared model store while using separate road heartbeat/output and MUST NOT enter the browser worker-control allowlist.
- FR-009: Road source configuration MUST be resolved from the protected sanitized camera-preview catalog for logical `road1`; repository/frontend/API source MUST NOT contain the physical road camera address, credential-bearing RTSP URL, username or password.
- FR-010: The model preparation helper MUST require a local model file plus expected SHA-256, copy only after digest verification, use exact runtime Python for CUDA/model self-test, write a digest-bound manifest and MUST NOT download/fallback automatically.
- FR-011: API MUST expose additive `/api/analytics/{camera_id}/state|events|roi|speed-config|speed-lines|objects` for supported `cam1` and `road1`; unknown camera IDs MUST fail closed.
- FR-012: Legacy `/api/cam1/**` behavior MUST remain available and delegate to Camera 1 data semantics.
- FR-013: API storage MUST isolate per-camera state/events/ROI/speed configuration and preserve historical object rows while additively adding analytics semantic columns/indexes.
- FR-014: A global Objects Registry API MUST support camera/domain/profile/object-type filtering while object detail/update/delete remains stable by object ID.
- FR-015: `/sea-speed/road/` MUST use only logical `road1` analytics endpoints and on-demand camera preview start for `road1`; preview policy remains maximum one active preview with existing TTL/stop behavior.
- FR-016: Main, Objects, Cameras and Road pages MUST expose consistent navigation containing Objects, Cameras and Road destinations.
- FR-017: VPS exact release/install/rollback/smoke handling MUST include the Road page.
- FR-018: VPS and Ubuntu exact artifacts MUST include the new profile/Road source assets and MUST reject model binaries as release inputs.
- FR-019: Shared `worker/**` changes MUST remain compatible with the existing Windows Worker package/runtime contract; no Windows-specific Road feature, service or browser control is added.
- FR-020: Source integration MUST NOT perform production mutation. VPS, Ubuntu Worker and Windows Worker activation/update require a later exact-merged-SHA production authorization and contour-specific runtime evidence.

## Acceptance criteria

- AC-001: Unit tests prove the two profile defaults and water `boat -> vessel` normalization.
- AC-002: Unit tests prove `water-v1` rejects all configured road classes and `road-v1` rejects `boat` while accepting all five road classes.
- AC-003: Worker and AI-child source pass/serialize profile/domain/object/model semantics without changing tracking/speed event ordering.
- AC-004: API contract exposes additive generic analytics routes for `cam1`/`road1`, rejects unsupported camera identity, keeps legacy Camera 1 routes and stores isolated per-camera files.
- AC-005: Objects storage migration is additive/non-destructive and global queries can filter by camera/domain/profile/object type.
- AC-006: Main/Objects/Cameras/Road HTML contains a Road navigation target and the Road page uses only logical `road1`, not a physical camera source.
- AC-007: Road page provides road state, overlay, ROI, speed configuration, recent events and on-demand clean preview without browser service control.
- AC-008: Ubuntu source defines an isolated road service/configuration path sharing the immutable runtime/model store and leaves existing control agent scoped to the main worker only.
- AC-009: Model preparation verifies SHA-256 and CUDA model self-test and source/artifact policy prevents `.pt`/ONNX/engine binaries from entering Git/exact artifacts.
- AC-010: VPS deploy transaction captures/installs/verifies/rolls back Road frontend state alongside existing frontends.
- AC-011: Exact final PR changed-file set equals the authorized 42 paths; no physical road source/credential/model binary is present.
- AC-012: PR Validation, Quality integration and Package Windows Worker succeed on one exact final head; merge uses fresh main/head/scope/review checks and post-merge push/main quality succeeds.
- AC-013: Production acceptance, after separate exact-SHA authorization, records model digest/CUDA readiness, both Ubuntu worker exact identities/progression, dual-worker GPU headroom, protected `road1` source binding, exact Windows package/source/process/freshness evidence, and browser smoke for Main/Road.

## NFR assessment

- NFR-001 | Area: Security | Target: No physical road source, camera userinfo, API token or model binary is committed or returned to browser/API | Validation: repository secret/binary policy plus focused profile tests | Evidence: `scripts/ci/validate_repo.py`, `tests/test_analytics_profiles.py` | Status: PASS
- NFR-002 | Area: Compatibility | Target: Legacy `/api/cam1/**` remains present and historical object rows require no destructive rewrite | Validation: API source/behavior tests and additive SQLite migration checks | Evidence: `tests/test_api_contract.py`, `api/app/main.py` | Status: PASS
- NFR-003 | Area: Isolation | Target: water and road use distinct logical IDs, state/events/config files, service/heartbeat/output and tracker processes | Validation: API/worker/systemd contract tests | Evidence: `tests/test_analytics_profiles.py`, `tests/test_ubuntu_worker_systemd.py` | Status: PASS
- NFR-004 | Area: Reliability | Target: Exact model activation is digest-bound, CUDA self-tested and has no silent fallback | Validation: model preparation source tests; runtime-manual gate after production authorization | Evidence: `deploy/worker/ubuntu/prepare-yolo-model.py` | Status: CONCERNS
- NFR-005 | Area: Performance | Target: Both Ubuntu profiles request 960 input and 5 FPS, and simultaneous workers produce sustained frame/state/AI progression without OOM/degraded inference | Validation: source defaults plus runtime-manual dual-worker GPU acceptance | Evidence: `worker/analytics_profiles.py`; production runtime evidence pending | Status: CONCERNS
- NFR-006 | Area: Operator UX | Target: Road destination is visible from all four Sea Speed pages and Road page exposes state/calibration/events/preview without arbitrary system control | Validation: frontend contract/browser smoke | Evidence: `tests/test_frontend_contract.py`, runtime browser smoke pending | Status: CONCERNS
- NFR-007 | Area: Provenance | Target: VPS/Ubuntu exact artifacts contain every new source asset but no model binary; runtime remains exact-source bound | Validation: exact artifact build/validation and deployment tests | Evidence: `scripts/quality/build_exact_artifacts.py`, `scripts/quality/validate_exact_artifacts.py` | Status: PASS
- NFR-008 | Area: Compatibility | Target: The final shared worker head produces a valid Windows package and preserves existing Windows runtime contract semantics | Validation: Package Windows Worker plus shared worker contract tests; runtime-manual exact package/process/freshness evidence after production authorization | Evidence: GitHub Package Windows Worker, `tests/test_worker_contract.py` | Status: CONCERNS

## Runtime feedback

- Source stage: implementation/CI pending.
- VPS production: REQUIRED by policy; NOT AUTHORIZED by source authorization.
- Ubuntu production/model staging: REQUIRED by policy; NOT AUTHORIZED by source authorization.
- Windows Worker: REQUIRED by shared `worker/**` policy classification; NOT AUTHORIZED by source authorization; no Windows-specific Road feature is introduced.
