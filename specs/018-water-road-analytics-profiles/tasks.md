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
- TASK-006: Preserve additive generic API state/events/ROI/speed/objects and legacy Camera 1 compatibility; perform no corrective API/storage schema change.
- TASK-007: Preserve `/sea-speed/road/`, synchronized navigation and global Objects behavior; do not change frontend source in production-learning remediations.
- TASK-008: Preserve Road frontend exact VPS deployment behavior and model-binary exclusion from artifacts.
- TASK-009: Preserve telemetry semantics and no-secret/no-model repository boundaries.
- TASK-010: Retain existing unit/integration/frontend/deployment regression coverage for the original product behavior.
- TASK-011: Keep historical PR #198 exact 42/42, PR #200 exact 10/10, PR #201 exact 12/12 and PR #202 exact 11/11 evidence auditable; every production-learning correction has its own authorization/diff evidence.
- TASK-012: Merge every corrective PR only after fresh main/head/scope/review verification with expected-head protection and post-merge push/main quality.
- TASK-013: Do not mutate corrected production until a fresh exact merged-SHA production envelope with current fingerprint and execution intent is authorized.
- TASK-014: Treat Windows as NOT APPLICABLE to corrective diffs without shared `worker/**`; Issue #199 separately owns contour retirement.
- TASK-015: First correction preserved exact Road worker M2M paths/methods on the existing private exact-peer listener.
- TASK-016: First correction preserved private Road state/events URL derivation from protected Camera 1 M2M origin.
- TASK-017: First correction preserved focused Auth/profile/Ubuntu contract tests.
- TASK-018: Keep feature SDD current as `PRODUCTION_LEARNING`, including concrete root causes, complete adjacent-stage reviews, risk/test design and full eight-stage Deployment Transaction Audit.
- TASK-019: First correction PR #200 remains the exact 10-path checkpoint `30e77e1f42397fddabc2a36fcfe922416a8efe57`.
- TASK-020: Final product acceptance requires VPS-observed `road1` online state, exact source, advancing frame, events/objects, clean preview and public Auth/Camera1 regression evidence.
- TASK-021: Second correction packaged the Auth cutover and nginx renderers in the deterministic VPS exact artifact.
- TASK-022: Second correction made canonical VPS deployment require `auth_v1_road_private_m2m=passed` before workflow success.
- TASK-023: Second correction made `deploy/vps/deploy.sh` own source plus Auth-boundary reconciliation and source rollback.
- TASK-024: Second correction retained protected-baseline nginx rollback in `sea-speed-auth-cutover.sh`.
- TASK-025: Second correction retained production-equivalent deployment fault-path coverage.
- TASK-026: Second correction retained Auth v1 and quality architecture binding.
- TASK-027: Second correction PR #201 remains the exact 12-path VPS-only checkpoint `f21b31d38e95179445e68e5543a1c934a744d514`.
- TASK-028: Record that the authorized `f21b31...` VPS production run failed at root privilege admission (`sudo` password required) after candidate source activation and safely rolled source back to `30e77...`; Ubuntu remained paused.
- TASK-029: Reject root SSH and broad `NOPASSWD` as the remediation; use least-privilege option A.
- TASK-030: Third correction added the fixed no-argument root helper, exact root-owned bundle and minimal sudoers boundary.
- TASK-031: Third correction added installer rollback, exact digest/path/topology validation and pre-live-mutation helper status admission.
- TASK-032: Third correction extended deterministic VPS exact artifact and real deployment fault-path coverage.
- TASK-033: Third correction PR #202 remains the exact 11-path checkpoint merged as `e7dd921d569d9b93d9ac1be9113f61a162102b19`.
- TASK-034: Record accepted third-correction production evidence: root bootstrap proves non-root deploy user/fixed-helper-no-args/no-root-shell and canonical Connector VPS deployment records `auth_v1_road_private_m2m=passed`.
- TASK-035: Record fourth production learning: before Ubuntu mutation, inspect the target transaction and prove `deploy-authorized.sh` previously omitted `configure-analytics-profiles.py`, while `update-exact.sh` consumes pre-existing protected `road-worker.env`; therefore stale public Road API configuration could survive exact activation.
- TASK-036: Fourth correction must change exactly five paths: `deploy/worker/ubuntu/deploy-authorized.sh`, `tests/test_ubuntu_worker_deploy_authorized.py`, and feature 018 spec/plan/tasks.
- TASK-037: Update `deploy-authorized.sh` required exact-source inventory to include `configure-analytics-profiles.py` and keep workflow fallback transport unchanged.
- TASK-038: Before helper reconciliation, back up protected `worker.env` and optional `road-worker.env` with presence, owner and mode state sufficient for exact restoration; do not print contents.
- TASK-039: Run the exact target `configure-analytics-profiles.py` against `/var/lib/sea-speed-camera-preview/active/camera-preview-catalog.json` after production authorization/main admission and before updater activation; require resulting `road-worker.env` regular mode 600.
- TASK-040: If configure fails, restore protected config and exit before any updater/service activation.
- TASK-041: If updater activation fails after its own runtime restoration, restore protected config and explicitly re-establish the predeployment Water/Road active state so processes reload matching env.
- TASK-042: If post-activation exact identity verification fails, restore protected config before `rollback-exact.sh` for a different previous source; for same-source reconciliation failure restore the predeployment service state directly.
- TASK-043: Preserve Main Water Worker operator desired state across success/failure and preserve prior Road service state on failed transactions.
- TASK-044: Add a deployment-manifest check proving `protected-road-profile-config-reconciled=passed` without serializing secrets/config values.
- TASK-045: Extend focused tests to prove authorization/config/activation/verification/state-commit ordering, configure-failure non-activation, updater-failure config/service restoration, post-verify config-before-source rollback, desired-state preservation and secret-negative evidence.
- TASK-046: Fourth correction source lifecycle: exact 5-path compare, one PR linked to Issue #197/spec 018, Ubuntu REQUIRED with `ONE_COMMAND_FALLBACK`, VPS/Windows NOT APPLICABLE, operator actions expected 1, Risk profile REQUIRED, Quality verdict PASS/CONCERNS but not FAIL; remediate only in-scope findings until exact-head PR Validation and aggregate Quality are green.
- TASK-047: Fourth correction production lifecycle: after exact-green merge/post-merge quality, compute a new production fingerprint and obtain fresh exact-SHA `PRODUCTION APPROVED` + `Execution-Intent: EXECUTE`; execute one Ubuntu fallback only, with no repeat VPS deployment.
- TASK-048: Fourth correction runtime acceptance: exact Ubuntu source/runtime/service identity, protected config reconciliation marker, advancing Road frame/state/AI, VPS-observed `worker_online=true` with exact source and advancing frame, events/objects/clean preview, public Auth/Camera1 regression, and unchanged Water desired state.

## Requirements traceability

- AC-001 | Task: TASK-002,TASK-010 | Evidence: `tests/test_analytics_profiles.py` | Coverage: COVERED
- AC-002 | Task: TASK-002,TASK-010 | Evidence: water/road class normalization matrix | Coverage: COVERED
- AC-003 | Task: TASK-003,TASK-010 | Evidence: unchanged worker contract tests | Coverage: COVERED
- AC-004 | Task: TASK-006,TASK-010 | Evidence: existing generic analytics/legacy Camera 1 API contract | Coverage: COVERED
- AC-005 | Task: TASK-006,TASK-010 | Evidence: existing additive SQLite/global Objects tests | Coverage: COVERED
- AC-006 | Task: TASK-007,TASK-010 | Evidence: frontend navigation/Road identity tests | Coverage: COVERED
- AC-007 | Task: TASK-007,TASK-010 | Evidence: Road frontend tests plus runtime browser smoke | Coverage: COVERED
- AC-008 | Task: TASK-004,TASK-005,TASK-010 | Evidence: Ubuntu systemd/update/rollback/deployment tests | Coverage: COVERED
- AC-009 | Task: TASK-004,TASK-008,TASK-009 | Evidence: model prep and exact-artifact exclusion | Coverage: COVERED
- AC-010 | Task: TASK-008,TASK-025 | Evidence: VPS deploy transaction tests | Coverage: COVERED
- AC-011 | Task: TASK-001,TASK-011,TASK-019,TASK-027,TASK-033,TASK-046 | Evidence: historical exact compares plus fourth exact 5-path compare | Coverage: COVERED
- AC-012 | Task: TASK-012,TASK-046 | Evidence: exact-head PR Validation/Quality, fresh merge gate, post-merge quality | Coverage: COVERED
- AC-013 | Task: TASK-013,TASK-020,TASK-048 | Evidence: retained model/CUDA/protected road source plus corrected runtime identity | Coverage: RUNTIME-MANUAL | Reason: Hosted CI cannot prove protected production network/GPU/media state.
- AC-014 | Task: TASK-016,TASK-010 | Evidence: private-origin derivation tests | Coverage: COVERED
- AC-015 | Task: TASK-015,TASK-010 | Evidence: exact private route/method/peer Auth tests | Coverage: COVERED
- AC-016 | Task: TASK-013,TASK-020,TASK-048 | Evidence: exact VPS/Ubuntu runtime state/source/frame/events/objects/preview/public regression | Coverage: RUNTIME-MANUAL | Reason: Acceptance depends on protected production state.
- AC-017 | Task: TASK-021,TASK-032 | Evidence: deterministic VPS artifact inventory/syntax | Coverage: COVERED
- AC-018 | Task: TASK-023,TASK-025,TASK-032 | Evidence: real `deploy/vps/deploy.sh` fault-path tests | Coverage: COVERED
- AC-019 | Task: TASK-024,TASK-010 | Evidence: protected-baseline/rollback Auth tests | Coverage: COVERED
- AC-020 | Task: TASK-027,TASK-028 | Evidence: PR #201 exact source and production failure evidence | Coverage: COVERED
- AC-021 | Task: TASK-030,TASK-032 | Evidence: `tests/test_vps_auth_privilege_boundary.py` | Coverage: COVERED
- AC-022 | Task: TASK-030,TASK-031 | Evidence: installer/sudoers contract and rollback markers | Coverage: COVERED
- AC-023 | Task: TASK-031,TASK-032 | Evidence: real deploy missing/mismatch pre-live-mutation tests | Coverage: COVERED
- AC-024 | Task: TASK-033,TASK-034 | Evidence: exact 11-path CI/merge plus accepted root bootstrap and Connector deployment | Coverage: COVERED
- AC-025 | Task: TASK-035,TASK-036,TASK-037,TASK-038,TASK-039,TASK-046 | Evidence: exact 5-path compare and protected-config-before-activation source/test evidence | Coverage: COVERED
- AC-026 | Task: TASK-040,TASK-041,TASK-042,TASK-043,TASK-044,TASK-045 | Evidence: `tests/test_ubuntu_worker_deploy_authorized.py` failure-path/manifest assertions | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current: feature 018 records four production-learning root causes, fourth exact 5-path Ubuntu scope, updated risk/test design and full eight-stage transaction audit.
- [ ] Exact changed-file scope verified: fourth corrective branch compare equals the authorized 5 paths exactly; historical 42/42, 10/10, 12/12 and 11/11 evidence remains unchanged.
- [ ] Required tests and evidence complete: focused Ubuntu transaction ordering/config rollback/state-preservation/secret-negative assertions plus unchanged profile/updater/rollback regressions pass.
- [ ] Required CI green: fourth corrective PR Validation and aggregate Quality integration succeed on the same exact final head; VPS and Windows are not applicable to this Ubuntu-only source diff.
- [ ] Exact-green-head merge complete: fresh main/head/scope/review gate, expected-head merge and post-merge push/main quality.
- [ ] Deployment state resolved: after separate exact-SHA production authorization, one Ubuntu fallback completes corrected `deploy-authorized.sh` transaction with valid exact deployment manifest; accepted VPS `e7dd921...` boundary is not redeployed.
- [ ] Runtime acceptance resolved: `road1` state is fresh on VPS with exact new source and advancing frame, Road events/objects/preview and public Auth/Camera1 regressions are accepted, and Main Water Worker desired state is preserved.
- [x] Deferred work recorded: broader maritime training/taxonomy and Issue #199 Windows-contour retirement remain separate.
- [ ] Risks resolved or explicitly accepted: Ubuntu config/rollback/runtime risks remain open until exact production acceptance; product-owner RISK-006 remains accepted.
- [x] Waivers resolved or current: no source-quality waiver is requested.

## Completion gate

The fourth corrective source integration advances only when the exact 5-path PR is green and merged with post-merge quality. Source merge does not authorize runtime mutation. The next human checkpoint is one fresh exact-release production authorization/execution intent. This exact diff truthfully has Ubuntu `ONE_COMMAND_FALLBACK`, VPS/Windows `NOT APPLICABLE`, and one expected operator runtime action. After that one Ubuntu command succeeds, deterministic runtime/product acceptance continues without another routine confirmation. Final `DONE` requires VPS-observed Road freshness/events/objects/preview, public/Auth/Camera1 regression evidence and preserved Water desired state.
