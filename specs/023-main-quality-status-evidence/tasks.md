# Delivery Tasks: Main Quality status evidence

- Specification: specs/023-main-quality-status-evidence/spec.md
- Plan: specs/023-main-quality-status-evidence/plan.md
- Issue: #216
- Status: Implementing

## Delivery tasks

- T-001 [P0] Create standalone completed-Quality `workflow_run` publisher with main-push guard and exact-SHA binding. IMPLEMENTED ON TASK BRANCH.
- T-002 [P0] Restrict publisher to `statuses: write` with no checkout, repository-code execution, artifacts, caches or deployment credentials. IMPLEMENTED ON TASK BRANCH.
- T-003 [P0] Publish fixed context plus source run ID, run number, conclusion and URL; map non-success conclusions fail-closed. IMPLEMENTED ON TASK BRANCH.
- T-004 [P0] Extend Quality status tests with workflow trigger, permission, exact-SHA, identity and mapping assertions. IMPLEMENTED ON TASK BRANCH.
- T-005 [P0] Reconcile SDD for control-plane-only impact and zero runtime deployment. IMPLEMENTED ON TASK BRANCH.
- T-006 [P0] Verify exact five-path diff against authorization base and open canonical PR with machine-valid Change Contract. PENDING.
- T-007 [P0] Reach exact-head PR Validation and aggregate Quality; remediate only in-scope deterministic defects. PENDING.
- T-008 [P0] Re-check base/head/scope/reviews and merge only exact green head. PENDING.
- T-009 [P0] Verify resulting exact main receives `sea-speed/quality-push-main` from its own push/main Quality and read it through Connector combined-status lookup without manual run ID. PENDING.
- T-010 [P0] Persist completion evidence to Issue #216 and close the Issue when all source and end-to-end gates pass. PENDING.

## Requirements traceability

- AC-001 | Task: T-001,T-004 | Evidence: workflow trigger regression | Coverage: COVERED
- AC-002 | Task: T-001,T-004 | Evidence: source event/branch guard regression | Coverage: COVERED
- AC-003 | Task: T-001,T-004 | Evidence: exact lowercase source-SHA binding regression | Coverage: COVERED
- AC-004 | Task: T-002,T-004 | Evidence: permission/no-checkout/no-actions regression plus workflow policy | Coverage: COVERED
- AC-005 | Task: T-003,T-004 | Evidence: fixed context and source run identity regression | Coverage: COVERED
- AC-006 | Task: T-003,T-004 | Evidence: success/non-success mapping regression | Coverage: COVERED
- AC-007 | Task: T-006,T-007,T-008 | Evidence: exact diff, PR Validation, aggregate Quality and expected-head merge | Coverage: COVERED
- AC-008 | Task: T-009,T-010 | Evidence: Connector combined-status result on merged exact main with source run identity | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current — Issue #216 and SDD define the approved control-plane Outcome.
- [ ] Exact changed-file scope verified — final branch must contain exactly the five authorized paths.
- [ ] Required tests and evidence complete — source tests are authored; CI and merged-main end-to-end evidence remain.
- [ ] Required CI green — exact-head PR Validation and aggregate Quality remain pending.
- [ ] Exact-green-head merge complete — task branch is not yet merged.
- [x] Deployment state resolved — no VPS or Ubuntu runtime deployment is required by this control-plane Outcome.
- [ ] Runtime acceptance resolved — no runtime mutation applies; completion requires merged-main Connector evidence instead.
- [x] Deferred work recorded — Connector implementation changes and existing Quality/deployment workflow redesign are explicitly out of scope.
- [x] Risks resolved or explicitly accepted — full risk profile is not required; least-privilege and fail-closed behavior are directly tested.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`COMPLETE` is forbidden until the exact five-path diff passes exact-head PR Validation and aggregate Quality, merges with expected-head protection, and the resulting exact main SHA self-reports successful push/main Quality through `sea-speed/quality-push-main` that Delivery Orchestrator reads via Connector without operator-supplied run ID.
