# Implementation Plan: Operator Command Handoff Format

- Feature: 036-operator-command-handoff
- Specification: specs/036-operator-command-handoff/spec.md
- Issue: #257
- Status: Source implementation

## Architecture

Two documentation touch points, no executable code:

1. `AGENTS.md` — the concise agent adapter gains a subsection under the Tool Routing Allowlist area defining the six paste-safety rules for operator command handoffs.
2. `contracts/SEA_SPEED_DELIVERY_POLICY.md` — canonical policy gains §13.1 with the same rule set, anchored to VPS execution (§13) where ONE_COMMAND_FALLBACK applies.

## Decisions

- Record the rule in both the adapter and the canonical policy: agents read `AGENTS.md` first; governance arbitration reads contracts. Duplication is intentional and small.
- Six rules only, all mechanically checkable by review: line length, variable assignment for long literals, real values, no in-block comments, self-contained block, no backslash continuations.
- No validator script in this scope: the rule governs chat output, not repository bytes; a CI check would validate nothing durable.

## Affected contours

- VPS deployment: NOT REQUIRED
- Ubuntu worker/relay update: NOT REQUIRED
- Production safety envelope: NOT REQUIRED

## Validation

- `python3 scripts/ci/validate_sdd.py`, `validate_repo.py`, `validate_contracts.py`
- `python3 -m unittest discover -s tests -p test_*.py` — full suite stays green
- Required CI on exact PR head; expected-head merge

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-036-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: grep of AGENTS.md shows handoff format section with six rules
- TEST-036-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: grep of SEA_SPEED_DELIVERY_POLICY.md §13.1 shows same rule set
- TEST-036-003 | Covers: AC-003, AC-004 | Level: integration | Priority: P0 | Evidence: validators PASS locally and required CI success on exact head
- TEST-036-004 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: git diff --name-only limited to authorized paths

## Correct-course check

- Trigger: NONE
- Issue impact: New Issue #257 records the outcome.
- Specification impact: New specs/036 specification authored.
- Plan impact: Documentation-only change plan.
- Tasks impact: Tasks 036 cover both files plus SDD.
- Authorization impact: Fresh OUTCOME APPROVED received immediately after the six-field Scope; CONTROL_PLANE only.
- Follow-up: None.

## Runtime feedback

- Runtime acceptance: NOT APPLICABLE — CONTROL_PLANE.
- Accepted production behavior: unchanged.
- Regressions/learning: rule derived from the 2026-08-22 Issue #255 bootstrap handoff failures.
- Follow-up work: none.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: not applicable — this feature is documentation hardening, not a production-failure remediation; the incident evidence is recorded in spec NFR-001.
- Production-learning adjacent-stage findings: not applicable — Trigger is NONE; no production transaction was mutated by this task.
