# Delivery Tasks: Water and road analytics profiles

- Specification: specs/018-water-road-analytics-profiles/spec.md
- Issue: #197
- Status: Production remediation

## Delivery tasks

- TASK-001: Preserve the historical PR #198 exact 42-path source record and all accepted water/road profile, API, frontend, model and runtime isolation behavior; never rewrite history to hide the later production-learning defect.
- TASK-002: Keep `worker/analytics_profiles.py` water-v1/road-v1 defaults and deterministic class normalization unchanged by the corrective diff.
- TASK-003: Keep in-process and supervised Ubuntu YOLO profile semantics, tracking/speed/event ordering and shared worker source unchanged by the corrective diff.
- TASK-004: Preserve protected road media/model configuration and isolated `sea-speed-road-worker.service` behavior.
- TASK-005: Preserve exact Ubuntu installation/update/rollback/deployment identity and protected `road-worker.env` handling without extending browser worker control.
- TASK-006: Preserve additive generic API state/events/ROI/speed/objects and legacy Camera 1 compatibility; perform no corrective API/storage schema change.
- TASK-007: Preserve `/sea-speed/road/`, synchronized navigation and global Objects behavior; do not change frontend source in this remediation.
- TASK-008: Preserve Road frontend exact VPS deployment behavior and model-binary exclusion from artifacts.
- TASK-009: Preserve telemetry semantics and no-secret/no-model repository boundaries.
- TASK-010: Retain existing unit/integration/frontend/deployment regression coverage for the original product behavior.
- TASK-011: Keep historical PR #198 exact 42/42 changed-file and green-CI evidence auditable; the corrective PR has a distinct exact 10-path authorization.
- TASK-012: Merge the corrective PR only after fresh main/head/scope/review verification with expected-head protection and verify post-merge push/main quality.
- TASK-013: Do not mutate corrected production until a fresh exact merged-SHA production envelope with current fingerprint and execution intent is authorized.
- TASK-014: Treat Windows as NOT APPLICABLE to the corrective diff because no shared `worker/**` source is changed; preserve historical #198 Windows evidence and leave contour retirement to Issue #199.
- TASK-015: Extend `scripts/operations/nginx_sea_speed_auth.py` with only exact Road worker M2M paths/methods on the existing private exact-peer listener, retaining deny-all catch-all, bearer forwarding and browser-control exclusion.
- TASK-016: Update `deploy/worker/ubuntu/configure-analytics-profiles.py` so Road state/events URLs are derived only from the validated protected Camera 1 private M2M endpoint and fail closed for public/credential/non-private/loopback/missing-port/query/wrong-path origins; keep `road-worker.env.example` free of public API defaults.
- TASK-017: Update focused Auth v1, analytics profile and Ubuntu deployment contract tests to exercise exact private route/method matrices, tamper rejection, private-origin derivation, mode-0600 protected config and absence of public Road worker API defaults.
- TASK-018: Keep this feature SDD current as `PRODUCTION_LEARNING`, including concrete root cause, complete adjacent-stage review, risk/test design, full eight-stage Deployment Transaction Audit and exact VPS+Ubuntu corrective applicability.
- TASK-019: Open one corrective PR linked to Issue #197/spec 018, maintain exactly the authorized 10 changed paths, declare VPS `CONNECTOR`, Ubuntu `ONE_COMMAND_FALLBACK`, Windows `NOT APPLICABLE`, one expected operator runtime action, and remediate only in-scope CI findings until exact-head PR Validation and aggregate Quality integration are green.
- TASK-020: After fresh production authorization, activate the corrected VPS private ingress first, then deploy/regenerate the exact Ubuntu Road protected config and verify Road service without starting the main Water Worker unless its operator-desired state separately requires it.
- TASK-021: Prove corrected acceptance from the VPS side: `road1` worker online, corrected exact source commit, advancing frame number, events/objects observable, clean preview start/media/stop green, and public Authentik/Camera1 regression green; do not accept worker-local POST logs as sufficient evidence.

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
- AC-011 | Task: TASK-001,TASK-011,TASK-019 | Evidence: historical PR #198 exact 42/42 compare plus corrective PR exact 10/10 compare | Coverage: COVERED
- AC-012 | Task: TASK-012,TASK-019 | Evidence: corrective exact-head PR Validation/Quality, fresh merge gate and post-merge push/main quality | Coverage: COVERED
- AC-013 | Task: TASK-013,TASK-020,TASK-021 | Evidence: retained exact model/CUDA/protected road source evidence and later corrected VPS/Ubuntu runtime identity | Coverage: RUNTIME-MANUAL | Reason: Hosted CI cannot prove production private-network ingress, protected mode-0600 Road config, physical relay/model continuity or actual VPS state freshness.
- AC-014 | Task: TASK-016,TASK-017 | Evidence: `tests/test_analytics_profiles.py` exact private-origin derivation, helper execution and invalid-origin matrix | Coverage: COVERED
- AC-015 | Task: TASK-015,TASK-017 | Evidence: `tests/test_sea_speed_auth_v1.py` exact Road path/method/peer matrix, generic-route absence and tamper rejection | Coverage: COVERED
- AC-016 | Task: TASK-013,TASK-020,TASK-021 | Evidence: later exact-SHA VPS/Ubuntu deployment evidence, `road1` source/frame freshness, events/objects/preview and public Auth/Camera1 regression | Coverage: RUNTIME-MANUAL | Reason: The acceptance condition depends on protected production ZeroTier/nginx/service state and the physical Road media path, which hosted CI cannot observe.

## Definition of Done

- [x] Issue/spec/plan/tasks current: Issue #197 contains the fresh corrective authorization evidence and feature 018 records the M2M production learning, root cause, exact 10-path scope, risk/test design and VPS+Ubuntu-only corrective applicability.
- [ ] Exact changed-file scope verified: corrective branch compare equals the separately authorized 10 paths exactly; historical PR #198 42/42 evidence remains unchanged.
- [ ] Required tests and evidence complete: Auth v1 exact-route/tamper tests, protected Road private-origin/config tests, existing API/frontend/worker/deployment regression suites and repository integrity checks pass.
- [ ] Required CI green: corrective PR Validation and aggregate Quality integration succeed on the same exact final head; no Windows packaging is required for the corrective no-`worker/**` diff.
- [ ] Exact-green-head merge complete: fresh main/head/scope/review gate plus expected-head merge and post-merge push/main quality.
- [ ] Deployment state resolved: new corrected merge remains production-pending until a fresh exact-SHA production authorization; then VPS private ingress and Ubuntu corrected source/config are resolved with exact deployment evidence.
- [ ] Runtime acceptance resolved: corrected `road1` state is fresh on VPS with exact source and advancing frame number; Road events/objects/preview and public Auth/Camera1 regression are accepted; main Water Worker desired-stopped state remains preserved unless separately changed.
- [x] Deferred work recorded: custom maritime model training/broader vessel taxonomy remain outside this Outcome; Issue #199 separately owns Windows-contour governance retirement; no frontend/API schema or detection redesign is part of this remediation.
- [ ] Risks resolved or explicitly accepted: RISK-002/RISK-005/RISK-009 remain open until corrected production freshness evidence; RISK-006 remains explicitly accepted; security route-matrix risk is mitigated by exact behavioral tests.
- [x] Waivers resolved or current: no source-quality waiver is requested for the corrective work.

## Completion gate

The corrective source integration may advance only when the exact 10-path PR is green and merged with post-merge quality evidence. Source merge does not authorize runtime mutation. The next human checkpoint is one fresh exact-release `PRODUCTION APPROVED` record with the current authorization fingerprint and `Execution-Intent: EXECUTE`. After that decision, execute the VPS + Ubuntu corrective transaction and require VPS-observed Road freshness plus product/browser evidence. Windows is not an applicable corrective contour; the historical #198 record and separate Issue #199 remain distinct audit/governance concerns.
