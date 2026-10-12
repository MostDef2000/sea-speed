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
      (single-statement ON CONFLICT upsert), `read_camera_state`. The
      dual-write-era transition-protocol primitives — `camera_has_rows`
      (per-camera emptiness probe), `import_legacy_records` (dedupe by
      the camera's retained canonical payload set AND by the durable
      `ingestion_log` registry; no timestamp comparison in the skip
      decision, oldest-first, cap applied in-transaction) and
      `import_legacy_camera_state`
      (legacy wins only when strictly newer — both sides must parse as ISO
      timestamps; undated legacy seeds empty rows only) — were REMOVED by
      the RISK-005 retirement act (see D-8) and no longer exist in
      store.py; they are listed here as the historical design record of
      the retired dual-write window.
2. `api/app/main.py` rewire — every hot-state mutation commits to SQLite
   first (SQLite is the only hot-state authority since the RISK-005
   retirement act stopped the legacy JSON projection mirrors); reads come
   from SQLite. Config
   GETs (speed-config/speed-lines/crossing-line) and camera-preview reads
   wrap `read_json_file` in `except store.JSON_READ_ERRORS` → HTTP 500.
   Startup called `import_legacy_state_store()` after the existing DB
   initialisations during the dual-write window — REMOVED by the RISK-005
   retirement act: boot now runs `initialize_state_db` only (schema
   creation plus the idempotent `DROP TABLE IF EXISTS ingestion_log`);
   `CROSSINGS_STORE_LIMIT` moves to the top constants
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
  (D-9 requires both sides parseable). RETIREMENT ADDENDUM (this release):
  the trigger fired 2026-10-09 (first verified full VPS contour deploy
  9e3b9ee8e02b75785393dc8ef246af5e4e05281b, issue #394 comment 6073231021);
  the act was executed in full on branch sdd/394-retirement —
  `DROP TABLE IF EXISTS ingestion_log` at startup, dual-write mirrors
  stopped, import path removed, all three together. The ingestion-identity
  design above is retained as historical record; the code no longer
  contains the registry or the import path.
- D-9 (RETIRED with the dual-write window): legacy reads were
  necessity-gated per (camera, kind) via `store.camera_has_rows`: an EMPTY
  target meant this boot performed the authoritative initial migration
  (corrupt legacy input raised — the deploy gate rolled back rather than
  silently losing history); a NON-EMPTY target meant migration already
  completed and the legacy file was a non-authoritative mirror (read/parse
  failure logged a stderr warning and skipped). The retirement act removed
  the whole import path, so no boot-time legacy reads remain; the decision
  is kept for the audit trail of the dual-write era.

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
  created next to the legacy JSON stores; the legacy files are no longer
  written (the projection mirrors were stopped by the RISK-005 retirement
  act) and are never removed — they remain on disk as inert history.

## Validation

- Full suite on the retirement head: green (Ran 902 tests, OK, 4 skipped —
  skips are pre-existing/environmental: the head-only fixed-tmp collision
  reconstruction, two root-required mediamtx runner tests, and
  systemd-analyze being unavailable in the sandbox; exact counts in the
  verification transcript).
- Post-retirement behavioral battery: StartupMigrationTests (fresh boot
  creates crossings/event_feed/camera_state WITHOUT ingestion_log; boots are
  idempotent; a pre-existing dual-write-era ingestion_log is dropped with
  retained records intact), RetiredDualWriteTests (contracted regression:
  boot drops a pre-existing ingestion_log, records accepted via the API
  append nothing to the legacy JSON mirrors, legacy files are never deleted
  nor modified), NoLostUpdateTests, StoreCapTests, CameraStateTests,
  FailLoudReadTests, StoreJsonIoTests, and the untouched T-E store-release
  staging tests (test_vps_deploy_transaction.py, 20 tests).
- Import-path coverage (T-A..T-D, V-A..V-E, W-A..W-E) was deleted WITH the
  import path — the contracted retirement of that coverage, not a
  weakening: the merge/anti-resurrection machinery it tested no longer
  exists. test_line_crossing.py reads the authoritative SQLite store
  instead of the retired mirror (assertions unchanged in strength).
- ruff (E9/F, `scripts/quality/ruff.toml`): All checks passed;
  `bash -n deploy/vps/deploy.sh` clean (deploy.sh unchanged — the #394
  store.py release plumbing stays exactly as installed);
  `python3 scripts/ci/validate_repo.py` rc=0;
  `python3 scripts/ci/validate_sdd.py` rc=0.

## Runtime feedback

- RF-001: Operator actions expected: 0 — deploy stages and activates
  `store.py`; the first boot runs the store migration (schema creation
  plus the idempotent `DROP TABLE IF EXISTS ingestion_log`) inside the
  deploy health gate. No legacy input is read at boot (RISK-001), so the
  dual-write-era corrupt-legacy-input → automatic-rollback path no longer
  exists; any unexpected store error still fails the gate loudly and the
  chain auto-rolls back.
- RF-002: Failure evidence: HTTP 500 messages naming the corrupt store
  file; the legacy-JSON mirrors are retired (RISK-005), so best-effort
  mirror stderr lines no longer exist; rollback removes `store.py` when
  returning to a pre-#394 release; legacy JSON files on disk are never
  deleted (inert history). Contracted rollback-semantics change: records
  accepted after the retirement are invisible to a pre-#394 rollback
  release (the dual-write window that fed those files is closed).

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from the VPS production impact; the
  deployment transaction audit below covers the contour.
- RISK-001 | Category: OPS | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: the boot-time store migration (initialize_state_db, import time) now only creates the hot-state tables and runs the idempotent `DROP TABLE IF EXISTS ingestion_log` retirement step; no legacy input is read at boot, so the corrupt-legacy-input failure mode no longer exists; any unexpected store error still fails the deploy health gate loudly and the chain auto-rolls back | Validation: StartupMigrationTests post-retirement (fresh schema without ingestion_log, idempotent boots, pre-existing registry dropped with retained records intact) green; full suite green | Residual risk: LOW — import-time store failure remains fail-closed by design (fail-closed acceptance) | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: DATA | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: the dual-write window is CLOSED by the contracted retirement act (RISK-005): SQLite is the only hot-state authority, the legacy JSON mirrors are no longer written, and legacy files on disk are never deleted (inert history); the registry drop touches no retained rows | Validation: RetiredDualWriteTests (boot drops a pre-existing ingestion_log; records accepted via the API append nothing to legacy JSON; legacy files not deleted or modified) + NoLostUpdateTests/StoreCapTests green | Residual risk: LOW — legacy JSON files go stale by design; rollback to a pre-#394 release no longer sees records accepted after the retirement (contracted expected change, documented in the PR Delivery section) | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: legacy JSON files are never deleted (inert history — the dual-write mirrors were stopped by the RISK-005 retirement act, so they are no longer kept fresh); activation is bound to the selected release's content — staged `.next` is promoted only when the release ships `api/app/store.py` (same condition as staging), otherwise the live copy and any stale `.next` are removed; the bootstrap capture keeps a live store.py with the captured main.py | Validation: test_vps_deploy_transaction behavioral suite (20 tests) including the store-less fixture: test_store_less_rollback_removes_live_store_and_stale_next and test_store_release_stages_and_promotes_normally; peer rollback-completeness verdict | Residual risk: NONE — the downgrade branch is now exercised against a store-less release fixture with a stale `.next` present | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: store.py install plumbing is a disclosed deviation from the work order's "No other deploy.sh changes"; required for boot; follows the file's existing conditional-install idiom; documented in SDD trio + amendment receipt 6052476179 | Validation: amendment receipt on #394; SDD validate green | Residual risk: NONE | Owner: Delivery Orchestrator | Status: ACCEPTED
- RISK-005 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: RETIRED — the bounded dual-write/rollback compatibility window delivered by this plan is CLOSED by the contracted retirement act, executed in full on branch sdd/394-retirement (this PR): startup migration runs `DROP TABLE IF EXISTS ingestion_log` (one-time, idempotent — existing VPS databases from the dual-write era shed the retired table), the dual-write legacy-JSON mirrors are stopped, and the legacy-JSON import path (import_legacy_records, import_legacy_camera_state, camera_has_rows and the ingestion-log registration) is removed — all three together, exactly as the pre-recorded residual-risk clause required. Trigger evidence: FIRED 2026-10-09 — first verified full VPS contour deploy 9e3b9ee8e02b75785393dc8ef246af5e4e05281b (issue #394 comment 6073231021); deadline (next release cycle) reached; the pre-agreed indexed-membership fallback was NOT needed. Historical rounds 1-5 (four validation blocks, the durable ingestion identity, the no-prune decision) remain recorded in D-8 as the audit trail of the retired design. Legacy JSON files are never deleted — they become inert history. Contracted rollback-semantics change: after this act, rollback to a pre-#394 release no longer sees records accepted during the (now closed) dual-write window | Validation: StartupMigrationTests (fresh boot creates the schema without ingestion_log; boots are idempotent; a pre-existing dual-write-era ingestion_log table is dropped while retained crossing records survive) + RetiredDualWriteTests (boot drops a pre-existing ingestion_log; records accepted via the API append path commit to SQLite and append nothing to legacy JSON; pre-existing legacy JSON files are byte-unchanged and never deleted) + full suite green; ruff E9/F + bash -n deploy.sh clean | Residual risk: NONE — the mechanism (registry growth, dual-write mirror amplification, import-path complexity) no longer exists in the codebase; the only residue is the contracted rollback-window closing above | Owner: Delivery Orchestrator | Status: CLOSED

## Test design

- TEST-001 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_concurrent_appenders_never_lose_records (8 barrier-forced racers, zero lost records on head, RED on base RMW)
- TEST-002 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_write_round_trip_is_atomic + test_concurrent_writers_leave_one_valid_file_and_no_tmp (25+25 alternating writers, no tmp leftovers)
- TEST-003 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: FailLoudReadTests — corrupt speed-config/speed-lines/crossing-line/preview stores raise HTTP 500 (RED on base: silent default); test_legacy_fixed_tmp_collision_is_eliminated (deterministic barrier RED vs base, head-only skip)
- TEST-004 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: caps tests (bulk-seed via one connection, append triggers same-transaction pruning 5000/500); camera_state upsert last-write-wins
- TEST-005 | Covers: RISK-001,RISK-003 | Level: integration | Priority: P0 | Evidence: StartupMigrationTests (post-retirement schema: fresh boot without ingestion_log, idempotent boots, pre-existing registry dropped with records intact) + test_vps_deploy_transaction.py (20 behavioral deploy/rollback tests)
- TEST-006 | Covers: RISK-005 | Level: unit | Priority: P0 | Evidence: RetiredDualWriteTests — the contracted regression: boot drops a pre-existing (dual-write-era) ingestion_log table; records accepted via the API append path (append_crossing_record) commit to SQLite and append nothing to the legacy JSON mirrors; pre-existing legacy JSON files are byte-unchanged and never deleted; second boot stays idempotent
- TEST-007 | Covers: RISK-002,RISK-005 | Level: unit | Priority: P0 | Evidence: import-path coverage (T-A..T-D, V-A..V-E, W-A..W-E) deleted WITH the import path — the contracted retirement of that coverage, not a weakening: the merge/anti-resurrection machinery it tested no longer exists; retained regression strength: test_concurrent_appenders_never_lose_records (8 racers, exact set, no duplicates in SQLite), caps tests, camera-state upsert tests
- TEST-008 | Covers: RISK-003,RISK-005 | Level: integration | Priority: P0 | Evidence: T-E test_store_less_rollback_removes_live_store_and_stale_next (store-less rollback release + stale `${STORE_TARGET}.next` → activation removes both, promotes nothing) + test_store_release_stages_and_promotes_normally
- Regression: full suite green — Ran 904 tests, OK, 4 skipped (the 902-test
  retirement run plus the two RetiredDualWriteTests event-feed/camera-state
  mirror pins added by the review follow-ups; the skips are
  pre-existing/environmental — see Validation above), including the updated
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
  by correct-course; the dual-write window retirement was pre-recorded in
  RISK-005 as follow-up release work and is now executed (below) — no
  unplanned course correction occurred.
- Retirement execution (RISK-005): the retirement trigger FIRED
  2026-10-09 — first verified full VPS contour deploy of this release,
  deployed_sha 9e3b9ee8e02b75785393dc8ef246af5e4e05281b (issue #394
  comment 6073231021) — and the deadline (the next release cycle)
  arrived. The contracted retirement act was executed in full, together,
  on branch sdd/394-retirement: `DROP TABLE IF EXISTS ingestion_log` in
  the startup migration, dual-write legacy-JSON mirrors stopped, and the
  legacy-JSON import path removed (store.py + main.py call sites). The
  pre-agreed fallback (indexed membership checks) was NOT needed. Legacy
  JSON files on disk are never deleted — they become inert history.
  Contracted rollback-semantics change: after this act, rollback to a
  pre-#394 release no longer sees records accepted during the (now
  closed) dual-write window; this is disclosed in the PR Delivery
  section.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: Block A owner approval (OUTCOME APPROVED session 2026-10-08) + receipts issuecomment-6051940042 (base scope) and issuecomment-6052476179 (deploy.sh install-plumbing amendment, peer rollback verdict)
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged VPS state | Retry: NO | Rollback: NONE | Evidence: release_complete + download_release required-list gate exits before rm -rf of the staged target (deploy.sh:203-286)
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged .next copies discarded; live API unchanged | Retry: NO | Rollback: install_release stages to .next and promotes via mv only after all copies stage successfully; store.py mv precedes main.py mv (new main cannot boot without it) | Evidence: install_release soft pattern (deploy.sh:603-649); test_vps_deploy_transaction behavioral suite (20 tests)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: restart_and_verify health gate (deploy.sh:738-753); fail-closed boot on unexpected store errors (initialize_state_db raises at import time, deploy auto-rollback); the dual-write-era fail-closed-on-corrupt-legacy-input clause (import_legacy_state_store propagates) is retired — the import path was removed and no legacy input is read at boot since the RISK-005 retirement act
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: dual-write window (now CLOSED by the RISK-005 retirement act: legacy JSON mirrors are no longer written; legacy files on disk are never deleted and become inert history; a rollback to a pre-#394 release no longer sees records accepted after the retirement — contracted and disclosed in the PR Delivery section)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging dirs may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: deploy.sh staging layout semantics unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: DEPLOYMENT_ACCEPTED line from the autonomous chain at exact-green-head merge
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour unchanged; activation is bound to the selected release's content — staged .next promoted only when the release ships store.py, otherwise live copy + stale .next removed — so an interrupted install can never leak a store.py into a store-less rollback; bootstrap capture preserves a live store.py with the captured main.py | Evidence: deploy.sh:643-649 (activation), deploy.sh:491-496 (bootstrap capture) + T-E tests (test_store_less_rollback_removes_live_store_and_stale_next)
