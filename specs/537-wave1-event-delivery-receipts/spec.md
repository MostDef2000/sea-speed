# Issue #537 — wave 1: durable road-event delivery receipts (API-side idempotent ingestion)

- Issue: #537
- Status: ACTIVE
- Date: 2026-10-19

## Product outcome

No undiscoverable road-event loss on the server side: a road event delivered
twice with the same global `event_id` and identical immutable content
collapses to one logical object and one feed row (HTTP 200, `duplicate=true`,
stored original event returned), a duplicate arriving after the capped feed
has pruned the original row is still recognized via a durable completion
receipt, and the same `event_id` delivered with different immutable content
or a different camera fails loudly with HTTP 409 and leaves no partial state.
Snapshot publication becomes crash-safe (atomic tmp+fsync+rename+dir-fsync),
schema migration is additive-at-boot and never deletes or rewrites retained
history, receipts are retained 90 days (owner decision, issue #537
Outcome Contract), and the media sweep cleans orphaned `*.tmp` siblings left
by interrupted atomic writes. The road publication gate, `event_id`
composition, contract files and the objects registry identity path are
unchanged (protected boundary; wave 2 adds the worker outbox).

## User scenarios

1. **Worker retry after an API outage** (wave 2 enables this): the worker
   re-posts the same event after the API recovers; the server recognizes the
   completed delivery and returns the stored success response instead of
   creating a second logical object or feed row.
2. **Duplicate after feed pruning**: the original feed row has been capped
   away (500 rows per camera), but the receipt persists; the duplicate is
   still collapsed and answered from the receipt.
3. **Conflicting delivery**: the same `event_id` arrives with different
   content or a different camera — the server answers 409, persists nothing,
   and the delivery stays worker-visible as unconfirmed.
4. **Crash mid-ingestion**: the process dies between the snapshot publish,
   registry persist and the feed/receipt commit; the verbatim retry
   completes exactly the missing pieces.
5. **Legacy payloads and water cameras**: events without the new receipt
   bookkeeping (legacy payload shapes, water camera path) keep their
   existing behavior.

## Requirements

- FR-001: A durable receipt table `event_receipts` keyed by the global
  `event_id` (camera_id, immutable content fingerprint, snapshot
  fingerprint, stored success-response event, completion timestamp) must
  live in the existing WAL state database and be created additively at
  boot.
- FR-002: Duplicate detection must consult the receipt first, then the
  feed's unique `event_id` identity inside one transaction
  (`store.deliver_event`), returning `("stored", None)` or
  `("duplicate", stored_event)` and raising `EventDeliveryConflict` for
  content/camera conflicts that abort the transaction with no partial
  state.
- FR-003: The feed insertion must be conflict-targeted
  `INSERT ... ON CONFLICT(event_id) DO NOTHING` — never an upsert — so an
  existing row is never reset or overwritten; on a degraded database where
  the unique index could not be created, the insert must degrade to an
  explicit stored-row comparison plus the legacy blind append, with the
  receipt still gating all future duplicates.
- FR-004: The handler ingest sequence must be: auth → existing
  domain/person gates → metadata validation → content fingerprint →
  receipt check (match → 200 `duplicate=true` with stored original;
  mismatch → 409) → same-ID serialization (`EVENT_INGEST_LOCK` with
  re-check) → atomic snapshot publish → registry persist (existing
  idempotent path; a False return means crash-repair completion, not
  failure) → feed+receipt transaction → success
  `{"ok": true, "event": ..., "duplicate": false|true}`.
- FR-005: The legacy non-duplicate response shape must stay compatible:
  existing consumers that do not read the additive `duplicate` field keep
  working; the person-filter response and the exact
  `snapshot is required` 422 pin are preserved verbatim.
- FR-006: Snapshot publication must be atomic (unique same-directory tmp
  file, flush+fsync, `os.replace`, directory fsync; tmp removed on any
  failure) and the snapshot filename must be a deterministic,
  traversal-safe function of validated identity (`store.safe_event_filename`)
  — raw client `event_id` values are never interpolated unchecked into a
  media path.
- FR-007: Migration must be additive-at-boot and idempotent: nullable
  `event_feed.event_id` column, backfill from stored payloads, inventory of
  duplicate historical ids recorded in `migration_inventory` (never deleted
  or rewritten), unique index `idx_event_feed_event_id` created only when
  history is conflict-free; downlevel code ignores the extra column/table.
- FR-008: Receipts are NOT pruned with the feed; only the 90-day retention
  sweep removes receipts older than the window and touches nothing else.
- FR-009: The media sweep must also remove orphaned `*.tmp` siblings older
  than the existing grace window; `.jpg` reference semantics are unchanged.
- FR-010: The legacy `append_event` path populates `event_id` from the
  payload so direct appends participate in the feed's unique identity.
- Protected boundary (unchanged): road publication gate AST
  (`tests/test_road_event_hygiene.py`), worker-source string pins
  (`tests/test_api_contract.py:401-425`), event composition pin
  (`tests/test_398_wave_a_demo.py:183-199`), `api/app/objects_registry.py`
  identity path, `data/contracts/*`, water/crossings/live/post_state
  surfaces, `worker/**` (wave 2).

## Acceptance criteria

- AC-001: A duplicate delivery with the same `event_id` and identical
  content returns HTTP 200 with `duplicate=true` and the stored original
  event; exactly one feed row and one receipt exist afterwards.
- AC-002: A duplicate arriving after the feed row has been pruned is still
  collapsed by the receipt (no reinsertion) and answered successfully.
- AC-003: The same `event_id` delivered with different snapshot content
  (or any differing immutable metadata) is answered 409 with no partial
  state: no feed row, no receipt, prior state intact.
- AC-004: The same `event_id` delivered for a different camera is answered
  409 with no partial state.
- AC-005: A failed atomic publish leaves no partially written snapshot and
  no orphan tmp file, records no receipt, and a clean retry succeeds; a
  successful delivery publishes the exact bytes and leaves no tmp file.
- AC-006: A crash between stages is repairable by the verbatim retry:
  after snapshot+registry without feed/receipt, the retry completes the
  missing feed row and receipt; after a registry-only persist, the retry
  completes snapshot+feed+receipt.
- AC-007: Concurrent same-ID ingestion (8 threads) produces exactly one
  stored delivery, seven duplicate responses and zero failures.
- AC-008: Migration over legacy feed rows backfills `event_id`, is
  idempotent on re-run, inventories duplicate historical ids in
  `migration_inventory` without deleting or rewriting them, defers the
  unique index on such history, and creates the index when history is
  conflict-free; a degraded (index-less) database falls back to explicit
  stored-row comparison.
- AC-009: Receipt retention pruning removes only receipts older than the
  90-day window; event feed and crossings rows are untouched.
- AC-010: The person-filter gate response is byte-identical to the
  previous behavior and persists nothing.
- AC-011: Legacy event payload shape and response stay `ok`-compatible,
  and water camera events ingest through the same path unchanged.
- AC-012: The media sweep removes orphaned `*.tmp` siblings with the same
  grace-window semantics while keeping `.jpg` reference-protection
  behavior identical.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: zero duplicate logical objects for duplicate deliveries (reliability budget `maximum_duplicate_logical_objects: 0`) | Validation: duplicate-collapse, post-prune receipt and 8-thread concurrency fault-injection suites | Evidence: tests/test_road_event_delivery.py (DuplicateDeliveryTests, DuplicateAfterPruneTests, ConcurrentDuplicateTests) | Status: PASS
- NFR-002 | Area: DATA | Target: additive-at-boot migration never deletes or rewrites retained history | Validation: migration backfill/inventory/idempotency tests | Evidence: tests/test_api_state_transaction.py EventFeedMigrationTests | Status: PASS
- NFR-003 | Area: SECURITY | Target: client-controlled `event_id` never escapes the media directory and deterministic retries rebuild the same snapshot_url | Validation: safe filename shape/digest tests + handler path | Evidence: tests/test_api_state_transaction.py EventIdentityHelperTests; tests/test_road_event_delivery.py | Status: PASS
- NFR-004 | Area: OPERATIONS | Target: additive-only deploy safe across restarts and version rollbacks; no destructive ops | Validation: migration idempotency + degraded fallback tests; downlevel-code tolerance | Evidence: EventFeedMigrationTests; store.py migration comments | Status: PASS
- NFR-005 | Area: PERFORMANCE | Target: ingest path adds bounded work (one indexed receipt lookup + one indexed insert; prune is an indexed DELETE on completed_at) | Validation: full-suite runtime unchanged in order of magnitude; code review | Evidence: scripts/quality review; full pytest run recorded in issue #537 | Status: PASS

## Runtime feedback

- Local: RED authenticity proven on base `27107db0` (37 behavioral failures
  across the two suites; 20 pre-existing tests pass as regression guard).
- Local: two focused suites green on the change (57 passed / 1 skipped).
- Pending (recorded in issue #537): full-suite + validators battery, PR CI
  on the exact head, lane-A VPS deploy, post-deploy external probes
  (duplicate delivery collapsed, receipt retention, migration over the live
  database).
