# Plan: Hash-locked shared worker runtime dependency graph

- Specification: specs/392-worker-runtime-hash-lock/spec.md

## Architecture

Three coordinated pieces:

- `prepare-runtime.sh` gains a third runtime-definition input
  (`requirements-runtime.lock.txt`) and a fail-closed gate:
  `validate_runtime_lock()` runs after the fingerprint and the
  `--runtime-id-only` exit but before the root check, and rejects a missing,
  marker-less, empty or hash-incomplete lock (uv-style continuation lines are
  joined before validation) as well as schema-2 contradictions (lock hash
  mismatch, missing pytorch artifact hashes, pytorch/requirements pins absent
  from the graph). Fresh creation becomes two-phase: `pip download
  --require-hashes --only-binary=:all:` over the complete lock across both
  pinned indexes into a per-run wheelhouse, then `pip install --no-index
  --find-links <wheelhouse> --require-hashes` over a directive-stripped
  resolved copy. `verify_python` parses the complete graph from the lock file
  (requirements cross-checked), optionally verifies the manifest lock hash and
  installed-graph equality, and is reused by fresh verification, ready-reuse
  and legacy adoption; `write_manifest` records
  `requirements_lock_sha256`; `finalize_runtime` copies the lock file into the
  immutable runtime; `verify_ready_runtime` byte-compares it and runs the
  manifest-aware verification.
- `runtime-lock.json` bumps to schema 2: `resolved_lock{file,sha256}`,
  `pytorch.index_provenance`, `pytorch.pypi_index_url` and
  `pytorch.artifact_sha256{torch,torchvision}` (hash values empty in this
  commit — the empty values are part of the fail-closed placeholder state and
  are filled from the CI resolver output in the follow-up commit).
- `.github/workflows/resolve-runtime-lock.yml` compiles the graph
  (`requirements-runtime.txt` + pytorch pins from the lock json) with
  `uv pip compile --generate-hashes` against both pinned indexes and uploads
  the lock as an artifact; dispatch-only, `contents: read`, no secrets, no
  deploy steps.

## Decisions

- DEC-1: Single merged lock file (complete graph including the torch cu130
  closure) instead of a second section/file: the contract offered the choice;
  one file keeps pip download (`-r lock` across both indexes) and offline
  install (`-r resolved`) simple, avoids comment-section parsing, and the
  torch artifact hashes are additionally pinned in runtime-lock.json
  `artifact_sha256` with a cross-check against the lock lines (drift fails
  closed) so the json stays the provenance record.
- DEC-2: Fail-closed validation sits between the `--runtime-id-only` exit and
  the root check: it performs pure reads, gates every mutation path (adoption
  and fresh creation) and keeps `--runtime-id-only` root-free for CI/tests;
  the fingerprint itself validates only byte presence, so CI provenance keeps
  working while the lock is a placeholder.
- DEC-3: Two-phase download/install with `--require-hashes` on both phases and
  `--no-index` offline install: phase 1 proves every artifact's sha256 at
  download time; phase 2 re-verifies offline so nothing can re-resolve against
  an index; directive lines (`^--`) are stripped for the offline install so
  the install cannot be re-pointed.
- DEC-4: The complete graph (direct + transitive + torch) is the verification
  authority: `verify_python` builds its expected set from the lock file rather
  than the direct requirements, cross-checks the requirements pins against the
  graph, and — when a manifest is provided — asserts the manifest lock hash
  and per-package installed equality; adoption therefore fails on transitive
  drift by construction (same runtime_id ⇒ same graph).
- DEC-5: The resolver is a read-only workflow_dispatch job (checkout,
  setup-python, pinned uv, `--generate-hashes`, artifact upload): resolution
  output is reviewed before it is committed, keeping untrusted-registry
  content out of the repository until a human/orchestrator gate.
- DEC-6: `grep` joins the required-command list; the fresh-path cleanup trap
  extended to the wheelhouse so an aborted creation leaves no wheel residue.

## Affected contours

- Ubuntu Worker/relay runtime creation only:
  `deploy/worker/ubuntu/prepare-runtime.sh`,
  `deploy/worker/ubuntu/runtime-lock.json`, the new
  `requirements-runtime.lock.txt` placeholder, the new dispatch-only resolver
  workflow, the new test module, one moved pin pair in
  `tests/test_ubuntu_worker_shared_runtime.py`, and this SDD trio.
- No change to deploy workflows (deploy-*.yml), deploy-authorized.sh,
  install-*.sh, worker/**, VPS code, docs or credential material;
  requirements-runtime.txt stays byte-identical.

## Validation

- `bash -n deploy/worker/ubuntu/prepare-runtime.sh`.
- `ruff check tests/test_ubuntu_worker_runtime_hash_lock.py` (E9+F,
  `scripts/quality/ruff.toml`).
- Targeted: `tests.test_ubuntu_worker_runtime_hash_lock`,
  `tests.test_ubuntu_worker_shared_runtime`,
  `tests.test_ubuntu_worker_runtime_provenance` green.
- Executed without-root script runs: `--runtime-id-only` fingerprint; the
  placeholder lock aborts with exit 3; the complete fixture lock reaches only
  the root gate.
- Full suite `python3 -m unittest discover -s tests -p 'test_*.py'` green.
- `python3 scripts/ci/validate_sdd.py` green.
- RED check: the new module against the base script materialized via
  `git show 31a246a:...` through the module-wide `SEA_SPEED_392_PREPARE_RUNTIME_PATH`
  override — the runtime-id, fail-closed and structural pins fail RED; the pip
  mechanics tests and the complete-lock root-gate guard stay green by design
  (environment/behavior guards, stated in the module docstring).

## Runtime feedback

- RF-001: Operator actions expected: 0 for deploy; lock resolution is an
  explicit workflow_dispatch, its artifact committed after review.
- RF-002: Post-deploy evidence: `RUNTIME_CREATED runtime_id=... hash_locked=true`;
  failure paths emit `ERROR runtime lock ...` before any mutation.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: fail-closed lock validation before any mutation (exit 3 before root check, venv creation, pip and adoption), two-phase hash-verified download plus offline --no-index --require-hashes install, complete-graph verification for fresh creation, ready-reuse AND legacy adoption, artifact_sha256 cross-check between runtime-lock.json and the lock file, executed pip-mechanics and fail-closed tests, RED anchors against the base script, exact file scope with requirements-runtime.txt untouched | Validation: targeted unittest modules, executed without-root script runs, full unittest discover suite, ruff, bash -n and SDD validators green locally; script-level tests RED against the base script materialized from 31a246a via the module-wide SEA_SPEED_392_PREPARE_RUNTIME_PATH override | Residual risk: LOW — the placeholder lock keeps the fresh-creation path fail-closed (exit 3) until the orchestrator commits the CI-resolved lock with real artifact hashes in the follow-up commit; resolver output is reviewed before commit; live-host behaviour is verified after production deploy | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: R-3 | Level: integration | Priority: P0 | Evidence: PipHashMechanicsTests (fixture wheels, no network: download verifies sha256 and aborts on tampered artifact; offline install succeeds with matching hashes and fails on mismatch) — environment tests, green on base by design
- TEST-002 | Covers: R-1 | Level: unit | Priority: P0 | Evidence: test_runtime_id_v2_formula_is_deterministic, test_any_single_byte_change_moves_the_runtime_id (executed --runtime-id-only, RED vs base)
- TEST-003 | Covers: R-2 | Level: integration | Priority: P0 | Evidence: test_placeholder_lock_fails_closed_before_any_mutation (exit 3, no mutation) and test_complete_lock_passes_validation_until_the_root_gate (executed, override-selected script)
- TEST-004 | Covers: R-2,R-3,R-4 | Level: unit | Priority: P0 | Evidence: StructuralPinsTests (two-phase install, fail-closed ordering, v2 payload, manifest lock hash, ready-runtime checks) — RED vs base
- TEST-005 | Covers: R-1,R-5 | Level: unit | Priority: P1 | Evidence: schema-2 provenance pin, placeholder pin, dispatch-only resolver pin; moved shared-runtime pins keep original strength; full suite green

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: Issue #392 scope receipt (issuecomment-6050353934, OUTCOME APPROVED receipt issuecomment-6050342081)
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged host state | Retry: NO | Rollback: NONE | Evidence: validate_runtime_lock aborts exit 3 before the root check and before any venv/pip/adoption mutation; executed placeholder fail-closed run proves the ordering
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged runtime directory removed by the EXIT trap (wheelhouse cleaned as well); existing shared runtime and legacy venvs untouched | Retry: NO | Rollback: no new runtime is activated — finalize_runtime publishes atomically via mv after all verification; a failed download/install aborts before finalize | Evidence: two-phase pip download --require-hashes / offline install; RUNTIME_CREATED hash_locked=true evidence line
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: staged runtime discarded, prior runtime still active | Retry: NO | Rollback: NONE | Evidence: verify_python complete-graph check, manifest lock-hash and installed-graph equality checks inside verify_ready_runtime and finalize_runtime
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: ready marker written before mv; ready-runtime reuse path byte-compares lock, requirements and lock file
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging/wheelhouse may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: cleanup trap covers staged_root and wheelhouse
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: RUNTIME_CREATED/RUNTIME_ADOPTED/RUNTIME_REUSED evidence lines with runtime_id; execution-audit v1
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour unchanged; a failed prepare leaves the previous shared runtime active (runtime_root selection is content-addressed; no in-place mutation) | Evidence: rollback manifest
