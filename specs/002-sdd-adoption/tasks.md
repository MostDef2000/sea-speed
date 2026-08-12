# Tasks: Spec Kit SDD Adoption

- Specification: specs/002-sdd-adoption/spec.md
- Plan: specs/002-sdd-adoption/plan.md
- Issue: #99

## Delivery tasks

- [x] T001 Create canonical Issue #99 and record the approved SDD adoption scope.
- [x] T002 Add Sea Speed Spec Kit constitution and project-local spec/plan/tasks template overrides.
- [x] T003 Add `specs/README.md` with source-of-truth hierarchy and workflow.
- [x] T004 Retrofit Issue #87 into `specs/001-camera-live-pipeline/` with accepted production architecture and learning.
- [x] T005 Self-document SDD adoption under `specs/002-sdd-adoption/`.
- [x] T006 Add `scripts/ci/validate_sdd.py` and focused unit tests.
- [x] T007 Update agent/governance/PR/CI entry points to require linked SDD artifacts for significant work.
- [x] T008 Obtain green required CI for the implementation head; final-head CI remains required after this bookkeeping update.
- [ ] T009 Obtain separate merge approval for the exact PR head.
- [ ] T010 Merge to main and record repository completion evidence; no deployment follows.

## Completion gate

- [x] Required SDD baseline files exist.
- [x] Camera Live production learning is captured.
- [x] Significant PR linkage is machine-validated.
- [x] Spec-only work remains lightweight.
- [x] PR Validation and Quality integration gate succeeded on the implementation head; final-head rerun is required before merge approval.
- [ ] Separate merge approval is present.
- [ ] Main contains the merged SDD baseline.
- [x] VPS deployment and Windows worker update are NOT REQUIRED.
