# Plan: Transactional mutable API state persistence

- Issue: #394
- Specification: specs/394-transactional-api-state/spec.md

## Implementation approach

1. `api/app/store.py` (new, standard library only):
   - `read_json_file(path, default)` — missing file returns the default;
     `OSError`/`ValueError` (JSON/Unicode decode) escape so callers can
     fail loud. `write_json_file(path, data)` — per-file flock on a
     `<name>.lock` sibling, uuid-unique tmp, `os.replace`, tmp cleanup.
   - SQLite hot state: `initialize_state_db` (WAL, idempotent),
      `open_state_db` (per-op connection, commit/rollback/raise),
      `append_crossing`/`read_crossings` (cap 5000, newest-first),
      `append_event`/`read_events` (cap 500), `upsert_camera_state`
      (single-statement ON CONFLICT upsert), `read_camera_state`,
      `camera_has_rows` (per-camera emptiness probe), and the
      transition-protocol primitives: `import_legacy_records` (content-keyed
      `INSERT OR IGNORE` merge on `(camera_id, content_key)`, oldest-first,
      cap applied in-transaction) and `import_legacy_camera_state`
      (legacy wins only when strictly newer; undated legacy seeds empty rows
      only).
2. `api/app/main.py` rewire — every hot-state mutation commits to SQLite
   first, then mirrors the committed projection to the legacy JSON file
   (best-effort, stderr log on failure); reads come from SQLite. Config
   GETs (speed-config/speed-lines/crossing-line) and camera-preview reads
   wrap `read_json_file` in `except store.JSON_READ_ERRORS` → HTTP 500.
   Startup calls `import_legacy_state_store()` after the existing DB
   initialisations; `CROSSINGS_STORE_LIMIT` moves to the top constants
   block because the startup migration runs at import time.
3. Tests — `tests/test_api_state_transaction.py` extracts the real
   main.py functions (AST, like the existing harnesses) and asserts the
   behavioral contract: fail-loud reads (RED on base), no lost updates
   (barrier-forced RMW interleaving, RED on base), unique-tmp collision
   (deterministic RED on base), caps 5000/500, camera-state upsert,
   idempotent/fail-closed/non-destructive migration. Tests that exercise
   main.py functions which only exist post-fix are `skipUnless`-gated so
   the base run shows clean RED failures rather than collection errors.
4. deploy.sh — the ROI migration heredoc writes through a uuid tmp +
   `os.replace`; `store.py` joins the release file set (completeness
   check, download required list, install) and is activated with the soft
   pattern (install + mv before main.py when present, `rm -f` on rollback
   to a pre-#394 release).

## Architecture

Three coordinated pieces:

- `api/app/store.py` (new, stdlib only) — the persistence seam: hardened
  JSON IO (fail-loud read, flock + uuid-tmp + `os.replace` write) and the
  WAL SQLite hot-state store (`crossings`/`event_feed`/`camera_state` with
  `camera_id`, per-op connections, single-statement mutations, same-
  transaction per-camera caps 5000/500, idempotent migration primitives).
  `api/app/main.py` depends only on this module's public surface.
- `api/app/main.py` — SQLite-authoritative reads/writes for state, events
  and crossings; every committed mutation mirrored best-effort into the
  legacy JSON projection (rollback window); config/preview reads fail
  loud as HTTP 500 via `except store.JSON_READ_ERRORS`; the startup
  migration runs after the existing DB initialisations, with
  `CROSSINGS_STORE_LIMIT` hoisted to the top constants block because the
  migration executes at import time.
- `deploy/vps/deploy.sh` — atomic uuid-tmp write in the ROI-migration
  heredoc and minimal `store.py` install plumbing following the file's
  existing conditional-file idiom (release completeness, download
  required list, install, soft activation before `main.py`, clean removal
  on pre-#394 rollback).

## Decisions

- D-1: SQLite (stdlib `sqlite3`, WAL) over file-locked JSON for hot
  state — single-statement inserts remove the RMW lost-update window that
  flock-on-JSON cannot fix without an app-level transaction log.
- D-2: SQLite authoritative + legacy JSON projection mirror (dual-write
  window) instead of a hard cutover — keeps the previous release and
  operator tooling functional for instant rollback; mirror failures are
  best-effort (stderr) so they can never fail an API request.
- D-3: Fail-loud reads with caller-chosen handling (endpoints → 500,
  migration → raise) instead of blanket `except Exception` — silent
  default-on-corruption was the defect being fixed.
- D-4: Per-camera caps enforced with same-transaction DELETEs bounded by
  the inserted row's timestamp — no separate pruning pass, no unbounded
  growth, no partial states.
- D-5: Startup migration never deletes legacy files — the previous release
  keeps reading them during the rollback window — and legacy reads are
  necessity-gated (D-9) so the mirror cannot sabotage a healthy store.
- D-6: Import-time startup call kept (matches the existing
  water-passages/ROI migration pattern) with names hoisted above the
  block; a failure fails the deploy health gate closed (accepted:
  fail-closed is the desired behaviour for corrupt legacy input).
- D-7: Tests extract the real functions from `main.py` via the existing
  AST harness idiom; head-only functions are `skipUnless`-gated so the
  base run produces clean RED failures instead of collection errors.
- D-8: The legacy-import dedupe key is the SHA-256 of the canonical
  payload JSON (`ensure_ascii=False, sort_keys=True`) — the exact bytes
  stored in `payload_json`. Record timestamps (created_at/updated_at/ts)
  participate because they are fields of the record; no generated value
  (the `_utc_now_iso` fallback for a missing created_at) ever does, so the
  same record hashes identically on every boot and `INSERT OR IGNORE` on
  `(camera_id, content_key)` is a deterministic content-keyed merge.
  Runtime appends keep `content_key` NULL (NULLs are distinct in SQLite
  UNIQUE constraints), preserving live-append duplicate semantics.
- D-9: Legacy reads are necessity-gated per (camera, kind) via
  `store.camera_has_rows`: an EMPTY target means this boot performs the
  authoritative initial migration (corrupt legacy input raises — the
  deploy gate rolls back rather than silently losing history); a
  NON-EMPTY target means migration already completed and the legacy file
  is a non-authoritative mirror (read/parse failure logs a stderr warning
  and skips, so a corrupt mirror cannot fail every boot of a healthy
  store).

## Affected contours

- Sea Speed API persistence only: `api/app/store.py` (new),
  `api/app/main.py`, the new `tests/test_api_state_transaction.py`,
  minimal harness updates in `tests/test_api_contract.py`,
  `tests/test_line_crossing.py`, `tests/test_road_event_hygiene.py`,
  `tests/test_vps_deploy_transaction.py`, `deploy/vps/deploy.sh`, and
  this SDD trio.
- No change to frontend/, worker/, .github/, object registry
  (objects.sqlite3 already transactional), water-passages store, or ROI
  migration semantics beyond the atomic write.
- On-disk state layout on the VPS changes: `state.sqlite3` is
  created next to the legacy JSON stores; the legacy files are kept fresh
  by the projection mirrors, not removed.

## Validation

- Full suite on head: green (see tasks.md AC-009 for exact counts);
  two-file behavioral battery 42 passed / 1 skipped (skip = head-only
  collision test).
- Transition-protocol repair tests (T-A..T-E) all green: StartupMigrationTests
  (necessity gate: fail-closed on empty target, best-effort warning on
  populated), LegacyMigrationTests (content-keyed merge, newer-wins
  camera state), VpsDeployTransactionTests (release-bound activation with
  store-less fixture + stale `.next`).
- RED-on-base (git stash → main.py @ 30ba326, untracked files survive):
  6 failed / 12 passed / 2 skipped — the six failures are exactly the
  fixed defects (4 fail-loud endpoint reads, no-lost-update RMW, fixed-tmp
  collision); stash pop restored the working tree. T-A..T-E are new
  behavior (not RED-on-base).
- ruff (E9/F, `scripts/quality/ruff.toml`) on the changed Python files:
  All checks passed; `bash -n deploy/vps/deploy.sh` clean;
  `tests/test_vps_deploy_transaction.py` 20 passed (store.py install
  plumbing + release-bound activation covered by the transaction harness).

## Runtime feedback

- RF-001: Operator actions expected: 0 — deploy stages and activates
  `store.py`; the first boot runs the legacy migration inside the deploy
  health gate (corrupt legacy input → gate fails → automatic rollback).
- RF-002: Failure evidence: HTTP 500 messages naming the corrupt store
  file; stderr lines for best-effort mirror failures; rollback removes
  `store.py` when returning to a pre-#394 release.

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from the VPS production impact; the
  deployment transaction audit below covers the contour.
- RISK-001 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: startup migration runs at import time so every name it uses (`CROSSINGS_STORE_LIMIT`, path helpers) is defined above the startup block; constants moved to the top block; migration reads via `analytics_data_file`; any import-time failure fails the deploy health gate loudly and the chain auto-rolls back | Validation: full suite green on head (764 passed); py_compile + ruff clean; deploy transaction behavioral suite exercises boot/verify ordering | Residual risk: LOW — corrupt legacy store fails boot closed by design (fail-closed acceptance) | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: DATA | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: SQLite is authoritative; the legacy JSON mirror is a best-effort projection of committed rows written after the SQLite commit (mirror failure logs to stderr, never fails the request); drift self-heals on the next write | Validation: dual-write order verified by independent peer session (APPROVE); mirror exception paths reviewed | Residual risk: LOW — mirror amplification on crossings (full-file rewrite up to 5000 records per post) is bounded by the cap and lasts one release cycle | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: legacy JSON files are never deleted and stay fresh via mirrors; activation is bound to the selected release's content — staged `.next` is promoted only when the release ships `api/app/store.py` (same condition as staging), otherwise the live copy and any stale `.next` are removed; the bootstrap capture keeps a live store.py with the captured main.py | Validation: test_vps_deploy_transaction behavioral suite (20 tests) including the store-less fixture: test_store_less_rollback_removes_live_store_and_stale_next and test_store_release_stages_and_promotes_normally; peer rollback-completeness verdict | Residual risk: NONE — the downgrade branch is now exercised against a store-less release fixture with a stale `.next` present | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: store.py install plumbing is a disclosed deviation from the work order's "No other deploy.sh changes"; required for boot; follows the file's existing conditional-install idiom; documented in SDD trio + amendment receipt 6052476179 | Validation: amendment receipt on #394; SDD validate green | Residual risk: NONE | Owner: Delivery Orchestrator | Status: ACCEPTED
- RISK-005 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: independent validation blocked the merge with three lifecycle defects (rollback→retry abandoned records because imports no-op'd on populated tables; corrupt non-authoritative mirrors failed every boot; activation could promote a stale `.next`); repaired as a content-keyed idempotent merge with a documented SHA-256 canonical-payload key (D-8), newer-wins camera-state import, a necessity-gated read protocol (D-9) and release-bound activation; the bootstrap capture now also preserves a live store.py | Validation: T-A/T-B/T-C/T-D/T-E behavioral tests green on head (StartupMigrationTests, LegacyMigrationTests, VpsDeployTransactionTests); full suite green; ruff + bash -n clean | Residual risk: LOW — legacy records that already existed only in SQLite when a rollback-period mirror was lost are unrecoverable by design (the merge is additive; no record is deleted) | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_concurrent_appenders_never_lose_records (8 barrier-forced racers, zero lost records on head, RED on base RMW)
- TEST-002 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_write_round_trip_is_atomic + test_concurrent_writers_leave_one_valid_file_and_no_tmp (25+25 alternating writers, no tmp leftovers)
- TEST-003 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: FailLoudReadTests — corrupt speed-config/speed-lines/crossing-line/preview stores raise HTTP 500 (RED on base: silent default); test_legacy_fixed_tmp_collision_is_eliminated (deterministic barrier RED vs base, head-only skip)
- TEST-004 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: caps tests (bulk-seed via one connection, append triggers same-transaction pruning 5000/500); camera_state upsert last-write-wins
- TEST-005 | Covers: RISK-001,RISK-003 | Level: integration | Priority: P0 | Evidence: StartupMigrationTests (idempotency, order parity, fail-closed on corrupt legacy input, never deletes legacy files) + test_vps_deploy_transaction.py (20 behavioral deploy/rollback tests)
- TEST-006 | Covers: RISK-005 | Level: unit | Priority: P0 | Evidence: T-A test_corrupt_legacy_mirror_is_best_effort_when_store_is_populated (populated store + corrupt mirror → no raise, stderr warning, authoritative data intact) + T-B test_corrupt_legacy_file_fails_closed (empty target + corrupt legacy → raises)
- TEST-007 | Covers: RISK-005 | Level: unit | Priority: P0 | Evidence: T-C test_rollback_window_records_are_merged_content_keyed (import → rollback-window append → re-import merges with correct content keys, duplicates ignored, cap respected) + T-D test_camera_state_import_is_newer_wins (legacy newer wins, older loses, mixed-UTC-offset ordering)
- TEST-008 | Covers: RISK-003,RISK-005 | Level: integration | Priority: P0 | Evidence: T-E test_store_less_rollback_removes_live_store_and_stale_next (store-less rollback release + stale `${STORE_TARGET}.next` → activation removes both, promotes nothing) + test_store_release_stages_and_promotes_normally
- Regression: full suite (764 passed, 4 skipped) including the updated
  harnesses and the untouched `test_roi_normalization.py`.

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE
- Correct-course note: implementation deviations (event_feed/crossings
  camera_id column, deploy.sh install plumbing) were disclosed in the SDD
  trio and amendment receipt issuecomment-6052476179 rather than handled
  by correct-course; dual-write window retirement lands as a follow-up
  release after the first VPS contour deploy verifies.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: Block A owner approval (OUTCOME APPROVED session 2026-10-08) + receipts issuecomment-6051940042 (base scope) and issuecomment-6052476179 (deploy.sh install-plumbing amendment, peer rollback verdict)
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged VPS state | Retry: NO | Rollback: NONE | Evidence: release_complete + download_release required-list gate exits before rm -rf of the staged target (deploy.sh:203-286)
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged .next copies discarded; live API unchanged | Retry: NO | Rollback: install_release stages to .next and promotes via mv only after all copies stage successfully; store.py mv precedes main.py mv (new main cannot boot without it) | Evidence: install_release soft pattern (deploy.sh:603-649); test_vps_deploy_transaction behavioral suite (20 tests)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: restart_and_verify health gate (deploy.sh:738-753); fail-closed boot on corrupt legacy store (import_legacy_state_store propagates, deploy auto-rollback)
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: dual-write window — legacy JSON mirrors kept fresh by best-effort projection writes so install_release of the previous release sees fresh data in both directions
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging dirs may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: deploy.sh staging layout semantics unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: DEPLOYMENT_ACCEPTED line from the autonomous chain at exact-green-head merge
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour unchanged; activation is bound to the selected release's content — staged .next promoted only when the release ships store.py, otherwise live copy + stale .next removed — so an interrupted install can never leak a store.py into a store-less rollback; bootstrap capture preserves a live store.py with the captured main.py | Evidence: deploy.sh:643-649 (activation), deploy.sh:491-496 (bootstrap capture) + T-E tests (test_store_less_rollback_removes_live_store_and_stale_next)
