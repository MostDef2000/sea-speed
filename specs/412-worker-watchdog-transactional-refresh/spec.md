# Spec: Transactional watchdog refresh in the Ubuntu worker exact updater

- Issue: #412
- Specification: specs/412-worker-watchdog-transactional-refresh/spec.md

## Product outcome

The Ubuntu worker exact updater (`deploy/worker/ubuntu/update-exact.sh`) refreshes
the camera1-h264 freshness watchdog copy during activation (added in #389), but
the step is not transactional: it installs the watchdog script, unit and timer,
then unconditionally runs `systemctl enable --now
sea-speed-camera1-h264-freshness.timer`. Every deploy therefore force-flips the
operator's timer enablement, and any activation failure after the refresh step
leaves the new watchdog artifacts installed while the deploy transaction rolls
back only the three deploy-managed units — a fresh host can even end up with a
freshly enabled timer after a failed deploy.

This change makes the refresh transactional with the same discipline the script
already applies to the deploy-managed units: the pre-refresh watchdog state is
captured before the first mutation, any activation abort after the refresh
started restores that captured state exactly, and the success path reapplies the
captured timer enablement instead of forcing it.

## User scenarios

- US-1: The operator keeps the watchdog timer enabled and active; a deploy
  refreshes the installed watchdog copy and the timer stays enabled and active.
- US-2: The operator disabled the watchdog timer deliberately; a deploy
  refreshes the copy and the timer stays disabled — the deploy never re-enables it.
- US-3: An activation abort after the refresh step started (control-service
  restart failure, worker state gate, runtime gates, verification failures)
  restores the previous watchdog script/unit/timer bytes — or removes them when
  they did not exist before — plus daemon-reload, and restores the captured
  timer enablement/active state; the abort evidence reports whether the
  watchdog pre-state was restored.
- US-4: A fresh host without watchdog artifacts: a failed deploy never leaves a
  freshly enabled timer; a successful deploy installs the artifacts but does
  not force-enable the timer (enablement stays an operator decision).

## Requirements

- R-1: Before the first watchdog mutation (the install of the refreshed script),
  the updater must capture the pre-refresh state: script, unit and timer file
  presence; byte-exact backups of existing files under the root-only updater
  directory; and timer enabled/active state via `systemctl is-enabled`/
  `systemctl is-active`, stored in dedicated variables.
- R-2: Any activation abort after the refresh block started — every
  `abort_activation` call site, including the `restore_previous()` path — must
  restore the watchdog artifacts to the captured pre-state (previous bytes via
  install, or removal when the file did not exist before) plus
  `systemctl daemon-reload`, and restore timer enablement/active state
  (enabled+active → enable and start; disabled → disable; enabled-inactive →
  enable without `--now`; absent → tolerant stop/disable and removal of the
  installed timer). A watchdog restoration failure must be reported loudly
  without blocking the managed-units restoration.
- R-3: The unconditional `systemctl enable --now
  sea-speed-camera1-h264-freshness.timer` must be removed. The success path
  reapplies the captured timer pre-state; a timer that did not exist before the
  deploy is left installed but not enabled.
- R-4: The EXIT-trap cleanup must cover the watchdog backup files; the watchdog
  restore function must be defined before `abort_activation`; the capture must
  precede every watchdog install; the refresh block's source checks, install
  commands (0755 script, 0644 unit/timer) and daemon-reload remain; no change to
  the three deploy-managed units, `rollback-exact.sh`, install-systemd.sh,
  install-manual.sh, workflows, the watchdog logic itself or any other contour.

## Acceptance criteria

- AC-001: The updater no longer contains the unconditional
  `systemctl enable --now` timer line; the timer enable is gated on the captured
  pre-state. Pins fail RED against the base script.
- AC-002: Pre-state capture markers (three backup mktemp variables, five
  presence/enablement/active flags, capture-failure abort reason and the
  `watchdog_prestate_captured=true` flag) are present, and a structural check
  proves the capture flag precedes the first watchdog install line.
- AC-003: `restore_previous_watchdog()` exists, restores previous bytes or
  removes absent artifacts and reapplies the captured timer state; it is defined
  before `abort_activation`, which calls it before the managed-units restore and
  reports `watchdog_prestate_restored=<bool>` on both `ACTIVATION_ABORTED` and
  `ACTIVE_MARKER_UNCHANGED` evidence lines.
- AC-004: `cleanup()` covers the three watchdog backup files; `bash -n` is
  green; all pre-existing updater and rollback test pins stay green.
- AC-005: A disabled timer stays disabled across a successful deploy: the
  reapply derives from the captured state (explicit enable/disable plus
  start/stop branches), the absent-timer branch contains no enable, and a
  `WATCHDOG_TIMER_REAPPLIED timer_present=...` evidence line precedes the
  control-service restart.

## Runtime feedback

- RF-001: Operator actions expected: 0; the deploy transaction preserves the
  operator's watchdog timer state autonomously.
- RF-002: Observability: `WATCHDOG_TIMER_REAPPLIED timer_present=...` on the
  success path, `RESTORED watchdog_script_present=...` on abort, and
  `watchdog_prestate_restored=<bool>` on both abort evidence lines.

## NFR assessment

- NFR-001 | Area: reliability | Target: any activation abort after the refresh started restores the captured watchdog pre-state (bytes or absence) and timer state | Validation: marker + structural tests demonstrated RED against the base script and GREEN after the change | Evidence: UbuntuWorkerWatchdogTransactionalRefreshTests | Status: PASS
- NFR-002 | Area: operability | Target: operator timer enablement is never force-flipped by a deploy | Validation: unconditional-enable absence pin plus gated reapply and absent-branch pins | Evidence: test_unconditional_timer_enable_is_removed, test_timer_reapply_is_gated_on_captured_prestate, test_fresh_host_timer_stays_not_enabled | Status: PASS
- NFR-003 | Area: security | Target: no credentials and no new exposure; watchdog backups stay in the root-only updater directory (0700) with 0600 modes | Validation: source review of backup creation and cleanup | Evidence: PR exact diff (update-exact.sh only) | Status: PASS
- NFR-004 | Area: reversibility | Target: the watchdog refresh is covered by the activation transaction like the deploy-managed units | Validation: abort-path restore pins; capture-before-mutation structural ordering | Evidence: test_abort_paths_restore_watchdog_prestate, test_prestate_capture_precedes_first_watchdog_mutation | Status: PASS
- NFR-005 | Area: maintainability | Target: single-script behaviour change following the existing restore/abort patterns, revertible without state migration | Validation: diff scope review against the admitted scope; existing test pins untouched except the stale unconditional-enable pin | Evidence: PR exact changed-file list | Status: PASS
