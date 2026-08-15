# Delivery Tasks: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Plan: specs/015-worker-operator-control/plan.md
- Issue: #178
- Status: Implementation validation

## Delivery tasks

- T-001 [P0] Implement the bounded Ubuntu worker-control agent for status/start/stop of `sea-speed-worker.service` only.
- T-002 [P0] Install an independent `sea-speed-worker-control.service` using the exact release source.
- T-003 [P0] Add VPS FastAPI worker-control routes with trusted browser identity, private-origin validation, bearer authentication and bounded timeouts.
- T-004 [P1] Add a distinct worker-control button to the Operator UI while preserving Camera 1 HLS and existing live Play/Stop controls.
- T-005 [P0] Preserve operator desired `running|stopped` state through exact updater and rollback semantics.
- T-006 [P0] Keep Ubuntu-to-VPS private ingress restricted to existing telemetry/config endpoints; worker-control routes remain absent.
- T-007 [P0] Add focused source tests for agent/API security, UI/media invariants, systemd independence and maintenance behavior.
- T-008 [P0] Validate the exact approved diff and linked SDD; open the bounded PR and reach exact-head CI green.
- T-009 [P0] Re-read main/head/scope/reviews and merge only the exact green head with expected-head protection.
- T-010 [P0] Stop at the production boundary until separate exact-SHA production authorization; then collect mixed-contour runtime evidence.

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
- AC-012 | Task: T-010 | Evidence: authorized production service/HLS acceptance on Issue #178 | Coverage: RUNTIME-MANUAL | Reason: source CI cannot prove live HLS continuity across a real production worker stop/start

## Delivery evidence

- EVID-001 | Type: unit | Priority: P0 | Covers: AC-002, AC-003, AC-004, AC-005, AC-006 | Source: tests/test_worker_operator_control.py | Status: PENDING
- EVID-002 | Type: integration | Priority: P1 | Covers: AC-001, AC-010 | Source: tests/test_frontend_contract.py | Status: PENDING
- EVID-003 | Type: integration | Priority: P0 | Covers: AC-007 | Source: tests/test_ubuntu_worker_systemd.py | Status: PENDING
- EVID-004 | Type: integration | Priority: P0 | Covers: AC-008 | Source: updater/rollback tests | Status: PENDING
- EVID-005 | Type: integration | Priority: P0 | Covers: AC-009 | Source: tests/test_sea_speed_auth_v1.py | Status: PENDING
- EVID-006 | Type: end-to-end | Priority: P0 | Covers: AC-011 | Source: exact-head GitHub Actions | Status: PENDING
- EVID-007 | Type: runtime-manual | Priority: P0 | Covers: AC-012 | Source: later authorized production acceptance | Status: PENDING

## Definition of Done

- Issue/spec/plan/tasks current: YES for source validation; production feedback remains pending.
- Exact changed-file scope verified: must remain exactly the approved 17 paths.
- Required tests and evidence complete: source tests and CI required before merge; AC-012 remains runtime-manual after production authorization.
- Required CI green: exact final PR head must have PR Validation and Quality integration SUCCESS.
- Exact-green-head merge complete: only after fresh scope/review verification and expected-head merge.
- Deployment state resolved: source delivery does not deploy; production remains explicitly pending a separate exact-SHA safety envelope.
- Runtime acceptance resolved: NO until authorized mixed-contour stop/start plus continuous-HLS evidence is recorded.
- Deferred work recorded: production rollout and runtime-manual AC-012 are the only expected deferred items at source merge.
- Risks resolved or explicitly accepted: all source mitigations must pass; residual production risks require runtime acceptance evidence.
- Waivers resolved or current: no waiver is currently required; any future waiver must satisfy the durable waiver contract.

## Completion gate

- Source gate: exact 17-path scope, current SDD, non-FAIL quality verdict, required source tests, PR Validation, Quality integration, review-thread check and expected-head merge.
- Production gate: separate `PRODUCTION APPROVED <exact-merged-sha>` before any VPS or Ubuntu runtime mutation.
- Terminal gate: `COMPLETE` is forbidden until worker/control-service identity and Camera 1 HLS continuity are accepted in production.
