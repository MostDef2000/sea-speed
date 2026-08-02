import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path("/opt/sea-speed-api")
DATA_DIR = BASE_DIR / "data"
MEDIA_DIR = BASE_DIR / "media"
OVERLAY_DIR = MEDIA_DIR / "overlays"
EVENTS_MEDIA_DIR = MEDIA_DIR / "events"
DEPLOYED_COMMIT_FILE = Path("/opt/sea-speed-deploy/state/current-release")

STATE_FILE = DATA_DIR / "cam1_state.json"
EVENTS_FILE = DATA_DIR / "events.json"
OBJECTS_DB_FILE = DATA_DIR / "objects.sqlite3"
ROI_FILE = DATA_DIR / "cam1_roi.json"
SPEED_CONFIG_FILE = DATA_DIR / "cam1_speed_config.json"
SPEED_LINES_FILE = DATA_DIR / "cam1_speed_lines.json"

API_TOKEN = os.environ.get("SEA_SPEED_API_TOKEN", "")
API_SCHEMA = "sea_speed_api_v1"
WORKER_STATE_SCHEMA = "sea_speed_worker_state_v1"
VEHICLE_EVENT_SCHEMA = "sea_speed_vehicle_event_v1"
TELEMETRY_SCHEMA = "sea_speed_telemetry_v1"
OBJECT_STATUSES = {"new", "reviewed", "ignored"}
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

DATA_DIR.mkdir(parents=True, exist_ok=True)
OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
EVENTS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Sea Speed API")
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def deployed_source_commit() -> str:
    configured = os.environ.get("SEA_SPEED_SOURCE_COMMIT", "").strip()
    if SHA_RE.fullmatch(configured):
        return configured.lower()
    try:
        value = DEPLOYED_COMMIT_FILE.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return "unknown"
    return value.lower() if SHA_RE.fullmatch(value) else "unknown"


def require_auth(authorization: Optional[str]) -> None:
    if not API_TOKEN:
        raise HTTPException(status_code=500, detail="SEA_SPEED_API_TOKEN is not set")

    expected = f"Bearer {API_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json_file(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


@contextmanager
def open_objects_db():
    connection = sqlite3.connect(str(OBJECTS_DB_FILE), timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


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
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_objects_detected_at ON objects(detected_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_objects_class_name ON objects(class_name)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_objects_speed_kmh ON objects(speed_kmh)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_objects_status ON objects(status)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_objects_deleted_at ON objects(deleted_at)"
        )


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


def persist_object_event(event: Dict[str, Any]) -> bool:
    object_id = stable_object_id(event)
    detected_at = str(event.get("created_at") or event.get("detected_at") or now_iso())
    created_at = str(event.get("created_at") or now_iso())
    original_event_json = json.dumps(event, ensure_ascii=False, sort_keys=True)

    with open_objects_db() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO objects (
                object_id, camera_id, track_id, detected_at, class_name,
                confidence, speed_kmh, snapshot_url, comment, status,
                original_event_json, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', 'new', ?, ?, ?, NULL)
            """,
            (
                object_id,
                str(event.get("camera_id") or "cam1"),
                optional_int(event.get("track_id")),
                detected_at,
                str(event.get("class_name") or event.get("class") or "object"),
                optional_float(event.get("confidence")),
                optional_float(event.get("speed_kmh")),
                event.get("snapshot_url"),
                original_event_json,
                created_at,
                now_iso(),
            ),
        )
        return cursor.rowcount > 0


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
) -> tuple[str, List[Any]]:
    clauses = ["camera_id = ?"]
    values: List[Any] = ["cam1"]
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
    return " AND ".join(clauses), values


def default_state() -> Dict[str, Any]:
    return {
        "camera_id": "cam1",
        "state_schema": WORKER_STATE_SCHEMA,
        "telemetry_schema": TELEMETRY_SCHEMA,
        "worker_source_commit": None,
        "updated_at": None,
        "worker_online": False,
        "motion_now": False,
        "motion_area": 0,
        "ai_active": False,
        "detections": 0,
        "tracks": 0,
        "frame_no": 0,
        "last_overlay_url": None,
        "message": "No worker state received yet",
    }


initialize_objects_db()
import_existing_events()


@app.get("/api/cam1/state")
def get_cam1_state() -> Dict[str, Any]:
    state = read_json_file(STATE_FILE, default_state())
    state.setdefault("state_schema", WORKER_STATE_SCHEMA)
    state.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    state.setdefault("worker_source_commit", None)
    state.setdefault("frame_no", 0)

    updated_at = state.get("updated_at")
    if not updated_at:
        state["worker_online"] = False
        return state

    try:
        dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        age = time.time() - dt.timestamp()
        state["worker_online"] = age <= 30
    except Exception:
        state["worker_online"] = False

    return state


@app.post("/api/cam1/state")
async def post_cam1_state(
    metadata: str = Form(...),
    overlay: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    require_auth(authorization)

    try:
        data = json.loads(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON")

    data["camera_id"] = "cam1"
    data.setdefault("state_schema", WORKER_STATE_SCHEMA)
    data.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    data.setdefault("worker_source_commit", None)
    data["updated_at"] = now_iso()
    data["worker_online"] = True

    if overlay is not None:
        overlay_path = OVERLAY_DIR / "cam1_latest_overlay.jpg"
        content = await overlay.read()
        overlay_path.write_bytes(content)
        data["last_overlay_url"] = "/sea-speed/media/overlays/cam1_latest_overlay.jpg"
    else:
        old_state = read_json_file(STATE_FILE, default_state())
        data["last_overlay_url"] = old_state.get("last_overlay_url")

    write_json_file(STATE_FILE, data)

    return {"ok": True, "state": data}


@app.get("/api/cam1/events")
def get_cam1_events(limit: int = 50) -> Dict[str, Any]:
    events = read_json_file(EVENTS_FILE, [])
    events = events[: max(1, min(limit, 200))]
    return {"ok": True, "camera_id": "cam1", "count": len(events), "events": events}


@app.post("/api/cam1/events")
async def post_cam1_event(
    metadata: str = Form(...),
    snapshot: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    require_auth(authorization)

    try:
        event = json.loads(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON")

    event_id = str(event.get("event_id") or uuid.uuid4())
    event["event_id"] = event_id
    event["camera_id"] = "cam1"
    event.setdefault("event_schema", VEHICLE_EVENT_SCHEMA)
    event.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    event.setdefault("worker_source_commit", None)
    event.setdefault("calibration_version", None)
    event["created_at"] = event.get("created_at") or now_iso()

    if snapshot is not None:
        filename = f"{event_id}.jpg"
        snapshot_path = EVENTS_MEDIA_DIR / filename
        content = await snapshot.read()
        snapshot_path.write_bytes(content)
        event["snapshot_url"] = f"/sea-speed/media/events/{filename}"

    persist_object_event(event)

    events: List[Dict[str, Any]] = read_json_file(EVENTS_FILE, [])
    events.insert(0, event)
    events = events[:500]
    write_json_file(EVENTS_FILE, events)

    return {"ok": True, "event": event}


@app.get("/api/cam1/objects")
def get_cam1_objects(
    limit: int = 50,
    offset: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    class_name: Optional[str] = None,
    status: Optional[str] = None,
    speed_min: Optional[float] = None,
    speed_max: Optional[float] = None,
    search: Optional[str] = None,
    include_deleted: bool = False,
) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    if speed_min is not None and speed_min < 0:
        raise HTTPException(status_code=400, detail="speed_min must be >= 0")
    if speed_max is not None and speed_max < 0:
        raise HTTPException(status_code=400, detail="speed_max must be >= 0")
    if speed_min is not None and speed_max is not None and speed_min > speed_max:
        raise HTTPException(status_code=400, detail="speed_min must be <= speed_max")

    where_sql, values = build_objects_where(
        date_from, date_to, class_name, status, speed_min, speed_max, search, include_deleted
    )
    with open_objects_db() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM objects WHERE {where_sql}", values
        ).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT * FROM objects
            WHERE {where_sql}
            ORDER BY detected_at DESC, object_id DESC
            LIMIT ? OFFSET ?
            """,
            [*values, limit, offset],
        ).fetchall()
    return {
        "ok": True,
        "camera_id": "cam1",
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "objects": [object_row_to_dict(row) for row in rows],
    }


@app.get("/api/cam1/objects/{object_id}")
def get_cam1_object(object_id: str) -> Dict[str, Any]:
    with open_objects_db() as connection:
        row = connection.execute(
            "SELECT * FROM objects WHERE object_id = ? AND camera_id = ? AND deleted_at IS NULL",
            (object_id, "cam1"),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return {"ok": True, "object": object_row_to_dict(row, include_original=True)}


@app.patch("/api/cam1/objects/{object_id}")
def patch_cam1_object(object_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
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
    values = [*updates.values(), object_id, "cam1"]
    with open_objects_db() as connection:
        cursor = connection.execute(
            f"UPDATE objects SET {set_sql} WHERE object_id = ? AND camera_id = ? AND deleted_at IS NULL",
            values,
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Object not found")
        row = connection.execute(
            "SELECT * FROM objects WHERE object_id = ? AND camera_id = ?",
            (object_id, "cam1"),
        ).fetchone()
    return {"ok": True, "object": object_row_to_dict(row, include_original=True)}


@app.delete("/api/cam1/objects/{object_id}")
def delete_cam1_object(object_id: str) -> Dict[str, Any]:
    deleted_at = now_iso()
    with open_objects_db() as connection:
        cursor = connection.execute(
            """
            UPDATE objects
            SET deleted_at = ?, updated_at = ?
            WHERE object_id = ? AND camera_id = ? AND deleted_at IS NULL
            """,
            (deleted_at, deleted_at, object_id, "cam1"),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Object not found")
    return {"ok": True, "object_id": object_id, "deleted_at": deleted_at}


@app.get("/api/cam1/roi")
def get_cam1_roi() -> Dict[str, Any]:
    default_roi = {"ok": True, "camera_id": "cam1", "enabled": False, "polygon": [], "updated_at": None}
    roi = read_json_file(ROI_FILE, default_roi)
    roi["ok"] = True
    roi["camera_id"] = "cam1"
    roi.setdefault("enabled", False)
    roi.setdefault("polygon", [])
    roi.setdefault("updated_at", None)
    return roi


@app.post("/api/cam1/roi")
def post_cam1_roi(payload: Dict[str, Any]) -> Dict[str, Any]:
    polygon = payload.get("polygon", [])
    enabled = bool(payload.get("enabled", True))

    clean_polygon = []
    if isinstance(polygon, list):
        for point in polygon:
            if not isinstance(point, dict):
                continue
            try:
                x = int(round(float(point.get("x"))))
                y = int(round(float(point.get("y"))))
            except Exception:
                continue
            clean_polygon.append({"x": x, "y": y})

    if enabled and len(clean_polygon) < 3:
        raise HTTPException(status_code=400, detail="ROI polygon must contain at least 3 points")

    roi = {
        "ok": True,
        "camera_id": "cam1",
        "enabled": enabled,
        "polygon": clean_polygon,
        "updated_at": now_iso(),
    }
    write_json_file(ROI_FILE, roi)
    return roi


@app.get("/api/cam1/speed-config")
def get_cam1_speed_config() -> Dict[str, Any]:
    default_config = {
        "ok": True,
        "camera_id": "cam1",
        "enabled": False,
        "kmh_per_px_s": 0.0,
        "updated_at": None,
    }
    config = read_json_file(SPEED_CONFIG_FILE, default_config)
    config["ok"] = True
    config["camera_id"] = "cam1"
    config.setdefault("enabled", False)
    config.setdefault("kmh_per_px_s", 0.0)
    config.setdefault("updated_at", None)
    return config


@app.post("/api/cam1/speed-config")
def post_cam1_speed_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    enabled = bool(payload.get("enabled", True))
    try:
        kmh_per_px_s = float(payload.get("kmh_per_px_s", 0.0))
    except Exception:
        raise HTTPException(status_code=400, detail="kmh_per_px_s must be a number")
    if kmh_per_px_s < 0:
        raise HTTPException(status_code=400, detail="kmh_per_px_s must be >= 0")

    config = {
        "ok": True,
        "camera_id": "cam1",
        "enabled": enabled and kmh_per_px_s > 0,
        "kmh_per_px_s": kmh_per_px_s,
        "updated_at": now_iso(),
    }
    write_json_file(SPEED_CONFIG_FILE, config)
    return config


def clean_points_list(raw_points: Any, max_points: int = 2) -> List[Dict[str, int]]:
    clean = []
    if not isinstance(raw_points, list):
        return clean
    for point in raw_points[:max_points]:
        if not isinstance(point, dict):
            continue
        try:
            x = int(round(float(point.get("x"))))
            y = int(round(float(point.get("y"))))
        except Exception:
            continue
        clean.append({"x": x, "y": y})
    return clean


@app.get("/api/cam1/speed-lines")
def get_cam1_speed_lines() -> Dict[str, Any]:
    default_config = {
        "ok": True,
        "camera_id": "cam1",
        "enabled": False,
        "distance_m": 57.0,
        "line_a": [],
        "line_b": [],
        "updated_at": None,
    }
    config = read_json_file(SPEED_LINES_FILE, default_config)
    config["ok"] = True
    config["camera_id"] = "cam1"
    config.setdefault("enabled", False)
    config.setdefault("distance_m", 57.0)
    config.setdefault("line_a", [])
    config.setdefault("line_b", [])
    config.setdefault("updated_at", None)
    return config


@app.post("/api/cam1/speed-lines")
def post_cam1_speed_lines(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        distance_m = float(payload.get("distance_m", 57.0))
    except Exception:
        raise HTTPException(status_code=400, detail="distance_m must be a number")
    if distance_m <= 0:
        raise HTTPException(status_code=400, detail="distance_m must be > 0")

    line_a = clean_points_list(payload.get("line_a"), max_points=2)
    line_b = clean_points_list(payload.get("line_b"), max_points=2)
    enabled = bool(payload.get("enabled", True))
    if enabled and (len(line_a) != 2 or len(line_b) != 2):
        raise HTTPException(status_code=400, detail="line_a and line_b must contain exactly 2 points each")

    config = {
        "ok": True,
        "camera_id": "cam1",
        "enabled": enabled,
        "distance_m": distance_m,
        "line_a": line_a,
        "line_b": line_b,
        "updated_at": now_iso(),
    }
    write_json_file(SPEED_LINES_FILE, config)
    return config


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "sea-speed-api",
        "api_schema": API_SCHEMA,
        "source_commit": deployed_source_commit(),
        "time": now_iso(),
    }
