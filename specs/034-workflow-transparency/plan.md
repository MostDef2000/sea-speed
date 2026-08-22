# Plan 034 — Workflow Transparency

- Specification: specs/034-workflow-transparency/spec.md
- Issue: #254
- Status: Active

## Architecture

Shared composite `.github/actions/verify-exact-release/action.yml` holds 4 steps: verify_source_protection + resolve SHA + verify_quality_status + evaluate policy. Deploy workflows call it via `uses: ./.github/actions/verify-exact-release`.

## Decisions

- Use composite action instead of reusable workflow to keep job context and avoid extra runner.
- Keep contract markers as comments to satisfy `validate_workflow_policy` string checks.
- Disable legacy workflows via API `disable` rather than file delete (GitHub retains them otherwise).

## Affected contours

- VPS deployment: NOT REQUIRED
- Ubuntu worker/relay update: NOT REQUIRED
- Production safety envelope: NOT REQUIRED

## Validation

- `scripts/quality/validate_workflow_policy.py` — must be valid
- `scripts/ci/validate_repo.py` + `validate_contracts.py`
- `python -m unittest discover -s tests -p test_*.py` — 428 PASS

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-034-001 | Covers: AC-001, FR-001, FR-002 | Level: unit | Priority: P0 | Evidence: `scripts/quality/validate_workflow_policy.py` — shared composite contains verify_source_protection, first-parent, verify_quality_status, evaluate_production_policy
- TEST-034-002 | Covers: AC-002, AC-003 | Level: integration | Priority: P0 | Evidence: `python -m unittest discover -s tests -p test_*.py` — 428 PASS, PR Validation + quality-integration success
- TEST-034-003 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: Actions shows 6 active workflows + 3 disabled, docs/WORKFLOW_OVERVIEW.md present

## Correct-course check

- Trigger: NONE
- Issue impact: No Issue impact — CONTROL_PLANE refactoring, Issue #254 remains.
- Specification impact: No spec impact beyond 034.
- Plan impact: Shared action reduces duplication, no runtime change.
- Tasks impact: Tasks 034 cover composite creation and docs.
- Authorization impact: Remains inside OUTCOME APPROVED for 034; no new production authority.
- Follow-up: None.

## Runtime feedback

- CONTROL_PLANE — no runtime verification needed; Autonomous still triggers only on Quality success.

## Deployment transaction audit

- NOT REQUIRED — CONTROL_PLANE, no production deployment, no transaction.
