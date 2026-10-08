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
   (no read-modify-write), per-camera rows are bounded by a same-transaction
   DELETE cap, and an idempotent legacy-JSON migration imports existing
   records into empty tables, failing closed on corrupt input and never
   deleting the legacy files (the rollback window keeps reading them).

Standard library only.
"""

import fcntl
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
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
    "import_legacy_records",
    "import_legacy_camera_state",
]

# OSError covers unreadable paths (permissions, directories, ...);
# ValueError covers json.JSONDecodeError and UnicodeDecodeError.
# read_json_file deliberately lets both escape instead of degrading to the
# caller's default.
JSON_READ_ERRORS = (OSError, ValueError)

_TABLE_BY_KIND = {"crossings": "crossings", "events": "event_feed"}

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
    """Insert one event-feed record and cap the camera to the newest ``limit`` rows."""
    payload_json = json.dumps(event, ensure_ascii=False, sort_keys=True)
    created_at = str(event.get("created_at") or _utc_now_iso())
    with open_state_db(db_path) as connection:
        connection.execute(
            "INSERT INTO event_feed (camera_id, payload_json, created_at) VALUES (?, ?, ?)",
            (camera_id, payload_json, created_at),
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


def import_legacy_records(db_path: Path, kind: str, camera_id: str, records: List[Any], limit: int) -> int:
    """Import legacy newest-first JSON records into an empty per-camera table.

    Idempotent: when the camera already has rows the import is a no-op.
    Legacy lists are newest-first, so records are inserted oldest-first to
    keep the id order identical to the legacy ordering semantics.
    """
    table = _TABLE_BY_KIND.get(kind)
    if table is None:
        raise ValueError(f"unknown legacy store kind: {kind}")
    with open_state_db(db_path) as connection:
        existing = connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE camera_id = ?", (camera_id,)
        ).fetchone()[0]
        if existing:
            return 0
        imported = 0
        for record in reversed(records):
            if not isinstance(record, dict):
                continue
            payload_json = json.dumps(record, ensure_ascii=False, sort_keys=True)
            created_at = str(record.get("created_at") or _utc_now_iso())
            connection.execute(
                f"INSERT INTO {table} (camera_id, payload_json, created_at) VALUES (?, ?, ?)",
                (camera_id, payload_json, created_at),
            )
            imported += 1
        _prune_camera_rows(connection, table, camera_id, limit)
        return imported


def import_legacy_camera_state(db_path: Path, camera_id: str, payload: Dict[str, Any]) -> bool:
    """Seed camera_state from legacy JSON; never overwrites an existing row."""
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    updated_at = str(payload.get("updated_at") or _utc_now_iso())
    with open_state_db(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO camera_state (camera_id, payload_json, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(camera_id) DO NOTHING
            """,
            (camera_id, payload_json, updated_at),
        )
        return bool(cursor.rowcount)
