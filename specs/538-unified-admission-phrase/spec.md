# Spec: #538 — unified admission phrase `commit approved`

- Issue: #538
- Reference checkout: 27107db05da44e57b8b6a63139f1ee4c322ceaae
- Status: IMPLEMENTED — change set complete in the working tree, suite and
  validators observed green (see plan Validation); commit/PR lifecycle is
  owned by the delivery orchestrator and pending by design

## Product outcome

Sea Speed presents exactly one scope-admission phrase for NEW source
admissions: the exact lowercase phrase `commit approved`. Legacy receipts
recorded as `OUTCOME APPROVED` remain valid historical evidence and are
still accepted by every machine gate (dual-accept), so no in-flight task,
persisted checkpoint or v1 upgrade path breaks. CI validation machinery is
unchanged in structure: the same validators, schema and required checks
admit PRs; only the presented phrase vocabulary and the accepted receipt
set change.

Owner decision 2026-10-19 (unified admission migration, delivery chat):
DUAL-ACCEPT in validators — `commit approved` is the only phrase presented
for NEW admissions (AGENTS.md, PR template); legacy `OUTCOME APPROVED`
receipts remain valid (owner's standing decision "legacy receipts remain
historical"). The family precedent is the SLF migration (2026-10-19,
`governance: thin-adapter AGENTS.md`), which added the same global-contract
pointer and phrase.

## User scenarios

- Owner authorizing a new task: presents approval as `commit approved`
  after the visible six-field Scope; the PR Change Contract carries
  `- Source authorization: commit approved` and both required CI gates
  (PR Validation, Quality integration) accept it.
- Owner or agent resuming a task admitted before 2026-10-19: the persisted
  Issue receipt says `OUTCOME APPROVED`; `validate_delivery_checkpoint.py`
  still validates the checkpoint and the v1 upgrade path preserves the
  legacy receipt without re-authorization.
- Agent preparing a PR from the template: the template presents
  `commit approved`; a PR body that still carries a legacy
  `OUTCOME APPROVED` line (for example generated before the migration)
  also validates — dual-accept — but the only presented default is the new
  phrase.
- Garbage or case-mangled phrases (`outcome approved`, `APPROVED OUTCOME`,
  `LEGACY COMMIT APPROVED`) fail closed in both validators with an error
  naming `commit approved` and the legacy acceptance.
- Automated tasks.md sync PRs: `build_sync_pr_body.py` emits
  `commit approved`; the generated body passes the real validator.

## Problem statement

Before this change the admission phrase was `OUTCOME APPROVED`, while the
workspace-wide global contract and sibling projects (SLF) already unified
on `commit approved`. Two live vocabularies for the same authority decision
invite cross-project phrase confusion (an agent working in both projects
must remember which phrase each repo expects) and the PR template taught a
phrase that is no longer the family-wide admission phrase. The migration is
deliberately one atomic change set: validators, schema, template, tests and
live contracts must be mutually consistent at the merge commit, because CI
runs the NEW validators via merge-commit checkout and both gates are
required checks.

## Requirements

- R-1: `scripts/ci/validate_change_contract.py` accepts `Source
  authorization: commit approved` and continues to accept the legacy
  `OUTCOME APPROVED` value (dual-accept); any other value fails with an
  error naming `commit approved`.
- R-2: `scripts/ci/validate_delivery_checkpoint.py` and
  `schemas/delivery-checkpoint-v2.schema.json` accept
  `authorization_receipt` values `commit approved` and `OUTCOME APPROVED`;
  other values fail closed. The v1 upgrade path keeps carrying a legacy
  receipt through validation.
- R-3: `.github/pull_request_template.md` presents exactly
  `commit approved` as the Source authorization default; it does not
  present the legacy phrase as a new-admission default.
- R-4: `scripts/ci/build_sync_pr_body.py` emits the new phrase in the
  generated auto-sync Change Contract.
- R-5: `AGENTS.md` carries the global-contract pointer line (durable
  source: profiles/global/** in ai-playground; scope-admission phrase
  `commit approved`; rules below additive) and its admission rules use the
  new phrase, noting legacy acceptance.
- R-6: All live contracts/docs/state the machine-acceptable values: the
  admission phrase in live rules is `commit approved`; wherever a document
  describes machine validation, legacy `OUTCOME APPROVED` receipts are
  noted as still accepted (historical). specs/** historical narrative and
  decision records DR-004/005/006 are untouched.
- R-7: The machine-gate flag names (`VISIBLE_SCOPE_PRESENTED=YES`,
  `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`,
  `SOURCE_AUTHORIZATION_ADMISSION=OPEN`) remain byte-identical.
- R-8: Tests cover: new-phrase PR body passes `validate_authorization`;
  legacy receipt still passes (dual-accept) for both validators; a v1
  checkpoint with legacy receipt still upgrades and validates; garbage
  phrases are rejected by both validators; template/validator/schema
  convergence pins assert the new literals.

## Non-goals

- Renaming or restructuring any validator, schema key, workflow, gate or
  flag name.
- Rewriting historical specs/** narrative, decision records, or historical
  Issue/PR evidence (immutable audit history).
- Migrating persisted Issue checkpoints or receipts (they remain valid as
  recorded).
- Any runtime/deploy contour change; no api/**, frontend/**, worker/**,
  deploy/** file changes.

## Acceptance criteria

- AC-001: A PR body with `- Source authorization: commit approved` passes
  `validate_authorization` and the full `validate_contract`.
- AC-002: A PR body with the legacy `- Source authorization: OUTCOME
  APPROVED` still passes (dual-accept), and a checkpoint whose
  `authorization_receipt` is `OUTCOME APPROVED` validates, including the
  v1-upgrade path carrying the legacy receipt.
- AC-003: Garbage/case-mangled authorization values are rejected by both
  validators, and the template/validator/schema convergence pins assert
  the new exact literals.
- AC-004: The generated auto-sync PR body (build_sync_pr_body) passes the
  real validator, and the machine-gate flag names are unchanged.
- AC-005: Live contracts/docs use `commit approved` as the admission
  phrase with legacy-acceptance notes where machine validation is
  described; specs/** narrative and DR-004/005/006 are untouched; the
  grep sweep over live paths shows only legacy-acceptance wording,
  dual-accept machinery/tests, or untouched historical files.
- AC-006: Full test suite and repository validators pass on the exact
  working head; mypy-strict stays clean for
  validate_delivery_checkpoint.py and ruff stays clean per repo config.

## NFR assessment

- NFR-001 | Area: compatibility | Target: every persisted legacy receipt and pre-migration PR-body shape remains machine-valid; zero re-authorization forced on in-flight tasks | Validation: dual-accept tests for both validators, v1-upgrade legacy test, schema enum test | Evidence: tests/test_change_contract.py, tests/test_delivery_checkpoint_state_machine.py, tests/test_delivery_contract_convergence.py green in full-suite run | Status: PASS
- NFR-002 | Area: security | Target: fail-closed admission preserved — only the two exact receipt values authorize; garbage/case variants rejected; machine-gate flag names and gate order byte-identical | Validation: garbage-phrase rejection tests, flag-name pins, full validator suite | Evidence: new rejection cases green; grep sweep confirms flags untouched | Status: PASS
- NFR-003 | Area: maintainability | Target: one atomic, mutually consistent change set; single source-of-truth constants per validator; convergence test pins validator/schema/template literals | Validation: convergence tests, py_compile, mypy-strict, ruff | Evidence: convergence tests and static checks green in the recorded battery | Status: PASS
- NFR-004 | Area: auditability | Target: the migration decision and dual-accept rule are recorded in the spec triplet and in the live contracts with dated owner decision references | Validation: docs review, validate_contracts link check | Evidence: validate_contracts.py green (no broken references); decision recorded in spec and JOURNAL per workspace convention | Status: PASS

## Runtime feedback

No runtime contour is touched; there is nothing to probe post-merge beyond
required CI. The one operational risk is a task admitted mid-migration
presenting the legacy phrase — covered by dual-accept, not by re-approval.
If a future amendment narrows the accepted set again, it must repeat this
atomic pattern: validators, schema, template, tests and live contracts in
one merge, because CI checks out the merged state.
