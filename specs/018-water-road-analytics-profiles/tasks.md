# Delivery Tasks: Water and road analytics profiles

- Specification: specs/018-water-road-analytics-profiles/spec.md
- Issue: #197
- Status: In implementation

## Delivery tasks

- TASK-001: Keep repository writes within the exact authorized 42 paths recorded on Issue #197; no physical road camera source, credentials, model binary, Authentik/MediaMTX/Windows changes.
- TASK-002: Add `worker/analytics_profiles.py` with `water-v1`/`road-v1` defaults and deterministic class normalization.
- TASK-003: Route in-process and supervised Ubuntu YOLO detections through the profile registry and add semantic fields to events/state while preserving tracking/speed behavior.
- TASK-004: Add protected road configuration/model-preparation helpers and isolated `sea-speed-road-worker.service` using the shared exact source/runtime/model store.
- TASK-005: Extend install/update/rollback/authorized deployment/health contracts to preserve exact road service identity and separate road state without extending browser worker control.
- TASK-006: Generalize API state/events/ROI/speed/objects for supported analytics cameras, preserve legacy Camera 1 routes and perform only additive object DB migration.
- TASK-007: Add `/sea-speed/road/`, synchronized navigation and global multi-camera Objects Registry filters; use logical `road1` preview only.
- TASK-008: Add Road page to exact VPS artifact and transactional deploy/install/rollback/smoke handling; add profile/road assets to Ubuntu exact artifact while rejecting model binaries.
- TASK-009: Update telemetry schema/validator and repository/HTML validation for analytics semantics and Road frontend.
- TASK-010: Add/update unit/integration/frontend/deployment tests for profile filtering, API/data isolation, systemd/exact release behavior, artifacts, Road deploy and no-secret/no-model boundaries.
- TASK-011: Open one PR linked to Issue #197, maintain exact 42/42 changed-file scope and remediate only in-scope CI defects until PR Validation and Quality integration are green on one exact head.
- TASK-012: Merge only after fresh main/head/scope/review verification with expected-head protection; verify post-merge push/main quality.
- TASK-013: After source merge, do not mutate production until a fresh exact merged-SHA production envelope is authorized; then run the documented VPS/Ubuntu/model/dual-worker/browser acceptance transaction.

## Requirements traceability

- AC-001 | Task: TASK-002,TASK-010 | Evidence: `worker/analytics_profiles.py`, `tests/test_analytics_profiles.py` | Coverage: COVERED
- AC-002 | Task: TASK-002,TASK-010 | Evidence: water/road allowed/rejected class matrix in `tests/test_analytics_profiles.py` | Coverage: COVERED
- AC-003 | Task: TASK-003,TASK-010 | Evidence: worker tracking/AI supervision contract tests | Coverage: COVERED
- AC-004 | Task: TASK-006,TASK-010 | Evidence: generic analytics and legacy Camera 1 API tests | Coverage: COVERED
- AC-005 | Task: TASK-006,TASK-010 | Evidence: additive SQLite migration/global query contract tests | Coverage: COVERED
- AC-006 | Task: TASK-007,TASK-010 | Evidence: frontend navigation/Road logical identity tests | Coverage: COVERED
- AC-007 | Task: TASK-007,TASK-010 | Evidence: Road page source tests plus later browser smoke | Coverage: COVERED
- AC-008 | Task: TASK-004,TASK-005,TASK-010 | Evidence: Ubuntu systemd/update/rollback/deploy tests | Coverage: COVERED
- AC-009 | Task: TASK-004,TASK-008,TASK-009,TASK-010 | Evidence: model helper + repository/exact artifact rejection tests | Coverage: COVERED
- AC-010 | Task: TASK-008,TASK-010 | Evidence: VPS deploy transaction tests | Coverage: COVERED
- AC-011 | Task: TASK-001,TASK-011 | Evidence: exact GitHub changed-file compare and repository binary/secret validation | Coverage: COVERED
- AC-012 | Task: TASK-011,TASK-012 | Evidence: exact-head PR Validation/Quality, expected-head merge, post-merge push/main quality | Coverage: COVERED
- AC-013 | Task: TASK-013 | Evidence: runtime-manual exact model/worker/GPU/source-binding/browser evidence after separate production authorization | Coverage: RUNTIME-MANUAL

## Definition of Done

- [x] Issue/spec/plan/tasks current: Issue #197 and feature 018 record the authorized product outcome, risks, test design and runtime contour.
- [ ] Exact changed-file scope verified: final branch compare equals the authorized 42 paths and nothing else.
- [ ] Required tests and evidence complete: profile, Worker, API/data, frontend, Ubuntu exact-release, VPS deploy, telemetry and artifact tests pass.
- [ ] Required CI green: PR Validation and aggregate Quality integration succeed on the same exact final head.
- [ ] Exact-green-head merge complete: fresh main/head/scope/review gate plus expected-head merge.
- [ ] Deployment state resolved: source merge alone leaves production pending; later exact-SHA production transaction must resolve VPS + Ubuntu when authorized.
- [ ] Runtime acceptance resolved: later evidence must prove exact `yolo26x.pt` digest/CUDA load, both worker progression/resource headroom, protected road1 binding and browser smoke.
- [x] Deferred work recorded: custom maritime model training/broader vessel taxonomy remain outside this Outcome.
- [ ] Risks resolved or explicitly accepted: RISK-002/RISK-005 remain open until production dual-worker/model evidence; RISK-006 is explicitly accepted as baseline taxonomy limitation.
- [x] Waivers resolved or current: no source-quality waiver is requested.

## Completion gate

Source integration is ready for the production decision only after exact 42-path merge and successful post-merge quality. The overall Outcome becomes `DONE` only after a separately authorized VPS/Ubuntu production transaction proves the exact model, both worker contours, protected road camera binding, resource headroom and browser acceptance. Until then production is intentionally pending rather than implicitly authorized.
