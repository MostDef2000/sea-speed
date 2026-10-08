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
   DELETE cap, and every ingestion — live append or legacy import — registers
   the record's canonical payload hash in a durable ``ingestion_log`` table
   inside the same transaction. The legacy-JSON migration is therefore an
   idempotent merge governed by ingestion history, not by event time: a
   legacy record is skipped when its canonical payload (the exact stored
   ``payload_json`` bytes) is already retained on the camera, or when its
   hash is already registered (it was ingested before and has since been
   pruned) — so records the previous release appended during a rollback
   window are picked up by the next boot, repeated boots are no-ops, and a
   stale mirror can never resurrect pruned history: equal timestamps,
   missing timestamps and lagged mirrors are all handled uniformly by the
   registry. Camera-state imports take the legacy row only when it is
   strictly newer than the stored one. Import fails closed on corrupt input
   and never deletes the legacy files (the rollback window keeps reading
   them).

Standard library only.
"""

import fcntl
import hashlib
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
    "camera_has_rows",
    "import_legacy_records",
    "import_legacy_camera_state",
]

# OSError covers unreadable paths (permissions, directories, ...);
# ValueError covers json.JSONDecodeError and UnicodeDecodeError.
# read_json_file deliberately lets both escape instead of degrading to the
# caller's default.
JSON_READ_ERRORS = (OSError, ValueError)

_TABLE_BY_KIND = {"crossings": "crossings", "events": "event_feed", "state": "camera_state"}

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
    CREATE TABLE IF NOT EXISTS ingestion_log (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        camera_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        payload_hash TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ingestion_log_keys ON ingestion_log(camera_id, kind, payload_hash)",
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


def _register_ingested(
    connection: sqlite3.Connection,
    camera_id: str,
    kind: str,
    records: List[Any],
) -> None:
    """Record ingested payloads in ``ingestion_log`` (pure append, never pruned).

    Every ingestion path (``append_crossing``/``append_event`` live
    appends, ``import_legacy_records`` imports) calls this inside its own
    transaction, so a payload hash is durable exactly when its record is.
    The hash covers the record's canonical payload bytes —
    ``json.dumps(record, ensure_ascii=False, sort_keys=True)`` — the exact
    bytes stored in ``payload_json`` by every writer.

    The log is NEVER pruned: identities live for the entire dual-write /
    rollback compatibility window of this release. That completeness is
    the anti-resurrection proof and is why it needs no timestamp
    comparison and no bounded window — a stale legacy mirror has bounded
    SIZE but unbounded AGE (it can stay arbitrarily old while mirror
    writes keep failing), so any window shorter than the window itself
    would expire identities and let that file resurrect pruned records
    with fresh ids, evicting retained history. Here, any legacy file that
    is still eligible for import can only contain records ingested before
    the dual-write window ends, so registry membership is a complete
    anti-resurrection proof for this release's lifetime: no pruning means
    no expiration. Rollback-period records the old release wrote while
    the new store was authoritative are unregistered by definition and
    still merge. Disk bound: ≈120 bytes per ingested record (hex sha256 +
    row overhead); at realistic rates growth stays well under 10 MB/day,
    and pathological ingestion bursts are accepted and documented in
    RISK-005 (plan.md). Retirement — ``DROP TABLE ingestion_log``, stop
    dual-write and drop the import path — is the recorded follow-up
    release work.
    """
    for record in records:
        if not isinstance(record, dict):
            continue
        payload_json = json.dumps(record, ensure_ascii=False, sort_keys=True)
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        connection.execute(
            "INSERT INTO ingestion_log (camera_id, kind, payload_hash) VALUES (?, ?, ?)",
            (camera_id, kind, payload_hash),
        )


def append_crossing(db_path: Path, camera_id: str, record: Dict[str, Any], limit: int = 5000) -> None:
    """Insert one crossing record and cap the camera to the newest ``limit`` rows.

    The payload hash is registered in ``ingestion_log`` inside the same
    transaction, so the anti-resurrection registry is durable exactly when
    the record is (cheap: one INSERT — the log is never pruned during the
    dual-write window).
    """
    payload_json = json.dumps(record, ensure_ascii=False, sort_keys=True)
    created_at = str(record.get("created_at") or _utc_now_iso())
    with open_state_db(db_path) as connection:
        connection.execute(
            "INSERT INTO crossings (camera_id, payload_json, created_at) VALUES (?, ?, ?)",
            (camera_id, payload_json, created_at),
        )
        _register_ingested(connection, camera_id, "crossings", [record])
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

    The payload hash is registered in ``ingestion_log`` inside the same
    transaction (see :func:`_register_ingested`).
    """
    payload_json = json.dumps(event, ensure_ascii=False, sort_keys=True)
    created_at = str(event.get("created_at") or _utc_now_iso())
    with open_state_db(db_path) as connection:
        connection.execute(
            "INSERT INTO event_feed (camera_id, payload_json, created_at) VALUES (?, ?, ?)",
            (camera_id, payload_json, created_at),
        )
        _register_ingested(connection, camera_id, "events", [event])
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


def _parse_iso_or_none(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_newer(candidate: Any, incumbent: Any) -> bool:
    """True when the ``candidate`` ISO timestamp is strictly newer.

    Both sides must parse as ISO timestamps, compared as timezone-aware
    datetimes (so mixed UTC-offset spellings order by the actual instant).
    If either side is missing or unparseable the candidate is NOT newer: a
    timestamp that cannot be dated must never displace stored state — only
    a genuinely absent stored row may be seeded by an undated payload
    (the caller owns that empty-row case).
    """
    left = _parse_iso_or_none(candidate)
    right = _parse_iso_or_none(incumbent)
    if left is None or right is None:
        return False
    return left > right


def camera_has_rows(db_path: Path, kind: str, camera_id: str) -> bool:
    """True when the per-camera hot-state target already holds committed rows.

    The startup migration consults this to gate legacy reads on necessity:
    an empty target means this boot performs the authoritative initial
    migration (fail closed on unreadable legacy JSON); a populated target
    means the migration already completed and the legacy file is only a
    non-authoritative mirror (best-effort reads).
    """
    table = _TABLE_BY_KIND.get(kind)
    if table is None:
        raise ValueError(f"unknown legacy store kind: {kind}")
    with open_state_db(db_path) as connection:
        row = connection.execute(
            f"SELECT 1 FROM {table} WHERE camera_id = ? LIMIT 1", (camera_id,)
        ).fetchone()
    return row is not None


def import_legacy_records(db_path: Path, kind: str, camera_id: str, records: List[Any], limit: int) -> int:
    """Ingestion-history-gated idempotent merge of legacy newest-first JSON records.

    Unlike an empty-table-only import this merge tolerates a populated
    target. Two guards keep the merge lifecycle-safe, and neither consults
    event timestamps (event time is not ingestion order):

    * Dedupe by retained payload equality — the canonical payload strings
      (``json.dumps(record, ensure_ascii=False, sort_keys=True)``, the
      exact bytes stored in ``payload_json``) of the camera's current rows
      are loaded in one query, and a legacy record whose canonical payload
      is already present is skipped (live appends carry no dedupe key;
      identical live submissions stay distinct as always).
    * Anti-resurrection by ingestion history — every ingestion (live
      append and import alike) registers the record's canonical payload
      hash in ``ingestion_log`` inside the same transaction, and a legacy
      record whose hash is already registered was ingested before (its row
      may since have been pruned by the cap) and is skipped. This is a
      durable ingestion/pruning identity, not a timestamp comparison:
      pruned records with timestamps EQUAL to the retained floor, undated
      or unparseable records are handled uniformly, and repeated boots
      cannot churn. Only genuinely never-ingested records — e.g. a
      rollback-period record with an old event timestamp — merge.

    Only merged records are registered, so repeated boots over an
    unchanged mirror are complete no-ops (no table writes, no registry
    writes). Legacy lists are newest-first, so records are inserted
    oldest-first to keep the id order identical to the legacy ordering
    semantics; the per-camera cap is then applied inside the same
    transaction.
    """
    table = _TABLE_BY_KIND.get(kind)
    if table is None:
        raise ValueError(f"unknown legacy store kind: {kind}")
    imported = 0
    merged: List[Dict[str, Any]] = []
    with open_state_db(db_path) as connection:
        rows = connection.execute(
            f"SELECT payload_json FROM {table} WHERE camera_id = ?", (camera_id,)
        ).fetchall()
        stored_payloads = {row["payload_json"] for row in rows}
        registered = {
            row["payload_hash"]
            for row in connection.execute(
                "SELECT payload_hash FROM ingestion_log WHERE camera_id = ? AND kind = ?",
                (camera_id, kind),
            ).fetchall()
        }
        for record in reversed(records):
            if not isinstance(record, dict):
                continue
            payload_json = json.dumps(record, ensure_ascii=False, sort_keys=True)
            payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            if payload_json in stored_payloads or payload_hash in registered:
                continue
            created_at = str(record.get("created_at") or _utc_now_iso())
            connection.execute(
                f"INSERT INTO {table} (camera_id, payload_json, created_at) VALUES (?, ?, ?)",
                (camera_id, payload_json, created_at),
            )
            stored_payloads.add(payload_json)
            merged.append(record)
            imported += 1
        _register_ingested(connection, camera_id, kind, merged)
        _prune_camera_rows(connection, table, camera_id, limit)
        return imported


def import_legacy_camera_state(db_path: Path, camera_id: str, payload: Dict[str, Any]) -> bool:
    """Seed camera_state from legacy JSON; the legacy state wins only when NEWER.

    During the rollback window the previous release keeps writing the legacy
    JSON, so a re-upgrade must not clobber fresher stored state with an older
    mirror — and conversely a fresher legacy row (written after the rollback)
    must win over the stale stored projection. A legacy payload without a
    usable ``updated_at`` is only imported into an empty row: it cannot be
    dated, so it never displaces a stored row.
    """
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    legacy_updated_at = payload.get("updated_at")
    with open_state_db(db_path) as connection:
        row = connection.execute(
            "SELECT updated_at FROM camera_state WHERE camera_id = ?", (camera_id,)
        ).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO camera_state (camera_id, payload_json, updated_at) VALUES (?, ?, ?)",
                (camera_id, payload_json, str(legacy_updated_at or _utc_now_iso())),
            )
            return True
        if legacy_updated_at is None or not _is_newer(legacy_updated_at, row["updated_at"]):
            return False
        connection.execute(
            "UPDATE camera_state SET payload_json = ?, updated_at = ? WHERE camera_id = ?",
            (payload_json, str(legacy_updated_at), camera_id),
        )
        return True
