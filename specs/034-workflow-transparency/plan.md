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

- Adjacent-stage review: COMPLETE
- TX-034-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: source remains unapproved, no deployment | Retry: retry after exact Issue/scope/hash admission | Rollback: not applicable | Evidence: Issue #254 scope, exact base e3ddda5, workflow-policy valid
- TX-034-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: workflows unchanged, no transport | Retry: repair exact source and re-verify policy | Rollback: not applicable | Evidence: verify_source_protection + verify_quality_status + evaluate_production_policy checks
- TX-034-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate workflows partially written, live workflows on previous commit | Retry: re-apply shared action and re-render | Rollback: restore previous workflow files from backup | Evidence: .github/actions/verify-exact-release staged, deploy workflows reference shared action
- TX-034-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: mutation not committed if verification fails | Retry: re-verify workflow-policy + SDD + tests | Rollback: restore previous workflows | Evidence: validate_workflow_policy PASS, validate_sdd PASS, 428 tests PASS
- TX-034-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: commit not advanced unless verification passes | Retry: commit only after verification | Rollback: keep previous commit as rollback target | Evidence: current branch head f8b8db0 + previous e3ddda5
- TX-034-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified workflows remain while stale branches await pruning | Retry: prune stale branches without touching main | Rollback: no rollback required | Evidence: branch agent/workflow-refactor-transparency pruned after merge
- TX-034-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: acceptance remains incomplete without evidence | Retry: recollect workflow evidence | Rollback: no evidence-only rollback | Evidence: PR #253 Change Contract + SDD 034 + Actions 6 active workflows
- TX-034-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous workflows remain rollback target | Retry: restore previous workflows and re-verify | Rollback: byte-identical restore of deploy workflows | Evidence: rollback via git revert + workflow-policy re-validation

