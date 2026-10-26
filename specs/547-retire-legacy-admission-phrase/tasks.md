# Tasks — 547 Retire legacy `OUTCOME APPROVED` admission phrase

- Specification: `specs/547-retire-legacy-admission-phrase/spec.md`
- Issue: #555
- Status: DELIVERED

## Delivery tasks

- [x] TASK-001: Narrow `SOURCE_AUTHORIZATIONS` in `scripts/ci/validate_change_contract.py` to `{"commit approved"}` with an explicit rejection error naming the live phrase. (AC-001)
- [x] TASK-002: Narrow `AUTHORIZATION_RECEIPTS` in `scripts/ci/validate_delivery_checkpoint.py` and the `authorization_receipt` enum in `schemas/delivery-checkpoint-v2.schema.json` to `["commit approved"]`. (AC-002)
- [x] TASK-003: Update contract documents (governance, policy, task runtime, release gate, project-manager, branch governance) to state the retirement (owner decision 2026-10-26) with historical readability preserved. (AC-004)
- [x] TASK-004: Flip test pins from legacy acceptance to legacy rejection: `test_change_contract.py`, `test_delivery_checkpoint_state_machine.py` (v2 rejection + v1-upgrade refusal), `test_delivery_contract_convergence.py` (validator set + schema enum + template pins). (AC-001, AC-002, AC-003, AC-004)
- [x] TASK-005: Verify locally (full suite, mypy on the CI-enforced validator, workflow policy) and dogfood the new validators against the PR Change Contract body. (AC-005)

## Requirements traceability

- AC-001 | Task: TASK-001,TASK-004 | Evidence: `tests/test_change_contract.py::test_legacy_outcome_approved_is_rejected` asserts `ContractError` naming `commit approved`; positive path covered by existing suite | Coverage: COVERED
- AC-002 | Task: TASK-002,TASK-004 | Evidence: `tests/test_delivery_checkpoint_state_machine.py::test_legacy_receipt_is_rejected_in_v2_checkpoint` asserts `CheckpointValidationError` naming `commit approved` | Coverage: COVERED
- AC-003 | Task: TASK-002,TASK-004 | Evidence: `tests/test_delivery_checkpoint_state_machine.py::test_legacy_receipt_v1_upgrade_requires_fresh_receipt` asserts upgrade refusal; positive upgrade covered by existing v1 tests | Coverage: COVERED
- AC-004 | Task: TASK-002,TASK-003,TASK-004 | Evidence: `tests/test_delivery_contract_convergence.py` pins `SOURCE_AUTHORIZATIONS = {"commit approved"}` and enum `["commit approved"]`; `tests/test_delivery_quality_layer.py` governance pin; contract wording diff | Coverage: COVERED
- AC-005 | Task: TASK-005 | Evidence: full suite 1131 OK (4 pre-existing skips); mypy clean on `scripts/ci/validate_delivery_checkpoint.py`; `validate_workflow_policy.py` valid | Coverage: COVERED

## Completion gate

- Merge is admitted only when: exact declared-files Change Contract passes, Repository validation (SDD) passes, quality-integration is green on the exact PR head, and issue #555 carries the owner decision record.
- Post-merge: flip the two freshness checkboxes above and record merge evidence on issue #555 (session-close housekeeping).

## Definition of Done

- [x] Issue/spec/plan/tasks current (issue #555 records the owner decision; this SDD dir is the linked delivery record)
- [x] Exact changed-file scope verified (12 delivery files + `specs/547-retire-legacy-admission-phrase/**`; PR Change Contract declared-files match; no protected surfaces)
- [x] Required tests and evidence complete (TEST-001..004 green locally; rejection asserted as raised exceptions)
- [ ] Required CI green (Repository validation + quality-integration on the exact PR head)
- [ ] Exact-green-head merge complete (merge commit evidence recorded on #555)
- [ ] Deployment state resolved — NOT REQUIRED (CI-only; no runtime deploy contour)
- [ ] Runtime acceptance resolved — NOT REQUIRED (validators are the acceptance surface; CI evidence on PR)
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — Risk profile NOT REQUIRED (plan.md)
- [x] Waivers resolved or current — none
