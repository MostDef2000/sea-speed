# Tasks: Run production-facing CI on Python 3.14

- Specification: specs/391-python314-prod-ci/spec.md

## Delivery tasks

- T-391-001: Bump the four setup-python pins in `quality-integration.yml`
  (lines 31, 74, 94, 127) from "3.12" to "3.14"
- T-391-002: Bump the setup-python pin in `pr-validation.yml` (line 33) from
  "3.12" to "3.14"
- T-391-003: Verify scope isolation: diff is exactly the five allowed files and
  deploy-classified workflows keep their current pins
- T-391-004: Run the full local battery on CPython 3.14.4 (validators,
  py_compile, unittest with -W error::ResourceWarning, exact artifacts) and
  record outputs in the PR
- T-391-005: Open PR, reach exact-green-head CI green on 3.14, merge; record
  evidence and close out the Definition of Done

## Completion gate

- [x] T-391-001
- [x] T-391-002
- [x] T-391-003
- [x] T-391-004
- [ ] T-391-005

## Requirements traceability

- AC-001 | Task: T-391-001,T-391-002 | Evidence: grep of both workflows shows 5x "3.14", 0x "3.12"; git diff shows only the scalar changed | Coverage: COVERED
- AC-002 | Task: T-391-005 | Evidence: setup-python logs of the green exact-green-head quality-integration and pr-validation runs | Coverage: COVERED
- AC-003 | Task: T-391-005 | Evidence: green quality-integration run (behavioral suite, property/fuzz/architecture, validators, exact artifacts, quality evidence) on 3.14 | Coverage: COVERED
- AC-004 | Task: T-391-003 | Evidence: git diff contains no deploy workflow; grep confirms deploy-vps.yml:78, deploy-ubuntu-worker.yml:73, deploy-runtime-autonomous.yml:69 still "3.12" | Coverage: COVERED
- AC-005 | Task: T-391-003,T-391-005 | Evidence: git diff --stat = 5 files (2 workflows + 3 SDD artifacts) | Coverage: COVERED

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
