import json
import os
import time
import uuid
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

STATE_FILE = DATA_DIR / "cam1_state.json"
EVENTS_FILE = DATA_DIR / "events.json"
ROI_FILE = DATA_DIR / "cam1_roi.json"
SPEED_CONFIG_FILE = DATA_DIR / "cam1_speed_config.json"
SPEED_LINES_FILE = DATA_DIR / "cam1_speed_lines.json"

API_TOKEN = os.environ.get("SEA_SPEED_API_TOKEN", "")

DATA_DIR.mkdir(parents=True, exist_ok=True)
OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
EVENTS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Sea Speed API")

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def default_state() -> Dict[str, Any]:
    return {
        "camera_id": "cam1",
        "updated_at": None,
        "worker_online": False,
        "motion_now": False,
        "motion_area": 0,
        "ai_active": False,
        "detections": 0,
        "tracks": 0,
        "last_overlay_url": None,
        "message": "No worker state received yet",
    }


@app.get("/api/cam1/state")
def get_cam1_state() -> Dict[str, Any]:
    state = read_json_file(STATE_FILE, default_state())

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

    return {
        "ok": True,
        "state": data,
    }


@app.get("/api/cam1/events")
def get_cam1_events(limit: int = 50) -> Dict[str, Any]:
    events = read_json_file(EVENTS_FILE, [])
    events = events[: max(1, min(limit, 200))]
    return {
        "ok": True,
        "camera_id": "cam1",
        "count": len(events),
        "events": events,
    }


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
    event["created_at"] = event.get("created_at") or now_iso()

    if snapshot is not None:
        filename = f"{event_id}.jpg"
        snapshot_path = EVENTS_MEDIA_DIR / filename
        content = await snapshot.read()
        snapshot_path.write_bytes(content)
        event["snapshot_url"] = f"/sea-speed/media/events/{filename}"

    events: List[Dict[str, Any]] = read_json_file(EVENTS_FILE, [])
    events.insert(0, event)
    events = events[:500]

    write_json_file(EVENTS_FILE, events)

    return {
        "ok": True,
        "event": event,
    }


@app.get("/api/cam1/roi")
def get_cam1_roi() -> Dict[str, Any]:
    default_roi = {
        "ok": True,
        "camera_id": "cam1",
        "enabled": False,
        "polygon": [],
        "updated_at": None,
    }

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
        "time": now_iso(),
    }
