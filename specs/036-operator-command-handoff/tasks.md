# Tasks: Operator Command Handoff Format

- Feature: 036-operator-command-handoff
- Specification: specs/036-operator-command-handoff/spec.md
- Plan: specs/036-operator-command-handoff/plan.md
- Issue: #257
- Status: Source implementation

## Delivery tasks

- [x] T001 Add operator terminal command handoff format section to `AGENTS.md`.
- [x] T002 Add §13.1 operator terminal command handoff format to `contracts/SEA_SPEED_DELIVERY_POLICY.md`.
- [x] T003 Author SDD artifacts under `specs/036-operator-command-handoff/`.
- [ ] T004 Validate locally (SDD/repo/contracts + full test suite) and open bounded PR.
- [ ] T005 Require Repository validation + quality-integration on exact head; expected-head merge.

## Requirements traceability

- AC-001 | Task: T001 | Evidence: AGENTS.md handoff format section present with six rules | Coverage: COVERED
- AC-002 | Task: T002 | Evidence: SEA_SPEED_DELIVERY_POLICY.md §13.1 present with same rule set | Coverage: COVERED
- AC-003 | Task: T004 | Evidence: validate_contracts.py + validate_repo.py PASS output | Coverage: COVERED
- AC-004 | Task: T005 | Evidence: required CI success runs and merged PR SHA | Coverage: COVERED
- AC-005 | Task: T004, T005 | Evidence: git diff --name-only limited to authorized paths | Coverage: COVERED

## Completion gate

- [x] Exact scope verified against Issue #257 authorization
- [x] SDD artifacts current
- [ ] Required CI green on exact head
- [ ] Expected-head merge complete

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [x] Deployment state resolved (NOT APPLICABLE — CONTROL_PLANE)
- [x] Runtime acceptance resolved (NOT APPLICABLE — CONTROL_PLANE)
- [x] Deferred work recorded (none)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (none required)
