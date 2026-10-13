# Spec: Live feeds + worker control extraction — api/app/live_feeds.py (Wave 6)

- Issue: #396
- Specification: specs/396-wave6-live-feeds-worker-control/spec.md

## Product outcome

Waves 1-5 (specs/396-wave1-shared-kernel, 396-wave2-objects-registry,
396-wave3-water-passages, 396-wave4-camera-preview, 396-wave5-analytics-services)
carved the dependency-free kernel, the objects registry + passage mirror layer,
the water-passages store, the camera-preview service and the analytics services
out of `api/app/main.py`. Wave 6 — the FINAL wave of the #396 decomposition —
carves out the live-feeds slice (road1/cam1 live ring buffers, envelope
validators, SSE stream generators) with **zero behavior change**:

1. `api/app/live_feeds.py` (new) — 10 names moved verbatim from `main.py`
   (base b9a956b9; 130 body lines in six regions), 4 functions + 6
   constants/state objects:
   - road live: `ROAD_LIVE_MAX`, `ROAD_LIVE`, `ROAD_LIVE_LOCK`
     (main.py:1038-1041 minus the seq counter), `_validate_road_live_envelope`
     (main.py:1043-1093), `_road_live_stream_gen` (main.py:1118-1132);
   - water live: `WATER_LIVE_MAX`, `WATER_LIVE`, `WATER_LIVE_LOCK`
     (main.py:1147-1150 minus the seq counter), `_validate_water_live_envelope`
     (main.py:1152-1194), `_water_live_stream_gen` (main.py:1218-1232).
   Imports exactly what the originals resolved at call time: `json`,
   `threading`, `collections.deque`, `typing.Any/Dict` and
   `fastapi.HTTPException` — stdlib plus the validator's exception type; the
   slice has NO intra-package dependencies, so plain imports load identically
   in package context (`api.app.live_feeds`) and direct-file loads
   (top-level `live_feeds`); one canonical module instance per import mode.
2. `api/app/main.py` keeps every route and all other logic (61 endpoints
   unchanged; 1249 -> 1145 lines); the moved names remain importable from
   `main` via the established thin explicit re-export seam (wave-6 try/except
   block, dual idiom, no star imports), so the staying live routes, the
   AST-harness suites, text-pinning suites and the deployed module see
   identical behavior — and identical deque/lock OBJECT identity, since the
   routes consume the shared objects through the seam while the generators
   use the module-local ones.

State-closure decision (deviation note D-1 — the wave-6 work order's primary
hazard): the ring buffers (`ROAD_LIVE`/`WATER_LIVE` deques), their
`threading.Lock` objects and the capacity constants are live-feeds-slice
exclusive and move with the slice. The per-camera sequence counters
(`ROAD_LIVE_SEQ`, `WATER_LIVE_SEQ`) intentionally STAY in `main.py`: the
staying route handlers increment them via `global` statements, and a Python
`global` rebinds the DEFINING module's namespace — moving the counters while
keeping the routes byte-identical would fork the counters per module
namespace (a permanently-zero zombie counter in `live_feeds.py` behind the
seam), i.e. duplicated state, which the wave contract forbids. The generators
deliberately never read the module-level counters (they sequence off the
per-envelope `_live_seq` field), so the split is closure-clean; the audit
proves exactly one module-level definition of each of the eight state names
(deques/locks/maxes in `live_feeds.py` only, counters in `main.py` only).
Do NOT "complete" the move by relocating the counters unless the route
handlers move with them.

Slice boundary decision (deviation note D-2): the work order's worker-control
scope (worker_control_origin, call_worker_control, operator-control service
functions, deployed_source_commit + release-file reading) resolves to EMPTY on
the wave-6 base: all of those primitives were extracted to `identity.py` in
wave 1 (deployed_source_commit reads `DEPLOYED_COMMIT_FILE` from `config` —
verified, no main-local literals) and `main.py` only imports/re-exports them.
The remaining worker-control surface in `main.py` is the six
`/api/worker/control*` route handlers plus `/api/session`, which stay per the
route contract (61 endpoints). The event/live diagnostics sweep found no
additional live-feeds-specific helpers: the only globals the moved functions
resolve are the moved state and stdlib/fastapi names (AST closure audit,
4/4 functions, both idioms).

#393 security-teeth impact (deviation note D-3): NONE. The pinned primitives
(`worker_control_origin`, `call_worker_control`, `require_auth`) are defined
in `identity.py` and executed by `tests/test_393_control_token_separation.py`
through its main+identity+config AST walk; byte-pinned source markers
(`os.environ.get("SEA_SPEED_WORKER_CONTROL_TOKEN"`,
`f"Bearer {WORKER_CONTROL_TOKEN}"`, installer gates, env hygiene) live in
`identity.py`/`config.py`/`deploy/**`, all untouched. The `require_auth`
calls remain inline in the staying `post_road_live`/`post_water_live` route
handlers, so the control-token separation and ingestion-auth assertions stay
byte-effective with ZERO test edits. Focused run after extraction:
`Ran 12 tests ... OK`.

No API surface change: the 61-endpoint route table, response shapes, schemas,
defaults, limits (120-entry ring buffers, 64-detection / 64 KiB envelopes,
20-item default history) and failure modes are unchanged (pinned by
`tests/test_route_table.py`'s frozen fingerprint; all eight staying live
route handlers verified byte-identical by the wave audit).

## User scenarios

- US-1: An operator deploys this release to the VPS; `deploy.sh` stages
  `live_feeds.py` into the release and activates it **before** `main.py`
  (mirroring the store.py/config.py/identity.py/objects_registry.py/
  passage_mirrors.py/water_passages.py/camera_preview.py/analytics.py
  pattern, seven sites, store.py soft pattern), so the first boot of the new
  `main.py` finds its imports and the health gate passes exactly as before.
- US-2: A rollback to a pre-wave-6 release removes the live `live_feeds.py`
  cleanly (the old `main.py` does not import it); a staged `.next` left by an
  interrupted install is never promoted; the bootstrap capture keeps a live
  copy next to the captured `main.py` so the rollback release stays bootable
  on its own.
- US-3: Road/water live telemetry (POST/GET + SSE streams, both internal and
  `/sea-speed/` public aliases) behaves identically: same ring buffer, same
  lock, same sequence semantics — the routes consume the moved state through
  the wave-6 seam and the generators read the same objects.
- US-4: A test loads `main.py` standalone (spec_from_file_location with
  mocked `fastapi`/`Path.mkdir`/`sqlite3.connect` — the roi-mock harness);
  the new module imports safely under the same mocks (stdlib-only
  dependencies) and no second module instance of any dependency is created
  inside one process.

## Scope

- `api/app/live_feeds.py` (new): the 10 names listed above, moved verbatim
  by scripted byte-range copy (130 body lines).
- `api/app/main.py`: remove the moved regions (keeping the two seq counters
  in place — D-1); add the wave-6 seam (thin explicit re-exports, dual idiom,
  no star imports); drop the now-unused `import threading` and
  `from collections import deque` (their only consumers moved; wave-5
  precedent). Routes and all other logic untouched.
- `deploy/vps/deploy.sh`: `LIVE_FEEDS_TARGET` joining all seven sites of the
  wave-1..5 pattern (target var, `release_complete`, download required list,
  release install, bootstrap capture, install staging `.next`, activation
  before `main.py` — see plan Decision D-4).
- Tests: exactly ONE reader edit, the established per-wave deploy-envelope
  fixture line (deviation note D-4): `tests/test_vps_deploy_transaction.py`
  `write_release` gains the `api/app/live_feeds.py` synthetic-release entry
  (wave 3/4/5 precedent — wave 5 added `analytics.py` the same way), because
  `release_complete` now requires the module and a fixture release without it
  falls into the re-download path where the fake curl produces no archive.
  Beyond that one fixture line: zero reader edits — repo-wide grep over every
  moved name (`ROAD_LIVE*`, `WATER_LIVE*`, `_validate_*_live_envelope`,
  `_*_live_stream_gen`, `*_SEQ`) hits only `worker/hls_motion_yolo_worker_events.py`
  (its own unrelated constants, no main import) and historical wave-5 spec
  prose; no logic reader extracts or text-scans any moved name (the full
  per-reader audit table is in plan.md Decision D-4). Suite test count is
  unchanged (908/4 baseline == head).
- `scripts/quality/build_exact_artifacts.py`: vps required list gains
  `api/app/live_feeds.py` (deploy.sh convergence, wave-3/4/5 precedent).
- SDD: this trio; `scripts/ci/validate_sdd.py` grandfather set gains
  `396-wave6-live-feeds-worker-control` (one entry; exact-set equality —
  this closes the "396" grandfather set, the final wave).

Out of scope: the live routes and worker-control routes (stay in `main.py`),
`ROAD_LIVE_SEQ`/`WATER_LIVE_SEQ` (stay in `main.py` — D-1), the
worker-control primitives (stay in `identity.py`, wave-1 owner),
`StreamingResponse`/`FileResponse` imports (used by staying routes),
`worker/`, `frontend/`, `.github/`, any behavior/limit/schema change, and the
wave 2-5 peer-review residuals (work order: "none new this wave").

## Requirements

- R-1: `api/app/live_feeds.py` owns the live-feeds slice verbatim
  (main.py:1038-1041/1043-1093/1118-1132 + 1147-1150/1152-1194/1218-1232 at
  base b9a956b9): the 4 functions and 6 constants/state objects listed
  above — byte-identical bodies, plain stdlib+fastapi imports that resolve
  exactly what the originals resolved, and no `main` import (import-cycle
  rule).
- R-2: `api/app/main.py` re-exports every moved name explicitly (no star
  imports) under the dual idiom; every route stays in `main.py`; the seq
  counters stay module-local to `main` (D-1); the dropped `threading`/`deque`
  imports lose their last consumers with this move; no sentinel/binding line
  is introduced beyond the seam.
- R-3: `deploy/vps/deploy.sh` — `LIVE_FEEDS_TARGET` defined next to
  `ANALYTICS_TARGET`; the file joins `release_complete`, the download
  required list and the release install; activation stages and promotes it
  **before** `main.py` bound to the selected release's content (staged
  `.next` promoted only when the release ships the file; otherwise the live
  copy and stale `.next` are removed — the store.py soft pattern); the
  bootstrap capture keeps a live copy with the captured `main.py` when
  present.
- R-4: The #393 control-token teeth remain byte-effective without edits
  (focused run 12/12 OK); no test file changes in this wave; no assertion
  weakened anywhere.
- R-5: `scripts/quality/build_exact_artifacts.py` vps required inventory
  converges with deploy.sh (gains `api/app/live_feeds.py`, now 10 app
  modules); `scripts/ci/validate_sdd.py` grandfathers the #396 wave set (one
  added entry, exact-set equality).
- R-6: No undefined name ships: every moved function's global references
  resolve against module imports/definitions (automated AST closure audit,
  4/4 functions + module level, both import idioms), and ruff F-rules are
  clean on the whole tree (catches F821 undefined names and F401 unused
  imports).

## Acceptance criteria

- AC-001: The full unittest suite is green on head with the test count equal
  to the 908/4 baseline (no test added or removed).
- AC-002: `scripts/ci/validate_repo.py` passes on head (new
  `api/app/live_feeds.py` admitted; `api/app/main.py` still required and
  present); `scripts/ci/validate_sdd.py` passes with the grandfathered wave
  set (six 396-wave entries).
- AC-003: `deploy/vps/deploy.sh` carries the new module through all seven
  module-pattern sites (target var, `release_complete`, download required
  list, release install, bootstrap capture, install staging `.next`,
  activation before `main.py` with the store.py soft pattern); `bash -n`
  passes and the VPS deploy transaction suite stays green.
- AC-004: The moved functions are behavior-identical: the six moved regions
  appear byte-identical in `live_feeds.py` against
  `git show b9a956b9:api/app/main.py` (automated audit, 4/4 per-function
  PASS, all 6 state lines verbatim) and the eight staying live route
  handlers are byte-identical to base.
- AC-005: The new module is import-safe in package mode and under the
  roi-normalization standalone-exec mock context (both observed green);
  `compile()`/`ast.parse` smoke passes; one canonical `live_feeds` instance
  per import mode with shared deque/lock object identity; dependency closure
  proven by the AST audit and ruff clean run.
- AC-006: No behavior change: the route table is pinned at exactly 61
  `@app.*` endpoints with unchanged handler bindings, response
  shapes/defaults/limits untouched; the only main.py edits are removal of
  the moved regions, the wave-6 seam and the two dropped dead imports.
- AC-007: No state duplication in any import mode: each of the eight
  live-feed state names has exactly one module-level definition
  (audit-verified); the seq-counter counters stay exclusively in `main.py`
  where their `global` mutators live (D-1).

## Runtime feedback

- RF-001: Operator actions expected: 1 — the VPS deploy of this wave rides
  the merge (DEPLOY-TRIGGER, полоса A); deploy.sh stages the new module
  before `main.py`, restarts and runs the origin/public health gate;
  rollback removes the module when returning to a pre-wave-6 release.
- RF-002: Failure evidence: a missing `live_feeds.py` in a release fails in
  `release_complete`/download BEFORE any live source mutation; a failed
  activation health gate rolls the full source set back via the existing
  install_release(rollback) path.

## NFR assessment

- NFR-001 | Area: reliability | Target: zero behavior change on the VPS — boot ordering identical (live_feeds.py activates before main.py), the 61-endpoint route table with unchanged handler bindings and response shapes, live ring buffers/locks byte-identical and single-instance | Validation: full suite green incl. the frozen route fingerprint test; main.py diff limited to moved regions + seam + 2 dropped imports; deploy transaction suite green | Evidence: tests/test_route_table.py, tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-002 | Area: compatibility | Target: text-pinning and AST-harness suites keep working without weakened assertions; reader updates limited to the established per-wave deploy-envelope fixture line (no logic/assertion changes); #393 teeth byte-effective (12/12 focused) | Validation: repo-wide grep over every moved name (only worker-local constants + historical spec prose); deploy-transaction class green (23/23) after the fixture line; focused #393 run green; full suite green (908/4) | Evidence: grep sweep recorded in the wave progress file; tests/test_393_control_token_separation.py; tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-003 | Area: deployability/rollback | Target: a release missing live_feeds.py can never reach activation (fails in release completeness/download), and a rollback to a pre-wave-6 release removes the module while keeping the old main bootable; bootstrap capture stays bootable | Validation: deploy.sh seven-site extension + soft activation pattern; synthetic-release tests carry the new file | Evidence: tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-004 | Area: maintainability | Target: live_feeds.py depends only on stdlib + fastapi.HTTPException; it never imports main (import-cycle rule); mutable state split is explicit — ring buffers/locks/maxes module-local to live_feeds, seq counters module-local to main (no fork, no zombie, no duplication) | Validation: module source review; AST dependency-closure audit (4/4 functions resolve, both idioms); single-definition audit (8/8 names); verbatim byte-range extraction with automated byte-identity audit | Evidence: api/app/live_feeds.py; /tmp/opencode/wave6_audit.py output (45/45 PASS) | Status: PASS
- NFR-005 | Area: security | Target: live-envelope validation moves by byte-range copy with no semantic drift; require_auth stays at the route boundary in main.py; no new env reads, no secret-shaped literals; limits (120 entries, 64 detections, 64 KiB) unchanged | Validation: byte-identity audit of the moved regions and staying routes; #393 focused run 12/12; ruff (E9/F) clean on head; suite green | Evidence: byte-identity audit output recorded in the wave report; scripts/quality/ruff.toml run | Status: PASS
