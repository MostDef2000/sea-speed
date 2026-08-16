# Implementation Plan: Water and road analytics profiles

- Specification: specs/018-water-road-analytics-profiles/spec.md
- Issue: #197
- Status: In implementation

## Architecture

1. **Profile normalization boundary.** `worker/analytics_profiles.py` owns detector defaults and model-class-to-domain mapping. Both the legacy in-process detector and supervised Ubuntu child normalize detections before they enter the existing tracking/speed/event pipeline.
2. **Process isolation.** The existing `sea-speed-worker.service` runs `water-v1`; `sea-speed-road-worker.service` runs `road-v1`. They share source bytes, immutable Python runtime and model store, but use separate process-local tracker state, working directories, outputs and heartbeats.
3. **Protected runtime binding.** A repository-owned configuration helper derives logical `road1` from the sanitized private preview catalog, writes protected mode-0600 road worker config, and never serializes camera credentials or physical source data to Git/frontend/API.
4. **Additive API generalization.** Supported analytics camera identities are `cam1` and `road1`. New generic routes use per-camera state/events/config paths; legacy Camera 1 routes delegate to the same helpers. SQLite is migrated with additive nullable semantic columns/indexes and historical rows remain intact.
5. **Operator contours.** Main remains water operator. New Road page uses generic road endpoints plus existing on-demand camera-preview APIs. Objects becomes global/multi-camera. Navigation is synchronized across Main/Objects/Cameras/Road.
6. **Release provenance.** VPS exact artifact/deployer includes Road HTML. Ubuntu artifact includes profile, road service/config and model-preparation assets; model binaries remain external protected runtime inputs. Shared `worker/**` also remains part of the existing Windows package/runtime contract, so the final head must pass Windows packaging/compatibility even though no Windows-specific Road feature is added.

## Decisions

### D-001 - Normalize at detector boundary
- Decision: Map model classes to domain semantics before tracking/event logic.
- Reason: Keeps ByteTrack, speed and event mechanics reusable and makes future detector replacement bounded to profile mapping.
- Alternatives rejected: Duplicate water worker; teach every downstream stage about model-specific labels.

### D-002 - Two Ubuntu services, one immutable runtime
- Decision: Separate water/road OS processes but share exact source/runtime/model store.
- Reason: ByteTrack state must never cross cameras, while duplicating multi-gigabyte Python/CUDA runtimes is operationally wasteful.
- Alternatives rejected: One process multiplexing two trackers; fully duplicated virtualenv/model stores.

### D-003 - Logical road identity only in source
- Decision: Repository knows `road1`; protected runtime inventory owns the private camera source.
- Reason: Existing preview architecture already provides credential separation and a sanitized relay catalog.
- Alternatives rejected: Commit RTSP URL/IP; expose arbitrary RTSP input through API/browser.

### D-004 - Additive API plus compatibility wrappers
- Decision: Add `/api/analytics/{camera_id}` and global `/api/objects` while retaining `/api/cam1/**`.
- Reason: Enables road without a flag-day frontend/worker migration and preserves existing integrations.
- Alternatives rejected: Rename/remove Camera 1 routes; duplicate a complete `/api/road1/**` API surface.

### D-005 - External model staging with exact digest
- Decision: Never package `yolo26x.pt`; require local file + digest and exact-runtime CUDA self-test.
- Reason: Model binaries are generated/runtime artifacts and production activation must not depend on mutable network downloads.
- Alternatives rejected: Commit model; allow Ultralytics implicit download; silently fall back to a smaller model.

### D-006 - Honor canonical shared-worker runtime classification
- Decision: Treat the same 42-path source diff as VPS + Ubuntu Worker + Windows Worker because canonical delivery policy applies shared `worker/**` runtime source to both worker contours.
- Reason: Change Contract applicability is derived from source paths and cannot be narrowed by product intent. Windows therefore receives compatibility/package/runtime verification, not a Road-specific feature surface.
- Alternatives rejected: falsely declare Windows `NOT REQUIRED`; weaken the policy classifier; add unrelated Windows-specific feature code.

## Affected contours

- Repository: Worker, Ubuntu deployment, VPS API/frontend/deploy, telemetry/quality/tests and feature 018 SDD within the exact 42 paths.
- VPS: REQUIRED after source merge and separate production authorization.
- Ubuntu Worker: REQUIRED after source merge and separate production authorization.
- Ubuntu private preview relay: implementation unchanged; protected runtime catalog may need a `road1` entry.
- Windows Worker: REQUIRED because shared `worker/**` changed; compatibility/update only, with no Windows-specific Road feature.
- Security: protected camera/model input boundary must remain fail closed; no new arbitrary service or RTSP input surface.

## Validation

- Unit: profile defaults/filtering/normalization, telemetry semantic validation, deterministic source contracts.
- Integration: API per-camera isolation/global registry, systemd/deploy/update/rollback exact identity, exact artifacts, VPS transaction Road state, shared worker compatibility.
- End-to-end source: HTML navigation/Road endpoint contracts, Package Windows Worker, exact final-head PR Validation and Quality integration.
- Runtime-manual after separate production authorization: model digest/CUDA self-test; water/road Ubuntu frame-state-AI progression; resource headroom/no OOM; protected road1 binding; exact Windows package/install/source/process/freshness/applicable telemetry; browser Main/Road smoke.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: logical road1 only in repository; protected catalog/env; repository secret/binary scanning; API never accepts arbitrary RTSP | Validation: source tests + runtime protected-config evidence | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: PERF | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: independent supervised inference processes, bounded 5 FPS baseline, explicit dual-worker production resource gate and no silent downgrade | Validation: runtime-manual VRAM/utilization/progression/OOM evidence | Residual risk: MEDIUM until production gate | Owner: Delivery Orchestrator | Status: OPEN
- RISK-003 | Category: DATA | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: additive nullable SQLite columns/indexes, no row rewrite/delete, camera/profile isolation and global query tests | Validation: API contract/migration tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: normalize before unchanged tracking/speed pipeline; child/in-process paths share one profile registry | Validation: worker/AI supervision and profile tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: separate road service/env/heartbeat/output, exact updater/rollback identity checks, Road deploy rollback state, protected model preparation | Validation: Ubuntu/VPS transaction tests + production exact runtime evidence | Residual risk: MEDIUM until runtime acceptance | Owner: Delivery Orchestrator | Status: OPEN
- RISK-006 | Category: BUS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: water baseline explicitly maps only COCO `boat`; future maritime expansion remains profile-level without false motion-only objects | Validation: class rejection tests and event contract | Residual risk: MEDIUM because baseline class coverage is intentionally narrow | Owner: Product owner | Status: ACCEPTED
- RISK-007 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: preserve legacy no-profile defaults in shared worker paths; require final-head Windows package plus existing worker contract tests; no Windows-specific Road surface | Validation: Package Windows Worker and later exact Windows runtime identity/freshness evidence | Residual risk: MEDIUM until Windows runtime acceptance | Owner: Delivery Orchestrator | Status: OPEN

## Test design

- TEST-001 | Covers: AC-001,AC-002,RISK-004,RISK-006 | Level: unit | Priority: P0 | Evidence: `tests/test_analytics_profiles.py`
- TEST-002 | Covers: AC-003,RISK-004,RISK-007 | Level: integration | Priority: P0 | Evidence: `tests/test_worker_contract.py`, `tests/test_worker_tracking_overlay.py`, `tests/test_ubuntu_worker_ai_supervision.py`
- TEST-003 | Covers: AC-004,AC-005,RISK-003 | Level: integration | Priority: P0 | Evidence: `tests/test_api_contract.py`
- TEST-004 | Covers: AC-006,AC-007 | Level: end-to-end | Priority: P1 | Evidence: `tests/test_frontend_contract.py` plus post-deploy browser smoke
- TEST-005 | Covers: AC-008,RISK-005 | Level: integration | Priority: P0 | Evidence: Ubuntu systemd/update/rollback/deploy-authorized test family
- TEST-006 | Covers: AC-009,RISK-001,RISK-005 | Level: integration | Priority: P0 | Evidence: `tests/test_analytics_profiles.py`, exact-artifact tests, runtime model-preparation evidence
- TEST-007 | Covers: AC-010,RISK-005 | Level: integration | Priority: P0 | Evidence: `tests/test_vps_deploy_transaction.py`
- TEST-008 | Covers: AC-011,AC-012 | Level: integration | Priority: P0 | Evidence: exact GitHub compare, PR Validation, Quality integration, Package Windows Worker and post-merge quality
- TEST-009 | Covers: AC-013,RISK-001,RISK-002,RISK-005,RISK-007 | Level: runtime-manual | Priority: P0 | Evidence: later exact-SHA VPS/Ubuntu/Windows deployment evidence, model digest/CUDA proof, two Ubuntu worker progression gates, GPU metrics, protected catalog identity, Windows package/process/freshness identity and browser smoke

## Correct-course check

- Trigger: MATERIAL_SCOPE_CHANGE
- Issue impact: Issue #197 retains the same product outcome and exact 42 paths; runtime applicability is corrected from VPS+Ubuntu to VPS+Ubuntu+Windows because canonical policy applies shared `worker/**` to both worker contours.
- Specification impact: Feature 018 now explicitly requires Windows compatibility/package/runtime evidence without adding Windows-specific Road behavior.
- Plan impact: Adds the canonical Windows compatibility contour and its package/runtime evidence to rollout, rollback and risk/test design.
- Tasks impact: Exact 42-path implementation remains unchanged; source and production completion now include the policy-derived Windows contour.
- Authorization impact: A complete six-field corrected Scope was shown and immediately re-authorized with `OUTCOME APPROVED`; production remains separately unauthorized.
- Follow-up: Complete exact-green source merge, then request a fresh exact-merge production authorization before any VPS/Ubuntu/Windows/model/runtime mutation.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production unchanged | Retry: repair exact-main/quality/production authorization envelope | Rollback: NOT REQUIRED | Evidence: current-main first-parent + exact quality + production authorization verifier
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: production unchanged; candidate artifacts/model may be staged only under protected transaction | Retry: correct missing protected model/catalog/env/package input | Rollback: delete/reject candidate only | Evidence: exact artifacts, Windows package, model SHA and protected configuration checks
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS, Ubuntu and/or Windows exact source may be active only inside its repository-owned transaction | Retry: recover actual state first | Rollback: previous exact contour release/package | Evidence: per-contour deploy/update transaction logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate cannot be accepted without all required contour gates | Retry: only after root-cause remediation; no model downgrade | Rollback: repository-owned previous exact contour identity | Evidence: VPS health/smoke, Ubuntu water/road progression, CUDA/model digest/GPU health, Windows source/process/freshness/telemetry
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: acceptance unresolved if exact deployment identity/manifests cannot commit | Retry: read actual runtime first | Rollback: use previous exact recorded target | Evidence: VPS/Ubuntu/Windows deployment manifests and active source/runtime IDs
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime stays accepted unless housekeeping affects active model/source/package | Retry: independent cleanup | Rollback: NOT REQUIRED solely for stale files | Evidence: deploy logs/model store/package inventory
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: runtime may be healthy but Outcome remains incomplete | Retry: recollect exact evidence without unnecessary mutation | Rollback: decide from actual runtime health | Evidence: Issue #197 per-contour deployment/runtime/browser evidence
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: unknown if rollback verification also fails; automated work stops | Retry: read-only recovery plus separately authorized repair | Rollback: no recursive guessing | Evidence: rollback source/runtime/package identity and service/process state

- Adjacent-stage review: NOT REQUIRED — this correction is a source-scope/runtime-applicability change, not a production-learning retry.

## Rollout and rollback

- Source rollout: branch -> exact 42-path compare -> PR linked #197 -> exact-head PR Validation + Quality + Package Windows Worker -> fresh main/head/scope/review -> expected-head merge -> post-merge quality.
- Production rollout: only after fresh exact merged-SHA production authorization; VPS additive API/frontend first, then protected model staging/CUDA gate, water profile activation, protected road1 config, road service activation, dual-worker resource/progression gate, then exact Windows package/update verification, then browser smoke.
- Production rollback: keep prior VPS release, prior Ubuntu exact source/runtime and prior Windows exact package/install identity as contour-specific rollback targets captured immediately before mutation. Reject model/profile candidate before state commit where possible. Do not auto-select a smaller model.

## Runtime feedback

- Source integration: PENDING.
- Production acceptance: PENDING separate exact-SHA authorization for VPS + Ubuntu Worker + Windows Worker.
- Deferred cleanup: custom maritime model training and broader vessel taxonomy are explicitly outside this Outcome.
