# Implementation Plan: Two-intent delivery automation

- Specification: specs/017-delivery-automation/spec.md
- Issue: #178
- Status: In implementation

## Architecture

The change introduces one policy layer and three execution layers while retaining the existing exact-SHA provenance model.

1. **Interaction policy**: governance, task-runtime, release-readiness and Delivery Orchestrator contracts define the two-intent budget, require a visible exact Scope block before every source-authorization request, make the presentation order a fail-closed source-admission gate, and make ordinary in-scope remediation a continuation of the original validly admitted `OUTCOME APPROVED` rather than a new approval event.
2. **Executable Change Contract**: every runtime-impacting PR declares per-contour execution capability and expected operator-action count. CI rejects required contours whose execution path is missing and rejects inconsistent manual-action budgets.
3. **Connector-addressable runtime request**: `deploy-runtime-request.yml` accepts only the exact three-line production authorization carrying `Execution-Intent: EXECUTE`, validates the comment through repository code, independently re-verifies durable production authorization and routes only the required contours.
4. **Ubuntu protected execution**: `deploy-ubuntu-worker.yml` owns hosted admission/provenance and selects either a separately provisioned restricted transport or one-command fallback. `deploy-authorized.sh` owns the target-side exact-source activation, verification, deployment evidence and rollback transaction.
5. **Production-equivalent CI**: the real Ubuntu transaction entrypoint executes in an isolated sandbox with fake Git/systemd/runtime boundaries so deterministic ordering, desired-state and rollback defects fail before production.

The runtime request is not itself a new authority model. Durable production authorization retains the existing fingerprint payload. `Execution-Intent: EXECUTE` is an additional exact line proving that the already authorized release should now execute. A two-line authorization remains authorize-only.

The source admission rule is also not a new user decision. It is a protocol invariant around the existing single `OUTCOME APPROVED`: the exact six-field Scope must be the last substantive assistant block before the request, the approval must be the next user decision, and no branch/source write is legal unless `VISIBLE_SCOPE_PRESENTED=YES` and `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`. Failure returns to `DISCUSSION` and requires re-presenting Scope plus a new token; the misplaced token is never retroactively reused.

## Decisions

### D-001 - Combine authority and execution intent in one operator decision

- Decision: Allow exact three-line canonical Issue evidence containing production approval, fingerprint and `Execution-Intent: EXECUTE`.
- Reason: Authorization and execution remain distinct semantics while avoiding a second user interaction solely to say “run it”.
- Rejected: infer execution from any production approval; keep mandatory `DEPLOY VPS`/`EXECUTE PREPARE` follow-up comments for every release.

### D-002 - Keep durable fingerprint semantics unchanged

- Decision: Do not add execution intent to the authorization fingerprint payload.
- Reason: The fingerprint binds the safety envelope; execution intent controls whether to act now. Existing two-line approvals remain valid audit/runtime authority evidence.
- Rejected: invalidate historical approvals or redefine the safety envelope hash for an orchestration UX change.

### D-003 - Make runtime execution capability machine-readable

- Decision: Add `CONNECTOR`, `ONE_COMMAND_FALLBACK`, `MISSING`, `NOT APPLICABLE` per contour plus exact `Operator actions expected`.
- Reason: A PR cannot claim a releasable runtime path while a mandatory contour is discovered to be operationally unreachable only after merge/authorization.
- Rejected: prose-only capability preflight retained in chat/PM memory.

### D-004 - Route, do not duplicate, protected runtime implementations

- Decision: `deploy-runtime-request.yml` parses/verifies/routes only. VPS continues through reusable `deploy-vps.yml`; Ubuntu uses reusable `deploy-ubuntu-worker.yml`.
- Reason: The request surface must not acquire SSH/runtime mutation authority and protected contour implementations remain single-source.
- Rejected: direct SSH from Issue-comment workflow or duplicate VPS deployment logic.

### D-005 - One Ubuntu target transaction owns prepare plus activate

- Decision: Add `deploy-authorized.sh` as exact-artifact-bound target entrypoint wrapping the existing exact updater/rollback primitives.
- Reason: Preparation, activation and post-verification are deterministic transaction stages and should not become serial user approvals.
- Rejected: continue the manual prepare → inspect → activate sequence as normal operation.

### D-006 - Zero-touch transport is capability, not an assumption

- Decision: Ubuntu workflow uses zero-touch only when a separately provisioned restricted deployment credential/route/remote protocol is actually present. Otherwise it emits one exact server-pull fallback and fails non-successfully until runtime mutation occurs.
- Reason: Source code cannot claim sudo/SSH privilege that has not been provisioned, and must not weaken host security to manufacture automation.
- Rejected: password automation, arbitrary root SSH, public self-hosted runner, silent sudoers mutation.

### D-007 - Execute the real Ubuntu transaction in CI

- Decision: Add guarded sandbox roots/test mode to `deploy-authorized.sh` and execute that real file with fake external commands.
- Reason: Previous production defects were executable shell contract/order/exit defects that source-string assertions missed.
- Rejected: test a Python model or only grep for expected shell lines.

### D-008 - Scope presentation is a mandatory pre-authorization gate

- Decision: The Orchestrator must render a visible `Scope` block before every request for `OUTCOME APPROVED`, with six minimum fields: product outcome, exact repository paths, protected/out-of-scope boundaries, runtime contour, production impact, and acceptance evidence. Re-authorization uses the revised block first.
- Reason: A single source approval is only low-friction when the operator can see exactly what it authorizes. Scope cannot remain implicit in internal reasoning or scattered earlier discussion.
- Rejected: bare approval prompts, scope shown only after approval, or requiring the operator to reconstruct the path set from chat history.

### D-009 - Scope/approval ordering is fail-closed state, not advisory prose

- Decision: Source execution requires `VISIBLE_SCOPE_PRESENTED=YES` and `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`; the Scope is the last substantive assistant block before the request and `OUTCOME APPROVED` is the next user decision. Any missing, incomplete, stale, ambiguous or non-adjacent presentation leaves admission blocked.
- Reason: A prose-only instruction allowed the Orchestrator to request/accept approval while the visible scope was absent from the immediately preceding turn. Treating ordering as explicit state prevents that failure from becoming a source write.
- Recovery: return to `DISCUSSION`, render the complete current Scope, request approval, and accept only the newly supplied immediately-following token.
- Rejected: retroactively accepting the earlier token after showing Scope; relying on “scope was mentioned somewhere above”; allowing branch creation before the presentation gate is proven.

## Affected contours

- Repository/control plane: governance and feature 017 SDD only for this remediation.
- VPS application runtime: unchanged.
- Ubuntu Worker/relay: runtime/source unchanged by this remediation; previously delivered automation remains unchanged.
- Windows AI Worker: unchanged.
- Public application/API/media behavior: unchanged.
- Credentials/privilege: no credential material, sudoers, root SSH policy, GitHub environment secret or runner provisioning is changed.
- Change Contract production class: CONTROL_PLANE; VPS/Ubuntu/Windows runtime deployment: NOT REQUIRED.

## Validation

- Static: repository/SDD validation and exact content review of the four active orchestration contracts.
- Contract UX: `AGENTS.md`, canonical governance, task runtime and Delivery Orchestrator contract all require Scope-before-approval ordering, immediate adjacency, two explicit admission state flags, and no source write while admission is blocked.
- Regression: feature 017 records bare approval, approval-before-scope, incomplete/stale Scope and non-adjacent Scope as invalid source-admission sequences; recovery requires a newly rendered Scope and new token.
- Scope: exact seven-path diff only; no application/runtime/deployment source changes.
- PR: exact in-scope diff, PR Validation and aggregate Quality integration on one exact final head; fresh main/head/scope/review gate before expected-head merge.
- Runtime: NOT REQUIRED for this control-plane-only remediation.

## Risk profile

- Risk profile: NOT REQUIRED

The current seven-path remediation is CONTROL_PLANE-only with security impact `NONE`, no API/event/state/storage schema impact, no destructive/data migration, no MIXED runtime impact and no other high-risk trigger. The broader feature 017 historical risk records are retained separately below as audit context and are not active risk rows for this Change Contract.

## Historical feature risk record

These records document the broader delivery/runtime automation work already delivered under feature 017. They are retained for audit continuity but are outside the current Change Contract's active `Risk profile` section.

- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: strict three-line parser, authorized actor/open Issue guard, independent durable authorization verification, request router contains no SSH/runtime mutation | Validation: parser and workflow architecture tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: Change Contract requires executable capability for every required contour and exact fallback action count | Validation: Change Contract unit tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: real Ubuntu deployment entrypoint runs in sandbox success/failure/rollback scenarios before production | Validation: `tests/test_ubuntu_worker_deploy_authorized.py` | Residual risk: MEDIUM because hosted CI cannot emulate physical GPU/network/systemd completely | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: zero-touch path requires separately provisioned restricted transport; source does not create credentials/sudoers/public runner; absent capability becomes one-command fallback | Validation: workflow policy plus explicit fallback path | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: target launcher captures previous exact source, updater owns pre-commit restoration, launcher invokes exact rollback on post-activation verification failure | Validation: real transaction rollback test | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-006 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: launcher is included in deterministic Ubuntu exact artifact and both workflow/target prove current-main exact SHA before mutation | Validation: exact-artifact architecture test and transaction staging guard | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-007 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: mandatory visible six-field Scope block before source authorization and before any material re-authorization | Validation: exact contract/SDD diff plus PR validation | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-008 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: make Scope adjacency explicit state, block branch/source writes on any unknown/NO value, require fresh Scope plus fresh approval to recover | Validation: four-contract content review, SDD regression trace and exact PR validation | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: integration | Priority: P0 | Evidence: governance/runtime/PM contract assertions through repository quality validation
- TEST-002 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: `tests/test_runtime_execution_request.py`
- TEST-003 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: `tests/test_production_authorization.py` plus verifier compile/behavior checks
- TEST-004 | Covers: AC-005,AC-007,AC-008 | Level: integration | Priority: P0 | Evidence: `tests/quality/test_quality_architecture.py` and `scripts/quality/validate_workflow_policy.py`
- TEST-005 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: `tests/test_change_contract.py`
- TEST-006 | Covers: AC-009,AC-010,AC-011 | Level: integration | Priority: P0 | Evidence: `tests/test_ubuntu_worker_deploy_authorized.py`
- TEST-007 | Covers: AC-012 | Level: integration | Priority: P0 | Evidence: deterministic exact-artifact test in `tests/quality/test_quality_architecture.py`
- TEST-008 | Covers: AC-013 | Level: integration | Priority: P0 | Evidence: exact-head PR Validation, Quality integration, fresh merge gate and expected-head merge
- TEST-009 | Covers: AC-014 | Level: integration | Priority: P1 | Evidence: exact approved diff plus Change Contract exclusions and post-merge runtime authorization boundary
- TEST-010 | Covers: AC-015 | Level: integration | Priority: P0 | Evidence: exact content review of `AGENTS.md`, `contracts/SEA_SPEED_GOVERNANCE.md`, `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`, `contracts/branches/project-manager.md` plus SDD validation
- TEST-011 | Covers: AC-016 | Level: integration | Priority: P0 | Evidence: exact content review proves the two admission flags, `DISCUSSION` fallback, source-write prohibition and fresh-token recovery are present in all four contracts; PR Validation and Quality integration validate the seven-path SDD change

## Correct-course check

- Trigger: ARCHITECTURE_PIVOT
- Issue impact: Issue #178 remains the product/runtime parent. Operator feedback exposed that the existing Scope-before-approval prose could still be executed incorrectly, so the same delivery-automation outcome now makes presentation ordering a fail-closed state gate.
- Specification impact: adds the invalid-sequence scenario, FR-016, AC-016 and NFR-008 without changing the two-intent model or runtime automation semantics.
- Plan impact: adds D-009 and explicit admission/recovery state; runtime/deployment architecture is unchanged.
- Tasks impact: adds bounded seven-path remediation for fail-closed Scope admission.
- Authorization impact: a complete seven-path Scope block was displayed immediately before the operator supplied `OUTCOME APPROVED`; admission is valid for this remediation.
- Follow-up: merge only an exact-green seven-path head; future source tasks must prove the two Scope-admission flags before any branch/source write.

## Deployment transaction audit

The following audit remains historical evidence for the broader feature 017 Ubuntu deployment automation. This current seven-path remediation is CONTROL_PLANE-only and introduces no production transaction.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: repository and runtime unchanged | Retry: correct exact comment/main-history/quality/authorization/capability evidence then re-enter protected workflow | Rollback: NOT REQUIRED because runtime mutation has not started | Evidence: strict request parser, first-parent check, push/main quality, durable authorization and release-manifest logs
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: exact release/evidence may exist only on runner or root-owned staging; active worker unchanged | Retry: correct missing transport/prerequisite or use the single declared fallback action | Rollback: NOT REQUIRED because target activation has not started | Evidence: exact artifact digest, release manifest, target baseline source/desired state and transport capability result
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: exact updater may have staged candidate units but active marker is not committed until updater verification; updater performs previous-unit restoration on activation failure | Retry: only after actual source/control/desired state is recovered and exact authorization remains current | Rollback: updater restores previous exact worker/control topology before returning failure | Evidence: updater logs plus real transaction test boundary
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate may be active but is not accepted by enclosing deployment transaction | Retry: resolve verification cause after read-only state recovery | Rollback: launcher invokes exact `rollback-exact.sh` to captured previous source when candidate active marker is present | Evidence: exact active marker, runtime-id, worker ExecStart, control unit/ExecStart/service and desired-state checks
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: runtime may be healthy but deployment acceptance is incomplete until deployment manifest is persisted | Retry: recover exact runtime state and write/validate evidence only when runtime identity is still proven | Rollback: use captured previous exact release if state cannot be proven; never invent completion from missing evidence | Evidence: root-owned `deployment-manifest-ubuntu-worker.json` with runtimeVerified/state fields
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime state remains valid while temporary staging may remain | Retry: remove root-owned staging independently without re-running activation | Rollback: NOT REQUIRED solely for temporary staging cleanup failure | Evidence: status-preserving EXIT cleanup and root-owned updater directory
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: runtime may be verified but product acceptance remains incomplete until manifest/artifact evidence is collected | Retry: recollect/validate evidence without unnecessary runtime mutation when exact runtime identity is unchanged | Rollback: decide from runtime/product evidence, not upload transport alone | Evidence: validated deployment manifest, release/quality/exact-artifact bundle and Issue runtime record
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if exact rollback fails runtime state is unknown and all further automation stops | Retry: read actual source/runtime/control/desired state before any new mutation and require a fresh authorized recovery if semantics changed | Rollback: no secondary guessed rollback; escalate with exact recovered state | Evidence: rollback script result, restored active marker/control topology and sandbox rollback scenario

## Runtime feedback

- Actual production transport after source merge: one-command fallback was used successfully for Issue #178 runtime target `8dc74762a344dbf763d3ce1e7ecb1bac6872affb`.
- Restricted zero-touch Ubuntu transport remains separately unprovisioned; the repository still truthfully advertises one-command fallback when needed.
- The current fail-closed scope-admission remediation is governance/control-plane only and performs no production mutation.
- Product runtime acceptance for Issue #178 has already confirmed worker Stop/Start independence from Camera 1 HLS; later UI polish remains separately scoped source work.
