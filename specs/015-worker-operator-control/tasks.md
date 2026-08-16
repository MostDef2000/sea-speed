# Delivery Tasks: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Plan: specs/015-worker-operator-control/plan.md
- Issue: #178
- Status: Ubuntu updater/legacy-control rollback remediation validation

## Delivery tasks

- T-001 [P0] Implement the bounded Ubuntu worker-control agent for status/start/stop of `sea-speed-worker.service` only. COMPLETE in merged PR #179.
- T-002 [P0] Install an independent `sea-speed-worker-control.service` using exact release source. COMPLETE in merged PR #179 source.
- T-003 [P0] Add VPS FastAPI worker-control routes with trusted browser identity, private-origin validation, bearer authentication and bounded timeouts. COMPLETE in merged PR #179 source.
- T-004 [P1] Add a distinct worker-control button while preserving Camera 1 HLS and existing live Play/Stop controls. COMPLETE in merged PR #179 source.
- T-005 [P0] Preserve operator desired `running|stopped` state through exact updater and rollback semantics. COMPLETE in merged PR #179 source; current remediation strengthens migration rollback topology.
- T-006 [P0] Keep Ubuntu-to-VPS private ingress restricted to existing telemetry/config endpoints. COMPLETE.
- T-007 [P0] Maintain focused source tests for agent/API security, UI/media invariants, systemd independence and maintenance behavior. COMPLETE for earlier source; aggregate CI remains authoritative.
- T-008 [P0] Validate active approved diff and linked SDD; open bounded remediation PR and reach exact-head CI green.
- T-009 [P0] Re-read main/head/scope/reviews and merge only exact green head with expected-head protection.
- T-010 [P0] Stop at production boundary until applicable exact-SHA production authorization is current; then collect required runtime evidence.
- T-011 [P0] Add fixed `sea_speed_worker_control_v1` marker and fail-closed VPS compatibility guard. COMPLETE in PR #180.
- T-012 [P0] Add deterministic `ubuntu-worker` exact artifact. COMPLETE in PR #180.
- T-013 [P0] Correct VPS origin-health probe to 8010. COMPLETE in PR #181.
- T-014 [P0] Add 8010 regression evidence and run #25 learning. COMPLETE in PR #181.
- T-015 [P0] Align historical deploy-contract assertions with 8010. COMPLETE in PR #181.
- T-016 [P0] Make first-parent admission pipefail-safe. COMPLETE in PR #182.
- T-017 [P0] Add first-parent regression evidence and run #26 learning. COMPLETE in PR #182.
- T-018 [P0] Make stale VPS release pruning best-effort after verified persistence. COMPLETE in PR #183.
- T-019 [P0] Add pruning/retention ordering regression and run #27 learning. COMPLETE in PR #183.
- T-020 [P0] Resolve run #27 VPS state, obtain fresh authorization and complete corrected VPS deployment evidence. COMPLETE: VPS accepted on `e2a4f39eab80849882a42cf6e892bba127223649`.
- T-021 [P0] Replace unsupported Ubuntu updater `--required-name` call with supported `--workflow-file quality-integration.yml` and execute the verifier parser surface in regression tests.
- T-022 [P0] Make automatic activation restoration and explicit rollback preserve exact modern/legacy control-service topology, including removal/absence verification for legacy targets and fail-closed partial target detection.
- T-023 [P0] Update exact-update/rollback runbooks plus SDD production learning, risk/test design and eight-stage Ubuntu transaction audit.
- T-024 [P0] Merge only exact-green 9-path source, verify push/main Quality integration and obtain a fresh exact-SHA Ubuntu production safety envelope.
- T-025 [P0] Prepare/activate the authorized exact Ubuntu release with expected shared-runtime reuse, verify exact worker/control identity, then execute Stop worker -> continuous HLS -> Start worker -> continuous HLS acceptance.

## Active remediation scope

The current correct-course source gate is exactly these 9 paths; historical scopes remain immutable audit history:

1. `deploy/worker/ubuntu/update-exact.sh`
2. `deploy/worker/ubuntu/rollback-exact.sh`
3. `tests/test_ubuntu_worker_exact_updater.py`
4. `tests/test_ubuntu_worker_rollback.py`
5. `docs/operations/UBUNTU_WORKER_EXACT_UPDATE.md`
6. `docs/operations/UBUNTU_WORKER_ROLLBACK.md`
7. `specs/015-worker-operator-control/spec.md`
8. `specs/015-worker-operator-control/plan.md`
9. `specs/015-worker-operator-control/tasks.md`

Current diff-derived production impact is Ubuntu Worker/relay. VPS deployment is `NOT REQUIRED`; Ubuntu worker/relay update is `REQUIRED`; Windows Worker update is `NOT REQUIRED`; a fresh exact-SHA production safety envelope is `REQUIRED` after merge. No API/frontend/media/AI/credential source is in this remediation.

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
- AC-011 | Task: T-008,T-009,T-024 | Evidence: exact-head PR Validation and Quality integration | Coverage: COVERED
- AC-012 | Task: T-010,T-025 | Evidence: separately authorized production service/HLS acceptance on Issue #178 | Coverage: RUNTIME-MANUAL | Reason: hosted source CI cannot prove live HLS continuity across a real production worker stop/start
- AC-013 | Task: T-011,T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-014 | Task: T-012,T-008 | Evidence: tests/quality/test_quality_architecture.py plus exact-artifact/release-evidence jobs | Coverage: COVERED
- AC-015 | Task: T-013,T-014,T-015 | Evidence: tests/test_vps_deploy_origin_health.py plus accepted VPS runtime evidence | Coverage: COVERED
- AC-016 | Task: T-016,T-017 | Evidence: tests/quality/test_quality_architecture.py plus successful deployment admission evidence | Coverage: COVERED
- AC-017 | Task: T-018,T-019,T-020 | Evidence: tests/test_vps_deploy_origin_health.py plus accepted VPS deployment evidence | Coverage: COVERED
- AC-018 | Task: T-021,T-023 | Evidence: tests/test_ubuntu_worker_exact_updater.py | Coverage: COVERED
- AC-019 | Task: T-022,T-023 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py | Coverage: COVERED

## Delivery evidence

- EVID-001 | Type: unit | Priority: P0 | Covers: AC-002,AC-003,AC-004,AC-005,AC-006,AC-013 | Source: tests/test_worker_operator_control.py | Status: GREEN earlier; aggregate CI revalidates
- EVID-002 | Type: integration | Priority: P1 | Covers: AC-001,AC-010 | Source: tests/test_frontend_contract.py | Status: GREEN earlier; aggregate CI revalidates
- EVID-003 | Type: integration | Priority: P0 | Covers: AC-007 | Source: tests/test_ubuntu_worker_systemd.py | Status: GREEN earlier; aggregate CI revalidates
- EVID-004 | Type: integration | Priority: P0 | Covers: AC-008,AC-018,AC-019 | Source: updater/rollback focused tests | Status: REQUIRED CURRENT REMEDIATION CI
- EVID-005 | Type: integration | Priority: P0 | Covers: AC-009 | Source: tests/test_sea_speed_auth_v1.py | Status: GREEN earlier; aggregate CI revalidates
- EVID-006 | Type: end-to-end | Priority: P0 | Covers: AC-011 | Source: exact-head GitHub Actions | Status: PENDING CURRENT REMEDIATION CI
- EVID-007 | Type: runtime-manual | Priority: P0 | Covers: AC-012 | Source: authorized production Stop/HLS/Start/HLS acceptance | Status: PENDING
- EVID-008 | Type: release-provenance | Priority: P0 | Covers: AC-014 | Source: deterministic exact-artifacts/release evidence | Status: GREEN earlier; aggregate CI revalidates
- EVID-009 | Type: production-learning | Priority: P0 | Covers: AC-018,AC-019 | Source: failed Ubuntu preparation output plus read-only baseline and adjacent-stage audit on Issue #178 | Status: CAPTURED
- EVID-010 | Type: runtime-manual | Priority: P0 | Covers: AC-015,AC-017 | Source: accepted corrected VPS deployment evidence | Status: ACCEPTED on `e2a4f39eab80849882a42cf6e892bba127223649`
- EVID-011 | Type: runtime-manual | Priority: P0 | Covers: AC-019 | Source: post-merge Ubuntu preparation/activation topology readback | Status: PENDING FRESH PRODUCTION AUTHORIZATION

## Definition of Done

- Issue/spec/plan/tasks current: YES for the active 9-path Ubuntu correct-course remediation and production-learning #5.
- Exact changed-file scope verified: must remain exactly the approved 9 remediation paths.
- Required tests and evidence complete: caller/verifier compatibility, modern/legacy control-topology rollback regression and full aggregate CI are required before merge; AC-012 remains runtime-manual after merge.
- Required CI green: exact final remediation PR head must have PR Validation and Quality integration SUCCESS.
- Risk-profile applicability: `Risk profile: REQUIRED` because Ubuntu production update/rollback topology is a high-risk operational boundary.
- Exact-green-head merge complete: only after fresh main/base/head/scope/review verification and expected-head merge.
- Deployment state resolved: source remediation does not itself mutate Ubuntu; current baseline is read-only known as `efdbdfd...` + runtime `a9a9aacc...` with no control service.
- Release provenance resolved: the remediation merge requires exact push/main quality/artifact evidence before production authorization and preparation.
- Runtime acceptance resolved: NO until exact Ubuntu preparation/activation, independent control identity/protocol and Stop/HLS/Start/HLS evidence are accepted.
- Deferred work recorded: merge current remediation; obtain fresh production authorization; prepare/activate exact release; complete final runtime acceptance.
- Risks resolved or explicitly accepted: CLI drift and legacy/modern control-topology failure paths must be regression-protected before merge; physical systemd behavior is finalized by authorized runtime evidence.
- Waivers resolved or current: no waiver; no waiver may bypass exact quality, production authorization, source/runtime identity or rollback topology.

## Completion gate

- Active source gate: exact 9-path remediation, current SDD with full deployment transaction audit, `Risk profile: REQUIRED`, non-FAIL quality verdict, focused updater/rollback regression, PR Validation, Quality integration, review-thread check and expected-head merge.
- Current production gate after merge: `VPS deployment: NOT REQUIRED`; `Ubuntu worker/relay update: REQUIRED`; `Windows worker update: NOT REQUIRED`; `Production safety envelope: REQUIRED` for the new merge SHA.
- Runtime preparation gate: fresh production authorization plus exact trusted checkout; supported quality-verifier CLI must pass; expected unchanged-runtime path must emit `RUNTIME_REUSED`; active baseline must remain unchanged until explicit activation.
- Runtime activation gate: exact worker/control units, exact shared runtime, desired-state preservation, runtime progression when running and automatic restoration of the legacy no-control baseline on failure.
- Terminal gate: `COMPLETE` is forbidden until worker/control exact identity, fixed protocol compatibility, Stop worker / Start worker state changes and Camera 1 HLS continuity are accepted in production.
