# Delivery Tasks: Road Operator parity

- Specification: specs/020-road-operator-parity/spec.md
- Plan: specs/020-road-operator-parity/plan.md
- Issue: #206
- Status: Implementing

## Delivery tasks

- T-001 [P0] Replace the simplified Road page with the canonical Operator visual hierarchy while keeping Road-specific labels and logical `road1` analytics. COMPLETE in source branch.
- T-002 [P0] Keep the Road clean-live panel permanently adjacent to the AI panel and auto-connect the existing protected `road1` preview with one contextual Stream action and retry/recovery semantics. COMPLETE in source branch.
- T-003 [P0] Add fixed authenticated VPS Road worker-control routes without introducing arbitrary target/service parameters. COMPLETE in source branch.
- T-004 [P0] Extend the private Ubuntu control agent from fixed Water-only to a fixed two-target Water/Road allowlist. COMPLETE in source branch.
- T-005 [P0] Add independent Road operator desired `running|stopped` state and preserve it through start/stop. COMPLETE in source branch.
- T-006 [P0] Preserve independent Water/Road desired states through exact update, rollback and authorized deployment verification. COMPLETE in source branch.
- T-007 [P0] Keep the hardened control systemd unit write-bounded to Water/Road runtime desired-state roots. COMPLETE in source branch.
- T-008 [P0] Keep private Worker-to-VPS ingress exact and explicitly exclude all Water/Road browser-control routes. COMPLETE in source branch.
- T-009 [P0] Add focused frontend/API/control/systemd/update/rollback/deploy/auth regression coverage. COMPLETE in source branch.
- T-010 [P0] Validate exact 20-path scope, syntax/SDD/secret absence, and open the canonical PR linked to Issue #206. PENDING.
- T-011 [P0] Reach exact-head PR Validation and aggregate Quality integration green, remediate only inside approved scope, and merge only the exact green head. PENDING.
- T-012 [P0] Verify post-merge exact-main Quality and compute a fresh production fingerprint for the mixed release. PENDING.
- T-013 [P0] After separate exact-SHA production authorization, deploy Ubuntu first through the accepted capability and verify exact source, independent desired states and Road control. PENDING PRODUCTION AUTHORIZATION.
- T-014 [P0] Deploy VPS second through Connector, preserving Authentik/private M2M boundaries and exact release provenance. PENDING PRODUCTION AUTHORIZATION.
- T-015 [P0] Complete authenticated browser acceptance: Operator visual parity, Road preview auto-available beside AI, Stream Stop/Play, Road Worker Stop with preview/Water unchanged, Road Worker Start with advancing exact-source state, calibration/diagnostics/events and protected public auth. PENDING RUNTIME.
- T-016 [P0] Persist final sanitized acceptance evidence to Issue #206 and close only when all source/runtime criteria are complete. PENDING.

## Requirements traceability

- AC-001 | Task: T-001,T-009 | Evidence: tests/test_frontend_contract.py | Coverage: COVERED
- AC-002 | Task: T-001,T-002,T-009 | Evidence: tests/test_frontend_contract.py | Coverage: COVERED
- AC-003 | Task: T-002,T-009 | Evidence: tests/test_frontend_contract.py and Road browser source contract | Coverage: COVERED
- AC-004 | Task: T-003,T-004,T-009 | Evidence: tests/test_worker_operator_control.py and tests/test_api_contract.py | Coverage: COVERED
- AC-005 | Task: T-004,T-005,T-009 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-006 | Task: T-006,T-009 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py | Coverage: COVERED
- AC-007 | Task: T-006,T-009 | Evidence: tests/test_ubuntu_worker_deploy_authorized.py | Coverage: COVERED
- AC-008 | Task: T-007,T-009 | Evidence: tests/test_ubuntu_worker_systemd.py | Coverage: COVERED
- AC-009 | Task: T-008,T-009 | Evidence: tests/test_sea_speed_auth_v1.py | Coverage: COVERED
- AC-010 | Task: T-010,T-011,T-012 | Evidence: exact-head PR Validation, aggregate Quality integration and post-merge main Quality | Coverage: COVERED
- AC-011 | Task: T-013,T-014,T-015,T-016 | Evidence: exact Ubuntu/VPS deployment manifests plus authenticated Road browser smoke | Coverage: RUNTIME-MANUAL | Reason: protected live-media behavior, cross-service runtime independence and final visual usability require production runtime/browser evidence after separate exact-SHA authorization

## Definition of Done

- Issue/spec/plan/tasks current: YES — Issue #206 and SDD 020 define the approved outcome, exact scope and runtime plan.
- Exact changed-file scope verified: NO — final branch compare must prove exactly the approved 20 paths before merge.
- Required tests and evidence complete: NO — source tests/CI and production browser evidence remain pending.
- Required CI green: NO — exact final head must pass PR Validation and aggregate Quality integration.
- Exact-green-head merge complete: NO — merge is pending exact-head gates and freshness checks.
- Deployment state resolved: NO — MIXED runtime deployment requires fresh exact-main production authorization and Ubuntu-first/VPS-second execution.
- Runtime acceptance resolved: NO — Road Stop/Start/preview/Water-independence and final protected browser parity remain pending.
- Deferred work recorded: YES — no hidden scope expansion is deferred inside this Outcome; unrelated AI/relay/auth topology remains explicitly out of scope.
- Risks resolved or explicitly accepted: YES — identified source/runtime risks have bounded mitigations; residual browser/runtime risk is gated by production acceptance.
- Waivers resolved or current: YES — no waiver is active.

## Completion gate

`COMPLETE` is forbidden until the exact approved 20-path source is merged from an exact-green head, post-merge exact-main Quality is successful, a fresh mixed production envelope is authorized, Ubuntu-first and VPS-second deployments are runtime-verified, authenticated Road browser acceptance passes, and Issue #206 contains terminal evidence.
