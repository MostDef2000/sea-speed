# Plan: #538 — unified admission phrase `commit approved`

- Specification: specs/538-unified-admission-phrase/spec.md
- Status: IMPLEMENTED — change set complete in the working tree; recorded
  verification battery green (see Validation); commit/PR lifecycle pending
  by design

## Architecture

Keep the existing validator architecture unchanged: field/section parsing
stays in `validate_change_contract.py`, checkpoint structural/cross-field
validation stays in `validate_delivery_checkpoint.py`, and the JSON schema
remains the declarative contract for checkpoint shape. The change widens
two admission-value sets and keeps everything else byte-identical:

- `SOURCE_AUTHORIZATIONS = {"commit approved", "OUTCOME APPROVED"}` with a
  dated comment naming the owner decision and dual-accept rule.
- `AUTHORIZATION_RECEIPTS = {"commit approved", "OUTCOME APPROVED"}` in the
  checkpoint validator, replacing the exact-equality check with a
  membership check whose error text names the new phrase and the legacy
  acceptance.
- Schema: `"authorization_receipt": {"enum": ["commit approved", "OUTCOME
  APPROVED"]}` replacing the single-value `const`.
- Template and generator present the new phrase for new admissions.

Error messages intentionally mention both values: the failure text teaches
the required phrase (`commit approved`) while documenting that legacy
receipts are still accepted — the machine-check description therefore
carries the legacy-acceptance wording required by the migration wording
rule.

## Decisions and rejected alternatives

- D-1: Dual-accept set (exactly two values) instead of any case-insensitive
  or normalized matching. Rejects phrase drift and keeps fail-closed
  behavior; `outcome approved` (wrong case) is garbage.
- D-2: Present the new phrase only in new-admission surfaces (template,
  generator, AGENTS.md rules); never rewrite persisted receipts. Rejects a
  bulk migration of historical Issues/specs (immutability).
- D-3: One atomic change set across machinery, tests and live contracts.
  CI checks out the merge commit, so a staged migration would let the NEW
  validator run against the OLD template/tests (or vice versa) and fail
  the required gates.
- D-4: Keep machine-gate flag names (`VISIBLE_SCOPE_PRESENTED=YES`,
  `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`,
  `SOURCE_AUTHORIZATION_ADMISSION=OPEN`) byte-identical — only the
  phrase vocabulary migrates, not the gate machine.
- D-5: Mirror the SLF family pointer line verbatim in AGENTS.md so the
  migrated family stays stylistically consistent.
- D-6: `build_sync_pr_body.py` migrates too although it was not on the
  original touch list: it generates a NEW admission body that the NEW
  validators consume; leaving the legacy phrase there would keep emitting
  legacy presentations after the merge and leave an uncategorizable hit
  in the grep sweep.

Binding inputs: owner decision 2026-10-19 (DUAL-ACCEPT; legacy receipts
remain historical), SLF precedent commit `governance: thin-adapter
AGENTS.md` (2026-10-19), JOURNAL 2026-10-19 standing decision.

## Affected contours

CONTROL_PLANE only: scripts/ci/**, schemas/**, contracts/**, tests/**,
.github/pull_request_template.md, AGENTS.md, README.md, specs/README.md,
.specify/**, docs/**, .opencode/**. No VPS or Ubuntu worker contour file
changes; no deployment workflow changes; no runtime transport changes.
`validate_change_contract.py` derives `CONTROL_PLANE` from the policy
patterns for this file set; no runtime contour is declared.

## Validation

Executed verification recorded at the working tree (see tasks T-4 for the
exact commands and observed outputs):

- Full suite: `python3 -m unittest discover -s tests -v` (or the six
  delivery/contract test files individually if environment deps block
  unrelated modules).
- `python3 -m py_compile scripts/ci/validate_change_contract.py
  scripts/ci/validate_delivery_checkpoint.py`.
- `python3 scripts/ci/validate_contracts.py` (canonical files, link check,
  resume markers).
- `python3 scripts/ci/validate_sdd.py` plus a direct
  `validate_feature_quality` call against this triplet with the draft PR
  body (quality layer: NFR, risk profile, test design, correct-course,
  traceability, DoD).
- mypy-strict on validate_delivery_checkpoint.py per
  scripts/quality/mypy.ini and ruff per repo config where the local
  toolchain allows; CI re-runs both on the PR.
- Grep sweep over live paths with per-hit categorization (legacy-acceptance
  wording / dual-accept machinery / test case / untouched historical).

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_change_contract.py::test_unified_phrase_passes_validate_authorization and default-body validate_contract green
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_change_contract.py::test_legacy_outcome_approved_remains_accepted; tests/test_delivery_checkpoint_state_machine.py legacy-receipt v2, v1-upgrade and garbage-receipt tests green
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_change_contract.py::test_garbage_authorization_phrase_is_rejected (both validators), convergence pins for template/validator/schema literals green
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: tests/test_sync_tasks_md_flow.py runs the real validator against the generated body; flag-name grep pins green
- TEST-005 | Covers: AC-005 | Level: unit | Priority: P1 | Evidence: grep sweep categorization recorded in the delivery report; untouched-file check (git diff --stat shows no specs/** narrative or decision-record paths)
- TEST-006 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: full-suite unittest summary line, py_compile, validate_contracts.py, validate_sdd.py outputs recorded in tasks.md; mypy/ruff per toolchain availability, re-run by CI

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: dual-accept set is exact-match only; garbage and case variants fail closed with an error naming the required phrase; machine-gate flags unchanged | Validation: TEST-003 green; flag grep | Residual risk: none identified beyond pre-existing admission mechanics | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: single atomic merge; convergence tests pin template, validator SOURCE line and schema enum so a partial checkout cannot pass required CI | Validation: TEST-003 convergence pins; required CI gates on merge commit | Residual risk: an open PR branch cut before the merge may need a trivial rebase to present the new phrase — dual-accept keeps it valid either way | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: live contracts state the dual-accept rule explicitly so agents and the owner see that old receipts continue to work; no action required on persisted checkpoints | Validation: docs review; validate_contracts link check | Residual risk: brief confusion window in cross-project agents — resolved by the AGENTS.md pointer line | Owner: delivery-orchestrator | Status: MITIGATED

Risk profile is REQUIRED because the change touches the checkpoint state
schema (`schemas/delivery-checkpoint-v2.schema.json`) and the CI admission
boundary — the schema-impact trigger of the Change Contract derivation.
No deployment transaction audit: no deploy/**, scripts/release/**, or
deployment-workflow files change and no runtime deployment field is
REQUIRED; the correct-course trigger is NONE.

## Correct-course check

- Trigger: NONE
- Issue impact: none — issue #538 records the migration as approved; no scope change occurred
- Specification impact: none — spec written directly for the approved DUAL-ACCEPT design
- Plan impact: none — the discovered touch point build_sync_pr_body.py was folded in as D-6 without widening the outcome
- Tasks impact: none — task list below matches the executed order
- Authorization impact: none — repository-lifecycle only; no runtime or settings authority touched
- Follow-up: none required; monitor that the post-merge auto-sync PR body validates (covered by TEST-004)

## Runtime feedback

Nothing runtime-facing changes, so there is no post-merge probe plan
beyond required CI. The observable post-merge behavior is: new PRs present
`commit approved`; pre-migration checkpoints keep validating. If a future
change needs to narrow the accepted set, repeat this atomic pattern and
record the owner decision first.
