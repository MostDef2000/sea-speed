# Tasks: Transactional watchdog refresh in the Ubuntu worker exact updater

- Specification: specs/412-worker-watchdog-transactional-refresh/spec.md

## Delivery tasks

- T-412-001: Capture the watchdog pre-state in `update-exact.sh` before the
  first watchdog mutation: script/unit/timer presence flags, byte-exact backups
  via `mktemp` under the updater directory, timer enabled/active state, and the
  `watchdog_prestate_captured` gate with capture-failure aborts
- T-412-002: Add `restore_previous_watchdog()` restoring previous bytes or
  removing absent artifacts plus daemon-reload and captured timer
  enablement/active state, defined before `abort_activation()`, and hook it into
  `abort_activation()` with `watchdog_prestate_restored=<bool>` evidence on both
  abort lines
- T-412-003: Replace the unconditional `systemctl enable --now
  sea-speed-camera1-h264-freshness.timer` with a reapply of the captured timer
  pre-state (a previously absent timer stays installed but not enabled) and add
  the `WATCHDOG_TIMER_REAPPLIED` evidence line
- T-412-004: Extend `cleanup()` to remove the three watchdog backup files via
  the existing EXIT-trap pattern
- T-412-005: Add the RED-anchored `UbuntuWorkerWatchdogTransactionalRefreshTests`
  class to `tests/test_ubuntu_worker_exact_updater.py` and update the stale
  unconditional-enable pin to the gated reapply contract; leave every other
  pre-existing pin untouched
- T-412-006: Run the verification battery (bash -n, ruff, targeted unittest,
  full unittest discover suite, SDD validator, RED stash check with sha256
  verification) and leave the changes uncommitted for orchestrator admission

## Completion gate

- [x] T-412-001
- [x] T-412-002
- [x] T-412-003
- [x] T-412-004
- [x] T-412-005
- [x] T-412-006

## Requirements traceability

- AC-001 | Task: T-412-003,T-412-005 | Evidence: assertNotIn pins for both unconditional enable forms plus gated reapply markers, demonstrated RED against the base script | Coverage: COVERED
- AC-002 | Task: T-412-001,T-412-005 | Evidence: test_prestate_capture_precedes_first_watchdog_mutation (markers plus structural index ordering) | Coverage: COVERED
- AC-003 | Task: T-412-002,T-412-005 | Evidence: test_restore_previous_watchdog_restores_captured_prestate and test_abort_paths_restore_watchdog_prestate | Coverage: COVERED
- AC-004 | Task: T-412-004,T-412-006 | Evidence: test_cleanup_covers_watchdog_backups, bash -n green, all pre-existing updater/rollback pins green | Coverage: COVERED
- AC-005 | Task: T-412-003,T-412-005 | Evidence: test_timer_reapply_is_gated_on_captured_prestate and test_fresh_host_timer_stays_not_enabled (absent branch contains no enable; reapply evidence precedes the control-service restart) | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [x] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main (7968f456)
- [x] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main (7968f456)
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned (timer state preserved across a live deploy)
- [ ] Deferred work recorded — none in this unit
- [ ] Risks resolved or explicitly accepted — RISK-001 mitigated; live-host behaviour verified post-deploy
- [ ] Waivers resolved or current — none
