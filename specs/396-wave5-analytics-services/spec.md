# Spec: Analytics services extraction — api/app/analytics.py (Wave 5)

- Issue: #396
- Specification: specs/396-wave5-analytics-services/spec.md

## Product outcome

Waves 1-4 (specs/396-wave1-shared-kernel, 396-wave2-objects-registry,
396-wave3-water-passages, 396-wave4-camera-preview) carved the dependency-free
kernel, the objects registry + passage mirror layer, the water-passages store
and the camera-preview service out of `api/app/main.py`. Wave 5 carves out the
analytics services slice — events sweep, camera-state/analytics state layer,
ROI/point-normalization helpers and the crossing-line/crossings services —
with **zero behavior change**:

1. `api/app/analytics.py` (new) — 27 names moved verbatim from `main.py`
   (base beea1067; 388 body lines in three regions), 18 functions + 9
   constants:
   - events media sweep: `EVENTS_MEDIA_GRACE_SECONDS`,
     `EVENTS_SWEEP_INTERVAL_SECONDS`, `_events_sweep_state`,
     `sweep_events_media` (main.py:286-329);
   - analytics state layer + the wave-3-deferred ROI helpers:
     `default_state`, `analytics_data_file`, `analytics_default_state`,
     `analytics_state`, `clean_points_list`, `DEFAULT_ROI_REF_W`,
     `DEFAULT_ROI_REF_H`, `LEGACY_ROI_W`, `LEGACY_ROI_H`,
     `_is_normalized_point`, `_clean_norm_points`, `_infer_legacy_ref_w_h`,
     `_normalize_from_absolute`, `_denormalize_to_absolute`,
     `_normalize_legacy_polygon` (main.py:342-511);
   - crossing services: `get_analytics_crossing_line`,
     `post_analytics_crossing_line`, `CROSSING_DIRECTIONS`,
     `append_crossing_record`, `post_analytics_crossing`, `VLZ_TIMEZONE`,
     `_vlz_day_bounds`, `get_analytics_crossings_summary`
     (main.py:1051-1218).
   Imports exactly what the originals resolved at call time: constants from
   `config`, `analytics_identity` and `now_iso` from `identity` (wave-1
   shared kernel), `open_objects_db`/`optional_float`/`optional_int`/
   `persist_object_event` from `objects_registry`,
   `read_json_file`/`write_json_file` from `store`, `fastapi.HTTPException`
   and stdlib — through the established dual package/direct-file idiom.
2. `api/app/main.py` keeps every route and all other logic (61 endpoints
   unchanged); the moved names remain importable from `main` via the
   established thin explicit re-export seam (wave-5 try/except block, dual
   idiom, no star imports), so AST-harness suites, text-pinning suites and
   the deployed module see identical behavior.

State-closure decision (deviation note D-1 — the wave-5 work order's
primary hazard): the sweep found exactly one module-level mutable object in
the slice, `_events_sweep_state` (a plain dict holding the last sweep
timestamps). It is referenced **exclusively** by `sweep_events_media` (grep
over the whole repo: no reader, no test, no staying route touches it), so it
is camera/analytics-slice-exclusive and moves with the slice — no
sentinel/injection is needed (the `passage_mirrors.open_passages_db` binding
pattern from wave 2 has no counterpart here). No locks/deques live in the
slice (the ROAD_LIVE/WATER_LIVE locks+deques belong to the live-stream slice,
which stays in `main.py`). All other moved module objects are immutable
constants (`CROSSING_DIRECTIONS`, `VLZ_TIMEZONE`, `DEFAULT_ROI_REF_W/H`,
`LEGACY_ROI_W/H`, `EVENTS_MEDIA_GRACE_SECONDS`,
`EVENTS_SWEEP_INTERVAL_SECONDS`).

Slice boundary decision (deviation note D-2): the ROI/point-normalization
helpers (`clean_points_list`, `_is_normalized_point`, `_clean_norm_points`,
`_infer_legacy_ref_w_h`, `_normalize_from_absolute`,
`_denormalize_to_absolute`, `_normalize_legacy_polygon`) were deferred in
wave 3 on the assumption that non-analytics callers existed. Re-verification
on the wave-5 base shows every caller is inside the moving slice: the
analytics ROI routes (`get/post_analytics_roi`), the speed-lines routes and
the crossing-line service functions. `get_cam1_roi`/`post_cam1_roi` delegate
to `get/post_analytics_roi`, which move. NO staying code calls them, so they
move with the slice instead of being duplicated in `main.py`.

Dependency closure (deviation note D-7 — DEFECT-1 fix): the byte-identity
audit verifies the moved bodies but not dependency closure; the first
battery caught `now_iso()` used by `post_analytics_crossing_line`,
`post_analytics_crossing` and `get_analytics_crossings_summary` without a
module import (F821 at call time). Fix: `now_iso` is imported from
`identity` in both import idioms of `analytics.py` (it stays owned by
`identity.py`, the wave-1 shared kernel — never moved). An AST-based
closure audit now compiles every moved function's global-name usage against
the module's imports/definitions (18/18 resolve) and ruff F-rules run clean
on the whole tree, which also surfaced the dead `typing.List` import in
`main.py` (its consumers moved) — dropped with the other dead imports.

No API surface change: the 61-endpoint route table, response shapes,
schemas, defaults, limits and failure modes are unchanged (pinned by
`tests/test_route_table.py`'s frozen fingerprint). The analytics route
handlers stay in `main.py` and delegate to the moved service functions
through the seam exactly as before.

## User scenarios

- US-1: An operator deploys this release to the VPS; `deploy.sh` stages
  `analytics.py` into the release and activates it **before** `main.py`
  (mirroring the store.py/config.py/identity.py/objects_registry.py/
  passage_mirrors.py/water_passages.py/camera_preview.py pattern), so the
  first boot of the new `main.py` finds its imports and the health gate
  passes exactly as before.
- US-2: A rollback to a pre-wave-5 release removes the live `analytics.py`
  cleanly (the old `main.py` does not import it); a staged `.next` left by
  an interrupted install is never promoted; the bootstrap capture keeps a
  live copy next to the captured `main.py` so the rollback release stays
  bootable on its own.
- US-3: The text-pinning and AST-harness suites keep reading the analytics
  code: their source walks now join `analytics.py` (right after
  `water_passages.py`, before `identity.py`), so definition pins, the ROI
  normalization pins and the crossing-summary VLZ pins resolve against the
  module that owns them, without weakening any assertion.
- US-4: A test loads `main.py` standalone (spec_from_file_location with
  mocked `fastapi`/`Path.mkdir`/`sqlite3.connect`); the new module imports
  safely under the same mocks and no second module instance of any
  dependency is created inside one process (dual idiom everywhere, one
  canonical instance per import mode).

## Scope

- `api/app/analytics.py` (new): the 27 names listed above, moved verbatim
  by scripted byte-range copy (388 body lines).
- `api/app/main.py`: remove the moved blocks (keeping the
  `passage_mirrors.open_passages_db` binding and the module-tail init calls
  in place); add the wave-5 seam (thin explicit re-exports, dual idiom, no
  star imports); drop the now-unused config seam names (`STATE_FILE`,
  `EVENTS_FILE`, `ROI_FILE`, `SPEED_CONFIG_FILE`, `SPEED_LINES_FILE`,
  `DATA_DIR`, `CROSSINGS_STORE_LIMIT`), the now-unused `date`/`timedelta`
  datetime names and the now-unused `typing.List` (their only consumers
  moved; wave-3/4 precedent). Routes and all other logic untouched.
- `deploy/vps/deploy.sh`: `ANALYTICS_TARGET` joining all seven sites of the
  wave-1/2/3/4 pattern (target var, `release_complete`, download required
  list, release install, bootstrap capture, install staging `.next`,
  activation before `main.py` — see plan Decision D-4).
- Tests: walk extensions only (deviation note D-4) —
  `tests/test_api_state_transaction.py` (multi-source `_extract_functions`),
  `tests/test_line_crossing.py` (module source + `tree_candidates` + two
  text-join readers), `tests/test_storage_retention.py` (`load_functions`
  walk), `tests/test_api_contract.py` (`api_sources` + `load_functions`
  walks), `tests/test_analytics_profiles.py` (additive/camera-isolated
  source walk), and the synthetic release fixture in
  `tests/test_vps_deploy_transaction.py`. `tests/test_road_event_hygiene.py`
  needs no change (it extracts `post_analytics_event`, which stays in
  `main.py`).
- `scripts/quality/build_exact_artifacts.py`: vps required list gains
  `api/app/analytics.py` (deploy.sh convergence, wave-3/4 precedent).
- SDD: this trio; `scripts/ci/validate_sdd.py` grandfather set gains
  `396-wave5-analytics-services` (one entry; exact-set equality otherwise
  fails the battery — see plan Decision D-6).

Out of scope: the analytics routes and route wrappers (stay in `main.py`),
the ROAD_LIVE/WATER_LIVE live-stream slices, camera/preview constants (stay
in `config.py`), `now_iso` (stays owned by `identity.py`), `worker/`,
`frontend/`, `.github/`, any behavior/limit/schema change, and the wave 2-4
peer-review residuals (work order: "none new this wave").

## Requirements

- R-1: `api/app/analytics.py` owns the analytics services slice verbatim
  (main.py:286-329 + 342-511 + 1051-1218 at base beea1067): the 18
  functions and 9 constants listed above — byte-identical bodies, with
  `now_iso` imported from `identity` (both idioms) exactly where the
  originals resolved it, and `_events_sweep_state` moving as the slice's
  exclusive mutable state (D-1).
- R-2: `api/app/main.py` re-exports every moved name explicitly (no star
  imports) under the dual idiom; every route stays in `main.py`; the
  `passage_mirrors.open_passages_db` binding and the module-tail init calls
  (including `sweep_events_media(force=True)`) stay; no sentinel/binding
  line is introduced beyond the seam.
- R-3: `deploy/vps/deploy.sh` — `ANALYTICS_TARGET` defined next to
  `API_TARGET`; the file joins `release_complete`, the download required
  list and the release install; activation stages and promotes it **before**
  `main.py` bound to the selected release's content (staged `.next`
  promoted only when the release ships the file; otherwise the live copy
  and stale `.next` are removed — the store.py soft pattern); the bootstrap
  capture keeps a live copy with the captured `main.py` when present.
- R-4: The reader suites resolve moved definitions/markers from the new
  module via extended multi-source walks so the pins hold on the head tree;
  no assertion is weakened and no retirement tooth is dulled (the
  `test_api_state_transaction` extraction still exercises the real store
  append/persist paths and byte-pinned legacy mirrors;
  `post_analytics_event` is still extracted from `main.py` and executed
  with the real `write_json_file` fallback). The
  `tests/test_vps_deploy_transaction.py` synthetic releases carry
  `analytics.py`.
- R-5: `scripts/quality/build_exact_artifacts.py` vps required inventory
  converges with deploy.sh (gains `api/app/analytics.py`);
  `scripts/ci/validate_sdd.py` grandfathers the #396 wave set (one entry).
- R-6: No undefined name ships: every function body's global references
  resolve against module imports/definitions (automated AST closure audit,
  18/18), and ruff F-rules are clean on the whole tree (catches F821
  undefined names and F401 unused imports).

## Acceptance criteria

- AC-001: The full unittest suite is green on head with the test count equal
  to the 908/4 baseline (no test added or removed).
- AC-002: `scripts/ci/validate_repo.py` passes on head (new
  `api/app/analytics.py` admitted; `api/app/main.py` still required and
  present); `scripts/ci/validate_sdd.py` passes with the grandfathered wave
  set.
- AC-003: `deploy/vps/deploy.sh` carries the new module through all seven
  module-pattern sites (target var, `release_complete`, download required
  list, release install, bootstrap capture, install staging `.next`,
  activation before `main.py` with the store.py soft pattern); `bash -n`
  passes and the VPS deploy transaction suite stays green.
- AC-004: The moved functions are behavior-identical: the three moved
  regions (44 + 170 + 168 lines) appear byte-identical in `analytics.py`
  against `git show beea1067:api/app/main.py` (automated audit, 18/18
  per-function PASS, all 9 constants verbatim).
- AC-005: The new module is import-safe in package mode and under the
  roi-normalization standalone-exec mock context (both observed green);
  `compile()`/`ast.parse` smoke passes; one canonical
  `config`/`store`/`identity` instance per import mode; dependency closure
  proven by the AST audit and ruff clean run.
- AC-006: No behavior change: the route table is pinned at exactly 61
  `@app.*` endpoints with unchanged handler bindings, response
  shapes/defaults/limits untouched; the only main.py edits are removal of
  the moved blocks, the wave-5 seam and the dropped dead imports.
- AC-007: The exact-artifact vps required list contains every `api/app/*`
  module deploy.sh requires (now 9 app modules).

## Runtime feedback

- RF-001: Operator actions expected: 1 — the VPS deploy of this wave rides
  the merge (DEPLOY-TRIGGER, полоса A); deploy.sh stages the new module
  before `main.py`, restarts and runs the origin/public health gate;
  rollback removes the module when returning to a pre-wave-5 release.
- RF-002: Failure evidence: a missing `analytics.py` in a release fails in
  `release_complete`/download BEFORE any live source mutation; a failed
  activation health gate rolls the full source set back via the existing
  install_release(rollback) path.

## NFR assessment

- NFR-001 | Area: reliability | Target: zero behavior change on the VPS — boot ordering identical (analytics.py activates before main.py), the 61-endpoint route table with unchanged handler bindings and response shapes, the events sweep and crossing services byte-identical | Validation: full suite green incl. the frozen route fingerprint test; main.py diff limited to moved blocks + seam + dropped imports; deploy transaction suite green | Evidence: tests/test_route_table.py, tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-002 | Area: compatibility | Target: text-pinning and AST-harness suites keep working without weakened assertions; the six extended walks resolve moved definitions from the new module; readers with no moved-name references stay untouched | Validation: the six reader suites green on head (test_api_state_transaction, test_line_crossing, test_storage_retention, test_api_contract, test_analytics_profiles, test_vps_deploy_transaction); test_road_event_hygiene green unchanged | Evidence: focused unittest runs (95 + 49 tests) | Status: PASS
- NFR-003 | Area: deployability/rollback | Target: a release missing analytics.py can never reach activation (fails in release completeness/download), and a rollback to a pre-wave-5 release removes the module while keeping the old main bootable; bootstrap capture stays bootable | Validation: deploy.sh seven-site extension + soft activation pattern; synthetic-release tests carry the new file | Evidence: tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-004 | Area: maintainability | Target: analytics.py depends only on config/identity/objects_registry/store/fastapi/stdlib; it never imports main (import-cycle rule); the only mutable state in the module is the slice-exclusive `_events_sweep_state` dict consumed exclusively by sweep_events_media | Validation: module source review; AST dependency-closure audit (18/18 functions resolve); verbatim byte-range extraction with automated byte-identity audit | Evidence: api/app/analytics.py; /tmp/opencode/wave5_closure.py output | Status: PASS
- NFR-005 | Area: security | Target: analytics validation/mutation paths move by byte-range copy with no semantic drift; no new env reads, no secret-shaped literals introduced; require_auth, identity checks, limits (EVENTS_FEED_LIMIT, CROSSINGS_STORE_LIMIT, EVENTS_MEDIA_GRACE_SECONDS) unchanged | Validation: byte-identity audit of the moved regions; ruff (E9/F) clean on head; suite green | Evidence: byte-identity audit output recorded in the wave report; scripts/quality/ruff.toml run | Status: PASS
