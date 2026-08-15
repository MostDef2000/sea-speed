# Implementation Plan: BMAD-derived delivery quality layer

- Specification: specs/014-bmad-derived-quality-layer/spec.md
- Issue: #176
- Status: Implementation

## Architecture

Extend the current SDD and Change Contract validators instead of adding another workflow engine. The quality data remains co-located with the canonical feature artifacts and PR body:

- `spec.md` owns NFR assessment;
- `plan.md` owns risk profile, risk-based test design and correct-course analysis;
- `tasks.md` owns acceptance traceability and Definition of Done;
- the PR Change Contract owns derived risk applicability and final source-quality disposition.

`validate_sdd.py` keeps repository-wide historical compatibility but applies the current delivery-quality format to the feature linked by a significant PR. `validate_change_contract.py` derives high-risk applicability from already-declared impact plus two explicit yes/no fields and validates quality verdict/waiver completeness. Both continue to run inside the existing static/contract quality domain.

## Decisions

### D-001 - Keep quality inside current SDD artifacts

- Decision: Do not introduce a separate BMAD directory, generated workflow configuration or standalone quality policy source of truth.
- Reason: Sea Speed already has canonical Issue, SDD and Change Contract layers; adding another authority would create drift.
- Alternatives rejected: BMAD agent/workflow engine and per-change standalone QA documents.

### D-002 - Enforce quality only for active linked significant work

- Decision: Repository validation keeps historical SDD readable; PR linkage validation requires current quality sections for the active significant feature.
- Reason: Avoid mass rewriting audit history while preventing stale quality structure from entering new significant work.
- Alternatives rejected: Mandatory retrofit of every historical feature directory.

### D-003 - Derive high-risk profile applicability at PR admission

- Decision: Security, schema, destructive/data migration, `MIXED` runtime or explicit other-high-risk trigger requires `Risk profile: REQUIRED`.
- Reason: Risk-profile applicability should be objective and machine checked instead of discretionary prose.
- Alternatives rejected: Always require full risk tables or never require them.

### D-004 - Waiver is quality disposition, never authorization

- Decision: `WAIVED` requires complete durable metadata but cannot bypass any existing hard gate.
- Reason: Quality concerns can be consciously accepted without collapsing delivery or production controls.
- Alternatives rejected: Treat waiver as an override token.

## Affected contours

- Repository: governance, SDD templates, PR template, SDD/Change Contract validators and tests only.
- VPS: NONE.
- Ubuntu worker/relay: NONE.
- Windows worker/AI: NONE.
- Public interfaces: NONE.

## Validation

- Static/CI: Python compile, validator unit tests, delivery-quality contract test, repository validation, PR Validation and Quality integration.
- Integration: significant-PR linkage exercises SDD quality checks through the same event contract used by aggregate CI.
- Runtime acceptance: NOT REQUIRED; CONTROL_PLANE only.

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001, AC-012 | Level: unit | Priority: P1 | Evidence: tests/test_validate_sdd.py significant-link and historical-compatibility cases
- TEST-002 | Covers: AC-002, AC-003, AC-008, AC-009 | Level: unit | Priority: P1 | Evidence: tests/test_change_contract.py risk and quality-verdict cases
- TEST-003 | Covers: AC-004, AC-005, AC-006, AC-007, AC-010 | Level: unit | Priority: P1 | Evidence: tests/test_validate_sdd.py risk/NFR/traceability and parser validation
- TEST-004 | Covers: AC-011, AC-013 | Level: integration | Priority: P1 | Evidence: tests/test_delivery_quality_layer.py template/governance compatibility assertions
- TEST-005 | Covers: AC-014 | Level: end-to-end | Priority: P0 | Evidence: exact-head PR Validation + Quality integration and post-merge push/main workflow evidence on Issue #176

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Rollout and rollback

- Rollout: merge exact green Stage C head into `main`; no production workflow or runtime mutation.
- Rollback: revert the Stage C merge if the quality validators create unintended repository admission regressions; production rollback is NOT REQUIRED.

## Runtime feedback

- Actual architecture after acceptance: pending exact-head and post-merge CI evidence on Issue #176.
- Differences from plan: NONE YET
- Deferred cleanup: NONE YET
