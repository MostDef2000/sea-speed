# Delivery Tasks: Water detection activation and registry cap

- Specification: specs/022-water-detection-registry-cap/spec.md
- Plan: specs/022-water-detection-registry-cap/plan.md
- Issue: #212
- Status: Implementing

## Delivery tasks

- T-001 [P0] Change shared analytics default from `road-v1` to `water-v1` without altering either profile's model/tracker/threshold/class-map values. COMPLETE in original source integration.
- T-002 [P0] Add deterministic combined SQLite Objects Registry retention helper with limit 100 and newest ordering `detected_at DESC, object_id DESC`. COMPLETE in original source integration.
- T-003 [P0] Enforce retention after database initialization and after every successful new object insertion. COMPLETE in original source integration.
- T-004 [P0] Add analytics-profile regression proving no-argument resolution selects Water and Road remains explicit/exact. COMPLETE in original source integration.
- T-005 [P0] Add API persistence regressions for oversized initialization and successful-insert pruning while preserving existing API behavior. COMPLETE in original source integration.
- T-006 [P0] Validate exact seven-path original scope, syntax/SDD/secret absence and canonical PR linkage. COMPLETE: PR #213 remained exactly seven approved paths.
- T-007 [P0] Reach exact-head PR Validation + aggregate Quality, refresh base/head/scope/reviews, and merge only the exact green head. COMPLETE: final head `1a619bc50ed5e6f8316bf13aa95f68a7c2e39a5e`, PR Validation #449 / `32094366745`, Quality #399 / `32094366780`, expected-head merge `9e0cd96aa2f790f1ba806299c3dd4019e5572899`.
- T-008 [P0] Resolve exact runtime release admission and production authority. IN PROGRESS: runtime target is exact `9e0cd96aa2f790f1ba806299c3dd4019e5572899`; production authorization fingerprint `3805756adc94a9419fdc4416aa61b01f4d6515c71cab5db4b4e757b41c2a4523` was granted with execution intent; durable Issue comment `5323137259` records the authority lines. Protected deployment code must independently verify successful exact `push/main` Quality before any runtime mutation.
- T-009 [P0] Record production learning from VPS privilege-boundary preflight. COMPLETE: current `deploy/vps/deploy.sh`, `install-auth-privilege-boundary.sh`, and `sea-speed-auth-privileged-helper.py` prove the root-owned Auth bundle is exact-source-bound and checked before accepted live application mutation; VPS truthful capability for `9e0cd96...` is `ONE_COMMAND_FALLBACK`.
- T-010 [P0] Integrate exactly the three authorized production-learning SDD paths under Issue #212 comment `5323340646`; require machine-valid `PRODUCTION_LEARNING` adjacent-stage audit, exact 3/3 diff, PR Validation + aggregate Quality on one exact head, fresh merge gate, expected-head merge and post-merge Quality. The corrective merge is source/control-plane evidence only and MUST NOT replace runtime target `9e0cd96...`. IN PROGRESS.
- T-011 [P0] Execute the single repository-owned VPS root privilege-boundary bootstrap on the canonical VPS from an exact `9e0cd96aa2f790f1ba806299c3dd4019e5572899` checkout for deployment user `sea-speed-deploy`; require exact-source/repository admission, `SEA_SPEED_AUTH_PRIVILEGE_INSTALL=PASS`, exact `SOURCE_SHA`, fixed helper/no-args scope, no root shell, fixed topology and transactional rollback evidence. PENDING RUNTIME.
- T-012 [P0] After T-011 PASS, run canonical Connector VPS deployment for exact runtime target `9e0cd96...`; require protected workflow exact-main Quality/authorization admission, exact release/deployment evidence with `runtimeVerified=true`, preserved Auth/private-M2M boundary and SQLite Objects Registry count <=100 after initialization and subsequent ingestion. PENDING RUNTIME.
- T-013 [P0] Only after T-012 acceptance, deploy/activate Ubuntu Water on exact runtime release and prove source/profile/model/service/frame/state/AI progression plus `vessel` detections entering registry; if restricted zero-touch transport is unavailable, use exactly one repository-owned Ubuntu fallback action. PENDING RUNTIME.
- T-014 [P0] Persist final corrective-source/bootstrap/VPS/registry/Ubuntu/Water evidence to Issue #212 and close only after every applicable source/runtime acceptance gate passes. PENDING.

## Requirements traceability

- AC-001 | Task: T-001,T-004 | Evidence: `tests/test_analytics_profiles.py` and original exact-head Quality | Coverage: COVERED
- AC-002 | Task: T-002,T-003,T-005 | Evidence: `tests/test_api_contract.py` initialization retention test | Coverage: COVERED
- AC-003 | Task: T-002,T-003,T-005 | Evidence: `tests/test_api_contract.py` insert retention test | Coverage: COVERED
- AC-004 | Task: T-005,T-007 | Evidence: existing API contract suite and original exact-head Quality #399 | Coverage: COVERED
- AC-005 | Task: T-006,T-009,T-010 | Evidence: original exact seven-path PR #213 plus exact three-path production-learning compare/CI; no executable path is authorized in the correction | Coverage: COVERED
- AC-006 | Task: T-007,T-008,T-010 | Evidence: original exact-head PR Validation #449, Quality #399, merge `9e0cd96...`, protected exact-main Quality admission before deployment, and corrective exact-head/merge/post-merge Quality | Coverage: COVERED
- AC-007 | Task: T-008,T-009,T-010,T-011,T-012,T-014 | Evidence: exact production authority, production-learning capability correction, exact-source VPS privilege-bootstrap PASS, exact VPS deployment manifest and registry-count runtime evidence | Coverage: RUNTIME-MANUAL | Reason: root-owned privilege state and production SQLite state require live VPS evidence
- AC-008 | Task: T-012,T-013,T-014 | Evidence: accepted VPS-first gate followed by Ubuntu deployment manifest or exact fallback evidence, Water exact source/model/profile/service/telemetry and resulting object record | Coverage: RUNTIME-MANUAL | Reason: physical camera/GPU/service runtime is outside hosted CI

## Definition of Done

- [ ] Issue/spec/plan/tasks current — production-learning correction is authored but must merge and receive post-merge Quality before main is current.
- [ ] Exact changed-file scope verified — original seven-path source is accepted; corrective branch must remain exactly the authorized three SDD paths through merge.
- [ ] Required tests and evidence complete — original source CI is complete; corrective CI, VPS bootstrap/deployment/registry evidence and Ubuntu Water acceptance remain.
- [ ] Required CI green — original exact-head CI is green; corrective exact-head and post-merge Quality remain, while runtime workflow must independently verify exact `push/main` Quality for `9e0cd96...` before mutation.
- [ ] Exact-green-head merge complete — original PR #213 is complete; corrective three-path PR remains.
- [ ] Deployment state resolved — exact runtime `9e0cd96...` still requires VPS root bootstrap, VPS Connector deployment/registry acceptance, then Ubuntu delivery.
- [ ] Runtime acceptance resolved — Water service/telemetry/object evidence remains.
- [x] Deferred work recorded — snapshot/media cleanup, JSON event retention and any retention-value redesign remain explicitly out of scope.
- [x] Risks resolved or explicitly accepted — irreversible loss of rows beyond newest 100 is accepted for the test phase; the observed root privilege-boundary constraint is addressed fail-closed by exact-source transactional bootstrap and the production-learning transaction audit.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`COMPLETE` is forbidden until original runtime target `9e0cd96aa2f790f1ba806299c3dd4019e5572899` remains accepted as the seven-path executable release, the exact three-path production-learning SDD correction is merged from an exact-green head with post-merge Quality, the protected runtime gate verifies successful exact `push/main` Quality and current production authorization, the single VPS root privilege-boundary bootstrap passes, canonical VPS deployment is `runtime_verified` with registry <=100, Ubuntu exact release/Water activation is accepted with advancing telemetry and `vessel` object evidence, and Issue #212 contains terminal sanitized evidence.