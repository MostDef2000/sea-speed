# Delivery Tasks: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Plan: specs/015-worker-operator-control/plan.md
- Issue: #178
- Status: Implementation

## Tasks

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

## Acceptance traceability

- AC-001 -> T-004, T-007 -> tests/test_frontend_contract.py
- AC-002 -> T-003, T-007 -> tests/test_worker_operator_control.py
- AC-003 -> T-001, T-003, T-007 -> tests/test_worker_operator_control.py
- AC-004 -> T-001, T-007 -> tests/test_worker_operator_control.py
- AC-005 -> T-001, T-007 -> tests/test_worker_operator_control.py
- AC-006 -> T-001, T-005, T-007 -> worker-control and updater/rollback tests
- AC-007 -> T-002, T-007 -> tests/test_ubuntu_worker_systemd.py
- AC-008 -> T-005, T-007 -> tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py
- AC-009 -> T-006, T-007 -> tests/test_sea_speed_auth_v1.py
- AC-010 -> T-004, T-007 -> frontend and worker-control tests
- AC-011 -> T-008, T-009 -> exact-head PR Validation and Quality integration
- AC-012 -> T-010 -> authorized runtime-manual evidence on Issue #178

## Delivery evidence

- EVID-001 | Type: unit | Priority: P0 | Covers: AC-002, AC-003, AC-004, AC-005, AC-006 | Source: tests/test_worker_operator_control.py | Status: PENDING
- EVID-002 | Type: integration | Priority: P1 | Covers: AC-001, AC-010 | Source: tests/test_frontend_contract.py | Status: PENDING
- EVID-003 | Type: integration | Priority: P0 | Covers: AC-007 | Source: tests/test_ubuntu_worker_systemd.py | Status: PENDING
- EVID-004 | Type: integration | Priority: P0 | Covers: AC-008 | Source: updater/rollback tests | Status: PENDING
- EVID-005 | Type: integration | Priority: P0 | Covers: AC-009 | Source: tests/test_sea_speed_auth_v1.py | Status: PENDING
- EVID-006 | Type: end-to-end | Priority: P0 | Covers: AC-011 | Source: exact-head GitHub Actions | Status: PENDING
- EVID-007 | Type: runtime-manual | Priority: P0 | Covers: AC-012 | Source: later authorized production acceptance | Status: PENDING

## Definition of Done

- Canonical Issue #178 contains the current Outcome Contract, approved scope and source authorization.
- SDD artifacts remain aligned with the exact implementation, risk profile, NFRs, test design, correct-course decision and acceptance traceability.
- Actual Git diff remains inside the approved path set and contains no runtime/media/environment artifacts.
- Worker-control implementation has no arbitrary service/command surface and no MediaMTX/camera-relay lifecycle operation.
- Source tests covering all non-runtime-manual acceptance criteria pass.
- PR Change Contract declares Issue #178, the specification, exact changed files, MIXED impact, VPS and Ubuntu applicability, security impact, required risk profile, rollout/rollback and a non-FAIL quality verdict.
- Exact final PR head has successful PR Validation and Quality integration, zero unresolved review threads, fresh base/head/scope check, and expected-head merge protection.
- Source-integration evidence is recorded on Issue #178 and production remains unchanged by source delivery.
- Production safety envelope remains PENDING until separately authorized for the exact merged main SHA.
- Terminal COMPLETE is not claimed until mixed-contour deployment and continuous-HLS worker stop/start evidence are recorded.
