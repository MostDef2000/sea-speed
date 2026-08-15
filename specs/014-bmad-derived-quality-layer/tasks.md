# Tasks: BMAD-derived delivery quality layer

- Specification: specs/014-bmad-derived-quality-layer/spec.md
- Plan: specs/014-bmad-derived-quality-layer/plan.md
- Issue: #176

## Delivery tasks

- [x] T001 Extend governance, delivery policy, task runtime, release readiness and review lens with bounded delivery-quality semantics while retaining Stage B authorization/orchestrator/runtime boundaries.
- [x] T002 Extend SDD constitution, README and templates with NFR, risk/test design, correct-course, traceability and Definition-of-Done artifacts.
- [x] T003 Extend the PR Change Contract and validator with derived risk-profile applicability and `PASS/CONCERNS/FAIL/WAIVED` disposition plus complete waiver validation.
- [x] T004 Extend SDD validation so historical directories remain valid but linked significant work requires current quality sections.
- [x] T005 Add deterministic validator and contract tests, including high-risk triggers, NFR fail-closed behavior, traceability and waiver behavior.
- [x] T006 Preserve CONTROL_PLANE/no-production semantics and exclude Issue #170/specs/011 plus PR #158/Issue #157.
- [ ] T007 Record exact final-head PR/aggregate CI, expected-head merge and post-merge push/main evidence on Issue #176.

## Requirements traceability

- AC-001 | Task: T004 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T003 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T003 | Evidence: TEST-002 | Coverage: COVERED
- AC-004 | Task: T004 | Evidence: TEST-003 | Coverage: COVERED
- AC-005 | Task: T004 | Evidence: TEST-003 | Coverage: COVERED
- AC-006 | Task: T004 | Evidence: TEST-003 | Coverage: COVERED
- AC-007 | Task: T004 | Evidence: TEST-003 | Coverage: COVERED
- AC-008 | Task: T003 | Evidence: TEST-002 | Coverage: COVERED
- AC-009 | Task: T003 | Evidence: TEST-002 and hard-gate assertions | Coverage: COVERED
- AC-010 | Task: T004 | Evidence: TEST-003 | Coverage: COVERED
- AC-011 | Task: T002 | Evidence: TEST-004 | Coverage: COVERED
- AC-012 | Task: T004 | Evidence: TEST-001 | Coverage: COVERED
- AC-013 | Task: T001 | Evidence: TEST-004 plus existing Stage B contract tests | Coverage: COVERED
- AC-014 | Task: T007 | Evidence: TEST-005 / GitHub workflow and merge evidence on Issue #176 | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [x] Deployment state resolved
- [x] Runtime acceptance resolved
- [x] Deferred work recorded
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current

Source-controlled checkboxes that depend on merge/post-merge state are intentionally completed by durable Issue #176 terminal evidence rather than a bookkeeping commit after the exact green head.

## Completion gate

- [x] Requirements are covered by tasks and traceability.
- [x] Spec, plan and tasks match the implemented behavior.
- [ ] Required CI is green on the exact final head.
- [ ] Exact-green-head merge evidence is recorded in the canonical Issue.
- [x] Applicable deployment/runtime acceptance is explicitly NOT REQUIRED.
- [x] Runtime learning and deferred work are either NOT REQUIRED or recorded as follow-up.
