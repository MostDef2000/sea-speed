# Spec: Objects registry extraction — api/app/objects_registry.py + api/app/passage_mirrors.py (Wave 2)

- Issue: #396
- Specification: specs/396-wave2-objects-registry/spec.md

## Product outcome

Wave 1 (specs/396-wave1-shared-kernel) carved the dependency-free kernel out
of `api/app/main.py`; the objects-registry slice is the largest remaining
self-contained block. Wave 2 carves it out with **zero behavior change**:

1. `api/app/objects_registry.py` (new) — the objects SQLite DB layer moved
   verbatim from `main.py` (base f863f1ca): `open_objects_db`,
   `prune_objects_registry`, `initialize_objects_db`, `optional_float`,
   `optional_int`, `stable_object_id`, `prune_snapshotless_objects`,
   `persist_object_event`, `import_existing_events`, `object_row_to_dict`,
   `build_objects_where`, `patch_object_record`, `delete_object_record`.
   The shared numeric coercion helpers `optional_float`/`optional_int` move
   WITH the layer (their moved callers resolve them at call time; `main.py`
   re-imports them through the seam so its remaining call sites are
   unchanged). Imports `config` constants, `identity.now_iso` and
   `store.read_json_file` exactly where the originals used them.
2. `api/app/passage_mirrors.py` (new) — the water-passage → objects-registry
   mirror layer moved verbatim: `persist_passage_object`,
   `import_existing_passages`, `_delete_passage_mirrors`,
   `reconcile_passage_mirrors`. It depends on `objects_registry` and on
   `open_passages_db`, which stays in `main.py` this wave (the water
   passages store is not in this wave's slice). `main.py` binds the
   connection factory into the mirror module immediately after its
   definition (`passage_mirrors.open_passages_db = open_passages_db`);
   the mirror module never imports `main` (import-cycle rule), and no
   caller can run before the binding (every caller lives in main.py's
   module tail or route handlers, both after the binding at import time).

`api/app/main.py` keeps every route, `open_passages_db`, the water-passages
store and all other logic; the moved names remain importable from `main` via
thin explicit re-exports under the same dual package/direct-file import
idiom waves 0-1 already use, so AST-harness suites, text-pinning suites and
the deployed module see identical behavior.

No API surface change: the 61-endpoint route table, response shapes,
schemas, defaults, limits and failure modes are unchanged (pinned by the
new `tests/test_route_table.py` fingerprint).

## User scenarios

- US-1: An operator deploys this release to the VPS; `deploy.sh` stages
  `objects_registry.py` and `passage_mirrors.py` into the release and
  activates them **before** `main.py` (mirroring the store.py/config.py/
  identity.py pattern), so the first boot of the new `main.py` finds its
  imports and the health gate passes exactly as before.
- US-2: A rollback to a pre-wave-2 release removes the live
  `objects_registry.py`/`passage_mirrors.py` cleanly (the old `main.py`
  does not import them); a staged `.next` left by an interrupted install is
  never promoted; the bootstrap capture keeps live copies next to the
  captured `main.py` so the rollback release stays bootable on its own.
- US-3: The AST-harness suites continue to exec the moved functions
  (`open_objects_db`, `persist_object_event`, `build_objects_where`,
  `persist_passage_object`, `reconcile_passage_mirrors`, ...) and pin their
  literal text — the harnesses now resolve those functions/markers from
  `objects_registry.py`/`passage_mirrors.py` with fallback to `main.py`,
  without weakening any assertion.
- US-4: A test loads `main.py` standalone (spec_from_file_location with
  mocked `fastapi`/`Path.mkdir`/`sqlite3`); both new modules import safely
  under the same mocks, the `open_passages_db` sentinel is bound by main's
  module-level injection line before any mirror call can run, and no second
  module instance of any dependency is created inside one process (dual
  idiom everywhere, one canonical instance per import mode).

## Scope

- `api/app/objects_registry.py` (new): the 13 functions listed above, moved
  verbatim by byte-range copy.
- `api/app/passage_mirrors.py` (new): the 4 mirror functions, moved
  verbatim by byte-range copy, plus the `open_passages_db` sentinel binding.
- `api/app/main.py`: remove the moved blocks; add the wave-2 seam (thin
  explicit re-exports, dual idiom, no star imports) and the one-line
  `open_passages_db` injection; drop the now-unused `import hashlib`.
  Routes and all other logic untouched this wave.
- `deploy/vps/deploy.sh`: `OBJECTS_REGISTRY_TARGET`/`PASSAGE_MIRRORS_TARGET`
  joining all seven wave-1-pattern sites (targets, `release_complete`,
  download required list, release install, bootstrap capture, install
  staging, activation before `main.py` — see plan Decisions D-1).
- Tests: harness reader extensions in `tests/test_api_contract.py`,
  `tests/test_unified_registry.py`, `tests/test_storage_retention.py`,
  `tests/test_water_passage.py`, `tests/test_line_crossing.py`; synthetic
  release fixtures in `tests/test_vps_deploy_transaction.py`; new route-table
  fingerprint `tests/test_route_table.py` (61 frozen routes).
- SDD: this trio; one-line grandfather entry for the #396 wave pair in
  `scripts/ci/validate_sdd.py` (see plan Decisions D-2).

Out of scope: the water-passages store (`open_passages_db`,
`prune_water_passages`, `initialize_water_passages_db`, `cleanup_passage_media`,
`passage_row_to_dict`, `_validate_passage_payload`, `upsert_water_passage`,
`list_water_passages` stay in `main.py` this wave), routes/handlers, sweep
(`sweep_events_media`), `worker/`, `frontend/`, `.github/`, exact-artifact
manifest changes, any behavior/limit/schema change.

## Requirements

- R-1: `api/app/objects_registry.py` owns the objects DB layer verbatim
  (main.py:170-352, 852-917, 1622-1679 at base f863f1ca): `open_objects_db`
  (with its `@contextmanager` decorator), `prune_objects_registry`,
  `initialize_objects_db`, `optional_float`, `optional_int`,
  `stable_object_id`, `prune_snapshotless_objects`, `persist_object_event`,
  `import_existing_events`, `object_row_to_dict`, `build_objects_where`,
  `patch_object_record`, `delete_object_record` — byte-identical bodies,
  imported constants from `config`, `now_iso` from `identity`,
  `read_json_file` from `store`.
- R-2: `api/app/passage_mirrors.py` owns `persist_passage_object`,
  `import_existing_passages`, `_delete_passage_mirrors`,
  `reconcile_passage_mirrors` (main.py:355-431, 439-474 at base) verbatim;
  it imports `objects_registry` names and `identity.now_iso` through the
  same dual idiom, holds an `open_passages_db = None` module binding, and
  never imports `main`.
- R-3: `api/app/main.py` re-exports every moved name explicitly (no star
  imports) under the dual idiom, keeps its module-level init calls
  (`initialize_objects_db`, `import_existing_events`,
  `import_existing_passages`, `reconcile_passage_mirrors`) in place, and
  binds `passage_mirrors.open_passages_db = open_passages_db` immediately
  after the `open_passages_db` definition, before any caller runs.
- R-4: `deploy/vps/deploy.sh` — `OBJECTS_REGISTRY_TARGET`/
  `PASSAGE_MIRRORS_TARGET` defined next to `API_TARGET`; both files join
  `release_complete`, the download required list and the release install;
  activation stages and promotes them **before** `main.py` bound to the
  selected release's content (staged `.next` promoted only when the release
  ships the file; otherwise the live copy and stale `.next` are removed —
  the store.py soft pattern); the bootstrap capture keeps live copies with
  the captured `main.py` when present.
- R-5: The AST/text harnesses that pin moved functions or literals
  (`tests/test_api_contract.py`, `tests/test_unified_registry.py`,
  `tests/test_storage_retention.py`, `tests/test_water_passage.py`,
  `tests/test_line_crossing.py`) resolve them from the new modules with
  fallback to `main.py` so the pins hold on both the base and head trees;
  no assertion is weakened. `tests/test_vps_deploy_transaction.py`
  synthetic releases carry both new modules so release completeness stays
  satisfiable. `tests/test_route_table.py` freezes the 61-route table.

## Acceptance criteria

- AC-001: The full unittest suite is green on head with the new route-table
  test included (expected 908 tests / 4 skipped versus the 907/4 baseline).
- AC-002: `scripts/ci/validate_repo.py` passes on head (new `api/app/*.py`
  files admitted; `api/app/main.py` still required and present).
- AC-003: `deploy/vps/deploy.sh` carries both new modules through all seven
  wave-1-pattern sites (targets, `release_complete`, download required list,
  release install, bootstrap capture, install staging `.next`, activation
  before `main.py` with the store.py soft pattern); `bash -n` passes and the
  VPS deploy transaction suite stays green.
- AC-004: The moved functions remain reachable through `main` and are
  behavior-identical: harness-executed objects/mirrors tests pass against
  the extracted sources with the same injected namespaces (byte-identity
  audit of all 17 moved regions against the base commit passes).
- AC-005: Both new modules are import-safe standalone and under the
  roi-normalization mock context; `compile()`/`ast.parse` smoke passes for
  both; the `open_passages_db` injection binds before any mirror call.
- AC-006: No behavior change: the route table is pinned at exactly 61
  `@app.*` endpoints, response shapes/defaults/limits untouched; the only
  main.py edits are removal of the moved blocks, the wave-2 seam, the
  injection line and the dropped `import hashlib`.

## Runtime feedback

- RF-001: Operator actions expected: 1 — the VPS deploy of this wave rides
  the merge (DEPLOY-TRIGGER, полоса A); deploy.sh stages the two new modules
  before `main.py`, restarts and runs the origin/public health gate;
  rollback removes both modules when returning to a pre-wave-2 release.
- RF-002: Failure evidence: a missing `objects_registry.py`/
  `passage_mirrors.py` in a release fails in `release_complete`/download
  BEFORE any live source mutation; a failed activation health gate rolls
  the full source set back via the existing install_release(rollback) path.

## NFR assessment

- NFR-001 | Area: reliability | Target: zero behavior change on the VPS — boot ordering identical (new modules activate before main.py, open_passages_db bound before any mirror call), the 61-endpoint route table and response shapes unchanged | Validation: full suite green incl. the new 61-route fingerprint test; route/logic diff of main.py limited to moved blocks + seam + injection; deploy transaction suite green | Evidence: tests/test_route_table.py, tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-002 | Area: compatibility | Target: AST-harness and text-pinning suites keep working without weakened assertions; multi-source readers resolve moved functions/markers from the new modules with fallback to main so the base tree stays clean | Validation: updated harness suites green on head (127 focused tests observed); baseline suite run for comparison | Evidence: tests/test_api_contract.py, tests/test_unified_registry.py, tests/test_storage_retention.py, tests/test_water_passage.py, tests/test_line_crossing.py | Status: PASS
- NFR-003 | Area: deployability/rollback | Target: a release missing either new module can never reach activation (fails in release completeness/download), and a rollback to a pre-wave-2 release removes both modules while keeping the old main bootable; bootstrap capture stays bootable | Validation: deploy.sh seven-site extension + soft activation pattern; synthetic-release tests carry the new files | Evidence: tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-004 | Area: maintainability | Target: objects_registry.py depends only on config/identity/store/fastapi; passage_mirrors.py depends only on objects_registry/identity and receives open_passages_db by binding (never imports main — import-cycle rule); one canonical module instance per import mode | Validation: module source review; verbatim byte-range extraction with automated byte-identity audit; standalone import smoke | Evidence: api/app/objects_registry.py, api/app/passage_mirrors.py | Status: PASS
- NFR-005 | Area: security | Target: object/passage persistence primitives move by byte-range copy with no semantic drift; no new env reads, no secret-shaped literals introduced; hashlib usage confined to stable_object_id in the new module | Validation: byte-identity audit of the 17 moved regions; ruff (E9/F) clean on head; suite green | Evidence: /tmp extraction audit output recorded in the wave report; scripts/quality/ruff.toml run | Status: PASS

## Deviations from the work order

- deploy.sh scope: the work order's "four sites, no more no less" was an
  orchestrator-wording error (see plan Decision D-1); the granted decision
  extends both modules through all seven sites of the wave-1
  config/identity pattern (targets, release_complete, download required
  list, release install, bootstrap capture, install staging, activation).
- `optional_float`/`optional_int` move into `objects_registry.py` rather
  than staying in `main.py`: the moved callers (`build_objects_where`,
  `persist_passage_object`, retention helpers) resolve them at call time,
  and `main.py` re-imports them through the seam, so behavior is
  identical; this follows the wave-1 "move with the layer + re-export"
  precedent.
- `scripts/ci/validate_sdd.py` gains a grandfather entry for the #396 wave
  pair (plan Decision D-2), authorized for this wave only.
