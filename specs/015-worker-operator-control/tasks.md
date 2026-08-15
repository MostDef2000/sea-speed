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
- T-007 [P0] Maintain focused source tests for agent/API security, UI/media invariants, systemd independence and maintenance behavior.
- T-008 [P0] Validate the active approved diff and linked SDD; open the bounded remediation PR and reach exact-head CI green.
- T-009 [P0] Re-read main/head/scope/reviews and merge only the exact green remediation head with expected-head protection.
- T-010 [P0] Stop at the production boundary after remediation merge until a new exact-SHA production authorization; then collect mixed-contour runtime evidence.
- T-011 [P0] Add the fixed `sea_speed_worker_control_v1` marker to successful Ubuntu agent responses and make VPS FastAPI reject a missing/mismatched marker before returning success.
- T-012 [P0] Add deterministic `ubuntu-worker` exact-artifact build/validation as release-specific provenance while preserving the existing quality-evidence v1 `vps`/legacy-`edge` contract.

## Active remediation scope

The current correct-course source gate is exactly these 9 paths; the historical 17-path PR #179 scope remains immutable audit history:

1. `api/app/main.py`
2. `deploy/worker/ubuntu/worker-control-agent.py`
3. `scripts/quality/build_exact_artifacts.py`
4. `scripts/quality/validate_exact_artifacts.py`
5. `tests/test_worker_operator_control.py`
6. `tests/quality/test_quality_architecture.py`
7. `specs/015-worker-operator-control/spec.md`
8. `specs/015-worker-operator-control/plan.md`
9. `specs/015-worker-operator-control/tasks.md`

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
- AC-012 | Task: T-010 | Evidence: newly authorized production service/HLS acceptance on Issue #178 | Coverage: RUNTIME-MANUAL | Reason: source CI cannot prove live HLS continuity across a real production worker stop/start
- AC-013 | Task: T-011, T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-014 | Task: T-012, T-008 | Evidence: tests/quality/test_quality_architecture.py plus aggregate exact-artifact/release-evidence jobs | Coverage: COVERED

## Delivery evidence

- EVID-001 | Type: unit | Priority: P0 | Covers: AC-002, AC-003, AC-004, AC-005, AC-006, AC-013 | Source: tests/test_worker_operator_control.py | Status: PENDING REMEDIATION CI
- EVID-002 | Type: integration | Priority: P1 | Covers: AC-001, AC-010 | Source: tests/test_frontend_contract.py | Status: PREVIOUSLY GREEN; aggregate CI will revalidate
- EVID-003 | Type: integration | Priority: P0 | Covers: AC-007 | Source: tests/test_ubuntu_worker_systemd.py | Status: PREVIOUSLY GREEN; aggregate CI will revalidate
- EVID-004 | Type: integration | Priority: P0 | Covers: AC-008 | Source: updater/rollback tests | Status: PREVIOUSLY GREEN; aggregate CI will revalidate
- EVID-005 | Type: integration | Priority: P0 | Covers: AC-009 | Source: tests/test_sea_speed_auth_v1.py | Status: PREVIOUSLY GREEN; aggregate CI will revalidate
- EVID-006 | Type: end-to-end | Priority: P0 | Covers: AC-011, AC-014 | Source: exact-head GitHub Actions | Status: PENDING REMEDIATION CI
- EVID-007 | Type: runtime-manual | Priority: P0 | Covers: AC-012 | Source: later newly authorized production acceptance | Status: PENDING
- EVID-008 | Type: release-provenance | Priority: P0 | Covers: AC-014 | Source: deterministic `vps`/`edge` quality artifacts plus release-specific `ubuntu-worker` artifact in the exact-artifacts manifest; release-manifest v2 binds the Ubuntu archive digest and exact-manifest SHA-256 | Status: PENDING REMEDIATION CI

## Definition of Done

- Issue/spec/plan/tasks current: YES for the active correct-course remediation; production feedback records the pre-mutation provenance blocker.
- Exact changed-file scope verified: must remain exactly the approved 9 remediation paths above.
- Required tests and evidence complete: protocol/provenance source tests and full aggregate CI required before remediation merge; AC-012 remains runtime-manual after a new production authorization.
- Required CI green: exact final remediation PR head must have PR Validation and Quality integration SUCCESS.
- Exact-green-head merge complete: only after fresh main/base/head/scope/review verification and expected-head merge.
- Deployment state resolved: source remediation does not deploy; the previous production attempt performed zero runtime writes and any future rollout requires a new exact-SHA safety envelope.
- Release provenance resolved: exact artifact inventory must validate `vps`, release-specific `ubuntu-worker`, and legacy `edge`; quality-evidence v1 remains valid for its existing `vps`/`edge` enum, while release-manifest v2 directly binds the Ubuntu artifact and the complete exact-artifacts manifest hash.
- Runtime acceptance resolved: NO until newly authorized mixed-contour stop/start plus continuous-HLS evidence is recorded.
- Deferred work recorded: production rollout and runtime-manual AC-012 are the only expected deferred items after remediation source merge.
- Risks resolved or explicitly accepted: all source mitigations including RISK-006/RISK-007 must pass; residual production risks require runtime acceptance evidence.
- Waivers resolved or current: no waiver is currently required; any future waiver must satisfy the durable waiver contract and cannot bypass exact artifacts or production authorization.

## Completion gate

- Active source gate: exact 9-path remediation scope, current SDD, REQUIRED risk profile, non-FAIL quality verdict, required source tests, PR Validation, Quality integration, review-thread check and expected-head merge.
- Production gate: a new `PRODUCTION APPROVED <exact-remediation-merged-sha>` with current fingerprint is required before any VPS or Ubuntu runtime mutation; the prior `dc0fd44d...` approval is stale for the new SHA.
- Mixed-contour gate: do not deploy VPS alone if Ubuntu exact-artifact/release admission is unavailable; fail closed before runtime mutation.
- Terminal gate: `COMPLETE` is forbidden until worker/control-service identity, protocol compatibility, exact mixed-contour provenance and Camera 1 HLS continuity are accepted in production.
