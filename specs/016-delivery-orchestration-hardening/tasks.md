# Delivery Tasks: Delivery orchestration hardening

- Specification: specs/016-delivery-orchestration-hardening/spec.md
- Issue: #184
- Status: In implementation

## Delivery tasks

- TASK-001: Keep the exact approved repository scope limited to these 18 paths: `AGENTS.md`, `contracts/SEA_SPEED_DELIVERY_POLICY.md`, `contracts/runtime/RELEASE_READINESS_GATE.md`, `contracts/branches/project-manager.md`, `.github/workflows/deploy-vps.yml`, `.github/workflows/deploy-vps-request.yml`, `.github/workflows/package-worker.yml`, `scripts/release/parse_deployment_request.py`, `scripts/quality/validate_workflow_policy.py`, `scripts/ci/validate_sdd.py`, `tests/quality/test_quality_architecture.py`, `tests/test_deployment_request.py`, `tests/test_vps_deploy_transaction.py`, `.specify/templates/overrides/plan-template.md`, `specs/README.md`, `specs/016-delivery-orchestration-hardening/spec.md`, `specs/016-delivery-orchestration-hardening/plan.md`, `specs/016-delivery-orchestration-hardening/tasks.md`.
- TASK-002: Add `workflow_call` to `Deploy VPS` without weakening any existing first-parent, push/main quality, production authorization, provenance, protected-environment, SSH, runtime verification or evidence gate; retain manual dispatch fallback.
- TASK-003: Add `deploy-vps-request.yml` so only a command-like newly created canonical Issue comment enters parser validation and successful parsing delegates to the reusable protected deployment workflow.
- TASK-004: Implement `parse_deployment_request.py` with exact one-line lowercase-SHA syntax, open Issue/non-PR context, consistent comment/sender actor and production-policy authorized actor checks.
- TASK-005: Add parser negative tests and workflow architecture/policy tests proving malformed/unauthorized request data cannot become a delegated deployment.
- TASK-006: Extend SDD quality admission with a conditional eight-stage Deployment Transaction Audit and mandatory adjacent-stage review for `PRODUCTION_LEARNING`; update canonical template/readme/governance.
- TASK-007: Add the isolated VPS transaction harness around the real unmodified `deploy/vps/deploy.sh`, covering success, transient health recovery, candidate rollback, stale-prune failure and idempotent retry without network/systemd/SSH/production access.
- TASK-008: If TASK-007 exposes a real deploy-script defect requiring any path outside this 18-path scope, stop writes and obtain a fresh Implementation Scope Check plus `OUTCOME APPROVED`; do not alter `deploy/vps/deploy.sh` under this authorization.
- TASK-009: Open one CONTROL_PLANE PR linked to Issue #184/spec 016, declare `Risk profile: REQUIRED`, all runtime deployment fields `NOT REQUIRED`, and drive only in-scope CI remediation.
- TASK-010: Merge only the exact green head after fresh main/head/scope/review checks, then verify exact push/main PR Validation and Quality integration.
- TASK-011: Record process integration evidence on Issue #184 and close it only when source/control-plane acceptance is complete; no production mutation is required for this task.
- TASK-012: Resume parent runtime Issue #178 only after this task is complete, starting with read-only recovery of actual VPS state from run #27 rather than assuming the runtime result.
- TASK-013: Correct the discovered `Package Windows Worker` control-plane debt by narrowing triggers to worker/package-workflow changes, preserving exact ZIP/SHA/source provenance, removing ordinary PR-time release-manifest v2 generation, and proving the final workflow succeeds without production authorization evidence.
- TASK-014: After any approved scope expansion, synchronize the PR Change Contract before the final source synchronization commit and preserve the validator's canonical field names/values exactly (`Approval recorded after Implementation Scope Check: YES`, `Material scope/protected-boundary change since authorization: NO`, `Local checks`, `PR checks`). If a run captured stale or noncanonical metadata, create a new in-scope synchronization commit rather than treating that event as source evidence.

## Requirements traceability

- AC-001 | Task: TASK-006 | Evidence: `scripts/ci/validate_sdd.py`, plan template, linked plan validation in static-contract-security | Coverage: COVERED
- AC-002 | Task: TASK-006 | Evidence: production-learning adjacent-stage fields in `specs/016-delivery-orchestration-hardening/plan.md` plus SDD validator | Coverage: COVERED
- AC-003 | Task: TASK-007 | Evidence: `tests/test_vps_deploy_transaction.py` executes the repository `deploy/vps/deploy.sh` in five deterministic sandbox scenarios | Coverage: COVERED
- AC-004 | Task: TASK-004,TASK-005 | Evidence: `scripts/release/parse_deployment_request.py` and `tests/test_deployment_request.py` | Coverage: COVERED
- AC-005 | Task: TASK-002,TASK-003,TASK-005 | Evidence: request workflow delegates to reusable deploy workflow; workflow policy prohibits SSH/environment in request path | Coverage: COVERED
- AC-006 | Task: TASK-002,TASK-005 | Evidence: `.github/workflows/deploy-vps.yml` plus `tests/quality/test_quality_architecture.py` and workflow policy | Coverage: COVERED
- AC-007 | Task: TASK-003,TASK-004,TASK-005 | Evidence: request job command prefix gate plus exact parser tests; durable production verifier remains inside called workflow | Coverage: COVERED
- AC-008 | Task: TASK-001,TASK-009,TASK-010,TASK-014 | Evidence: exact 18-path Git compare, synchronized CONTROL_PLANE Change Contract and exact-head/post-merge CI | Coverage: COVERED
- AC-009 | Task: TASK-013 | Evidence: `.github/workflows/package-worker.yml`, `tests/quality/test_quality_architecture.py`, and final-head Package Windows Worker run | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current: Issue #184 and feature 016 describe the accepted process outcome, the CI-discovered packaging finding and exact expanded scope.
- [ ] Exact changed-file scope verified: final branch diff must equal the approved 18 paths with no runtime source expansion.
- [ ] Required tests and evidence complete: parser, workflow policy/architecture, transaction harness, packaging-boundary assertions and repository behavioral tests must pass on the final exact head.
- [ ] Required CI green: PR Validation and aggregate Quality integration must both succeed on the same final head; because `.github/workflows/package-worker.yml` changes, final-head Package Windows Worker must also succeed.
- [ ] Exact-green-head merge complete: merge only after fresh base/head/scope/review checks with expected-head protection.
- [x] Deployment state resolved: NOT REQUIRED for this CONTROL_PLANE process PR; Issue #178 runtime remains separately paused/pending recovery.
- [x] Runtime acceptance resolved: NOT REQUIRED for this CONTROL_PLANE process PR.
- [x] Deferred work recorded: parent runtime Issue #178 resumes only after this hardening; any out-of-scope deploy-script defect requires separate authorization.
- [x] Risks resolved or explicitly accepted: RISK-001 through RISK-005 are mitigated by parser, reusable workflow gates, transaction audit, fault-path tests and package-boundary checks; exact-head CI remains required.
- [x] Waivers resolved or current: no waiver is requested; quality verdict must not be FAIL.

## Completion gate

This task is complete only when the exact 18-path source change is merged from a green head, post-merge push/main quality is successful, and Issue #184 carries durable integration evidence. It must not claim or require VPS/Ubuntu/Windows runtime acceptance. The first subsequent production attempt belongs to the separately authorized runtime task and uses the hardened process.
