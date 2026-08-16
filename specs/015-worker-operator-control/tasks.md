# Delivery Tasks: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Plan: specs/015-worker-operator-control/plan.md
- Issue: #178
- Status: VPS release-pruning remediation validation

## Delivery tasks

- T-001 [P0] Implement the bounded Ubuntu worker-control agent for status/start/stop of `sea-speed-worker.service` only. COMPLETE in merged PR #179.
- T-002 [P0] Install an independent `sea-speed-worker-control.service` using the exact release source. COMPLETE in merged PR #179 source.
- T-003 [P0] Add VPS FastAPI worker-control routes with trusted browser identity, private-origin validation, bearer authentication and bounded timeouts. COMPLETE in merged PR #179 source.
- T-004 [P1] Add a distinct worker-control button to the Operator UI while preserving Camera 1 HLS and existing live Play/Stop controls. COMPLETE in merged PR #179 source.
- T-005 [P0] Preserve operator desired `running|stopped` state through exact updater and rollback semantics. COMPLETE in merged PR #179 source.
- T-006 [P0] Keep Ubuntu-to-VPS private ingress restricted to existing telemetry/config endpoints; worker-control routes remain absent. COMPLETE in merged PR #179 source.
- T-007 [P0] Maintain focused source tests for agent/API security, UI/media invariants, systemd independence and maintenance behavior. COMPLETE for PR #179/#180 source; aggregate CI remains authoritative on later exact heads.
- T-008 [P0] Validate the active approved diff and linked SDD; open the bounded remediation PR and reach exact-head CI green.
- T-009 [P0] Re-read main/head/scope/reviews and merge only the exact green remediation head with expected-head protection.
- T-010 [P0] Stop at the production boundary after remediation merge until the applicable exact-SHA production authorization is current; then collect required runtime evidence.
- T-011 [P0] Add the fixed `sea_speed_worker_control_v1` marker to successful Ubuntu agent responses and make VPS FastAPI reject a missing/mismatched marker before returning success. COMPLETE in merged PR #180.
- T-012 [P0] Add deterministic `ubuntu-worker` exact-artifact build/validation as release-specific provenance while preserving the existing quality-evidence v1 `vps`/legacy-`edge` contract. COMPLETE in merged PR #180.
- T-013 [P0] Change the VPS exact-deployment default origin-health probe from stale `127.0.0.1:8000` to accepted Auth v1 origin `127.0.0.1:8010`, preserving the single verifier used for candidate and automatic rollback checks. COMPLETE in merged PR #181.
- T-014 [P0] Add regression evidence for the canonical 8010 deployment/rollback probe and record run #25/restored-baseline production learning in feature 015. COMPLETE in merged PR #181.
- T-015 [P0] Align the two historical deploy-contract assertions exposed by exact-head CI (`test_camera_preview_gallery.py` and `test_sea_speed_auth_v1.py`) with canonical port 8010 without changing their unrelated media/auth assertions. COMPLETE in merged PR #181.
- T-016 [P0] Replace Deploy VPS first-parent membership pipeline with a full-consumption explicit match flag that remains strict under `set -o pipefail` and rejects non-first-parent targets. COMPLETE in merged PR #182.
- T-017 [P0] Add regression evidence that forbids the unsafe `git rev-list --first-parent ... | grep -q` pattern, requires the pipefail-safe guard, and record run #26 as a pre-SSH production-learning false-negative. COMPLETE in merged PR #182.
- T-018 [P0] Make stale VPS release pruning best-effort after verified state persistence: never prune current/previous, conditionally remove only older releases, and warn rather than fail when an older release cannot be removed.
- T-019 [P0] Add regression evidence for protected rollback-pair pruning, non-fatal stale cleanup failure and ordering of state/manifest persistence before pruning; record Deploy VPS run #27 production learning.
- T-020 [P0] After exact-green merge, verify push/main quality, resolve the actual post-run #27 VPS state read-only, obtain fresh exact-SHA production authorization and require a complete successful Deploy VPS evidence bundle before Ubuntu continuation.

## Active remediation scope

The current correct-course source gate is exactly these 5 paths; historical PR/scopes remain immutable audit history:

1. `deploy/vps/deploy.sh`
2. `tests/test_vps_deploy_origin_health.py`
3. `specs/015-worker-operator-control/spec.md`
4. `specs/015-worker-operator-control/plan.md`
5. `specs/015-worker-operator-control/tasks.md`

Current diff-derived production impact is `VPS`; VPS deployment is `REQUIRED` after merge under a fresh exact-SHA production safety envelope. Ubuntu Worker/relay and Windows Worker updates are `NOT REQUIRED` for this remediation diff. The parent Outcome still has pending Ubuntu worker-control acceptance after VPS runtime acceptance.

## Requirements traceability

- AC-001 | Task: T-004, T-007 | Evidence: tests/test_frontend_contract.py | Coverage: COVERED
- AC-002 | Task: T-003, T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-003 | Task: T-001, T-003, T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-004 | Task: T-001, T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-005 | Task: T-001, T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-006 | Task: T-001, T-005, T-007 | Evidence: tests/test_worker_operator_control.py plus updater/rollback tests | Coverage: COVERED
- AC-007 | Task: T-002, T-007 | Evidence: tests/test_ubuntu_worker_systemd.py | Coverage: COVERED
- AC-008 | Task: T-005, T-007 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py | Coverage: COVERED
- AC-009 | Task: T-006, T-007 | Evidence: tests/test_sea_speed_auth_v1.py | Coverage: COVERED
- AC-010 | Task: T-004, T-007 | Evidence: tests/test_frontend_contract.py and tests/test_worker_operator_control.py | Coverage: COVERED
- AC-011 | Task: T-008, T-009 | Evidence: exact-head PR Validation and Quality integration | Coverage: COVERED
- AC-012 | Task: T-010, T-020 | Evidence: separately authorized production service/HLS acceptance on Issue #178 | Coverage: RUNTIME-MANUAL | Reason: source CI cannot prove live HLS continuity across a real production worker stop/start
- AC-013 | Task: T-011, T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-014 | Task: T-012, T-008 | Evidence: tests/quality/test_quality_architecture.py plus aggregate exact-artifact/release-evidence jobs | Coverage: COVERED
- AC-015 | Task: T-013, T-014, T-015, T-008 | Evidence: tests/test_vps_deploy_origin_health.py, tests/test_camera_preview_gallery.py, tests/test_sea_speed_auth_v1.py plus runtime 8010 source/health proof | Coverage: COVERED
- AC-016 | Task: T-016, T-017, T-008 | Evidence: tests/quality/test_quality_architecture.py plus Deploy VPS run #27 first-parent admission evidence | Coverage: COVERED
- AC-017 | Task: T-018, T-019, T-008, T-020 | Evidence: tests/test_vps_deploy_origin_health.py plus next complete Deploy VPS logs/evidence | Coverage: COVERED

## Delivery evidence

- EVID-001 | Type: unit | Priority: P0 | Covers: AC-002, AC-003, AC-004, AC-005, AC-006, AC-013 | Source: tests/test_worker_operator_control.py | Status: GREEN on merged PR #180; aggregate CI will revalidate
- EVID-002 | Type: integration | Priority: P1 | Covers: AC-001, AC-010 | Source: tests/test_frontend_contract.py | Status: PREVIOUSLY GREEN; aggregate CI will revalidate
- EVID-003 | Type: integration | Priority: P0 | Covers: AC-007 | Source: tests/test_ubuntu_worker_systemd.py | Status: PREVIOUSLY GREEN; aggregate CI will revalidate
- EVID-004 | Type: integration | Priority: P0 | Covers: AC-008 | Source: updater/rollback tests | Status: PREVIOUSLY GREEN; aggregate CI will revalidate
- EVID-005 | Type: integration | Priority: P0 | Covers: AC-009, AC-015 | Source: tests/test_sea_speed_auth_v1.py | Status: GREEN on merged PR #181; aggregate CI will revalidate
- EVID-006 | Type: end-to-end | Priority: P0 | Covers: AC-011, AC-014, AC-015, AC-016, AC-017 | Source: exact-head GitHub Actions | Status: PENDING CURRENT VPS REMEDIATION CI
- EVID-007 | Type: runtime-manual | Priority: P0 | Covers: AC-012 | Source: later authorized production acceptance | Status: PENDING
- EVID-008 | Type: release-provenance | Priority: P0 | Covers: AC-014 | Source: deterministic `vps`/`edge` quality artifacts plus release-specific `ubuntu-worker` artifact in the exact-artifacts manifest; release-manifest v2 binds the Ubuntu archive digest and exact-manifest SHA-256 | Status: GREEN on merged PR #180; aggregate CI will revalidate
- EVID-009 | Type: integration | Priority: P0 | Covers: AC-015, AC-017 | Source: tests/test_vps_deploy_origin_health.py | Status: PENDING CURRENT VPS REMEDIATION CI
- EVID-010 | Type: runtime-manual | Priority: P0 | Covers: AC-015, AC-017 | Source: next Deploy VPS retry plus `127.0.0.1:8010/api/health`, exact source identity, protected current/previous state and deployment evidence | Status: PENDING
- EVID-011 | Type: production-learning | Priority: P0 | Covers: AC-016 | Source: Deploy VPS run #26 logs showing exact `INPUT_COMMIT` equals fetched `origin/main` while the old pipeline failed before quality/auth/SSH | Status: CAPTURED on Issue #178
- EVID-012 | Type: integration | Priority: P0 | Covers: AC-016 | Source: tests/quality/test_quality_architecture.py | Status: GREEN in merged PR #182 and push/main quality #275
- EVID-013 | Type: production-learning | Priority: P0 | Covers: AC-017 | Source: Deploy VPS run #27 logs showing successful admission/quality/auth/provenance/SSH/8010/public-smoke followed only by permission-denied stale-release pruning and skipped evidence upload | Status: CAPTURED on Issue #178

## Definition of Done

- Issue/spec/plan/tasks current: YES for the active 5-path VPS correct-course remediation; production feedback records run #27 as post-verification stale-release cleanup failure.
- Exact changed-file scope verified: must remain exactly the approved 5 remediation paths above.
- Required tests and evidence complete: best-effort pruning/protected rollback pair/ordering regression plus full aggregate CI are required before remediation merge; AC-012 and runtime portions of AC-015/AC-017 remain runtime-manual after merge.
- Required CI green: exact final remediation PR head must have PR Validation and Quality integration SUCCESS.
- Risk-profile applicability: `Risk profile: REQUIRED` because release deletion/rollback-retention logic is a high-risk operational boundary; plan risk rows must remain complete and mitigated/accepted according to evidence.
- Exact-green-head merge complete: only after fresh main/base/head/scope/review verification and expected-head merge.
- Deployment state resolved: source remediation does not itself deploy. Actual post-run #27 VPS state must be re-read before the next mutation because formal deployment-evidence collection was skipped after pruning failed.
- Release provenance resolved: the remediation merge creates a new VPS source identity and must have exact artifacts/quality evidence before production authorization.
- Runtime acceptance resolved: NO until corrected VPS deployment evidence and the pending Ubuntu worker-control stop/start plus continuous-HLS evidence are accepted.
- Deferred work recorded: merge VPS pruning fix; resolve post-run #27 state; obtain fresh production authorization for new merge SHA; deploy/collect evidence; then continue Ubuntu installation and final AC-012 acceptance.
- Risks resolved or explicitly accepted: current/previous pruning protection and warning-only stale cleanup must be regression-protected before merge; final production proof occurs on the next authorized deployment.
- Waivers resolved or current: no waiver is currently required; any future waiver cannot bypass exact artifacts, production authorization, origin health, rollback identity or current/previous protection.

## Completion gate

- Active source gate: exact 5-path remediation scope, current SDD, `Risk profile: REQUIRED`, non-FAIL quality verdict, best-effort-pruning regression, PR Validation, Quality integration, review-thread check and expected-head merge.
- Current VPS production gate: `VPS deployment: REQUIRED`; `Ubuntu worker/relay update: NOT REQUIRED`; `Windows worker update: NOT REQUIRED`; `Production safety envelope: REQUIRED` for the exact new merge SHA.
- Runtime retry gate: after merge and push/main quality, re-read current/previous/service/source state; obtain fresh `PRODUCTION APPROVED <new-sha>` and fingerprint; manually dispatch Deploy VPS from current `main` targeting that exact SHA with Issue #178; require successful evidence collection/upload.
- Parent Ubuntu gate: this VPS remediation does not authorize or require an Ubuntu update. Before Ubuntu mutation, re-verify the eligible exact Ubuntu source, applicable production authorization, release artifact/runtime identity and rollout compatibility.
- Terminal gate: `COMPLETE` is forbidden until corrected VPS deployment/rollback/retention verification, worker/control-service identity, protocol compatibility, exact applicable provenance and Camera 1 HLS continuity are accepted in production.
