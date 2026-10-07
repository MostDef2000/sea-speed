# Plan: Transactional watchdog refresh in the Ubuntu worker exact updater

- Specification: specs/412-worker-watchdog-transactional-refresh/spec.md

## Architecture

Single-script change in `deploy/worker/ubuntu/update-exact.sh` that extends the
script's existing transactional patterns to the #389 watchdog refresh step:

- A capture block sits immediately before the first watchdog mutation. It
  records script/unit/timer presence, stages byte-exact backups via `mktemp`
  under the root-only updater directory (0600), and records timer
  enabled/active state with `systemctl is-enabled`/`is-active`. The
  `watchdog_prestate_captured` flag is raised only after every pre-state
  artifact is secured; capture failures abort before any watchdog mutation.
- `restore_previous_watchdog()` mirrors `restore_previous_control()`: previous
  bytes are reinstalled with production modes (0755 script, 0644 unit/timer),
  absent-before artifacts are removed, and the captured timer enablement/active
  state is reapplied with verification.
- `abort_activation()` gains a guarded hook before the managed-units restore so
  every abort path — including first-activation aborts where
  `restore_previous()` returns 1 early — restores the watchdog pre-state, and
  both abort evidence lines report `watchdog_prestate_restored=<bool>`.
- The success path replaces the unconditional `systemctl enable --now` with a
  reapply of the captured timer state (explicit enable/disable and start/stop
  branches) and emits a `WATCHDOG_TIMER_REAPPLIED` evidence line.

## Decisions

- DEC-1: Hook the watchdog restore in `abort_activation()` rather than inside
  `restore_previous()`: `restore_previous()` returns 1 immediately on a first
  activation (no previous release), so hooking there would skip watchdog
  restoration exactly on fresh-host aborts; `abort_activation()` is the single
  choke point of every post-refresh abort path.
- DEC-2: Gate the restore on `watchdog_prestate_captured`: capture only reads
  and stages backups, so if capture fails the abort happens before any watchdog
  mutation and skipping the restore is correct; pre-capture aborts (e.g. "unit
  installation failed") must not touch watchdog state.
- DEC-3: On success with a previously absent timer, leave the freshly installed
  timer not enabled: the refresh's purpose is keeping existing copies fresh,
  while enablement is an operator decision — #412 exists precisely because the
  deploy forced it.
- DEC-4: Backup naming, location and mode follow the existing pattern
  (`mktemp` in the updater directory, 0600, removed by the EXIT trap); the
  restore installs back with production modes 0755/0644.
- DEC-5: Reapply with explicit enable/disable plus start/stop instead of
  `enable --now` so each captured dimension is reapplied separately and a
  previously disabled timer provably stays disabled (no enable token remains).

## Affected contours

- Ubuntu Worker/relay deploy transaction only: `deploy/worker/ubuntu/update-exact.sh`,
  its two test files, and this SDD trio.
- No change to `rollback-exact.sh`, `install-systemd.sh`, `install-manual.sh`,
  workflows, the watchdog logic, MediaMTX configuration, the three deploy-managed
  units, or any credential material.

## Validation

- `bash -n deploy/worker/ubuntu/update-exact.sh`.
- `ruff check` (0.16.10, `scripts/quality/ruff.toml`) on both touched test files.
- `python3 -m unittest tests.test_ubuntu_worker_exact_updater
  tests.test_ubuntu_worker_rollback -v` green, including all pre-existing pins.
- Full suite `python3 -m unittest discover -s tests -p 'test_*.py'` green.
- `python3 scripts/ci/validate_sdd.py` green.
- RED check: stash `update-exact.sh`, run the new test class (must fail), pop,
  verify the working file via sha256 comparison.

## Runtime feedback

- RF-001: Operator actions expected: 0; the deploy transaction preserves the
  operator's watchdog timer state autonomously.
- RF-002: Post-deploy evidence: `WATCHDOG_TIMER_REAPPLIED timer_present=...`
  in the deploy journal; timer state after a deploy equals the state before it.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: capture strictly before the first mutation, guarded abort hook that cannot block the managed-units restore, pattern-consistent restore function with verification, RED-anchored marker/structural tests, exact single-script scope | Validation: targeted unittest classes, full unittest suite, ruff, bash -n and SDD validators green locally; RED check against the base script | Residual risk: runtime behaviour of the transaction on a live host is verified only after production deploy | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: R-1 | Level: unit | Priority: P0 | Evidence: test_prestate_capture_precedes_first_watchdog_mutation (markers plus structural index ordering, RED vs base)
- TEST-002 | Covers: R-2 | Level: unit | Priority: P0 | Evidence: test_restore_previous_watchdog_restores_captured_prestate and test_abort_paths_restore_watchdog_prestate (RED vs base)
- TEST-003 | Covers: R-3 | Level: unit | Priority: P0 | Evidence: test_unconditional_timer_enable_is_removed, test_timer_reapply_is_gated_on_captured_prestate, test_fresh_host_timer_stays_not_enabled (RED vs base)
- TEST-004 | Covers: R-4 | Level: unit | Priority: P1 | Evidence: test_cleanup_covers_watchdog_backups, bash -n, all pre-existing updater/rollback pins green unchanged
- TEST-005 | Covers: R-1,R-2,R-3,R-4 | Level: integration | Priority: P1 | Evidence: full unittest discover suite, ruff and SDD validators green

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: Issue #412 checkpoint + authorization receipt (OUTCOME APPROVED, issuecomment-6042860905)
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: updater preflight gates; watchdog pre-state capture stages backups before mutation
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: previous release restored for the deploy-managed units AND the watchdog artifacts restored to the captured pre-state (previous bytes or removal) with the captured timer enablement/active state; a previously absent timer is never left freshly enabled | Retry: NO | Rollback: restore_previous_watchdog() via abort_activation(), followed by the managed-units restore_previous(); rollback-exact.sh unchanged for its own contour | Evidence: ACTIVATION_ABORTED/ACTIVE_MARKER_UNCHANGED lines with watchdog_prestate_restored=<bool>; RESTORED watchdog_script_present=... line
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: verification gates abort via abort_activation and trigger the transactional watchdog restore | Retry: NO | Rollback: NONE | Evidence: control-service active gate, worker state gates, WATCHDOG_TIMER_REAPPLIED evidence line
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: active-source-commit marker
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging may remain | Retry: NO | Rollback: NONE | Evidence: cleanup trap now covers the watchdog backups alongside the managed-unit backups
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: execution-audit v1
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh (managed units); the in-script watchdog refresh is rolled back transactionally by restore_previous_watchdog() during the same activation run | Evidence: rollback manifest
