# Spec: Runtime verification failure rebuild (#426)

- Issue: #426
- Specification: specs/426-runtime-rebuild/spec.md

## Product outcome

The #406 autonomous UBUNTU_WORKER deploy (main @ b923fe8, run 37761728923)
failed closed at `prepare-runtime.sh:376`: an EXISTING on-box shared runtime
dir no longer passed `verify_ready_runtime`, the script emitted one opaque
ERROR line (`existing runtime ID is incomplete or fails verification`) and
exited 12, the exact updater aborted and the fail-closed rollback chain fired
(`DEPLOY_CONFIG_ROLLED_BACK reason=updater_failed`, exit 20). The rollback
chain worked as designed, but the same drifted on-box state (most plausibly an
apt python upgrade invalidating the recorded runtime-manifest) makes EVERY
future worker deploy fail deterministically: the locks are unchanged so the
runtime_id is unchanged, and no deployed fix can converge the host without
manual on-box steps.

This change adds a bounded, deterministic self-heal INSIDE the same prepare
transaction, with zero change to the healthy path:

1. When the existing runtime dir fails `verify_ready_runtime`, the script now
   records WHICH ordered sub-check failed (ready marker file, venv python
   executable, definition files, ready-marker content, the three lock byte
   compares, or the manifest `verify_python` gate) as
   `RUNTIME_VERIFY_FAILED runtime_id=… check=<name>` (plus, for the manifest
   gate, `RUNTIME_VERIFY_DETAIL …` carrying the underlying verify_python
   message).
2. The failed dir is quarantined, never deleted: an intact same-filesystem
   rename into a hidden, collision-proof sibling
   `$runtime_parent/.quarantine.<runtime_id>.<mktemp>` (following the existing
   `.prepare.<runtime_id>.XXXXXX` convention). The read-only evidence bytes
   are preserved exactly.
3. The script then proceeds through the EXISTING fresh staging path
   (`.prepare.` staging dir → hash-locked two-phase pip install →
   `finalize_runtime` → atomic `mv` publish) and emits
   `RUNTIME_REBUILT runtime_id=… reason=<failing check>` on success. Legacy
   adoption is skipped for a rebuild (it is a migration-only path and shares
   the same on-box python state that just failed verification).
4. If the rebuild/staging itself fails, existing fail-closed semantics are
   preserved: non-zero exit, the cleanup trap removes the staged tree (and
   emits `RUNTIME_REBUILD_FAILED runtime_id=… reason=…` evidence), the
   quarantine dir remains as evidence, and NO partial runtime is ever
   published at the final path (the only publish step is the final atomic
   `mv`).
5. The healthy path is byte-identical: `verify_ready_runtime` is untouched,
   a passing existing runtime still prints exactly
   `PASS runtime_lock_validated` / `RUNTIME_REUSED runtime_id=…` /
   `RUNTIME_ID …` and a fresh install still prints `RUNTIME_CREATED …`.
   Runtime-id derivation is untouched.

## User scenarios

- US-1: The on-box runtime drifted (e.g. apt python upgrade invalidating the
  recorded manifest): the next deploy's prepare step emits
  `RUNTIME_VERIFY_FAILED … check=manifest_python` (+ VERIFY_DETAIL),
  quarantines the old dir, rebuilds from the exact release tree and emits
  `RUNTIME_REBUILT … reason=manifest_python`; the subsequent verify step and
  all future deploys reuse the fresh runtime (`RUNTIME_REUSED`). No manual
  on-box steps.
- US-2: The rebuild itself fails (e.g. no network and a cold wheel cache):
  the prepare step fails closed with `RUNTIME_REBUILD_FAILED` evidence, the
  updater rollback chain fires as today, and the quarantine dir + the absent
  final path prove no partial runtime was installed.
- US-3: A healthy existing runtime: behavior is byte-identical to before —
  `RUNTIME_REUSED`, no quarantine dir, empty diagnostic stderr.
- US-4: An operator or audit reads the deploy log and can tell exactly which
  sub-check invalidated the old runtime (ready missing vs venv python vs cmp
  byte drift vs manifest verify_python) from the `check=` token alone.

## Scope

- `deploy/worker/ubuntu/prepare-runtime.sh`: new
  `classify_ready_runtime_failure()` (mirrors the ordered verify_ready_runtime
  sub-checks and names the first failing one), rebuild wiring in the
  existing-runtime block (`rebuild_reason`, RUNTIME_VERIFY_FAILED /
  RUNTIME_VERIFY_DETAIL / RUNTIME_QUARANTINED evidence, quarantine rename),
  legacy-adoption skip while a rebuild is pending,
  `RUNTIME_REBUILT`/`RUNTIME_CREATED` emission split, and a
  `RUNTIME_REBUILD_FAILED` evidence line in the fresh-path cleanup trap.
  `verify_ready_runtime`, `verify_python`, `write_manifest`,
  `finalize_runtime`, the two-phase pip install and runtime-id derivation are
  untouched.
- `tests/test_ubuntu_worker_runtime_rebuild.py`: new executed harness module
  (real script end-to-end in a sandbox: EUID-gate-relaxed transform,
  fixture definition files around a really-installed package, python3/pip/
  chown PATH stubs) covering scenarios (a)-(d) plus structural wiring pins.
- This SDD trio and the durable progress file
  (`.tmp-b/progress-426.md`, outside the repo tree).
- Out of scope: `update-exact.sh`, `deploy-authorized.sh`, `api/**`,
  `deploy/vps/**`, `.github/**`, runtime-id derivation, venv internals,
  on-box manual remediation, all other scripts.

## Requirements

- R-1: An existing runtime dir that fails `verify_ready_runtime` is
  quarantined (intact rename, never deleted) and rebuilt through the existing
  fresh staging + atomic install path in the same transaction, emitting
  `RUNTIME_REBUILT runtime_id=… reason=<check>` on success.
- R-2: The failing sub-check is recorded as
  `RUNTIME_VERIFY_FAILED runtime_id=… check=<name>` where `<name>` mirrors
  the ordered verify_ready_runtime checks (ready_file, venv_python,
  runtime_lock_file, requirements_file, lock_file, manifest_file,
  ready_marker, cmp_runtime_lock, cmp_requirements, cmp_lock_file,
  manifest_python); the manifest_python case additionally emits the
  underlying verify_python message as `RUNTIME_VERIFY_DETAIL …`.
- R-3: A rebuild/staging failure fails closed: non-zero exit, staged tree
  removed, `RUNTIME_REBUILD_FAILED` evidence, quarantine dir preserved, and
  no partial runtime at the final path (atomic `mv` is the only publish
  step).
- R-4: The healthy path is byte-identical: passing runtime →
  `PASS runtime_lock_validated` + `RUNTIME_REUSED runtime_id=…` +
  `RUNTIME_ID …` with empty diagnostic stderr; fresh install →
  `RUNTIME_CREATED …`; `verify_ready_runtime` and runtime-id derivation are
  unchanged.
- R-5: A pending rebuild skips the legacy-adoption path (migration-only;
  shares the drifted on-box python state) and goes straight to fresh staging.

## Acceptance criteria

- AC-1: Verification failure on an existing runtime → deterministic rebuild:
  `RUNTIME_VERIFY_FAILED … check=…` + quarantine + `RUNTIME_REBUILT …
  reason=…`, and the immediately following prepare run reuses the fresh
  runtime (`RUNTIME_REUSED`) through the script's own verification gate.
- AC-2: Rebuild/staging failure → fail-closed non-zero exit, no partial
  runtime at the final path, exactly one quarantine dir preserving the old
  bytes, no `.prepare.` staging leftovers, `RUNTIME_REBUILD_FAILED` evidence.
- AC-3: Healthy runtime → exact stdout (`PASS runtime_lock_validated`,
  `RUNTIME_REUSED runtime_id=…`, `RUNTIME_ID …`), empty stderr, no
  quarantine dir.
- AC-4: Which-check evidence correctness: ready-marker-missing,
  venv-python-missing, lock byte drift and manifest drift report
  `ready_file`, `venv_python`, `cmp_runtime_lock` and `manifest_python`
  respectively; only `manifest_python` carries `RUNTIME_VERIFY_DETAIL`.
- AC-5: Full pytest suite green; `bash -n` clean on prepare-runtime.sh; ruff
  clean on the changed Python test file; `validate_sdd.py` green; the
  existing prepare-runtime batteries
  (test_ubuntu_worker_runtime_hash_lock.py, test_ubuntu_worker_shared_runtime.py,
  test_ubuntu_worker_manual_install.py) stay green.

## Runtime feedback

- RF-001: Operator actions expected: 0 on deploy — the rebuild is fully
  automatic inside the existing prepare/update transaction; the next
  autonomous UBUNTU_WORKER deploy over a drifted on-box runtime converges
  without manual steps (the #406 failure class).
- RF-002: Evidence lines on the rebuild path:
  `RUNTIME_VERIFY_FAILED runtime_id=… check=<name>` (+ `RUNTIME_VERIFY_DETAIL`
  for the manifest gate), `RUNTIME_QUARANTINED runtime_id=… path=…`,
  `RUNTIME_REBUILT runtime_id=… reason=<name>`; on a failed rebuild
  `RUNTIME_REBUILD_FAILED runtime_id=… reason=<name>` before the fail-closed
  exit that feeds the existing updater rollback (DEPLOY_CONFIG_ROLLED_BACK).
  The old runtime bytes remain under
  `$install_root/runtimes/.quarantine.<runtime_id>.<…>` for audit.

## NFR assessment

- NFR-001 | Area: reliability/operations | Target: a drifted on-box runtime no longer wedges every future deploy — verification failure deterministically rebuilds in-transaction with which-check evidence and quarantine semantics (issue #426 / #406 run 37761728923 failure class closed without manual steps) | Validation: executed end-to-end scenarios (failing runtime → RUNTIME_REBUILT + failing-check evidence → next run RUNTIME_REUSED; staging failure → fail-closed with quarantine preserved and no partial runtime) | Evidence: tests/test_ubuntu_worker_runtime_rebuild.py — test_verification_failure_rebuilds_and_converges, test_rebuild_staging_failure_fails_closed_preserving_quarantine, test_failing_check_evidence_names_each_sub_check | Status: PASS
- NFR-002 | Area: compatibility | Target: the healthy path is byte-identical — verify_ready_runtime, runtime-id derivation, RUNTIME_REUSED/RUNTIME_CREATED emissions and the existing structural pins are unchanged; no behavior change for any currently-green deploy | Validation: exact stdout/stderr pin on a healthy fixture runtime plus the untouched-source pins and the full existing prepare-runtime batteries | Evidence: tests/test_ubuntu_worker_runtime_rebuild.py — test_healthy_runtime_is_reused_byte_identically, test_verify_ready_runtime_is_unchanged, test_healthy_path_emissions_are_unchanged; tests/test_ubuntu_worker_shared_runtime.py + tests/test_ubuntu_worker_runtime_hash_lock.py green | Status: PASS
- NFR-003 | Area: operations/evidence | Target: the failure branch is observable — the log alone answers WHICH sub-check failed, WHERE the old dir was quarantined, and WHETHER the rebuild succeeded, without on-box access | Validation: executed assertions on the emitted marker lines (check names, quarantine path, rebuild/rebuild-failed lines, manifest detail) | Evidence: tests/test_ubuntu_worker_runtime_rebuild.py — test_failing_check_evidence_names_each_sub_check, test_rebuild_evidence_markers_present | Status: PASS
- NFR-004 | Area: security/data | Target: quarantine never deletes evidence and never mutates the failed runtime bytes (intact same-filesystem rename into a hidden sibling following the .prepare. convention); no new network surface, no credential material, staging remains hash-locked two-phase | Validation: structural never-delete pins (no rm of the runtime root; rmdir-of-placeholder before mv) plus the executed quarantine-content byte-equality assertions | Evidence: tests/test_ubuntu_worker_runtime_rebuild.py — test_quarantine_preserves_evidence_and_never_deletes, test_rebuild_staging_failure_fails_closed_preserving_quarantine (quarantined lock bytes compared) | Status: PASS

## Deviations from the work order

- None in scope. The quarantine location uses the documented alternative the
  work order explicitly allows ("or sibling inside runtimes/ — follow
  existing dir conventions"): a hidden, collision-proof
  `.quarantine.<runtime_id>.<mktemp>` sibling (mktemp allocation instead of a
  raw epoch suffix) so same-second rebuilds can never collide and the
  existing `.prepare.<runtime_id>.XXXXXX` convention is followed.
