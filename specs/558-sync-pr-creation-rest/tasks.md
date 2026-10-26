# Tasks — 558 Sync workflow: PR creation on REST

- Specification: `specs/558-sync-pr-creation-rest/spec.md`
- Issue: #558
- Status: DELIVERED

## Delivery tasks

- [x] TASK-001: Replace the GraphQL-backed CLI create path in `.github/workflows/sync-merged-tasks.yml` with `gh api -X POST "repos/${GH_REPO}/pulls"` (head/base/title/body, `--jq '.number'`), keeping the reuse PATCH path unchanged. (AC-001)
- [x] TASK-002: Extend `tests/test_sync_tasks_md_flow.py`: pin the REST create form, forbid the CLI create path; preserve the RF-014 reuse pins. (AC-001, AC-002)
- [x] TASK-003: Verify locally (flow test, full suite, workflow policy validator) and dogfood the Change Contract validators against the PR body. (AC-003)
- [ ] TASK-004: Live confirmation — the first sync run with a tasks.md delta creates the auto-sync PR via REST; record the run on issue #558. (AC-001, runtime feedback)

## Requirements traceability

- AC-001 | Task: TASK-001,TASK-004 | Evidence: workflow diff shows REST POST create with no CLI create occurrence; structural pin in `tests/test_sync_tasks_md_flow.py`; live run recorded on #558 | Coverage: COVERED
- AC-002 | Task: TASK-002 | Evidence: `tests/test_sync_tasks_md_flow.py` assertions (REST create present, CLI create absent, RF-014 PATCH pins preserved) | Coverage: COVERED
- AC-003 | Task: TASK-003 | Evidence: full suite green; `scripts/quality/validate_workflow_policy.py` valid | Coverage: COVERED

## Completion gate

- Merge is admitted only when: exact declared-files Change Contract passes, Repository validation (SDD) passes, quality-integration is green on the exact PR head, and issue #558 records the live failure evidence (run 40281552508).
- Post-merge: flip the two freshness checkboxes above; TASK-004 closes with the first live REST-create sync run recorded on #558 (the flip of this very file on merge is itself a live REST-create exercise).

## Definition of Done

- [x] Issue/spec/plan/tasks current (issue #558 records the live failure; this SDD dir is the linked delivery record)
- [x] Exact changed-file scope verified (workflow + flow test + `specs/558-sync-pr-creation-rest/**`; PR Change Contract declared-files match; no protected surfaces)
- [x] Required tests and evidence complete (TEST-001..003 green locally)
- [ ] Required CI green (Repository validation + quality-integration on the exact PR head)
- [ ] Exact-green-head merge complete (merge commit evidence recorded on #558)
- [ ] Deployment state resolved — NOT REQUIRED (CI-only; no runtime deploy contour)
- [ ] Runtime acceptance resolved — TASK-004 rides the next natural sync run with a delta (evidence on #558)
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — Risk profile NOT REQUIRED (plan.md)
- [x] Waivers resolved or current — none
