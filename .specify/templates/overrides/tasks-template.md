# Tasks: [FEATURE NAME]

- Specification: specs/[NNN-feature-slug]/spec.md
- Plan: specs/[NNN-feature-slug]/plan.md
- Issue: #[ISSUE]

## Delivery tasks

- [ ] T001 [specific bounded task]
- [ ] T002 [specific bounded task]
- [ ] T003 [validation/evidence task]

## Requirements traceability

Map every `AC-*` from the specification exactly once.

- AC-001 | Task: T001 | Evidence: TEST-001 / [test or evidence path] | Coverage: COVERED
- AC-002 | Task: T002 | Evidence: [runtime evidence] | Coverage: RUNTIME-MANUAL | Reason: [why hosted CI cannot prove it]

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [ ] Deferred work recorded
- [ ] Risks resolved or explicitly accepted
- [ ] Waivers resolved or current

## Completion gate

- [ ] Requirements are covered by tasks and traceability.
- [ ] Spec, plan and tasks match the implemented behavior.
- [ ] Required CI is green.
- [ ] Exact-green-head merge evidence is recorded in the canonical Issue.
- [ ] Applicable deployment/runtime acceptance is complete, or explicitly NOT REQUIRED.
- [ ] Runtime learning and deferred work are written back to the feature artifacts or recorded as approved follow-up.
