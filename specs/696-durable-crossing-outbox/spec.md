# Spec: #696 — durable crossing delivery through the existing worker outbox

- Issue: #696
- Specification: `specs/696-durable-crossing-outbox/spec.md`
- Authorization: wave-9 admission (issue #696), branch
  `agent/wave9-696-durable-crossing-outbox`, base
  `172e938b43ad791bcc968e1ea9795e10c98be9ab`.
- Related: #537 wave 2 (worker durable outbox), #397 wave 6 (crossing module).
  A separate test worker owns `tests/**`; production code and this SDD trio are
  the only artifacts of this change.

## Product outcome

Ubuntu worker crossings stop being best-effort. Today a detected crossing is
appended to the in-memory `_crossing_pending_posts` list and posted by
`flush_crossing_posts`; an API outage, a transport error or a process restart
silently drops it. This change routes Ubuntu crossing acceptance through the
SAME durable outbox the road events already use (#537): `update_crossing_counts`
gets an optional synchronous acceptance callback, the Ubuntu entrypoint binds it
to the existing `_ensure_outbox()` instance, and a crossing is written as one
`crossing_pending` row (empty snapshot BLOB) BEFORE the counter, the track side,
`last_cross` and the returned event are committed. The single publisher thread
drains both row kinds FIFO by `id` and dispatches strictly by the stored status;
crossing rows post the crossing API (same URL derivation as
`worker_transport.post_crossing`) and are confirmed only by
`{"ok": true, "event_id": <same id>}`. No new database, table, queue thread,
flag or main-loop rewrite; the road `_post` and its HTTP classifications are
untouched.

## User scenarios

Feature: durable crossing delivery through the existing outbox

  Rule: a crossing is durably accepted before it is counted

    Scenario: crossing detection persists before counting
      Given the Ubuntu worker has the durable crossing callback bound
      And the shared outbox is open
      When a tracked object crosses the configured line
      Then a crossing_pending row with an empty snapshot BLOB is committed
      And only then are the counters, the track side, last_cross and the
        returned event updated
      And the in-memory crossing list stays empty

    Scenario: persistence failure does not count or silently post the crossing
      Given the outbox INSERT fails (disk full or SQLite error)
      When a tracked object crosses the configured line
      Then no counter, track side, last_cross or returned event is updated
      And no crossing is appended to the in-memory list
      And a "crossing accept failed" line is written to stdout
      And the track keeps its previous side so the next frame can retry

  Rule: an accepted crossing survives a crash, kill or restart

    Scenario: kill before the HTTP send replays on restart
      Given a crossing is durably persisted as a crossing_pending row
      And the worker process is killed before the publisher sends it
      When the worker restarts and reopens the same outbox database
      Then the publisher selects the row by its stored crossing_pending status
      And posts the byte-identical metadata with the same event_id
      And the crossing appears once the API confirms the acknowledgement

  Rule: crossing delivery uses its own endpoint and confirmation

    Scenario: terminal 4xx is retained as terminal_error
      Given a crossing_pending row
      When the crossing API answers a permanent 4xx (for example 400 or 403)
      Then the row becomes terminal_error and is never retried
      And the row stays in the outbox and counts as unconfirmed

    Scenario: transient failures retry instead of dropping
      Given a crossing_pending row
      When the request fails at transport level or the API answers 5xx, 408
        or 429, or the acknowledgement is malformed or carries another event_id
      Then the row stays crossing_pending
      And it is retried with the existing bounded exponential backoff
      And only {"ok": true, "event_id": <the same event id>} confirms it

  Rule: rollback to the previous binary isolates crossing rows

    Scenario: an older binary leaves crossing rows untouched
      Given crossing_pending rows exist in the outbox
      When the worker is rolled back to the previous main binary
      Then that binary selects only status='pending'
      And the crossing rows stay untouched for forward recovery
      And no crossing row is posted to the road /events endpoint

## Requirements

1. `worker/worker_crossings.py`: `update_crossing_counts(detections, now=None,
   accept=None)` gains the OPTIONAL synchronous acceptance callback; the hook
   is bound once via `set_crossing_accept` (module hook) or passed explicitly.
   The crossing dict is built once. When a callback is bound, it is invoked
   BEFORE the crossing-side transition, `last_cross`, the counters and the
   returned event are committed; a falsy return or an exception prints a
   `crossing accept failed` line and leaves all of them untouched. The
   transport-owned `_crossing_pending_posts` list is appended to only when no
   callback is bound (non-Ubuntu callers); it is never an Ubuntu fallback.
2. `worker/ubuntu_worker_entrypoint.py`: the Ubuntu wiring block binds the
   callback (`_bind_crossing_acceptance()` → `set_crossing_accept`) to the SAME
   lazily opened `_ensure_outbox()` instance. A stable namespaced event ID
   (`crossing:<camera_id>:<created_at>:<track_id>:<direction>`) and the
   camera/profile/domain identity are frozen once, with the original
   `created_at`, into the metadata before `enqueue_crossing`.
3. `worker/worker_outbox.py`: the existing outbox gains the `crossing_pending`
   row status (existing TEXT column, no schema migration) written by
   `enqueue_crossing` with an empty snapshot BLOB. Only the common INSERT is
   factored; the road `enqueue(event_id, metadata_json, snapshot_path)`
   signature, snapshot read and `pending` status are intact.
4. The publisher selects BOTH pending statuses ordered by the existing `id`,
   includes both in pending metrics, and dispatches strictly by the selected
   status. Terminal rejections reuse `terminal_error`; no endpoint is inferred
   from an empty JPEG or from a user-controlled metadata field.
5. The crossing POST derives the URL exactly as
   `worker/worker_transport.py:237-260` (`SEA_SPEED_API_URL` with the last path
   segment replaced by `crossings`), uses the Bearer token, sends
   `data={"metadata": json.dumps(...)}` and NO file, and confirms only
   `ok: true` with a matching `event_id`. Permanent 4xx (except 408/429) are
   terminal; 5xx, 408/429, transport errors and malformed acknowledgements are
   retryable. The road `_post`/`_deliver` success log is not reused for
   crossings; the road HTTP classifications are unchanged.
6. No new feature flag: a disabled flag would keep losing crossings. Rollback is
   a lane-A deploy of the previous main SHA; the old binary selects only
   `status='pending'`, so crossing rows remain untouched for forward recovery.
7. Delivery semantics are at-least-once: stable event IDs make replays
   identifiable; the duplicate window is between the API insert and the local
   acknowledgement. Server-side deduplication is out of scope (the API contract
   is unchanged).
8. One ordered outbox means a retrying crossing can delay later road rows (FIFO
   head-of-line). This is accepted and documented; it is not a road
   wire-semantics change.

## Delivery semantics (at-least-once)

- **Why at-least-once rather than idempotent end-to-end.** The crossing API
  returns `{"ok": true, "event_id": ...}` but keeps no delivery receipt and does
  not deduplicate by `event_id`. A crash after the API insert and before the
  local delete therefore redelivers the same event ID and the API appends a
  second crossing record. Closing that window needs a server-side receipt
  contract, which is explicitly out of scope; the stable ID keeps every replay
  identifiable for operators.
- **Duplicate window.** Between "API inserted the crossing" and "worker deleted
  the local row". Any failure inside that window replays the crossing exactly
  once more per restart cycle.
- **Shared FIFO consequence.** Road events and crossings share one publisher
  thread and one `ORDER BY id` selection. While the head row waits out its
  bounded backoff (base 1s, x2, cap 60s), later rows of either kind wait too.
  A persistently failing crossing therefore delays road delivery by at most the
  current backoff interval; the heartbeat `pending`/`oldest` metrics expose it.
  No road wire format, endpoint or acknowledgement handling changes.

## Acceptance criteria

- AC-001: On Ubuntu, a detected crossing is written as a `crossing_pending`
  outbox row (empty snapshot BLOB, stable namespaced event ID, frozen
  created_at/camera/profile/domain) synchronously before the counter, track
  side, `last_cross` and returned event are committed; the in-memory crossing
  list stays empty.
- AC-002: If persistence fails, `update_crossing_counts` writes a
  `crossing accept failed` line and leaves counters, track side, `last_cross`,
  returned event and the in-memory list untouched; the previous side is kept so
  the next frame retries the crossing.
- AC-003: After a kill/restart, the publisher replays a surviving
  `crossing_pending` row with byte-identical metadata and the same event ID, so
  at-least-once delivery survives the crash.
- AC-004: Crossing delivery posts the crossing endpoint (URL derived exactly as
  `worker_transport.post_crossing`), sends metadata only, and is confirmed only
  by `ok: true` with a matching `event_id`; permanent 4xx (except 408/429) is
  `terminal_error` and retained, while 5xx, 408/429, transport errors and
  malformed or mismatched acknowledgements retry. Road `/events` handling is
  unchanged.
- AC-005: A rollback to the previous binary leaves `crossing_pending` rows
  untouched (old binary selects only `status='pending'`), no crossing row is
  ever posted to `/events`, both statuses are counted in pending metrics and
  selected in one `id`-ordered FIFO, and a non-Ubuntu caller keeps the legacy
  list path.

## Runtime feedback

- Before this change, `update_crossing_counts` appended to
  `_crossing_pending_posts` and `flush_crossing_posts` posted on a best-effort
  basis; any HTTP failure or restart lost the crossing with no local trace.
- Constraint discovered: `tests/test_line_crossing.py` execs AST-extracted
  crossing functions into a stub namespace that has no new module globals, so
  the hook is read with `globals().get("_crossing_accept")` inside
  `update_crossing_counts`; a bare global reference raises `NameError` there.
- Constraint discovered: `tests/test_ubuntu_worker_runtime_provenance.py` and
  `tests/test_worker_outbox_module.py` load the entrypoint with a mocked worker
  module, so the crossing module import is function-local and only an
  `ImportError` is tolerated; the shipped Ubuntu artifact set always contains
  `worker_crossings.py`.
- Constraint discovered: `tests/test_worker_crossings_module.py` pins the exact
  worker re-export list (six crossing defs) and the crossings import allowlist;
  the new setter stays in `worker_crossings.py` and the entrypoint imports it
  directly — the worker re-export block is untouched.
- The road row literal stays `pending` so the pre-change binary keeps selecting
  it; no schema migration is needed because `status` is an existing TEXT column.

## NFR assessment

- NFR-001 | Area: Reliability | Target: an accepted Ubuntu crossing is durably committed before it is counted, and a persistence failure never counts, advances or silently posts a crossing | Validation: `worker_crossings.py:170-187` acceptance-before-commit block + scratch oracle (failed callback left `left_to_right` at 0 and the RAM list empty; the next frame retried and counted once) + entrypoint binding at `ubuntu_worker_entrypoint.py:843`; dedicated test-worker oracle PENDING (`tests/**` owned by the test worker) | Evidence: `python3 /tmp/opencode/696-smoke.py` → `CROSSING SEAM OK` / `OUTBOX CROSSING OK`; py_compile and ruff green | Status: CONCERNS
- NFR-002 | Area: Compatibility | Target: rollback isolation — the previous binary selects only `status='pending'`, crossing rows stay untouched, no crossing is posted to `/events`, and the road `_post`/`enqueue` contract is byte-identical | Validation: `_head_row` selects `IN ('pending','crossing_pending')` (worker_outbox.py:421-430), road `enqueue` delegates to the shared INSERT with `_ROAD_PENDING` (worker_outbox.py:255-272); existing suites `tests.test_worker_outbox_module` + `tests.test_worker_outbox_delivery` (33 tests) and `tests.test_line_crossing` + `tests.test_worker_crossings_module` (64 tests together with provenance) green | Evidence: observed unittest runs below; no road assertion changed | Status: PASS
- NFR-003 | Area: Operability | Target: both pending kinds appear in `pending_count()`/`snapshot()`, crossing confirmations/terminal/send errors have distinct log lines, and no new environment variable or feature flag is introduced | Validation: parameterized `WHERE status IN (?, ?, ?)` in pending metrics (worker_outbox.py:308-330); distinct `POST crossing ok` / `outbox crossing accept_error` / `outbox crossing send error` lines (worker_outbox.py:493-535); no new env reads beyond the existing `SEA_SPEED_*`/`CAMERA_ID`/`ANALYTICS_PROFILE` derivation mirrored from `worker_transport.post_crossing` | Evidence: scratch oracle observed all three crossing log lines and both-status metrics; py_compile/ruff green | Status: PASS
- NFR-004 | Area: Performance | Target: one publisher thread, one database and the existing bounded backoff (base 1s, x2, cap 60s) serve both row kinds; shared-FIFO head-of-line delay is bounded by the current backoff interval and visible in heartbeat metrics | Validation: single `_publish_loop`/`_head_row` selection over both statuses; no second thread/DB introduced (worker_outbox.py:380-420, 421-430); `pending`/`oldest_unconfirmed_sec` include crossing rows | Evidence: design reviewed against the existing outbox internals; existing outbox suite (backoff/retry/metrics) stays green | Status: PASS
