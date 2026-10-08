# Plan: Installed-copy refresh in the worker deploy transaction

- Issue: #406
- Specification: specs/406-installed-copy-refresh/spec.md

## Implementation approach

1. RECON-established installed-copy inventory (grep across
   `deploy/worker/ubuntu/*`): the only release-derived copies installed
   outside the release tree are the camera1-h264 watchdog trio —
   `camera1-h264-freshness-watchdog.py` →
   `/usr/local/sbin/sea-speed-camera1-h264-freshness-watchdog` (0755,
   installed by `camera1-h264-transcode.sh` activate) and
   `sea-speed-camera1-h264-freshness.{service,timer}` →
   `/etc/systemd/system/` (0644). Deploy-managed units are swapped
   transactionally by `install-systemd.sh`; `worker-control-agent.py` /
   `check-worker-health.py` and every other deploy script execute in place
   from the release tree (absolute ExecStart paths); the transcode script
   binds `$script_dir` at unit-generation time and is never copied by the
   deploy chain; `mediamtx` is an external download.
2. `deploy/worker/ubuntu/update-exact.sh`: add `sha256sum` to the required
   command gate; add the `installed_copy_backup` global plus EXIT-cleanup;
   add `refresh_installed_copies()` (declared inventory
   `"release-source|installed-path|mode"` reusing the `watchdog_*_src/dst`
   globals, per-entry skip/backup/refresh/verify/restore) and replace the
   three literal watchdog install lines with
   `refresh_installed_copies || abort_activation "installed copy refresh failed"`
   positioned after `capture_watchdog_prestate` and before the watchdog
   daemon-reload/timer reapply.
3. `deploy/worker/ubuntu/deploy-authorized.sh`: unchanged — its
   classification maps every `deploy/worker/ubuntu/*` mutation (except
   itself and `authentik/*`) to the full analytics-worker transaction, so
   the new step inherits exact-source coverage with no wiring.
4. Tests: new `tests/test_ubuntu_worker_installed_copy_refresh.py` in the
   established two-tier style — structural contract pins (inventory
   completeness, transaction positioning, backup-before-mutation,
   SHA-256 parity, leftover report-not-delete, cleanup coverage) and an
   executed sandbox harness that extracts `refresh_installed_copies()`,
   runs it under stubbed mktemp/install (byte-copying install stub,
   fail-on-Nth-call and poison-on-Nth-call injection) with the real
   coreutils `sha256sum`, and mirrors the production
   `refresh_installed_copies || abort_activation` wiring.
5. `tests/test_ubuntu_worker_exact_updater.py`: two documented anchor
   updates so the #389/#412 suites pin the generalized mechanism; no
   assertion weakened.

## Architecture

- The inventory is data, not code paths: each entry is a
  `release-source|installed-path|mode` string reusing the existing
  `watchdog_*_src`/`watchdog_*_dst` globals, so adding a future installed
  copy is one inventory line plus (if it is a systemd unit/timer) the
  matching prestate globals — the refresh/verify/restore semantics are
  shared.
- Transaction ordering is unchanged from #412: prestate capture →
  inventory refresh (per entry: backup 0600 → install → SHA-256 parity →
  inline restore on any failure) → daemon-reload → captured-state timer
  reapply → control/worker/road restarts and gates. The refresh failure
  path reuses `abort_activation`, so rollback of the deploy-managed units
  and the watchdog prestate stays exactly as validated for #412.
- Bounded leftover behavior: a missing release source with an existing
  installed copy prints `INSTALLED_COPY_LEFTOVER ... action=reported_not_deleted`
  and continues; the transaction never deletes installed artifacts.

## Decisions

- D-1: Generalize instead of adding a second hard-coded refresh block —
  the stale-copy class is closed by an inventory, so future installed
  copies are added declaratively rather than by copying the #390 block.
- D-2: SHA-256 parity after every refresh (work order requirement; the
  #412 block installed without verifying the result) — a torn or poisoned
  install now fails the deploy closed instead of leaving a silently
  corrupted executable on the host.
- D-3: Backup-restore before abort: the refresh restores prior bytes
  inline first (defense in depth) and then routes through
  `abort_activation`, which restores the captured watchdog prestate and
  deploy-managed units — a refresh failure can never leave a mixed
  old/new host state behind.
- D-4: Leftovers are reported, never deleted (work order bounded
  behavior): an installed-only legacy file may be operator-intentional;
  deletion is a separate authorized decision.
- D-5: `camera1-h264-transcode.sh` refresh option (a) chosen: the script
  has no installed copy (the generated unit binds `$script_dir` in place),
  so there is nothing to refresh and no release-pinned migration is
  needed; recorded in spec.md.
- D-6: Executed tests mirror the production wiring
  (`refresh_installed_copies || abort_activation ...`) rather than a bare
  invocation, so `set -e` cannot mask the fail-closed path in the harness.

## Affected contours

- Ubuntu Worker/relay only: `deploy/worker/ubuntu/update-exact.sh`, the
  new `tests/test_ubuntu_worker_installed_copy_refresh.py`, two anchor
  updates in `tests/test_ubuntu_worker_exact_updater.py`, and this SDD
  trio (+ durable progress file outside the repo tree).
- `deploy/worker/ubuntu/deploy-authorized.sh` deliberately unchanged: the
  `deploy/worker/ubuntu/*` → `worker_runtime_changed` classification
  (deploy-authorized.sh:124-139) already routes this release through the
  full analytics-worker transaction; no new contour step is required.
- No change to `api/**`, `worker/**`, `frontend/**`, `.github/**`,
  `deploy/vps/**`; no schema, API or config-format changes on the host.

## Validation

- Full suite on head branch: green (exact counts in the verification
  transcript and tasks.md AC-6).
- New regression battery verbose: 17 tests green (structural contract +
  executed fault-path scenarios a–d from the work order).
- `bash -n` on `deploy/worker/ubuntu/update-exact.sh`: clean.
- ruff (`scripts/quality/ruff.toml`) on the changed Python files: clean.
- `python3 scripts/ci/validate_sdd.py`: green.

## Runtime feedback

- RF-001: Operator actions expected: 0 — refresh failure aborts the
  deploy with automatic restoration (previous release + watchdog
  prestate), surfacing `ERROR activation failed: installed copy refresh
  failed`.
- RF-002: Success evidence per deploy: `INSTALLED_COPY_REFRESHED
  installed_path=... mode=... sha256=...` for every inventory entry;
  leftover evidence `INSTALLED_COPY_LEFTOVER ... action=reported_not_deleted`.

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from the Ubuntu Worker production
  impact (UBUNTU_WORKER deployment contour, deploy/worker/ubuntu/** change
  — the Change Contract derives a full risk profile); the deployment
  transaction audit below covers the contour.
- RISK-001 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: the refresh runs inside the existing #412 transaction ordering — prestate capture precedes the first mutation, every per-entry failure restores prior bytes inline and then routes through abort_activation, so a failed refresh leaves the previous release and watchdog prestate intact and the deploy exits non-zero | Validation: executed fault-path scenarios (install failure, poisoned-write hash mismatch, backup mktemp failure) assert abort + prior bytes restored + no partial inventory mutation; full existing #412 executed suite green | Residual risk: LOW — a failure that corrupts an installed copy AND defeats both the inline restore and the prestate restore is CRITICAL-logged (pre-existing #412 disposition, unchanged) | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: SHA-256 parity is verified after every refresh; divergence between installed and release bytes fails the deploy closed, so a stale or tampered installed copy cannot silently survive a deploy (the #388/#389 defect class) | Validation: hash-mismatch scenario (poisoned write detected, prior bytes restored, abort recorded); post-transaction whole-inventory parity scenario | Residual risk: LOW — parity is verified at deploy time only; post-deploy on-host tampering is out of scope for the deploy transaction | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: DATA | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the refresh only rewrites release-derived installed copies from the exact release tree; protected configs (worker.env/road-worker.env), models, datasets and output are untouched; leftovers are reported and never deleted; fresh hosts get installs from the release (idempotent, verified byte-identical on re-run) | Validation: leftover report-not-delete scenario; fresh-install scenario; idempotency scenario (second run byte-identical) | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: OPS | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: two anchor updates in the #389/#412 structural suite are the only existing-test changes; both are mechanical re-pins to the generalized mechanism with the assertion strength preserved (capture-precedes-mutation ordering, watchdog delivery markers) and are documented inline | Validation: tests/test_ubuntu_worker_exact_updater.py 24 tests green; no #412 executed-scenario change | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_stale_installed_copies_are_refreshed_to_release_bytes (executed harness: stale watchdog trio refreshed to exact release bytes, INSTALLED_COPY_REFRESHED evidence per entry)
- TEST-002 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_fresh_host_installs_every_inventory_entry_from_release (missing installed copies → installs from release, no backup step) + test_second_run_is_byte_identical_idempotent (second run byte-identical, no abort)
- TEST-003 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_install_failure_fails_closed_and_restores_prior_bytes (fail-on-Nth-call install stub) + test_hash_mismatch_fails_closed_and_restores_prior_bytes (poisoned write) + test_backup_mktemp_failure_aborts_before_any_mutation (abort before any mutation, empty install log)
- TEST-004 | Covers: RISK-003 | Level: unit | Priority: P0 | Evidence: test_post_transaction_hash_parity_holds_for_whole_inventory (mixed host: only the script stale — whole-inventory SHA-256 parity post-transaction)
- TEST-005 | Covers: RISK-003 | Level: unit | Priority: P1 | Evidence: test_release_tree_lacking_source_reports_leftover_without_deletion (INSTALLED_COPY_LEFTOVER action=reported_not_deleted, bytes preserved, other entries refreshed, no abort)
- TEST-006 | Covers: RISK-004 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_exact_updater.py full suite (24 tests) green — #389/#412 transaction semantics preserved (prestate ordering, captured-state timer reapply, abort restoration, cleanup coverage)
  TEST-006 covers the two-anchor-update regression discipline; the
  structural contract pins for the new mechanism live in
  UbuntuWorkerInstalledCopyRefreshContractTests (inventory completeness,
  transaction positioning, backup-before-mutation, hash gate,
  report-not-delete, sha256sum required-command gate, cleanup coverage).

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: canonical Issue #406 Outcome Contract scope; allowed-path list (update-exact.sh, deploy-authorized.sh, transcode script conditional, worker deploy tests, SDD trio, progress file) enforced before first write
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: release prepared and verified (source-commit, runtime-id, quality marker) before activation; #412 prestate capture precedes the first watchdog mutation
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: per-entry prior bytes restored from the staged backup; inventory entries after the failed entry untouched | Retry: NO | Rollback: refresh_installed_copies backs up each installed copy (0600) before mutating it, restores on install/verify failure, and the caller aborts activation so deploy-managed units and the watchdog prestate are restored (restore_previous / restore_previous_watchdog) | Evidence: executed fault-path tests (install failure, hash mismatch, mktemp failure) in tests/test_ubuntu_worker_installed_copy_refresh.py
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: SHA-256 parity of every refreshed copy against the release source inside the same step; post-activation identity checks (ExecStart commit/runtime binding) unchanged from #412
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: active-source-commit marker move unchanged; installed-copy refresh carries no independent state commit
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging/backup temporaries may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: EXIT cleanup trap removes staging_root and all backup temporaries including installed_copy_backup
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: INSTALLED_COPY_REFRESHED lines (path, mode, sha256) per entry; INSTALLED_COPY_LEFTOVER for installed-only files; DEPLOYMENT_ACCEPTED from the authorized chain
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: activation failure restores the previous units, service states and watchdog prestate exactly as validated for #412; a refreshed installed copy is rolled back by the same captured prestate (restore_previous_watchdog) or, for a failed refresh, by the inline per-entry restore | Evidence: abort_activation path tests (test_ubuntu_worker_exact_updater.py test_abort_paths_restore_watchdog_prestate) + refresh inline-restore executed scenarios
