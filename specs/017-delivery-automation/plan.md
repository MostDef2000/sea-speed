# Implementation Plan: Two-intent delivery automation

- Specification: specs/017-delivery-automation/spec.md
- Issue: #178
- Status: In implementation

## Architecture

The change introduces one policy layer and three execution layers while retaining the existing exact-SHA provenance model.

1. **Interaction policy**: governance, task-runtime, release-readiness and Delivery Orchestrator contracts define the two-intent budget and make ordinary in-scope remediation a continuation of the original `OUTCOME APPROVED` rather than a new approval event.
2. **Executable Change Contract**: every runtime-impacting PR declares per-contour execution capability and expected operator-action count. CI rejects required contours whose execution path is missing and rejects inconsistent manual-action budgets.
3. **Connector-addressable runtime request**: `deploy-runtime-request.yml` accepts only the exact three-line production authorization carrying `Execution-Intent: EXECUTE`, validates the comment through repository code, independently re-verifies durable production authorization and routes only the required contours.
4. **Ubuntu protected execution**: `deploy-ubuntu-worker.yml` owns hosted admission/provenance and selects either a separately provisioned restricted transport or one-command fallback. `deploy-authorized.sh` owns the target-side exact-source activation, verification, deployment evidence and rollback transaction.
5. **Production-equivalent CI**: the real Ubuntu transaction entrypoint executes in an isolated sandbox with fake Git/systemd/runtime boundaries so deterministic ordering, desired-state and rollback defects fail before production.

The runtime request is not itself a new authority model. Durable production authorization retains the existing fingerprint payload. `Execution-Intent: EXECUTE` is an additional exact line proving that the already authorized release should now execute. A two-line authorization remains authorize-only.

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

## Affected contours

- Repository/control plane: governance, Change Contract, runtime request parser/workflows, quality architecture and feature 017 SDD.
- VPS application runtime: unchanged. Existing reusable VPS deployment implementation is only routed by the new request workflow.
- Ubuntu Worker/relay: source impact `REQUIRED` because `deploy/worker/ubuntu/deploy-authorized.sh` becomes part of the exact Ubuntu release artifact and production execution surface.
- Windows AI Worker: runtime/source unchanged. Runtime router fails closed for a required Windows contour because Windows production automation is outside this task.
- Public application/API/media behavior: unchanged.
- Credentials/privilege: no credential material, sudoers, root SSH policy, GitHub environment secret or runner provisioning is changed.

## Validation

- Static: Python compile, shell syntax, repository/SDD validation, workflow policy, Change Contract tests.
- Unit/integration: strict execution-request parser, production-authorization execution-intent behavior, execution-capability admission.
- Transaction: execute real `deploy-authorized.sh` in isolated sandbox for success, desired stopped, authorization failure before mutation and post-activation verification failure with rollback.
- Provenance: build deterministic exact artifacts twice and require `deploy-authorized.sh` inside `ubuntu-worker` release files.
- Workflow architecture: request workflow has no SSH/environment production; Ubuntu workflow performs quality/auth/provenance before transport and has explicit one-command fallback.
- PR: exact 23-path diff, PR Validation and aggregate Quality integration on one exact final head; fresh main/head/scope/review gate before expected-head merge.
- Runtime after merge: fresh exact-SHA production approval plus execution intent; Ubuntu release deployment and parent #178 Stop/Start + continuous Camera 1 HLS acceptance remain separate runtime evidence.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: strict three-line parser, authorized actor/open Issue guard, independent durable authorization verification, request router contains no SSH/runtime mutation | Validation: parser and workflow architecture tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: Change Contract requires executable capability for every required contour and exact fallback action count | Validation: Change Contract unit tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: real Ubuntu deployment entrypoint runs in sandbox success/failure/rollback scenarios before production | Validation: `tests/test_ubuntu_worker_deploy_authorized.py` | Residual risk: MEDIUM because hosted CI cannot emulate physical GPU/network/systemd completely | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: zero-touch path requires separately provisioned restricted transport; source does not create credentials/sudoers/public runner; absent capability becomes one-command fallback | Validation: workflow policy plus explicit fallback path | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: target launcher captures previous exact source, updater owns pre-commit restoration, launcher invokes exact rollback on post-activation verification failure | Validation: real transaction rollback test | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-006 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: launcher is included in deterministic Ubuntu exact artifact and both workflow/target prove current-main exact SHA before mutation | Validation: exact-artifact architecture test and transaction staging guard | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: integration | Priority: P0 | Evidence: governance/runtime/PM contract assertions through repository quality validation
- TEST-002 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: `tests/test_runtime_execution_request.py`
- TEST-003 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: `tests/test_production_authorization.py` plus verifier compile/behavior checks
- TEST-004 | Covers: AC-005,AC-007,AC-008 | Level: integration | Priority: P0 | Evidence: `tests/quality/test_quality_architecture.py` and `scripts/quality/validate_workflow_policy.py`
- TEST-005 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: `tests/test_change_contract.py`
- TEST-006 | Covers: AC-009,AC-010,AC-011 | Level: integration | Priority: P0 | Evidence: `tests/test_ubuntu_worker_deploy_authorized.py`
- TEST-007 | Covers: AC-012 | Level: integration | Priority: P0 | Evidence: deterministic exact-artifact test in `tests/quality/test_quality_architecture.py`
- TEST-008 | Covers: AC-013 | Level: integration | Priority: P0 | Evidence: exact-head PR Validation, Quality integration, fresh merge gate and expected-head merge
- TEST-009 | Covers: AC-014 | Level: integration | Priority: P1 | Evidence: exact 23-path diff plus Change Contract exclusions and post-merge runtime authorization boundary

## Correct-course check

- Trigger: ARCHITECTURE_PIVOT
- Issue impact: Issue #178 remains the product/runtime parent, while this correct-course adds a bounded delivery-automation sub-outcome prompted by operator feedback about excessive orchestration interactions.
- Specification impact: Feature 017 defines two-intent delivery, machine runtime capability and one-transaction Ubuntu deployment without changing the worker-control product semantics.
- Plan impact: Runtime orchestration changes from serial manual stage confirmations to a router plus protected contour workflows and target transaction.
- Tasks impact: Adds governance, Change Contract, request/parser, Ubuntu workflow/launcher, real transaction tests and exact-artifact binding inside the approved 23 paths.
- Authorization impact: Existing `OUTCOME APPROVED` covers this exact 23-path process-hardening outcome; production remains unauthorized until the merged exact SHA receives a fresh production envelope.
- Follow-up: Merge only an exact-green head, verify push/main release evidence, then request one fresh exact-release production authorization with `Execution-Intent: EXECUTE`; resume #178 runtime acceptance through the new path.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: repository and runtime unchanged | Retry: correct exact comment/main-history/quality/authorization/capability evidence then re-enter protected workflow | Rollback: NOT REQUIRED because runtime mutation has not started | Evidence: strict request parser, first-parent check, push/main quality, durable authorization and release-manifest logs
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: exact release/evidence may exist only on runner or root-owned staging; active worker unchanged | Retry: correct missing transport/prerequisite or use the single declared fallback action | Rollback: NOT REQUIRED because target activation has not started | Evidence: exact artifact digest, release manifest, target baseline source/desired state and transport capability result
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: exact updater may have staged candidate units but active marker is not committed until updater verification; updater performs previous-unit restoration on activation failure | Retry: only after actual source/control/desired state is recovered and exact authorization remains current | Rollback: updater restores previous exact worker/control topology before returning failure | Evidence: updater logs plus real transaction test boundary
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate may be active but is not accepted by enclosing deployment transaction | Retry: resolve verification cause after read-only state recovery | Rollback: launcher invokes exact `rollback-exact.sh` to captured previous source when candidate active marker is present | Evidence: exact active marker, runtime-id, worker ExecStart, control unit/ExecStart/service and desired-state checks
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: runtime may be healthy but deployment acceptance is incomplete until deployment manifest is persisted | Retry: recover exact runtime state and write/validate evidence only when runtime identity is still proven | Rollback: use captured previous exact release if state cannot be proven; never invent completion from missing evidence | Evidence: root-owned `deployment-manifest-ubuntu-worker.json` with runtimeVerified/state fields
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime state remains valid while temporary staging may remain | Retry: remove root-owned staging independently without re-running activation | Rollback: NOT REQUIRED solely for temporary staging cleanup failure | Evidence: status-preserving EXIT cleanup and root-owned updater directory
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: runtime may be verified but product acceptance remains incomplete until manifest/artifact evidence is collected | Retry: recollect/validate evidence without unnecessary runtime mutation when exact runtime identity is unchanged | Rollback: decide from runtime/product evidence, not upload transport alone | Evidence: validated deployment manifest, release/quality/exact-artifact bundle and Issue runtime record
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if exact rollback fails runtime state is unknown and all further automation stops | Retry: read actual source/runtime/control/desired state before any new mutation and require a fresh authorized recovery if semantics changed | Rollback: no secondary guessed rollback; escalate with exact recovered state | Evidence: rollback script result, restored active marker/control topology and sandbox rollback scenario

## Runtime feedback

- Actual production transport after source merge: PENDING independent capability verification; source does not claim restricted Ubuntu credentials exist.
- Expected fallback until bootstrap provisioning: `ONE_COMMAND_FALLBACK`, one operator action for the Ubuntu contour.
- Current Ubuntu parent runtime remains accepted legacy baseline until fresh exact-SHA production authorization for the hardening merge.
- Product runtime acceptance for Issue #178 still requires worker Stop/Start through the operator control path while Camera 1 HLS remains continuously available.
