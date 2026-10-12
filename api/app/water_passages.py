"""Water passages SQLite store for the Sea Speed API (issue #396, wave 3).

Functions extracted verbatim from ``api/app/main.py``: the water-passages
connection factory (``open_passages_db``), snapshot media cleanup
(``cleanup_passage_media``), retention pruning (``prune_water_passages``),
schema initialization (``initialize_water_passages_db``), payload validation
(``_validate_passage_payload``), row serialization (``passage_row_to_dict``)
and the store API (``upsert_water_passage`` / ``list_water_passages``).

Depends on ``config`` constants, ``identity.now_iso``, the shared numeric
coercion helpers ``optional_float``/``optional_int`` from ``objects_registry``
and ``passage_mirrors._delete_passage_mirrors`` for the mirror prune. The
mirror dependency is one-directional: ``prune_water_passages`` calls
``_delete_passage_mirrors``, so this module must not be imported by
``passage_mirrors`` back (import-cycle rule) and the mirror keeps its wave-2
``open_passages_db`` sentinel - ``main.py`` binds the factory defined here
into the mirror module right after the seam (the binding line is unchanged
from wave 2; it runs at main's import time, before any mirror caller: every
caller lives in main.py's module tail or route handlers). Same dual import
idiom as the other ``api/app`` modules: one canonical instance per import mode.
"""

import json
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

try:  # package context (api.app.water_passages) and direct-file load both supported
    from . import config  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
    from .config import (  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
        PASSAGES_DB_FILE,
        PASSAGES_RETENTION_LIMIT,
        PASSAGE_MEDIA_DIR,
        PASSAGE_ID_RE,
        PASSAGE_STATUSES,
        PASSAGE_SPEED_STATUSES,
    )
    from . import identity  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
    from .identity import now_iso
    from . import objects_registry  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
    from .objects_registry import optional_float, optional_int
    from . import passage_mirrors  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
    from .passage_mirrors import _delete_passage_mirrors
except ImportError:  # direct uvicorn app-dir / spec_from_file_location execution
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
    from config import (  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
        PASSAGES_DB_FILE,
        PASSAGES_RETENTION_LIMIT,
        PASSAGE_MEDIA_DIR,
        PASSAGE_ID_RE,
        PASSAGE_STATUSES,
        PASSAGE_SPEED_STATUSES,
    )
    import identity  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
    from identity import now_iso
    import objects_registry  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
    from objects_registry import optional_float, optional_int
    import passage_mirrors  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
    from passage_mirrors import _delete_passage_mirrors

__all__ = [
    "open_passages_db",
    "cleanup_passage_media",
    "prune_water_passages",
    "initialize_water_passages_db",
    "_validate_passage_payload",
    "passage_row_to_dict",
    "upsert_water_passage",
    "list_water_passages",
]

@contextmanager
def open_passages_db():
    connection = sqlite3.connect(str(PASSAGES_DB_FILE), timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def cleanup_passage_media(snapshot_url: Optional[str]) -> None:
    if not snapshot_url:
        return
    prefix = "/sea-speed/media/passages/"
    value = str(snapshot_url)
    if not value.startswith(prefix):
        return
    filename = value[len(prefix):]
    if not filename or filename != Path(filename).name or not filename.endswith(".jpg"):
        return
    try:
        (PASSAGE_MEDIA_DIR / filename).unlink(missing_ok=True)
    except OSError:
        pass

def prune_water_passages(connection: sqlite3.Connection, target_limit: int = PASSAGES_RETENTION_LIMIT) -> List[str]:
    target_limit = max(0, int(target_limit))
    count = int(connection.execute("SELECT COUNT(*) FROM water_passages").fetchone()[0])
    excess = max(0, count - target_limit)
    if excess == 0:
        return []
    rows = connection.execute(
        """
        SELECT passage_id, snapshot_url
        FROM water_passages
        WHERE status = 'completed'
        ORDER BY COALESCE(completed_at, last_seen_at, started_at) ASC, passage_id ASC
        LIMIT ?
        """,
        (excess,),
    ).fetchall()
    if not rows:
        return []
    passage_ids = [str(row["passage_id"]) for row in rows]
    placeholders = ",".join("?" for _ in passage_ids)
    connection.execute(f"DELETE FROM water_passages WHERE passage_id IN ({placeholders})", passage_ids)
    _delete_passage_mirrors(passage_ids)
    return [str(row["snapshot_url"]) for row in rows if row["snapshot_url"]]

def initialize_water_passages_db() -> None:
    orphan_urls: List[str] = []
    with open_passages_db() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS water_passages (
                passage_id TEXT PRIMARY KEY,
                camera_id TEXT NOT NULL,
                class_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                completed_at TEXT,
                track_fragments_json TEXT NOT NULL,
                vessel_id TEXT,
                confidence REAL,
                direction TEXT,
                speed_status TEXT NOT NULL,
                speed_kmh REAL,
                speed_method TEXT,
                measurement_meta_json TEXT NOT NULL,
                snapshot_url TEXT,
                snapshot_score REAL NOT NULL DEFAULT 0,
                observation_count INTEGER NOT NULL DEFAULT 0,
                worker_source_commit TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_water_passages_last_seen ON water_passages(last_seen_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_water_passages_completed ON water_passages(status, completed_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_water_passages_speed ON water_passages(speed_status, speed_kmh)")
        orphan_urls.extend(prune_water_passages(connection, target_limit=PASSAGES_RETENTION_LIMIT))
        count = int(connection.execute("SELECT COUNT(*) FROM water_passages").fetchone()[0])
        if count > PASSAGES_RETENTION_LIMIT:
            raise RuntimeError("water passage registry exceeds hard limit with non-prunable active rows")
    for snapshot_url in orphan_urls:
        cleanup_passage_media(snapshot_url)

def _validate_passage_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="passage payload must be an object")
    passage_id = str(payload.get("passage_id") or "").strip()
    if not PASSAGE_ID_RE.fullmatch(passage_id):
        raise HTTPException(status_code=400, detail="passage_id is invalid")
    status = str(payload.get("status") or "tracking").strip()
    if status not in PASSAGE_STATUSES:
        raise HTTPException(status_code=400, detail="passage status is invalid")
    speed_status = str(payload.get("speed_status") or "unknown").strip()
    if speed_status not in PASSAGE_SPEED_STATUSES:
        raise HTTPException(status_code=400, detail="speed_status is invalid")
    started_at = str(payload.get("started_at") or "").strip()
    last_seen_at = str(payload.get("last_seen_at") or started_at).strip()
    completed_at = str(payload.get("completed_at") or "").strip() or None
    if not started_at or len(started_at) > 80 or not last_seen_at or len(last_seen_at) > 80:
        raise HTTPException(status_code=400, detail="passage timestamps are invalid")
    class_name = str(payload.get("class_name") or "vessel").strip()
    if class_name != "vessel":
        raise HTTPException(status_code=400, detail="Water passage class_name must be vessel")
    raw_fragments = payload.get("track_fragments") or []
    if not isinstance(raw_fragments, list) or len(raw_fragments) > 64:
        raise HTTPException(status_code=400, detail="track_fragments is invalid")
    track_fragments: List[int] = []
    for value in raw_fragments:
        track_id = optional_int(value)
        if track_id is None:
            raise HTTPException(status_code=400, detail="track_fragments is invalid")
        if track_id not in track_fragments:
            track_fragments.append(track_id)
    speed_kmh = optional_float(payload.get("speed_kmh"))
    if speed_kmh is not None and speed_kmh < 0:
        raise HTTPException(status_code=400, detail="speed_kmh must be >= 0")
    if speed_status == "measured" and speed_kmh is None:
        raise HTTPException(status_code=400, detail="measured passage requires speed_kmh")
    measurement_meta = payload.get("measurement_meta") or {}
    if not isinstance(measurement_meta, dict):
        raise HTTPException(status_code=400, detail="measurement_meta must be an object")
    measurement_meta_json = json.dumps(measurement_meta, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(measurement_meta_json.encode("utf-8")) > 8192:
        raise HTTPException(status_code=400, detail="measurement_meta is too large")
    confidence = optional_float(payload.get("confidence"))
    snapshot_score = optional_float(payload.get("snapshot_score")) or 0.0
    observation_count = optional_int(payload.get("observation_count")) or 0
    if snapshot_score < 0 or observation_count < 0:
        raise HTTPException(status_code=400, detail="passage counters are invalid")
    vessel_id = payload.get("vessel_id")
    vessel_id = str(vessel_id).strip() if vessel_id not in (None, "") else None
    if vessel_id is not None and len(vessel_id) > 128:
        raise HTTPException(status_code=400, detail="vessel_id is invalid")
    direction = payload.get("direction")
    direction = str(direction).strip() if direction not in (None, "") else None
    if direction is not None and len(direction) > 32:
        raise HTTPException(status_code=400, detail="direction is invalid")
    speed_method = payload.get("speed_method")
    speed_method = str(speed_method).strip() if speed_method not in (None, "") else None
    if speed_method is not None and len(speed_method) > 64:
        raise HTTPException(status_code=400, detail="speed_method is invalid")
    worker_source_commit = payload.get("worker_source_commit")
    worker_source_commit = str(worker_source_commit).strip().lower() if worker_source_commit not in (None, "") else None
    if worker_source_commit is not None and (len(worker_source_commit) != 40 or any(ch not in "0123456789abcdef" for ch in worker_source_commit)):
        raise HTTPException(status_code=400, detail="worker_source_commit is invalid")
    snapshot_url = payload.get("snapshot_url")
    snapshot_url = str(snapshot_url).strip() if snapshot_url not in (None, "") else None
    if snapshot_url is not None and not snapshot_url.startswith("/sea-speed/media/passages/"):
        raise HTTPException(status_code=400, detail="snapshot_url is invalid")
    return {
        "passage_id": passage_id,
        "camera_id": "cam1",
        "class_name": "vessel",
        "status": status,
        "started_at": started_at,
        "last_seen_at": last_seen_at,
        "completed_at": completed_at,
        "track_fragments": track_fragments,
        "vessel_id": vessel_id,
        "confidence": confidence,
        "direction": direction,
        "speed_status": speed_status,
        "speed_kmh": speed_kmh,
        "speed_method": speed_method,
        "measurement_meta": measurement_meta,
        "measurement_meta_json": measurement_meta_json,
        "snapshot_url": snapshot_url,
        "snapshot_score": snapshot_score,
        "observation_count": observation_count,
        "worker_source_commit": worker_source_commit,
    }

def passage_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    try:
        data["track_fragments"] = json.loads(data.pop("track_fragments_json", "[]"))
    except Exception:
        data["track_fragments"] = []
    try:
        data["measurement_meta"] = json.loads(data.pop("measurement_meta_json", "{}"))
    except Exception:
        data["measurement_meta"] = {}
    return data

def upsert_water_passage(payload: Dict[str, Any], snapshot_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    incoming = _validate_passage_payload(payload)
    orphan_urls: List[str] = []
    snapshot_path: Optional[Path] = None
    snapshot_data: Optional[bytes] = None
    with open_passages_db() as connection:
        existing_row = connection.execute(
            "SELECT * FROM water_passages WHERE passage_id = ?", (incoming["passage_id"],)
        ).fetchone()
        if existing_row is None:
            count = int(connection.execute("SELECT COUNT(*) FROM water_passages").fetchone()[0])
            if count >= PASSAGES_RETENTION_LIMIT:
                orphan_urls.extend(prune_water_passages(connection, target_limit=PASSAGES_RETENTION_LIMIT - 1))
                count = int(connection.execute("SELECT COUNT(*) FROM water_passages").fetchone()[0])
                if count >= PASSAGES_RETENTION_LIMIT:
                    raise RuntimeError("water passage registry is full with active passages")
            current: Dict[str, Any] = {}
            existing_fragments: List[int] = []
            existing_meta: Dict[str, Any] = {}
        else:
            current = dict(existing_row)
            try:
                existing_fragments = json.loads(current.get("track_fragments_json") or "[]")
            except Exception:
                existing_fragments = []
            try:
                existing_meta = json.loads(current.get("measurement_meta_json") or "{}")
            except Exception:
                existing_meta = {}
        fragments: List[int] = []
        for value in [*existing_fragments, *incoming["track_fragments"]]:
            track_id = optional_int(value)
            if track_id is not None and track_id not in fragments:
                fragments.append(track_id)
        status_rank = {"tracking": 0, "measuring": 1, "measured": 2, "completed": 3}
        speed_rank = {"unknown": 0, "measuring": 1, "incomplete": 2, "measured": 3}
        current_status = str(current.get("status") or "tracking")
        status = incoming["status"] if status_rank.get(incoming["status"], -1) >= status_rank.get(current_status, -1) else current_status
        current_speed_status = str(current.get("speed_status") or "unknown")
        use_incoming_speed = speed_rank.get(incoming["speed_status"], -1) >= speed_rank.get(current_speed_status, -1)
        speed_status = incoming["speed_status"] if use_incoming_speed else current_speed_status
        speed_kmh = incoming["speed_kmh"] if use_incoming_speed else optional_float(current.get("speed_kmh"))
        direction = incoming["direction"] if use_incoming_speed and incoming["direction"] else current.get("direction")
        speed_method = incoming["speed_method"] or current.get("speed_method")
        measurement_meta = incoming["measurement_meta"] if use_incoming_speed else existing_meta
        existing_snapshot_score = optional_float(current.get("snapshot_score")) or 0.0
        snapshot_score = max(existing_snapshot_score, incoming["snapshot_score"])
        snapshot_url = incoming["snapshot_url"] or current.get("snapshot_url")
        if snapshot_bytes is not None and incoming["snapshot_score"] >= existing_snapshot_score:
            if len(snapshot_bytes) > 5 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="passage snapshot is too large")
            filename = f'{incoming["passage_id"]}.jpg'
            snapshot_path = PASSAGE_MEDIA_DIR / filename
            snapshot_data = bytes(snapshot_bytes)
            snapshot_url = f"/sea-speed/media/passages/{filename}"
        if not snapshot_url or not str(snapshot_url).strip().startswith("/sea-speed/media/"):
            raise HTTPException(status_code=422, detail="passage snapshot is required")
        now = now_iso()
        merged = {
            **incoming,
            "status": status,
            "started_at": str(current.get("started_at") or incoming["started_at"]),
            "last_seen_at": max(str(current.get("last_seen_at") or incoming["last_seen_at"]), incoming["last_seen_at"]),
            "completed_at": incoming["completed_at"] or current.get("completed_at"),
            "track_fragments": fragments,
            "confidence": max(optional_float(current.get("confidence")) or 0.0, incoming["confidence"] or 0.0),
            "direction": direction,
            "speed_status": speed_status,
            "speed_kmh": speed_kmh,
            "speed_method": speed_method,
            "measurement_meta": measurement_meta,
            "measurement_meta_json": json.dumps(measurement_meta, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "snapshot_url": snapshot_url,
            "snapshot_score": snapshot_score,
            "observation_count": max(optional_int(current.get("observation_count")) or 0, incoming["observation_count"]),
            "worker_source_commit": incoming["worker_source_commit"] or current.get("worker_source_commit"),
        }
        values = (
            merged["passage_id"], "cam1", "vessel", merged["status"], merged["started_at"], merged["last_seen_at"],
            merged["completed_at"], json.dumps(merged["track_fragments"]), merged["vessel_id"], merged["confidence"],
            merged["direction"], merged["speed_status"], merged["speed_kmh"], merged["speed_method"],
            merged["measurement_meta_json"], merged["snapshot_url"], merged["snapshot_score"],
            merged["observation_count"], merged["worker_source_commit"],
            str(current.get("created_at") or now), now,
        )
        connection.execute(
            """
            INSERT INTO water_passages (
                passage_id, camera_id, class_name, status, started_at, last_seen_at, completed_at,
                track_fragments_json, vessel_id, confidence, direction, speed_status, speed_kmh,
                speed_method, measurement_meta_json, snapshot_url, snapshot_score, observation_count,
                worker_source_commit, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(passage_id) DO UPDATE SET
                status=excluded.status, last_seen_at=excluded.last_seen_at, completed_at=excluded.completed_at,
                track_fragments_json=excluded.track_fragments_json, vessel_id=excluded.vessel_id,
                confidence=excluded.confidence, direction=excluded.direction,
                speed_status=excluded.speed_status, speed_kmh=excluded.speed_kmh,
                speed_method=excluded.speed_method, measurement_meta_json=excluded.measurement_meta_json,
                snapshot_url=excluded.snapshot_url, snapshot_score=excluded.snapshot_score,
                observation_count=excluded.observation_count, worker_source_commit=excluded.worker_source_commit,
                updated_at=excluded.updated_at
            """,
            values,
        )
        orphan_urls.extend(prune_water_passages(connection, target_limit=PASSAGES_RETENTION_LIMIT))
        row = connection.execute("SELECT * FROM water_passages WHERE passage_id = ?", (merged["passage_id"],)).fetchone()
    if snapshot_path is not None and snapshot_data is not None:
        try:
            PASSAGE_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
            temp_path = snapshot_path.with_suffix(".jpg.tmp")
            temp_path.write_bytes(snapshot_data)
            temp_path.replace(snapshot_path)
        except OSError as exc:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise HTTPException(status_code=503, detail="passage snapshot storage is unavailable") from exc
    for snapshot_url in orphan_urls:
        cleanup_passage_media(snapshot_url)
    if row is None:
        raise RuntimeError("water passage persistence failed")
    return passage_row_to_dict(row)

def list_water_passages(limit: int = 50) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    with open_passages_db() as connection:
        rows = connection.execute(
            "SELECT * FROM water_passages ORDER BY last_seen_at DESC, passage_id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [passage_row_to_dict(row) for row in rows]
