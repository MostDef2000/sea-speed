# Delivery Tasks: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Plan: specs/015-worker-operator-control/plan.md
- Issue: #178
- Status: Ubuntu updater cleanup-exit remediation validation

## Delivery tasks

- T-001 [P0] Implement bounded Ubuntu worker-control status/start/stop for literal `sea-speed-worker.service`. COMPLETE in PR #179.
- T-002 [P0] Install independent `sea-speed-worker-control.service`. COMPLETE in PR #179 source.
- T-003 [P0] Add protected VPS FastAPI worker-control routes. COMPLETE in PR #179 source.
- T-004 [P1] Add distinct worker UI control while preserving Camera 1 HLS/browser Play/Stop. COMPLETE in PR #179 source.
- T-005 [P0] Preserve desired `running|stopped` state through update/rollback. COMPLETE in source; later remediations strengthen exact maintenance semantics.
- T-006 [P0] Keep Ubuntu-to-VPS ingress restricted to existing telemetry/config endpoints. COMPLETE.
- T-007 [P0] Maintain focused product/security/media/systemd/update/rollback tests. COMPLETE; aggregate CI remains authoritative.
- T-008 [P0] Validate approved diff/SDD, open bounded PR and reach exact-head CI green.
- T-009 [P0] Re-read main/head/scope/reviews and merge only exact green head with expected-head protection.
- T-010 [P0] Stop at production boundary until exact-SHA production authorization is current.
- T-011 [P0] Add `sea_speed_worker_control_v1` and VPS fail-closed compatibility guard. COMPLETE in PR #180.
- T-012 [P0] Add deterministic `ubuntu-worker` exact artifact. COMPLETE in PR #180.
- T-013 [P0] Correct VPS origin health to 8010. COMPLETE in PR #181.
- T-014 [P0] Add 8010 regression evidence. COMPLETE in PR #181.
- T-015 [P0] Align historical deploy-contract assertions with 8010. COMPLETE in PR #181.
- T-016 [P0] Make VPS first-parent admission pipefail-safe. COMPLETE in PR #182.
- T-017 [P0] Add first-parent regression evidence. COMPLETE in PR #182.
- T-018 [P0] Make stale VPS release pruning best-effort after verified persistence. COMPLETE in PR #183.
- T-019 [P0] Add pruning/retention ordering regression. COMPLETE in PR #183.
- T-020 [P0] Complete corrected VPS deployment evidence. COMPLETE: VPS accepted at `e2a4f39eab80849882a42cf6e892bba127223649`.
- T-021 [P0] Replace unsupported Ubuntu updater quality CLI argument with `--workflow-file quality-integration.yml` and execute verifier parser in tests. COMPLETE in PR #186.
- T-022 [P0] Preserve exact modern/legacy worker-control topology across failed activation and rollback. COMPLETE in PR #186.
- T-023 [P0] Synchronize Ubuntu runbooks and transaction audit for production learning #5. COMPLETE in PR #186.
- T-024 [P0] Merge exact-green PR #186, verify push/main quality and obtain fresh Ubuntu production envelope. COMPLETE for source/authorization.
- T-025 [P0] Prepare/activate authorized Ubuntu release and execute Stop/HLS/Start/HLS acceptance. PREPARATION BLOCKED by production learning #6 before activation.
- T-026 [P0] Make updater `cleanup()` capture and return the primary exit status while treating all temporary cleanup operations as best-effort.
- T-027 [P0] Add executable regression that runs the real cleanup function through an EXIT trap under `set -euo pipefail` and verifies success, original failure and forced-cleanup-failure semantics.
- T-028 [P0] Merge only exact-green 5-path cleanup remediation, verify post-merge quality/artifacts, then obtain a fresh exact-SHA Ubuntu production envelope before runtime continuation.

## Active remediation scope

The current correct-course source gate is exactly these 5 paths; historical scopes remain immutable audit history:

1. `deploy/worker/ubuntu/update-exact.sh`
2. `tests/test_ubuntu_worker_exact_updater.py`
3. `specs/015-worker-operator-control/spec.md`
4. `specs/015-worker-operator-control/plan.md`
5. `specs/015-worker-operator-control/tasks.md`

Current diff-derived production impact is `UBUNTU_WORKER`. VPS deployment is `NOT REQUIRED`; Ubuntu worker/relay update is `REQUIRED`; Windows Worker update is `NOT REQUIRED`; a fresh exact-SHA production safety envelope is `REQUIRED` after merge. No API/frontend/media/AI/credential/rollback-script source is in this remediation.

## Requirements traceability

- AC-001 | Task: T-004,T-007 | Evidence: tests/test_frontend_contract.py | Coverage: COVERED
- AC-002 | Task: T-003,T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-003 | Task: T-001,T-003,T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-004 | Task: T-001,T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-005 | Task: T-001,T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-006 | Task: T-001,T-005,T-007 | Evidence: tests/test_worker_operator_control.py plus updater/rollback tests | Coverage: COVERED
- AC-007 | Task: T-002,T-007 | Evidence: tests/test_ubuntu_worker_systemd.py | Coverage: COVERED
- AC-008 | Task: T-005,T-022 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py | Coverage: COVERED
- AC-009 | Task: T-006,T-007 | Evidence: tests/test_sea_speed_auth_v1.py | Coverage: COVERED
- AC-010 | Task: T-004,T-007 | Evidence: tests/test_frontend_contract.py and tests/test_worker_operator_control.py | Coverage: COVERED
- AC-011 | Task: T-008,T-009,T-028 | Evidence: exact-head PR Validation and Quality integration | Coverage: COVERED
- AC-012 | Task: T-010,T-025,T-028 | Evidence: separately authorized production service/HLS acceptance on Issue #178 | Coverage: RUNTIME-MANUAL | Reason: hosted source CI cannot prove live HLS continuity across a real production worker stop/start
- AC-013 | Task: T-011,T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-014 | Task: T-012,T-008 | Evidence: tests/quality/test_quality_architecture.py plus exact-artifact/release-evidence jobs | Coverage: COVERED
- AC-015 | Task: T-013,T-014,T-015 | Evidence: tests/test_vps_deploy_origin_health.py plus accepted VPS runtime evidence | Coverage: COVERED
- AC-016 | Task: T-016,T-017 | Evidence: tests/quality/test_quality_architecture.py plus accepted VPS admission evidence | Coverage: COVERED
- AC-017 | Task: T-018,T-019,T-020 | Evidence: tests/test_vps_deploy_origin_health.py plus accepted VPS deployment evidence | Coverage: COVERED
- AC-018 | Task: T-021,T-023 | Evidence: tests/test_ubuntu_worker_exact_updater.py | Coverage: COVERED
- AC-019 | Task: T-022,T-023 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py | Coverage: COVERED
- AC-020 | Task: T-026,T-027,T-028 | Evidence: tests/test_ubuntu_worker_exact_updater.py executable EXIT-trap cleanup cases plus exact-head CI | Coverage: COVERED

## Delivery evidence

- EVID-001 | Type: unit | Priority: P0 | Covers: AC-002,AC-003,AC-004,AC-005,AC-006,AC-013 | Source: tests/test_worker_operator_control.py | Status: GREEN earlier; aggregate CI revalidates
- EVID-002 | Type: integration | Priority: P1 | Covers: AC-001,AC-010 | Source: tests/test_frontend_contract.py | Status: GREEN earlier; aggregate CI revalidates
- EVID-003 | Type: integration | Priority: P0 | Covers: AC-007 | Source: tests/test_ubuntu_worker_systemd.py | Status: GREEN earlier; aggregate CI revalidates
- EVID-004 | Type: integration | Priority: P0 | Covers: AC-008,AC-018,AC-019 | Source: updater/rollback focused tests | Status: GREEN in PR #186; aggregate CI revalidates
- EVID-005 | Type: integration | Priority: P0 | Covers: AC-009 | Source: tests/test_sea_speed_auth_v1.py | Status: GREEN earlier; aggregate CI revalidates
- EVID-006 | Type: end-to-end | Priority: P0 | Covers: AC-011 | Source: exact-head GitHub Actions | Status: PENDING CURRENT 5-PATH REMEDIATION CI
- EVID-007 | Type: runtime-manual | Priority: P0 | Covers: AC-012 | Source: authorized production Stop/HLS/Start/HLS acceptance | Status: PENDING
- EVID-008 | Type: release-provenance | Priority: P0 | Covers: AC-014 | Source: deterministic exact-artifacts/release evidence | Status: GREEN earlier; aggregate CI revalidates
- EVID-009 | Type: production-learning | Priority: P0 | Covers: AC-018,AC-019 | Source: production learning #5 on Issue #178 | Status: CAPTURED
- EVID-010 | Type: runtime-manual | Priority: P0 | Covers: AC-015,AC-017 | Source: accepted corrected VPS deployment evidence | Status: ACCEPTED on `e2a4f39eab80849882a42cf6e892bba127223649`
- EVID-011 | Type: production-learning | Priority: P0 | Covers: AC-020 | Source: production learning #6 preparation log plus Issue #178 adjacent-stage audit | Status: CAPTURED
- EVID-012 | Type: integration | Priority: P0 | Covers: AC-020 | Source: tests/test_ubuntu_worker_exact_updater.py real cleanup/EXIT execution | Status: REQUIRED CURRENT REMEDIATION CI

## Definition of Done

- Issue/spec/plan/tasks current: YES for production learning #6 and the active 5-path cleanup remediation.
- Exact changed-file scope verified: must remain exactly the approved 5 paths.
- Required tests and evidence complete: executable cleanup exit-status regression plus aggregate existing product/runtime contracts are required before merge; AC-012 remains runtime-manual.
- Required CI green: exact final remediation head must have PR Validation and Quality integration SUCCESS.
- Risk-profile applicability: `Risk profile: REQUIRED` because updater result semantics gate production runtime continuation.
- Exact-green-head merge complete: only after fresh main/base/head/scope/review verification and expected-head merge.
- Deployment state resolved: source delivery performs no runtime mutation; actual Ubuntu state must be re-read before the next separately authorized preparation/activation.
- Release provenance resolved: remediation merge requires exact push/main quality and exact artifact evidence before production authorization.
- Runtime acceptance resolved: NO until corrected exact Ubuntu preparation/activation, control identity/protocol and Stop/HLS/Start/HLS evidence are accepted.
- Deferred work recorded: merge current remediation; obtain fresh production authorization; reconcile actual worker/prepared release state; prepare/activate exact release; finish product acceptance.
- Risks resolved or explicitly accepted: cleanup exit masking must be executable-regression protected; physical systemd/HLS behavior remains runtime-manual.
- Waivers resolved or current: no waiver; no waiver may bypass exact quality, production authorization, source/runtime identity or rollback topology.

## Completion gate

- Active source gate: exact 5-path remediation, current SDD with complete deployment transaction audit, `Risk profile: REQUIRED`, non-FAIL quality verdict, executable cleanup regression, PR Validation, Quality integration, review-thread check and expected-head merge.
- Current production gate after merge: `VPS deployment: NOT REQUIRED`; `Ubuntu worker/relay update: REQUIRED`; `Windows worker update: NOT REQUIRED`; `Production safety envelope: REQUIRED` for the new merge SHA.
- Runtime preparation gate: fresh production authorization plus exact trusted checkout; exact quality must pass; unchanged runtime must emit `RUNTIME_REUSED`; updater process must exit 0; active baseline remains unchanged until explicit activation.
- Runtime activation gate: exact worker/control units, exact shared runtime, desired-state preservation, runtime progression when running and automatic restoration of legacy no-control baseline on failure.
- Terminal gate: `COMPLETE` is forbidden until worker/control exact identity, protocol compatibility, Stop worker / Start worker state changes and Camera 1 HLS continuity are accepted in production.
