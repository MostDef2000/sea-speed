"""Objects registry DB layer for the Sea Speed API (issue #396, wave 2).

Functions extracted verbatim from ``api/app/main.py``: the objects SQLite
store (``open_objects_db``), retention/pruning helpers, the event
persistence layer (``persist_object_event`` / ``import_existing_events``),
the row/query helpers (``object_row_to_dict`` / ``build_objects_where``)
and the record mutation primitives (``patch_object_record`` /
``delete_object_record``), plus the shared numeric coercion helpers
``optional_float`` / ``optional_int`` their bodies resolve at call time.

Single canonical import identity: constants come from ``config``, ``now_iso``
from ``identity`` and ``read_json_file`` from ``store`` through the same
dual idiom ``main.py`` uses for its store seam (relative import in package
context; sys.path-anchored absolute import for direct-file loads), so
``main`` and this module always share one instance of each dependency per
import mode. ``main.py`` imports this module normally at module level and
re-exports the public names, keeping the historical import surface intact.
"""

import hashlib
import json
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

try:  # package context (api.app.objects_registry) and direct-file load both supported
    from . import config  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from .config import (
        EVENTS_FILE,
        OBJECT_STATUSES,
        OBJECTS_DB_FILE,
        OBJECTS_RETENTION_LIMIT,
    )
    from . import identity  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from .identity import now_iso
    from . import store  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from .store import read_json_file
except ImportError:  # direct uvicorn app-dir / spec_from_file_location execution
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from config import (
        EVENTS_FILE,
        OBJECT_STATUSES,
        OBJECTS_DB_FILE,
        OBJECTS_RETENTION_LIMIT,
    )
    import identity  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from identity import now_iso
    import store  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from store import read_json_file

__all__ = [
    "open_objects_db",
    "prune_objects_registry",
    "initialize_objects_db",
    "optional_float",
    "optional_int",
    "stable_object_id",
    "prune_snapshotless_objects",
    "persist_object_event",
    "import_existing_events",
    "object_row_to_dict",
    "build_objects_where",
    "patch_object_record",
    "delete_object_record",
]

@contextmanager
def open_objects_db():
    connection = sqlite3.connect(str(OBJECTS_DB_FILE), timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def prune_objects_registry(connection: sqlite3.Connection) -> List[str]:
    retention = max(0, int(OBJECTS_RETENTION_LIMIT))
    eviction_subquery = """
        SELECT object_id FROM (
            SELECT object_id, ROW_NUMBER() OVER (
                PARTITION BY domain
                ORDER BY detected_at DESC, object_id DESC
            ) AS rn
            FROM objects
        )
        WHERE rn > ?
    """
    evicted = connection.execute(
        f"SELECT object_id, snapshot_url FROM objects WHERE object_id IN ({eviction_subquery})",
        (retention,),
    ).fetchall()
    if not evicted:
        return []
    connection.execute(
        f"DELETE FROM objects WHERE object_id IN ({eviction_subquery})",
        (retention,),
    )
    return [str(row["snapshot_url"]) for row in evicted if row["snapshot_url"]]


def initialize_objects_db() -> None:
    with open_objects_db() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS objects (
                object_id TEXT PRIMARY KEY,
                camera_id TEXT NOT NULL,
                track_id INTEGER,
                detected_at TEXT NOT NULL,
                class_name TEXT,
                analytics_profile TEXT,
                domain TEXT,
                object_type TEXT,
                model_class TEXT,
                confidence REAL,
                speed_kmh REAL,
                snapshot_url TEXT,
                comment TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new', 'reviewed', 'ignored')),
                original_event_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            )
            """
        )
        existing = {row[1] for row in connection.execute("PRAGMA table_info(objects)")}
        for name in ("analytics_profile", "domain", "object_type", "model_class"):
            if name not in existing:
                connection.execute(f"ALTER TABLE objects ADD COLUMN {name} TEXT")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_detected_at ON objects(detected_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_class_name ON objects(class_name)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_speed_kmh ON objects(speed_kmh)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_status ON objects(status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_deleted_at ON objects(deleted_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_camera_id ON objects(camera_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_domain ON objects(domain)")
        prune_objects_registry(connection)
        try:
            prune_snapshotless_objects(connection)
        except Exception:
            pass


def optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def stable_object_id(event: Dict[str, Any]) -> str:
    explicit_id = event.get("event_id") or event.get("object_id")
    if explicit_id not in (None, ""):
        return str(explicit_id)
    canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return f"legacy-{digest}"


def prune_snapshotless_objects(connection: sqlite3.Connection) -> int:
    now = now_iso()
    cursor = connection.execute(
        "UPDATE objects SET deleted_at = ?, updated_at = ? WHERE deleted_at IS NULL AND (snapshot_url IS NULL OR TRIM(snapshot_url) = '')",
        (now, now),
    )
    return int(cursor.rowcount)


def persist_object_event(event: Dict[str, Any]) -> bool:
    snapshot_url = event.get("snapshot_url")
    if not snapshot_url or not str(snapshot_url).strip():
        return False
    if not str(snapshot_url).strip().startswith("/sea-speed/media/"):
        return False
    object_id = stable_object_id(event)
    detected_at = str(event.get("created_at") or event.get("detected_at") or now_iso())
    created_at = str(event.get("created_at") or now_iso())
    camera_id = str(event.get("camera_id") or "cam1")
    profile = event.get("analytics_profile")
    domain = event.get("domain")
    if camera_id == "cam1":
        profile = profile or "water-v1"
        domain = domain or "water"
    elif camera_id == "road1":
        profile = profile or "road-v1"
        domain = domain or "road"
    object_type = event.get("object_type") or event.get("class_name") or event.get("class") or "object"
    model_class = event.get("model_class") or event.get("class_name") or event.get("class") or "object"
    original_event_json = json.dumps(event, ensure_ascii=False, sort_keys=True)
    with open_objects_db() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO objects (
                object_id, camera_id, track_id, detected_at, class_name,
                analytics_profile, domain, object_type, model_class,
                confidence, speed_kmh, snapshot_url, comment, status,
                original_event_json, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'new', ?, ?, ?, NULL)
            """,
            (
                object_id,
                camera_id,
                optional_int(event.get("track_id")),
                detected_at,
                str(event.get("class_name") or event.get("class") or object_type),
                profile,
                domain,
                str(object_type),
                str(model_class),
                optional_float(event.get("confidence")),
                optional_float(event.get("speed_kmh")),
                event.get("snapshot_url"),
                original_event_json,
                created_at,
                now_iso(),
            ),
        )
        inserted = cursor.rowcount > 0
        if inserted:
            prune_objects_registry(connection)
        return inserted


def import_existing_events() -> int:
    events = read_json_file(EVENTS_FILE, [])
    if not isinstance(events, list):
        return 0
    imported = 0
    for event in events:
        if isinstance(event, dict) and persist_object_event(event):
            imported += 1
    return imported


def object_row_to_dict(row: sqlite3.Row, include_original: bool = False) -> Dict[str, Any]:
    data = dict(row)
    raw = data.pop("original_event_json", "{}")
    if include_original:
        try:
            data["original_event"] = json.loads(raw)
        except Exception:
            data["original_event"] = {}
    return data


def build_objects_where(
    date_from: Optional[str],
    date_to: Optional[str],
    class_name: Optional[str],
    status: Optional[str],
    speed_min: Optional[float],
    speed_max: Optional[float],
    search: Optional[str],
    include_deleted: bool,
    camera_id: Optional[str] = "cam1",
    domain: Optional[str] = None,
    analytics_profile: Optional[str] = None,
    object_type: Optional[str] = None,
) -> tuple[str, List[Any]]:
    clauses: List[str] = []
    values: List[Any] = []
    if camera_id:
        clauses.append("camera_id = ?")
        values.append(camera_id)
    if domain:
        clauses.append("domain = ?")
        values.append(domain)
    if analytics_profile:
        clauses.append("analytics_profile = ?")
        values.append(analytics_profile)
    if object_type:
        clauses.append("object_type = ?")
        values.append(object_type)
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if date_from:
        clauses.append("detected_at >= ?")
        values.append(date_from)
    if date_to:
        clauses.append("detected_at <= ?")
        values.append(date_to)
    if class_name:
        clauses.append("class_name = ?")
        values.append(class_name.strip())
    if status:
        if status not in OBJECT_STATUSES:
            raise HTTPException(status_code=400, detail="status must be new, reviewed or ignored")
        clauses.append("status = ?")
        values.append(status)
    if speed_min is not None:
        clauses.append("speed_kmh >= ?")
        values.append(speed_min)
    if speed_max is not None:
        clauses.append("speed_kmh <= ?")
        values.append(speed_max)
    if search:
        term = f"%{search.strip()}%"
        clauses.append("(object_id LIKE ? OR class_name LIKE ? OR comment LIKE ?)")
        values.extend([term, term, term])
    return " AND ".join(clauses) if clauses else "1=1", values


def patch_object_record(object_id: str, payload: Dict[str, Any], camera_id: Optional[str] = None) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    if "class_name" in payload:
        class_name = str(payload.get("class_name") or "").strip()
        if not class_name or len(class_name) > 80:
            raise HTTPException(status_code=400, detail="class_name must contain 1 to 80 characters")
        updates["class_name"] = class_name
    if "speed_kmh" in payload:
        value = payload.get("speed_kmh")
        if value in (None, ""):
            updates["speed_kmh"] = None
        else:
            try:
                speed_kmh = float(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="speed_kmh must be a number or null")
            if speed_kmh < 0:
                raise HTTPException(status_code=400, detail="speed_kmh must be >= 0")
            updates["speed_kmh"] = speed_kmh
    if "comment" in payload:
        comment = str(payload.get("comment") or "").strip()
        if len(comment) > 2000:
            raise HTTPException(status_code=400, detail="comment must contain at most 2000 characters")
        updates["comment"] = comment
    if "status" in payload:
        object_status = str(payload.get("status") or "")
        if object_status not in OBJECT_STATUSES:
            raise HTTPException(status_code=400, detail="status must be new, reviewed or ignored")
        updates["status"] = object_status
    if not updates:
        raise HTTPException(status_code=400, detail="No editable fields supplied")
    updates["updated_at"] = now_iso()
    set_sql = ", ".join(f"{name} = ?" for name in updates)
    where = "object_id = ? AND deleted_at IS NULL"
    values: List[Any] = [*updates.values(), object_id]
    if camera_id:
        where += " AND camera_id = ?"
        values.append(camera_id)
    with open_objects_db() as connection:
        cursor = connection.execute(f"UPDATE objects SET {set_sql} WHERE {where}", values)
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Object not found")
        row = connection.execute("SELECT * FROM objects WHERE object_id = ?", (object_id,)).fetchone()
    return {"ok": True, "object": object_row_to_dict(row, include_original=True)}


def delete_object_record(object_id: str, camera_id: Optional[str] = None) -> Dict[str, Any]:
    deleted_at = now_iso()
    where = "object_id = ? AND deleted_at IS NULL"
    values: List[Any] = [deleted_at, deleted_at, object_id]
    if camera_id:
        where += " AND camera_id = ?"
        values.append(camera_id)
    with open_objects_db() as connection:
        cursor = connection.execute(f"UPDATE objects SET deleted_at = ?, updated_at = ? WHERE {where}", values)
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Object not found")
    return {"ok": True, "object_id": object_id, "deleted_at": deleted_at}
