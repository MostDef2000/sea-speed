# Tasks: Refresh stale camera1-h264 watchdog copy during Ubuntu deploy transaction

- Specification: specs/389-watchdog-deploy-refresh/spec.md

## Delivery tasks

- T-389-001: Add watchdog script copy step to `update-exact.sh` activation
- T-389-002: Add idempotent unit + timer reinstall to `update-exact.sh`
- T-389-003: Guard each step with `abort_activation` (fail-closed)
- T-389-004: Confirm scope isolation (no logic/transcode/VPS/other changes)
- T-389-005: Add `test_watchdog_copy_is_refreshed_from_release_source` marker test
- T-389-006: Open PR, reach exact-green-head, merge, autonomous deploy, verify

## Completion gate

- [x] T-389-001
- [x] T-389-002
- [x] T-389-003
- [x] T-389-004
- [x] T-389-005
- [ ] T-389-006

## Requirements traceability

- AC-001 | Task: T-389-001,T-389-006 | Evidence: update-exact.sh watchdog copy step + post-deploy file compare | Coverage: COVERED
- AC-002 | Task: T-389-006 | Evidence: post-deploy systemctl status of freshness.service | Coverage: RUNTIME-MANUAL | Reason: post-deploy verification requires target host access
- AC-003 | Task: T-389-002 | Evidence: timer enable in update-exact.sh | Coverage: COVERED
- AC-004 | Task: T-389-003 | Evidence: abort_activation guards in update-exact.sh | Coverage: COVERED
- AC-005 | Task: T-389-004 | Evidence: diff scope review | Coverage: COVERED

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
