# Plan — 547 Retire legacy `OUTCOME APPROVED` admission phrase

- Specification: `specs/547-retire-legacy-admission-phrase/spec.md`
- Issue: #555
- Status: DELIVERED

## Architecture

Repository-governance change confined to the control plane: two validators (`scripts/ci/validate_change_contract.py`, `scripts/ci/validate_delivery_checkpoint.py`), one JSON schema (`schemas/delivery-checkpoint-v2.schema.json`), six contract documents, four test modules, and this SDD feature directory. No runtime surface, no workflow file, no deploy path. The validators are the single enforcement points the repository already routes PR admission and checkpoint validation through, so the retirement is enforced by narrowing their accepted phrase sets from `{"commit approved", "OUTCOME APPROVED"}` to `{"commit approved"}` with explicit rejection errors.

## Decisions

- DEC-001: Narrow the accepted sets instead of adding a deprecation-warning mode. Rationale: the owner decision is a hard retirement; a warning mode would leave two live phrases and defeat the unification. Historical records stay readable by design — validation rejects the value for new admissions and updated checkpoints only.
- DEC-002: Keep the v1→v2 upgrade mechanics unchanged; the upgrade validates and therefore refuses a legacy receipt. Rationale: v1 records remain readable evidence, but continuation under a retired receipt requires a fresh `commit approved` — conversion must not recreate source authority.
- DEC-003: Do not touch `.github/pull_request_template.md` or historical specs. Rationale: the template never mentioned the legacy phrase; old specs (e.g. 013) record the history of when the phrase was current.
- DEC-004: Link this feature's own SDD directory instead of an existing spec. Rationale: the existing admission-phrase spec (538) declares Risk profile REQUIRED and describes the unification, not the retirement; no other complete spec covers the validators; linking an unrelated spec would be traceability laundering.

## Affected contours

- CONTROL_PLANE only: `scripts/ci/`, `schemas/`, `contracts/`, `tests/`, `specs/547-retire-legacy-admission-phrase/`. No VPS, no Ubuntu worker, no Windows (retired), no deploy/ or scripts/release/ paths.

## Validation

- Local: full `python3 -m unittest discover -s tests` (1131 OK, 4 pre-existing skips), `mypy --config-file scripts/quality/mypy.ini scripts/ci/validate_delivery_checkpoint.py` (clean), `python3 scripts/quality/validate_workflow_policy.py` (valid), dogfooded `validate_change_contract` and `validate_sdd --event` against the PR body and diff.
- PR: Repository validation (SDD + Change Contract), quality-integration (unittest + mypy), static security, Gitleaks.

## Runtime feedback

- Not applicable — CI-only control-plane change. The validators themselves are the acceptance surface; CI evidence is recorded on the PR and issue #555.

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: `tests/test_change_contract.py` `test_legacy_outcome_approved_is_rejected` asserts `ContractError` naming `commit approved` on both `validate_authorization` and `validate_contract`
- TEST-002 | Covers: AC-002, AC-003 | Level: unit | Priority: P0 | Evidence: `tests/test_delivery_checkpoint_state_machine.py` `test_legacy_receipt_is_rejected_in_v2_checkpoint` and `test_legacy_receipt_v1_upgrade_requires_fresh_receipt` assert `CheckpointValidationError`; positive v1→v2 upgrade with `commit approved` covered by existing tests
- TEST-003 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: `tests/test_delivery_contract_convergence.py` pins `SOURCE_AUTHORIZATIONS = {"commit approved"}` and schema enum `["commit approved"]`; contract retirement wording covered by `tests/test_delivery_quality_layer.py` governance pin
- TEST-004 | Covers: AC-005 | Level: integration | Priority: P1 | Evidence: full suite 1131 OK (4 pre-existing skips); mypy clean on CI-enforced validator; `validate_workflow_policy` valid

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE
