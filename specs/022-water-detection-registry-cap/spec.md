# Feature Specification: Water detection activation and registry cap

- Feature: 022-water-detection-registry-cap
- Issue: #212
- Status: Implementing
- Owner outcome: Activate the existing Water analytics path safely and bound the shared SQLite Objects Registry to the newest 100 records for the temporary test phase.

## Product outcome

Water analytics uses the existing `water-v1` profile as the safe default: `cam1`, `models/yolo26x.pt`, `imgsz=960`, confidence `0.15`, ByteTrack, `SAMPLE_FPS=5`, accepting model class `boat` as domain object `vessel`. Road remains explicitly `road-v1` and unchanged.

The shared SQLite Objects Registry retains at most the newest 100 rows across Water and Road. The cap is enforced at database initialization and after every successful new event insertion. Ordering is deterministic by `detected_at DESC, object_id DESC`. Snapshot/media files and JSON event histories are not pruned in this Outcome.

The executable runtime target is the already merged exact main release `9e0cd96aa2f790f1ba806299c3dd4019e5572899`. Production learning does not change that release, the Outcome Contract, Water model/profile semantics, registry-cap behavior, or runtime contour set. It corrects only the truthful execution capability and pre-mutation sequence required to deliver that release safely.

## User scenarios

### Scenario 1 - Water detector resolves to the intended profile
Given the shared Water worker starts without an explicit analytics profile override, it resolves to `water-v1`, loads the existing YOLO26x configuration, accepts `boat` detections and publishes them as `vessel` without adopting Road classes.

### Scenario 2 - registry stays bounded during testing
Given Water and Road events continue arriving, the persistent SQLite registry keeps only the newest 100 rows across both cameras, using deterministic detected-time/object-id ordering.

### Scenario 3 - oversized existing registry is normalized on startup
Given the VPS already contains more than 100 registry rows when the new API release starts, initialization removes rows outside the newest 100 before normal API operation continues.

### Scenario 4 - production remains separately controlled
Given source changes are merged, neither VPS storage mutation nor Ubuntu Water service activation occurs until the exact release passes production admission and the separately authorized runtime sequence is executed.

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
- FR-011: For runtime target `9e0cd96aa2f790f1ba806299c3dd4019e5572899`, VPS execution capability MUST be treated as `ONE_COMMAND_FALLBACK` because the root-owned Auth privileged bundle is exact-source-bound; one repository-owned exact-source privilege-boundary bootstrap MUST pass before canonical Connector VPS deployment can cross the pre-live-mutation boundary.
- FR-012: Ubuntu Worker execution MUST remain `ONE_COMMAND_FALLBACK` unless restricted zero-touch transport is independently observed as provisioned. Worst-case operator actions for the MIXED release are therefore two, one per required fallback contour.

## Acceptance criteria

- AC-001: Analytics-profile tests prove no-argument profile resolution is `water-v1`, Water remains `boat -> vessel`, and Road defaults remain exact.
- AC-002: API contract tests prove initialization prunes an oversized registry to exactly the newest 100 rows.
- AC-003: API contract tests prove each successful insertion prunes the registry to at most 100 rows and preserves newest deterministic ordering.
- AC-004: Existing API/filter/edit/delete contract tests remain green.
- AC-005: Original product source remains the exact approved seven-path PR #213 release; the production-learning correction is limited to exactly this feature's `spec.md`, `plan.md`, and `tasks.md` and changes no executable source.
- AC-006: Original PR Validation and aggregate Quality succeed on the exact product head, expected-head merge produces runtime target `9e0cd96aa2f790f1ba806299c3dd4019e5572899`, and the production-learning correction passes its own exact-head PR Validation/Quality, expected-head merge, and post-merge Quality without creating a new runtime target.
- AC-007: After exact production authorization, the repository-owned VPS root privilege-boundary bootstrap passes for `9e0cd96aa2f790f1ba806299c3dd4019e5572899`, the subsequent canonical Connector VPS deployment is runtime-verified, and production proves registry count <=100 after deployment and new detections.
- AC-008: Only after VPS acceptance, Ubuntu runtime proves exact source/profile/model provenance, `sea-speed-worker.service` running, advancing Water frame/state/AI telemetry and `vessel` detections entering the registry; if restricted zero-touch transport is absent, exactly one repository-owned Ubuntu fallback action is used.

## NFR assessment

- NFR-001 | Area: DATA_SAFETY | Target: pruning is deterministic and bounded to rows older than the newest 100 | Validation: API unit tests plus production registry evidence | Evidence: `tests/test_api_contract.py` and Issue #212 | Status: CONCERNS
- NFR-002 | Area: RELIABILITY | Target: Water default cannot accidentally select Road semantics | Validation: analytics-profile tests | Evidence: `tests/test_analytics_profiles.py` | Status: PASS
- NFR-003 | Area: BACKWARD_COMPATIBILITY | Target: API URLs/schema/edit/delete behavior remains compatible | Validation: existing API contract suite | Evidence: `tests/test_api_contract.py` | Status: PASS
- NFR-004 | Area: RELEASE_PROVENANCE | Target: mixed release is exact-main, quality-gated, rollback-capable, separately production-authorized, and each required runtime contour uses its truthful execution capability | Validation: PR/main quality, production admission, exact-source privilege bootstrap, and runtime manifests | Evidence: GitHub Actions and Issue #212 | Status: CONCERNS

## Runtime feedback

- Original source integration is merged through PR #213 as exact runtime target `9e0cd96aa2f790f1ba806299c3dd4019e5572899`; `water-v1` is the safe default and SQLite retention is capped to newest 100 combined Water+Road rows in source.
- Final original exact-head evidence is PR Validation #449 / run `32094366745` and Quality integration #399 / run `32094366780`, both successful before expected-head merge. The protected deployment implementation independently requires a successful exact `push/main` Quality run before any production mutation.
- Durable accepted Ubuntu baseline records Water desired state/service stopped while Road remains running. YOLO26x protected model staging and CUDA self-test were previously accepted; this Outcome does not change the model binary or detector parameters.
- Exact release production authorization was granted for `9e0cd96aa2f790f1ba806299c3dd4019e5572899`. To preserve the approved VPS-first rollout, the durable Issue authority was initially recorded without execution intent and a VPS-only request was issued rather than triggering the parallel MIXED router.
- Production-learning evidence then established that `deploy/vps/deploy.sh` checks the root-owned Auth privilege bundle after exact release staging but before live application/service/current-release/nginx mutation, while the privileged bundle manifest requires its `source_sha` to equal the deployment request SHA. The last accepted root bundle is bound to an older runtime, so Connector-only VPS delivery of `9e0cd96...` cannot pass without an exact-source root bootstrap.
- Fresh production-learning source authorization is Issue #212 comment `5323340646`, bounded to this SDD triplet only. The executable runtime target remains `9e0cd96aa2f790f1ba806299c3dd4019e5572899`; no API/Worker/deploy/workflow/model behavior changes in this correction.