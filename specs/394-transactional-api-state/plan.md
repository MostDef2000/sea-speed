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
      transition-protocol primitives: `import_legacy_records` (dedupe by
      the camera's retained canonical payload set AND by the durable
      `ingestion_log` registry — `_register_ingested` hashes each
      ingested record's canonical payload bytes in the same transaction
      as every ingestion and the log is never pruned (whole-window
      retention; retirement is follow-up-release work);
      no timestamp comparison in the skip decision), oldest-first, cap
      applied in-transaction, and
      `import_legacy_camera_state`
      (legacy wins only when strictly newer — both sides must parse as ISO
      timestamps; undated legacy seeds empty rows only).
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
- D-8: The legacy-import merge is governed by a durable ingestion
  identity (validator-endorsed, round 4). History: a first-round design
  keyed rows on a SHA-256 `content_key` column with
  `UNIQUE(camera_id, content_key)` and kept runtime appends NULL-keyed;
  validation round 2 rejected it because the NULL/keyed split meant the
  UNIQUE constraint never crossed the domains — an ordinary restart
  re-imported a mirror of live rows as keyed copies (reads returned
  both), at the cap the keyed copies evicted retained history, and a
  lagged mirror resurrected pruned records with new ids. The column was
  removed entirely (live appends keep no dedupe key; pre-#394 and new
  tables identical). The round-3 repair deduped imports by canonical
  payload equality against retained rows and guarded resurrection with a
  timestamp floor (skip records older than the oldest retained row);
  validation round 3 rejected the floor with two blockers: a pruned
  record whose timestamp EQUALS the retained floor re-imported from a
  stale mirror with a new id and evicted retained records (churn on
  every restart); undated/unparseable records bypassed the floor
  structurally; and a rollback-period record with an old event timestamp
  was silently discarded despite free cap headroom (event time is not
  ingestion order — the API preserves supplied `created_at`). Round 4
  adopted the ingestion log: `ingestion_log(seq INTEGER PRIMARY KEY
  AUTOINCREMENT, camera_id TEXT NOT NULL, kind TEXT NOT NULL,
  payload_hash TEXT NOT NULL)` indexed on (camera_id, kind,
  payload_hash); `_register_ingested(connection, camera_id, kind,
  records)` runs inside the SAME transaction as every ingestion —
  live appends in `append_crossing`/`append_event`, imports in
  `import_legacy_records` — hashing the record's canonical payload bytes
  (`json.dumps(record, ensure_ascii=False, sort_keys=True)`, the exact
  stored `payload_json` bytes). Imports skip a record iff its canonical
  payload is in the retained set OR its hash is registered; only merged
  records are registered, so repeated boots over an unchanged mirror are
  complete no-ops (no table or registry writes). Round 4 initially
  pruned the log to the newest 4×cap entries per (camera, kind);
  validation round 4 rejected that prune with one blocker: a mirror has
  bounded SIZE but unbounded AGE — while the pruned window expires
  identities, a stale legacy file can remain arbitrarily old (production
  sequence: import 500 events → 2001 new events with failing mirror
  writes → every original hash falls out of the registry AND retention →
  the intact stale file re-imports with fresh ids and evicts the 500
  authoritative records). Round 5 (validator's option A) removed the
  prune entirely: `_register_ingested` is a pure INSERT and
  `ingestion_log` is retained for the ENTIRE dual-write/rollback
  compatibility window of this release — any legacy file eligible for
  import can only contain records ingested before that window ends, so
  registry membership is a complete anti-resurrection proof for this
  release's lifetime; no pruning means no expiration. Retirement (DROP
  TABLE ingestion_log + stop dual-write + drop the import path) is the
  recorded follow-up release work. Camera-state import stays newer-wins
  (D-9 requires both sides parseable).
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
  two-file behavioral battery 49 passed / 1 skipped (skip = head-only
  collision test).
- Transition-protocol repair tests (T-A..T-E, V-A..V-D, W-A..W-D) all
  green: StartupMigrationTests (necessity gate: fail-closed on empty
  target, best-effort warning on populated), LegacyMigrationTests
  (ingestion-history-gated merge with time-blind anti-resurrection,
  newer-wins camera state that ignores unusable timestamps),
  VpsDeployTransactionTests
  (release-bound activation with store-less fixture + stale `.next`).
- RED-on-base (git stash → main.py @ 30ba326, untracked files survive;
  session-4 run against the pre-repair test file): 6 failed / 12 passed /
  2 skipped — the six failures are exactly the
  fixed defects (4 fail-loud endpoint reads, no-lost-update RMW, fixed-tmp
  collision); stash pop restored the working tree. T-A..T-E, V-A..V-D and
  W-A..W-D are new behavior (not RED-on-base).
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
- RISK-001 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: startup migration runs at import time so every name it uses (`CROSSINGS_STORE_LIMIT`, path helpers) is defined above the startup block; constants moved to the top block; migration reads via `analytics_data_file`; any import-time failure fails the deploy health gate loudly and the chain auto-rolls back | Validation: full suite green on head (776 passed); py_compile + ruff clean; deploy transaction behavioral suite exercises boot/verify ordering | Residual risk: LOW — corrupt legacy store fails boot closed by design (fail-closed acceptance) | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: DATA | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: SQLite is authoritative; the legacy JSON mirror is a best-effort projection of committed rows written after the SQLite commit (mirror failure logs to stderr, never fails the request); drift self-heals on the next write | Validation: dual-write order verified by independent peer session (APPROVE); mirror exception paths reviewed | Residual risk: LOW — mirror amplification on crossings (full-file rewrite up to 5000 records per post) is bounded by the cap and lasts one release cycle | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: legacy JSON files are never deleted and stay fresh via mirrors; activation is bound to the selected release's content — staged `.next` is promoted only when the release ships `api/app/store.py` (same condition as staging), otherwise the live copy and any stale `.next` are removed; the bootstrap capture keeps a live store.py with the captured main.py | Validation: test_vps_deploy_transaction behavioral suite (20 tests) including the store-less fixture: test_store_less_rollback_removes_live_store_and_stale_next and test_store_release_stages_and_promotes_normally; peer rollback-completeness verdict | Residual risk: NONE — the downgrade branch is now exercised against a store-less release fixture with a stale `.next` present | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: store.py install plumbing is a disclosed deviation from the work order's "No other deploy.sh changes"; required for boot; follows the file's existing conditional-install idiom; documented in SDD trio + amendment receipt 6052476179 | Validation: amendment receipt on #394; SDD validate green | Residual risk: NONE | Owner: Delivery Orchestrator | Status: ACCEPTED
- RISK-005 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: independent validation blocked the merge four times. Round 1 found three lifecycle defects (rollback→retry abandoned records because imports no-op'd on populated tables; corrupt non-authoritative mirrors failed every boot; activation could promote a stale `.next`). Round 2 rejected the SHA-256 content-key repair (D-8): the UNIQUE(camera_id, content_key) constraint never crossed the live-NULL/imported-keyed domains, so an ordinary restart duplicated live rows from their mirror and at the cap evicted retained history; a lagged mirror resurrected pruned records with new ids; and an unparseable `updated_at` displaced stored camera state via lexical fallback. Round 3 rejected the timestamp floor: equal-timestamp pruned records re-imported from stale mirrors with new ids and churned retention across restarts, undated records bypassed the floor structurally, and delayed rollback-period records with old event timestamps were discarded despite free cap headroom. Round 4 closed both round-3 blockers with the durable ingestion identity (D-8): every ingestion registers the record's canonical payload hash in `ingestion_log` inside its transaction; imports skip registered hashes time-blind, so equal-timestamp, undated and unparseable pruned records are uniformly never resurrected while never-ingested rollback records merge regardless of event time; necessity-gated reads, strict both-sides-parse newer-wins camera-state import and release-bound activation stand unchanged; the bootstrap capture preserves a live store.py. Round 4's own 4×cap registry prune was then rejected (bounded SIZE ≠ bounded AGE: with failing mirror writes the stale legacy file stays arbitrarily old while the window expires identities — 2001 churned events would expire all 500 original hashes and let the intact stale file re-import and evict the authoritative records); round 5 removed the prune entirely (validator's option A, D-8): the registry is a pure append that lives for the whole dual-write/rollback window, so no identity can expire within this release's lifetime | Validation: T-A..T-E behavioral tests green on head (StartupMigrationTests, LegacyMigrationTests, VpsDeployTransactionTests) plus the regression battery V-A (live row + mirror → no duplication across restarts), V-B (mixed imported + live rows at the 5000/500 caps → no eviction beyond exact arithmetic), W-A (equal-timestamp stale mirror → pruned record skipped, retention stable across repeated boots, no churn), W-B (pruned undated record skipped via registry, genuinely new undated rollback record merged), W-C (delayed rollback record with old event time + free cap headroom → merged), W-D (≥3 boots on a stable intact mirror → zero mutations after the first import; after churn far beyond any window scale the ORIGINAL stale mirror is still a complete no-op — zero new rows, retained rows byte-identical, registry count unchanged: identities never expire), W-E (validator's production-cap sequence scaled down: import F at the cap → churn with failing mirror writes beyond the round-4 4×cap window → rollback appends to the stale file → re-upgrade: rollback records merge, stale records do NOT resurrect, retained set stable); full suite green; ruff + bash -n clean | Residual risk: LOW — the registry is never pruned, so identities never expire; ingestion_log grows ≈ ~120 bytes per ingested record (realistic growth well under 10MB/day; pathological ingestion bursts accepted and bounded by the follow-up retirement that ends the dual-write window: DROP TABLE ingestion_log + stop dual-write + drop the import path) | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_concurrent_appenders_never_lose_records (8 barrier-forced racers, zero lost records on head, RED on base RMW)
- TEST-002 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_write_round_trip_is_atomic + test_concurrent_writers_leave_one_valid_file_and_no_tmp (25+25 alternating writers, no tmp leftovers)
- TEST-003 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: FailLoudReadTests — corrupt speed-config/speed-lines/crossing-line/preview stores raise HTTP 500 (RED on base: silent default); test_legacy_fixed_tmp_collision_is_eliminated (deterministic barrier RED vs base, head-only skip)
- TEST-004 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: caps tests (bulk-seed via one connection, append triggers same-transaction pruning 5000/500); camera_state upsert last-write-wins
- TEST-005 | Covers: RISK-001,RISK-003 | Level: integration | Priority: P0 | Evidence: StartupMigrationTests (idempotency, order parity, fail-closed on corrupt legacy input, never deletes legacy files) + test_vps_deploy_transaction.py (20 behavioral deploy/rollback tests)
- TEST-006 | Covers: RISK-005 | Level: unit | Priority: P0 | Evidence: T-A test_corrupt_legacy_mirror_is_best_effort_when_store_is_populated (populated store + corrupt mirror → no raise, stderr warning, authoritative data intact) + T-B test_corrupt_legacy_file_fails_closed (empty target + corrupt legacy → raises)
- TEST-007 | Covers: RISK-005 | Level: unit | Priority: P0 | Evidence: T-C test_rollback_window_records_are_merged_idempotent (import → rollback-window append → re-import merges, duplicates skipped, cap respected) + T-D test_camera_state_import_is_newer_wins (legacy newer wins, older loses, mixed-UTC-offset ordering) + V-A test_live_rows_are_not_duplicated_by_mirror_import (mirror of a live row → no duplication, restart-stable) + V-B test_import_at_production_caps_preserves_retained_history (mixed imported + live rows at the 5000/500 caps → no eviction beyond exact arithmetic) + W-A test_equal_timestamp_stale_mirror_never_resurrects_or_churns (equal-timestamp stale mirror → pruned record skipped via ingestion history, retention stable across repeated boots) + W-B test_undated_records_obey_the_ingestion_registry (pruned undated record skipped, genuinely new undated rollback record merged) + W-C test_delayed_rollback_record_with_old_event_time_merges (old event time + free cap headroom → merged; the round-3 floor would have skipped it) + W-D test_repeated_boots_are_zero_mutation_and_identities_never_expire (≥3 boots → zero mutations; after churn far beyond any window scale the ORIGINAL stale mirror imports as a complete no-op — zero new rows, retained rows byte-identical, registry count unchanged, no identities expired) + W-E test_rollback_after_churn_beyond_window_keeps_retention_stable (production-cap sequence scaled down: import F at the cap → churn with failing mirror writes → rollback appends to the stale file → re-upgrade merges exactly the rollback records, stale records never resurrect, retained set stable) + V-D test_camera_state_import_ignores_unusable_timestamps (unparseable/absent updated_at → stored state stays; undated seeds empty only)
- TEST-008 | Covers: RISK-003,RISK-005 | Level: integration | Priority: P0 | Evidence: T-E test_store_less_rollback_removes_live_store_and_stale_next (store-less rollback release + stale `${STORE_TARGET}.next` → activation removes both, promotes nothing) + test_store_release_stages_and_promotes_normally
- Regression: full suite (776 passed, 4 skipped) including the updated
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
