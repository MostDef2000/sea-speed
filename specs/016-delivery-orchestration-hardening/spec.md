# Specification: Delivery orchestration hardening

- Issue: #184
- Status: In implementation

## Product outcome

Sea Speed delivery must catch adjacent deployment-transaction defects before production and must let the Delivery Orchestrator initiate an already-authorized VPS deployment through the connected GitHub Connector without using the operator as a manual GitHub Actions button. Exact-SHA provenance, durable production authorization, protected environment admission, rollback semantics and runtime acceptance remain fail-closed.

## User scenarios

### Scenario 1 - Production learning produces a broad safety review, not a serial symptom fix

When a production attempt fails at any stage, the Delivery Orchestrator records the root cause, audits the neighboring stages of the deployment transaction and adds deterministic failure-path coverage before proposing another retry. A small source fix is still preferred, but the analysis is not limited to the final log line.

### Scenario 2 - Authorized VPS deployment starts from the canonical Issue

After exact-SHA `PRODUCTION APPROVED` evidence is current, the Delivery Orchestrator writes one exact `DEPLOY VPS <sha>` comment through the GitHub Connector. Repository-owned request tooling validates the comment actor, Issue context and exact SHA, then delegates to the same protected VPS deployment workflow. The operator does not need to open Actions merely to press Run workflow.

### Scenario 3 - Invalid comments cannot become production execution

Normal Issue discussion, pull-request comments, malformed commands, uppercase/short SHAs, closed-Issue commands and comments from unauthorized actors do not produce an admitted deployment request. Even an admitted request still fails closed unless the reusable deployment workflow independently verifies quality, provenance and durable production authorization.

### Scenario 4 - Pre-release Windows packaging does not fabricate production provenance

A Windows Worker source change can still produce an exact-commit ZIP and SHA-256 package during PR/main validation. Unrelated release-tool changes do not trigger Windows packaging, and ordinary packaging does not manufacture a production-bound release manifest without the production authorization evidence required by release-manifest v2.

## Requirements

- FR-001: Linked significant deployment/release work MUST carry a machine-valid Deployment Transaction Audit covering `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, and `ROLLBACK`.
- FR-002: `PRODUCTION_LEARNING` MUST additionally record `Adjacent-stage review: COMPLETE`, a concrete root cause and concrete adjacent-stage findings before the next production retry.
- FR-003: CI MUST execute the real `deploy/vps/deploy.sh` in an isolated fault-injected sandbox that can exercise success, transient verification recovery, candidate failure/rollback, stale-prune failure and idempotent retry without network or production access.
- FR-004: A VPS deployment request MUST be exactly `DEPLOY VPS <40-character-lowercase-sha>` on a newly created comment of an open canonical Issue from an actor listed in the production authorization policy.
- FR-005: The Issue request workflow MUST only validate/delegate; SSH, the `production` environment and runtime mutation MUST remain in the protected reusable `deploy-vps.yml` workflow.
- FR-006: `deploy-vps.yml` MUST retain every existing exact-main, push/main quality, durable production authorization, release-provenance, SSH and deployment-evidence gate when exposed through `workflow_call`.
- FR-007: Manual `workflow_dispatch` MUST remain available as emergency/operator fallback but MUST NOT be the normal Delivery Orchestrator path when Connector Issue writes are available.
- FR-008: A deployment-request comment MUST NOT itself count as `PRODUCTION APPROVED` or bypass fingerprint verification.
- FR-009: This process-hardening source task MUST remain `CONTROL_PLANE`; it performs no production/runtime mutation and does not modify `deploy/vps/deploy.sh` behavior.
- FR-010: Ordinary Windows Worker package validation MUST be scoped to Windows Worker/package-workflow changes, MUST bind the exact source SHA through the package contents/name/summary and SHA-256 sidecar, and MUST NOT build production release-manifest v2 without a real production safety envelope.

## Acceptance criteria

- AC-001: A linked significant PR that changes deployment/release paths, a deploy workflow, declares any runtime deployment `REQUIRED`, or uses `PRODUCTION_LEARNING` is rejected by SDD validation unless all eight deployment transaction stages are present with required failure/retry/rollback/evidence fields.
- AC-002: A `PRODUCTION_LEARNING` linked plan is rejected unless adjacent-stage review is `COMPLETE` and concrete root-cause plus adjacent-stage findings are recorded.
- AC-003: `tests/test_vps_deploy_transaction.py` executes the real unmodified VPS deploy script in a sandbox and proves successful state commit, transient health recovery, candidate rollback, warning-only stale pruning, idempotent retry and protection of current/previous releases.
- AC-004: Repository request parsing accepts an exact authorized open-Issue command and rejects unauthorized actors, PR comments, closed Issues, malformed/uppercase/short SHAs, extra text/lines and non-created events.
- AC-005: `deploy-vps-request.yml` delegates admitted requests to reusable `deploy-vps.yml`, while the request workflow contains no SSH or `environment: production` runtime mutation path.
- AC-006: `deploy-vps.yml` supports both `workflow_call` and fallback `workflow_dispatch` while preserving `environment: production`, exact-main first-parent, exact push/main quality, durable authorization and provenance gates before SSH.
- AC-007: Normal non-command Issue comments do not enter the request job, and a request command remains distinct from durable production authorization.
- AC-008: The exact PR diff is limited to the approved 18 paths, derives `CONTROL_PLANE`, declares all runtime deployments `NOT REQUIRED`, and requires no production safety envelope or runtime acceptance for this process PR.
- AC-009: `Package Windows Worker` does not trigger on unrelated `scripts/release/**` or schema-only changes and its ordinary package job emits exact worker ZIP/SHA provenance without invoking `build_release_manifest.py` or producing a production release manifest.

## NFR assessment

- NFR-001 | Area: Security | Target: No new path can reach VPS SSH without the existing exact-SHA durable authorization and protected environment gates | Validation: workflow policy plus parser and workflow architecture tests | Evidence: `tests/test_deployment_request.py`, `tests/quality/test_quality_architecture.py` | Status: PASS
- NFR-002 | Area: Reliability | Target: Five deterministic VPS transaction scenarios execute without network or production dependencies | Validation: isolated fault-injected real-script test | Evidence: `tests/test_vps_deploy_transaction.py` | Status: PASS
- NFR-003 | Area: Operator UX | Target: Normal authorized VPS execution requires no manual GitHub Actions click when Connector Issue writes are available | Validation: Issue-comment trigger delegates to reusable deployment workflow | Evidence: `.github/workflows/deploy-vps-request.yml` | Status: PASS
- NFR-004 | Area: Maintainability | Target: Production-learning review requirements are machine-enforced from the linked SDD rather than retained only in chat convention | Validation: SDD validator and plan template | Evidence: `scripts/ci/validate_sdd.py`, `.specify/templates/overrides/plan-template.md` | Status: PASS
- NFR-005 | Area: Safety | Target: This hardening PR performs zero runtime mutation and changes no runtime application/deploy-script behavior | Validation: exact changed-file scope and Change Contract | Evidence: Issue #184 Implementation Scope Check and PR diff | Status: PASS
- NFR-006 | Area: Provenance | Target: Pre-release Windows packaging never fabricates production authorization or a release-manifest v2 | Validation: package-workflow architecture regression test | Evidence: `.github/workflows/package-worker.yml`, `tests/quality/test_quality_architecture.py` | Status: PASS

## Runtime feedback

- Runtime acceptance: NOT REQUIRED for this CONTROL_PLANE task.
- Production mutation during implementation: NONE.
- Parent runtime task #178: intentionally paused until this hardening is merged and source integration evidence is green.
- First PR CI learning: the new `scripts/release/**` request parser exposed pre-existing `Package Windows Worker` coupling to every release-tool change plus a stale release-manifest v2 invocation without authorization evidence. Scope was expanded from 17 to 18 paths after a fresh Implementation Scope Check and `OUTCOME APPROVED`; remediation separates pre-release package provenance from production release provenance.
- Post-merge validation: exercise the new request path only under a separately current production envelope for the actual runtime task; do not manufacture a production deployment solely to test this process PR.
