# Tasks: Runtime verification failure rebuild (#426)

- Specification: specs/426-runtime-rebuild/spec.md

## Delivery tasks

- T-426-001: RECON the prepare-runtime flow (verify_ready_runtime ordered
  sub-checks, staging/finalize/atomic-publish machinery, legacy adoption
  path, exit-code contract with the exact updater), the #406 executed-harness
  test patterns (extract/stub/override-env), and the change-control
  classification for the changed-file set; record findings in the durable
  progress file
- T-426-002: Add the rebuild branch to
  `deploy/worker/ubuntu/prepare-runtime.sh`:
  `classify_ready_runtime_failure()` mirroring the ordered
  verify_ready_runtime sub-checks, RUNTIME_VERIFY_FAILED / RUNTIME_VERIFY_DETAIL
  evidence, quarantine rename into
  `.quarantine.<runtime_id>.<mktemp>` (never delete), `rebuild_reason`
  wiring, legacy-adoption skip while rebuilding, RUNTIME_REBUILT /
  RUNTIME_CREATED emission split, RUNTIME_REBUILD_FAILED cleanup-trap
  evidence; keep verify_ready_runtime, verify_python, write_manifest,
  finalize_runtime and the runtime-id derivation byte-verbatim
- T-426-003: Add `tests/test_ubuntu_worker_runtime_rebuild.py`: executed
  end-to-end harness (real script, EUID-gate-relaxed transform documented,
  fixture definition files around a really-installed package, python3/pip/
  chown PATH stubs) covering verification-failure rebuild + convergence,
  staging-failure fail-closed, healthy-path byte-identical pin, which-check
  evidence table, and structural wiring pins; prove RED against base
  b923fe8 via SEA_SPEED_426_PREPARE_RUNTIME_PATH
- T-426-004: Record the SDD trio (spec/plan/tasks) with the derived
  UBUNTU_WORKER risk profile (REQUIRED) and the deployment transaction audit
- T-426-005: Run the verification battery (full pytest, new battery verbose,
  RED-vs-base contrast, `bash -n` on prepare-runtime.sh, ruff on the changed
  Python test file, `scripts/ci/validate_sdd.py`) and commit locally with the
  approved author identity; leave the branch unpushed for orchestrator
  admission

## Completion gate

- [ ] T-426-001
- [ ] T-426-002
- [ ] T-426-003
- [ ] T-426-004
- [ ] T-426-005
- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned (next UBUNTU_WORKER deploy over a drifted on-box runtime converges: RUNTIME_VERIFY_FAILED → RUNTIME_QUARANTINED → RUNTIME_REBUILT evidence in the deploy log)
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-004 mitigated or disclosed in plan.md
- [ ] Waivers resolved or current — none

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (rebuild reaches the worker through the existing deploy-authorized → update-exact → prepare-runtime transaction)
- [ ] Runtime acceptance resolved — orchestrator-owned (a drifted on-box runtime demonstrably rebuilds with RUNTIME_VERIFY_FAILED/RUNTIME_REBUILT evidence in an autonomous deploy log)
- [ ] Deferred work recorded — none (quarantine dir pruning is deliberately out of scope; disk reclamation is an operator decision)
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-004 in plan.md Risk profile
- [ ] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-426-002,T-426-003 | Evidence: test_verification_failure_rebuilds_and_converges (RUNTIME_VERIFY_FAILED check=ready_file + RUNTIME_QUARANTINED + RUNTIME_REBUILT reason=ready_file; second run RUNTIME_REUSED through the script's own verification gate) | Coverage: COVERED
- AC-2 | Task: T-426-002,T-426-003 | Evidence: test_rebuild_staging_failure_fails_closed_preserving_quarantine (non-zero exit, RUNTIME_REBUILD_FAILED, final path absent, quarantine bytes preserved, no .prepare. leftovers) | Coverage: COVERED
- AC-3 | Task: T-426-002,T-426-003 | Evidence: test_healthy_runtime_is_reused_byte_identically (exact stdout incl. PASS runtime_lock_validated + RUNTIME_REUSED + RUNTIME_ID, empty stderr, no quarantine) | Coverage: COVERED
- AC-4 | Task: T-426-002,T-426-003 | Evidence: test_failing_check_evidence_names_each_sub_check (ready_file / venv_python / cmp_runtime_lock / manifest_python; RUNTIME_VERIFY_DETAIL only for manifest_python) + test_classify_mirrors_verify_ready_runtime_check_order | Coverage: COVERED
- AC-5 | Task: T-426-005 | Evidence: full pytest suite green; new battery verbose green; RED-vs-base contrast recorded (12 failures on b923fe8 via SEA_SPEED_426_PREPARE_RUNTIME_PATH, healthy pin green on base by design); bash -n clean; ruff clean on the changed test module; validate_sdd.py green; existing prepare-runtime batteries unchanged green | Coverage: COVERED
