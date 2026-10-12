# Spec: Water passages extraction — api/app/water_passages.py (Wave 3)

- Issue: #396
- Specification: specs/396-wave3-water-passages/spec.md

## Product outcome

Wave 1 (specs/396-wave1-shared-kernel) carved the dependency-free kernel out
of `api/app/main.py`; wave 2 (specs/396-wave2-objects-registry) carved out the
objects registry and the passage→object mirror layer. Wave 3 carves out the
water-passages store — the slice the wave-2 contract explicitly deferred —
with **zero behavior change**:

1. `api/app/water_passages.py` (new) — the water-passages SQLite store moved
   verbatim from `main.py` (base 38595d32): `open_passages_db` (with its
   `@contextmanager` decorator), `cleanup_passage_media`,
   `prune_water_passages`, `initialize_water_passages_db`,
   `_validate_passage_payload`, `passage_row_to_dict`,
   `upsert_water_passage`, `list_water_passages`. Imports `config`
   constants, `identity.now_iso`, `objects_registry.optional_float` /
   `optional_int` and `passage_mirrors._delete_passage_mirrors` exactly where
   the originals resolved them.
2. `api/app/main.py` keeps every route and all other logic; the moved names
   remain importable from `main` via the established thin explicit re-export
   seam (dual package/direct-file idiom, no star imports), so AST-harness
   suites, text-pinning suites and the deployed module see identical
   behavior.

Slice-boundary decision (deviation note D-1): `clean_points_list` and the ROI
normalization helpers/constants (`_is_normalized_point`, `_clean_norm_points`,
`_infer_legacy_ref_w_h`, `_normalize_from_absolute`,
`_denormalize_to_absolute`, `_normalize_legacy_polygon`, `DEFAULT_ROI_REF_W/H`,
`LEGACY_ROI_W/H`) stay in `main.py`. The work order listed them "if their
closure is water-passage-specific"; dependency tracing shows their only
callers are the analytics ROI / speed-lines / crossing-line handlers, so
their closure is analytics-specific, not water-passage-specific. Moving them
would have broken that closure rule without any ownership gain.

`open_passages_db` relocation + binding semantics (deviation note D-2): the
factory moves into `water_passages.py`; `passage_mirrors` keeps its wave-2
`open_passages_db = None` sentinel and `main.py` keeps the wave-2 binding
line `passage_mirrors.open_passages_db = open_passages_db` **byte-identical**
(now binding the factory imported from the new module). The mirror module
cannot import `water_passages` directly because `prune_water_passages` calls
`_delete_passage_mirrors` — that edge would close an import cycle — so the
sentinel+binding design from wave 2 remains the only cycle-free shape, and
the binding still executes at main's import time, before any mirror caller
(every caller lives in main.py's module tail or route handlers).

No API surface change: the 61-endpoint route table, response shapes,
schemas, defaults, limits and failure modes are unchanged (pinned by
`tests/test_route_table.py`, extended this wave to also pin handler function
names).

## User scenarios

- US-1: An operator deploys this release to the VPS; `deploy.sh` stages
  `water_passages.py` into the release and activates it **before** `main.py`
  (mirroring the store.py/config.py/identity.py/objects_registry.py/
  passage_mirrors.py pattern), so the first boot of the new `main.py` finds
  its imports and the health gate passes exactly as before.
- US-2: A rollback to a pre-wave-3 release removes the live
  `water_passages.py` cleanly (the old `main.py` does not import it); a
  staged `.next` left by an interrupted install is never promoted; the
  bootstrap capture keeps a live copy next to the captured `main.py` so the
  rollback release stays bootable on its own.
- US-3: The AST-harness suites continue to exec the moved functions
  (`open_passages_db`, `prune_water_passages`, `initialize_water_passages_db`,
  `upsert_water_passage`, ...) and pin their literal text — the harnesses now
  resolve those functions/markers from `water_passages.py` with fallback to
  `main.py`, without weakening any assertion.
- US-4: A test loads `main.py` standalone (spec_from_file_location with
  mocked `fastapi`/`Path.mkdir`/`sqlite3.connect`); the new module imports
  safely under the same mocks, the binding line re-binds the factory into
  `passage_mirrors` before any mirror call can run, and no second module
  instance of any dependency is created inside one process (dual idiom
  everywhere, one canonical instance per import mode).

## Scope

- `api/app/water_passages.py` (new): the 8 functions listed above, moved
  verbatim by scripted byte-range copy.
- `api/app/main.py`: remove the moved blocks; add the wave-3 seam (thin
  explicit re-exports, dual idiom, no star imports); keep the binding line
  byte-identical (comment updated to describe the wave-3 shape); drop the
  now-unused `import sqlite3` and `from contextlib import contextmanager`
  (their only consumers moved; wave-2 `import hashlib` precedent). Routes
  and all other logic untouched this wave.
- `deploy/vps/deploy.sh`: `WATER_PASSAGES_TARGET` joining all seven sites of
  the wave-1/wave-2 pattern (target var, `release_complete`, download
  required list, release install, bootstrap capture, install staging `.next`,
  activation before `main.py` — see plan Decision D-3).
- Tests: harness reader extensions in `tests/test_water_passage.py`,
  `tests/test_storage_retention.py`, `tests/test_unified_registry.py`,
  `tests/test_api_contract.py` (`api_sources()` join + function walk — the
  "passage snapshot is required" pin moved with `upsert_water_passage`),
  `tests/test_line_crossing.py`, `tests/test_analytics_profiles.py`;
  synthetic release fixture in `tests/test_vps_deploy_transaction.py`.
- Hardening A (wave-2 peer-review follow-up, declared in the wave-3 Change
  Contract): `tests/test_route_table.py` fingerprint extended to pin the
  handler function name per route — `(handler_name, method, path)` — still
  import-free AST, still exactly 1 test method.
- Hardening B (wave-2 peer-review follow-up): `scripts/quality/
  build_exact_artifacts.py` vps required list converges with deploy.sh —
  `api/app/store.py`, `config.py`, `identity.py`, `objects_registry.py`,
  `passage_mirrors.py`, `water_passages.py` join `api/app/main.py` so a
  release payload built from exact-artifact components satisfies deploy.sh
  `download_release`'s required checks (verified by building and validating
  the artifacts in the wave battery).
- SDD: this trio; `scripts/ci/validate_sdd.py` grandfather set gains
  `396-wave3-water-passages` (one entry; exact-set equality otherwise fails
  the battery — see plan Decision D-4).

Out of scope: `clean_points_list` and the ROI normalization helpers/constants
(closure is analytics-specific — see D-1), routes/handlers, sweep
(`sweep_events_media`), analytics/state layers, `worker/`, `frontend/`,
`.github/`, any behavior/limit/schema change.

## Requirements

- R-1: `api/app/water_passages.py` owns the water-passages store verbatim
  (main.py:269-606 at base 38595d32): `open_passages_db` (with its
  `@contextmanager` decorator), `cleanup_passage_media`,
  `prune_water_passages`, `initialize_water_passages_db`,
  `_validate_passage_payload`, `passage_row_to_dict`,
  `upsert_water_passage`, `list_water_passages` — byte-identical bodies,
  imported constants from `config`, `now_iso` from `identity`,
  `optional_float`/`optional_int` from `objects_registry`,
  `_delete_passage_mirrors` from `passage_mirrors`.
- R-2: `api/app/main.py` re-exports every moved name explicitly (no star
  imports) under the dual idiom, keeps its module-level init calls
  (`initialize_water_passages_db` and the mirror backfill calls) in place,
  and keeps `passage_mirrors.open_passages_db = open_passages_db` running at
  import time before any mirror caller, with the binding line itself
  byte-identical to wave 2.
- R-3: `deploy/vps/deploy.sh` — `WATER_PASSAGES_TARGET` defined next to
  `API_TARGET`; the file joins `release_complete`, the download required
  list and the release install; activation stages and promotes it **before**
  `main.py` bound to the selected release's content (staged `.next` promoted
  only when the release ships the file; otherwise the live copy and stale
  `.next` are removed — the store.py soft pattern); the bootstrap capture
  keeps a live copy with the captured `main.py` when present.
- R-4: The AST/text harnesses that pin moved functions or literals
  (`tests/test_water_passage.py`, `tests/test_storage_retention.py`,
  `tests/test_unified_registry.py`, `tests/test_api_contract.py`,
  `tests/test_line_crossing.py`, `tests/test_analytics_profiles.py`) resolve
  them from the new module with fallback to `main.py` so the pins hold on
  both the base and head trees; no assertion is weakened.
  `tests/test_vps_deploy_transaction.py` synthetic releases carry
  `water_passages.py` so release completeness stays satisfiable.
- R-5: `tests/test_route_table.py` freezes the 61-route table WITH handler
  function names (wave-3 hardening A); `scripts/quality/build_exact_artifacts.py`
  vps required inventory converges with deploy.sh (wave-3 hardening B);
  `scripts/ci/validate_sdd.py` grandfathers the #396 wave set (one entry).

## Acceptance criteria

- AC-001: The full unittest suite is green on head with the test count equal
  to the 908/4 baseline (route-table test still exactly 1 method).
- AC-002: `scripts/ci/validate_repo.py` passes on head (new
  `api/app/water_passages.py` admitted; `api/app/main.py` still required and
  present); `scripts/ci/validate_sdd.py` passes with the grandfathered wave
  set.
- AC-003: `deploy/vps/deploy.sh` carries the new module through all seven
  wave-1-pattern sites (target var, `release_complete`, download required
  list, release install, bootstrap capture, install staging `.next`,
  activation before `main.py` with the store.py soft pattern); `bash -n`
  passes and the VPS deploy transaction suite stays green.
- AC-004: The moved functions are behavior-identical: harness-executed
  water-passage tests pass against the extracted source with the same
  injected namespaces (byte-identity audit of all 8 moved regions plus the
  binding line against the base commit passes).
- AC-005: The new module is import-safe in package mode and under the
  roi-normalization standalone-exec mock context; `compile()`/`ast.parse`
  smoke passes; the binding line binds the moved factory before any mirror
  call in both import modes.
- AC-006: No behavior change: the route table is pinned at exactly 61
  `@app.*` endpoints with unchanged handler bindings, response
  shapes/defaults/limits untouched; the only main.py edits are removal of
  the moved blocks, the wave-3 seam, the binding comment update and the two
  dropped imports.
- AC-007: Hardening A — the route fingerprint pins `(handler_name, method,
  path)` for all 61 endpoints and the file still contains exactly 1 test
  method.
- AC-008: Hardening B — a vps exact artifact built from the converged
  required list contains every `api/app/*` module deploy.sh requires, and
  `validate_exact_artifacts.py` passes on the built manifest.

## Runtime feedback

- RF-001: Operator actions expected: 1 — the VPS deploy of this wave rides
  the merge (DEPLOY-TRIGGER, полоса A); deploy.sh stages the new module
  before `main.py`, restarts and runs the origin/public health gate;
  rollback removes the module when returning to a pre-wave-3 release.
- RF-002: Failure evidence: a missing `water_passages.py` in a release fails
  in `release_complete`/download BEFORE any live source mutation; a failed
  activation health gate rolls the full source set back via the existing
  install_release(rollback) path.

## NFR assessment

- NFR-001 | Area: reliability | Target: zero behavior change on the VPS — boot ordering identical (water_passages.py activates before main.py, open_passages_db bound before any mirror call), the 61-endpoint route table with unchanged handler bindings and response shapes | Validation: full suite green incl. the route-name-pinned fingerprint test; main.py diff limited to moved blocks + seam + binding comment + dropped imports; deploy transaction suite green | Evidence: tests/test_route_table.py, tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-002 | Area: compatibility | Target: AST-harness and text-pinning suites keep working without weakened assertions; multi-source readers resolve moved functions/markers from the new module with fallback to main so the base tree stays clean | Validation: updated harness suites green on head (124 focused tests observed); baseline suite run for comparison | Evidence: tests/test_api_contract.py, tests/test_unified_registry.py, tests/test_storage_retention.py, tests/test_water_passage.py, tests/test_line_crossing.py, tests/test_analytics_profiles.py | Status: PASS
- NFR-003 | Area: deployability/rollback | Target: a release missing water_passages.py can never reach activation (fails in release completeness/download), and a rollback to a pre-wave-3 release removes the module while keeping the old main bootable; bootstrap capture stays bootable | Validation: deploy.sh seven-site extension + soft activation pattern; synthetic-release tests carry the new file | Evidence: tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-004 | Area: maintainability | Target: water_passages.py depends only on config/identity/objects_registry/passage_mirrors/fastapi; it never imports main (import-cycle rule); the passage_mirrors sentinel + main binding line is kept because prune_water_passages → _delete_passage_mirrors would close a cycle; one canonical module instance per import mode | Validation: module source review; verbatim byte-range extraction with automated byte-identity audit; package-import and standalone smoke | Evidence: api/app/water_passages.py | Status: PASS
- NFR-005 | Area: security | Target: water-passage persistence primitives move by byte-range copy with no semantic drift; no new env reads, no secret-shaped literals introduced; SQL and validation limits unchanged | Validation: byte-identity audit of the 8 moved regions; ruff (E9/F) clean on head; suite green | Evidence: byte-identity audit output recorded in the wave report; scripts/quality/ruff.toml run | Status: PASS
