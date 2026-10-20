"""Worker durable outbox for Sea Speed analytics events (issue #537 wave 2).

Purpose (FR-001..FR-012, decisions D-101..D-110 of
specs/537-wave2-worker-outbox/): a class-based SQLite WAL outbox that
persists every accepted road event (byte-verbatim metadata JSON string +
snapshot JPEG bytes as a BLOB) in ONE transaction before acceptance is
reported, then delivers rows FIFO from a single daemon publisher thread with
bounded exponential backoff (base 1s, factor x2, cap 60s, injectable seeded
jitter). Rows are deleted only on server confirmation (delete-on-confirm;
the server keeps 90-day receipts); a byte-verbatim redelivery is answered
``duplicate=true`` from the receipt path and confirms identically. HTTP 409
is a TERMINAL accept-error: the accept-error counter increments, the row is
retained with ``status='terminal_error'`` so it is never re-picked by the
publisher yet still counts as unconfirmed (the oldest-unconfirmed age keeps
reflecting undelivered rows). ``{"ok": true, "event": null}`` (person-filtered
road event) is terminal success with nothing persisted server-side: the row
is deleted and no retry is posted. NO attempt-based discard: a row is only
ever removed by a confirmed delivery (or operator intervention via
SEA_SPEED_OUTBOX_DB).

Import allowlist (guarded-import convention, D-102): stdlib json, time,
pathlib, hashlib, sqlite3, threading, os, random + requests only. requests is
imported guarded: the persistence layer (schema init, enqueue, snapshot)
works without requests installed; the publisher then records send errors and
retries (rows stay pending, never dropped). The guarded import runs once at
module load and _post reads that module-level binding, so it does not
self-heal within a process lifetime: installing requests while the worker
runs is picked up on the NEXT process start, when the module is re-imported
and the import succeeds. Deliberate deviation from the
D-102 enumeration, reported to the delivery orchestrator: ``os`` is required
for the FR-002 ``SEA_SPEED_OUTBOX_DB`` override and the FR-006 URL/token
derivation (SEA_SPEED_EVENT_API_URL / SEA_SPEED_API_URL /
SEA_SPEED_API_TOKEN) because the protected worker_transport.py cannot be
consumed for env reads without importing its module; ``random`` is required
for the FR-005 default jitter source. NO cv2/numpy/ultralytics/av and NO
subprocess/socket - persistence and delivery stay in their own layers.

Thread-safety: one WorkerOutbox instance per worker process. enqueue() is
called from the worker main-loop thread; the publisher daemon thread (started
via start()) is the only other accessor. Every database access - enqueue,
publisher updates, snapshot() - happens under one instance lock around a
single sqlite3 connection opened with check_same_thread=False; the network
POST is deliberately performed OUTSIDE the lock so acceptance is never
blocked by an in-flight delivery. enqueue() is called from the worker main
loop thread; the schema is created in __init__ on that same caller thread -
never from a publisher-thread path.

Explicit-init rationale (D-103): schema creation happens eagerly in
__init__ at outbox open - never lazily from a publisher-thread path (wave-1
"lazy migration" gotcha, KB INFRASTRUCTURE.md gotcha #34). A failed open or
init propagates to the seam, which fails closed (falls back to the wave-1
synchronous poster) and never claims durable acceptance.

Schema (outbox schema version 1):
    outbox_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,      -- UTC wall-clock ISO acceptance time
        metadata TEXT NOT NULL,        -- byte-verbatim JSON string (D-109)
        snapshot_bytes BLOB NOT NULL,  -- JPEG bytes captured at enqueue time
        pending_since REAL NOT NULL,   -- time.monotonic() at acceptance
        attempts INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        send_errors INTEGER NOT NULL DEFAULT 0,
        retries INTEGER NOT NULL DEFAULT 0,
        accept_errors INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending')
    outbox_events_status_id_idx(status, id)
    outbox_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)

status semantics (FR-007/D-104): 'pending' rows are re-picked FIFO by the
publisher; 'terminal_error' rows (HTTP 409 accept-errors) are never
re-picked but stay in the table and count as unconfirmed, so the
oldest-unconfirmed age keeps reflecting undelivered rows (AC-007).

Counter semantics: ``attempts`` counts delivery attempts per row;
``send_errors`` counts failed send attempts per row (exceptions, non-200,
200 without ok:true); ``retries`` counts re-delivery attempts of a row that
already failed at least once (a retry that succeeds still counts);
``accept_errors`` counts 409 terminal accept-errors per row. The heartbeat
snapshot reports LIFETIME totals kept in outbox_meta
(outbox_send_errors_total / outbox_retries_total /
outbox_accept_errors_total) so delete-on-confirm cannot erase delivery
history; last_confirmed is a wall-clock epoch or null.

Clock note (per implementation order): pending_since uses time.monotonic(),
so ages are comparable only within one host uptime. A process restart on the
same host is unaffected (the monotonic clock continues across process
restarts, so surviving rows keep aging from their original acceptance).
After a HOST REBOOT a surviving row's pre-reboot pending_since lies ahead of
the restarted monotonic clock, so its age clamps to 0.0 (max(0.0, ...) in
snapshot()) until the row turns over; created_at keeps the wall-clock
acceptance time for operator inspection.

Delivery contract: POST with the SAME URL derivation, auth header and
multipart layout as worker_transport.post_event (mirror, not import -
worker_transport stays untouched/protected and does not expose the response
body, D-102): SEA_SPEED_EVENT_API_URL, else derived from SEA_SPEED_API_URL
by replacing the last path segment with ``events``; Bearer
SEA_SPEED_API_TOKEN; ``metadata`` posted byte-verbatim; snapshot bytes as
``event.jpg`` (image/jpeg). Response handling per FR-007/D-110: 200 with
``ok: true`` (duplicate false, duplicate true, or person-filtered
``event: null``) is a confirmed completion and deletes the row; 409 is a
terminal accept-error (row retained, never retried, never dropped
silently); anything else is a send error retried with bounded backoff.

Backoff (FR-005/D-104): delay = min(60, 1 * 2**(attempts-1)) with jitter.
The jitter source is injectable via ``jitter_function`` (a zero-argument
callable returning floats in [0, 1); default uses the random module) so
tests are deterministic with a seeded RNG. The jittered delay is
``raw + jitter_function() * 0.25 * raw`` (i.e. in [raw, 1.25 * raw))
capped at 60s, so a deterministic rng of 0 reproduces the exact
base-1s/x2/60s envelope and observed delays never exceed the cap. No row
is ever discarded after any number of attempts. Scheduling is strict FIFO
head-of-line: the single publisher thread serializes sends, and while the
head row waits out its backoff the rows behind it wait too (bounded retry
load: one attempt per backoff interval for the head row).
"""

import hashlib
import json
import os
import random
import sqlite3
import threading
import time
from pathlib import Path

try:
    import requests
except Exception:  # pragma: no cover - persistence must work without requests
    requests = None  # type: ignore[assignment]

_SCHEMA_VERSION = 1
_BACKOFF_BASE_SEC = 1.0
_BACKOFF_FACTOR = 2.0
_BACKOFF_CAP_SEC = 60.0
# Exponent clamp applied BEFORE the power (see _backoff_delay): 2**6 = 64
# already exceeds the 60s cap, and an unclamped 2.0**1024 raises OverflowError -
# the publisher retries indefinitely, so attempt counts are unbounded. Keeps
# the exact 1/2/4/8/16/32/60 envelope.
_BACKOFF_EXPONENT_CAP = 6
_METRIC_INTERVAL_SEC = 5.0
_ERROR_TEXT_LIMIT = 300


class WorkerOutbox:
    """Durable SQLite WAL outbox for analytics events (one per process).

    Thread-safety: enqueue() is called from the worker main-loop thread; the
    publisher daemon thread started by start() is the only other accessor.
    All database access is serialized through one lock around a single
    connection (sqlite3 connections are not shareable across threads without
    check_same_thread=False, and check_same_thread=False alone would still
    race transactions).
    """

    def __init__(self, db_path, *, jitter_function=None):
        self._db_path = Path(db_path)
        self._jitter = jitter_function if jitter_function is not None else random.random
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._next_attempt_mono: dict[int, float] = {}
        self._last_marker_mono = 0.0
        # Explicit schema init at outbox open (D-103): never lazily from a
        # publisher-thread path (wave-1 "lazy migration" gotcha, KB
        # INFRASTRUCTURE.md gotcha #34). A failed open/init propagates so the
        # seam can fail closed instead of reporting durable acceptance.
        self._conn = sqlite3.connect(
            str(self._db_path), check_same_thread=False, timeout=30.0
        )
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=30000")
            # synchronous=FULL: fsync per commit so a reported acceptance
            # survives power loss (AC-001); the enqueue rate is low, so
            # correctness over throughput.
            self._conn.execute("PRAGMA synchronous=FULL")
            with self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS outbox_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        snapshot_bytes BLOB NOT NULL,
                        pending_since REAL NOT NULL,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        last_error TEXT,
                        send_errors INTEGER NOT NULL DEFAULT 0,
                        retries INTEGER NOT NULL DEFAULT 0,
                        accept_errors INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'pending'
                    )
                    """
                )
                self._conn.execute(
                    "CREATE INDEX IF NOT EXISTS outbox_events_status_id_idx "
                    "ON outbox_events(status, id)"
                )
                self._conn.execute(
                    "CREATE TABLE IF NOT EXISTS outbox_meta ("
                    "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
                )
                if self._meta_get("schema_version") is None:
                    self._meta_set("schema_version", _SCHEMA_VERSION)
                for counter in (
                    "outbox_send_errors_total",
                    "outbox_retries_total",
                    "outbox_accept_errors_total",
                ):
                    if self._meta_get(counter) is None:
                        self._meta_set(counter, "0")
            self._conn.commit()
        except BaseException:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            raise

    # ------------------------------------------------------------------
    # persistence surface
    # ------------------------------------------------------------------

    def enqueue(self, event_id, metadata_json, snapshot_path) -> bool:
        """Persist one accepted event durably; return True.

        The snapshot JPEG bytes are read from disk INSIDE the enqueue (the
        file-based snapshots rotate later, D-109) and the metadata JSON
        string is stored byte-verbatim. The snapshot file read precedes the
        INSERT; only the insert is transactional, and the seam fails closed
        either way: any failure (OSError on the read, sqlite3.Error on the
        insert) raises before acceptance is reported - the seam converts
        that to False so nothing is reported accepted that was not durably
        persisted (fail-closed, FR-003).
        """
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("outbox enqueue requires a non-empty event_id string")
        if not isinstance(metadata_json, str) or not metadata_json.strip():
            raise ValueError("outbox enqueue requires the metadata JSON string")
        snapshot_bytes = Path(snapshot_path).read_bytes()
        now_mono = time.monotonic()
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO outbox_events "
                    "(event_id, created_at, metadata, snapshot_bytes, pending_since,"
                    " attempts, send_errors, retries, accept_errors, status) "
                    "VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 'pending')",
                    (
                        event_id,
                        created_at,
                        metadata_json,
                        snapshot_bytes,
                        now_mono,
                    ),
                )
        self._wake.set()
        return True

    def pending_count(self) -> int:
        """Unconfirmed rows: pending plus retained 409 terminal rows."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM outbox_events"
                " WHERE status IN ('pending', 'terminal_error')"
            ).fetchone()
        return int(row[0]) if row else 0

    def snapshot(self) -> dict:
        """Heartbeat summary (FR-008): the six additive outbox metrics."""
        with self._lock:
            count, oldest_pending_since = self._conn.execute(
                "SELECT COUNT(*), MIN(pending_since) FROM outbox_events"
                " WHERE status IN ('pending', 'terminal_error')"
            ).fetchone()
            send_errors = self._meta_int("outbox_send_errors_total")
            retries = self._meta_int("outbox_retries_total")
            accept_errors = self._meta_int("outbox_accept_errors_total")
            last_confirmed_raw = self._meta_get("last_confirmed_epoch")
        oldest_age = None
        if count and oldest_pending_since is not None:
            oldest_age = max(0.0, time.monotonic() - float(oldest_pending_since))
        last_confirmed = None
        if last_confirmed_raw is not None:
            try:
                last_confirmed = float(last_confirmed_raw)
            except (TypeError, ValueError):
                last_confirmed = None
        return {
            "pending": int(count or 0),
            "oldest_unconfirmed_sec": oldest_age,
            "send_errors": send_errors,
            "retries": retries,
            "accept_errors": accept_errors,
            "last_confirmed_epoch": last_confirmed,
        }

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the single daemon publisher thread (idempotent)."""
        if self._thread is not None and self._thread.is_alive():
            return
        thread = threading.Thread(
            target=self._publish_loop,
            name="sea-speed-outbox-publisher",
            daemon=True,
        )
        self._thread = thread
        thread.start()

    def close(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5.0)
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass

    # ------------------------------------------------------------------
    # publisher internals (single daemon thread only)
    # ------------------------------------------------------------------

    def _publish_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._emit_marker_if_due()
                row = self._head_row()
                if row is None:
                    # idle: wake on enqueue or at marker cadence
                    self._wake.wait(timeout=_METRIC_INTERVAL_SEC)
                    self._wake.clear()
                    continue
                row_id, event_id, metadata_json, snapshot_bytes, attempts, retries = row
                due_at = self._next_attempt_mono.get(row_id)
                now_mono = time.monotonic()
                if due_at is not None and now_mono < due_at:
                    self._wait_until(due_at)
                    continue
                self._deliver(
                    row_id, event_id, metadata_json, snapshot_bytes, attempts, retries
                )
            except Exception as exc:
                # The publisher must never die: rows stay pending on disk.
                try:
                    print(f"outbox publisher error reason={type(exc).__name__}", flush=True)
                except Exception:
                    pass
                self._stop.wait(1.0)

    def _head_row(self):
        with self._lock:
            row = self._conn.execute(
                "SELECT id, event_id, metadata, snapshot_bytes, attempts, retries"
                " FROM outbox_events WHERE status = 'pending' ORDER BY id LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return row

    def _deliver(self, row_id, event_id, metadata_json, snapshot_bytes, attempts, retries):
        is_retry = attempts > 0
        action, detail = self._post(metadata_json, snapshot_bytes)
        new_attempts = attempts + 1
        new_retries = retries + (1 if is_retry else 0)
        content_sha = hashlib.sha256(
            metadata_json.encode("utf-8") + b"\x00" + bytes(snapshot_bytes)
        ).hexdigest()[:12]
        with self._lock:
            if action == "confirmed":
                with self._conn:
                    self._conn.execute(
                        "DELETE FROM outbox_events WHERE id = ?", (row_id,)
                    )
                    self._meta_set("last_confirmed_epoch", f"{time.time():.6f}")
                    if is_retry:
                        self._meta_increment("outbox_retries_total")
                self._next_attempt_mono.pop(row_id, None)
            elif action == "terminal":
                with self._conn:
                    self._conn.execute(
                        "UPDATE outbox_events SET attempts = ?, retries = ?,"
                        " accept_errors = accept_errors + 1, last_error = ?,"
                        " status = 'terminal_error' WHERE id = ?",
                        (new_attempts, new_retries, detail, row_id),
                    )
                    self._meta_increment("outbox_accept_errors_total")
                    if is_retry:
                        self._meta_increment("outbox_retries_total")
                self._next_attempt_mono.pop(row_id, None)
            else:  # send error -> bounded backoff, NO attempt-based discard
                delay = self._backoff_delay(new_attempts)
                with self._conn:
                    self._conn.execute(
                        "UPDATE outbox_events SET attempts = ?, send_errors = send_errors + 1,"
                        " retries = ?, last_error = ? WHERE id = ?",
                        (new_attempts, new_retries, detail, row_id),
                    )
                    self._meta_increment("outbox_send_errors_total")
                    if is_retry:
                        self._meta_increment("outbox_retries_total")
                self._next_attempt_mono[row_id] = time.monotonic() + delay
        if action == "confirmed":
            suffix = ""
            if isinstance(detail, dict):
                if detail.get("duplicate") is True:
                    suffix = " duplicate=true"
                elif detail.get("event", "missing") is None:
                    suffix = " person_filtered=true"
            print(f"POST event ok id={event_id} class={_meta_class(metadata_json)} conf={_meta_conf(metadata_json):.2f}{suffix}", flush=True)
        elif action == "terminal":
            print(
                f"outbox accept_error event_id={event_id} reason={detail}",
                flush=True,
            )
        else:
            next_delay = self._next_attempt_mono.get(row_id)
            delay_text = "0.0s" if next_delay is None else f"{max(0.0, next_delay - time.monotonic()):.1f}s"
            print(
                f"outbox send error event_id={event_id} attempt={new_attempts}"
                f" content={content_sha} delay={delay_text} reason={detail}",
                flush=True,
            )

    def _post(self, metadata_json, snapshot_bytes):
        """One HTTP delivery; returns (action, detail) per FR-007."""
        if requests is None:
            return "retry", "requests module unavailable"
        url = _event_url()
        token = os.environ.get("SEA_SPEED_API_TOKEN", "").strip()
        if not url or not token:
            return "retry", "event URL or token is not set"
        try:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                data={"metadata": metadata_json},
                files={"snapshot": ("event.jpg", snapshot_bytes, "image/jpeg")},
                timeout=10,
            )
        except Exception as exc:
            return "retry", f"{type(exc).__name__}: {exc}"[:_ERROR_TEXT_LIMIT]
        if response.status_code == 409:
            # Terminal accept-error: retained row, never retried (D-104).
            return "terminal", f"HTTP 409 {response.text[:200]}"
        if response.status_code != 200:
            return "retry", f"HTTP {response.status_code} {response.text[:200]}"
        try:
            body = response.json()
        except Exception:
            return "retry", "response body is not JSON"
        if not isinstance(body, dict) or body.get("ok") is not True:
            return "retry", f"unexpected response body {str(body)[:200]}"
        # 200 + ok:true covers FR-007 confirm / duplicate receipt hit and the
        # D-110 person-filter terminal success {"ok": true, "event": null}.
        return "confirmed", body

    def _backoff_delay(self, attempts: int) -> float:
        # Clamp the exponent BEFORE the power: an unclamped factor**attempts
        # overflows for extreme attempt counts even though the cap makes the
        # extra exponent irrelevant.
        raw = min(
            _BACKOFF_CAP_SEC,
            _BACKOFF_BASE_SEC
            * (_BACKOFF_FACTOR ** min(max(0, attempts - 1), _BACKOFF_EXPONENT_CAP)),
        )
        jittered = raw + self._jitter() * 0.25 * raw
        return min(_BACKOFF_CAP_SEC, max(0.0, jittered))

    def _wait_until(self, due_mono: float) -> None:
        # Sleep in slices bounded by the marker cadence so heartbeat metrics
        # stay fresh even during a 60s backoff wait.
        while not self._stop.is_set():
            now = time.monotonic()
            if now >= due_mono:
                return
            marker_due_in = _METRIC_INTERVAL_SEC - (now - self._last_marker_mono)
            self._stop.wait(timeout=max(0.05, min(due_mono - now, marker_due_in)))
            self._emit_marker_if_due()

    def _emit_marker_if_due(self) -> None:
        now = time.monotonic()
        if now - self._last_marker_mono < _METRIC_INTERVAL_SEC:
            return
        self._last_marker_mono = now
        try:
            summary = self.snapshot()
        except Exception:
            return
        oldest = summary["oldest_unconfirmed_sec"]
        last_confirmed = summary["last_confirmed_epoch"]
        print(
            "outbox pending={pending} oldest={oldest} send_errors={send_errors}"
            " retries={retries} accept_errors={accept_errors}"
            " last_confirmed={last_confirmed}".format(
                pending=summary["pending"],
                oldest="none" if oldest is None else f"{oldest:.1f}",
                send_errors=summary["send_errors"],
                retries=summary["retries"],
                accept_errors=summary["accept_errors"],
                last_confirmed=(
                    "none" if last_confirmed is None else f"{last_confirmed:.3f}"
                ),
            ),
            flush=True,
        )

    # ------------------------------------------------------------------
    # meta helpers (callers hold self._lock)
    # ------------------------------------------------------------------

    def _meta_get(self, key: str):
        row = self._conn.execute(
            "SELECT value FROM outbox_meta WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def _meta_set(self, key: str, value) -> None:
        self._conn.execute(
            "INSERT INTO outbox_meta (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    def _meta_int(self, key: str) -> int:
        try:
            return int(float(self._meta_get(key) or 0))
        except (TypeError, ValueError):
            return 0

    def _meta_increment(self, key: str) -> None:
        self._meta_set(key, self._meta_int(key) + 1)


def _event_url() -> str:
    """Mirror worker_transport.post_event URL derivation exactly (D-102)."""
    event_url = os.environ.get("SEA_SPEED_EVENT_API_URL", "").strip()
    if event_url:
        return event_url
    state_url = os.environ.get("SEA_SPEED_API_URL", "").strip()
    if state_url:
        return state_url.rsplit("/", 1)[0] + "/events"
    return ""


def _meta_class(metadata_json: str) -> str:
    try:
        payload = json.loads(metadata_json)
    except Exception:
        return "?"
    if isinstance(payload, dict):
        return str(payload.get("class_name") or "?")
    return "?"


def _meta_conf(metadata_json: str) -> float:
    try:
        payload = json.loads(metadata_json)
        if isinstance(payload, dict):
            return float(payload.get("confidence") or 0.0)
    except Exception:
        pass
    return 0.0
