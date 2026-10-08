# Tasks: Hash-locked shared worker runtime dependency graph

- Specification: specs/392-worker-runtime-hash-lock/spec.md

## Delivery tasks

- T-392-001: Bump `runtime-lock.json` to schema 2 (`resolved_lock` section,
  `index_provenance`, `pypi_index_url`, per-package `artifact_sha256` — empty
  until the CI resolution) and add the placeholder
  `requirements-runtime.lock.txt` (schema marker, no pins)
- T-392-002: Rewire `prepare-runtime.sh`: runtime_id v2 over all three
  definition files, fail-closed `validate_runtime_lock` (exit 3 before the
  root check and before any mutation), complete-graph `verify_python` with
  manifest lock-hash and installed-graph checks, `requirements_lock_sha256`
  in `write_manifest`, lock file in `finalize_runtime` and
  `verify_ready_runtime`, two-phase hash-locked fresh creation (verified
  download into a per-run wheelhouse, offline `--require-hashes` install from
  a directive-stripped resolved copy)
- T-392-003: Add the dispatch-only resolver workflow
  `.github/workflows/resolve-runtime-lock.yml` (checkout, setup-python, pinned
  uv, `uv pip compile --generate-hashes` across both pinned indexes, artifact
  upload; no secrets, no deploy logic, no checkout write)
- T-392-004: Add `tests/test_ubuntu_worker_runtime_hash_lock.py` (executed pip
  hash-mechanics over in-test fixture wheels, executed runtime_id v2 and
  fail-closed runs through the module-wide `SEA_SPEED_392_PREPARE_RUNTIME_PATH`
  override, structural pins) and move the two superseded pins in
  `tests/test_ubuntu_worker_shared_runtime.py` (schema_version 2, v2
  fingerprint formula) without weakening them
- T-392-005: Run the verification battery (bash -n, ruff, targeted unittest
  modules, full unittest discover suite, SDD validator, RED check against the
  base script materialized from 31a246a) and leave the changes uncommitted for
  orchestrator admission; the real hash-locked lock content and the resolved
  `runtime-lock.json` hash fields land in the follow-up commit after CI
  resolution

## Completion gate

- [ ] T-392-001
- [ ] T-392-002
- [ ] T-392-003
- [ ] T-392-004
- [ ] T-392-005

## Requirements traceability

- AC-001 | Task: T-392-004 | Evidence: PipHashMechanicsTests (download verifies sha256 and aborts on tampered artifact; offline install succeeds with matching hashes and fails on mismatch; environment tests, no network, green on base by design) | Coverage: COVERED
- AC-002 | Task: T-392-002,T-392-004 | Evidence: test_runtime_id_v2_formula_is_deterministic and test_any_single_byte_change_moves_the_runtime_id (executed via SEA_SPEED_392_PREPARE_RUNTIME_PATH; RED vs base) | Coverage: COVERED
- AC-003 | Task: T-392-002,T-392-004 | Evidence: test_placeholder_lock_fails_closed_before_any_mutation (exit 3, ERROR lines, no RUNTIME_CREATED) and test_complete_lock_passes_validation_until_the_root_gate | Coverage: COVERED
- AC-004 | Task: T-392-002,T-392-004 | Evidence: StructuralPinsTests — two-phase install, fail-closed ordering before root check/venv, manifest lock hash, ready-runtime lock-file/manifest checks; all RED against the base script | Coverage: COVERED
- AC-005 | Task: T-392-004,T-392-005 | Evidence: tests.test_ubuntu_worker_shared_runtime (2 moved pins, original strength), tests.test_ubuntu_worker_runtime_provenance, tests.test_ubuntu_worker_exact_updater, tests.test_ubuntu_worker_manual_install all green; full discover suite green | Coverage: COVERED

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [x] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main (1f81c5e3)
- [x] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main (1f81c5e3)
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned (hash-locked fresh creation verified on a live host after the follow-up lock commit)
- [ ] Deferred work recorded — follow-up commit lands the CI-resolved lock (real hashes + resolved_lock.sha256); prepare-runtime is intentionally fail-closed until then
- [ ] Risks resolved or explicitly accepted — RISK-001 mitigated; live-host behaviour verified post-deploy
- [ ] Waivers resolved or current — none
