# Spec: Installed-copy refresh in the worker deploy transaction

- Issue: #406
- Specification: specs/406-installed-copy-refresh/spec.md

## Product outcome

Installed copies of release-derived scripts on the Ubuntu worker are NOT
refreshed by the deploy transaction chain as a class: production can run
arbitrarily old code while the fixed release sits untouched in
`/opt/sea-speed-worker/releases/`. The stale-copy class (audit 2026-10-07)
has three production precedents: #388 (stale transcode script with inline
credentials live in `/proc` cmdline), BUG #1 (stale watchdog `/cam1` vs
`/cam1-h264`), and #389/#390 (a release-source refresh ADDED for the
installed watchdog copy inside the deploy transaction — #412 made that
refresh transactional).

This change generalizes the #389/#390/#412 pattern into an
inventory-driven, transactional installed-copy refresh inside
`update-exact.sh` activation:

1. A declared inventory maps every release-derived installed copy:
   release-source path → installed path → mode. The recon-enumerated full
   inventory is the camera1-h264 watchdog trio —
   `camera1-h264-freshness-watchdog.py` →
   `/usr/local/sbin/sea-speed-camera1-h264-freshness-watchdog` (0755),
   `sea-speed-camera1-h264-freshness.service` and
   `sea-speed-camera1-h264-freshness.timer` → `/etc/systemd/system/`
   (0644) — the only release-derived copies installed outside the release
   tree. Deploy-managed units (worker/road/control) are swapped by
   `install-systemd.sh` inside the same transaction; every other
   `deploy/worker/ubuntu` component (worker-control-agent.py,
   check-worker-health.py, ...) executes in place from
   `$release_root/source/deploy/worker/ubuntu/` via absolute ExecStart
   paths, so it cannot go stale. `/usr/local/bin/mediamtx` is an external
   binary download, not release-derived, and is out of scope.
   `camera1-h264-transcode.sh` itself is executed in place from wherever
   the operator runs it (`$script_dir` binding in the generated unit);
   the repository deploy chain never copies it, so it has no installed
   copy to refresh (refresh option (a) chosen; no release-pinned
   migration of the transcode script).
2. For every inventory entry, inside the deploy transaction (after release
   install/verification): an existing installed copy is backed up
   byte-for-byte before the first mutation, refreshed from the exact
   release tree, and verified by SHA-256 parity against the release
   source; a missing installed copy is a fresh install from the release
   (idempotent). Any backup, install or verification failure restores the
   prior bytes from the backup and fails the activation closed through
   the existing `abort_activation` transaction (prior units/services
   restored).
3. A release tree that lacks the source for an existing installed copy
   (installed-only legacy leftover) is reported
   (`INSTALLED_COPY_LEFTOVER`) and left untouched — the transaction never
   deletes installed artifacts (bounded behavior).

## User scenarios

- US-1: A worker host has a stale
  `/usr/local/sbin/sea-speed-camera1-h264-freshness-watchdog` (or stale
  watchdog unit/timer) from an old install; the deploy transaction
  refreshes it to the exact release bytes, verifies SHA-256 parity, and
  the stale code can no longer survive a deploy.
- US-2: The refresh cannot write the installed copy (unwritable target)
  or the post-refresh bytes do not match the release source (torn or
  poisoned write); the transaction aborts activation, the prior bytes are
  restored from the backup, the deploy-managed units are restored, and
  the deploy exits non-zero — production never ends up with a half-written
  installed copy.
- US-3: A fresh host (no installed copies) deploys; the inventory entries
  are installed from the release and the transaction completes normally.
- US-4: A second deploy with no release change re-runs the refresh; every
  installed copy ends byte-identical (same SHA-256) and nothing aborts.
- US-5: The release tree no longer ships a source for an installed legacy
  copy; the leftover is reported and left untouched while the remaining
  inventory entries still refresh.

## Scope

- `deploy/worker/ubuntu/update-exact.sh`: `sha256sum` in the required
  command gate; `installed_copy_backup` global + EXIT-cleanup coverage; a
  new `refresh_installed_copies()` function declaring the inventory and
  performing the transactional backup/refresh/verify/restore loop; the
  activation flow calls it between `capture_watchdog_prestate` and the
  watchdog daemon-reload, routing failure through `abort_activation`.
- `tests/test_ubuntu_worker_installed_copy_refresh.py` (new): structural
  contract tests plus executed sandbox-harness fault-path coverage
  following the `test_ubuntu_worker_exact_updater.py` harness style.
- `tests/test_ubuntu_worker_exact_updater.py`: two minimal documented
  anchor updates for the generalized mechanism (literal install-line pins
  move to the inventory-refresh call); assertion strength preserved.
- `deploy/worker/ubuntu/deploy-authorized.sh`: no changes — the existing
  contour classification already routes `deploy/worker/ubuntu/*` updates
  through the full analytics-worker transaction, so the refresh inherits
  exact transaction coverage without new wiring.
- This SDD trio and the durable progress file.
- Out of scope: release-pinned migration of `camera1-h264-transcode.sh`
  (it has no installed copy; refresh option (a) chosen), the external
  `mediamtx` binary, `api/**`, `deploy/vps/**`, `.github/**`, `frontend/**`.

## Requirements

- R-1: The refresh runs inside the deploy transaction (after release
  install/verification, before service restarts) for every declared
  inventory entry.
- R-2: An existing installed copy is backed up byte-for-byte before the
  first mutation of that entry.
- R-3: After refresh, the installed bytes must hash-match (SHA-256) the
  release source; a mismatch is a refresh failure.
- R-4: Any backup, install or verification failure restores the prior
  bytes from the backup and fails the activation closed via
  `abort_activation` (restore of deploy-managed units and watchdog
  prestate per #412).
- R-5: A missing installed copy is installed from the release; the
  transaction is idempotent (a second run over refreshed copies is
  byte-identical and does not abort).
- R-6: A release tree lacking the source for an existing installed copy
  reports `INSTALLED_COPY_LEFTOVER` and leaves the copy untouched; it is
  not a transaction failure.
- R-7: Every refresh emits an evidence line
  (`INSTALLED_COPY_REFRESHED installed_path=... mode=... sha256=...`).

## Acceptance criteria

- AC-1: A stale installed copy is detected and refreshed to the exact
  release bytes by the transaction, with post-transaction SHA-256 parity
  for the whole inventory (executed harness: stale scenario + mixed-host
  parity scenario).
- AC-2: A refresh failure (simulated install failure and simulated
  poisoned write) fails closed: abort activation, prior bytes restored
  from backup, remaining inventory untouched by the failed transaction.
- AC-3: Hash parity holds post-transaction for the whole inventory
  (executed assertion over all three entries).
- AC-4: Idempotency: the second run over a refreshed host is
  byte-identical and reports success; fresh hosts get every inventory
  entry installed from the release.
- AC-5: Installed-only leftovers are reported (`INSTALLED_COPY_LEFTOVER`,
  `action=reported_not_deleted`) and never deleted; other entries still
  refresh.
- AC-6: Full pytest suite green; `bash -n` clean on the changed shell
  file; ruff clean on the changed Python test file; `validate_sdd.py`
  green.

## Runtime feedback

- RF-001: Operator actions expected: 0 — the refresh is part of the
  existing autonomous Ubuntu deploy transaction; a refresh failure aborts
  the deploy with the previous release restored.
- RF-002: Failure evidence: `ERROR activation failed: installed copy
  refresh failed` plus `ACTIVATION_ABORTED`/`RESTORED watchdog_*` lines
  from the #412 transaction restoration; success evidence is the
  `INSTALLED_COPY_REFRESHED` lines per inventory entry.

## NFR assessment

- NFR-001 | Area: reliability/operations | Target: no release-derived installed copy outside the release tree can stay stale across a deploy — every inventory entry is refreshed from the exact release source with post-refresh SHA-256 parity; fresh installs are idempotent | Validation: executed sandbox harness (stale-refresh, mixed-host parity, fresh-install, second-run byte-identical scenarios) plus structural inventory-position pins | Evidence: tests/test_ubuntu_worker_installed_copy_refresh.py — test_stale_installed_copies_are_refreshed_to_release_bytes, test_post_transaction_hash_parity_holds_for_whole_inventory, test_fresh_host_installs_every_inventory_entry_from_release, test_second_run_is_byte_identical_idempotent | Status: PASS
- NFR-002 | Area: rollback safety | Target: a refresh or verification failure fails the activation closed — prior bytes restored from the backup, watchdog prestate and deploy-managed units restored through the existing #412 abort path, and no partial refresh leaks (remaining inventory untouched by the failed transaction) | Validation: executed fault-path scenarios (install failure, hash mismatch, backup mktemp failure abort-before-mutation) | Evidence: test_install_failure_fails_closed_and_restores_prior_bytes, test_hash_mismatch_fails_closed_and_restores_prior_bytes, test_backup_mktemp_failure_aborts_before_any_mutation | Status: PASS
- NFR-003 | Area: security | Target: the installed copy can never diverge silently from the release source — SHA-256 parity is verified after every refresh and any divergence fails the deploy closed; installed-only leftovers are reported, never deleted, and never silently accepted as fresh | Validation: hash-mismatch fault scenario (poisoned write detected and restored); leftover report-not-delete scenario asserting byte preservation | Evidence: test_hash_mismatch_fails_closed_and_restores_prior_bytes, test_release_tree_lacking_source_reports_leftover_without_deletion | Status: PASS
- NFR-004 | Area: compatibility | Target: the transaction semantics of #389/#390/#412 are preserved — prestate capture still precedes the first watchdog mutation, timer enablement is still reapplied from captured state, abort paths still restore the watchdog prestate, and the refresh adds no new host state beyond the installed copies themselves | Validation: the full existing #389/#412 structural and executed suites stay green with only two documented anchor updates | Evidence: tests/test_ubuntu_worker_exact_updater.py (24 tests green), test_unconditional_timer_enable_is_removed, test_prestate_capture_precedes_first_watchdog_mutation | Status: PASS

## Deviations from the work order

- None in scope. `deploy/worker/ubuntu/deploy-authorized.sh` was listed as
  allowed but needs no change: the contour classification already maps
  `deploy/worker/ubuntu/*` updates to the full analytics-worker
  transaction, so the new step needs no additional wiring (documented in
  plan.md Affected contours). `camera1-h264-transcode.sh` is unchanged —
  the refresh option (a) applies to installed copies, and the transcode
  script has none (executed in place via the generated unit's `$script_dir`
  binding); the choice is recorded in this spec's Product outcome.
