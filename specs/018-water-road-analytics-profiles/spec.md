# Specification: Water and road analytics profiles

- Issue: #197
- Status: Production remediation

## Product outcome

Sea Speed MUST run one profile-driven analytics implementation across two isolated operator domains. The existing main operator contour becomes `water-v1`, using a locally staged `yolo26x.pt` baseline and normalizing model-native `boat` into canonical maritime object type `vessel`. A new authenticated `/sea-speed/road/` contour runs `road-v1` against logical camera `road1`, with separate worker process, tracking state, configuration, event/state files and overlay/output state. Both Ubuntu analytics workers reuse the same immutable Python runtime and shared read-only model store. Protected runtime configuration resolves `road1` to its private camera source without exposing source credentials or the physical source through Git/frontend/API.

The original PR #198 changed shared `worker/**`, so canonical delivery policy classified that historical source release as VPS + Ubuntu Worker + Windows Worker. Windows was compatibility/update only and no Windows-specific Road feature, UI or service was introduced. The production-learning remediation described below changes no shared `worker/**`; its exact runtime contours are VPS + Ubuntu Worker/relay only. The historical #198 applicability remains audit truth and Issue #199 separately owns removal of the unused Windows production contour from governance.

Production acceptance of merged source `39cc330b61dc50aede4b809ee2dfc7a712b698d9` exposed a cross-boundary defect: the Road worker progressed frames and AI locally, but its generated state/event URLs targeted the public Authentik-protected `/sea-speed/**` surface while the dedicated private Worker-to-VPS ingress exposed only legacy Camera 1 paths. The first corrective design routes Road worker M2M traffic through the existing exact-peer private ingress and extends that ingress only with exact logical `road1` analytics paths and methods.

Production execution of the first corrective source `30e77e1f42397fddabc2a36fcfe922416a8efe57` exposed a second adjacent-stage defect: the protected VPS workflow successfully deployed API/frontend source but invoked only `deploy/vps/deploy.sh`; it never executed the source-managed `sea-speed-auth-cutover.sh` that owns the private nginx route matrix. Therefore a successful VPS deployment workflow did not prove that the `road1` private M2M routes were active. The second corrective design makes the canonical protected VPS Connector transaction stage the exact Auth cutover/renderers, require an already-protected rollback baseline, prepare and SHA-bind the nginx candidate, activate and verify the exact Road route matrix plus public Auth/Camera 1/H264 regressions, automatically restore the captured protected nginx backup on post-mutation failure, and record a passed `auth_v1_road_private_m2m` deployment-manifest check before the workflow may report runtime verification. This second corrective diff is VPS-only and does not change the pending Ubuntu Road configuration implementation.

Production execution of exact source `f21b31d38e95179445e68e5543a1c934a744d514` then exposed a third adjacent-stage defect: the deployment SSH account could update application files and restart the API but could not execute the root-only Auth v1 nginx transaction non-interactively. The deployment correctly rolled source back to `30e77e1f42397fddabc2a36fcfe922416a8efe57` after `sudo: a password is required`. The third corrective design MUST NOT grant CI a root shell or broad passwordless sudo. Instead it provisions one root-owned fixed helper with no command-line arguments; the helper accepts only a fixed request file, binds one exact source SHA and root-owned privileged bundle, validates staged release digests, uses the approved fixed private topology, and executes only the installed root-owned Auth cutover/renderers. Absence or mismatch of this boundary must stop deployment before any live source mutation.

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

### Scenario 6 - Historical shared worker compatibility remains auditable

The original #198 shared worker source was packaged through the existing Windows Worker pipeline because the then-current canonical policy classified shared `worker/**` as mixed. This production-learning remediation does not edit shared worker source or add any Windows Road surface; Windows is therefore not an applicable runtime contour for the corrective diff.

### Scenario 7 - Road Worker uses the private M2M boundary

Protected Ubuntu configuration derives the Road state and event endpoints from the already-provisioned private Camera 1 Worker-to-VPS M2M endpoint. The public Authentik-protected `/sea-speed/**` surface remains browser/operator-facing and is never used as the Road worker write path. The VPS private listener remains exact-peer, deny-by-default and exact-path/exact-method only.

### Scenario 8 - VPS deployment proves the Road M2M boundary

When an exact authorized VPS release is deployed by the protected Connector workflow, the same transaction must reconcile the private Auth v1 nginx boundary from exact release bytes. The workflow may report success only after the candidate is SHA-bound, the exact Road M2M routes and peer restriction verify, public Authentik/Camera 1/H264 regressions pass, and deployment evidence records the boundary check. A post-mutation boundary failure restores the captured already-protected nginx backup and verifies that rollback before the deployment is rejected.

### Scenario 9 - VPS deployment uses least privilege

The deployment SSH account remains non-root. One operator bootstrap installs a root-owned exact-SHA privileged bundle and a sudoers rule for only `/usr/local/sbin/sea-speed-auth-privileged-helper` with no arguments. Normal Connector deployment then writes a bounded request file and invokes that exact helper. The helper rejects arbitrary actions, arguments, release paths, symlinks, source-SHA mismatch, privileged-bundle mismatch and staged-asset digest mismatch. It never executes a script from the deployment-user-writable release directory as root.

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
- FR-019: The original #198 shared `worker/**` changes MUST remain historically compatible with the existing Windows Worker package/runtime contract; this remediation MUST NOT add or modify Windows-specific Road behavior.
- FR-020: Source integration MUST NOT perform production mutation. Every corrective VPS/Ubuntu activation requires a later exact-merged-SHA production authorization and contour-specific runtime evidence.
- FR-021: `configure-analytics-profiles.py` MUST derive `road1` state and event URLs only from the protected Camera 1 private M2M `SEA_SPEED_API_URL`. It MUST require credential-free private HTTP on a literal non-loopback RFC1918 IPv4 with explicit port and exact `/api/cam1/state` path, and MUST fail closed for public, HTTPS, credential-bearing, loopback, missing-port, query/fragment or wrong-path values.
- FR-022: The VPS private Worker ingress MUST add only exact `road1` worker paths: POST state, POST events, GET ROI, GET speed-config and GET speed-lines. It MUST preserve the exact peer allowlist, deny all other peers, reject all other paths through the catch-all, forward the bearer token, and MUST NOT expose generic `/api/analytics/**`, Objects, preview, browser worker-control or arbitrary service-control endpoints.
- FR-023: Public `/sea-speed/**` MUST remain protected by Authentik and Camera 1 media/browser behavior MUST remain unchanged. The corrective diff MUST NOT change API/event/state/storage schemas, detection/tracking/calibration/speed formulas, physical camera binding, model input, ZeroTier topology or `worker/**` source. Windows Worker is NOT APPLICABLE to this corrective diff.
- FR-024: The canonical protected VPS workflow MUST require Road private-M2M reconciliation for production deployments and MUST pass only the existing approved non-secret private topology values into the exact target transaction; it MUST NOT introduce a mutable arbitrary private-origin or peer deployment input.
- FR-025: The deterministic VPS exact artifact MUST contain `deploy/vps/sea-speed-auth-cutover.sh`, `scripts/operations/nginx_cam1_direct_h264.py` and `scripts/operations/nginx_sea_speed_auth.py`, validate their syntax, and bind them to the exact source SHA before SSH/runtime mutation.
- FR-026: Canonical VPS deployment MUST execute the Auth v1 `prepare -> SHA-bound activate -> verify` transaction from exact release bytes. With protected-baseline mode, activation MUST prove the current boundary is already Auth v1 protected before mutation and MUST automatically restore and verify the captured root-only nginx backup if post-mutation validation, reload, health or public-boundary acceptance fails.
- FR-027: VPS deployment MUST NOT report `runtime_verified` for the canonical Road corrective release unless deployment evidence contains `auth_v1_road_private_m2m=passed`. A boundary failure on an already-current source MUST be recorded as failed rather than treating the API/frontend source identity alone as acceptance.
- FR-028: The VPS deployment account MUST remain non-root and MUST NOT receive general passwordless `sudo`, shell, interpreter, nginx or arbitrary systemctl privileges. The only new passwordless privilege is the fixed root-owned `sea-speed-auth-privileged-helper` command with explicitly no command-line arguments.
- FR-029: The privilege-boundary installer MUST require an exact lowercase source SHA, verify the source checkout SHA and repository identity, reject a root deployment user, stage a root-owned helper/bundle, validate the sudoers fragment with `visudo`, install atomically and restore the previous helper/bundle/sudoers state on post-mutation installation failure.
- FR-030: The privileged helper MUST accept only the fixed request schema/actions `status|reconcile`, the canonical `/opt/sea-speed-deploy/releases/<exact-sha>` path and a root-owned bundle manifest for the same SHA; it MUST validate its own digest, all root-owned privileged assets and all staged release asset digests, reject symlink/path escape and use only the fixed approved Authentik/listen/peer topology.
- FR-031: `deploy/vps/deploy.sh` MUST stage the exact privilege assets and successfully run privileged `status` before bootstrap/current-release capture or any live API/frontend mutation. Reconcile MUST use the installed root-owned helper rather than `sudo bash` on a writable release script. Missing/mismatched privilege state MUST emit bootstrap-required evidence and leave the live source/current-release/deployment-manifest state unchanged.

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
- AC-011: Historical PR #198 remains auditable as the original exact 42/42 source integration; the first production-learning corrective PR changes exactly the separately authorized 10 remediation paths and no others.
- AC-012: Each corrective PR passes PR Validation and aggregate Quality integration on one exact final head; merge uses fresh main/head/scope/review checks and post-merge push/main quality succeeds. Windows packaging is not required when the exact corrective diff contains no `worker/**` source.
- AC-013: Production acceptance after separate authorization retains the previously established exact model/CUDA and protected road source evidence and verifies the corrected VPS + Ubuntu M2M path without requiring a Windows corrective rollout.
- AC-014: Behavioral tests prove Road state/events URLs are derived from the exact private Camera 1 M2M endpoint and all public, credential-bearing, non-private, loopback, missing-port and wrong-path alternatives fail closed.
- AC-015: Renderer/verifier tests prove the private ingress contains exactly the approved Camera 1 and Road worker endpoints with exact methods, exact peer restriction, no generic analytics route and no browser worker-control exposure while public Authentik protection remains intact.
- AC-016: After a new exact-SHA production authorization, VPS private ingress is active, Road protected config uses the private M2M origin, `road1` state becomes fresh with the exact corrected source commit and advancing frame number, Road events/objects are observable, clean preview start/media/stop passes, and Camera 1/public Authentik regression checks remain green.
- AC-017: Exact-artifact tests prove the VPS release contains the Auth cutover plus both nginx renderers and that all three are exact-source/syntax validated before production SSH.
- AC-018: VPS transaction tests execute the real `deploy/vps/deploy.sh` with isolated runtime boundaries and prove successful boundary evidence, candidate API failure rollback, Auth-boundary failure source rollback after boundary self-rollback, and fail-closed behavior when an already-current source cannot obtain boundary acceptance.
- AC-019: Auth cutover contract tests prove protected-baseline admission, SHA-bound candidate activation, protected-backup restoration markers and exact Road/private/public security invariants remain present while legacy/manual cutover semantics are preserved.
- AC-020: The second production-learning corrective PR changes exactly its separately approved 12-path VPS-only scope; after merge a fresh exact-SHA VPS production authorization is required, and Ubuntu corrective execution remains paused until VPS `auth_v1_road_private_m2m` runtime evidence is green.
- AC-021: Privilege-helper tests prove status/reconcile only, exact canonical release path, fixed topology, installed/staged digest binding, symlink/path-escape rejection and that only the root-owned installed cutover is executed.
- AC-022: Installer tests/contract evidence prove exact checkout/repository admission, non-root deployment user, one fixed no-argument sudo command, `visudo` validation and installation rollback markers without general root shell/interpreter privileges.
- AC-023: Real `deploy/vps/deploy.sh` transaction tests prove a missing or SHA-mismatched helper fails before any live API/frontend source mutation or deployment-manifest commit, while accepted privilege state retains existing success and rollback semantics.
- AC-024: The third production-learning corrective PR changes exactly its separately authorized 11 paths. After merge, production requires a new exact-SHA authorization; the first runtime action is one root/operator bootstrap for the exact privilege bundle, after which the same authorized VPS Connector deployment must obtain `auth_v1_road_private_m2m=passed` before Ubuntu resumes.

## NFR assessment

- NFR-001 | Area: Security | Target: No physical road source, camera userinfo, API token or model binary is committed or returned to browser/API | Validation: repository secret/binary policy plus focused profile tests | Evidence: `scripts/ci/validate_repo.py`, `tests/test_analytics_profiles.py` | Status: PASS
- NFR-002 | Area: Compatibility | Target: Legacy `/api/cam1/**` remains present and historical object rows require no destructive rewrite | Validation: API source/behavior tests and additive SQLite migration checks | Evidence: `tests/test_api_contract.py`, `api/app/main.py` | Status: PASS
- NFR-003 | Area: Isolation | Target: water and road use distinct logical IDs, state/events/config files, service/heartbeat/output and tracker processes | Validation: API/worker/systemd contract tests | Evidence: `tests/test_analytics_profiles.py`, `tests/test_ubuntu_worker_systemd.py` | Status: PASS
- NFR-004 | Area: Reliability | Target: Exact model activation is digest-bound, CUDA self-tested and has no silent fallback | Validation: model preparation source tests plus already collected production model evidence | Evidence: `deploy/worker/ubuntu/prepare-yolo-model.py`, Issue #197 runtime evidence | Status: PASS
- NFR-005 | Area: Performance | Target: Road Worker maintains advancing frames/AI under the corrected transport without OOM/degraded inference | Validation: source defaults plus runtime-manual corrected-state acceptance | Evidence: `worker/analytics_profiles.py`; corrected production runtime evidence pending | Status: CONCERNS
- NFR-006 | Area: Operator UX | Target: Road destination remains authenticated and functional without exposing arbitrary system control | Validation: frontend contract and post-remediation browser smoke | Evidence: `tests/test_frontend_contract.py`, runtime browser smoke pending | Status: CONCERNS
- NFR-007 | Area: Provenance | Target: Corrective VPS/Ubuntu release remains exact-source bound and contains no model binary or protected runtime inputs | Validation: exact artifact/release validation | Evidence: repository exact-artifact and release gates | Status: PASS
- NFR-008 | Area: Compatibility | Target: Historical #198 Windows compatibility evidence remains unchanged; the corrective diff edits no shared Worker source and requires no Windows package mutation | Validation: exact changed-file compare against corrective scope | Evidence: GitHub compare and Change Contract | Status: PASS
- NFR-009 | Area: Security | Target: Road Worker machine-to-machine traffic bypasses the browser Authentik flow only through an exact-peer, exact-path, exact-method private ingress and cannot expand to arbitrary analytics/control APIs | Validation: renderer/verifier endpoint matrix plus protected-config behavioral tests | Evidence: `tests/test_sea_speed_auth_v1.py`, `tests/test_analytics_profiles.py` | Status: PASS
- NFR-010 | Area: Reliability | Target: VPS API receives fresh Road state/events rather than redirect-mediated false-positive HTTP success | Validation: runtime-manual exact-SHA state freshness, source commit and frame progression checks | Evidence: post-remediation Issue #197 runtime acceptance | Status: CONCERNS
- NFR-011 | Area: Deployment integrity | Target: A successful protected VPS workflow proves both source deployment and the exact Road private-M2M nginx boundary from the same exact release | Validation: workflow policy, exact-artifact inventory and deployment-manifest check | Evidence: `.github/workflows/deploy-vps.yml`, `tests/quality/test_quality_architecture.py`, production deployment artifact | Status: CONCERNS
- NFR-012 | Area: Recovery | Target: A failed post-mutation Auth candidate cannot leave the canonical deployment transaction claiming success and can restore the captured already-protected nginx baseline without reintroducing retired public `/cams/**` semantics | Validation: protected-baseline/rollback contract and deployment fault-path tests | Evidence: `tests/test_sea_speed_auth_v1.py`, `tests/test_vps_deploy_transaction.py` | Status: CONCERNS
- NFR-013 | Area: Least privilege | Target: CI never gains arbitrary root execution; only one fixed no-argument root-owned helper can reconcile the exact digest-bound Auth boundary and missing/mismatched privilege state fails before live mutation | Validation: helper/installer tests plus real VPS deploy fault path | Evidence: `tests/test_vps_auth_privilege_boundary.py`, `tests/test_vps_deploy_transaction.py` | Status: CONCERNS until first production bootstrap and Connector acceptance

## Runtime feedback

- Original source integration: PR #198 merged as `39cc330b61dc50aede4b809ee2dfc7a712b698d9`; historical exact 42-path evidence remains unchanged.
- First production learning: Road worker/media/model/AI progression was healthy, but VPS `road1` state remained empty because generated Road worker writes targeted the public Authentik boundary while the private M2M ingress lacked generic `road1` routes. Redirect-following HTTP behavior made worker-side POST success insufficient evidence of API state commit.
- First corrective source authorization: a fresh six-field 10-path Scope was shown and immediately approved with `OUTCOME APPROVED` on 2026-08-17; PR #200 merged as `30e77e1f42397fddabc2a36fcfe922416a8efe57` with green post-merge quality.
- Second production learning: the authorized `30e77...` VPS run proved API/frontend source deployment but the protected workflow did not invoke `sea-speed-auth-cutover.sh`; therefore the new Road route matrix remained unproven/unactivated and Ubuntu corrective execution was correctly paused.
- Second corrective source authorization: a fresh six-field 12-path VPS-only Scope was shown and immediately approved with `OUTCOME APPROVED` on 2026-08-17; PR #201 merged as `f21b31d38e95179445e68e5543a1c934a744d514` with green post-merge quality.
- Third production learning: the authorized `f21b31...` VPS run reached the exact Auth-boundary step but the non-root deployment account could not run the root-only cutover without an interactive sudo password. The canonical transaction rolled the live source back to `30e77...`; Ubuntu remained paused. Broad root SSH/NOPASSWD shell was rejected in favor of least privilege.
- Third corrective source authorization: the operator selected privilege-remediation option A and immediately approved a fresh six-field exact 11-path VPS-only Scope with `OUTCOME APPROVED` on 2026-08-17.
- Third corrective VPS production: after exact-green merge, a new production authorization is required. Runtime capability is initially `ONE_COMMAND_FALLBACK` for one root bootstrap that installs the exact helper/bundle/sudoers boundary; the existing Connector then reruns the exact VPS transaction. Ubuntu and Windows are NOT APPLICABLE to the third source diff.
- Pending Ubuntu Worker/relay production from the first correction remains paused until the third corrective VPS boundary and `auth_v1_road_private_m2m=passed` evidence are green.
- Issue #199 remains the separate governance task for retiring the unused Windows contour; no historical evidence is rewritten by this remediation.
