# Delivery Tasks: Worker operator control

- Specification: specs/015-worker-operator-control/spec.md
- Plan: specs/015-worker-operator-control/plan.md
- Issue: #178
- Status: Single dynamic Stream action remediation

## Delivery tasks

- T-001 [P0] Implement bounded Ubuntu worker-control status/start/stop for literal `sea-speed-worker.service`. COMPLETE in PR #179.
- T-002 [P0] Install independent `sea-speed-worker-control.service`. COMPLETE in PR #179 source.
- T-003 [P0] Add protected VPS FastAPI worker-control routes. COMPLETE in PR #179 source.
- T-004 [P1] Add distinct worker UI control while preserving Camera 1 HLS/browser lifecycle. COMPLETE in PR #179 source.
- T-005 [P0] Preserve desired `running|stopped` state through update/rollback. COMPLETE.
- T-006 [P0] Keep Ubuntu-to-VPS ingress restricted to existing telemetry/config endpoints. COMPLETE.
- T-007 [P0] Maintain focused product/security/media/systemd/update/rollback tests. COMPLETE; aggregate CI remains authoritative.
- T-008 [P0] Validate approved diff/SDD, open bounded PR and reach exact-head CI green. COMPLETE for historical source cycles.
- T-009 [P0] Re-read main/head/scope/reviews and merge only exact green head with expected-head protection. COMPLETE for historical source cycles.
- T-010 [P0] Stop at production boundary until exact-SHA production authorization is current. COMPLETE as an ongoing hard gate.
- T-011 [P0] Add `sea_speed_worker_control_v1` and VPS fail-closed compatibility guard. COMPLETE in PR #180.
- T-012 [P0] Add deterministic `ubuntu-worker` exact artifact. COMPLETE in PR #180.
- T-013 [P0] Correct VPS origin health to 8010. COMPLETE in PR #181.
- T-014 [P0] Add 8010 regression evidence. COMPLETE in PR #181.
- T-015 [P0] Align historical deploy-contract assertions with 8010. COMPLETE in PR #181.
- T-016 [P0] Make VPS first-parent admission pipefail-safe. COMPLETE in PR #182.
- T-017 [P0] Add first-parent regression evidence. COMPLETE in PR #182.
- T-018 [P0] Make stale VPS release pruning best-effort after verified persistence. COMPLETE in PR #183.
- T-019 [P0] Add pruning/retention ordering regression. COMPLETE in PR #183.
- T-020 [P0] Complete corrected VPS deployment evidence. COMPLETE.
- T-021 [P0] Replace unsupported Ubuntu updater quality CLI argument with `--workflow-file quality-integration.yml` and execute verifier parser in tests. COMPLETE in PR #186.
- T-022 [P0] Preserve exact modern/legacy worker-control topology across failed activation and rollback. COMPLETE in PR #186.
- T-023 [P0] Synchronize Ubuntu runbooks and transaction audit for production learning #5. COMPLETE in PR #186.
- T-024 [P0] Merge exact-green PR #186, verify push/main quality and obtain fresh Ubuntu production envelope. COMPLETE.
- T-025 [P0] Prepare/activate authorized Ubuntu release and execute Stop/HLS/Start/HLS acceptance. COMPLETE: Ubuntu exact source `8dc74762a344dbf763d3ce1e7ecb1bac6872affb` accepted and HLS remained continuous.
- T-026 [P0] Make updater `cleanup()` capture and return the primary exit status while treating temporary cleanup as best-effort. COMPLETE in PR #187.
- T-027 [P0] Add executable EXIT-trap cleanup regression. COMPLETE in PR #187.
- T-028 [P0] Merge exact-green cleanup remediation and complete production continuation. COMPLETE.
- T-029 [P0] Keep Worker control in the top status strip and render only `▶` / `■` with dynamic accessibility. COMPLETE in PR #192.
- T-030 [P0] Remove the worker Stop `confirm(...)` gate. COMPLETE in PR #192.
- T-031 [P0] Move HLS controls from the Live camera card into the top Stream status item. COMPLETE in PR #192, but browser acceptance found the simultaneous Play+Stop presentation unsuitable.
- T-032 [P0] Extend frontend contract for top-strip placement/no Live camera duplicates. COMPLETE in PR #192; superseded for Stream cardinality by T-034/T-035.
- T-033 [P0] Merge/deploy exact-green five-path UI source. COMPLETE: VPS exact source `0c2651629f517f939b8d18cacbc624654e8c4e11` runtime-verified; final browser acceptance FAILED because two Stream buttons were simultaneously visible.
- T-034 [P0] Replace `connectBtn` + `disconnectBtn` with exactly one `streamControlBtn` in the top Stream status item.
- T-035 [P0] Render `streamControlBtn` contextually: Play when HLS is not desired/active, Stop when HLS is desired/active; update dynamic `aria-label` and `title`.
- T-036 [P0] Preserve the existing HLS connect/disconnect/retry/recovery/autoconnect lifecycle while routing manual action through the single contextual button.
- T-037 [P0] Extend `tests/test_frontend_contract.py` to prove one Stream action ID, no legacy second Stream button, dynamic action rendering/accessibility and no Live camera controls.
- T-038 [P0] Merge only exact-green five-path remediation, obtain fresh exact-release VPS production authorization/execution intent, deploy VPS only, and repeat browser smoke before closing #178.

## Active remediation scope

Exact authorized scope after the fail-closed visible Scope gate:

1. `frontend/sea-speed/index.html`
2. `tests/test_frontend_contract.py`
3. `specs/015-worker-operator-control/spec.md`
4. `specs/015-worker-operator-control/plan.md`
5. `specs/015-worker-operator-control/tasks.md`

Product correction: the top `STREAM` item exposes exactly one contextual action, not simultaneous Play and Stop buttons. `WORKER` remains one contextual action. The Live camera card remains free of Stream action buttons.

Production impact is `VPS`; Ubuntu Worker/relay and Windows Worker updates are NOT REQUIRED. API, MediaMTX/relay, worker agent, systemd, credentials and AI semantics are outside this continuation. Source authorization does not authorize production mutation.

## Requirements traceability

- AC-001 | Task: T-004,T-029,T-034,T-035,T-037 | Evidence: tests/test_frontend_contract.py | Coverage: CURRENT
- AC-002 | Task: T-003,T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-003 | Task: T-001,T-003,T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-004 | Task: T-001,T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-005 | Task: T-001,T-007 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-006 | Task: T-001,T-005,T-007 | Evidence: tests/test_worker_operator_control.py plus updater/rollback tests | Coverage: COVERED
- AC-007 | Task: T-002,T-007 | Evidence: tests/test_ubuntu_worker_systemd.py | Coverage: COVERED
- AC-008 | Task: T-005,T-022 | Evidence: updater/rollback tests | Coverage: COVERED
- AC-009 | Task: T-006 | Evidence: tests/test_sea_speed_auth_v1.py | Coverage: COVERED
- AC-010 | Task: T-004,T-036,T-037 | Evidence: frontend and worker-control tests | Coverage: CURRENT
- AC-011 | Task: T-038 | Evidence: exact-head PR Validation and Quality integration | Coverage: PENDING
- AC-012 | Task: T-025,T-038 | Evidence: accepted Ubuntu Stop/HLS/Start/HLS plus current VPS browser smoke | Coverage: RUNTIME-MANUAL
- AC-021 | Task: T-029,T-030,T-034,T-035,T-037,T-038 | Evidence: frontend contract plus production Operator UI smoke | Coverage: CURRENT

## Delivery evidence

- EVID-001 | Type: unit/integration | Priority: P0 | Source: existing worker-control/auth/systemd/updater/rollback tests | Status: GREEN historical; aggregate CI revalidates
- EVID-002 | Type: integration | Priority: P0 | Source: tests/test_frontend_contract.py | Status: REQUIRED CURRENT
- EVID-003 | Type: end-to-end | Priority: P0 | Source: exact-head GitHub Actions | Status: PENDING CURRENT PR
- EVID-004 | Type: runtime-manual | Priority: P0 | Source: accepted Ubuntu Stop/HLS/Start/HLS evidence | Status: ACCEPTED
- EVID-005 | Type: runtime-manual | Priority: P0 | Source: deployed VPS Operator UI single-action browser smoke | Status: PENDING

## Definition of Done

- Issue/spec/plan/tasks current: YES for the single-action remediation once this SDD update is merged.
- Exact changed-file scope: must remain within the exact five authorized paths and target 5/5 paths.
- Required source behavior: exactly one `streamControlBtn`; no `connectBtn`/`disconnectBtn`; dynamic Play/Stop action; no Live camera duplicates; Worker remains one dynamic control.
- Required tests: frontend regression plus aggregate existing contracts.
- Required CI: exact final head PR Validation and Quality integration SUCCESS.
- Merge: fresh main/head/scope/review verification and expected-head protection.
- Deployment: VPS REQUIRED after fresh exact-SHA production authorization; Ubuntu/Windows NOT REQUIRED.
- Runtime acceptance: authenticated browser shows one Stream action and one Worker action, no duplicate controls, and UI is usable; HLS behavior remains intact.
- Waivers: none.

## Completion gate

`COMPLETE` for Issue #178 is forbidden until the exact-green five-path remediation is merged, the new exact VPS source is separately authorized and deployed, and browser acceptance confirms a single contextual Stream action with no duplicates.
