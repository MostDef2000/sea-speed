# Plan: Runtime verification failure rebuild (#426)

- Issue: #426
- Specification: specs/426-runtime-rebuild/spec.md

## Implementation approach

1. RECON-established facts: `prepare-runtime.sh` derives the runtime_id from
   the three definition files, fail-closes on lock validation (exit 3), gates
   on EUID (exit 1), then for an existing runtime dir runs
   `verify_ready_runtime()` (11 ordered sub-checks ending in the manifest
   `verify_python` gate) and on failure printed one opaque ERROR and exited
   12 — the #406 run 37761728923 wedge. The fresh staging path stages into
   `$runtime_parent/.prepare.<id>.XXXXXX` and publishes via a single atomic
   `mv` inside `finalize_runtime`; legacy adoption is a separate
   migration-only path gated on `$install_root/releases`. No deploy script
   enumerates `runtimes/` beyond exact-ID lookups (update-exact.sh:217,
   install-systemd.sh:78), so extra sibling dirs are inert. Sandbox runs as
   uid 1000, so executed tests use the #406-suite pattern: a transformed copy
   of the real script (only the EUID gate relaxed, documented) plus PATH
   stubs (python3 fake-venv, pip, chown) and fixture definition files built
   around a really-installed package so verify_python checks are real.
2. `classify_ready_runtime_failure()`: new function mirroring
   verify_ready_runtime's predicates in the exact same order, printing the
   first failing check name (ready_file, venv_python, runtime_lock_file,
   requirements_file, lock_file, manifest_file, ready_marker,
   cmp_runtime_lock, cmp_requirements, cmp_lock_file, manifest_python) and
   "unknown" only as a race fallback. verify_ready_runtime itself is left
   verbatim — the healthy path cannot change.
3. Existing-runtime block: on verification failure emit
   `RUNTIME_VERIFY_FAILED runtime_id=… check=…` (and
   `RUNTIME_VERIFY_DETAIL …` from a verify_python re-run for the
   manifest_python case), quarantine via
   `mktemp -d "$runtime_parent/.quarantine.$runtime_id.XXXXXX"` + `rmdir` +
   `mv` (intact rename; no chmod needed — rename only touches the parent
   dir; the read-only evidence bytes are preserved), set `rebuild_reason`,
   emit `RUNTIME_QUARANTINED … path=…`, and fall through.
4. Legacy-adoption guard: `if [[ -z "$rebuild_reason" ]]` wraps the
   active-marker detection, the release-venv candidate scan, the adoption
   loop and the exit-21 fallback gate (wrapped, body unchanged — a two-line
   diff so reviewers see the migration path untouched).
5. Emission split at the end of the fresh staging path:
   `RUNTIME_REBUILT runtime_id=… reason=…` when `rebuild_reason` is set,
   otherwise the unchanged `RUNTIME_CREATED runtime_id=… cache=…
   hash_locked=true`. The fresh-path cleanup trap additionally emits
   `RUNTIME_REBUILD_FAILED runtime_id=… reason=…` — it can only run when the
   staging path died before finalize, so it is pure failure evidence and
   cannot fire on the healthy path.
6. Tests: new executed module tests/test_ubuntu_worker_runtime_rebuild.py —
   structural wiring pins + the real script executed end-to-end per scenario
   (a)-(d); RED-vs-base proven through SEA_SPEED_426_PREPARE_RUNTIME_PATH.

## Architecture

- The rebuild rides the EXISTING staging/finalize machinery — no new install
  code path, no new flags, no caller changes. The only new executable logic
  is the classification helper (pure reads) and the quarantine rename
  (same-filesystem mv between two dirs under the root-owned runtimes/).
- Fail-closed properties are inherited, not re-implemented: `set -euo
  pipefail` aborts on any staging error; the cleanup trap removes the staged
  tree; the atomic `mv` remains the only step that can create the final
  path, so a failed stage can never leave a half runtime there.
- The quarantine naming (`mktemp` allocation, hidden dot-prefix sibling)
  makes same-second rebuild collisions impossible and preserves the failed
  bytes read-only for audit; nothing in the deploy scripts enumerates
  `runtimes/` beyond exact-ID lookups, so quarantine siblings are inert.

## Decisions

- D-1: Keep `verify_ready_runtime` byte-verbatim and add a mirroring
  classifier instead of refactoring it — the healthy reuse path (and every
  existing structural pin) must be provably untouched.
- D-2: Skip legacy adoption while a rebuild is pending: the work order
  mandates the fresh staging path, adoption is a migration-only path, and its
  legacy venvs share the same on-box python state that just failed
  verification, so adoption could not rescue the drift class anyway.
- D-3: Quarantine via `mktemp -d` + `rmdir` + `mv` rather than a raw
  `<runtime_root>.quarantine-<epoch>` name: collision-proof under
  same-second retries and consistent with the existing
  `.prepare.<runtime_id>.XXXXXX` convention (the work order explicitly allows
  the sibling convention).
- D-4: `RUNTIME_VERIFY_DETAIL` (the underlying verify_python message, e.g.
  "runtime Python ABI mismatch" or "runtime manifest requirements_lock_sha256
  mismatch") is emitted only for check=manifest_python — the one check whose
  name alone cannot distinguish on-box python drift from manifest drift.
- D-5: The rebuild-failure evidence line lives in the fresh-path cleanup trap
  rather than wrapping the pip invocations: the trap only runs when staging
  died before finalize, the exit code stays the raw fail-closed code the
  updater already handles, and the pip phases remain untouched.

## Affected contours

- Ubuntu Worker/relay: `deploy/worker/ubuntu/prepare-runtime.sh` (runtime
  provisioning behavior inside the existing deploy transaction), the new
  focused test module, this SDD trio (+ durable progress file outside the
  repo tree).
- No change to `update-exact.sh`, `deploy-authorized.sh`, `api/**`,
  `deploy/vps/**`, `.github/**`, worker/**, systemd units, or runtime-id
  derivation.

## Validation

- Full suite on head branch: green (exact counts in the verification
  transcript and tasks.md AC-5).
- New battery verbose: executed scenarios (a)-(d) + structural pins green;
  RED-vs-base proven via SEA_SPEED_426_PREPARE_RUNTIME_PATH (12 failures on
  b923fe8, healthy-path pin green on base by design).
- `bash -n deploy/worker/ubuntu/prepare-runtime.sh`: clean.
- ruff (`scripts/quality/ruff.toml`) on the changed Python test file: clean.
- `python3 scripts/ci/validate_sdd.py`: green.

## Runtime feedback

- RF-001: Operator actions expected: 0 — the rebuild is automatic inside the
  existing prepare transaction; a drifted on-box runtime converges on the
  next deploy.
- RF-002: Evidence: RUNTIME_VERIFY_FAILED / RUNTIME_VERIFY_DETAIL /
  RUNTIME_QUARANTINED / RUNTIME_REBUILT (success) or RUNTIME_REBUILD_FAILED
  (fail-closed); quarantined bytes remain under
  `runtimes/.quarantine.<runtime_id>.<…>`.

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from
  `scripts/ci/validate_change_contract.py` `classify_file`/`derive_impact`
  over the changed-file set —
  `deploy/worker/ubuntu/prepare-runtime.sh` classifies UBUNTU_WORKER
  (executed: `classify_file → UBUNTU_WORKER`), and `derive_impact` over the
  full changed set returns UBUNTU_WORKER (runtime contours {UBUNTU_WORKER}),
  matching the #406/#407 precedent that the Ubuntu Worker contour derives a
  full risk profile.
- RISK-001 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: the rebuild closes the #406 deterministic wedge class (drifted on-box runtime → every future deploy fails exit 12) at the code level, with which-check evidence and quarantine-before-rebuild ordering; the healthy path is pinned byte-identical so no currently-green deploy changes behavior | Validation: executed rebuild convergence scenario (failing runtime → RUNTIME_REBUILT → next run RUNTIME_REUSED) and exact healthy-path stdout/stderr pin | Residual risk: LOW — a drifted runtime now gets quarantined even when the drift is transient (e.g. a mid-deploy external mutation); the rebuild still converges from the exact release tree, and the quarantined bytes remain for audit | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: quarantine trades disk for evidence — each rebuild leaves one hidden sibling dir (multi-GB with the torch closure) and nothing in the deploy path prunes it; the old dir was already unusable (it failed verification) and no deploy script enumerates runtimes/ beyond exact-ID lookups, so quarantine siblings are inert | Validation: executed quarantine assertions (exactly one dir, old bytes preserved) + structural never-delete pins | Residual risk: LOW — quarantine dirs accumulate only per rebuild event (rare by construction: each rebuild converges the runtime so the next deploy reuses); disk reclamation stays an operator decision outside this change's scope | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: DATA | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: fail-closed rebuild failure — set -e aborts the staging path, the cleanup trap removes the staged tree, the atomic mv remains the only publish step so no partial runtime can exist at the final path, and the updater rollback chain (unchanged) restores the prior release state | Validation: executed staging-failure scenario (non-zero exit, RUNTIME_REBUILD_FAILED, final path absent, quarantine preserved, no .prepare. leftovers) | Residual risk: LOW — between quarantine and successful rebuild the host has no shared runtime at the new ID; the previous release keeps running (its venv is untouched) and the updater's fail-closed semantics are unchanged | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: the classification mirrors verify_ready_runtime's predicates in the exact same order (pinned structurally), so the reported check name is the true first failure; the "unknown" fallback only covers a verify-passing race between the two reads and still quarantines + rebuilds rather than reusing | Validation: test_classify_mirrors_verify_ready_runtime_check_order + executed which-check table (ready_file / venv_python / cmp_runtime_lock / manifest_python) | Residual risk: LOW — an exotic state that flips between verify and classify reports "unknown" with full rebuild behavior (fail-safe direction) | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-001 | Level: integration | Priority: P0 | Evidence: test_verification_failure_rebuilds_and_converges (executed real script: verify-fail → RUNTIME_VERIFY_FAILED check=ready_file → RUNTIME_QUARANTINED → RUNTIME_REBUILT reason=ready_file; pip phases recorded; next run RUNTIME_REUSED through the script's own gate)
- TEST-002 | Covers: RISK-003 | Level: integration | Priority: P0 | Evidence: test_rebuild_staging_failure_fails_closed_preserving_quarantine (executed: pip install stub failure → non-zero exit, RUNTIME_REBUILD_FAILED, final path absent, quarantine bytes preserved, no .prepare. leftovers)
- TEST-003 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_healthy_runtime_is_reused_byte_identically (exact stdout incl. PASS runtime_lock_validated, empty stderr, no quarantine) + test_verify_ready_runtime_is_unchanged + test_healthy_path_emissions_are_unchanged + test_quarantine_preserves_evidence_and_never_deletes (never-delete pins)
- TEST-004 | Covers: RISK-004 | Level: integration | Priority: P0 | Evidence: test_failing_check_evidence_names_each_sub_check (executed which-check table: ready_file, venv_python, cmp_runtime_lock, manifest_python; DETAIL only for manifest_python) + test_classify_mirrors_verify_ready_runtime_check_order
- TEST-005 | Covers: RISK-001 | Level: unit | Priority: P1 | Evidence: test_rebuild_skips_legacy_adoption_and_runs_fresh_staging (guard before RUNTIME_ADOPTED/RUNTIME_NETWORK_FALLBACK_BLOCKED; RUNTIME_REBUILT after finalize) + test_rebuild_origin_and_ownership_wiring_executed (finalize chown recorded; final dir 0555)
- TEST-006 | Covers: RISK-003 | Level: integration | Priority: P0 | Evidence: full pytest suite green including the existing prepare-runtime batteries (test_ubuntu_worker_runtime_hash_lock.py, test_ubuntu_worker_shared_runtime.py, test_ubuntu_worker_manual_install.py) and the #406/#412 updater suites; bash -n; ruff; validate_sdd.py

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: canonical Issue #426 Outcome Contract scope; allowed paths (prepare-runtime.sh, focused test module, SDD trio, progress file) enforced before first write
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: runtime lock validation and the EUID/command gates run before any mutation (unchanged); classification and quarantine run only after the existing-runtime verification has already failed
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: quarantined old runtime preserved intact; no partial runtime at the final path | Retry: NO | Rollback: the updater's existing fail-closed rollback chain (unchanged) restores the prior release state on any prepare failure; the quarantine rename is itself the evidence-preserving mutation boundary | Evidence: executed staging-failure scenario (test_rebuild_staging_failure_fails_closed_preserving_quarantine)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: quarantined old runtime preserved, final path absent | Retry: NO | Rollback: NONE | Evidence: finalize_runtime re-runs verify_python on the staged tree before publish (unchanged); the rebuilt runtime must pass the script's own verify_ready_runtime on the next run (executed convergence assertion)
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: the only state commit is the atomic mv publish inside finalize_runtime (unchanged); active-source-commit/service wiring remains updater-owned
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: none beyond existing staging temporaries | Retry: NO | Rollback: NONE | Evidence: the fresh-path cleanup trap (unchanged removal behavior) additionally records RUNTIME_REBUILD_FAILED evidence; the quarantine dir is deliberately NOT housekept (evidence)
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: RUNTIME_VERIFY_FAILED (check=), RUNTIME_VERIFY_DETAIL (manifest gate), RUNTIME_QUARANTINED (path), RUNTIME_REBUILT (reason) / RUNTIME_REBUILD_FAILED lines on the deploy log
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rebuild failure keeps the existing fail-closed semantics — non-zero prepare exit feeds the unchanged updater rollback (DEPLOY_CONFIG_ROLLED_BACK); quarantine dir preserved as rollback-adjacent evidence | Evidence: test_rebuild_staging_failure_fails_closed_preserving_quarantine; update-exact.sh/deploy-authorized.sh untouched (forbidden paths honored)
