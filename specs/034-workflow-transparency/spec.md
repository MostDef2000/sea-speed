# Feature Specification: Workflow Transparency Refactor

- Feature: 034-workflow-transparency
- Issue: #254
- Status: Active
- Source authorization: OUTCOME APPROVED
- Authorization base main: e3ddda5ee200262a16c3c727151c7e595122d8bc

## Product outcome

Make CI/CD workflows transparent and DRY — extract duplicated verify protection / resolve SHA / verify Quality / evaluate policy into shared composite action `.github/actions/verify-exact-release`, keep `deploy-vps.yml` and `deploy-ubuntu-worker.yml` thin, disable 3 legacy HLS workflows, and add `docs/WORKFLOW_OVERVIEW.md` with 5-step diagram. No runtime change, CONTROL_PLANE only.

## User scenarios

### Scenario 1 — PR shows two required checks
Given a PR from `agent/workflow-refactor-transparency` to `main`, when CI runs, then `Repository validation` and `quality-integration` are required and both succeed before merge is allowed.

### Scenario 2 — Shared verification is used
Given a deploy workflow runs on `main`, when it verifies exact release, then it calls `.github/actions/verify-exact-release` which checks `verify_source_protection.py`, `verify_quality_status.py`, and `evaluate_production_policy.py --require-allow` with `vars.SEA_SPEED_PRODUCTION_DELEGATION_V1`.

### Scenario 3 — Legacy workflows are gone
Given Actions tab is opened, when workflows are listed, then `agent-hls-*` and `repair-speed-stability` are `disabled_manually` and not active.

## Requirements

- FR-001: `deploy-vps.yml` and `deploy-ubuntu-worker.yml` MUST use `.github/actions/verify-exact-release` for shared verification.
- FR-002: Shared action MUST verify public protected source (`Repository validation` + `quality-integration`), resolve `--first-parent` SHA, verify quality status, and evaluate policy with `--require-allow`.
- FR-003: Docs MUST describe 5-step flow `PR Validation -> Quality gate -> Main Quality status -> Autonomous -> Deploy`.
- FR-004: Legacy workflows `agent-hls-stabilize`, `agent-hls-false-reconnect`, `repair-speed-stability-branch` MUST be disabled.

## Acceptance criteria

- AC-001: `validate_workflow_policy.py` PASS — Workflow policy valid.
- AC-002: `validate_repo.py` PASS, `validate_contracts.py` PASS, `python -m unittest discover` 428 PASS (2 skipped).
- AC-003: PR Validation and quality-integration both `success` on PR head.
- AC-004: Actions shows 6 active workflows (Pr Validation, Quality gate, Main Quality status, Autonomous, Deploy VPS, Deploy Ubuntu) + 3 disabled.
- AC-005: Deploy workflows contain `verify_source_protection.py` before `evaluate_production_policy.py` and `refs/heads/main` checks.

## NFR assessment

- NFR-OPS-001 | Area: OPERABILITY | Target: Reduce duplication by ~60 lines each, improve maintainability | Validation: diff stat | Evidence: .github/actions/verify-exact-release/action.yml | Status: PASS
- NFR-SEC-001 | Area: SECURITY | Target: No change to production authority or secrets handling | Validation: workflow policy | Evidence: scripts/quality/validate_workflow_policy.py | Status: PASS

## Compatibility and boundaries

- Stable: ` SEA_SPEED_PRODUCTION_DELEGATION_V1`, `environment: production`, `first-parent` checks.
- Out of scope: Runtime VPS/Ubuntu logic, secrets, api/frontend/worker.

## Runtime feedback

- Runtime acceptance: NOT APPLICABLE — CONTROL_PLANE, no production deployment.
- Accepted production behavior: NOT REQUIRED.
- Regressions/learning: None.
- Follow-up work: None.
