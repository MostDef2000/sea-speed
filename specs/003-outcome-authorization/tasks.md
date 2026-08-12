# Tasks: Outcome Authorization

- Specification: specs/003-outcome-authorization/spec.md
- Plan: specs/003-outcome-authorization/plan.md
- Issue: #107

## Delivery tasks

- [x] T001 Record Outcome Authorization product semantics, protected escalation boundaries and production separation in the canonical governance contracts and `AGENTS.md`.
- [x] T002 Extend the PR Change Contract template with source-authorization, boundary-change and production-safety-envelope declarations.
- [x] T003 Extend `scripts/ci/validate_change_contract.py` to validate the new authorization fields without weakening exact changed-file or production-impact checks.
- [x] T004 Add focused tests for Outcome Authorization, legacy compatibility, protected-boundary rejection and production-envelope applicability.
- [x] T005 Add this SDD specification/plan/task set and link the transition PR to it.
- [ ] T006 Verify exact 11-file branch diff, complete-file integrity, no secrets/runtime artifacts and required CI.
- [ ] T007 Obtain the one final legacy `MERGE APPROVED` for this transition task after exact-head CI evidence, then merge without runtime deployment.
- [ ] T008 Record completion in Issue #107 and use Outcome Authorization as the preferred model for subsequent tasks.

## Completion gate

- [x] Requirements are covered by tasks.
- [x] Spec, plan and tasks match the intended implementation.
- [ ] Exact changed-file scope is the approved 11 files.
- [ ] Required CI is green for the exact PR head.
- [ ] This transition task has the required legacy post-CI merge approval.
- [ ] VPS deployment is NOT REQUIRED and Windows worker installation is NOT REQUIRED.
- [ ] Issue #107 records the merged activation of Outcome Authorization.
