# Feature Specification: Operator Command Handoff Format

- Feature: 036-operator-command-handoff
- Issue: #257
- Status: Source implementation

## Product outcome

Operator-facing terminal command handoffs (ONE_COMMAND_FALLBACK and bounded read-only host commands) survive SSH-terminal pasting without corruption. The format rules are canonical in `AGENTS.md` and `contracts/SEA_SPEED_DELIVERY_POLICY.md`, so every future handoff is paste-safe by construction.

## User scenarios

1. An operator receives a bootstrap command block, pastes it into a root SSH session, and the block executes top-to-bottom without syntax errors caused by wrapping or placeholders.
2. A 40-character SHA is used in a command without the line exceeding terminal width, because it is assigned to a short variable first.
3. A review of any handed-off block finds no `<PLACEHOLDER>` tokens, no comment lines inside the block, and no dependency on variables from earlier messages.

## Requirements

- FR-001: Handed-off blocks MUST contain one command per line with every line at most 72 characters.
- FR-002: Long literals (40-character SHAs, URLs, paths) MUST be assigned to a short variable on their own line inside the same block.
- FR-003: Placeholders such as `<DEPLOY_USER>` MUST NOT appear inside paste blocks; real values only.
- FR-004: Comment lines MUST NOT appear inside paste blocks; explanations belong outside.
- FR-005: A paste block MUST execute top-to-bottom exactly as pasted without depending on variables from earlier messages or blocks.
- FR-006: Backslash continuations MUST NOT be used inside paste blocks; several short lines are preferred over one long line.
- FR-007: The rule MUST be recorded in both `AGENTS.md` (adapter) and `contracts/SEA_SPEED_DELIVERY_POLICY.md` (canonical policy).

## Acceptance criteria

- AC-001: `AGENTS.md` contains the operator terminal command handoff format section with all six rules.
- AC-002: `contracts/SEA_SPEED_DELIVERY_POLICY.md` contains the same rule set as §13.1.
- AC-003: `validate_contracts.py` and `validate_repo.py` PASS on the PR head.
- AC-004: Required CI (Repository validation + quality-integration) success on exact head; expected-head merge completes.
- AC-005: No runtime files, workflows or scripts change; diff is exactly the two authorized paths plus SDD artifacts.

## NFR assessment

- NFR-001 | Area: OPERABILITY | Target: zero corrupted handoff commands during operator execution | Validation: this task's own VPS bootstrap handoff incident reviewed against the rule | Evidence: 2026-08-22 #255 bootstrap handoff failures (unset `$SHA`, `<DEPLOY_USER>` placeholder, wrapped long line) | Status: PASS
- NFR-002 | Area: SECURITY | Target: no new authority or credential exposure introduced by the rule | Validation: rule text review; protected values remain outside chat/Git | Evidence: contracts/SEA_SPEED_DELIVERY_POLICY.md §13.1 | Status: PASS

## Runtime feedback

- Runtime acceptance: NOT APPLICABLE — CONTROL_PLANE documentation rule; no production deployment.
- Accepted production behavior: unchanged; the rule constrains assistant-to-operator communication only.
- Regressions/learning: learned from Issue #255 ONE_COMMAND_FALLBACK handoff where multi-line blocks broke on SSH paste.
- Follow-up work: none.
