# Spec: Camera preview/snapshot extraction — api/app/camera_preview.py (Wave 4)

- Issue: #396
- Specification: specs/396-wave4-camera-preview/spec.md

## Product outcome

Wave 1 (specs/396-wave1-shared-kernel) carved the dependency-free kernel out
of `api/app/main.py`; wave 2 (specs/396-wave2-objects-registry) carved out
the objects registry and the passage→object mirror layer; wave 3
(specs/396-wave3-water-passages) carved out the water-passages store. Wave 4
carves out the camera-preview/snapshot service slice — the media-facing
process-management layer the program contract scheduled for this wave —
with **zero behavior change**:

1. `api/app/camera_preview.py` (new) — 15 functions moved verbatim from
   `main.py` (base 5cad94c6, lines 477-763): relay source validation
   (`validate_camera_preview_source`), catalog loading
   (`load_camera_preview_catalog`), snapshot path/metadata/quality gates
   (`camera_snapshot_path`, `camera_snapshot_public_metadata`,
   `build_camera_snapshot_extract_args`, `camera_snapshot_luma_spread`,
   `camera_snapshot_candidate_is_usable`), snapshot commit
   (`commit_camera_snapshot_locked`), and the one-active-preview process
   lifecycle (`camera_preview_public_state`, `camera_preview_pid_matches`,
   `cleanup_camera_preview_media`, `terminate_camera_preview_locked`,
   `active_camera_preview_locked`, `build_camera_preview_ffmpeg_args`,
   `start_camera_preview_locked`). Imports the camera/preview constants
   from `config` and the stateless JSON helpers `read_json_file`/
   `write_json_file` from `store` exactly where the originals resolved them.
2. `api/app/main.py` keeps every route and all other logic; the six camera
   routes (`get_cameras`, `get_camera_snapshot`, `commit_camera_snapshot`,
   `get_camera_preview`, `start_camera_preview`, `stop_camera_preview`)
   stay in `main.py` per the wave pattern (61 endpoints unchanged); the
   moved names remain importable from `main` via the established thin
   explicit re-export seam (dual package/direct-file idiom, no star
   imports), so AST-harness suites, text-pinning suites and the deployed
   module see identical behavior.

State-closure decision (deviation note D-1 — the wave-4 work order's
primary hazard): the moved functions reference **no mutable module state**.
The `*_locked` suffix means "the caller must hold `config.CAMERA_PREVIEW_LOCK`";
the lock itself (created at config import time) and every camera/preview
constant have lived in `config.py` since wave 1, and the only acquirers are
the five lock-acquiring route handlers that stay in (of the six staying) `main.py`. Runtime preview state
persists in the JSON state file (`CAMERA_PREVIEW_STATE_FILE`) through
`store`'s stateless `read_json_file`/`write_json_file` helpers — not in any
module global. Therefore nothing mutable moves, no sentinel/injection is
needed (the `passage_mirrors.open_passages_db` binding pattern from wave 2
has no counterpart here), and the single-instance-per-import-mode rule
holds trivially: the lock is created exactly once, in `config.py`, whichever
import mode boots the package (verified: `main.CAMERA_PREVIEW_LOCK is
main.config.CAMERA_PREVIEW_LOCK` in package mode, and the mock harness boots
the same config singleton in direct-file mode).

Constants decision (deviation note D-2): the work order lists "camera/preview
constants consumed only by this slice" as scope candidates. Dependency
tracing shows **no camera constant remains in `main.py`** — all of them
(`CAMERA_PREVIEW_DIR`, `CAMERA_SNAPSHOT_DIR`, `CAMERA_PREVIEW_CATALOG_FILE`,
`CAMERA_PREVIEW_STATE_FILE`, `CAMERA_PREVIEW_FFMPEG_BIN`,
`CAMERA_PREVIEW_CATALOG_SCHEMA`, `CAMERA_PREVIEW_ID_RE`,
`CAMERA_PREVIEW_SESSION_RE`, `CAMERA_PREVIEW_RFC1918`,
`CAMERA_PREVIEW_LOCK`, `CAMERA_PREVIEW_START_TIMEOUT_SEC`,
`CAMERA_SNAPSHOT_EXTRACT_TIMEOUT_SEC`, `CAMERA_SNAPSHOT_MIN_BYTES`,
`CAMERA_SNAPSHOT_MIN_LUMA_SPREAD`, `CAMERA_PREVIEW_TTL_SEC`) moved to
`config.py` in wave 1 under its exactly-one-owner rule. Moving them again
out of `config.py` would contradict the wave-1 ownership decision and break
the config `__all__` seam, so they stay; the new module imports them from
`config` like every other `api/app` module. Three of them
(`CAMERA_PREVIEW_CATALOG_SCHEMA`, `CAMERA_PREVIEW_SESSION_RE`,
`CAMERA_PREVIEW_TTL_SEC`) are consumed by both the moved functions and the
staying routes — both modules import them from `config`, no duplication.

No API surface change: the 61-endpoint route table, response shapes,
schemas, defaults, limits and failure modes are unchanged (pinned by
`tests/test_route_table.py`'s frozen fingerprint).

## User scenarios

- US-1: An operator deploys this release to the VPS; `deploy.sh` stages
  `camera_preview.py` into the release and activates it **before** `main.py`
  (mirroring the store.py/config.py/identity.py/objects_registry.py/
  passage_mirrors.py/water_passages.py pattern), so the first boot of the
  new `main.py` finds its imports and the health gate passes exactly as
  before.
- US-2: A rollback to a pre-wave-4 release removes the live
  `camera_preview.py` cleanly (the old `main.py` does not import it); a
  staged `.next` left by an interrupted install is never promoted; the
  bootstrap capture keeps a live copy next to the captured `main.py` so the
  rollback release stays bootable on its own.
- US-3: The text-pinning suites keep reading the camera-preview code: the
  gallery source walk now joins `camera_preview.py` right after `main.py`,
  so definition pins (`def camera_snapshot_candidate_is_usable...`), the
  quality-gate ordering pin and the private-source-field slices resolve
  against the module that owns them, without weakening any assertion.
- US-4: A test loads `main.py` standalone (spec_from_file_location with
  mocked `fastapi`/`Path.mkdir`/`sqlite3.connect`); the new module imports
  safely under the same mocks (it needs no mocks beyond the existing ones:
  `threading` is real stdlib and the lock lives in `config.py`, which
  already booted under this harness since wave 1), and no second module
  instance of any dependency is created inside one process (dual idiom
  everywhere, one canonical instance per import mode).

## Scope

- `api/app/camera_preview.py` (new): the 15 functions listed above, moved
  verbatim by scripted byte-range copy (287 body lines).
- `api/app/main.py`: remove the moved blocks; add the wave-4 seam (thin
  explicit re-exports, dual idiom, no star imports); drop the now-unused
  `import ipaddress`, `import re`, `import signal`, `import subprocess` and
  `from urllib.parse import urlsplit` (their only consumers moved;
  wave-3 `import sqlite3` precedent). Routes and all other logic untouched
  this wave.
- `deploy/vps/deploy.sh`: `CAMERA_PREVIEW_TARGET` joining all seven sites of
  the wave-1/2/3 pattern (target var, `release_complete`, download required
  list, release install, bootstrap capture, install staging `.next`,
  activation before `main.py` — see plan Decision D-3).
- Tests: the gallery source walk in `tests/test_camera_preview_gallery.py`
  (deviation note D-4) and the synthetic release fixture in
  `tests/test_vps_deploy_transaction.py`. No other reader requires changes:
  `test_api_contract.py`'s `api_sources()`/`load_functions` walks reference
  no moved name; `test_route_table.py` reads `main.py` only (routes stay);
  `test_roi_normalization.py` loads `main.py` through the seam unchanged.
- `scripts/quality/build_exact_artifacts.py`: vps required list gains
  `api/app/camera_preview.py` (deploy.sh convergence, wave-3 precedent).
- SDD: this trio; `scripts/ci/validate_sdd.py` grandfather set gains
  `396-wave4-camera-preview` (one entry; exact-set equality otherwise fails
  the battery — see plan Decision D-5).

Out of scope: the six camera routes and the `CAMERA_PREVIEW_LOCK`
acquisition points (stay in `main.py`), camera/preview constants (stay in
`config.py` — D-2), analytics/state layers, `worker/`, `frontend/`,
`.github/`, any behavior/limit/schema change, and the wave 2-3
peer-review residuals (work order: "none new this wave").

## Requirements

- R-1: `api/app/camera_preview.py` owns the camera-preview/snapshot service
  slice verbatim (main.py:477-763 at base 5cad94c6): the 15 functions
  listed above — byte-identical bodies, constants imported from `config`,
  `read_json_file`/`write_json_file` from `store`, `store.JSON_READ_ERRORS`
  resolved through the `store` module exactly as before.
- R-2: `api/app/main.py` re-exports every moved name explicitly (no star
  imports) under the dual idiom; the six camera routes stay in `main.py`
  with their `with CAMERA_PREVIEW_LOCK:` blocks untouched; no
  sentinel/binding line is introduced (D-1: no mutable state moved).
- R-3: `deploy/vps/deploy.sh` — `CAMERA_PREVIEW_TARGET` defined next to
  `API_TARGET`; the file joins `release_complete`, the download required
  list and the release install; activation stages and promotes it **before**
  `main.py` bound to the selected release's content (staged `.next`
  promoted only when the release ships the file; otherwise the live copy
  and stale `.next` are removed — the store.py soft pattern); the bootstrap
  capture keeps a live copy with the captured `main.py` when present.
- R-4: The text-pinning reader `tests/test_camera_preview_gallery.py`
  resolves camera-preview definitions/markers from the new module (source
  walk extended) so the pins hold on the head tree; no assertion is
  weakened. `tests/test_vps_deploy_transaction.py` synthetic releases carry
  `camera_preview.py` so release completeness stays satisfiable.
- R-5: `scripts/quality/build_exact_artifacts.py` vps required inventory
  converges with deploy.sh (gains `api/app/camera_preview.py`);
  `scripts/ci/validate_sdd.py` grandfathers the #396 wave set (one entry).

## Acceptance criteria

- AC-001: The full unittest suite is green on head with the test count equal
  to the 908/4 baseline (no test added or removed).
- AC-002: `scripts/ci/validate_repo.py` passes on head (new
  `api/app/camera_preview.py` admitted; `api/app/main.py` still required and
  present); `scripts/ci/validate_sdd.py` passes with the grandfathered wave
  set.
- AC-003: `deploy/vps/deploy.sh` carries the new module through all seven
  module-pattern sites (target var, `release_complete`, download required
  list, release install, bootstrap capture, install staging `.next`,
  activation before `main.py` with the store.py soft pattern); `bash -n`
  passes and the VPS deploy transaction suite stays green.
- AC-004: The moved functions are behavior-identical: the full 287-line
  moved region appears byte-identical in `camera_preview.py` against
  `git show 5cad94c6:api/app/main.py` (automated audit, 15/15 per-function
  PASS).
- AC-005: The new module is import-safe in package mode and under the
  roi-normalization standalone-exec mock context (both observed green);
  `compile()`/`ast.parse` smoke passes; one canonical `config`/`store`
  instance per import mode; the lock singleton identity holds.
- AC-006: No behavior change: the route table is pinned at exactly 61
  `@app.*` endpoints with unchanged handler bindings, response
  shapes/defaults/limits untouched; the only main.py edits are removal of
  the moved blocks, the wave-4 seam and the five dropped imports.
- AC-007: The exact-artifact vps required list contains every `api/app/*`
  module deploy.sh requires (now 8 app modules).

## Runtime feedback

- RF-001: Operator actions expected: 1 — the VPS deploy of this wave rides
  the merge (DEPLOY-TRIGGER, полоса A); deploy.sh stages the new module
  before `main.py`, restarts and runs the origin/public health gate;
  rollback removes the module when returning to a pre-wave-4 release.
- RF-002: Failure evidence: a missing `camera_preview.py` in a release fails
  in `release_complete`/download BEFORE any live source mutation; a failed
  activation health gate rolls the full source set back via the existing
  install_release(rollback) path.

## NFR assessment

- NFR-001 | Area: reliability | Target: zero behavior change on the VPS — boot ordering identical (camera_preview.py activates before main.py), the 61-endpoint route table with unchanged handler bindings and response shapes, preview process lifecycle semantics untouched | Validation: full suite green incl. the frozen route fingerprint test; main.py diff limited to moved blocks + seam + dropped imports; deploy transaction suite green | Evidence: tests/test_route_table.py, tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-002 | Area: compatibility | Target: text-pinning and AST-harness suites keep working without weakened assertions; the gallery walk resolves moved definitions from the new module; readers with no moved-name references stay untouched | Validation: tests/test_camera_preview_gallery.py, tests/test_api_contract.py, tests/test_roi_normalization.py, tests/test_route_table.py green on head | Evidence: focused pytest run (40 passed) | Status: PASS
- NFR-003 | Area: deployability/rollback | Target: a release missing camera_preview.py can never reach activation (fails in release completeness/download), and a rollback to a pre-wave-4 release removes the module while keeping the old main bootable; bootstrap capture stays bootable | Validation: deploy.sh seven-site extension + soft activation pattern; synthetic-release tests carry the new file | Evidence: tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-004 | Area: maintainability | Target: camera_preview.py depends only on config/store/fastapi/stdlib; it never imports main (import-cycle rule); no mutable module state in the new module — the lock stays in config.py (single instance per process), preview runtime state lives in the JSON state file via stateless store helpers | Validation: module source review; lock singleton identity check in package mode; verbatim byte-range extraction with automated byte-identity audit | Evidence: api/app/camera_preview.py | Status: PASS
- NFR-005 | Area: security | Target: camera-preview validation/quality gates move by byte-range copy with no semantic drift; no new env reads, no secret-shaped literals introduced; ffmpeg arg construction, RFC1918 pinning and the no-credentials checks unchanged | Validation: byte-identity audit of the moved region; ruff (E9/F) clean on head; suite green | Evidence: byte-identity audit output recorded in the wave report; scripts/quality/ruff.toml run | Status: PASS
