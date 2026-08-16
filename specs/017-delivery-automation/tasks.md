# Delivery Tasks: Two-intent delivery automation

- Specification: specs/017-delivery-automation/spec.md
- Issue: #178
- Active governance continuation: #195
- Status: In implementation
- Active remediation: three-state terminal interaction contract

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
- TASK-019: Require an explicit operator-visible six-field Scope block before every `OUTCOME APPROVED` request or re-authorization request; update agent/governance/task-runtime/PM contracts so a bare approval prompt is invalid and scope cannot be left implicit.
- TASK-020: Make source authorization admission fail closed. Require `VISIBLE_SCOPE_PRESENTED=YES` and `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES` before branch/source writes; require the Scope block as the last substantive assistant block before the request; reject bare, incomplete, stale or non-adjacent approval sequences; and recover only through a newly rendered Scope followed by a new approval token.
- TASK-021: Deliver TASK-020 as an exact seven-path CONTROL_PLANE remediation limited to `AGENTS.md`, canonical governance, PM contract, task runtime and feature 017 spec/plan/tasks. Derived Change Contract production class is CONTROL_PLANE; VPS/Ubuntu/Windows runtime deployment impact is NONE.
- TASK-022: Validate TASK-020 through exact content review, SDD validation, PR Validation and Quality integration on one exact final head; use active `Risk profile: NOT REQUIRED` for this CONTROL_PLANE Change Contract while retaining broader feature `RISK-*` records in a separate historical audit section; merge only after fresh main/head/scope/review checks and expected-head protection.
- TASK-023: For canonical Issue #195, update exactly six active orchestration/governance contracts so returning control is legal only as `DONE`, `BLOCKED`, or `HUMAN DECISION REQUIRED`; classify `FAILED` as an internal event and prohibit progress-only terminal handoffs while deterministic authorized continuation exists.
- TASK-024: Add `tests/test_delivery_terminal_states.py` to regression-protect the six-contract state set, external-blocker evidence/unblock semantics, structured human decision semantics, automatic remediation/resume, and the absence of legacy terminal-state wording.
- TASK-025: Deliver TASK-023/024 as an exact ten-path CONTROL_PLANE PR for Issue #195, automatically remediate in-scope CI, verify exact ten-path scope and fresh reviews/main, merge the exact green head with expected-head protection, verify post-merge quality, persist terminal evidence in Issue #195, and close it as completed.

## Requirements traceability

- AC-001 | Task: TASK-002 | Evidence: `AGENTS.md`, `contracts/SEA_SPEED_GOVERNANCE.md`, `contracts/SEA_SPEED_DELIVERY_POLICY.md`, `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`, `contracts/branches/project-manager.md` | Coverage: COVERED
- AC-002 | Task: TASK-002,TASK-014 | Evidence: governance/PM continuation rules and exact-scope CI remediation policy | Coverage: COVERED
- AC-003 | Task: TASK-004 | Evidence: `scripts/release/parse_runtime_execution_request.py`, `tests/test_runtime_execution_request.py` | Coverage: COVERED
- AC-004 | Task: TASK-005 | Evidence: `scripts/release/verify_production_authorization.py` plus execution-intent unit coverage in `tests/test_runtime_execution_request.py` | Coverage: COVERED
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
- AC-015 | Task: TASK-019 | Evidence: `AGENTS.md`, `contracts/SEA_SPEED_GOVERNANCE.md`, `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`, `contracts/branches/project-manager.md`, plus feature 017 SDD | Coverage: COVERED
- AC-016 | Task: TASK-020,TASK-021,TASK-022 | Evidence: same four contracts define the two admission flags, `DISCUSSION` recovery and source-write prohibition; feature 017 SDD records the regression/recovery sequence; exact seven-path PR Validation and Quality integration | Coverage: COVERED
- AC-017 | Task: TASK-023,TASK-024,TASK-025 | Evidence: six active orchestration/governance contracts plus `tests/test_delivery_terminal_states.py`, exact ten-path PR Validation/Quality integration, fresh expected-head merge and Issue #195 terminal evidence | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current: Issue #178 carries the historical automation/runtime delivery; Issue #195 carries the accepted terminal-interaction governance continuation; feature 017 captures both.
- [x] Original hardening release deployed/accepted: exact Ubuntu target `8dc74762a344dbf763d3ce1e7ecb1bac6872affb` was deployed through the one-command fallback and worker Stop/Start was confirmed independent from continuously available Camera 1 HLS.
- [x] Scope-before-approval rule merged: contracts require visible exact Scope before every approval request.
- [x] Fail-closed source admission merged: contracts require `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, block source writes on invalid ordering, and require fresh Scope+token recovery.
- [x] Historical seven-path fail-closed remediation source/CI/merge completed before Issue #195.
- [x] Active risk-profile applicability aligned: the Issue #195 CONTROL_PLANE Change Contract is `NOT REQUIRED`; historical feature risks are preserved outside the active Risk profile section.
- [x] Terminal interaction source implemented on the Issue #195 branch: six active contracts define `DONE`, `BLOCKED`, `HUMAN DECISION REQUIRED`; `FAILED` is not terminal; deterministic progress-only stops are forbidden.
- [x] Terminal interaction regression added: `tests/test_delivery_terminal_states.py` covers AC-017 semantics.
- [ ] Exact changed-file scope verified: ten approved CONTROL_PLANE paths only; no frontend/API/deployment/runtime implementation file changes.
- [ ] Required tests and evidence complete: terminal-state regression, SDD validation and repository quality checks prove AC-017.
- [ ] Required CI green: PR Validation and aggregate Quality integration succeed on the same exact final head.
- [ ] Exact-green-head merge complete: fresh main/head/scope/review gate passes and merge uses expected-head protection.
- [ ] Post-merge quality complete and Issue #195 terminal evidence persisted/closed.
- [x] Deployment state resolved: NOT REQUIRED for this CONTROL_PLANE-only continuation.
- [x] Runtime acceptance resolved: NOT REQUIRED for this CONTROL_PLANE-only continuation.
- [x] Deferred work recorded: provisioning restricted zero-touch Ubuntu transport and Windows production automation remain separate future capabilities.
- [x] Risks resolved or explicitly accepted: active Risk profile is NOT REQUIRED; historical broader-feature risk rows remain audit-only outside the active section.
- [x] Waivers resolved or current: no quality waiver is requested; all hard gates remain mandatory.

## Completion gate

The delivery-automation hardening is valid only while both interaction invariants hold. Source authorization follows **Scope first, approval second** as a fail-closed transition: new work or material re-authorization displays the complete six-field Scope block immediately before requesting `OUTCOME APPROVED`, and source writes are forbidden unless both admission flags are `YES`. After authorization, execution ownership remains with the Delivery Orchestrator: deterministic authorized work continues without status-only handoffs until exactly one terminal interaction state is justified — `DONE`, `BLOCKED` with concrete external blocker/evidence/unblock/next action, or `HUMAN DECISION REQUIRED` with a structured protected decision and exact response format. `FAILED` is an event to remediate or classify, never a terminal interaction state.