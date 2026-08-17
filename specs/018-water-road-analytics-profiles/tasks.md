# Delivery Tasks: Water and road analytics profiles

- Specification: specs/018-water-road-analytics-profiles/spec.md
- Issue: #197
- Status: Production remediation

## Delivery tasks

- TASK-001: Preserve historical PR #198 exact 42-path source record and accepted water/road profile behavior; do not rewrite history to hide production-learning defects.
- TASK-002: Keep `worker/analytics_profiles.py` water-v1/road-v1 defaults and deterministic class normalization unchanged by corrective diffs.
- TASK-003: Keep worker/AI tracking/speed/event semantics unchanged by corrective diffs.
- TASK-004: Preserve protected road media/model configuration and isolated `sea-speed-road-worker.service` behavior.
- TASK-005: Preserve exact Ubuntu installation/update/rollback/deployment identity and protected `road-worker.env` handling without extending browser worker control.
- TASK-006: Preserve additive generic API state/events/ROI/speed/objects and legacy Camera 1 compatibility; perform no fifth-correction API/storage schema change.
- TASK-007: Preserve `/sea-speed/road/`, synchronized navigation and global Objects behavior; do not change frontend source in the fifth correction.
- TASK-008: Preserve Road frontend exact VPS deployment behavior and model-binary exclusion from artifacts.
- TASK-009: Preserve telemetry semantics and no-secret/no-model repository boundaries.
- TASK-010: Retain existing unit/integration/frontend/deployment regression coverage for the original product behavior.
- TASK-011: Keep historical PR #198 exact 42/42, PR #200 exact 10/10, PR #201 exact 12/12, PR #202 exact 11/11 and PR #203 exact 5/5 evidence auditable; every production-learning correction has its own authorization/diff evidence.
- TASK-012: Merge every corrective PR only after fresh main/head/scope/review verification with expected-head protection and post-merge push/main quality.
- TASK-013: Do not mutate corrected production until a fresh exact merged-SHA production envelope with current fingerprint and execution intent is authorized.
- TASK-014: Preserve Issue #199 / PR #204 prospective retirement of Windows while leaving historical #198 Windows evidence immutable; new #197 correction uses only active VPS/Ubuntu contour fields.
- TASK-015: Preserve exact Road worker M2M paths/methods on the existing private exact-peer listener.
- TASK-016: Preserve private Road state/events URL derivation from protected Camera 1 M2M origin.
- TASK-017: Preserve focused Auth/profile/Ubuntu contract tests.
- TASK-018: Keep feature SDD current as `PRODUCTION_LEARNING`, including concrete root causes, complete adjacent-stage reviews, risk/test design and full eight-stage Deployment Transaction Audit.
- TASK-019: Preserve first correction PR #200 checkpoint `30e77e1f42397fddabc2a36fcfe922416a8efe57`.
- TASK-020: Final product acceptance requires VPS-observed `road1` online state, exact source, advancing frame, source-bound events, isolated objects, clean preview and public Auth/Camera1 regression evidence.
- TASK-021: Preserve deterministic VPS artifact binding for Auth cutover and nginx renderers.
- TASK-022: Preserve canonical VPS requirement `auth_v1_road_private_m2m=passed` before VPS workflow success.
- TASK-023: Preserve `deploy/vps/deploy.sh` source plus Auth-boundary reconciliation and rollback semantics.
- TASK-024: Preserve protected-baseline nginx rollback in `sea-speed-auth-cutover.sh`.
- TASK-025: Preserve production-equivalent VPS deployment fault-path coverage.
- TASK-026: Preserve Auth v1 and quality architecture binding.
- TASK-027: Preserve second correction PR #201 checkpoint `f21b31d38e95179445e68e5543a1c934a744d514`.
- TASK-028: Preserve evidence that the authorized `f21b31...` VPS run failed at root privilege admission and safely rolled source back before least-privilege remediation.
- TASK-029: Preserve rejection of root SSH and broad `NOPASSWD`; use the fixed no-argument helper boundary.
- TASK-030: Preserve third correction fixed root helper, exact root-owned bundle and minimal sudoers boundary.
- TASK-031: Preserve installer rollback, exact digest/path/topology validation and pre-live-mutation helper status admission.
- TASK-032: Preserve deterministic VPS exact artifact and real deployment fault-path coverage.
- TASK-033: Preserve third correction PR #202 checkpoint merged as `e7dd921d569d9b93d9ac1be9113f61a162102b19`.
- TASK-034: Preserve accepted third-correction production evidence: fixed helper/no-root-shell plus `auth_v1_road_private_m2m=passed`.
- TASK-035: Preserve fourth production learning that `deploy-authorized.sh` previously omitted `configure-analytics-profiles.py` and could consume stale protected Road config.
- TASK-036: Preserve fourth correction PR #203 exact 5-path source record merged as `116dcf0f5f0d625f2b223a4549525ca7ddaa56d3`.
- TASK-037: Preserve fourth correction required exact-source inventory including `configure-analytics-profiles.py`.
- TASK-038: Preserve protected `worker.env` / optional `road-worker.env` backup without printing contents.
- TASK-039: Preserve exact target profile reconciliation against the fixed protected preview catalog before updater activation.
- TASK-040: Preserve configure-failure behavior: restore protected config and exit before updater/service activation.
- TASK-041: Preserve updater-failure behavior: restore protected config and predeployment Water/Road active state after updater-owned rollback.
- TASK-042: Preserve post-activation failure ordering: protected config restoration precedes previous-source rollback.
- TASK-043: Preserve Main Water Worker operator desired state across success/failure and prior Road state on failed transactions.
- TASK-044: Preserve deployment-manifest check `protected-road-profile-config-reconciled=passed` without serializing secrets/config values.
- TASK-045: Preserve focused fourth-correction deployment transaction tests.
- TASK-046: Record accepted fourth-correction source/production evidence: exact 5-path merge, protected config reconciliation, exact source/runtime activation, Road frame/state/AI progression and Water desired-stopped state.
- TASK-047: Record fifth production learning from final VPS acceptance: `ERROR=ROAD_STATE_SOURCE_1` while Road runtime/M2M freshness remained healthy; rollback was not indicated.
- TASK-048: Record source root cause: Ubuntu systemd provides exact `SEA_SPEED_SOURCE_COMMIT`, but `worker/ubuntu_worker_entrypoint.py` did not propagate it into shared state/event POST metadata.
- TASK-049: In `worker/ubuntu_worker_entrypoint.py`, add one exact lowercase 40-SHA validator for `SEA_SPEED_SOURCE_COMMIT` and invoke it before `BoundedYoloSupervisor` / shared worker main admission.
- TASK-050: Capture original shared `post_state` and `post_event`, wrap them in Ubuntu-specific functions that copy metadata and overwrite `worker_source_commit` with the validated environment-bound SHA, then rebind the shared module functions.
- TASK-051: Do not copy `SEA_SPEED_API_TOKEN`, HLS/media URLs, private API origin or any other environment/config values into provenance metadata; do not modify shared worker source, API/schema or deployment transaction source.
- TASK-052: Add `tests/test_ubuntu_worker_runtime_provenance.py` proving state/event injection, caller-identity override prevention, missing/uppercase/non-hex/wrong-length fail closed, no original POST on invalid identity, protected-environment non-propagation and startup validation ordering.
- TASK-053: Fifth correction source lifecycle: exact 5-path compare from authorization base `3544e0a4b6ef4afd4dddf4e0139f8218caeeeffb`, one PR linked to Issue #197/spec 018, Ubuntu REQUIRED with `ONE_COMMAND_FALLBACK`, VPS NOT REQUIRED, operator actions expected 1, Risk profile REQUIRED, Quality verdict not FAIL; remediate in-scope findings until exact-head PR Validation and aggregate Quality are green.
- TASK-054: Fifth correction production lifecycle: after exact-green merge/post-merge quality, compute a new production fingerprint and obtain exact-SHA `PRODUCTION APPROVED` + `Execution-Intent: EXECUTE`; execute one Ubuntu fallback only and do not repeat VPS deployment.
- TASK-055: Fifth correction runtime acceptance: exact Ubuntu deployment/runtime/service identity, advancing Road frame/state/AI, VPS `road1.worker_source_commit=<new SHA>`, source-bound recent Road events, isolated Road objects, clean preview start/HLS/media/stop, unchanged Water desired-stopped state and unchanged public Authentik protection.

## Requirements traceability

- AC-001 | Task: TASK-002,TASK-010 | Evidence: `tests/test_analytics_profiles.py` | Coverage: COVERED
- AC-002 | Task: TASK-002,TASK-010 | Evidence: water/road class normalization matrix | Coverage: COVERED
- AC-003 | Task: TASK-003,TASK-010 | Evidence: unchanged worker contract tests | Coverage: COVERED
- AC-004 | Task: TASK-006,TASK-010 | Evidence: existing generic analytics/legacy Camera 1 API contract | Coverage: COVERED
- AC-005 | Task: TASK-006,TASK-010 | Evidence: existing additive SQLite/global Objects tests | Coverage: COVERED
- AC-006 | Task: TASK-007,TASK-010 | Evidence: frontend navigation/Road identity tests | Coverage: COVERED
- AC-007 | Task: TASK-007,TASK-010 | Evidence: Road frontend tests plus runtime preview acceptance | Coverage: COVERED
- AC-008 | Task: TASK-004,TASK-005,TASK-010 | Evidence: Ubuntu systemd/update/rollback/deployment tests | Coverage: COVERED
- AC-009 | Task: TASK-004,TASK-008,TASK-009 | Evidence: model prep and exact-artifact exclusion | Coverage: COVERED
- AC-010 | Task: TASK-008,TASK-025 | Evidence: VPS deploy transaction tests | Coverage: COVERED
- AC-011 | Task: TASK-001,TASK-011,TASK-036,TASK-053 | Evidence: historical exact compares plus fifth exact 5-path compare | Coverage: COVERED
- AC-012 | Task: TASK-012,TASK-053 | Evidence: exact-head PR Validation/Quality, fresh merge gate, post-merge quality | Coverage: COVERED
- AC-013 | Task: TASK-013,TASK-020,TASK-055 | Evidence: retained model/CUDA/protected road source plus exact two-contour runtime identity | Coverage: RUNTIME-MANUAL | Reason: Hosted CI cannot prove protected production network/GPU/media state.
- AC-014 | Task: TASK-016,TASK-010 | Evidence: private-origin derivation tests | Coverage: COVERED
- AC-015 | Task: TASK-015,TASK-010 | Evidence: exact private route/method/peer Auth tests | Coverage: COVERED
- AC-016 | Task: TASK-013,TASK-020,TASK-055 | Evidence: exact VPS/Ubuntu state/source/frame/events/objects/preview/public regression | Coverage: RUNTIME-MANUAL | Reason: Acceptance depends on protected production state.
- AC-017 | Task: TASK-021,TASK-032 | Evidence: deterministic VPS artifact inventory/syntax | Coverage: COVERED
- AC-018 | Task: TASK-023,TASK-025,TASK-032 | Evidence: real `deploy/vps/deploy.sh` fault-path tests | Coverage: COVERED
- AC-019 | Task: TASK-024,TASK-010 | Evidence: protected-baseline/rollback Auth tests | Coverage: COVERED
- AC-020 | Task: TASK-027,TASK-028 | Evidence: PR #201 exact source and production failure evidence | Coverage: COVERED
- AC-021 | Task: TASK-030,TASK-032 | Evidence: `tests/test_vps_auth_privilege_boundary.py` | Coverage: COVERED
- AC-022 | Task: TASK-030,TASK-031 | Evidence: installer/sudoers contract and rollback markers | Coverage: COVERED
- AC-023 | Task: TASK-031,TASK-032 | Evidence: real deploy missing/mismatch pre-live-mutation tests | Coverage: COVERED
- AC-024 | Task: TASK-033,TASK-034 | Evidence: exact 11-path CI/merge plus accepted root bootstrap and Connector deployment | Coverage: COVERED
- AC-025 | Task: TASK-035,TASK-036,TASK-037,TASK-038,TASK-039,TASK-046 | Evidence: fourth exact 5-path source/deployment evidence | Coverage: COVERED
- AC-026 | Task: TASK-040,TASK-041,TASK-042,TASK-043,TASK-044,TASK-045,TASK-046 | Evidence: `tests/test_ubuntu_worker_deploy_authorized.py` plus accepted fourth production output | Coverage: COVERED
- AC-027 | Task: TASK-048,TASK-049,TASK-050,TASK-051,TASK-052 | Evidence: `tests/test_ubuntu_worker_runtime_provenance.py` | Coverage: COVERED
- AC-028 | Task: TASK-053 | Evidence: exact 5-path compare, modern two-contour Change Contract, exact-head CI/merge evidence | Coverage: COVERED
- AC-029 | Task: TASK-054,TASK-055 | Evidence: exact Ubuntu deployment manifest plus VPS-observed source-bound Road state/events/frame/objects/preview and regression checks | Coverage: RUNTIME-MANUAL | Reason: Final product acceptance depends on protected production runtime and media evidence.

## Definition of Done

- [x] Issue/spec/plan/tasks current: feature 018 records five production-learning root causes, current two-contour governance, fifth exact 5-path Ubuntu provenance scope, updated risk/test design and full eight-stage transaction audit.
- [ ] Exact changed-file scope verified: fifth corrective branch compare equals the authorized 5 paths exactly; historical 42/42, 10/10, 12/12, 11/11 and fourth 5/5 evidence remains unchanged.
- [ ] Required tests and evidence complete: focused runtime provenance assertions plus existing Ubuntu AI/profile/worker/API/deployment regressions pass.
- [ ] Required CI green: fifth corrective PR Validation and aggregate Quality integration succeed on the same exact final head; VPS is not applicable to this Ubuntu-only source diff.
- [ ] Exact-green-head merge complete: fresh main/head/scope/review gate, expected-head merge and post-merge push/main quality.
- [ ] Deployment state resolved: after separate exact-SHA production authorization, one Ubuntu fallback completes existing accepted `deploy-authorized.sh` transaction with valid exact deployment manifest; VPS `e7dd921...` boundary is not redeployed.
- [ ] Runtime acceptance resolved: `road1` state is fresh on VPS with exact new `worker_source_commit` and advancing frame, new Road events carry source provenance, objects/preview/public Auth regressions pass, and Main Water Worker desired-stopped state is preserved.
- [x] Deferred work recorded: broader maritime training/taxonomy remains separate; Issue #199 Windows-contour retirement is completed and historical #198 evidence remains immutable.
- [ ] Risks resolved or explicitly accepted: source-provenance runtime evidence risks remain open until exact production acceptance; all protected-input/security source risks have focused mitigations.
- [x] Waivers resolved or current: no source-quality waiver is requested.

## Completion gate

The fifth corrective source integration advances only when the exact 5-path PR is green and merged with post-merge quality. Source merge does not authorize runtime mutation. The next human checkpoint is one fresh exact-release production authorization/execution intent for the new merge SHA. This exact diff has Ubuntu `ONE_COMMAND_FALLBACK`, VPS `NOT APPLICABLE`, no retired Windows runtime field and one expected operator runtime action. After that one Ubuntu command succeeds, deterministic product acceptance continues without another routine confirmation. Final `DONE` requires VPS-observed exact Road state/event source provenance, advancing frames, isolated objects, clean preview media, public Auth/Camera1 regression evidence and preserved Water desired-stopped state.
