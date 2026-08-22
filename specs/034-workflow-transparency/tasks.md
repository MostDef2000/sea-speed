# Tasks 034 — Workflow Transparency

- Specification: specs/034-workflow-transparency/spec.md
- Plan: specs/034-workflow-transparency/plan.md
- Issue: #254
- Status: Active

## Delivery tasks

- [x] T001 Create composite action `.github/actions/verify-exact-release/action.yml`
- [x] T002 Refactor `deploy-vps.yml` and `deploy-ubuntu-worker.yml` to use shared action (-60 lines each)
- [x] T003 Add `docs/WORKFLOW_OVERVIEW.md` with 5-step diagram
- [x] T004 Disable legacy HLS workflows via API (agent-hls-*, repair-speed-stability)
- [x] T005 Add SDD specs/034 with required markers
- [x] T006 Update PR #253 Change Contract to reference Issue #254 and specs/034
- [x] T007 Validate SDD, workflow-policy, and tests

## Requirements traceability

- AC-001 | Task: T001, T002 | Evidence: `scripts/quality/validate_workflow_policy.py` PASS | Coverage: COVERED
- AC-002 | Task: T002 | Evidence: `python -m unittest discover` 428 PASS | Coverage: COVERED
- AC-003 | Task: T001, T002 | Evidence: PR Validation + quality-integration success | Coverage: COVERED
- AC-004 | Task: T003, T004 | Evidence: Actions shows 6 active + 3 disabled | Coverage: COVERED
- AC-005 | Task: T002 | Evidence: deploy workflows contain verify before evaluate | Coverage: COVERED

## Completion gate

- [x] Exact scope verified
- [x] SDD current
- [x] Tests PASS

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [x] Required CI green
- [x] Exact-green-head merge complete
- [x] Deployment state resolved
- [x] Runtime acceptance resolved
- [x] Deferred work recorded
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current
