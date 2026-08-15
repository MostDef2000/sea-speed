# Delivery Tasks: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Plan: specs/015-worker-operator-control/plan.md
- Issue: #178
- Status: Correct-course remediation validation

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
- T-013 [P0] Change the VPS exact-deployment default origin-health probe from stale `127.0.0.1:8000` to accepted Auth v1 origin `127.0.0.1:8010`, preserving the single verifier used for candidate and automatic rollback checks.
- T-014 [P0] Add regression evidence for the canonical 8010 deployment/rollback probe and record run #25/restored-baseline production learning in feature 015.
- T-015 [P0] Align the two historical deploy-contract assertions exposed by exact-head CI (`test_camera_preview_gallery.py` and `test_sea_speed_auth_v1.py`) with canonical port 8010 without changing their unrelated media/auth assertions.

## Active remediation scope

The current correct-course source gate is exactly these 7 paths; the historical 17-path PR #179, 9-path PR #180, and superseded 5-path remediation scope remain immutable audit history:

1. `deploy/vps/deploy.sh`
2. `tests/test_vps_deploy_origin_health.py`
3. `tests/test_camera_preview_gallery.py`
4. `tests/test_sea_speed_auth_v1.py`
5. `specs/015-worker-operator-control/spec.md`
6. `specs/015-worker-operator-control/plan.md`
7. `specs/015-worker-operator-control/tasks.md`

Current diff-derived runtime applicability is VPS only. The parent Outcome still has a separately pending Ubuntu worker-control production installation/acceptance from merged PR #180; this 7-path remediation does not rewrite that source history or imply Ubuntu deployment.

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
- AC-012 | Task: T-010 | Evidence: separately authorized production service/HLS acceptance on Issue #178 | Coverage: RUNTIME-MANUAL | Reason: source CI cannot prove live HLS continuity across a real production worker stop/start
- AC-013 | Task: T-011, T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-014 | Task: T-012, T-008 | Evidence: tests/quality/test_quality_architecture.py plus aggregate exact-artifact/release-evidence jobs | Coverage: COVERED
- AC-015 | Task: T-013, T-014, T-015, T-008 | Evidence: tests/test_vps_deploy_origin_health.py, tests/test_camera_preview_gallery.py, tests/test_sea_speed_auth_v1.py plus later runtime 8010 source/health proof | Coverage: COVERED

## Delivery evidence

- EVID-001 | Type: unit | Priority: P0 | Covers: AC-002, AC-003, AC-004, AC-005, AC-006, AC-013 | Source: tests/test_worker_operator_control.py | Status: GREEN on merged PR #180; aggregate CI will revalidate
- EVID-002 | Type: integration | Priority: P1 | Covers: AC-001, AC-010 | Source: tests/test_frontend_contract.py | Status: PREVIOUSLY GREEN; aggregate CI will revalidate
- EVID-003 | Type: integration | Priority: P0 | Covers: AC-007 | Source: tests/test_ubuntu_worker_systemd.py | Status: PREVIOUSLY GREEN; aggregate CI will revalidate
- EVID-004 | Type: integration | Priority: P0 | Covers: AC-008 | Source: updater/rollback tests | Status: PREVIOUSLY GREEN; aggregate CI will revalidate
- EVID-005 | Type: integration | Priority: P0 | Covers: AC-009, AC-015 | Source: tests/test_sea_speed_auth_v1.py | Status: PENDING CURRENT REMEDIATION CI
- EVID-006 | Type: end-to-end | Priority: P0 | Covers: AC-011, AC-014, AC-015 | Source: exact-head GitHub Actions | Status: PENDING CURRENT REMEDIATION CI
- EVID-007 | Type: runtime-manual | Priority: P0 | Covers: AC-012 | Source: later authorized production acceptance | Status: PENDING
- EVID-008 | Type: release-provenance | Priority: P0 | Covers: AC-014 | Source: deterministic `vps`/`edge` quality artifacts plus release-specific `ubuntu-worker` artifact in the exact-artifacts manifest; release-manifest v2 binds the Ubuntu archive digest and exact-manifest SHA-256 | Status: GREEN on merged PR #180; aggregate CI will revalidate
- EVID-009 | Type: integration | Priority: P0 | Covers: AC-015 | Source: tests/test_vps_deploy_origin_health.py and tests/test_camera_preview_gallery.py | Status: PENDING CURRENT REMEDIATION CI
- EVID-010 | Type: runtime-manual | Priority: P0 | Covers: AC-015 | Source: Deploy VPS retry plus `127.0.0.1:8010/api/health` exact source identity / rollback evidence | Status: PENDING NEW VPS AUTHORIZATION

## Definition of Done

- Issue/spec/plan/tasks current: YES for the active 7-path correct-course remediation; production feedback records run #25 false-negative and the restored healthy VPS baseline.
- Exact changed-file scope verified: must remain exactly the approved 7 remediation paths above.
- Required tests and evidence complete: canonical VPS origin-health regression plus both historical deploy-contract assertions and full aggregate CI are required before remediation merge; AC-012 and runtime part of AC-015 remain runtime-manual after production authorization.
- Required CI green: exact final remediation PR head must have PR Validation and Quality integration SUCCESS.
- Risk-profile applicability: current 7-path PR derives VPS-only impact with Security impact NONE, schema impact NONE, destructive migration NO and other high-risk trigger NO, therefore Change Contract declares `Risk profile: NOT REQUIRED`; the parent feature's full MIXED/security risk evidence remains immutable in merged PR #180/Issue #178 for final runtime acceptance.
- Exact-green-head merge complete: only after fresh main/base/head/scope/review verification and expected-head merge.
- Deployment state resolved: source remediation does not deploy. Current VPS runtime is restored/healthy at `6bf909c13d48df1d44b87a62d0686b61d8c3af45` on 8010; Ubuntu rollout from PR #180 has not started.
- Release provenance resolved: PR #180 established deterministic `vps`, release-specific `ubuntu-worker`, and legacy `edge` exact provenance; the current VPS-only diff must preserve aggregate release-evidence validity.
- Runtime acceptance resolved: NO until corrected VPS deployment evidence and the pending Ubuntu worker-control stop/start plus continuous-HLS evidence are accepted.
- Deferred work recorded: fresh exact-SHA VPS authorization/retry, then authorization/compatibility re-verification for pending Ubuntu installation and final AC-012 acceptance.
- Risks resolved or explicitly accepted: the VPS origin-health source mitigation must pass exact-head CI; parent feature residual runtime risks remain subject to production acceptance.
- Waivers resolved or current: no waiver is currently required; any future waiver must satisfy the durable waiver contract and cannot bypass exact artifacts or production authorization.

## Completion gate

- Active source gate: exact 7-path remediation scope, current SDD, diff-derived `Risk profile: NOT REQUIRED`, non-FAIL quality verdict, canonical origin-health regression tests, PR Validation, Quality integration, review-thread check and expected-head merge.
- Current remediation production gate: new merge SHA will require its own `PRODUCTION APPROVED <exact-remediation-merged-sha>` before VPS mutation; the existing `1d0aa285...` approval cannot authorize the new SHA.
- Parent Ubuntu gate: this VPS-only PR does not itself authorize or require an Ubuntu update. Before Ubuntu mutation, re-verify the eligible exact Ubuntu source, applicable production authorization, release artifact/runtime identity and rollout compatibility instead of inferring authorization from the VPS remediation.
- Terminal gate: `COMPLETE` is forbidden until corrected VPS deployment/rollback verification, worker/control-service identity, protocol compatibility, exact applicable provenance and Camera 1 HLS continuity are accepted in production.
