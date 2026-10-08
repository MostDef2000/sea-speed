# Tasks: Installed-copy refresh in the worker deploy transaction

- Specification: specs/406-installed-copy-refresh/spec.md

## Delivery tasks

- T-406-001: RECON the installed-copy inventory across
  `deploy/worker/ubuntu/*` (grep cp/install into `/usr/local/{bin,sbin}`
  and other installed locations); map source path → installed path →
  installer → current refresh semantics; record the inventory and the
  transcode-script (no installed copy) disposition in the SDD and durable
  progress file
- T-406-002: Extend `deploy/worker/ubuntu/update-exact.sh` with the
  inventory-driven transactional refresh: `sha256sum` in the required
  command gate, `installed_copy_backup` global + EXIT-cleanup coverage,
  `refresh_installed_copies()` (declared watchdog-trio inventory,
  per-entry report-not-delete leftovers, backup-before-mutation, install
  from the exact release tree, SHA-256 parity gate, inline restore +
  fail-closed return), and the activation-flow call routed through
  `abort_activation`
- T-406-003: Add `tests/test_ubuntu_worker_installed_copy_refresh.py`
  (structural contract class + executed sandbox harness class) covering:
  stale copy refreshed to release bytes, refresh/verification failure
  fail-closed with prior bytes restored, post-transaction whole-inventory
  SHA-256 parity, fresh-install and second-run byte-identical idempotency,
  installed-only leftover report-not-delete, and backup-allocation
  abort-before-mutation; keep the #389/#412 harness discipline
- T-406-004: Update `tests/test_ubuntu_worker_exact_updater.py` with the
  two minimal documented anchor re-pins for the generalized mechanism
  (capture-precedes-refresh ordering; watchdog delivery markers) without
  weakening any assertion
- T-406-005: Confirm `deploy/worker/ubuntu/deploy-authorized.sh` needs no
  change (contour classification already covers the refresh inside the
  analytics-worker transaction) and record the decision in the SDD
- T-406-006: Run the verification battery (full pytest, new regression
  tests verbose, `bash -n` on changed shell files, ruff on changed Python
  files, `scripts/ci/validate_sdd.py`) and leave the changes uncommitted
  for orchestrator admission

## Completion gate

- [ ] T-406-001
- [ ] T-406-002
- [ ] T-406-003
- [ ] T-406-004
- [ ] T-406-005
- [ ] T-406-006
- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned (Ubuntu worker deploy transaction; INSTALLED_COPY_REFRESHED evidence verified post-deploy)
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-004 mitigated or disclosed in plan.md
- [ ] Waivers resolved or current — none

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (autonomous Ubuntu worker deploy fans out at merge)
- [ ] Runtime acceptance resolved — orchestrator-owned (deploy transaction refreshes the installed watchdog trio; INSTALLED_COPY_REFRESHED evidence lines verified on the worker post-deploy)
- [ ] Deferred work recorded — none (installed-copy inventory is declarative; future installed copies extend the inventory)
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-004 in plan.md Risk profile
- [ ] Waivers resolved or current — none

## Requirements traceability

- AC-001 | Task: T-406-002,T-406-003 | Evidence: test_stale_installed_copies_are_refreshed_to_release_bytes (executed harness: stale trio → exact release bytes + INSTALLED_COPY_REFRESHED per entry) | Coverage: COVERED
- AC-002 | Task: T-406-002,T-406-003 | Evidence: test_install_failure_fails_closed_and_restores_prior_bytes, test_hash_mismatch_fails_closed_and_restores_prior_bytes, test_backup_mktemp_failure_aborts_before_any_mutation (abort + prior bytes restored, no partial inventory mutation) | Coverage: COVERED
- AC-003 | Task: T-406-002,T-406-003 | Evidence: test_post_transaction_hash_parity_holds_for_whole_inventory (mixed host, whole-inventory SHA-256 parity post-transaction) | Coverage: COVERED
- AC-004 | Task: T-406-002,T-406-003 | Evidence: test_fresh_host_installs_every_inventory_entry_from_release + test_second_run_is_byte_identical_idempotent | Coverage: COVERED
- AC-005 | Task: T-406-002,T-406-003 | Evidence: test_release_tree_lacking_source_reports_leftover_without_deletion (report-not-delete, bytes preserved, no abort) | Coverage: COVERED
- AC-006 | Task: T-406-005,T-406-006 | Evidence: full pytest suite green; new battery verbose green; bash -n clean; ruff clean; validate_sdd.py green; deploy-authorized.sh contour decision recorded (T-406-005) | Coverage: COVERED
