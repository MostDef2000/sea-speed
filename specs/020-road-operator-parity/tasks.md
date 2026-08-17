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
- T-009 [P0] Add focused frontend/API/control/systemd/update/rollback/deploy/auth regression coverage and synchronize the historical analytics-profile Road test with the fixed `road1` browser-control contract while retaining private-source/M2M safety assertions. COMPLETE in source branch.
- T-010 [P0] Validate exact 21-path product source scope, syntax/SDD/secret absence, maintain the canonical PR linked to Issue #206, and keep its Change Contract normalized to the current canonical `- Field: value` parser contract. COMPLETE for PR #207.
- T-011 [P0] Reach exact-head PR Validation and aggregate Quality integration green, remediate only inside approved scope, and merge only the exact green head. COMPLETE for PR #207: final head `69a0abee3f1fc46a2b0d433895e6b48fb6af92a7` merged as `fd449af7bdbd4036517f321b96de31fe206f623b`.
- T-012 [P0] Verify post-merge exact-main Quality and compute a fresh production fingerprint for the mixed release. COMPLETE: Quality #373 / `32020898065` succeeded for exact runtime release `fd449af7bdbd4036517f321b96de31fe206f623b`; production fingerprint `96d52923342e997d03fbd3b1c80a58abf11ea456638ee74087872fa0c32c1018` was authorized with execution intent.
- T-013 [P0] Deploy Ubuntu first through the accepted capability and verify exact source, independent desired states and Road control. COMPLETE: Ubuntu `ONE_COMMAND_FALLBACK` action `1/2` accepted exact `fd449af7bdbd4036517f321b96de31fe206f623b`, Water desired `stopped`, Road desired `running`, Road progression PASS and protected configuration reconciled.
- T-014 [P0] Correct the production-learning delivery capability/action budget in exactly `spec.md`, `plan.md` and `tasks.md`: VPS is `ONE_COMMAND_FALLBACK`, Ubuntu is `ONE_COMMAND_FALLBACK`, operator actions expected `2`; preserve the unchanged authorized runtime release and fingerprint inputs. PENDING corrective PR validation/merge.
- T-015 [P0] After T-014 is merged and post-merge Quality is green, execute the repository-owned exact root VPS privilege-bundle bootstrap for `fd449af7bdbd4036517f321b96de31fe206f623b` as action `2/2`, then retry the canonical Connector VPS deployment and require exact deployment manifest plus `auth_v1_road_private_m2m=passed`. PENDING RUNTIME.
- T-016 [P0] Complete authenticated browser acceptance: Operator visual parity, Road preview auto-available beside AI, Stream Stop/Play, Road Worker Stop with preview/Water unchanged, Road Worker Start with advancing exact-source state, calibration/diagnostics/events and protected public auth. PENDING RUNTIME.
- T-017 [P0] Persist final sanitized acceptance evidence to Issue #206 and close only when all source/runtime criteria are complete. PENDING.

## Requirements traceability

- AC-001 | Task: T-001,T-009 | Evidence: tests/test_frontend_contract.py | Coverage: COVERED
- AC-002 | Task: T-001,T-002,T-009 | Evidence: tests/test_frontend_contract.py | Coverage: COVERED
- AC-003 | Task: T-002,T-009 | Evidence: tests/test_frontend_contract.py and Road browser source contract | Coverage: COVERED
- AC-004 | Task: T-003,T-004,T-009 | Evidence: tests/test_worker_operator_control.py and tests/test_api_contract.py | Coverage: COVERED
- AC-005 | Task: T-004,T-005,T-009 | Evidence: tests/test_worker_operator_control.py | Coverage: COVERED
- AC-006 | Task: T-006,T-009 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py | Coverage: COVERED
- AC-007 | Task: T-006,T-009,T-013 | Evidence: tests/test_ubuntu_worker_deploy_authorized.py plus accepted Ubuntu deployment output | Coverage: COVERED
- AC-008 | Task: T-007,T-009 | Evidence: tests/test_ubuntu_worker_systemd.py | Coverage: COVERED
- AC-009 | Task: T-008,T-009 | Evidence: tests/test_sea_speed_auth_v1.py and tests/test_analytics_profiles.py | Coverage: COVERED
- AC-010 | Task: T-009,T-010,T-011,T-012 | Evidence: synchronized analytics-profile regression, exact 21-path compare, exact-head PR Validation, aggregate Quality integration and post-merge main Quality | Coverage: COVERED
- AC-011 | Task: T-013,T-015,T-016,T-017 | Evidence: accepted Ubuntu deployment, exact VPS bootstrap/deployment manifest plus authenticated Road browser smoke | Coverage: RUNTIME-MANUAL | Reason: protected live-media behavior, cross-service runtime independence and final visual usability require production runtime/browser evidence after separate exact-SHA authorization
- AC-012 | Task: T-014,T-015 | Evidence: exact three-path production-learning corrective PR, PR Validation/Quality/post-merge Quality, Issue #206 authorization/evidence, exact VPS root bootstrap and Connector retry | Coverage: IN PROGRESS

## Definition of Done

- Issue/spec/plan/tasks current: PARTIAL — product Outcome Contract and original 21-path source integration are current; production learning requires this exact three-path SDD correction to merge and Issue evidence to record the corrected action budget.
- Exact changed-file scope verified: PENDING for the corrective branch — it must remain exactly `specs/020-road-operator-parity/spec.md`, `specs/020-road-operator-parity/plan.md`, `specs/020-road-operator-parity/tasks.md`.
- Required tests and evidence complete: NO — corrective source CI, VPS bootstrap/deployment and final browser acceptance remain pending.
- Required CI green: PENDING — corrective PR Validation and aggregate Quality must pass on the same exact final corrective head, followed by post-merge main Quality.
- Exact-green-head merge complete: YES for original product PR #207; NO for the production-learning corrective PR.
- Deployment state resolved: NO — Ubuntu-first is accepted, but VPS-second is blocked on the required exact root privilege-bundle bootstrap followed by Connector retry.
- Runtime acceptance resolved: NO — Road Stop/Start/preview/Water-independence and final protected browser parity remain pending after VPS-second.
- Deferred work recorded: YES — no product/runtime behavior expansion is hidden in this correction; unrelated AI/relay/auth topology remains explicitly out of scope.
- Risks resolved or explicitly accepted: YES — the production-learning capability misclassification is now fail-closed and corrected before further VPS mutation.
- Waivers resolved or current: YES — no waiver is active.

## Completion gate

`COMPLETE` is forbidden until the original exact approved 21-path product source and the exact approved three-path production-learning correction are both merged from exact-green heads with post-merge Quality, Ubuntu action `1/2` remains accepted, VPS action `2/2` exact root privilege-bundle bootstrap succeeds, Connector VPS-second is runtime-verified with exact manifest/private-M2M Auth evidence, authenticated Road browser acceptance passes, and Issue #206 contains terminal evidence.
