# Plan: Live feeds + worker control extraction — api/app/live_feeds.py (Wave 6)

- Issue: #396
- Specification: specs/396-wave6-live-feeds-worker-control/spec.md

## Implementation approach

1. `api/app/live_feeds.py` (new) — byte-range extraction of SIX regions of
   main.py at base b9a956b9 as verbatim copies: 1038-1041 minus
   `ROAD_LIVE_SEQ = 0` (road state: `ROAD_LIVE_MAX`, `ROAD_LIVE`,
   `ROAD_LIVE_LOCK`), 1043-1093 (`_validate_road_live_envelope`), 1118-1132
   (`_road_live_stream_gen`), 1147-1150 minus `WATER_LIVE_SEQ = 0` (water
   state), 1152-1194 (`_validate_water_live_envelope`), 1218-1232
   (`_water_live_stream_gen`) — 130 body lines, 10 names. Header imports the
   stdlib set the bodies use (`json`, `threading`, `collections.deque`,
   `typing.Any/Dict`) plus `fastapi.HTTPException`; NO intra-package imports
   (the slice resolves nothing from config/identity/store/objects_registry),
   so no dual try/except idiom is needed — plain imports behave identically
   in package and direct-file load modes. The extraction is performed by a
   scripted line-range copy from the base `main.py` (never retyped) with
   count==1 anchored replacements; an automated audit asserts the moved
   regions appear byte-identical in the new module (4/4 per-function + 6
   state lines) and that the eight staying live route handlers are
   byte-identical to base.
2. `api/app/main.py` — delete the moved regions; KEEP the two seq counters
   (`ROAD_LIVE_SEQ = 0`, `WATER_LIVE_SEQ = 0`) in place (Decision D-1);
   insert the wave-6 seam after the wave-5 seam (try/except dual idiom,
   explicit re-export list of all 10 names, `# noqa: F401`); drop the
   now-unused `import threading` and `from collections import deque` (both
   seam branches untouched — they belong to waves 1-5; only the stdlib
   imports die). No binding line is added — the state-closure trace
   (Decision D-1) shows the deque/lock move with their module-local
   consumers and the staying routes receive the same objects through the
   seam. Routes and all other logic untouched this wave.
3. Tests — ONE edit, the per-wave deploy-envelope fixture line (Decision
   D-4): `tests/test_vps_deploy_transaction.py::write_release` gains the
   `api/app/live_feeds.py` synthetic-release entry (wave-3/4/5 precedent).
   The first full-suite run proved the necessity: `release_complete` requires
   the module, so fixture releases without it fail completeness, deploy.sh
   falls into the re-download path, the fake curl's fallthrough prints `200`
   without writing an archive and `sha256sum` aborts — 17 failures + 2
   manifest-absent errors, all one root cause. With the fixture line the
   class runs 23/23 green and no other test needs changes (no assertion
   weakened, no logic reader touched). The #393 suite needs no extension: its
   AST walk (main+identity+config) still finds all pinned functions in
   identity.py, and its byte pins scan untouched files.
4. `deploy/vps/deploy.sh` — add `LIVE_FEEDS_TARGET` and mirror the
   wave-1..5 pattern through all seven sites (see Decision D-3).
5. `scripts/quality/build_exact_artifacts.py` — vps required list gains
   `api/app/live_feeds.py` (deploy.sh convergence, wave-3/4/5 precedent);
   `scripts/ci/validate_sdd.py` — grandfather the wave set (Decision D-5).

## Architecture

One new leaf module under `api/app/`, deployed before `main.py`:

- `api/app/live_feeds.py` — live-feed ring buffers and stream services;
  depends on `json`, `threading`, `collections.deque`, `typing` and
  `fastapi.HTTPException` only. Carries exactly six module-level objects:
  the two ring-buffer deques, their two locks and the two capacity
  constants — all slice-exclusive. Never imports `main` or any other
  `api/app` module.
- `api/app/main.py` — unchanged logic; thin explicit re-exports keep the
  historical import surface (`main.ROAD_LIVE`, `main._road_live_stream_gen`,
  ...) working for callers and any future test readers; the live routes
  stay in `main.py` and reach the moved state/services through the seam,
  which is the SAME object (deque/lock identity preserved — in-place
  `append` and lock acquisition are shared); the seq counters remain
  module-level to `main` because only the staying route handlers mutate
  them (`global`).

Import-cycle rule: the new module never imports `main` and has no
intra-package edges, so no sentinel/binding mechanism is needed — the
simplest dependency graph of all waves. The route-table fingerprint
(handler_name, method, path) is untouched because only function bodies
moved.

## Decisions

- D-1 (state closure — the work order's primary hazard, the fork trap):
  the mutable-state sweep found six module-level objects in the slice. The
  deques, locks and capacity constants are slice-exclusive and move with
  the slice. The two int counters (`ROAD_LIVE_SEQ`, `WATER_LIVE_SEQ`) DO
  NOT move: their mutators are `global` statements inside the STAYING
  route handlers (`post_road_live`/`post_water_live`), and Python `global`
  rebinds the defining module's namespace — a moved counter behind the
  re-export seam would fork into a permanently-zero zombie in live_feeds
  while main's copy increments (duplicated state, the exact hazard the
  wave contract forbids). The generators never read the module-level
  counters (they sequence off the per-envelope `_live_seq` field), so no
  moved code needs the counters. Single-definition audit: 8/8 state names
  have exactly one module-level definition per import mode. This is the
  primary deviation from "state moves with the slice": the counters' only
  consumers are the staying routes, so by the same exclusivity rule they
  stay with them.
- D-2 (worker-control scope resolves to EMPTY): `worker_control_origin`,
  `call_worker_control`, `require_auth`, `require_operator_identity` and
  `deployed_source_commit` were extracted to `identity.py` in wave 1;
  `main.py` imports and re-exports them (wave-1 seam, `# noqa: F401`).
  `deployed_source_commit` reads `DEPLOYED_COMMIT_FILE` from `config`
  (hazard-4 check: no main-local path literals). The remaining
  worker-control surface in main.py is route-only (six
  `/api/worker/control*` handlers + `/api/session`) and stays per the
  route contract. No worker-control code moves in wave 6.
- D-3 (deploy envelope, wave-1..5 precedent): `deploy.sh` is extended
  through all seven sites of the established module pattern for
  `live_feeds.py`: (1) `LIVE_FEEDS_TARGET` next to `ANALYTICS_TARGET`;
  (2) `release_complete` existence check; (3) download required list;
  (4) release install; (5) `bootstrap_current_release` capture of the live
  copy; (6) `install_release` staging to `.next`; (7) activation mv/rm
  **before** the `main.py` promotion, bound to the release's content
  (store.py soft pattern: staged copy promoted only when the release ships
  the module, otherwise live copy + stale `.next` removed so a pre-wave-6
  rollback boots cleanly).
- D-4 (reader updates: one fixture line — audit evidence): every listed
  candidate logic reader was checked against every moved name and needs NO
  edit. `test_route_table.py` pins handler names (unchanged, routes stay);
  `test_sea_speed_auth_v1.py` uses paths only; `test_393_control_token_separation.py`
  and `test_worker_operator_control.py` scan main+identity+config for
  worker-control/auth markers (all in identity.py or staying routes);
  `test_api_contract.py`/`test_api_state_transaction.py` walk for
  store/analytics/state-layer names (none in the live slice);
  `test_roi_normalization.py` standalone-execs main.py with mocked
  fastapi/PIL/sqlite (green — the wave-6 seam imports cleanly under the
  mocks); `test_frontend_contract.py`, `test_road_event_hygiene.py`,
  `test_unified_registry.py`, `test_water_passage.py`,
  `test_analytics_profiles.py`, `test_camera_preview_gallery.py`,
  `test_storage_retention.py`, `test_line_crossing.py`,
  `test_auth_session_identity.py` reference no moved name (grep sweep in the
  wave progress file). The ONE exception is the deploy envelope:
  `test_vps_deploy_transaction.py` builds synthetic releases from a fixed
  file list that must mirror deploy.sh's required inputs (wave 3/4/5 each
  added their module the same way) — the first full-suite run failed 17+2
  with exactly this root cause (release_complete rejection -> re-download ->
  fake curl writes no archive), fixed by the single `write_release` fixture
  line; the class then passed 23/23. No assertion weakened.
- D-5 (grandfather update): `scripts/ci/validate_sdd.py` grandfathers
  `396-wave6-live-feeds-worker-control` in the `"396"` set of
  `GRANDFATHERED_PREFIX_COLLISIONS` (exact-set equality; this is the final
  396 wave, closing the set). Authorized by the wave-6 work order (standing
  directive 2026-10-12; wave-5 precedent 2026-10-13).
- D-6 (imports dropped from main): `import threading` and
  `from collections import deque` lose their last consumers with this move
  (only the moved state lines used them; verified by line-level scan over
  the post-move main.py — the roi-mock harness and full suite stay green).
  KEEP verified in use: `datetime`/`timezone` (post_road_live/post_water_live
  receipt stamps and analytics state), `StreamingResponse` (staying stream
  routes), `json`/`os`/`sys`/`time`/`uuid`, all wave-1..5 seams. The
  wave-6 seam imports keep `# noqa: F401` (explicit re-export seam
  precedent).

## Affected contours

- VPS only (`api/**` + `deploy/vps/deploy.sh` + quality scripts):
  deploy envelope REQUIRED; deploy rides the merge via deploy-vps.yml
  (orchestrator DEPLOY-TRIGGER, полоса A). No Ubuntu worker, no edge, no
  frontend change.

## Validation

- Full suite `python3 -m unittest discover -s tests -p 'test_*.py'` green
  (baseline: 908 tests / 4 skipped; expected head: 908 / 4 — no test count
  change).
- `python3 scripts/ci/validate_repo.py` green.
- `python3 scripts/ci/validate_sdd.py` green (grandfathered #396 wave set,
  six entries).
- `ruff check . --config scripts/quality/ruff.toml` clean (0 errors —
  catches F821 dependency-closure breaks and F401 dead imports).
- `bash -n deploy/vps/deploy.sh` clean.
- Byte-identity audit: the six moved regions byte-identical to
  `git show b9a956b9:api/app/main.py` (full-function + 6 state lines);
  the eight staying live route handlers byte-identical to base; route table
  61 == 61 vs base with unchanged handler names.
- AST dependency-closure audit green (4/4 moved functions resolve all
  global names in both idioms; 8/8 main live routes resolve through the
  seam); single-definition audit 8/8.
- Import modes: package import smoke and the roi-normalization
  standalone-exec mock harness both green.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: deploy.sh extended through all seven module-pattern sites with staging+activation of live_feeds.py BEFORE main.py; bootstrap capture keeps rollback releases bootable; a missing module fails the release before any live mutation | Validation: deploy transaction suite + bash -n + release-shape fixtures | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: the dependency-closure hazard (wave-5 lesson) is guarded two ways: ruff F-rules tree-wide (F821/F401) and an AST closure audit compiling every moved function's globals against module imports (4/4, both idioms; module-level too — the battery's exec-namespace harnesses mask missing module globals) | Validation: ruff exit 0; wave6_audit.py "45 passed / 45"; full suite green | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: the seq-counter fork hazard is resolved by KEEPING the counters in main.py (D-1): `global` in a staying route rebinds main's namespace, so a moved counter would fork into a zombie — exactly the duplicated state the contract forbids; the generators need no counters; single-definition audit proves no duplication; docstring warns future movers | Validation: wave6_audit.py single-definition checks 8/8; module docstring documents the invariant | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: deque/lock object identity is shared between main routes and live_feeds generators via the re-export seam (in-place append / lock acquisition hit the same objects); no per-module state split | Validation: package-mode + direct-file import audit asserts one deque/lock instance per mode; route/generator byte-identity | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: validate_sdd grandfather is an exact-set match for the six registered #396 wave dirs only; any other duplicate prefix still fails closed | Validation: python3 scripts/ci/validate_sdd.py green on head | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-006 | Category: DATA | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: move-only extraction — ring buffer capacity (120), envelope limits (64 detections / 64 KiB), SSE keepalive cadence and response shapes are byte-identical; no schema or data migration | Validation: byte-identity audit; live route handlers byte-identical to base | Residual risk: LOW | Owner: Worker | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P1 | Evidence: python3 -m unittest discover -s tests -p 'test_*.py' (expected 908 tests / 4 skipped; baseline 908/4; observed OK)
- TEST-002 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: tests/test_vps_deploy_transaction.py (synthetic releases carry live_feeds.py via the deploy.sh-converged required set)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P1 | Evidence: bash -n deploy/vps/deploy.sh; seven-site grep audit (10 lowercase / 11 uppercase-var references, soft pattern before main.py mv)
- TEST-004 | Covers: AC-002 | Level: unit | Priority: P1 | Evidence: python3 scripts/ci/validate_repo.py (670 files); python3 scripts/ci/validate_sdd.py; build_exact_artifacts vps list contains every deploy.sh api/app module (10)
- TEST-005 | Covers: AC-004, AC-006 | Level: unit | Priority: P1 | Evidence: tests/test_route_table.py (61-route frozen fingerprint with handler names); byte-identity audit of the moved regions and staying routes vs b9a956b9
- TEST-006 | Covers: AC-004, AC-007 | Level: unit | Priority: P1 | Evidence: wave6_audit.py — byte-identity (4 fns + 6 state lines + 8 routes), single-definition 8/8, closure 4/4+8/8, import modes
- TEST-007 | Covers: AC-005 | Level: unit | Priority: P2 | Evidence: tests/test_roi_normalization.py (mocked standalone exec of main.py; wave-6 seam import chain exercised) + package-import smoke + AST closure audit
- TEST-008 | Covers: AC-001, AC-005 | Level: unit | Priority: P1 | Evidence: python3 -m ruff check . --config scripts/quality/ruff.toml (0 errors — F821/F401 guard)
- TEST-009 | Covers: AC-006 (NFR-002) | Level: unit | Priority: P1 | Evidence: tests/test_393_control_token_separation.py focused run (12/12) — teeth byte-effective without edits

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Runtime feedback

- RF-001: Deploy rides the merge (deploy-vps.yml, orchestrator-owned
  DEPLOY-TRIGGER); health gate = origin + public smoke as before; no new
  operator steps.
- RF-002: If activation health fails, deploy.sh rolls back to the previous
  release via install_release(previous) — for a pre-wave-6 previous release
  live_feeds.py is removed from live (the old main.py does not import it);
  bootstrap releases capture the live copy when present.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: work order for #396 wave 6 (extraction-only scope, standing directive 2026-10-12, final 396 wave); branch sdd/396-wave6-live-feeds-worker-control from b9a956b9
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged VPS state | Retry: NO | Rollback: NONE | Evidence: release_complete and the download required list now also require api/app/live_feeds.py; the gate exits before any mutation of the live tree
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged .next copies discarded; live API unchanged | Retry: NO | Rollback: install_release stages live_feeds.py to .next and promotes via mv only after all copies stage successfully; the mv precedes the main.py mv (the new main imports it at boot) | Evidence: install_release soft pattern; test_vps_deploy_transaction behavioral suite
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: restart_and_verify health gate unchanged by wave 6
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: wave 6 moves no persistence code (in-memory ring buffers only; no store/DB protocol touched; state/seq split keeps single-owner semantics)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging dirs may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: deploy.sh staging layout semantics unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: DEPLOYMENT_ACCEPTED line from the autonomous chain at exact-green-head merge
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour unchanged; activation is bound to the selected release content for live_feeds.py exactly as for analytics.py — staged .next promoted only when the release ships the module, otherwise the live copy and any stale .next are removed so a pre-wave-6 rollback boots cleanly; bootstrap capture preserves a live live_feeds.py alongside the captured main.py | Evidence: deploy.sh activation + bootstrap capture sites + test_vps_deploy_transaction rollback tests

## Deviations from the work order

- D-1 (primary): state-closure decision — the ring buffers, locks and
  capacity constants move with the slice (exclusive state), but the two
  per-camera sequence counters STAY in `main.py`: the staying route handlers
  mutate them via `global` statements and a Python `global` rebinds the
  defining module's namespace, so relocating the counters would fork state
  (zero-zombie behind the seam) — the duplicated state the wave contract
  forbids. No state is duplicated in any import mode (single-definition
  audit 8/8); the generators need no counters (per-envelope `_live_seq`).
- D-2: worker-control scope resolves to EMPTY — the work order's
  worker-control candidates (worker_control_origin, call_worker_control,
  operator-control service fns, deployed_source_commit + release-file
  reading) have lived in `identity.py` since wave 1; main.py re-exports them
  and keeps only the six `/api/worker/control*` route handlers plus
  `/api/session`, which stay per the route contract. One module
  (`live_feeds.py`, not two) shipped; the "1-2 modules bounded" allowance is
  used at one.
- D-3: deploy.sh seven-site mirror, artifact-manifest entry and the
  validate_sdd grandfather entry delivered as prescribed (grandfather
  authorized by the work order; final 396 wave).
- D-4: reader updates: exactly ONE — the per-wave deploy-envelope fixture
  line in `tests/test_vps_deploy_transaction.py::write_release` (the
  work order's zero-reader-edit expectation was audited and held for every
  logic reader; the deploy fixture is the established per-wave exception,
  wave 3/4/5 precedent — the first full-suite run proved its necessity with
  17+2 failures of one root cause). Grep sweep evidence in the wave progress
  file; zero weakened assertions; #393 teeth byte-effective (12/12 focused).
- D-5 (honest process note): `validate_sdd.py` fails until the specs trio
  exists (grandfather exact-set equality) — the trio was written before the
  final validate_sdd run in the same session; no transient state shipped.
