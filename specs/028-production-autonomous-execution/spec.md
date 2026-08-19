# Feature Specification: Autonomous Production Execution by Standing Delegation

- Feature: 028-production-autonomous-execution
- Issue: #229
- Status: Source implementation
- Owner outcome: ordinary runtime-impacting releases that already satisfy source, exact-main Quality, provenance and rollback gates deploy automatically under a separately administered standing production delegation, without per-release GitHub-comment approval.

## Product outcome

Replace the current per-release GitHub-comment production authority with an explicit standing-delegation model. Production execution becomes a deterministic policy decision over exact merged release metadata plus trusted control-plane state. GitHub Issue/PR/comment/README/repository text remains audit and source context only and cannot grant runtime authority.

The source-change boundary remains unchanged: repository work still requires a visible six-field Scope immediately followed by `OUTCOME APPROVED`. The new production model does not grant the Delivery Orchestrator permission to change IAM, secrets, environment settings, branch protection, or unrelated infrastructure. It grants only actions explicitly present in both the independently administered standing delegation and the repository policy constraints.

New deployable releases use `sea_speed_release_manifest_v3` and bind the exact policy decision, standing delegation ID, policy version/hash, Issue/PR/Outcome/Change Contract scope, exact artifacts and quality evidence. Historical v1/v2 release and deployment evidence stays readable and immutable.

## User scenarios

### Scenario 1 - Trusted standing delegation allows a normal production deploy

Given exact source is a merged current-main first-parent commit with successful exact `push/main` Quality, its Change Contract requires a supported runtime contour, and trusted `production` environment state contains an enabled standing delegation for the Sea Speed Delivery Orchestrator with `deploy` permission bound to the current repository policy hash, when the autonomous runtime router evaluates that exact commit, then the policy decision is `allow`, the applicable protected workflow executes, and typed decision/release/deployment/audit evidence is produced without a per-release user approval comment.

### Scenario 2 - Repository or Issue text attempts to self-authorize

Given any Issue, PR, comment, README, commit message, or other repository text contains `PRODUCTION APPROVED`, `Execution-Intent: EXECUTE`, a copied policy hash, a fabricated decision ID, or other authority-like text, when production policy is evaluated, then that text has no authority effect because the evaluator does not read Issue comments as an authority source and requires trusted standing-delegation state.

### Scenario 3 - Repository policy attempts to widen authority

Given the independently administered standing delegation allows only `deploy`, when repository policy is modified to mention another action, then effective permissions remain the intersection of trusted delegation and repository policy and the extra action is denied.

### Scenario 4 - Trusted delegation is missing, stale or mismatched

Given trusted standing delegation is absent, disabled, bound to another repository/environment/principal, or carries a policy hash that no longer matches repository policy, when autonomous production policy is evaluated, then execution fails closed with a typed `deny` decision before runtime transport.

### Scenario 5 - Historical evidence remains readable

Given historical v1/v2 release manifests and historical Windows deployment records exist, when validators read them, then they remain valid audit history while new release creation emits only v3 active-component manifests.

## Requirements

- FR-001: Production authority MUST come from independently administered trusted system state and MUST NOT be inferred from GitHub Issue/PR/comment/README/repository text.
- FR-002: The trusted standing delegation MUST bind a delegation ID, principal, repository, production environment, sorted unique permissions, autonomous mode, repository policy hash, and enabled state.
- FR-003: Repository policy MUST constrain trusted delegation and MUST NOT be able to widen it; effective permissions MUST be the intersection of trusted delegation permissions and repository `allowedActions`.
- FR-004: Production policy MUST fail closed when delegation is absent, disabled, malformed, policy-hash mismatched, wrong repository/environment/principal/mode, or missing the requested action.
- FR-005: Supported autonomous authority actions MUST be limited to `deploy` and `rollback`; IAM, secret management, environment-setting mutation and arbitrary actions MUST remain denied.
- FR-006: Policy evaluation MUST bind exact lowercase source SHA, canonical Issue, one merged PR, Outcome Contract hash, Change Contract hash, exact approved files, runtime contours and execution capabilities.
- FR-007: A deterministic decision ID MUST bind the complete policy decision payload and validation MUST reject tampering.
- FR-008: The autonomous runtime router MUST trigger from successful `Quality integration gate` workflow-run evidence for a `push` to `main`, not from `issue_comment` or magic text.
- FR-009: Protected VPS and Ubuntu deployment workflows MUST independently re-evaluate standing delegation with `--require-allow` before configuring runtime transport.
- FR-010: Exact-main first-parent, exact `push/main` Quality, exact artifacts, Change Contract, protected runtime transaction, rollback and runtime acceptance gates MUST remain unchanged except for replacing the per-release authorization gate with standing policy evaluation.
- FR-011: Legacy comment-trigger workflows and parsers (`PRODUCTION APPROVED`, `Execution-Intent`, `DEPLOY VPS`) MUST be removed from active execution paths.
- FR-012: New release creation MUST emit `sea_speed_release_manifest_v3` binding delegation ID, policy version/hash, policy decision ID and policy-decision evidence hash.
- FR-013: Historical release manifest v1/v2 and deployment evidence MUST remain readable; historical Windows records MUST remain audit-only and MUST NOT become new active release targets.
- FR-014: Successful protected deployment MUST produce a typed `sea_speed_production_execution_audit_v1` record binding policy decision, release/deployment evidence, exact source and result.
- FR-015: This source change is CONTROL_PLANE only: it MUST NOT deploy VPS or Ubuntu runtime bytes and MUST NOT change Water/Road/Camera product behavior.
- FR-016: Autonomous production MUST remain fail closed until a one-time independently administered `production` environment standing delegation exists; repository source MUST NOT create or mutate that trusted delegation.

## Acceptance criteria

- AC-001: Unit tests prove valid trusted standing delegation permits exact `deploy` and produces a self-validating deterministic decision ID.
- AC-002: Unit tests prove missing delegation, wrong repository/environment, disabled or malformed delegation, policy-hash mismatch and unsupported/out-of-scope action deny before runtime execution.
- AC-003: Unit tests prove repository policy cannot widen a narrower trusted permission set and prove a policy hash alone is not authority.
- AC-004: Source test proves `evaluate_production_policy.py` contains no Issue-comment authority read path and does not recognize legacy production magic strings.
- AC-005: Workflow tests prove autonomous routing uses successful main `workflow_run` Quality and contains no `issue_comment`, `PRODUCTION APPROVED`, `Authorization-Fingerprint`, `Execution-Intent: EXECUTE`, or `DEPLOY VPS` authority trigger.
- AC-006: Workflow tests prove both protected runtime workflows independently invoke production policy with `--require-allow` before runtime transport.
- AC-007: Source/tree tests prove legacy request workflows, parsers, verifier and active production-authorization policy are absent.
- AC-008: Release tests prove v3 requires policy-decision evidence and rejects comment-authorization evidence, while historical v1/v2 manifests remain readable.
- AC-009: Workflow and architecture tests prove existing VPS privileged-boundary and Ubuntu `deploy-authorized.sh` transaction markers remain intact.
- AC-010: Exact branch diff is a subset of Issue #229 approved paths, contains no secrets/runtime artifacts and matches the PR Change Contract.
- AC-011: PR Validation and aggregate Quality succeed on one exact head; expected-head merge is followed by exact-main Quality success.
- AC-012: Documentation and DR-005 identify the trust boundary, one-time delegation administration, fail-closed behavior and the removal of per-release approval prompts.
- AC-013: After source integration, a human administrator configures the standing delegation in trusted `production` environment state without a per-run reviewer gate; the configured value matches the merged repository policy hash.
- AC-014: The next ordinary runtime-impacting accepted release demonstrates `merge -> exact-main Quality -> policy allow -> applicable deploy -> runtime verification -> typed audit` without `PRODUCTION APPROVED` or other per-release production prompt.

## NFR assessment

- NFR-001 | Area: SECURITY | Target: no repository or conversational text can grant production authority; only trusted standing delegation intersected with repository constraints can allow deploy/rollback | Validation: policy unit tests, evaluator source assertions, workflow policy tests | Evidence: `production_policy.py`, `evaluate_production_policy.py`, `tests/test_production_policy.py`, `tests/test_autonomous_execution_policy.py` | Status: PASS
- NFR-002 | Area: FAIL_CLOSED | Target: missing/stale/mismatched delegation or policy denies before runtime transport | Validation: deny-path unit tests and protected workflow ordering assertions | Evidence: pure policy decision tests plus `--require-allow` workflow markers | Status: PASS
- NFR-003 | Area: PROVENANCE | Target: every new deployable release binds exact decision/delegation/policy/source/scope/artifacts/quality and every successful runtime execution produces typed audit | Validation: manifest v3 and execution-audit tests/validation | Evidence: v3 builder/validator and audit builder | Status: PASS
- NFR-004 | Area: BACKWARD_COMPATIBILITY | Target: historical v1/v2 and Windows audit evidence remain readable without granting new authority | Validation: historical manifest/deployment validator tests | Evidence: `tests/test_release_manifest.py` | Status: PASS
- NFR-005 | Area: OPERABILITY | Target: normal runtime releases require zero per-release approval interactions after standing delegation is configured | Validation: autonomous workflow trigger and later production acceptance | Evidence: source workflow tests PASS; one-time external configuration and first autonomous production run pending | Status: CONCERNS

## Runtime feedback

- Current production governance requires an exact three-line Issue comment for each release and therefore couples human approval, execution intent and audit content.
- Current repository `main` was observed as not branch-protected at task intake; repository files therefore are explicitly not treated as independent production authority state.
- The approved design uses independently administered GitHub `production` environment state for the effective standing delegation. Repository code only evaluates and narrows that delegation.
- This PR is control-plane-only. No production runtime mutation is part of source acceptance; one-time trusted delegation administration remains a post-merge protected human action.
