# Feature Specification: Water detection activation and registry cap

- Feature: 022-water-detection-registry-cap
- Issue: #212
- Status: Implementing
- Owner outcome: Activate the existing Water analytics path safely and bound the shared SQLite Objects Registry to the newest 100 records for the temporary test phase.

## Product outcome

Water analytics uses the existing `water-v1` profile as the safe default: `cam1`, `models/yolo26x.pt`, `imgsz=960`, confidence `0.15`, ByteTrack, `SAMPLE_FPS=5`, accepting model class `boat` as domain object `vessel`. Road remains explicitly `road-v1` and unchanged.

The shared SQLite Objects Registry retains at most the newest 100 rows across Water and Road. The cap is enforced at database initialization and after every successful new event insertion. Ordering is deterministic by `detected_at DESC, object_id DESC`. Snapshot/media files and JSON event histories are not pruned in this Outcome.

Source integration does not start or stop production services. Water runtime activation occurs only after a separate exact-SHA production authorization.

## User scenarios

### Scenario 1 - Water detector resolves to the intended profile
Given the shared Water worker starts without an explicit analytics profile override, it resolves to `water-v1`, loads the existing YOLO26x configuration, accepts `boat` detections and publishes them as `vessel` without adopting Road classes.

### Scenario 2 - registry stays bounded during testing
Given Water and Road events continue arriving, the persistent SQLite registry keeps only the newest 100 rows across both cameras, using deterministic detected-time/object-id ordering.

### Scenario 3 - oversized existing registry is normalized on startup
Given the VPS already contains more than 100 registry rows when the new API release starts, initialization removes rows outside the newest 100 before normal API operation continues.

### Scenario 4 - production remains separately controlled
Given source changes are merged, neither VPS storage mutation nor Ubuntu Water service activation occurs until a separate exact-SHA production authorization is recorded and admitted.

## Requirements

- FR-001: `DEFAULT_PROFILE` MUST be `water-v1`.
- FR-002: `water-v1` MUST retain `models/yolo26x.pt`, `imgsz=960`, `conf=0.15`, `bytetrack.yaml`, `SAMPLE_FPS=5.0`, and `boat -> vessel` semantics.
- FR-003: `road-v1` MUST remain explicit and unchanged.
- FR-004: SQLite Objects Registry MUST contain no more than 100 rows after initialization completes.
- FR-005: After a successful new object insertion, SQLite Objects Registry MUST contain no more than 100 rows.
- FR-006: Retention MUST keep the newest records deterministically by `detected_at DESC, object_id DESC` and delete older rows only.
- FR-007: API routes, filters, object schema fields, soft-delete/edit behavior and pagination contracts MUST remain compatible.
- FR-008: Snapshot/media deletion and JSON event-history retention are out of scope.
- FR-009: Production activation of Water MUST remain separately exact-SHA authorized.
- FR-010: Mixed runtime rollout MUST be VPS first for storage-cap verification, then Ubuntu Worker for exact-source Water activation.

## Acceptance criteria

- AC-001: Analytics-profile tests prove no-argument profile resolution is `water-v1`, Water remains `boat -> vessel`, and Road defaults remain exact.
- AC-002: API contract tests prove initialization prunes an oversized registry to exactly the newest 100 rows.
- AC-003: API contract tests prove each successful insertion prunes the registry to at most 100 rows and preserves newest deterministic ordering.
- AC-004: Existing API/filter/edit/delete contract tests remain green.
- AC-005: Exact branch diff remains exactly the approved seven paths and contains no secrets/runtime artifacts.
- AC-006: PR Validation and aggregate Quality integration pass on the exact final head, followed by expected-head merge and exact-main post-merge Quality.
- AC-007: After separate production authorization, VPS runtime proves registry count <=100 after deployment and new detections.
- AC-008: After separate production authorization, Ubuntu runtime proves exact source/profile/model provenance, `sea-speed-worker.service` running, advancing Water frame/state/AI telemetry and `vessel` detections entering the registry.

## NFR assessment

- NFR-001 | Area: DATA_SAFETY | Target: pruning is deterministic and bounded to rows older than the newest 100 | Validation: API unit tests | Evidence: `tests/test_api_contract.py` | Status: CONCERNS
- NFR-002 | Area: RELIABILITY | Target: Water default cannot accidentally select Road semantics | Validation: analytics-profile tests | Evidence: `tests/test_analytics_profiles.py` | Status: PASS
- NFR-003 | Area: BACKWARD_COMPATIBILITY | Target: API URLs/schema/edit/delete behavior remains compatible | Validation: existing API contract suite | Evidence: `tests/test_api_contract.py` | Status: PASS
- NFR-004 | Area: RELEASE_PROVENANCE | Target: mixed release is exact-main, quality-gated, rollback-capable and separately production-authorized | Validation: PR/main quality plus runtime manifests | Evidence: GitHub Actions and Issue #212 | Status: CONCERNS

## Runtime feedback

- Current-main source already defines Water `water-v1` on YOLO26x but previously had `DEFAULT_PROFILE = road-v1`.
- Durable accepted Ubuntu evidence records Water desired state/service stopped while Road remains running.
- YOLO26x protected model staging and CUDA self-test were previously accepted; this Outcome does not change the model binary or detector parameters.
- Current SQLite persistence inserts rows without retention pruning; API page-size limits are not storage retention.
