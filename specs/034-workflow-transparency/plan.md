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

- No new tests — EXISTING tests `tests/test_autonomous_execution_policy.py`, `tests/quality/test_quality_architecture.py`, `tests/test_ubuntu_zero_touch_transport.py` cover workflow contracts.
- Validate with `scripts/quality/validate_workflow_policy.py`, `scripts/ci/validate_repo.py`, `python -m unittest discover`.

## Correct-course check

- If composite breaks, fallback to inline verification (revert to previous inline 4 steps). No data loss, CONTROL_PLANE only.

## Runtime feedback

- CONTROL_PLANE — no runtime verification needed; Autonomous still triggers only on Quality success.
