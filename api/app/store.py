"""Transactional persistence primitives for the Sea Speed API (issue #394).

Two complementary layers:

1. Hardened JSON file IO for the rarely-edited operator config files
   (roi / speed-config / speed-lines / crossing-line) and the camera-preview
   state: every write takes a per-file advisory lock on a ``<name>.lock``
   sibling and lands through a uuid-unique temporary file plus
   ``os.replace`` (no fixed-sibling tmp race); reads are fail-loud — a
   missing file yields the caller's default, a corrupt or unreadable file
   raises so callers can surface HTTP 500 instead of silently degrading.
2. A small transactional SQLite store (WAL) for hot operational state —
   line-crossing records, the analytics event feed and the 1 Hz camera
   state. Every mutation is a single-statement or single-transaction write
   (no read-modify-write) and per-camera rows are bounded by a
   same-transaction DELETE cap.

RISK-005 retirement (contracted follow-up to the #394 dual-write window):
the trigger fired 2026-10-09 (first verified full VPS contour deploy
9e3b9ee8, issue #394 comment 6073231021) and the deadline — the next
release cycle — has arrived. The retirement act is executed in full: the
dual-write legacy-JSON mirrors are gone from the callers, the legacy-JSON
import path is removed, and the ``ingestion_log`` registry is dropped —
startup runs a one-time idempotent ``DROP TABLE IF EXISTS ingestion_log``
so existing databases from the dual-write era shed the retired table.
SQLite is the only hot-state authority. Legacy JSON files already on disk
are never deleted; they become inert history. Contracted rollback-semantics
change: after this act, rolling back to a pre-#394 release no longer sees
records accepted during the (now closed) dual-write window.

Standard library only.
"""

import fcntl
import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

__all__ = [
    "JSON_READ_ERRORS",
    "read_json_file",
    "write_json_file",
    "open_state_db",
    "initialize_state_db",
    "append_crossing",
    "read_crossings",
    "append_event",
    "read_events",
    "upsert_camera_state",
    "read_camera_state",
    # Issue #537 wave 1: durable road-event delivery receipts.
    "EVENT_RECEIPTS_RETENTION_DAYS",
    "EVENT_INGEST_LOCK",
    "EventDeliveryConflict",
    "atomic_write_bytes",
    "deliver_event",
    "event_content_fingerprint",
    "find_event_receipt",
    "hash_bytes",
    "prune_event_receipts",
    "safe_event_filename",
]

# OSError covers unreadable paths (permissions, directories, ...);
# ValueError covers json.JSONDecodeError and UnicodeDecodeError.
# read_json_file deliberately lets both escape instead of degrading to the
# caller's default.
JSON_READ_ERRORS = (OSError, ValueError)

_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS crossings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camera_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_crossings_camera ON crossings(camera_id, id)",
    """
    CREATE TABLE IF NOT EXISTS event_feed (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camera_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_event_feed_camera ON event_feed(camera_id, id)",
    """
    CREATE TABLE IF NOT EXISTS camera_state (
        camera_id TEXT PRIMARY KEY,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    # Issue #537 wave 1: durable delivery receipts keyed by the global
    # event_id. Receipts are deliberately NOT pruned with the feed (the feed
    # is capped per camera); only the 90-day retention sweep touches them.
    """
    CREATE TABLE IF NOT EXISTS event_receipts (
        event_id TEXT PRIMARY KEY,
        camera_id TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        snapshot_hash TEXT NOT NULL,
        response_event_json TEXT NOT NULL,
        completed_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_event_receipts_completed_at ON event_receipts(completed_at)",
)

_init_lock = threading.Lock()
_initialized: set = set()


def read_json_file(path: Path, default: Any) -> Any:
    """Read JSON from ``path``; a missing file yields ``default``, corruption raises."""
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, data: Any) -> None:
    """Atomically write ``data`` as JSON under a per-file advisory lock.

    The temporary file name carries a uuid so concurrent writers (or a
    deploy-side migration process) can never share the fixed ``.tmp``
    sibling that the previous implementation used.
    """
    path = Path(path)
    lock_path = path.with_name(f"{path.name}.lock")
    tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(lock_path, "a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp_path, path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize_state_db(db_path: Path) -> None:
    """Create the hot-state schema once per database file (idempotent)."""
    resolved = str(db_path)
    if resolved in _initialized:
        return
    with _init_lock:
        if resolved in _initialized:
            return
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(resolved, timeout=10)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            for statement in _SCHEMA_STATEMENTS:
                connection.execute(statement)
            # RISK-005 retirement: databases created during the dual-write
            # window still carry the ingestion_log registry. The schema no
            # longer creates it; this one-time idempotent drop sheds the
            # retired table from every existing database at boot (fresh
            # installs never have it). Dropping the table also removes its
            # index; retained crossings/event_feed/camera_state rows are
            # untouched.
            connection.execute("DROP TABLE IF EXISTS ingestion_log")
            # Issue #537 wave 1, additive-at-boot migration over legacy feed
            # rows: (1) nullable event_id column on the capped event feed,
            # (2) backfill from the stored payloads, (3) inventory of
            # duplicate historical ids and (4) the unique event_id index —
            # created only when the backfill proves the existing rows are
            # conflict-free. Conflicting historical rows are NEVER deleted or
            # rewritten to make the index succeed: they are recorded in
            # migration_inventory (and logged) and the index is deferred, so
            # the migration can never corrupt retained history. Every step is
            # idempotent and safe to re-run across restarts and version
            # rollbacks (downlevel code ignores the extra column and table).
            event_feed_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(event_feed)")
            }
            if "event_id" not in event_feed_columns:
                connection.execute("ALTER TABLE event_feed ADD COLUMN event_id TEXT")
            # Raw connection (no row_factory): rows are tuples — (id, payload_json).
            for row in connection.execute(
                "SELECT id, payload_json FROM event_feed WHERE event_id IS NULL"
            ).fetchall():
                try:
                    payload = json.loads(row[1])
                except ValueError:
                    continue  # corrupt legacy payload: keep the row, leave event_id NULL
                raw_event_id = payload.get("event_id") if isinstance(payload, dict) else None
                if raw_event_id in (None, ""):
                    continue
                connection.execute(
                    "UPDATE event_feed SET event_id = ? WHERE id = ?",
                    (str(raw_event_id), row[0]),
                )
            # Rows are (event_id, retained_rows) tuples on this raw connection.
            duplicate_rows = connection.execute(
                "SELECT event_id, COUNT(*) FROM event_feed "
                "WHERE event_id IS NOT NULL GROUP BY event_id HAVING COUNT(*) > 1"
            ).fetchall()
            if duplicate_rows:
                inventory = [
                    {"event_id": str(row[0]), "retained_rows": int(row[1])}
                    for row in duplicate_rows
                ]
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS migration_inventory ("
                    "key TEXT PRIMARY KEY, value_json TEXT NOT NULL, recorded_at TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO migration_inventory (key, value_json, recorded_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, "
                    "recorded_at=excluded.recorded_at",
                    (
                        "event_feed_duplicate_event_ids",
                        json.dumps(inventory, ensure_ascii=False, sort_keys=True),
                        _utc_now_iso(),
                    ),
                )
                print(
                    f"event-feed migration: retained {len(inventory)} duplicate historical "
                    "event_id(s) without deletion; unique event_id index deferred "
                    "(issue #537 wave 1)",
                    file=sys.stderr,
                )
            else:
                # Plain UNIQUE index (NULLs are distinct in SQLite, so every
                # legacy row without an event_id stays legal). A partial
                # index (WHERE event_id IS NOT NULL) cannot serve as the
                # conflict target of INSERT ... ON CONFLICT(event_id), so the
                # non-partial form is the one that provides both properties
                # the design mandates: non-NULL uniqueness AND
                # conflict-targeted DO NOTHING inserts.
                connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_event_feed_event_id ON event_feed(event_id)"
                )
            connection.commit()
        finally:
            connection.close()
        _initialized.add(resolved)


@contextmanager
def open_state_db(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Per-operation connection: commit on success, rollback and re-raise on error."""
    initialize_state_db(db_path)
    connection = sqlite3.connect(str(db_path), timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def _prune_camera_rows(connection: sqlite3.Connection, table: str, camera_id: str, limit: int) -> None:
    connection.execute(
        f"DELETE FROM {table} WHERE camera_id = ? AND id NOT IN "
        f"(SELECT id FROM {table} WHERE camera_id = ? ORDER BY id DESC LIMIT ?)",
        (camera_id, camera_id, max(0, int(limit))),
    )


def append_crossing(db_path: Path, camera_id: str, record: Dict[str, Any], limit: int = 5000) -> None:
    """Insert one crossing record and cap the camera to the newest ``limit`` rows."""
    payload_json = json.dumps(record, ensure_ascii=False, sort_keys=True)
    created_at = str(record.get("created_at") or _utc_now_iso())
    with open_state_db(db_path) as connection:
        connection.execute(
            "INSERT INTO crossings (camera_id, payload_json, created_at) VALUES (?, ?, ?)",
            (camera_id, payload_json, created_at),
        )
        _prune_camera_rows(connection, "crossings", camera_id, limit)


def read_crossings(db_path: Path, camera_id: str) -> List[Dict[str, Any]]:
    """All crossing records for a camera, newest first (legacy file semantics)."""
    with open_state_db(db_path) as connection:
        rows = connection.execute(
            "SELECT payload_json FROM crossings WHERE camera_id = ? ORDER BY id DESC",
            (camera_id,),
        ).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def append_event(db_path: Path, camera_id: str, event: Dict[str, Any], limit: int = 500) -> None:
    """Insert one event-feed record and cap the camera to the newest ``limit`` rows.

    Issue #537 wave 1: the nullable event_id column is populated from the
    payload when present, so direct appends participate in the feed's unique
    event_id index. This remains the legacy blind append — the receipt-aware
    delivery path is ``deliver_event``.
    """
    payload_json = json.dumps(event, ensure_ascii=False, sort_keys=True)
    created_at = str(event.get("created_at") or _utc_now_iso())
    raw_event_id = event.get("event_id")
    event_id = str(raw_event_id) if raw_event_id not in (None, "") else None
    with open_state_db(db_path) as connection:
        connection.execute(
            "INSERT INTO event_feed (camera_id, payload_json, created_at, event_id) VALUES (?, ?, ?, ?)",
            (camera_id, payload_json, created_at, event_id),
        )
        _prune_camera_rows(connection, "event_feed", camera_id, limit)


def read_events(db_path: Path, camera_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Event-feed records for a camera, newest first, optionally bounded."""
    query = "SELECT payload_json FROM event_feed WHERE camera_id = ? ORDER BY id DESC"
    parameters: List[Any] = [camera_id]
    if limit is not None:
        query += " LIMIT ?"
        parameters.append(max(0, int(limit)))
    with open_state_db(db_path) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


# ---------------------------------------------------------------------------
# Issue #537 wave 1: durable road-event delivery receipts.
#
# The event feed is capped per camera, so a unique feed index alone stops
# duplicates only while the original row survives. A receipt keyed by the
# global event_id records each completed delivery (camera, immutable content
# fingerprint, snapshot fingerprint, the stored success response and the
# completion timestamp) and outlives any feed pruning.
# ---------------------------------------------------------------------------

# Approved owner decision (issue #537, 2026-10-19): receipts are retained for
# 90 days, NOT pruned with the feed. Residual risk (documented in
# specs/537-wave1-event-delivery-receipts/spec.md): a retry arriving more
# than 90 days after the completed delivery finds no receipt and is treated
# as a new delivery; the feed's unique event_id index still prevents a
# duplicate row while the (500-per-camera capped) original row survives.
EVENT_RECEIPTS_RETENTION_DAYS = 90

# Serializes same-ID ingestion inside one API process (design §3 step 4);
# cross-process same-ID races are settled by the receipt check plus the
# event_feed unique index inside the deliver_event transaction.
EVENT_INGEST_LOCK = threading.Lock()

_SAFE_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


class EventDeliveryConflict(RuntimeError):
    """Same event_id delivered with different immutable content or camera."""


def hash_bytes(data: bytes) -> str:
    """SHA-256 hex digest of raw bytes (snapshot fingerprint primitive)."""
    return hashlib.sha256(data).hexdigest()


def event_content_fingerprint(event: Dict[str, Any]) -> str:
    """Immutable content fingerprint of a normalized event payload.

    Canonical JSON (sorted keys, no ambient whitespace) so a verbatim retry
    fingerprints identically while any differing business field — including
    camera_id, snapshot_url and created_at, which are part of the normalized
    event — produces a different fingerprint and a 409 conflict. Retry-only
    transport metadata never enters the event payload (contract
    scripts/quality/common.py RETRY_ONLY_FIELDS stays external to it).
    """
    canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def safe_event_filename(camera_id: str, event_id: str) -> str:
    """Deterministic, traversal-safe event snapshot filename (issue #537).

    Client-controlled event_id values are never interpolated into a media
    path directly: ids matching the safe shape are used verbatim (so retries
    rebuild the same snapshot_url), anything else falls back to a sha256
    digest of the id — still deterministic, never escaping the media
    directory and never colliding with the safe shape.
    """
    safe_id = event_id if _SAFE_EVENT_ID_RE.fullmatch(str(event_id)) else None
    if safe_id is None:
        safe_id = "ev-" + hashlib.sha256(str(event_id).encode("utf-8")).hexdigest()[:32]
    return f"{camera_id}-{safe_id}.jpg"


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Crash-safe file publish: unique tmp, fsync, os.replace, dir fsync.

    A failure at any stage leaves any previous file content untouched and
    removes the temporary file, so no partially written snapshot is ever
    observable and the caller can retry cleanly.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp_path, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    directory_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    except OSError:
        # Best-effort on filesystems without directory fsync; the file data
        # itself is already fsynced and the rename has happened.
        pass
    finally:
        os.close(directory_fd)


def find_event_receipt(db_path: Path, event_id: str) -> Optional[Dict[str, Any]]:
    """The stored delivery receipt for ``event_id``, or None when unseen."""
    with open_state_db(db_path) as connection:
        row = connection.execute(
            "SELECT event_id, camera_id, content_hash, snapshot_hash, response_event_json, completed_at "
            "FROM event_receipts WHERE event_id = ?",
            (str(event_id),),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def deliver_event(
    db_path: Path,
    camera_id: str,
    event: Dict[str, Any],
    content_hash: str,
    snapshot_hash: str,
    limit: int = 500,
) -> tuple[str, Optional[Dict[str, Any]]]:
    """Insert the feed row and the completion receipt in ONE transaction.

    Returns ``("stored", None)`` when this call inserted the feed row, or
    ``("duplicate", stored_event)`` when an identical delivery already
    completed (via the receipt or a retained feed row) — the stored original
    event is returned for the duplicate success response. Raises
    ``EventDeliveryConflict`` for the same event_id with different immutable
    content or a different camera; the conflict aborts the transaction so no
    partial state is committed.

    The feed insertion is conflict-targeted ``INSERT ... ON CONFLICT(event_id)
    DO NOTHING`` — never an upsert: an existing row (e.g. a legacy row from
    before the upgrade) is never reset or overwritten. On databases where the
    unique index could not be created (unresolvable duplicate history), the
    insert degrades to the legacy blind append after an explicit stored-row
    check, and the receipt still gates all future duplicates.
    """
    payload_json = json.dumps(event, ensure_ascii=False, sort_keys=True)
    created_at = str(event.get("created_at") or _utc_now_iso())
    event_id = str(event.get("event_id") or "")
    with open_state_db(db_path) as connection:
        receipt_row = connection.execute(
            "SELECT camera_id, content_hash, snapshot_hash, response_event_json "
            "FROM event_receipts WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if receipt_row is not None:
            if (
                receipt_row["camera_id"] != camera_id
                or receipt_row["content_hash"] != content_hash
                or receipt_row["snapshot_hash"] != snapshot_hash
            ):
                raise EventDeliveryConflict(
                    "event_id already delivered with different content or camera"
                )
            return "duplicate", json.loads(receipt_row["response_event_json"])
        if not event_id:
            # No explicit identity: legacy blind append (nothing to dedupe
            # on — the handler mints event_ids before reaching this path).
            connection.execute(
                "INSERT INTO event_feed (camera_id, payload_json, created_at, event_id) "
                "VALUES (?, ?, ?, NULL)",
                (camera_id, payload_json, created_at),
            )
            _prune_camera_rows(connection, "event_feed", camera_id, limit)
            return "stored", None
        unique_index_present = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'idx_event_feed_event_id'"
        ).fetchone() is not None
        if unique_index_present:
            cursor = connection.execute(
                "INSERT INTO event_feed (camera_id, payload_json, created_at, event_id) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(event_id) DO NOTHING",
                (camera_id, payload_json, created_at, event_id),
            )
            feed_inserted = cursor.rowcount > 0
        else:
            # Degraded legacy database (duplicate historical event_ids kept
            # the unique index from being created): no conflict target
            # exists, so compare against the retained rows explicitly and
            # use the legacy blind append only for genuinely new content.
            stored_row = connection.execute(
                "SELECT camera_id, payload_json FROM event_feed WHERE event_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (event_id,),
            ).fetchone()
            if stored_row is not None:
                stored_event = json.loads(stored_row["payload_json"])
                if (
                    stored_row["camera_id"] == camera_id
                    and json.dumps(stored_event, ensure_ascii=False, sort_keys=True) == payload_json
                ):
                    connection.execute(
                        "INSERT OR IGNORE INTO event_receipts "
                        "(event_id, camera_id, content_hash, snapshot_hash, response_event_json, completed_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (event_id, camera_id, content_hash, snapshot_hash, stored_row["payload_json"], _utc_now_iso()),
                    )
                    return "duplicate", stored_event
                raise EventDeliveryConflict(
                    "event_id already delivered with different content or camera"
                )
            connection.execute(
                "INSERT INTO event_feed (camera_id, payload_json, created_at, event_id) "
                "VALUES (?, ?, ?, ?)",
                (camera_id, payload_json, created_at, event_id),
            )
            feed_inserted = True
        if feed_inserted:
            _prune_camera_rows(connection, "event_feed", camera_id, limit)
        else:
            stored_row = connection.execute(
                "SELECT camera_id, payload_json FROM event_feed WHERE event_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (event_id,),
            ).fetchone()
            stored_event = json.loads(stored_row["payload_json"])
            if (
                stored_row["camera_id"] != camera_id
                or json.dumps(stored_event, ensure_ascii=False, sort_keys=True) != payload_json
            ):
                raise EventDeliveryConflict(
                    "event_id already delivered with different content or camera"
                )
            payload_json = stored_row["payload_json"]
        connection.execute(
            "INSERT OR IGNORE INTO event_receipts "
            "(event_id, camera_id, content_hash, snapshot_hash, response_event_json, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, camera_id, content_hash, snapshot_hash, payload_json, _utc_now_iso()),
        )
        if feed_inserted:
            return "stored", None
        return "duplicate", json.loads(payload_json)


def prune_event_receipts(
    db_path: Path,
    now: Optional[float] = None,
    retention_days: int = EVENT_RECEIPTS_RETENTION_DAYS,
) -> int:
    """Delete only receipts older than the retention window (default 90 days).

    The event feed and crossings are untouched: receipts are never pruned
    with the feed. ISO-8601 UTC ``completed_at`` strings compare
    lexicographically, so the cutoff is a plain string comparison.
    """
    moment = datetime.now(timezone.utc) if now is None else datetime.fromtimestamp(float(now), timezone.utc)
    cutoff = (moment - timedelta(days=max(0, int(retention_days)))).isoformat()
    with open_state_db(db_path) as connection:
        cursor = connection.execute(
            "DELETE FROM event_receipts WHERE completed_at < ?", (cutoff,)
        )
        return int(cursor.rowcount)


def upsert_camera_state(db_path: Path, camera_id: str, payload: Dict[str, Any]) -> None:
    """Single-statement transactional upsert of the 1 Hz camera state."""
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    updated_at = str(payload.get("updated_at") or _utc_now_iso())
    with open_state_db(db_path) as connection:
        connection.execute(
            """
            INSERT INTO camera_state (camera_id, payload_json, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(camera_id) DO UPDATE SET
                payload_json=excluded.payload_json, updated_at=excluded.updated_at
            """,
            (camera_id, payload_json, updated_at),
        )


def read_camera_state(db_path: Path, camera_id: str) -> Optional[Dict[str, Any]]:
    """Current state payload for a camera, or None when absent."""
    with open_state_db(db_path) as connection:
        row = connection.execute(
            "SELECT payload_json FROM camera_state WHERE camera_id = ?", (camera_id,)
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["payload_json"])
