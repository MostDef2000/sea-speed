# Issue #537 — wave 2: worker durable outbox (durable road-event acceptance + delivery retries)

- Issue: #537
- Status: ACTIVE
- Date: 2026-10-21

## Product outcome

No undiscoverable road-event loss on the worker side: an accepted road event is
durably persisted (metadata + snapshot JPEG bytes) in a local SQLite WAL outbox
before acceptance is reported (`post_event` returns True only after durable
local acceptance), delivery retries run with bounded exponential backoff until
the server confirms — the merged wave-1 receipts collapse byte-verbatim
duplicates — and accepted rows are never discarded. Worker restart loses
nothing already accepted; recovery publishes pending rows even with no new
detections. The same `event_id` delivered with different immutable content or a
different camera fails loudly with HTTP 409 (server behavior, wave 1); the
worker treats 409 as a terminal accept-error that is never retried and never
dropped silently, surfaced through heartbeat metrics. Prolonged delivery
failure is visible in monitoring (heartbeat fields + worker health checks).
The road publication gate code and `event_id` composition remain unchanged
(protected boundary; wave 1 added the API-side receipts).

## User scenarios

1. **Worker retry after an API outage** (wave 1 enables the server side): the
   road worker accepts events while the API is unreachable; the outbox retains
   metadata + snapshot bytes and a single publisher retries with bounded
   backoff; after recovery every pending row is delivered byte-verbatim, the
   server answers from the receipt path (`duplicate=true` for redeliveries),
   and confirmed rows are deleted locally.
2. **Restart with pending rows**: the worker restarts mid-outage (power, deploy);
   on boot the outbox reopens its database and the publisher drains all
   accepted-but-unconfirmed rows even with no new detections.
3. **Disk-full at acceptance**: the seam fails closed — `post_event` returns
   False, the worker keeps its file-based behavior, and nothing is reported as
   accepted that was not durably persisted.
4. **Conflicting delivery**: the server answers 409 for the same `event_id`
   with different content or a different camera; the outbox increments the
   accept-error counter, retains the row (it remains the oldest-unconfirmed),
   never retries it and never drops it silently.
5. **Person-filtered road event**: the server answers
   `{"ok": true, "event": null}` — terminal success with nothing persisted
   server-side; the outbox deletes the row and posts no retry.

## Requirements

- FR-001: `worker/worker_outbox.py` (new) persists each accepted road event as
  one SQLite transaction (metadata JSON + snapshot JPEG bytes as a BLOB) in a
  WAL-mode database before acceptance is reported; snapshot bytes are captured
  at enqueue time because the file-based snapshots (`cv2.imwrite` to
  `EVENTS_DIR`) are rotated later.
- FR-002: the outbox database is a single SQLite file for the road contour,
  default `shared/road-runtime/road-worker-outbox.sqlite3` alongside the road
  heartbeat, overridable via `SEA_SPEED_OUTBOX_DB`; WAL mode; schema init is
  EXPLICIT at outbox open (never lazily from a publisher-thread path — the
  wave-1 "lazy migration" gotcha, KB INFRASTRUCTURE.md gotcha #34).
- FR-003: the entrypoint seam `post_event`
  (`worker/ubuntu_worker_entrypoint.py:162-171`) returns True only after
  durable outbox acceptance; disk-full/SQLite write failure returns False
  (fail-closed; the worker keeps its file-based behavior); the in-memory event
  queue (maxsize 32, consumer swallows exceptions, no retry, no persistence) is
  retired from the event path.
- FR-004: sync publish mode (`_is_sync_publish`, `SEA_SPEED_SYNC_PUBLISH`)
  keeps its passthrough semantics
  (`tests/test_ubuntu_worker_runtime_provenance.py` pins).
- FR-005: a dedicated publisher thread delivers rows FIFO with bounded
  exponential backoff (base 1s, factor ×2, cap 60s, jitter injectable via a
  seeded RNG so tests are deterministic); NO attempt-based discard; restart
  recovery publishes pending rows even with no new detections.
- FR-006: the publisher posts with its own HTTP client
  (`worker/worker_transport.py` stays untouched and protected — it does not
  expose the response body the outbox needs): requests-based POST, same URL
  derivation (`SEA_SPEED_API_URL` → `/api/analytics/{camera_id}/events`),
  Bearer `SEA_SPEED_API_TOKEN`, multipart `metadata` (byte-verbatim JSON
  string) + `snapshot` file; the new module's import allowlist is stdlib
  (json, time, pathlib, hashlib, sqlite3, threading) + requests only, declared
  in the module docstring per the guarded-import convention of the worker_*.py
  modules.
- FR-007: response handling: HTTP 200 `{"ok": true, "event": ..., "duplicate":
  false}` → confirmed, row deleted (delete-on-confirm; the server keeps 90-day
  receipts, so local copies are not needed after confirmation); 200
  `duplicate=true` → confirmed (receipt hit), row deleted; 200
  `{"ok": true, "event": null}` (person-filtered road event) → terminal
  success, row deleted, no retry; 409 → terminal accept-error: never retried,
  never dropped silently, accept-error counter incremented and the row retained
  so the oldest-unconfirmed age continues to reflect undelivered rows; any
  other error → send error, row retried with backoff.
- FR-008: heartbeat metrics are additive only: pending count,
  oldest-unconfirmed age, send errors, retries, accept errors, last confirmed —
  surfaced via worker stdout markers parsed by
  `deploy/worker/ubuntu/observed-worker-runner.py` (additive `record_line`
  branches + state keys) and additive report fields in
  `deploy/worker/ubuntu/check-worker-health.py`; `schema_version` stays 1 and
  its consumers (`verify-runtime-progression.py`,
  `tests/test_ubuntu_worker_observability.py:178-182`) keep passing.
- FR-009: `worker/worker_outbox.py` joins the Ubuntu compatibility gate
  `MODULE_SOURCES` union (`scripts/worker/check_ubuntu_compatibility.py:26-35`),
  the five module count pins move 8→9
  (`tests/test_worker_transport_module.py:371-375`,
  `tests/test_worker_crossings_module.py:476`,
  `tests/test_worker_live_module.py:536`,
  `tests/test_worker_tracking_module.py:495`,
  `tests/test_worker_roi_module.py:632`) and the union gains
  `worker/worker_outbox.py`.
- FR-010: the installer/artifact fail-closed lists gain
  `worker/worker_outbox.py` together: `deploy/worker/ubuntu/install-systemd.sh`,
  `scripts/quality/build_exact_artifacts.py`,
  `scripts/quality/validate_exact_artifacts.py`, `scripts/ci/validate_repo.py`.
- FR-011: retries are byte-verbatim: the metadata JSON string and snapshot
  bytes re-posted on retry are byte-identical to the accepted delivery, keeping
  the server content fingerprint (SHA-256 of the canonical normalized event
  JSON including camera_id/snapshot_url/created_at) stable so verbatim retries
  collapse via receipts and never 409.
- FR-012: post_state coalescing, water passage posting, crossing queue
  (`_crossing_pending_posts`), live envelopes, the road publication gate latch
  (`worker/hls_motion_yolo_worker_events.py:721-723`) and `event_id`
  composition keep working unchanged.

## Acceptance criteria

- AC-001: `post_event` returns True only after metadata + snapshot bytes are
  durably persisted in the outbox; an event accepted and then immediately
  "crashed" (no further worker writes) is still in the outbox afterwards.
- AC-002: with the API unreachable, accepted rows remain pending, the publisher
  keeps retrying with bounded backoff and discards nothing; when the API
  recovers, every pending row is delivered and confirmed.
- AC-003: a byte-verbatim re-delivery of an already-confirmed event is answered
  200 `duplicate=true` by the server receipt path and the outbox deletes the
  row on confirm — one logical object/feed entry server-side.
- AC-004: a worker restart with pending rows loses nothing already accepted;
  recovery publishes pending rows even with no new detections.
- AC-005: a disk-full/SQLite write failure at the seam returns False
  (fail-closed) and never reports a durable acceptance that did not happen.
- AC-006: retry delays follow base 1s, factor ×2, cap 60s with seeded-jitter
  determinism; observed delays stay within the bounded envelope and no row is
  discarded after any number of attempts.
- AC-007: a 409 conflict is terminal: never retried, never silently dropped;
  the accept-error counter increments, the row remains the
  oldest-unconfirmed, and subsequent events continue to be delivered.
- AC-008: a person-filtered road event (`{"ok": true, "event": null}`) is
  terminal success: the row is deleted, no retry is posted, nothing is
  persisted server-side.
- AC-009: heartbeat metrics (pending count, oldest-unconfirmed age, send
  errors, retries, accept errors, last confirmed) are visible via
  `observed-worker-runner.py` state keys and `check-worker-health.py` report
  fields; `schema_version` stays 1 and existing observability/provenance tests
  keep passing unmodified.
- AC-010: the compatibility gate `MODULE_SOURCES` is the nine-file union
  including `worker/worker_outbox.py` and the five module count pins read 9.
- AC-011: the installer/artifact fail-closed lists gain
  `worker/worker_outbox.py` together and the exact-artifact/repo validators
  stay green.
- AC-012: protected surfaces stay green unmodified: sync-publish passthrough
  pins, post_state coalescing, water passage, crossing queue, live envelopes,
  road publication gate AST pins, `event_id` composition pin and the
  joined-worker-source string pins
  (`tests/test_api_contract.py:401-425` over
  `tests/support/worker_source.py` `DEFAULT_WORKER_SOURCES`).
- AC-013: retries are byte-verbatim: the re-posted metadata JSON string and
  snapshot bytes are identical to the accepted delivery.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: zero accepted-event loss across restarts and API outages (delete-on-confirm only; no attempt-based discard) | Validation: outage-recovery, restart-recovery and duplicate-collapse fault-injection suites | Evidence: tests/test_worker_outbox_delivery.py 23 tests + tests/test_worker_outbox_module.py 9 tests (focused run 32 passed on head 8a51a07); OutboxFaultInjectionTests (outage→recovery FIFO delivery with nothing discarded, restart recovery without new detections, duplicate collapse with delete-on-confirm, no attempt-based discard after 12 failures) | Status: PASS
- NFR-002 | Area: DATA | Target: explicit schema init at outbox open in a WAL database; a failed/corrupt open or disk-full write never reports durable acceptance | Validation: disk-full, init-at-open and open-failure fault-injection tests | Evidence: tests/test_worker_outbox_module.py WorkerOutboxSchemaTests (schema + lifetime meta counters created at open before any enqueue and without the publisher thread; WAL active; synchronous=FULL per-commit fsync pinned, D-112) + tests/test_worker_outbox_delivery.py disk-full fail-closed (OutboxDurabilityTests module arm incl. missing-snapshot OSError, EntrypointSeamTests seam arm); a failed open propagates and the seam degrades fail-closed by construction (D-103 seam path) | Status: PASS
- NFR-003 | Area: OPERATIONS | Target: prolonged delivery failure visible within one heartbeat interval (pending count, oldest-unconfirmed age, send errors, retries, accept errors, last confirmed) | Validation: runner state-key and health report-field tests with schema_version 1 consumers green | Evidence: tests/test_worker_outbox_delivery.py OutboxHeartbeatObservabilityTests (real subprocess marker → six observed-worker-runner.py state keys, none/noise line handling, check-worker-health.py additive report fields with backward-compatible nulls; schema_version 1; tests/test_ubuntu_worker_observability.py consumers green in the regression guard) | Status: PASS
- NFR-004 | Area: PERFORMANCE | Target: acceptance adds one local SQLite WAL transaction plus bounded snapshot byte capture; publisher is one thread with backoff bounded at a 60s cap | Validation: backoff-bounds test; full-suite runtime unchanged in order of magnitude | Evidence: backoff envelope + jitter determinism pinned (OutboxFaultInjectionTests backoff cases; extreme-attempt overflow guard pinned per D-112); acceptance cost is one snapshot file read + one SQLite WAL INSERT with synchronous=FULL fsync per commit (worker/worker_outbox.py enqueue, D-109/D-112); CI green on the exact head 8a51a07 (all 8 PR checks, runs 39468294685 + 39468294700) — no runtime timing measurements exist yet, so the order-of-magnitude target stays unproven; runtime timing evidence lands with the worker-deploy acceptance probes | Status: CONCERNS
- NFR-005 | Area: SECURITY | Target: no new credentials, endpoints or metadata mutation — the outbox reuses Bearer SEA_SPEED_API_TOKEN and the existing URL derivation; module imports limited to stdlib + requests | Validation: byte-verbatim retry test; import-allowlist module test (guarded-import convention) | Evidence: tests/test_worker_outbox_module.py WorkerOutboxImportAllowlistTests (stdlib + guarded-requests allowlist, forbidden offline/process layers absent, allowlist declared in the module docstring) + tests/test_worker_outbox_delivery.py test_retry_posts_identical_metadata_string_and_snapshot_bytes (same URL derivation, Bearer SEA_SPEED_API_TOKEN, byte-verbatim re-posts) | Status: PASS

## Protected / out of scope

- Water passage posting, crossing queue (`_crossing_pending_posts`), live
  envelopes, post_state coalescing.
- `worker/worker_transport.py` and its import allowlist.
- `data/contracts/*` and `contract-policy-v1.json`.
- Telemetry schema semantics.
- M2M auth topology.
- Road publication gate AST pins (`tests/test_road_event_hygiene.py:51-104`).
- `event_id` composition pin (`tests/test_398_wave_a_demo.py:183-199`).
- No attempt-based event discard.
- Never weaken or delete tests.

## Runtime feedback

- Local: RED authenticity proven — three neutralization shims (409-terminal
  handling, backoff envelope, durable enqueue) and five fix-simulation
  shims, each FAIL under the shim and PASS without it; the two DEF-1 pins
  ran RED against the pre-fix tree (1 failed / 20 passed and 1 failed /
  21 passed observed) and are GREEN after the in-wave fix
  (worker/worker_outbox.py:388-389 confirmed, :400-401 terminal at head
  8a51a07; D-111 in plan.md); the two pre-merge validator-finding pins ran
  RED→GREEN (D-112, fix commit 8a51a07).
- Local: final battery green on head 8a51a07 (orchestrator-observed) —
  focused suites tests/test_worker_outbox_delivery.py (23 tests) +
  tests/test_worker_outbox_module.py (9 tests) → 32 passed; protected-surface
  regression guard green (82 passed / 6 subtests); full battery 145 passed +
  6 subtests across 14 suites; ruff clean; validate_repo green (772 files);
  validate_sdd green; compatibility gate compatible=True; functional probe
  all-probes-OK; PR CI all 8 checks green on the exact head (runs
  39468294685, 39468294700).
- Pending (recorded in issue #537): exact-green-head merge, lane-A Ubuntu
  worker/relay deploy (worker first; pending outbox rows preserved and
  paused, not dropped), post-deploy probes (outage→recovery delivery,
  restart recovery, duplicate collapse, 409 visibility, heartbeat fields).
- Reconciled (2026-10-21, same flow as the wave-1 trio): delivery tasks
  T-537-100..T-537-109 are [x] with Evidence (T-537-109 = CI gate: all 8 PR
  checks green on head 8a51a07), TEST/NFR Evidence is filled with suite
  references and RISK-001..006 are MITIGATED; merge, lane-A deploy and
  post-deploy probes remain orchestrator-owned.
