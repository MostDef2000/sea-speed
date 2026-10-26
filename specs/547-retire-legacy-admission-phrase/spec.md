# 547 — Retire legacy `OUTCOME APPROVED` admission phrase

- Issue: #555
- Status: DELIVERED
- Linked plan: `specs/547-retire-legacy-admission-phrase/plan.md`
- Linked tasks: `specs/547-retire-legacy-admission-phrase/tasks.md`

## Product outcome

After this feature, the only live source-authorization phrase in sea-speed is `commit approved`. The legacy phrase `OUTCOME APPROVED` is retired per the owner decision of 2026-10-26 (dev chat): the Change Contract validator, the delivery-checkpoint validator, and the checkpoint v2 schema reject it for new admissions and updated checkpoints, the six active contracts state the retirement instead of legacy acceptance, and historical records (past issues, PRs, git history) stay untouched and readable.

## User scenarios

- Delivery Orchestrator admits a new task with `commit approved` — both validators accept; delivery proceeds unchanged.
- A stale or legacy `OUTCOME APPROVED` receipt is presented for a new Change Contract or checkpoint update — validation fails with an error naming `commit approved`; the task re-enters admission.
- A persisted v1 checkpoint still carrying a legacy receipt reaches its next meaningful transition — the v1 upgrade refuses the legacy value; a fresh `commit approved` is required.
- An auditor reads past issues/PRs — historical legacy receipts remain machine-readable as history; nothing is rewritten.

## Requirements

- FR-001: `scripts/ci/validate_change_contract.py` accepts only `commit approved` as Source authorization for new Change Contracts and raises a contract error naming the live phrase for any other value.
- FR-002: `scripts/ci/validate_delivery_checkpoint.py` accepts only `commit approved` as `authorization_receipt` for new and updated checkpoints and raises a checkpoint validation error naming the live phrase.
- FR-003: `schemas/delivery-checkpoint-v2.schema.json` declares `authorization_receipt` enum `["commit approved"]`.
- FR-004: the six active contracts (`SEA_SPEED_GOVERNANCE.md`, `SEA_SPEED_DELIVERY_POLICY.md`, `SEA_SPEED_TASK_RUNTIME.md`, `RELEASE_READINESS_GATE.md`, `project-manager.md`, branch `governance.md`) state the retirement (owner decision 2026-10-26) instead of legacy acceptance; historical readability is preserved in wording.
- FR-005: the v1→v2 upgrade path refuses a legacy receipt and requires a fresh `commit approved` at the next meaningful transition.
- FR-006: tests assert legacy rejection as behavior (raised exceptions), not only as documentation strings.

## Acceptance criteria

- AC-001: `validate_authorization` and `validate_contract` accept `commit approved` and raise `ContractError` naming `commit approved` for `OUTCOME APPROVED` (tests/test_change_contract.py).
- AC-002: `validate_checkpoint` raises `CheckpointValidationError` naming `commit approved` for a v2 checkpoint whose `authorization_receipt` is `OUTCOME APPROVED` (tests/test_delivery_checkpoint_state_machine.py).
- AC-003: `upgrade_v1_checkpoint` on a v1 record carrying a legacy receipt raises `CheckpointValidationError` naming `commit approved`; the upgrade of a `commit approved` v1 record still succeeds.
- AC-004: the schema enum and the convergence pins in tests/test_delivery_contract_convergence.py match `["commit approved"]` exactly; no live contract text states legacy acceptance.
- AC-005: full test suite green; mypy clean on the CI-enforced `scripts/ci/validate_delivery_checkpoint.py`.

## Runtime feedback

- CI-only change; no runtime behavior. The acceptance surface is the repository's own CI validators (Repository validation + quality-integration) and the local suite evidence recorded on issue #555 and the PR Change Contract.
- If a future checkpoint resume hits the legacy rejection, the operator records a fresh `commit approved` in the canonical issue; no code change is expected.

## NFR assessment

- NFR-001 | Area: Governance consistency | Target: zero live acceptance of `OUTCOME APPROVED` across validators, schema, and the six active contracts | Validation: convergence and rejection tests plus full suite | Evidence: PR CI (Repository validation, quality-integration) and local run 1131 OK | Status: PASS
- NFR-002 | Area: Historical integrity | Target: no historical record (issue, PR, git history) rewritten by this change | Validation: changed-files diff review — only validators, schema, contracts, tests, and this SDD dir | Evidence: PR diff | Status: PASS
- NFR-003 | Area: Type safety | Target: mypy clean on CI-enforced validator files | Validation: quality-integration mypy step | Evidence: PR CI run | Status: PASS
