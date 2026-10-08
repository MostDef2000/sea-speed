# Spec: Transactional mutable API state persistence

- Issue: #394
- Specification: specs/394-transactional-api-state/spec.md

## Product outcome

The Sea Speed API persists every piece of mutable state through
`read_json_file`/`write_json_file` with a blanket read exception handler
(corruption silently degrades to defaults) and a **fixed** `.tmp` sibling
write. Concurrent writers — the 1 Hz worker state posts, the deploy-time ROI
migration (which runs while the OLD service is still serving) and multiple
uvicorn threads — can clobber each other's temporary files, and read-modify-
write feed/append loops (`events.insert(0, ...)`, crossings RMW) lose records
under concurrency. Corrupt files are masked instead of surfaced.

This change introduces `api/app/store.py` (standard library only):

1. Hardened JSON IO — reads are fail-loud (`JSON_READ_ERRORS = (OSError,
   ValueError)`; missing file yields the caller default, corruption raises),
   writes take a per-file flock and land through a uuid-unique temporary file
   plus `os.replace` (no shared fixed `.tmp`).
2. A transactional SQLite store (WAL) for hot operational state — line
   crossing records, the analytics event feed and the 1 Hz camera state —
   with per-operation connections (commit/rollback/raise), single-statement
   mutations, per-camera same-transaction DELETE caps (crossings 5000, events
   500) and a legacy-JSON startup migration that is an **ingestion-history
   idempotent merge** (every ingestion registers the record's canonical
   payload hash in a durable `ingestion_log` in the same transaction; a
   legacy record is skipped when its canonical payload is already retained
   on the camera or its hash was ever ingested, camera-state imported only
   when strictly newer than the stored row)
   and **necessity-gated**: an empty target fails closed on corrupt legacy
   input while a populated target reads the legacy mirror best-effort
   (warning + skip). The migration never deletes the legacy files.

`api/app/main.py` becomes SQLite-authoritative for state/events/crossings
with a best-effort legacy JSON projection mirror (dual-write window for
rollback and operator tooling), and the operator config endpoints
(speed-config, speed-lines, crossing-line, camera-preview state) surface
corrupt storage as HTTP 500 instead of silently degrading.

## User scenarios

- US-1: Two writers (API process + deploy migration) write the same JSON
  file concurrently; each write lands through its own unique tmp file under
  a per-file lock, so no write crashes with `FileNotFoundError` and no file
  ever contains a torn mix of two payloads.
- US-2: A JSON store file is corrupted (partial write, disk issue); the
  affected GET endpoints return HTTP 500 with an explicit message instead of
  pretending the store is empty.
- US-3: Eight crossing posts race; every record survives (single-statement
  SQLite inserts, no read-modify-write window).
- US-4: Long-lived stores stay bounded: crossings prune to 5000 and the
  event feed to 500 rows per camera in the same transaction as the insert.
- US-5: An existing VPS deploys this release; the startup migration merges
  the legacy JSON stores into SQLite (dedupe by retained canonical payload
  equality and by ingestion-log history, so re-upgrades pick up records
  the previous release wrote during a rollback window, repeated boots are
  no-ops and mirrors of live-appended rows never duplicate them; records
  that were ever ingested — including ones the cap has since pruned — are
  never resurrected, whatever their event timestamps), fails closed on corrupt legacy
  input while the target is still empty (deploy health gate rolls the
  release back), degrades to a warning when the store is already
  populated (a corrupt non-authoritative mirror must not fail every boot
  of a healthy store) and never deletes the legacy files the previous
  release still reads.
- US-6: A rollback to a pre-#394 release removes the live `store.py` copy
  cleanly; the old `main.py` does not import it. Activation promotes a
  staged `store.py` only when the selected release actually ships one, so a
  stale `.next` left by an interrupted install can never be promoted.

## Scope

- `api/app/store.py` (new): JSON IO primitives + SQLite hot-state store +
  migration primitives.
- `api/app/main.py`: rewire state/events/crossings to SQLite with legacy
  mirrors; fail-loud config/preview reads; startup migration; constants.
- `deploy/vps/deploy.sh`: atomic heredoc write in the ROI migration;
  `api/app/store.py` install plumbing (release completeness, download
  required list, install, activation with soft removal on rollback).
- Tests: `tests/test_api_state_transaction.py` (new behavioral suite, RED on
  base); minimal harness updates in `test_api_contract.py`,
  `test_line_crossing.py`, `test_road_event_hygiene.py`,
  `test_vps_deploy_transaction.py`.
- SDD: this trio.

Out of scope: frontend/, worker/, .github/, object registry (objects.sqlite3
already transactional), water-passages store, ROI migration semantics beyond
the atomic write.

## Requirements

- R-1: JSON IO hardening — `api/app/store.py` provides `read_json_file`
  (missing file → caller default; `OSError`/`ValueError` on corruption
  escape via `JSON_READ_ERRORS = (OSError, ValueError)`) and
  `write_json_file` (per-file flock, uuid-unique temporary file,
  `os.replace`, tmp cleanup; no shared fixed `.tmp` sibling).
- R-2: Transactional SQLite hot-state store (WAL, per-operation
  connections with commit/rollback/raise) for line crossings, the
  analytics event feed and 1 Hz camera state, each row carrying
  `camera_id`; single-statement mutations (no read-modify-write windows);
  per-camera same-transaction DELETE caps (crossings 5000, events 500);
  `upsert_camera_state` as an idempotent ON CONFLICT write.
- R-3: Startup migration — `import_legacy_state_store()` runs once at
  import time after the existing DB initialisations and is
  necessity-gated per (camera, kind) via `store.camera_has_rows`: an EMPTY
   target makes the read authoritative (unreadable/corrupt legacy JSON
   raises — fail closed), a NON-EMPTY target makes it best-effort (read or
   parse failure prints a warning to stderr and skips). Import is a
   canonical-payload idempotent merge: a record's canonical payload is
   `json.dumps(record, ensure_ascii=False, sort_keys=True)` — the exact
   bytes stored in `payload_json` — and the canonical payloads of the
   target camera's current rows (one query) form the dedupe set, so a
   legacy record already present is skipped (boot idempotency; mirrors of
    live-appended rows never duplicate them, while identical live
    submissions stay distinct as today); anti-resurrection is a durable
    ingestion identity, not a timestamp comparison — every ingestion
    (live append and import) registers the record's canonical payload
    hash in `ingestion_log` inside the same transaction, and a legacy
    record whose hash is already registered was ingested before (its row
    may since have been pruned) and is skipped, uniformly covering
    equal-timestamp, undated and unparseable records, while genuinely
    never-ingested rollback-period records merge regardless of their
    event timestamps; the log is bounded at 4×cap per (camera, kind)),
    inserted oldest-first to
    preserve legacy newest-first read order, capped per camera as today;
   camera-state import takes the legacy payload only when its `updated_at`
   is strictly newer than the stored row's (both sides must parse as ISO
   timestamps — an unusable timestamp never displaces stored state; an
   undated payload only seeds an empty row). The migration never deletes
   the legacy files.
- R-4: `api/app/main.py` rewiring — SQLite is authoritative for
  state/events/crossings; every committed mutation is mirrored best-effort
  to the legacy JSON projection (stderr log on failure, request never
  fails); config/preview reads (speed-config, speed-lines, crossing-line,
  camera state) wrap reads in `except store.JSON_READ_ERRORS` → HTTP 500;
  constants `STATE_DB_FILE`, `EVENTS_FEED_LIMIT`, `CROSSINGS_STORE_LIMIT`
  defined in the top block (import-time ordering).
- R-5: deploy.sh — ROI-migration heredoc writes atomically (uuid tmp +
  `os.replace`); `api/app/store.py` joins the release file set
  (completeness check, download required list, install) and is activated
  with the soft pattern bound to the selected release's content: staged
  `.next` is promoted only when the release ships `api/app/store.py` (the
  same condition as staging), otherwise the live copy and any stale `.next`
  are removed; the bootstrap capture also captures a live `store.py` next
  to the captured `main.py` when present.
- R-6: Behavioral test suite `tests/test_api_state_transaction.py` — RED
  against the base implementation for the fixed defects, green on head,
  with harness updates limited to the new store seam and no weakened
  assertions.

## Acceptance criteria

- AC-001: Concurrent JSON writers never corrupt each other or leave tmp
  debris (atomic round-trip; 25+25 alternating writers leave one valid
  file and no tmp leftovers).
- AC-002: The legacy fixed-tmp collision is eliminated — a deterministic
  barrier test fails on base (the `_FakePath` shim surfaces
  `TypeError: replace: dst should be string, bytes or os.PathLike`; the
  genuine base defect independently surfaces as `FileNotFoundError` from
  the consumed shared `.tmp` in the no-lost-update test) and self-skips
  on head (head's `write_json_file` lives in store.py).
- AC-003: Corrupt config stores surface as HTTP 500 on speed-config,
  speed-lines and crossing-line (base silently returned defaults → RED);
  the events endpoint reads SQLite authoritatively.
- AC-004: Concurrent crossing appenders never lose records (8
  barrier-forced racers; RED on base read-modify-write, zero losses on
  head).
- AC-005: Store caps hold: crossings prune to 5000 and the event feed to
  500 rows per camera, pruned in the same transaction as the insert.
- AC-006: Camera state is last-write-wins via upsert; absent state reads
  None.
- AC-007: The startup migration is an ingestion-history idempotent merge —
  rollback-window records written by the previous release are picked up on
  re-upgrade (T-C), duplicates (including mirrors of live-appended rows,
  V-A) are skipped, imports at the production caps preserve retained
  history with exact cap arithmetic (V-B), anti-resurrection is decided
  by ingestion-log history, not event time: equal-timestamp stale mirrors
  never resurrect pruned records nor churn retention (W-A), pruned
  undated records stay skipped while genuinely new undated rollback
  records merge (W-B), delayed rollback-period records with old event
  timestamps merge under free cap headroom (W-C), and repeated boots are
  zero-mutation with the registry bounded at 4×cap (W-D); camera-state
  import is newer-wins with
  unusable timestamps never displacing stored state (T-D, V-D); empty
  target + corrupt legacy input fails closed (T-B); populated store +
  corrupt legacy mirror warns to stderr, skips and leaves authoritative
  data intact (T-A); legacy files are never deleted.
- AC-008: Activation is release-bound: a store-less rollback release with a
  stale `${STORE_TARGET}.next` present removes both files and promotes
  nothing (T-E); a release shipping `store.py` stages and promotes it
  normally; the bootstrap capture keeps a live `store.py` with the captured
  `main.py`.
- AC-009: Regression battery green — full suite green on head; ruff E9/F
  clean; `bash -n` clean; changes left uncommitted for orchestrator
  admission.

## Runtime feedback

- RF-001: Operator actions expected: 0 — the deploy pipeline stages and
  activates `store.py` automatically; first boot after deploy runs the
  legacy migration during the health gate (fail-closed → automatic
  rollback on corrupt legacy input).
- RF-002: Failure evidence: HTTP 500 messages naming the corrupt store
  file for config/preview reads; `stderr` lines from best-effort legacy
  mirror failures — a corrupt mirror over a populated (non-authoritative)
  store logs "legacy <camera> <kind> mirror is unreadable and will be
  skipped" and the boot proceeds, while the same corruption over an empty
  target fails the boot closed; deploy rollback removes `store.py` when
  returning to a pre-#394 release.

## NFR assessment

- NFR-001 | Area: reliability | Target: concurrent writers can no longer destroy each other's temporary files; the lost-update window on crossings/events is eliminated (SQLite single-statement writes) | Validation: barrier-forced concurrency tests (25+25 alternating JSON writers, 8 SQLite racers) RED against base's fixed-tmp RMW; no-lost-update and atomic round-trip tests green on head | Evidence: test_write_round_trip_is_atomic, test_concurrent_writers_leave_one_valid_file_and_no_tmp, test_concurrent_appenders_never_lose_records | Status: PASS
- NFR-002 | Area: observability | Target: corruption surfaces as explicit HTTP 500 messages instead of silent defaults; legacy mirror failures print to stderr without failing requests | Validation: fail-loud endpoint tests RED on base (silent default); dual-write mirror exception-path review | Evidence: FailLoudReadTests, test_camera_preview_state_corruption_fails_loud | Status: PASS
- NFR-003 | Area: compatibility | Target: public API surface unchanged (61 routes, response shapes, ordering semantics); legacy JSON files stay fresh (projection mirrors) for the previous release and operator tooling during the rollback window | Validation: AST-harness regression suites (contract/line-crossing/road-hygiene) green; route-decorator count parity checked by peer verification | Evidence: test_api_contract.py, test_line_crossing.py, test_road_event_hygiene.py | Status: PASS
- NFR-004 | Area: security/robustness | Target: standard library only; parameterized SQL with whitelisted table names; per-camera row caps bound storage growth (5000 crossings / 500 events) | Validation: ruff clean; store.py code review (independent peer session); cap-enforcement tests | Evidence: test_caps_enforced_per_camera, peer verification report | Status: PASS
- NFR-005 | Area: rollback safety | Target: legacy files are never deleted by the API; deploy activation removes store.py when rolling back to a pre-#394 release; corrupt legacy store fails boot closed (deploy auto-rollback) | Validation: deploy transaction behavioral suite (20 tests); soft-pattern code review; migration fail-closed tests | Evidence: test_vps_deploy_transaction.py, StartupMigrationTests | Status: PASS
- NFR-006 | Area: reliability/data-integrity | Target: the legacy transition protocol survives the full rollback/retry lifecycle — imports are an ingestion-history idempotent merge (rollback-window records written by the previous release are picked up on re-upgrade; duplicates — including mirrors of live-appended rows — are skipped by canonical payload equality; anti-resurrection is decided by the durable `ingestion_log` registry, not event time: ever-ingested records are never resurrected whatever their timestamps, never-ingested delayed rollback records merge; per-camera cap respected with exact arithmetic), camera-state import is newer-wins with unusable timestamps never displacing stored state, and legacy reads are necessity-gated so a corrupt non-authoritative mirror can never fail a boot of a healthy authoritative store while the initial migration stays fail-closed; activation is bound to release content, not to a stale `.next` | Validation: T-A (populated store + corrupt mirror → no raise, stderr warning, authoritative data intact), T-B (empty target + corrupt legacy → raises), T-C (import → rollback-window append → re-import merges, dedupes, caps), T-D (newer/older camera-state), T-E (store-less rollback + stale `.next` removed; store release promotes), V-A (live row + mirror → no duplication across restarts), V-B (mixed imported + live rows at the 5000/500 caps → no eviction beyond exact arithmetic), W-A (equal-timestamp stale mirror → pruned record skipped, retention stable across repeated boots, no churn), W-B (pruned undated record skipped via registry, genuinely new undated rollback record merged), W-C (delayed rollback record with old event time + free cap headroom → merged), W-D (≥3 boots on a stable intact mirror → zero mutations after the first import; registry bounded at 4×cap after churn beyond the cap), V-D (unusable/absent updated_at → stored state stays) — all green on head | Evidence: test_rollback_window_records_are_merged_idempotent, test_live_rows_are_not_duplicated_by_mirror_import, test_import_at_production_caps_preserves_retained_history, test_equal_timestamp_stale_mirror_never_resurrects_or_churns, test_undated_records_obey_the_ingestion_registry, test_delayed_rollback_record_with_old_event_time_merges, test_repeated_boots_are_zero_mutation_and_registry_stays_bounded, test_camera_state_import_is_newer_wins, test_camera_state_import_ignores_unusable_timestamps, test_corrupt_legacy_mirror_is_best_effort_when_store_is_populated, test_corrupt_legacy_file_fails_closed, test_store_less_rollback_removes_live_store_and_stale_next, test_store_release_stages_and_promotes_normally | Status: PASS

## Deviations from the work order

- `event_feed`/`crossings` tables carry a `camera_id` column (the work
  order sketch omitted it) — required for per-camera caps and reads.
- deploy.sh received store.py install plumbing although the work order said
  "No other deploy.sh changes": without it the new `main.py` cannot boot on
  the VPS (the install step only staged `main.py`). The change is the
  minimal soft-install pattern mirroring the existing conditional file
  idiom.
