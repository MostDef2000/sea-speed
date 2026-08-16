# Implementation Plan: Delivery orchestration hardening

- Specification: specs/016-delivery-orchestration-hardening/spec.md
- Issue: #184
- Status: In implementation

## Architecture

The hardening has three control-plane layers that meet at existing protected production/release admission.

1. **Development transaction quality**: the linked SDD plan describes all eight deployment transaction stages. `scripts/ci/validate_sdd.py` conditionally enforces that section for deployment/release paths, deploy workflows, Change Contracts with runtime deployment `REQUIRED`, and every `PRODUCTION_LEARNING`. Production learning additionally requires a completed adjacent-stage review with concrete root cause/findings. `tests/test_vps_deploy_transaction.py` executes the current repository-owned `deploy/vps/deploy.sh` in a sandbox using temporary paths and fake runtime commands; the production script itself is not modified by this task.
2. **Connector-addressable execution request**: a newly created canonical Issue comment matching `DEPLOY VPS <sha>` enters `.github/workflows/deploy-vps-request.yml`. Repository-owned `scripts/release/parse_deployment_request.py` validates exact one-line syntax, open-Issue/non-PR context, authorized actor and lowercase SHA. The request workflow contains no SSH/runtime logic and calls reusable `.github/workflows/deploy-vps.yml`, which retains `environment: production` and all existing exact-SHA quality/authorization/provenance gates. Manual `workflow_dispatch` remains fallback.
3. **Pre-release package provenance separation**: `.github/workflows/package-worker.yml` validates/builds Windows Worker packages only for `worker/**` or its own workflow changes. It produces an exact-commit ZIP, embedded `commit-sha.txt`, SHA-256 sidecar and summary, but does not invoke release-manifest v2. Production-bound release manifests remain downstream of real production authorization evidence rather than being fabricated during ordinary PR packaging.

The deployment request is deliberately separate from durable production authorization. Request admission proves only that an authorized actor asked GitHub to attempt the protected workflow; `deploy-vps.yml` still proves that runtime mutation is authorized for that exact release. Likewise, a pre-release worker package is deliberately distinct from an authorized production release manifest.

## Decisions

### D-001 - Reuse the protected Deploy VPS workflow

- Decision: Add `workflow_call` to `.github/workflows/deploy-vps.yml` and route Connector Issue requests into it.
- Reason: One deployment implementation prevents the comment path and manual fallback from drifting in quality, provenance, SSH, environment or evidence gates.
- Alternatives rejected: Duplicate the deployment job in the request workflow; direct SSH from the request workflow; weaken manual-only governance without a replacement admission path.

### D-002 - Treat Issue comments as execution requests, never authorization

- Decision: Accept only exact `DEPLOY VPS <lowercase-sha>` comments on open Issues from policy-authorized actors, then re-run the existing durable production authorization verifier in the called workflow.
- Reason: Connector Issue comments are available in this chat while direct workflow dispatch creation is not; preserving a second authorization verifier prevents command injection or accidental comments from becoming production authority.
- Alternatives rejected: Infer deployment from `PRODUCTION APPROVED`; use arbitrary natural-language comments; allow PR comments; let request parsing verify/replace the production fingerprint.

### D-003 - Make deployment analysis transactional and machine-enforced

- Decision: Add an eight-stage Deployment Transaction Audit to the SDD quality layer and require adjacent-stage review for production learning.
- Reason: Runs #25, #26 and #27 exposed different defects at admission, verification and housekeeping. Fixing only the current failing line created serial production retries.
- Alternatives rejected: Rely on reviewer memory; add more prose without validator enforcement; require broad source changes instead of broad analysis.

### D-004 - Test the real deploy script without production

- Decision: Use temporary filesystem state and fake `curl`, `sudo`, `systemctl`, `sleep` and `rm` around the real `deploy/vps/deploy.sh`.
- Reason: This exercises state ordering and failure behavior while preventing network, systemd, SSH or production mutation.
- Alternatives rejected: Copy the shell logic into a Python model; only assert source strings; invoke a live VPS from CI.

### D-005 - Keep Windows CI packaging pre-release, not production-authorized

- Decision: Remove generic `scripts/release/**`/schema triggers and release-manifest v2 construction from `Package Windows Worker`; retain exact ZIP/SHA/source identity for actual worker/package-workflow changes.
- Reason: PR #185 exposed that the workflow had been stale since release-manifest v2 began requiring authorization evidence. Supplying synthetic authorization would weaken provenance semantics; broad release-tool triggers also caused irrelevant Windows packaging failures.
- Alternatives rejected: Manufacture placeholder production authorization; make release-manifest v2 accept missing authorization; keep every release-tool change coupled to Windows packaging; ignore a known red workflow.

## Affected contours

- Repository: governance, SDD validator/template, release request parser, GitHub workflows, quality tests and feature 016 SDD only.
- VPS: NONE for this process PR; future separately authorized VPS deployments use the new request path.
- Ubuntu worker/relay: NONE.
- Windows worker/AI runtime: NONE. The package workflow is control-plane CI only; no worker source or installation is changed.
- Public interfaces: GitHub Issue execution-request command `DEPLOY VPS <exact-sha>` is a new operator/control-plane interface; application/public HTTP interfaces are unchanged.

## Validation

- Static/CI: repository/contract validation, SDD validation, workflow policy, Python compilation, full behavioral test discovery, PR Validation and aggregate Quality integration.
- Integration: parser tests, workflow architecture/policy tests, sandboxed real-script VPS transaction tests, and Windows pre-release packaging architecture assertions.
- Package workflow: because `.github/workflows/package-worker.yml` itself changes, the final PR head must execute `Package Windows Worker` and prove exact ZIP/SHA packaging succeeds without release-manifest v2.
- Runtime acceptance: NOT REQUIRED for this CONTROL_PLANE PR. The request path is used later only when a separate runtime task has current production authorization.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: Exact command parser requires open Issue, non-PR context, policy-authorized actor and lowercase SHA; reusable deploy still verifies durable production authorization and protected environment | Validation: parser negative tests plus workflow architecture/policy tests | Residual risk: LOW because request is not authority | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: Single reusable deploy workflow preserves existing first-parent, push/main quality, provenance, SSH and evidence gates for both request and manual paths | Validation: workflow policy and quality architecture tests | Residual risk: LOW after exact-head CI | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: Transaction tests execute the real deploy script with controlled fakes instead of a duplicate state-machine implementation | Validation: five fault-path transaction tests | Residual risk: MEDIUM because hosted CI cannot reproduce all VPS filesystem/systemd behavior | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: Production-learning validator requires full adjacent-stage review before retry and any newly discovered out-of-scope defect returns to scope authorization | Validation: SDD validator plus this plan audit | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: Package workflow remains triggered for every `worker/**` change and its own workflow changes while release-tool-only changes are decoupled; exact ZIP/SHA/source identity remains | Validation: package workflow execution plus quality architecture assertions | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002,RISK-004 | Level: integration | Priority: P0 | Evidence: `scripts/ci/validate_sdd.py` exercised by PR/static quality validation against this linked plan
- TEST-002 | Covers: AC-003,RISK-003 | Level: integration | Priority: P0 | Evidence: `tests/test_vps_deploy_transaction.py`
- TEST-003 | Covers: AC-004,RISK-001 | Level: unit | Priority: P0 | Evidence: `tests/test_deployment_request.py`
- TEST-004 | Covers: AC-005,AC-006,AC-007,RISK-001,RISK-002 | Level: integration | Priority: P0 | Evidence: `tests/quality/test_quality_architecture.py` plus `scripts/quality/validate_workflow_policy.py`
- TEST-005 | Covers: AC-008 | Level: integration | Priority: P1 | Evidence: PR Change Contract, exact 18-path compare and post-merge quality evidence
- TEST-006 | Covers: AC-009,RISK-005 | Level: integration | Priority: P0 | Evidence: `tests/quality/test_quality_architecture.py` plus final-head `Package Windows Worker` run proving ZIP/SHA packaging without release-manifest v2

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #184 isolates delivery-process remediation from product/runtime Issue #178 and records the exact 18-path scope after the separately approved packaging-workflow expansion.
- Specification impact: Feature 016 makes transactional failure analysis, Connector-addressable VPS execution and pre-release-vs-production provenance separation explicit acceptance requirements.
- Plan impact: Architecture separates execution request from authorization, models deployment as an eight-stage transaction and separates ordinary Windows packaging from production release-manifest generation.
- Tasks impact: Adds parser/workflow/validator/harness/governance work plus the authorized package-workflow compatibility remediation before #178 production retry resumes.
- Authorization impact: Fresh `OUTCOME APPROVED` was obtained first for the 17-path control-plane scope and again after the exact expansion to 18 paths; no production authorization is created by this task.
- Follow-up: Merge only exact-green source after PR Validation, Quality integration and the applicable Package Windows Worker check are green on the same final head, then resume #178 from read-only runtime-state recovery and the separately applicable production envelope using the new request mechanism.

## Deployment transaction audit

This audit describes the protected VPS transaction that this process change must review and test. This PR itself remains CONTROL_PLANE and does not execute the mutation stages.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: runtime unchanged and no SSH configured | Retry: correct Issue command/main-history/quality/authorization/provenance evidence then submit a fresh request | Rollback: NOT REQUIRED because runtime mutation has not started | Evidence: request parser output plus first-parent/quality/authorization/release admission logs
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: runtime unchanged with deployment artifacts prepared only on runner | Retry: correct protected environment secrets/prerequisites and rerun the exact authorized request | Rollback: NOT REQUIRED because target mutation has not started | Evidence: exact artifacts, release manifest, quality evidence and SSH configuration result
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate files may be installed while committed current-release still identifies prior verified release until verification succeeds | Retry: only through repository-owned safe retry after actual state recovery | Rollback: candidate verification failure invokes install of the prior current release | Evidence: deploy script logs and sandbox mutation/rollback tests
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not committed when verification fails and automatic rollback is attempted | Retry: resolve root cause and verify actual runtime state before another deployment | Rollback: reinstall prior current release and require canonical origin plus frontend smoke verification | Evidence: 8010 origin health, public smoke checks and transaction tests
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: acceptance is unresolved if current/previous/manifest cannot be persisted consistently | Retry: read actual runtime and state files before any further mutation | Rollback: use the still-known prior verified release according to recovered state | Evidence: current-release, previous-release and deployment-manifest ordering/assertions
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified current and previous releases plus committed deployment state remain valid while stale files may remain | Retry: cleanup may be retried independently after deployment | Rollback: NOT REQUIRED solely for stale-release pruning failure | Evidence: warning-only stale-prune transaction test and retained current/previous directories
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: runtime may be healthy but acceptance remains insufficient until exact deployment evidence is recollected | Retry: recollect and validate deployment manifest/artifacts without unnecessary runtime mutation when safe | Rollback: decide from runtime evidence rather than evidence-upload transport failure alone | Evidence: validated deployment manifest and uploaded exact release/authorization evidence
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if rollback verification fails runtime state is unknown and further automated mutation stops | Retry: recover actual service/source/state read-only and use separately authorized recovery | Rollback: secondary automatic rollback is not guessed; escalate with exact recovered state | Evidence: rollback health/source identity and rolled_back deployment manifest

- Adjacent-stage review: COMPLETE
- Production-learning root cause: Runs #25, #26 and #27 exposed independent stale verification configuration, pipefail-sensitive admission logic, and fatal post-commit housekeeping; the delivery process reviewed only the immediate failing stage before each retry.
- Production-learning adjacent-stage findings: Admission must be pipefail-safe and exact-main bound; verification must use the canonical 8010 origin; state commit must precede housekeeping; housekeeping failure must not invalidate verified state; evidence transport must remain distinct from runtime health; rollback and idempotent retry require explicit fault-path tests; CI trigger boundaries must match actual dependency boundaries; pre-release packaging must not fabricate production release authorization/provenance.

## Rollout and rollback

- Rollout: Merge this CONTROL_PLANE PR only after exact-head PR Validation, aggregate Quality integration and final-head Package Windows Worker are green; verify post-merge push/main quality. Do not deploy this PR to VPS/Ubuntu/Windows. Once merged, resume Issue #178 from read-only runtime recovery and use the new Issue-comment request only when its exact runtime authorization remains/currently becomes valid.
- Rollback: If the process change proves defective before runtime use, revert the exact process-hardening merge through normal source governance. Manual `workflow_dispatch` remains fallback, and no runtime state depends on this PR until a separately authorized deployment request is executed.

## Runtime feedback

- Actual architecture after acceptance: PENDING exact-green merge; no runtime acceptance applies to this task.
- Differences from plan: Initial 17-path implementation reached green PR Validation/Quality integration but triggered pre-existing `Package Windows Worker` failure because `scripts/release/**` was over-broadly coupled to Windows packaging and the workflow still called release-manifest v2 without required authorization evidence. The operator approved an exact one-path expansion to `.github/workflows/package-worker.yml`; the final scope is 18 paths.
- Deferred cleanup: NONE for this task; any deploy-script defect discovered outside the approved 18-path scope still requires separate authorization rather than hidden expansion.
