# Delivery Tasks: Water and road analytics profiles

- Specification: specs/018-water-road-analytics-profiles/spec.md
- Issue: #197
- Status: Production remediation

## Delivery tasks

- TASK-001: Preserve the historical PR #198 exact 42-path source record and all accepted water/road profile, API, frontend, model and runtime isolation behavior; never rewrite history to hide later production-learning defects.
- TASK-002: Keep `worker/analytics_profiles.py` water-v1/road-v1 defaults and deterministic class normalization unchanged by corrective diffs.
- TASK-003: Keep in-process and supervised Ubuntu YOLO profile semantics, tracking/speed/event ordering and shared worker source unchanged by corrective diffs.
- TASK-004: Preserve protected road media/model configuration and isolated `sea-speed-road-worker.service` behavior.
- TASK-005: Preserve exact Ubuntu installation/update/rollback/deployment identity and protected `road-worker.env` handling without extending browser worker control.
- TASK-006: Preserve additive generic API state/events/ROI/speed/objects and legacy Camera 1 compatibility; perform no corrective API/storage schema change.
- TASK-007: Preserve `/sea-speed/road/`, synchronized navigation and global Objects behavior; do not change frontend source in production-learning remediations.
- TASK-008: Preserve Road frontend exact VPS deployment behavior and model-binary exclusion from artifacts.
- TASK-009: Preserve telemetry semantics and no-secret/no-model repository boundaries.
- TASK-010: Retain existing unit/integration/frontend/deployment regression coverage for the original product behavior.
- TASK-011: Keep historical PR #198 exact 42/42 changed-file and green-CI evidence auditable; each production-learning correction has its own exact authorization/diff evidence.
- TASK-012: Merge every corrective PR only after fresh main/head/scope/review verification with expected-head protection and verify post-merge push/main quality.
- TASK-013: Do not mutate corrected production until a fresh exact merged-SHA production envelope with current fingerprint and execution intent is authorized.
- TASK-014: Treat Windows as NOT APPLICABLE to corrective diffs that contain no shared `worker/**`; preserve historical #198 Windows evidence and leave contour retirement to Issue #199.
- TASK-015: First correction: extend `scripts/operations/nginx_sea_speed_auth.py` with only exact Road worker M2M paths/methods on the existing private exact-peer listener, retaining deny-all catch-all, bearer forwarding and browser-control exclusion.
- TASK-016: First correction: update `deploy/worker/ubuntu/configure-analytics-profiles.py` so Road state/events URLs are derived only from the validated protected Camera 1 private M2M endpoint and fail closed for public/credential/non-private/loopback/missing-port/query/wrong-path origins; keep `road-worker.env.example` free of public API defaults.
- TASK-017: First correction: update focused Auth v1, analytics profile and Ubuntu deployment contract tests for exact private route/method matrices, tamper rejection, private-origin derivation, mode-0600 protected config and absence of public Road worker API defaults.
- TASK-018: Keep feature SDD current as `PRODUCTION_LEARNING`, including concrete root causes, complete adjacent-stage reviews, risk/test design, full eight-stage Deployment Transaction Audit and exact per-correction applicability.
- TASK-019: First correction: merge PR #200 only with the exact authorized 10 paths, VPS `CONNECTOR`, Ubuntu `ONE_COMMAND_FALLBACK`, Windows `NOT APPLICABLE`, and exact-head green PR Validation/Quality. Preserve `30e77e1f42397fddabc2a36fcfe922416a8efe57` as the first corrective source checkpoint.
- TASK-020: First correction runtime: after valid authorization, activate the corrected VPS private ingress first, then deploy/regenerate Ubuntu Road protected config and verify Road service without starting the main Water Worker unless its operator-desired state separately requires it.
- TASK-021: Final product acceptance: prove from the VPS side that `road1` is online, exact source is bound, frame number advances, events/objects are observable, clean preview start/media/stop is green, and public Authentik/Camera1 regressions remain green; worker-local POST logs are insufficient evidence.
- TASK-022: Second correction: include `sea-speed-auth-cutover.sh`, `nginx_cam1_direct_h264.py` and `nginx_sea_speed_auth.py` in the deterministic VPS exact artifact and validate their shell/Python syntax and source inventory before SSH.
- TASK-023: Second correction: make `.github/workflows/deploy-vps.yml` require the approved non-secret private topology, invoke one exact target deployment transaction, and reject deployment evidence unless `auth_v1_road_private_m2m=passed` with `runtime_verified` state.
- TASK-024: Second correction: extend `deploy/vps/deploy.sh` so exact source release staging includes Auth cutover/renderers; canonical invocation performs boundary `prepare -> expected SHA activate -> evidence`; already-current source fails closed when boundary acceptance fails; a new candidate source rolls back when boundary reconciliation rejects it.
- TASK-025: Second correction: extend `sea-speed-auth-cutover.sh` with `--require-protected-baseline`. Prove the current live boundary is already Authentik-protected with exact private listen/peer and Camera 1 machine routes before mutation; on post-mutation failure restore the captured root-only nginx backup, reload and re-verify the protected baseline; preserve legacy/manual non-automatic rollback semantics without the flag.
- TASK-026: Second correction: execute production-equivalent fault-path coverage through the real `deploy/vps/deploy.sh` with isolated fake runtime boundaries for successful boundary evidence, API candidate failure, Auth candidate failure after boundary self-rollback, and already-current-source boundary failure.
- TASK-027: Second correction: strengthen Auth v1 and quality architecture tests to require protected-baseline/rollback contract markers, canonical deploy integration, exact VPS Auth artifact contents and workflow policy binding.
- TASK-028: Second correction: maintain exactly the separately authorized 12 changed paths, open one PR linked to Issue #197/spec 018, declare VPS `CONNECTOR`, Ubuntu/Windows `NOT APPLICABLE`, operator actions expected 0 for this exact diff, and remediate only in-scope CI findings until exact-head PR Validation and aggregate Quality are green.
- TASK-029: Second correction: after exact-green merge and post-merge quality, compute a new production authorization fingerprint and obtain one fresh exact-SHA VPS `PRODUCTION APPROVED` + `Execution-Intent: EXECUTE` before any second-correction runtime mutation.
- TASK-030: Second correction runtime: run the protected VPS Connector transaction and require exact source, validated exact artifact, protected-baseline/candidate/rollback capability evidence and `auth_v1_road_private_m2m=passed`. Do not resume the pending Ubuntu first-correction runtime action until this VPS evidence is green.

## Requirements traceability

- AC-001 | Task: TASK-002,TASK-010 | Evidence: `tests/test_analytics_profiles.py` | Coverage: COVERED
- AC-002 | Task: TASK-002,TASK-010 | Evidence: water/road class normalization matrix in `tests/test_analytics_profiles.py` | Coverage: COVERED
- AC-003 | Task: TASK-003,TASK-010 | Evidence: unchanged worker source plus existing worker/AI supervision contract tests | Coverage: COVERED
- AC-004 | Task: TASK-006,TASK-010 | Evidence: existing generic analytics and legacy Camera 1 API contract tests | Coverage: COVERED
- AC-005 | Task: TASK-006,TASK-010 | Evidence: existing additive SQLite/global Objects API tests | Coverage: COVERED
- AC-006 | Task: TASK-007,TASK-010 | Evidence: existing frontend navigation/Road identity tests | Coverage: COVERED
- AC-007 | Task: TASK-007,TASK-010 | Evidence: existing Road frontend source tests plus later browser smoke | Coverage: COVERED
- AC-008 | Task: TASK-004,TASK-005,TASK-010 | Evidence: existing Ubuntu systemd/update/rollback/deployment tests | Coverage: COVERED
- AC-009 | Task: TASK-004,TASK-008,TASK-009,TASK-010 | Evidence: existing model preparation and exact-artifact rejection evidence | Coverage: COVERED
- AC-010 | Task: TASK-008,TASK-010 | Evidence: existing VPS deploy transaction tests | Coverage: COVERED
- AC-011 | Task: TASK-001,TASK-011,TASK-019,TASK-028 | Evidence: historical PR #198 exact 42/42, PR #200 exact 10/10, second correction exact 12/12 compare | Coverage: COVERED
- AC-012 | Task: TASK-012,TASK-019,TASK-028 | Evidence: corrective exact-head PR Validation/Quality, fresh merge gate and post-merge push/main quality | Coverage: COVERED
- AC-013 | Task: TASK-013,TASK-020,TASK-021,TASK-030 | Evidence: retained exact model/CUDA/protected road source plus corrected VPS/Ubuntu runtime identity | Coverage: RUNTIME-MANUAL | Reason: Hosted CI cannot prove production private-network ingress, protected Road config, physical relay/model continuity or actual VPS state freshness.
- AC-014 | Task: TASK-016,TASK-017 | Evidence: `tests/test_analytics_profiles.py` exact private-origin derivation and invalid-origin matrix | Coverage: COVERED
- AC-015 | Task: TASK-015,TASK-017,TASK-027 | Evidence: `tests/test_sea_speed_auth_v1.py` exact Road path/method/peer matrix, generic-route absence, tamper rejection and protected rollback contract | Coverage: COVERED
- AC-016 | Task: TASK-013,TASK-020,TASK-021,TASK-030 | Evidence: exact authorized VPS/Ubuntu deployment evidence, `road1` source/frame freshness, events/objects/preview and public Auth/Camera1 regression | Coverage: RUNTIME-MANUAL | Reason: Acceptance depends on protected production ZeroTier/nginx/service state and the physical Road media path.
- AC-017 | Task: TASK-022,TASK-027 | Evidence: deterministic VPS artifact inventory/syntax in `tests/quality/test_quality_architecture.py` and exact-artifact validator | Coverage: COVERED
- AC-018 | Task: TASK-024,TASK-026 | Evidence: `tests/test_vps_deploy_transaction.py` executes real `deploy/vps/deploy.sh` across success and failure paths | Coverage: COVERED
- AC-019 | Task: TASK-025,TASK-027 | Evidence: `tests/test_sea_speed_auth_v1.py` protected-baseline/rollback and exact security-boundary assertions | Coverage: COVERED
- AC-020 | Task: TASK-011,TASK-012,TASK-018,TASK-028,TASK-029,TASK-030 | Evidence: exact 12-path compare, exact-head CI/merge/post-merge quality, fresh exact-SHA VPS production authorization and deployment evidence | Coverage: COVERED + RUNTIME-MANUAL

## Definition of Done

- [x] Issue/spec/plan/tasks current for source authorization: Issue #197 records the second corrective source admission; feature 018 records both production-learning root causes, second exact 12-path VPS-only scope, updated risk/test design and full transaction audit.
- [ ] Exact changed-file scope verified: second corrective branch compare equals the separately authorized 12 paths exactly; historical PR #198 42/42 and PR #200 10/10 evidence remains unchanged.
- [ ] Required tests and evidence complete: VPS real-entrypoint transaction faults, Auth v1 protected-baseline/rollback contract, exact-artifact inventory, workflow policy and existing security/product regression suites pass.
- [ ] Required CI green: second corrective PR Validation and aggregate Quality integration succeed on the same exact final head; Ubuntu and Windows packaging/runtime are not applicable to this exact VPS-only source diff.
- [ ] Exact-green-head merge complete: fresh main/head/scope/review gate plus expected-head merge and post-merge push/main quality.
- [ ] Second corrective deployment state resolved: new merge remains production-pending until a fresh exact-SHA VPS production authorization; then protected VPS workflow yields a validated deployment manifest with `auth_v1_road_private_m2m=passed`.
- [ ] Pending first-correction Ubuntu deployment resumed only after VPS boundary acceptance; corrected Road protected config and service are resolved with exact deployment evidence while main Water Worker desired-stopped state remains preserved unless separately changed.
- [ ] Runtime/product acceptance resolved: corrected `road1` state is fresh on VPS with exact source and advancing frame number; Road events/objects/preview and public Auth/Camera1 regression are accepted.
- [x] Deferred work recorded: custom maritime model training/broader vessel taxonomy remain outside this Outcome; Issue #199 separately owns Windows-contour governance retirement; no frontend/API schema, worker inference or topology redesign is part of the second remediation.
- [ ] Risks resolved or explicitly accepted: performance/product runtime risks remain open until final Road freshness evidence; second-correction deployment/rollback risks require first production execution evidence; RISK-006 remains explicitly accepted.
- [x] Waivers resolved or current: no source-quality waiver is requested for corrective work.

## Completion gate

The second corrective source integration may advance only when the exact 12-path PR is green and merged with post-merge quality evidence. Source merge does not authorize runtime mutation. The next human checkpoint after source integration is one fresh exact-release VPS `PRODUCTION APPROVED` record with the current authorization fingerprint and `Execution-Intent: EXECUTE`. After that decision, the protected VPS Connector must produce exact `auth_v1_road_private_m2m=passed` evidence before the previously pending Ubuntu first-correction action may resume. Final `DONE` still requires VPS-observed Road freshness plus product/browser evidence. Windows is not an applicable corrective contour; historical evidence and Issue #199 remain distinct audit/governance concerns.
