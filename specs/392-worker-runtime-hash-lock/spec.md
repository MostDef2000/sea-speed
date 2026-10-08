# Spec: Hash-locked shared worker runtime dependency graph

- Issue: #392
- Specification: specs/392-worker-runtime-hash-lock/spec.md

## Product outcome

The shared worker runtime is created by `deploy/worker/ubuntu/prepare-runtime.sh`
from `runtime-lock.json` and `requirements-runtime.txt`, but the pip
installation carries no artifact hashes: fresh creation runs
`pip install` directly against the PyTorch cu130 index and the default PyPI
index, so any artifact that upstream re-publishes (or any transitive dependency
that resolves differently) silently enters the runtime while the runtime_id
stays unchanged. Verification covers only the direct pins, not the transitive
graph, and the manifest records no lock-graph fingerprint.

This change makes the runtime dependency graph hash-locked and fail-closed:
a new complete lock file (`requirements-runtime.lock.txt`, resolved by a
dispatch-only CI workflow with `--generate-hashes`) becomes the third
runtime-definition input — it changes the runtime_id, its absence or
incompleteness aborts the prepare step, fresh creation downloads every
artifact with verified sha256 hashes and installs strictly offline from the
verified wheel set, and runtime verification enforces the complete locked
graph (direct + transitive + torch) for fresh creation, ready-reuse checks and
legacy adoption alike.

## User scenarios

- US-1: An artifact in the dependency graph is republished with different
  bytes; the fresh-creation download phase fails closed on the sha256
  verification instead of installing the drifted artifact.
- US-2: The lock file is missing, lacks the schema marker, is empty
  (placeholder state), or contains any requirement line without a sha256
  hash; the prepare step aborts with exit 3 and an ERROR line before any
  mutation (no venv, no pip, no adoption).
- US-3: A legacy per-release venv matches all direct pins but drifts on a
  transitive dependency; adoption fails because verification now enforces the
  complete locked graph (same runtime_id ⇒ same graph).
- US-4: The operator triggers `resolve-runtime-lock.yml` (workflow_dispatch);
  the workflow compiles the requirements graph plus the declared pytorch cu130
  pins with `--generate-hashes` and uploads the lock file as an artifact — no
  repository write, no secrets, no deploy logic.

## Requirements

- R-1: runtime_id v2 — SHA-256 over runtime-lock.json bytes ‖ b"\0" ‖
  requirements-runtime.txt bytes ‖ b"\0" ‖ requirements-runtime.lock.txt
  bytes; `runtime-lock.json` bumps to `"schema_version": 2` with a
  `resolved_lock` section (`{"file": "requirements-runtime.lock.txt",
  "sha256": ...}`) and explicit pytorch provenance (`index_provenance`,
  `pypi_index_url`, per-package `artifact_sha256` for torch/torchvision,
  filled by the CI resolution in the follow-up commit).
- R-2: prepare-runtime.sh fails closed (exit 3 with an ERROR line) before any
  mutation when the lock file is absent, lacks the schema marker, yields an
  empty graph, contains a requirement line without ` --hash=sha256:`, or when
  the runtime-lock.json schema-2 sections are missing/contradictory (lock
  hash mismatch, missing pytorch artifact hashes, pytorch pins absent from the
  graph, requirements pins absent from the graph). `--runtime-id-only` keeps
  working without root and without semantic validation (fingerprint of bytes).
- R-3: Fresh creation becomes two-phase fail-closed: (1) `pip download
  --only-binary=:all: --require-hashes` over the lock file across both pinned
  indexes (cu130 from runtime-lock.json, PyPI as `pypi_index_url`) into a
  per-run wheelhouse — every artifact hash is verified at download time;
  (2) `pip install --no-index --find-links <wheelhouse> --require-hashes`
  over a directive-stripped resolved copy of the lock file. No direct index
  install remains.
- R-4: `verify_python` enforces the complete lock graph (direct + transitive +
  torch, parsed from the lock file, requirements cross-checked against it);
  `write_manifest` records `requirements_lock_sha256`;
  `verify_ready_runtime` extends to the lock file (presence + byte compare)
  and verifies the manifest lock hash plus installed-graph equality; the
  adoption path inherits the same complete-graph enforcement.
- R-5: `.github/workflows/resolve-runtime-lock.yml` is workflow_dispatch-only
  with `contents: read`, builds its resolution input from runtime-lock.json,
  compiles with `uv pip compile --generate-hashes` against both pinned indexes
  and uploads `requirements-runtime.lock.txt` as an artifact; no checkout
  write, no secrets, no deploy steps. `requirements-runtime.txt` stays
  byte-identical; the placeholder lock file carries the schema marker and no
  pins, and this unit leaves the changes uncommitted for orchestrator
  admission (real hashes land in the follow-up commit after CI resolution).

## Acceptance criteria

- AC-001: Executed pip-mechanics proof: `pip download --require-hashes` over
  locally built fixture wheels verifies a matching sha256 and aborts on a
  tampered artifact; `pip install --no-index --find-links --require-hashes`
  installs with matching hashes and aborts on mismatch (environment tests, no
  network; green against base by design).
- AC-002: Executed runtime_id v2 proof via `--runtime-id-only` (module-wide
  `SEA_SPEED_392_PREPARE_RUNTIME_PATH` override): identical inputs produce the
  identical id, and changing one byte in any of the three definition files
  moves the id; the id equals the independently computed v2 fingerprint.
- AC-003: Executed fail-closed proof: the placeholder lock aborts the prepare
  step with exit 3 and ERROR lines before any mutation; a complete fixture
  lock passes validation and reaches only the root gate.
- AC-004: Structural pins: two-phase install (`--require-hashes` on both pip
  invocations, `--no-index` + `--find-links` on install, direct index install
  removed), fail-closed validation ordering before the root check and venv
  creation, manifest `requirements_lock_sha256`, ready-runtime lock-file and
  manifest checks — all RED against the base script.
- AC-005: Pre-existing runtime suites (shared runtime, provenance, exact
  updater, manual install) stay green; the two moved pins
  (`schema_version` 2, v2 fingerprint formula) keep their original strength.

## Runtime feedback

- RF-001: Operator actions expected: 0 for deploy; the lock resolution is an
  operator-triggered workflow_dispatch whose artifact the orchestrator
  commits in the follow-up commit.
- RF-002: Failure evidence: `ERROR runtime lock ...` lines with exit 3 before
  any mutation; `RUNTIME_CREATED runtime_id=... hash_locked=true` on success.

## NFR assessment

- NFR-001 | Area: security/supply-chain | Target: every artifact entering the shared runtime is hash-verified against the committed lock graph; no direct index install remains | Validation: executed pip download/install hash-mechanics tests over fixture wheels; structural pins for --require-hashes on both phases and --no-index offline install; RED against the base script | Evidence: PipHashMechanicsTests, StructuralPinsTests | Status: PASS
- NFR-002 | Area: reliability | Target: a missing, marker-less, empty or incomplete lock aborts the prepare step closed before any mutation | Validation: executed placeholder fail-closed run (exit 3 before root/venv/pip) plus complete-lock fixture reaching only the root gate | Evidence: test_placeholder_lock_fails_closed_before_any_mutation, test_complete_lock_passes_validation_until_the_root_gate | Status: PASS
- NFR-003 | Area: integrity | Target: runtime_id covers all three definition bytes deterministically; manifest fingerprints the lock file | Validation: executed v2 formula/determinism/byte-flip tests; manifest field pin | Evidence: RuntimeIdAndLockTests, test_manifest_records_lock_hash_and_finalizes_lock_file | Status: PASS
- NFR-004 | Area: maintainability | Target: single-source provenance — index URLs read from runtime-lock.json, resolver input derived from the same lock, requirements-runtime.txt untouched | Validation: structural pins (schema-2 sections, workflow input built from the lock) and exact-diff review | Evidence: test_runtime_lock_json_schema_2_carries_provenance, test_resolver_workflow_is_dispatch_only_without_deploy_logic | Status: PASS
- NFR-005 | Area: reversibility | Target: the change reverts cleanly; existing runtimes stay valid for their v1 runtime_id directories while new activations derive v2 ids | Validation: diff scope review; pre-existing updater/manual-install/provenance pins green unchanged | Evidence: full unittest discover suite green | Status: PASS
