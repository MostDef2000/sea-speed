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
- TASK-011: Keep historical PR #198 exact 42/42, PR #200 exact 10/10 and PR #201 exact 12/12 evidence auditable; every production-learning correction has its own authorization/diff evidence.
- TASK-012: Merge every corrective PR only after fresh main/head/scope/review verification with expected-head protection and post-merge push/main quality.
- TASK-013: Do not mutate corrected production until a fresh exact merged-SHA production envelope with current fingerprint and execution intent is authorized.
- TASK-014: Treat Windows as NOT APPLICABLE to corrective diffs without shared `worker/**`; Issue #199 separately owns contour retirement.
- TASK-015: First correction preserved exact Road worker M2M paths/methods on the existing private exact-peer listener.
- TASK-016: First correction preserved private Road state/events URL derivation from protected Camera 1 M2M origin.
- TASK-017: First correction preserved focused Auth/profile/Ubuntu contract tests.
- TASK-018: Keep feature SDD current as `PRODUCTION_LEARNING`, including concrete root causes, complete adjacent-stage reviews, risk/test design and full eight-stage Deployment Transaction Audit.
- TASK-019: First correction PR #200 remains the exact 10-path checkpoint `30e77e1f42397fddabc2a36fcfe922416a8efe57`.
- TASK-020: First correction Ubuntu runtime remains pending until the VPS boundary is accepted.
- TASK-021: Final product acceptance requires VPS-observed `road1` online state, exact source, advancing frame, events/objects, clean preview and public Auth/Camera1 regression evidence.
- TASK-022: Second correction packaged the Auth cutover and nginx renderers in the deterministic VPS exact artifact.
- TASK-023: Second correction made canonical VPS deployment require `auth_v1_road_private_m2m=passed` before workflow success.
- TASK-024: Second correction made `deploy/vps/deploy.sh` own source plus Auth-boundary reconciliation and source rollback.
- TASK-025: Second correction retained protected-baseline nginx rollback in `sea-speed-auth-cutover.sh`.
- TASK-026: Second correction retained production-equivalent deployment fault-path coverage.
- TASK-027: Second correction retained Auth v1 and quality architecture binding.
- TASK-028: Second correction PR #201 remains the exact 12-path VPS-only checkpoint `f21b31d38e95179445e68e5543a1c934a744d514`.
- TASK-029: Record that the authorized `f21b31...` VPS production run failed at root privilege admission (`sudo` password required) after candidate source activation and safely rolled source back to `30e77...`; Ubuntu remained paused.
- TASK-030: Reject root SSH and broad `NOPASSWD` as the remediation; use least-privilege option A.
- TASK-031: Add `deploy/vps/sea-speed-auth-privileged-helper.py` as one fixed no-argument root helper. It accepts only fixed request schema/actions, exact canonical release path, exact source SHA, root-owned bundle/digests and fixed approved topology; it executes only the root-owned installed Auth cutover/renderers.
- TASK-032: Add `deploy/vps/install-auth-privilege-boundary.sh` to verify exact checkout/repository identity, non-root deployment user, stage helper/bundle, validate a one-command no-argument sudoers rule with `visudo`, install root-owned files atomically and restore prior helper/bundle/sudoers on injected post-install failure.
- TASK-033: Update `deploy/vps/deploy.sh` so exact privilege assets are staged with the release, helper `status` is required before bootstrap/current-release capture or live source mutation, and reconcile uses only the fixed installed helper. Missing/mismatched helper emits `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES` and leaves live source/state unchanged.
- TASK-034: Extend deterministic VPS exact artifact build/validation to require installer/helper/cutover/renderers and validate shell/Python syntax and exact source inventory.
- TASK-035: Add `tests/test_vps_auth_privilege_boundary.py` for request/action/path/digest/symlink/fixed-topology/root-owned-execution behavior and least-privilege installer/sudoers contract.
- TASK-036: Extend `tests/test_vps_deploy_transaction.py` to execute the real deployment entrypoint and prove missing/mismatched privilege state fails before live mutation while accepted privilege state retains success/API rollback/Auth rollback/already-current/housekeeping behavior.
- TASK-037: Extend `tests/quality/test_quality_architecture.py` so exact artifacts and deployment architecture require the least-privilege assets and pre-mutation status gate.
- TASK-038: Third correction source lifecycle: maintain exactly the authorized 11 changed paths, one PR linked to Issue #197/spec 018, VPS REQUIRED with `ONE_COMMAND_FALLBACK`, Ubuntu/Windows NOT APPLICABLE, operator actions expected 1, Risk profile REQUIRED, Quality verdict PASS/CONCERNS but not FAIL; remediate only in-scope findings until exact-head PR Validation and aggregate Quality are green.
- TASK-039: Third correction production lifecycle: after exact-green merge/post-merge quality, compute a new production fingerprint and obtain fresh exact-SHA `PRODUCTION APPROVED` + `Execution-Intent: EXECUTE`; expose one root VPS server-pull/bootstrap command for the exact installer, then continue Connector VPS deployment without another routine confirmation.
- TASK-040: Third correction runtime acceptance: root bootstrap must prove exact SHA, non-root deploy user, fixed-helper/no-args sudo scope and no root shell grant; Connector must then prove helper status exact SHA, API/public health, Auth/private Road matrix and deployment manifest `auth_v1_road_private_m2m=passed` before pending Ubuntu correction resumes.

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
- AC-010 | Task: TASK-008,TASK-036 | Evidence: VPS deploy transaction tests | Coverage: COVERED
- AC-011 | Task: TASK-001,TASK-011,TASK-019,TASK-028,TASK-038 | Evidence: historical exact compares and third exact 11-path compare | Coverage: COVERED
- AC-012 | Task: TASK-012,TASK-038 | Evidence: exact-head PR Validation/Quality, fresh merge gate, post-merge quality | Coverage: COVERED
- AC-013 | Task: TASK-013,TASK-020,TASK-021,TASK-040 | Evidence: retained model/CUDA/protected road source plus corrected runtime identity | Coverage: RUNTIME-MANUAL | Reason: Hosted CI cannot prove protected production network/GPU/media state.
- AC-014 | Task: TASK-016,TASK-010 | Evidence: private-origin derivation tests | Coverage: COVERED
- AC-015 | Task: TASK-015,TASK-010 | Evidence: exact private route/method/peer Auth tests | Coverage: COVERED
- AC-016 | Task: TASK-013,TASK-021,TASK-040 | Evidence: exact VPS/Ubuntu runtime state/source/frame/events/objects/preview/public regression | Coverage: RUNTIME-MANUAL | Reason: Acceptance depends on protected production state.
- AC-017 | Task: TASK-022,TASK-034,TASK-037 | Evidence: deterministic VPS artifact inventory/syntax | Coverage: COVERED
- AC-018 | Task: TASK-024,TASK-026,TASK-036 | Evidence: real `deploy/vps/deploy.sh` fault-path tests | Coverage: COVERED
- AC-019 | Task: TASK-025,TASK-010 | Evidence: protected-baseline/rollback Auth tests | Coverage: COVERED
- AC-020 | Task: TASK-028,TASK-029 | Evidence: PR #201 exact source and production failure evidence | Coverage: COVERED
- AC-021 | Task: TASK-031,TASK-035 | Evidence: `tests/test_vps_auth_privilege_boundary.py` | Coverage: COVERED
- AC-022 | Task: TASK-032,TASK-035 | Evidence: installer/sudoers contract and rollback markers | Coverage: COVERED
- AC-023 | Task: TASK-033,TASK-036 | Evidence: real deploy missing/mismatch pre-live-mutation tests | Coverage: COVERED
- AC-024 | Task: TASK-038,TASK-039,TASK-040 | Evidence: exact 11-path CI/merge plus root bootstrap and Connector deployment | Coverage: RUNTIME-MANUAL | Reason: Root bootstrap and protected VPS Connector execution are production-only evidence.

## Definition of Done

- [x] Issue/spec/plan/tasks current: feature 018 records three production-learning root causes, third exact 11-path least-privilege scope, updated risk/test design and full eight-stage transaction audit.
- [ ] Exact changed-file scope verified: third corrective branch compare equals the authorized 11 paths exactly; historical 42/42, 10/10 and 12/12 evidence remains unchanged.
- [ ] Required tests and evidence complete: helper/installer contract, real VPS pre-mutation privilege fault path, exact-artifact inventory and existing Auth/product regressions pass.
- [ ] Required CI green: third corrective PR Validation and aggregate Quality integration succeed on the same exact final head; Ubuntu and Windows are not applicable to this VPS-only source diff.
- [ ] Exact-green-head merge complete: fresh main/head/scope/review gate, expected-head merge and post-merge push/main quality.
- [ ] Deployment state resolved: after separate exact-SHA production authorization, the one root privilege bootstrap and canonical VPS Connector deployment must both complete with exact identity and `auth_v1_road_private_m2m=passed`; until then production remains unresolved and Ubuntu stays paused.
- [ ] Runtime acceptance resolved: pending Ubuntu correction resumes only after VPS boundary acceptance; `road1` state is fresh on VPS with exact source and advancing frame, Road events/objects/preview and public Auth/Camera1 regressions are accepted; main Water Worker desired-stopped state is preserved unless separately changed.
- [x] Deferred work recorded: broader maritime training/taxonomy and Issue #199 Windows-contour retirement remain separate.
- [ ] Risks resolved or explicitly accepted: privilege/bootstrap/deployment and final runtime risks remain open until first accepted production run; product-owner RISK-006 remains accepted.
- [x] Waivers resolved or current: no source-quality waiver is requested.

## Completion gate

The third corrective source integration advances only when the exact 11-path PR is green and merged with post-merge quality. Source merge does not authorize runtime mutation. The next human checkpoint is one fresh exact-release production authorization/execution intent. Because this exact diff truthfully has VPS `ONE_COMMAND_FALLBACK`, the Orchestrator may then expose one repository-owned root bootstrap on the VPS; after it succeeds, deterministic Connector deployment continues without another routine confirmation. Ubuntu remains paused until VPS `auth_v1_road_private_m2m=passed` evidence is green. Final `DONE` still requires VPS-observed Road freshness and product/browser evidence.
