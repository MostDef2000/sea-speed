# Delivery Tasks: Two-intent delivery automation

- Specification: specs/017-delivery-automation/spec.md
- Issue: #178
- Status: In implementation

## Delivery tasks

- TASK-001: Keep the exact approved repository scope limited to the 23 paths recorded in Issue #178 comment `5305673441`; no API/frontend/media/AI algorithm/credential/sudoers/Windows-runtime expansion.
- TASK-002: Update governance, delivery policy, task runtime, release-readiness and Delivery Orchestrator contracts so one `OUTCOME APPROVED` covers deterministic in-scope source continuation and the normal interaction budget is two protected decisions.
- TASK-003: Extend the PR Change Contract and validator with per-contour runtime execution capability plus exact operator-action count; reject required missing capabilities and inconsistent counts.
- TASK-004: Implement strict `parse_runtime_execution_request.py` for exact three-line production approval + fingerprint + `Execution-Intent: EXECUTE` on an open canonical Issue by an authorized actor.
- TASK-005: Extend `verify_production_authorization.py` without changing fingerprint payload so historical two-line authorization remains valid, exact third-line execution intent is detectable/required when requested, and exact runtime contours are emitted for routing.
- TASK-006: Add `deploy-runtime-request.yml` as a non-mutating parser/verifier/router that delegates applicable VPS/Ubuntu contours and fails closed for Windows automation outside this scope.
- TASK-007: Add reusable protected `deploy-ubuntu-worker.yml` with current-main first-parent, exact push/main quality, durable authorization, exact artifact/release provenance and production environment gates before transport.
- TASK-008: Add exact-artifact-bound `deploy-authorized.sh` that owns target-side exact staging, execution-intent verification, updater activation, identity verification, deployment manifest and exact rollback on post-activation failure.
- TASK-009: Include `deploy-authorized.sh` in deterministic `ubuntu-worker` exact-artifact bytes.
- TASK-010: Add one-command Ubuntu fallback generation when independently provisioned restricted zero-touch transport is unavailable; the workflow must not claim runtime success until mutation actually occurs.
- TASK-011: Execute the real `deploy-authorized.sh` in an isolated sandbox for success, desired stopped, authorization failure and post-activation rollback scenarios.
- TASK-012: Update Ubuntu operations documentation to make `deploy-authorized.sh` the normal transaction and low-level prepare/activate diagnostic/recovery primitives rather than routine user checkpoints.
- TASK-013: Open one exact 23-path PR linked to feature 017, declare Ubuntu-only runtime impact, `Ubuntu worker execution capability: ONE_COMMAND_FALLBACK`, `Operator actions expected: 1`, and preserve all protected exclusions.
- TASK-014: Remediate PR/CI findings automatically only inside the approved 23 paths; any material path/protected-boundary expansion returns to source authorization.
- TASK-015: Merge only the exact green head after fresh main/head/scope/review checks and expected-head protection; verify exact push/main PR Validation and Quality integration plus exact Ubuntu artifact evidence.
- TASK-016: After merge, obtain one fresh exact-release production approval carrying `Execution-Intent: EXECUTE`; do not ask separately for prepare/activate execution intent.
- TASK-017: Route the authorized Ubuntu release through the protected workflow. Until restricted zero-touch transport is independently provisioned, expose only the single exact fallback action and then collect deployment/runtime evidence.
- TASK-018: Complete parent Issue #178 product acceptance only after exact Ubuntu deployment plus worker Stop/Start behavior and continuous Camera 1 HLS evidence are proven.

## Requirements traceability

- AC-001 | Task: TASK-002 | Evidence: `AGENTS.md`, `contracts/SEA_SPEED_GOVERNANCE.md`, `contracts/SEA_SPEED_DELIVERY_POLICY.md`, `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`, `contracts/branches/project-manager.md` | Coverage: COVERED
- AC-002 | Task: TASK-002,TASK-014 | Evidence: governance/PM continuation rules and exact-scope CI remediation policy | Coverage: COVERED
- AC-003 | Task: TASK-004 | Evidence: `scripts/release/parse_runtime_execution_request.py`, `tests/test_runtime_execution_request.py` | Coverage: COVERED
- AC-004 | Task: TASK-005 | Evidence: `scripts/release/verify_production_authorization.py`, production authorization tests/CI | Coverage: COVERED
- AC-005 | Task: TASK-006 | Evidence: `.github/workflows/deploy-runtime-request.yml`, workflow architecture/policy tests | Coverage: COVERED
- AC-006 | Task: TASK-003 | Evidence: `.github/pull_request_template.md`, `scripts/ci/validate_change_contract.py`, `tests/test_change_contract.py` | Coverage: COVERED
- AC-007 | Task: TASK-007 | Evidence: `.github/workflows/deploy-ubuntu-worker.yml`, `scripts/quality/validate_workflow_policy.py`, `tests/quality/test_quality_architecture.py` | Coverage: COVERED
- AC-008 | Task: TASK-007,TASK-010 | Evidence: explicit restricted-transport capability gate, one-command fallback artifact and fail-non-success behavior | Coverage: COVERED
- AC-009 | Task: TASK-008,TASK-011 | Evidence: real launcher sandbox success plus generated Ubuntu deployment manifest | Coverage: COVERED
- AC-010 | Task: TASK-011 | Evidence: desired-stopped and authorization-before-mutation cases in `tests/test_ubuntu_worker_deploy_authorized.py` | Coverage: COVERED
- AC-011 | Task: TASK-008,TASK-011 | Evidence: real launcher post-activation verification failure restores previous source/control topology | Coverage: COVERED
- AC-012 | Task: TASK-009 | Evidence: `scripts/quality/build_exact_artifacts.py` plus deterministic artifact architecture test | Coverage: COVERED
- AC-013 | Task: TASK-013,TASK-014,TASK-015 | Evidence: exact 23-path PR, exact-head PR Validation/Quality integration, fresh merge gate and post-merge push/main evidence | Coverage: COVERED
- AC-014 | Task: TASK-001,TASK-015,TASK-016 | Evidence: exact diff exclusions plus separate fresh production envelope after source merge | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current: Issue #178 carries the approved 23-path automation scope and feature 017 captures the accepted architecture.
- [ ] Exact changed-file scope verified: final branch diff must equal the 23 approved paths with no protected product/runtime expansion.
- [ ] Required tests and evidence complete: request parser, production verifier, Change Contract, workflow policy/architecture, real Ubuntu transaction sandbox and exact-artifact tests pass.
- [ ] Required CI green: PR Validation and aggregate Quality integration succeed on the same exact final head.
- [ ] Exact-green-head merge complete: fresh main/head/scope/review gate passes and merge uses expected-head protection.
- [ ] Deployment state resolved: after merge, exact Ubuntu hardening release is deployed or an exact truthful fallback blocker is recorded under a fresh production envelope.
- [ ] Runtime acceptance resolved: exact Ubuntu runtime identity plus parent #178 Stop/Start and continuous Camera 1 HLS evidence are accepted before product completion.
- [x] Deferred work recorded: provisioning a restricted zero-touch Ubuntu transport and Windows production automation are separate future capabilities; this task provides safe one-command Ubuntu fallback and fail-closed Windows routing.
- [ ] Risks resolved or explicitly accepted: RISK-001 through RISK-006 require exact-head CI and runtime evidence where applicable.
- [x] Waivers resolved or current: no quality waiver is requested; all hard gates remain mandatory.

## Completion gate

Source integration is complete only after the exact 23-path green head is merged and exact push/main quality/artifact evidence is recorded. The process-hardening outcome reaches runtime completion only after a fresh exact-SHA production authorization with `Execution-Intent: EXECUTE` drives the Ubuntu contour through the protected workflow/one-command fallback and runtime evidence is valid. Parent Issue #178 reaches `COMPLETE` only after worker Stop/Start is proven independent from continuously available Camera 1 HLS.
