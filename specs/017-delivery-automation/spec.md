# Specification: Two-intent delivery automation

- Issue: #178
- Active governance continuation: #195
- Status: In implementation

## Product outcome

Sea Speed delivery should require the operator to make only the decisions that are genuinely protected: one source-outcome authorization and, for each exact production release, one authorization carrying explicit execution intent. Deterministic branch/PR/CI/merge/deployment sub-stages must be repository-owned, fail closed, and automated where capability exists. Ubuntu Worker deployment must have a protected reusable workflow and one target-side transaction so preparation, activation, verification, evidence and rollback are not exposed as serial confirmation prompts. The single source-authorization decision must always be preceded by a visible, exact scope presentation so the operator knows precisely what `OUTCOME APPROVED` will authorize. The scope/approval presentation order is itself a fail-closed state gate: an approval token received without the immediately preceding complete Scope block cannot authorize repository writes. The Orchestrator must also retain execution ownership instead of stopping on intermediate status: control returns to the operator only as `DONE`, `BLOCKED` with a concrete external blocker, or `HUMAN DECISION REQUIRED` with a structured protected decision.

## User scenarios

### Scenario 1 - Scope is visible before source approval

Before the Delivery Orchestrator asks the operator for `OUTCOME APPROVED`, it displays a concrete Scope block containing the product outcome, exact repository paths, protected/out-of-scope boundaries, runtime/production impact and acceptance evidence. The Scope block is the last substantive assistant content before the approval request, and the approval is the immediately following user decision. If a later material change requires re-authorization, the revised scope is displayed under the same ordering rule before the fresh approval request.

### Scenario 2 - Source delivery continues after one approval

After the operator supplies a validly admitted `OUTCOME APPROVED` for the displayed exact Implementation Scope Check, the Delivery Orchestrator creates the branch, implements the bounded outcome, repairs PR metadata, remediates CI inside the approved paths and merges the exact green head without requesting another routine source approval.

### Scenario 3 - One production decision can authorize and execute

The operator may post exactly three lines on the canonical Issue: `PRODUCTION APPROVED <sha>`, the current authorization fingerprint, and `Execution-Intent: EXECUTE`. Repository-owned request tooling treats the first two lines as authority and the third as execution intent, independently verifies the complete envelope, derives the exact required runtime contours and routes only those contours.

### Scenario 4 - Ubuntu deployment is one transaction

When Ubuntu Worker/relay deployment is required, the protected Ubuntu workflow validates exact-main quality/provenance and then either uses a separately provisioned restricted Connector transport or emits one exact server-pull bootstrap. The target-side `deploy-authorized.sh` performs exact staging, authorization/execution-intent verification, updater activation, exact identity verification, evidence and rollback as one transaction.

### Scenario 5 - Missing runtime execution capability fails before release

A runtime-impacting PR must declare execution capability for VPS, Ubuntu Worker/relay and Windows AI Worker plus the expected manual-action count. A required contour cannot be admitted with `MISSING`; a one-command fallback is explicit and counted.

### Scenario 6 - Misordered or bare source approval fails closed

If the operator sends `OUTCOME APPROVED` when the immediately preceding assistant turn does not contain the complete current six-field Scope block, source authorization admission remains blocked. No branch or source/SDD write may begin. The Delivery Orchestrator returns to `DISCUSSION`, renders the full current Scope again as the last substantive block before the request, and accepts only a new approval supplied in the immediately following user turn; the misplaced token is never retroactively reused.

### Scenario 7 - Orchestrator returns control only at a real terminal interaction boundary

After authorization, the Delivery Orchestrator must continue through every safe deterministic action it can perform. PR creation, queued/running CI, a remediable source/test/metadata/CI failure, merge readiness, packaging, deployment preparation or deployment start are progress events and cannot end the turn. The Orchestrator returns control only as `DONE` when the Outcome is actually complete, `BLOCKED` when a concrete external blocker prevents continuation and its evidence/unblock condition/next action are known, or `HUMAN DECISION REQUIRED` when a genuine protected human choice is needed and the exact options/consequences/reply format are stated. `FAILED` is an event to remediate or classify, never a terminal interaction state.

## Requirements

- FR-001: One current `OUTCOME APPROVED` MUST authorize all deterministic reversible source-lifecycle transitions inside the exact approved paths, including ordinary in-scope bug/test/CI remediation and exact-green-head merge.
- FR-002: A new source approval MUST be required only when the product outcome, approved repository path set or protected/security boundary materially expands or changes, except that a misordered approval sequence requires protocol recovery before any source execution.
- FR-003: A production authorization comment MAY add exact third line `Execution-Intent: EXECUTE`; two-line authorization remains authorize-only and MUST NOT itself trigger runtime mutation.
- FR-004: The runtime execution request parser MUST accept only an exact three-line comment from a production-policy authorized actor on an open canonical Issue, with lowercase full SHA and lowercase SHA-256 fingerprint.
- FR-005: The runtime request workflow MUST independently re-run durable production authorization verification with execution-intent required before routing any contour and MUST contain no SSH/runtime mutation implementation.
- FR-006: The runtime request workflow MUST route VPS and Ubuntu only when the applicable merged Change Contract declares those contours `REQUIRED`; Windows required work MUST fail closed until its separately scoped production automation exists.
- FR-007: Change Contracts MUST declare `CONNECTOR`, `ONE_COMMAND_FALLBACK`, `MISSING`, or `NOT APPLICABLE` for each runtime contour plus an integer `Operator actions expected`.
- FR-008: A required runtime contour MUST NOT be admitted with `MISSING`/`NOT APPLICABLE`; a non-required contour MUST be `NOT APPLICABLE`; expected operator actions MUST equal required one-command fallback contours.
- FR-009: `.github/workflows/deploy-ubuntu-worker.yml` MUST retain `environment: production`, current-main first-parent, exact push/main quality, durable authorization and exact release/artifact provenance gates before runtime transport.
- FR-010: `deploy/worker/ubuntu/deploy-authorized.sh` MUST stage the exact current-main target, require durable authorization plus execution intent, preserve the previous exact source and desired worker state, invoke exact updater activation, verify exact worker/runtime/control identities, write deployment-manifest evidence and roll back the previous exact release if post-activation verification fails.
- FR-011: The Ubuntu exact artifact MUST contain `deploy-authorized.sh`, binding the production-installed launcher to deterministic release provenance.
- FR-012: If a restricted zero-touch Ubuntu transport is not independently provisioned, the protected workflow MUST emit one exact server-pull bootstrap and remain non-successful until runtime mutation actually occurs; it MUST NOT decompose fallback into separate prepare/activate approvals.
- FR-013: Production-equivalent CI MUST execute the real Ubuntu deployment entrypoint in an isolated sandbox with fake Git/systemd/runtime boundaries and cover running-state success, intentional stopped state, authorization failure before mutation and post-activation verification failure/rollback.
- FR-014: Existing exact-SHA provenance, production fingerprint semantics, rollback, Authentik/M2M boundaries, Camera 1/MediaMTX behavior, AI algorithms, credentials and Windows runtime behavior MUST NOT be weakened or changed by this outcome.
- FR-015: Before every request for `OUTCOME APPROVED`, including re-authorization, the Delivery Orchestrator MUST first render an operator-visible Scope block with product outcome, exact repository paths, protected/out-of-scope boundaries, runtime/production impact and acceptance evidence. A bare approval prompt without that visible scope MUST be treated as an invalid authorization request sequence.
- FR-016: Source authorization admission MUST require `VISIBLE_SCOPE_PRESENTED=YES` and `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES` before branch creation or any source/SDD write. The complete Scope MUST be the last substantive assistant block before the approval request and the approval MUST be the immediately following user decision. Missing, incomplete, stale, ambiguous or non-adjacent scope evidence MUST leave admission blocked and require a newly rendered Scope plus a new approval; an earlier misplaced token MUST NOT be reused.
- FR-017: The Delivery Orchestrator MUST return control only as `DONE`, `BLOCKED`, or `HUMAN DECISION REQUIRED`. `BLOCKED` MUST identify a concrete external blocker, evidence, unblock condition and next admissible action; `HUMAN DECISION REQUIRED` MUST identify the exact protected decision, bounded alternatives/consequences where applicable and exact reply/action format; `FAILED` MUST be treated as a remediable/classifiable event rather than a terminal interaction state. Deterministic authorized work MUST continue automatically until one of these states is justified.

## Acceptance criteria

- AC-001: Governance and Delivery Orchestrator contracts state a normal two-intent interaction budget: one source approval and one exact-release production authorization+execution-intent decision, with zero intermediate deterministic confirmations.
- AC-002: Source continuation explicitly allows ordinary in-scope defect/test/CI remediation without another `OUTCOME APPROVED`.
- AC-003: `parse_runtime_execution_request.py` accepts only the exact three-line authorize-and-execute form and rejects authorize-only, malformed, unauthorized, PR, closed-Issue and non-created events.
- AC-004: `verify_production_authorization.py` preserves historical two-line authorization, detects exact third-line execution intent, can require it, and emits exact runtime-contour outputs for routing.
- AC-005: `deploy-runtime-request.yml` contains no SSH/runtime mutation and routes exact required VPS/Ubuntu contours only after parser plus independent production verification.
- AC-006: Change Contract validation rejects required contours with missing execution capability and rejects operator-action counts inconsistent with one-command fallback declarations.
- AC-007: `deploy-ubuntu-worker.yml` preserves exact-main, exact push/main quality, durable authorization, release provenance and protected environment gates before transport.
- AC-008: Ubuntu workflow exposes `CONNECTOR` execution only through separately provisioned restricted transport; otherwise it produces one exact fallback bootstrap and does not claim deployment success.
- AC-009: `deploy-authorized.sh` performs exact target deployment and writes a valid runtime-verified Ubuntu deployment manifest on sandbox success.
- AC-010: The real launcher sandbox proves intentional stopped state remains stopped and authorization failure performs no mutation.
- AC-011: The real launcher sandbox proves post-activation verification failure restores the previous exact source and removes the candidate control topology through rollback.
- AC-012: Deterministic `ubuntu-worker` exact artifact bytes include `deploy/worker/ubuntu/deploy-authorized.sh`.
- AC-013: PR Validation and aggregate Quality integration succeed on the exact final head; merge uses a fresh main/head/scope/review check and expected-head protection.
- AC-014: This source task changes no API/frontend/media/AI algorithm/credential/sudoers/runtime secret behavior and performs no production mutation before a fresh exact-SHA production envelope for the merge commit.
- AC-015: `AGENTS.md`, canonical governance, task runtime and Delivery Orchestrator contract all require the visible Scope-before-approval order, define the minimum scope fields, prohibit a standalone `OUTCOME APPROVED` prompt, and require revised scope presentation before re-authorization.
- AC-016: The same four contracts define fail-closed admission: `VISIBLE_SCOPE_PRESENTED=YES` plus `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES` are required before source writes; a bare/misordered/non-adjacent approval remains in `DISCUSSION`, cannot create a branch/write source, and can recover only through a newly displayed Scope followed by a new approval.
- AC-017: `AGENTS.md`, governance, delivery policy, task runtime, release readiness and Delivery Orchestrator contract all define the same three terminal interaction states and prohibit intermediate status-only stops; `tests/test_delivery_terminal_states.py` regression-protects state names, blocker/human-decision semantics, automatic remediation and automatic resume.

## NFR assessment

- NFR-001 | Area: Operator UX | Target: Normal source lifecycle consumes one source authorization; normal production release consumes one combined authorization/execution-intent decision; intermediate deterministic confirmations are zero | Validation: governance contracts, Change Contract fields, runtime request workflow | Evidence: `AGENTS.md`, `contracts/**`, `.github/pull_request_template.md`, `.github/workflows/deploy-runtime-request.yml` | Status: PASS
- NFR-002 | Area: Security | Target: No runtime request reaches mutation without exact current durable authorization and explicit execution intent; request router itself has no SSH/runtime authority | Validation: parser tests and workflow architecture policy | Evidence: `tests/test_runtime_execution_request.py`, `scripts/quality/validate_workflow_policy.py` | Status: PASS
- NFR-003 | Area: Reliability | Target: Real Ubuntu deployment transaction is executed in four deterministic sandbox scenarios including rollback | Validation: production-equivalent transaction test | Evidence: `tests/test_ubuntu_worker_deploy_authorized.py` | Status: PASS
- NFR-004 | Area: Provenance | Target: Ubuntu deployment launcher is included in deterministic exact artifact and exact-main/release admission precedes transport | Validation: exact-artifact and workflow architecture tests | Evidence: `scripts/quality/build_exact_artifacts.py`, `tests/quality/test_quality_architecture.py` | Status: PASS
- NFR-005 | Area: Safety | Target: Required runtime contour cannot be admitted with missing execution capability; manual action count is machine-consistent | Validation: Change Contract unit tests | Evidence: `scripts/ci/validate_change_contract.py`, `tests/test_change_contract.py` | Status: PASS
- NFR-006 | Area: Compatibility | Target: Legacy `DEPLOY VPS <sha>` and two-line production authorization remain readable/usable under their existing semantics | Validation: unchanged legacy request workflow plus authorization verifier behavior | Evidence: `.github/workflows/deploy-vps-request.yml`, `scripts/release/verify_production_authorization.py` | Status: PASS
- NFR-007 | Area: Operator comprehension | Target: Every source-authorization request is preceded by an explicit exact scope presentation, including re-authorization | Validation: governance/agent/task-runtime/PM contract review and exact diff | Evidence: `AGENTS.md`, `contracts/SEA_SPEED_GOVERNANCE.md`, `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`, `contracts/branches/project-manager.md` | Status: PASS
- NFR-008 | Area: Process reliability | Target: A missing/incomplete/stale/non-adjacent Scope can never be converted into source execution merely because the operator typed `OUTCOME APPROVED`; admission must remain blocked until the exact presentation sequence is repaired | Validation: contract state-machine review and feature 017 regression scenario | Evidence: `AGENTS.md`, `contracts/SEA_SPEED_GOVERNANCE.md`, `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`, `contracts/branches/project-manager.md`, `specs/017-delivery-automation/{spec,plan,tasks}.md` | Status: PASS
- NFR-009 | Area: Orchestration reliability | Target: Every Delivery Orchestrator turn with active work continues deterministic authorized actions until exactly `DONE`, `BLOCKED`, or `HUMAN DECISION REQUIRED`; no status-only terminal handoff or terminal `FAILED` is permitted | Validation: six-contract consistency plus regression test | Evidence: `tests/test_delivery_terminal_states.py`, `AGENTS.md`, `contracts/SEA_SPEED_GOVERNANCE.md`, `contracts/SEA_SPEED_DELIVERY_POLICY.md`, `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`, `contracts/runtime/RELEASE_READINESS_GATE.md`, `contracts/branches/project-manager.md` | Status: PASS

## Runtime feedback

- Runtime acceptance for the original automation source task was REQUIRED because that exact diff added an Ubuntu production entrypoint under `deploy/worker/ubuntu/**`; that runtime deployment and acceptance were completed for Issue #178.
- Production mutation during the fail-closed scope-admission remediation and Issue #195 terminal-interaction governance continuation: NONE; both are CONTROL_PLANE only.
- Issue #195 records the accepted three-state terminal interaction contract: `DONE`, `BLOCKED`, `HUMAN DECISION REQUIRED`; `FAILED` is now an internal event, not a terminal handoff.
- Zero-touch Ubuntu transport is deliberately not claimed by source alone. Until a restricted deploy credential/route/privilege boundary is independently provisioned, the guaranteed capability remains one-command fallback.