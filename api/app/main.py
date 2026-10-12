import json
import os
import sys
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from collections import deque
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse

try:  # package context (api.app.main) and direct-file load both supported
    from . import store
    from .store import read_json_file, write_json_file
except ImportError:  # direct uvicorn app-dir / spec_from_file_location execution
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import store
    from store import read_json_file, write_json_file


try:  # package context (api.app.main) and direct-file load both supported
    from . import config  # noqa: F401  # explicit re-export seam (issue #396 wave 1)
    from .config import (  # noqa: F401  # explicit re-export seam (issue #396 wave 1)
        BASE_DIR,
        DATA_DIR,
        MEDIA_DIR,
        OVERLAY_DIR,
        EVENTS_MEDIA_DIR,
        PASSAGES_MEDIA_DIR,
        PASSAGE_MEDIA_DIR,
        CAMERA_PREVIEW_DIR,
        CAMERA_SNAPSHOT_DIR,
        DEPLOYED_COMMIT_FILE,
        STATE_FILE,
        EVENTS_FILE,
        OBJECTS_DB_FILE,
        PASSAGES_DB_FILE,
        STATE_DB_FILE,
        EVENTS_FEED_LIMIT,
        CROSSINGS_STORE_LIMIT,
        ROI_FILE,
        SPEED_CONFIG_FILE,
        SPEED_LINES_FILE,
        ANALYTICS_IDENTITIES,
        CAMERA_PREVIEW_CATALOG_FILE,
        CAMERA_PREVIEW_STATE_FILE,
        CAMERA_PREVIEW_FFMPEG_BIN,
        API_TOKEN,
        WORKER_CONTROL_TOKEN,
        WORKER_CONTROL_URL,
        WORKER_CONTROL_PROTOCOL,
        API_SCHEMA,
        WORKER_STATE_SCHEMA,
        VEHICLE_EVENT_SCHEMA,
        TELEMETRY_SCHEMA,
        CAMERA_PREVIEW_CATALOG_SCHEMA,
        OBJECT_STATUSES,
        OBJECTS_RETENTION_LIMIT,
        PASSAGES_RETENTION_LIMIT,
        PASSAGE_STATUSES,
        PASSAGE_SPEED_STATUSES,
        PASSAGE_ID_RE,
        SHA_RE,
        CAMERA_PREVIEW_ID_RE,
        CAMERA_PREVIEW_SESSION_RE,
        CAMERA_PREVIEW_RFC1918,
        CAMERA_PREVIEW_LOCK,
        CAMERA_PREVIEW_START_TIMEOUT_SEC,
        CAMERA_SNAPSHOT_EXTRACT_TIMEOUT_SEC,
        CAMERA_SNAPSHOT_MIN_BYTES,
        CAMERA_SNAPSHOT_MIN_LUMA_SPREAD,
        WORKER_CONTROL_TIMEOUT_SEC,
        CAMERA_PREVIEW_TTL_SEC,
    )
    from . import identity  # noqa: F401  # explicit re-export seam (issue #396 wave 1)
    from .identity import (  # noqa: F401  # explicit re-export seam (issue #396 wave 1)
        now_iso,
        deployed_source_commit,
        require_auth,
        require_operator_identity,
        worker_control_origin,
        call_worker_control,
        analytics_identity,
    )
except ImportError:  # direct uvicorn app-dir / spec_from_file_location execution
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config  # noqa: F401  # explicit re-export seam (issue #396 wave 1)
    from config import (  # noqa: F401  # explicit re-export seam (issue #396 wave 1)
        BASE_DIR,
        DATA_DIR,
        MEDIA_DIR,
        OVERLAY_DIR,
        EVENTS_MEDIA_DIR,
        PASSAGES_MEDIA_DIR,
        PASSAGE_MEDIA_DIR,
        CAMERA_PREVIEW_DIR,
        CAMERA_SNAPSHOT_DIR,
        DEPLOYED_COMMIT_FILE,
        STATE_FILE,
        EVENTS_FILE,
        OBJECTS_DB_FILE,
        PASSAGES_DB_FILE,
        STATE_DB_FILE,
        EVENTS_FEED_LIMIT,
        CROSSINGS_STORE_LIMIT,
        ROI_FILE,
        SPEED_CONFIG_FILE,
        SPEED_LINES_FILE,
        ANALYTICS_IDENTITIES,
        CAMERA_PREVIEW_CATALOG_FILE,
        CAMERA_PREVIEW_STATE_FILE,
        CAMERA_PREVIEW_FFMPEG_BIN,
        API_TOKEN,
        WORKER_CONTROL_TOKEN,
        WORKER_CONTROL_URL,
        WORKER_CONTROL_PROTOCOL,
        API_SCHEMA,
        WORKER_STATE_SCHEMA,
        VEHICLE_EVENT_SCHEMA,
        TELEMETRY_SCHEMA,
        CAMERA_PREVIEW_CATALOG_SCHEMA,
        OBJECT_STATUSES,
        OBJECTS_RETENTION_LIMIT,
        PASSAGES_RETENTION_LIMIT,
        PASSAGE_STATUSES,
        PASSAGE_SPEED_STATUSES,
        PASSAGE_ID_RE,
        SHA_RE,
        CAMERA_PREVIEW_ID_RE,
        CAMERA_PREVIEW_SESSION_RE,
        CAMERA_PREVIEW_RFC1918,
        CAMERA_PREVIEW_LOCK,
        CAMERA_PREVIEW_START_TIMEOUT_SEC,
        CAMERA_SNAPSHOT_EXTRACT_TIMEOUT_SEC,
        CAMERA_SNAPSHOT_MIN_BYTES,
        CAMERA_SNAPSHOT_MIN_LUMA_SPREAD,
        WORKER_CONTROL_TIMEOUT_SEC,
        CAMERA_PREVIEW_TTL_SEC,
    )
    import identity  # noqa: F401  # explicit re-export seam (issue #396 wave 1)
    from identity import (  # noqa: F401  # explicit re-export seam (issue #396 wave 1)
        now_iso,
        deployed_source_commit,
        require_auth,
        require_operator_identity,
        worker_control_origin,
        call_worker_control,
        analytics_identity,
    )




try:  # package context (api.app.main) and direct-file load both supported
    from . import objects_registry  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from .objects_registry import (  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
        open_objects_db,
        prune_objects_registry,
        initialize_objects_db,
        optional_float,
        optional_int,
        stable_object_id,
        prune_snapshotless_objects,
        persist_object_event,
        import_existing_events,
        object_row_to_dict,
        build_objects_where,
        patch_object_record,
        delete_object_record,
    )
    from . import passage_mirrors  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from .passage_mirrors import (  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
        persist_passage_object,
        import_existing_passages,
        _delete_passage_mirrors,
        reconcile_passage_mirrors,
    )
except ImportError:  # direct uvicorn app-dir / spec_from_file_location execution
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import objects_registry  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from objects_registry import (  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
        open_objects_db,
        prune_objects_registry,
        initialize_objects_db,
        optional_float,
        optional_int,
        stable_object_id,
        prune_snapshotless_objects,
        persist_object_event,
        import_existing_events,
        object_row_to_dict,
        build_objects_where,
        patch_object_record,
        delete_object_record,
    )
    import passage_mirrors  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
    from passage_mirrors import (  # noqa: F401  # explicit re-export seam (issue #396 wave 2)
        persist_passage_object,
        import_existing_passages,
        _delete_passage_mirrors,
        reconcile_passage_mirrors,
    )


try:  # package context (api.app.main) and direct-file load both supported
    from . import water_passages  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
    from .water_passages import (  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
        open_passages_db,
        cleanup_passage_media,
        prune_water_passages,
        initialize_water_passages_db,
        _validate_passage_payload,
        passage_row_to_dict,
        upsert_water_passage,
        list_water_passages,
    )
except ImportError:  # direct uvicorn app-dir / spec_from_file_location execution
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import water_passages  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
    from water_passages import (  # noqa: F401  # explicit re-export seam (issue #396 wave 3)
        open_passages_db,
        cleanup_passage_media,
        prune_water_passages,
        initialize_water_passages_db,
        _validate_passage_payload,
        passage_row_to_dict,
        upsert_water_passage,
        list_water_passages,
    )


try:  # package context (api.app.main) and direct-file load both supported
    from . import camera_preview  # noqa: F401  # explicit re-export seam (issue #396 wave 4)
    from .camera_preview import (  # noqa: F401  # explicit re-export seam (issue #396 wave 4)
        validate_camera_preview_source,
        load_camera_preview_catalog,
        camera_snapshot_path,
        camera_snapshot_public_metadata,
        build_camera_snapshot_extract_args,
        camera_snapshot_luma_spread,
        camera_snapshot_candidate_is_usable,
        commit_camera_snapshot_locked,
        camera_preview_public_state,
        camera_preview_pid_matches,
        cleanup_camera_preview_media,
        terminate_camera_preview_locked,
        active_camera_preview_locked,
        build_camera_preview_ffmpeg_args,
        start_camera_preview_locked,
    )
except ImportError:  # direct uvicorn app-dir / spec_from_file_location execution
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import camera_preview  # noqa: F401  # explicit re-export seam (issue #396 wave 4)
    from camera_preview import (  # noqa: F401  # explicit re-export seam (issue #396 wave 4)
        validate_camera_preview_source,
        load_camera_preview_catalog,
        camera_snapshot_path,
        camera_snapshot_public_metadata,
        build_camera_snapshot_extract_args,
        camera_snapshot_luma_spread,
        camera_snapshot_candidate_is_usable,
        commit_camera_snapshot_locked,
        camera_preview_public_state,
        camera_preview_pid_matches,
        cleanup_camera_preview_media,
        terminate_camera_preview_locked,
        active_camera_preview_locked,
        build_camera_preview_ffmpeg_args,
        start_camera_preview_locked,
    )


app = FastAPI(title="Sea Speed API")
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


EVENTS_MEDIA_GRACE_SECONDS = 24 * 3600
EVENTS_SWEEP_INTERVAL_SECONDS = 3600
_events_sweep_state = {"last": 0.0}


def sweep_events_media(force: bool = False, now: Optional[float] = None) -> int:
    current = time.time() if now is None else float(now)
    last = float(_events_sweep_state.get("last") or 0.0)
    if not force and current - last < EVENTS_SWEEP_INTERVAL_SECONDS:
        return 0
    _events_sweep_state["last"] = current
    try:
        candidates = list(EVENTS_MEDIA_DIR.iterdir())
    except OSError:
        return 0
    try:
        with open_objects_db() as connection:
            referenced = {
                str(row[0]) for row in connection.execute("SELECT DISTINCT snapshot_url FROM objects")
            }
    except Exception as error:
        print(f"events media sweep skipped: {error}", file=sys.stderr)
        return 0
    deleted = 0
    for path in candidates:
        if not path.is_file():
            continue
        name = path.name
        if not name.endswith(".jpg") or name != Path(name).name:
            continue
        if f"/sea-speed/media/events/{name}" in referenced:
            continue
        try:
            age = current - path.stat().st_mtime
        except OSError:
            continue
        if age <= EVENTS_MEDIA_GRACE_SECONDS:
            continue
        try:
            path.unlink()
            deleted += 1
        except OSError as error:
            print(f"events media sweep failed for {name}: {error}", file=sys.stderr)
    return deleted


# passage_mirrors resolves open_passages_db through this binding: the factory
# moved to water_passages.py in wave 3 (issue #396) and main imports it through
# the seam, so this wave-2 binding line is unchanged - it injects the same
# function object before any mirror caller can run (all callers live in
# main.py's module tail or route handlers, after this line). The mirror module
# cannot import water_passages itself: prune_water_passages calls
# _delete_passage_mirrors, so that edge would close an import cycle.
passage_mirrors.open_passages_db = open_passages_db


def default_state() -> Dict[str, Any]:
    return {
        "camera_id": "cam1",
        "analytics_profile": "water-v1",
        "domain": "water",
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
        "frame_width": 1920,
        "frame_height": 1080,
        "sample_fps": 10.0,
        "effective_fps": None,
        "p95_inference_ms": None,
        "overlay_rev": 0,
        "last_overlay_url": None,
        "message": "No worker state received yet",
    }


def analytics_data_file(camera_id: str, kind: str) -> Path:
    analytics_identity(camera_id)
    legacy = {
        "state": STATE_FILE,
        "events": EVENTS_FILE,
        "roi": ROI_FILE,
        "speed_config": SPEED_CONFIG_FILE,
        "speed_lines": SPEED_LINES_FILE,
    }
    if camera_id == "cam1" and kind in legacy:
        return legacy[kind]
    return DATA_DIR / f"{camera_id}_{kind}.json"


def analytics_default_state(camera_id: str) -> Dict[str, Any]:
    identity = analytics_identity(camera_id)
    data = default_state() if camera_id == "cam1" else {
        "camera_id": camera_id,
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
        "frame_width": 1920,
        "frame_height": 1080,
        "sample_fps": 10.0,
        "effective_fps": None,
        "p95_inference_ms": None,
        "overlay_rev": 0,
        "last_overlay_url": None,
        "message": "No worker state received yet",
    }
    data.update(identity)
    data["camera_id"] = camera_id
    return data


def analytics_state(camera_id: str) -> Dict[str, Any]:
    record = store.read_camera_state(STATE_DB_FILE, camera_id)
    state = record if record is not None else analytics_default_state(camera_id)
    identity = analytics_identity(camera_id)
    state["camera_id"] = camera_id
    state.setdefault("analytics_profile", identity["analytics_profile"])
    state.setdefault("domain", identity["domain"])
    state.setdefault("state_schema", WORKER_STATE_SCHEMA)
    state.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    state.setdefault("worker_source_commit", None)
    state.setdefault("frame_no", 0)
    state.setdefault("frame_width", 1920)
    state.setdefault("frame_height", 1080)
    state.setdefault("sample_fps", 10.0)
    state.setdefault("effective_fps", None)
    state.setdefault("p95_inference_ms", None)
    state.setdefault("overlay_rev", state.get("frame_no", 0))
    updated_at = state.get("updated_at")
    if not updated_at:
        state["worker_online"] = False
        return state
    try:
        dt = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        state["worker_online"] = time.time() - dt.timestamp() <= 30
    except Exception:
        state["worker_online"] = False
    return state


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


# Normalized ROI geometry — 0..1 + reference, scale-on-read to current frame size
DEFAULT_ROI_REF_W = 1920
DEFAULT_ROI_REF_H = 1080
LEGACY_ROI_W = 704
LEGACY_ROI_H = 576


def _is_normalized_point(point: Any) -> bool:
    return isinstance(point, dict) and ("x_norm" in point or "y_norm" in point)


def _clean_norm_points(raw_points: Any, max_points: int = 1000) -> List[Dict[str, float]]:
    clean: List[Dict[str, float]] = []
    if not isinstance(raw_points, list):
        return clean
    for p in raw_points[:max_points]:
        if not isinstance(p, dict):
            continue
        try:
            xn = float(p.get("x_norm", p.get("x", 0)))
            yn = float(p.get("y_norm", p.get("y", 0)))
        except Exception:
            continue
        # if caller passed absolute x 0..1920 already treat as norm only when explicitly x_norm present
        if "x_norm" not in p and "y_norm" not in p:
            continue
        xn = max(0.0, min(1.0, xn))
        yn = max(0.0, min(1.0, yn))
        clean.append({"x_norm": xn, "y_norm": yn})
    return clean


def _infer_legacy_ref_w_h(polygon: List[Dict[str, int]]) -> tuple[int, int]:
    if not polygon:
        return DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H
    max_x = max((p.get("x", 0) for p in polygon), default=0)
    max_y = max((p.get("y", 0) for p in polygon), default=0)
    if max_x <= LEGACY_ROI_W and max_y <= LEGACY_ROI_H and max_x > 0 and max_y > 0:
        return LEGACY_ROI_W, LEGACY_ROI_H
    return DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H


def _normalize_from_absolute(polygon: List[Dict[str, int]], ref_w: int, ref_h: int) -> List[Dict[str, float]]:
    return [{"x_norm": p["x"] / ref_w, "y_norm": p["y"] / ref_h} for p in polygon]


def _denormalize_to_absolute(polygon_norm: List[Dict[str, float]], dst_w: int, dst_h: int) -> List[Dict[str, int]]:
    return [{"x": int(round(p["x_norm"] * dst_w)), "y": int(round(p["y_norm"] * dst_h))} for p in polygon_norm]


def _normalize_legacy_polygon(legacy: List[Dict[str, int]], raw: Dict[str, Any]) -> tuple[List[Dict[str, float]], int, int]:
    ref_w, ref_h = _infer_legacy_ref_w_h(legacy)
    ref_w = int(raw.get("reference_width") or raw.get("referenceWidth") or ref_w)
    ref_h = int(raw.get("reference_height") or raw.get("referenceHeight") or ref_h)
    return _normalize_from_absolute(legacy, ref_w, ref_h), ref_w, ref_h


initialize_objects_db()
import_existing_events()
import_existing_passages()
reconcile_passage_mirrors()
sweep_events_media(force=True)
initialize_water_passages_db()


@app.get("/api/cameras")
def get_cameras() -> Dict[str, Any]:
    cameras = load_camera_preview_catalog()
    with CAMERA_PREVIEW_LOCK:
        active = camera_preview_public_state(active_camera_preview_locked())
    public_cameras = [
        {"camera_id": camera["camera_id"], "display_name": camera["display_name"], "available": True,
         "snapshot": camera_snapshot_public_metadata(camera["camera_id"])} for camera in cameras
    ]
    return {"ok": True, "schema": CAMERA_PREVIEW_CATALOG_SCHEMA, "count": len(public_cameras), "cameras": public_cameras,
            "active": active, "preview_policy": {"max_active": 1, "ttl_sec": CAMERA_PREVIEW_TTL_SEC}}


@app.get("/api/cameras/{camera_id}/snapshot")
def get_camera_snapshot(camera_id: str):
    cameras = load_camera_preview_catalog()
    if not any(entry["camera_id"] == camera_id for entry in cameras):
        raise HTTPException(status_code=404, detail="Camera is not present in the preview catalog")
    path = camera_snapshot_path(camera_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Camera snapshot is not available")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"})


@app.post("/api/cameras/{camera_id}/snapshot/commit")
def commit_camera_snapshot(camera_id: str, session_id: str) -> Dict[str, Any]:
    cameras = load_camera_preview_catalog()
    if not any(entry["camera_id"] == camera_id for entry in cameras):
        raise HTTPException(status_code=404, detail="Camera is not present in the preview catalog")
    if not CAMERA_PREVIEW_SESSION_RE.fullmatch(session_id):
        raise HTTPException(status_code=409, detail="Camera preview session is stale")
    with CAMERA_PREVIEW_LOCK:
        state = active_camera_preview_locked()
        if not state or state.get("camera_id") != camera_id or state.get("session_id") != session_id:
            raise HTTPException(status_code=409, detail="Camera preview session is stale")
        snapshot = commit_camera_snapshot_locked(state)
    return {"ok": True, "camera_id": camera_id, "snapshot": snapshot}


@app.get("/api/cameras/preview")
def get_camera_preview() -> Dict[str, Any]:
    with CAMERA_PREVIEW_LOCK:
        active = camera_preview_public_state(active_camera_preview_locked())
    return {"ok": True, "active": active}


@app.post("/api/cameras/{camera_id}/preview/start")
def start_camera_preview(camera_id: str) -> Dict[str, Any]:
    cameras = load_camera_preview_catalog()
    camera = next((entry for entry in cameras if entry["camera_id"] == camera_id), None)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera is not present in the preview catalog")
    with CAMERA_PREVIEW_LOCK:
        state = start_camera_preview_locked(camera)
    return {"ok": True, "preview": camera_preview_public_state(state)}


@app.post("/api/cameras/preview/stop")
def stop_camera_preview() -> Dict[str, Any]:
    with CAMERA_PREVIEW_LOCK:
        stopped_camera_id = terminate_camera_preview_locked()
    return {"ok": True, "stopped_camera_id": stopped_camera_id, "active": None}


@app.get("/api/cam1/state")
def get_cam1_state() -> Dict[str, Any]:
    record = store.read_camera_state(STATE_DB_FILE, "cam1")
    state = record if record is not None else default_state()
    state.setdefault("analytics_profile", "water-v1")
    state.setdefault("domain", "water")
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
async def post_cam1_state(metadata: str = Form(...), overlay: Optional[UploadFile] = File(None), authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    return await post_analytics_state("cam1", metadata, overlay, authorization)


@app.get("/api/cam1/events")
def get_cam1_events(limit: int = 50) -> Dict[str, Any]:
    return get_analytics_events("cam1", limit)


@app.post("/api/cam1/events")
async def post_cam1_event(metadata: str = Form(...), snapshot: Optional[UploadFile] = File(None), authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    return await post_analytics_event("cam1", metadata, snapshot, authorization)


@app.get("/api/cam1/passages")
def get_cam1_passages(limit: int = 50) -> Dict[str, Any]:
    passages = list_water_passages(limit)
    return {"ok": True, "camera_id": "cam1", "count": len(passages), "passages": passages}


@app.post("/api/cam1/passages")
async def post_cam1_passage(
    metadata: str = Form(...),
    snapshot: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    require_auth(authorization)
    try:
        payload = json.loads(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="metadata must be a JSON object")
    snapshot_bytes = await snapshot.read() if snapshot is not None else None
    try:
        passage = upsert_water_passage(payload, snapshot_bytes=snapshot_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc
    try:
        persist_passage_object(passage)
    except Exception as error:
        print(f"passage registry mirror failed for {passage.get('passage_id')}: {error}", file=sys.stderr)
    sweep_events_media()
    return {"ok": True, "passage": passage}


@app.get("/api/cam1/objects")
def get_cam1_objects(
    limit: int = 50, offset: int = 0, date_from: Optional[str] = None, date_to: Optional[str] = None,
    class_name: Optional[str] = None, status: Optional[str] = None, speed_min: Optional[float] = None,
    speed_max: Optional[float] = None, search: Optional[str] = None, include_deleted: bool = False,
) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    if speed_min is not None and speed_min < 0:
        raise HTTPException(status_code=400, detail="speed_min must be >= 0")
    if speed_max is not None and speed_max < 0:
        raise HTTPException(status_code=400, detail="speed_max must be >= 0")
    if speed_min is not None and speed_max is not None and speed_min > speed_max:
        raise HTTPException(status_code=400, detail="speed_min must be <= speed_max")
    where_sql, values = build_objects_where(date_from, date_to, class_name, status, speed_min, speed_max, search, include_deleted)
    with open_objects_db() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM objects WHERE {where_sql}", values).fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM objects WHERE {where_sql} ORDER BY detected_at DESC, object_id DESC LIMIT ? OFFSET ?",
            [*values, limit, offset],
        ).fetchall()
    return {"ok": True, "camera_id": "cam1", "count": len(rows), "total": total, "limit": limit, "offset": offset,
            "objects": [object_row_to_dict(row) for row in rows]}


@app.get("/api/cam1/objects/{object_id}")
def get_cam1_object(object_id: str) -> Dict[str, Any]:
    with open_objects_db() as connection:
        row = connection.execute("SELECT * FROM objects WHERE object_id = ? AND camera_id = ? AND deleted_at IS NULL", (object_id, "cam1")).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return {"ok": True, "object": object_row_to_dict(row, include_original=True)}


@app.patch("/api/cam1/objects/{object_id}")
def patch_cam1_object(object_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return patch_object_record(object_id, payload, "cam1")


@app.delete("/api/cam1/objects/{object_id}")
def delete_cam1_object(object_id: str) -> Dict[str, Any]:
    return delete_object_record(object_id, "cam1")


@app.get("/api/cam1/roi")
def get_cam1_roi() -> Dict[str, Any]:
    return get_analytics_roi("cam1")


@app.post("/api/cam1/roi")
def post_cam1_roi(payload: Dict[str, Any]) -> Dict[str, Any]:
    return post_analytics_roi("cam1", payload)


@app.get("/api/cam1/speed-config")
def get_cam1_speed_config() -> Dict[str, Any]:
    return get_analytics_speed_config("cam1")


@app.post("/api/cam1/speed-config")
def post_cam1_speed_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    return post_analytics_speed_config("cam1", payload)


@app.get("/api/cam1/speed-lines")
def get_cam1_speed_lines() -> Dict[str, Any]:
    return get_analytics_speed_lines("cam1")


@app.post("/api/cam1/speed-lines")
def post_cam1_speed_lines(payload: Dict[str, Any]) -> Dict[str, Any]:
    return post_analytics_speed_lines("cam1", payload)


@app.get("/api/cam1/crossing-line")
def get_cam1_crossing_line() -> Dict[str, Any]:
    return get_analytics_crossing_line("cam1")


@app.post("/api/cam1/crossing-line")
def post_cam1_crossing_line(payload: Dict[str, Any]) -> Dict[str, Any]:
    return post_analytics_crossing_line("cam1", payload)


@app.post("/api/cam1/crossings")
async def post_cam1_crossing(
    metadata: str = Form(...),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return await api_post_crossing("cam1", metadata=metadata, authorization=authorization)


@app.get("/api/cam1/crossings/summary")
def get_cam1_crossings_summary(
    hours: int = 24, date_from: Optional[str] = None, date_to: Optional[str] = None,
) -> Dict[str, Any]:
    return get_analytics_crossings_summary("cam1", hours, date_from, date_to)


@app.get("/api/analytics/{camera_id}/state")
def get_analytics_state(camera_id: str) -> Dict[str, Any]:
    return analytics_state(camera_id)


@app.post("/api/analytics/{camera_id}/state")
async def post_analytics_state(
    camera_id: str,
    metadata: str = Form(...),
    overlay: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    require_auth(authorization)
    identity = analytics_identity(camera_id)
    try:
        data = json.loads(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON")
    data["camera_id"] = camera_id
    data["analytics_profile"] = identity["analytics_profile"]
    data["domain"] = identity["domain"]
    data.setdefault("state_schema", WORKER_STATE_SCHEMA)
    data.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    data.setdefault("worker_source_commit", None)
    data["updated_at"] = now_iso()
    data["worker_online"] = True
    if overlay is not None:
        overlay_path = OVERLAY_DIR / f"{camera_id}_latest_overlay.jpg"
        overlay_bytes = await overlay.read()
        # atomic replace to avoid readers seeing partial JPEG
        overlay_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = overlay_path.with_suffix(".tmp")
        tmp_path.write_bytes(overlay_bytes)
        os.replace(tmp_path, overlay_path)
        data["last_overlay_url"] = f"/sea-speed/media/overlays/{camera_id}_latest_overlay.jpg"
        # ensure overlay_rev bound to frame_no if not already
        if data.get("overlay_rev") is None:
            try:
                data["overlay_rev"] = int(data.get("frame_no", 0))
            except Exception:
                data["overlay_rev"] = 0
    else:
        old_state = store.read_camera_state(STATE_DB_FILE, camera_id)
        if old_state is None:
            old_state = analytics_default_state(camera_id)
        data["last_overlay_url"] = old_state.get("last_overlay_url")
        if data.get("overlay_rev") is None:
            data["overlay_rev"] = old_state.get("overlay_rev", old_state.get("frame_no", 0))
    store.upsert_camera_state(STATE_DB_FILE, camera_id, data)
    return {"ok": True, "state": data}


@app.get("/api/analytics/{camera_id}/events")
def get_analytics_events(camera_id: str, limit: int = 50) -> Dict[str, Any]:
    analytics_identity(camera_id)
    events = store.read_events(STATE_DB_FILE, camera_id)
    events = events[: max(1, min(limit, 200))]
    return {"ok": True, "camera_id": camera_id, "count": len(events), "events": events}


@app.post("/api/analytics/{camera_id}/events")
async def post_analytics_event(
    camera_id: str,
    metadata: str = Form(...),
    snapshot: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    require_auth(authorization)
    identity = analytics_identity(camera_id)
    try:
        event = json.loads(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON")
    event_id = str(event.get("event_id") or uuid.uuid4())
    event["event_id"] = event_id
    event["camera_id"] = camera_id
    event["analytics_profile"] = identity["analytics_profile"]
    event["domain"] = identity["domain"]
    person_blocked = (
        identity["domain"] == "road"
        and str(event.get("object_type") or "").strip().lower() == "person"
    )
    if person_blocked:
        return {"ok": True, "event": None}
    event.setdefault("object_type", event.get("class_name") or event.get("class") or "object")
    event.setdefault("model_class", event.get("class_name") or event.get("class") or "object")
    event.setdefault("event_schema", VEHICLE_EVENT_SCHEMA)
    event.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    event.setdefault("worker_source_commit", None)
    event.setdefault("calibration_version", None)
    event["created_at"] = event.get("created_at") or now_iso()
    if snapshot is None:
        raise HTTPException(status_code=422, detail="snapshot is required")
    filename = f"{camera_id}-{event_id}.jpg"
    snapshot_path = EVENTS_MEDIA_DIR / filename
    snapshot_path.write_bytes(await snapshot.read())
    event["snapshot_url"] = f"/sea-speed/media/events/{filename}"
    if not persist_object_event(event):
        raise HTTPException(status_code=422, detail="snapshot is required")
    sweep_events_media()
    store.append_event(STATE_DB_FILE, camera_id, event, EVENTS_FEED_LIMIT)
    return {"ok": True, "event": event}


@app.get("/api/analytics/{camera_id}/roi")
def get_analytics_roi(camera_id: str) -> Dict[str, Any]:
    analytics_identity(camera_id)
    default_roi = {"ok": True, "camera_id": camera_id, "enabled": False, "polygon": [], "polygon_norm": [], "reference_width": DEFAULT_ROI_REF_W, "reference_height": DEFAULT_ROI_REF_H, "updated_at": None}
    roi_path = analytics_data_file(camera_id, "roi")
    if roi_path.exists():
        try:
            roi = json.loads(roi_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=500, detail="ROI storage is corrupted") from exc
        if not isinstance(roi, dict):
            raise HTTPException(status_code=500, detail="ROI storage is corrupted")
    else:
        roi = dict(default_roi)
    roi["ok"] = True
    roi["camera_id"] = camera_id
    roi.setdefault("enabled", False)
    roi.setdefault("updated_at", None)
    # migrate legacy absolute polygon to normalized if needed
    if roi.get("polygon_norm") is None or not isinstance(roi.get("polygon_norm"), list) or not roi.get("polygon_norm"):
        legacy = clean_points_list(roi.get("polygon", []), max_points=1000)
        if legacy:
            norm, ref_w, ref_h = _normalize_legacy_polygon(legacy, roi)
            roi["polygon_norm"] = norm
            roi["reference_width"] = ref_w
            roi["reference_height"] = ref_h
            # keep legacy polygon but also ensure denormalized to default for compat
            roi["polygon"] = _denormalize_to_absolute(norm, DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
            write_json_file(analytics_data_file(camera_id, "roi"), {k: v for k, v in roi.items() if k not in ("ok", "camera_id")})
        else:
            roi.setdefault("polygon_norm", [])
            roi.setdefault("reference_width", DEFAULT_ROI_REF_W)
            roi.setdefault("reference_height", DEFAULT_ROI_REF_H)
            roi.setdefault("polygon", [])
    else:
        # ensure polygon absolute is in sync with norm for legacy clients
        norm = _clean_norm_points(roi.get("polygon_norm"), max_points=1000)
        ref_w = int(roi.get("reference_width", DEFAULT_ROI_REF_W))
        ref_h = int(roi.get("reference_height", DEFAULT_ROI_REF_H))
        roi["polygon_norm"] = norm
        roi["reference_width"] = ref_w
        roi["reference_height"] = ref_h
        roi["polygon"] = _denormalize_to_absolute(norm, DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    return roi


@app.post("/api/analytics/{camera_id}/roi")
def post_analytics_roi(camera_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    analytics_identity(camera_id)
    enabled = bool(payload.get("enabled", True))
    # accept either normalized or legacy
    norm = _clean_norm_points(payload.get("polygon_norm") or payload.get("polygon") or [], max_points=1000)
    if norm:
        ref_w = int(payload.get("reference_width") or payload.get("referenceWidth") or DEFAULT_ROI_REF_W)
        ref_h = int(payload.get("reference_height") or payload.get("referenceHeight") or DEFAULT_ROI_REF_H)
        polygon_norm = norm
    else:
        legacy = clean_points_list(payload.get("polygon", []), max_points=1000)
        if enabled and len(legacy) < 3:
            raise HTTPException(status_code=400, detail="ROI polygon must contain at least 3 points")
        if legacy:
            polygon_norm, ref_w, ref_h = _normalize_legacy_polygon(legacy, payload)
        else:
            polygon_norm, ref_w, ref_h = [], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H
            if enabled:
                raise HTTPException(status_code=400, detail="ROI polygon must contain at least 3 points")
    if enabled and len(polygon_norm) < 3:
        raise HTTPException(status_code=400, detail="ROI polygon must contain at least 3 points")
    polygon = _denormalize_to_absolute(polygon_norm, DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    roi = {"ok": True, "camera_id": camera_id, "enabled": enabled, "polygon": polygon, "polygon_norm": polygon_norm, "reference_width": ref_w, "reference_height": ref_h, "updated_at": now_iso()}
    write_json_file(analytics_data_file(camera_id, "roi"), {k: v for k, v in roi.items() if k not in ("ok", "camera_id")})
    return roi


@app.get("/api/analytics/{camera_id}/speed-config")
def get_analytics_speed_config(camera_id: str) -> Dict[str, Any]:
    analytics_identity(camera_id)
    default_config = {"ok": True, "camera_id": camera_id, "enabled": False, "kmh_per_px_s": 0.0, "updated_at": None}
    try:
        config = read_json_file(analytics_data_file(camera_id, "speed_config"), default_config)
    except store.JSON_READ_ERRORS as exc:
        raise HTTPException(status_code=500, detail="speed-config storage is corrupted") from exc
    config["ok"] = True
    config["camera_id"] = camera_id
    config.setdefault("enabled", False)
    config.setdefault("kmh_per_px_s", 0.0)
    config.setdefault("updated_at", None)
    return config


@app.post("/api/analytics/{camera_id}/speed-config")
def post_analytics_speed_config(camera_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    analytics_identity(camera_id)
    enabled = bool(payload.get("enabled", True))
    try:
        kmh_per_px_s = float(payload.get("kmh_per_px_s", 0.0))
    except Exception:
        raise HTTPException(status_code=400, detail="kmh_per_px_s must be a number")
    if kmh_per_px_s < 0:
        raise HTTPException(status_code=400, detail="kmh_per_px_s must be >= 0")
    config = {"ok": True, "camera_id": camera_id, "enabled": enabled and kmh_per_px_s > 0,
              "kmh_per_px_s": kmh_per_px_s, "updated_at": now_iso()}
    write_json_file(analytics_data_file(camera_id, "speed_config"), config)
    return config


@app.get("/api/analytics/{camera_id}/speed-lines")
def get_analytics_speed_lines(camera_id: str) -> Dict[str, Any]:
    analytics_identity(camera_id)
    default_config = {"ok": True, "camera_id": camera_id, "enabled": False, "distance_m": 57.0,
                      "line_a": [], "line_b": [], "line_a_norm": [], "line_b_norm": [], "reference_width": DEFAULT_ROI_REF_W, "reference_height": DEFAULT_ROI_REF_H, "updated_at": None}
    try:
        config = read_json_file(analytics_data_file(camera_id, "speed_lines"), default_config)
    except store.JSON_READ_ERRORS as exc:
        raise HTTPException(status_code=500, detail="speed-lines storage is corrupted") from exc
    config["ok"] = True
    config["camera_id"] = camera_id
    config.setdefault("enabled", False)
    config.setdefault("distance_m", 57.0)
    config.setdefault("updated_at", None)
    # migrate legacy
    if not config.get("line_a_norm") or not config.get("line_b_norm"):
        la = clean_points_list(config.get("line_a", []), max_points=2)
        lb = clean_points_list(config.get("line_b", []), max_points=2)
        if la and lb:
            ref_w, ref_h = _infer_legacy_ref_w_h(la + lb)
            ref_w = int(config.get("reference_width", ref_w))
            ref_h = int(config.get("reference_height", ref_h))
            config["line_a_norm"] = _normalize_from_absolute(la, ref_w, ref_h)
            config["line_b_norm"] = _normalize_from_absolute(lb, ref_w, ref_h)
            config["reference_width"] = ref_w
            config["reference_height"] = ref_h
            config["line_a"] = _denormalize_to_absolute(config["line_a_norm"], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
            config["line_b"] = _denormalize_to_absolute(config["line_b_norm"], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
            write_json_file(analytics_data_file(camera_id, "speed_lines"), {k: v for k, v in config.items() if k not in ("ok", "camera_id")})
        else:
            config.setdefault("line_a", [])
            config.setdefault("line_b", [])
            config.setdefault("line_a_norm", [])
            config.setdefault("line_b_norm", [])
            config.setdefault("reference_width", DEFAULT_ROI_REF_W)
            config.setdefault("reference_height", DEFAULT_ROI_REF_H)
    else:
        # sync absolute for legacy clients
        ref_w = int(config.get("reference_width", DEFAULT_ROI_REF_W))
        ref_h = int(config.get("reference_height", DEFAULT_ROI_REF_H))
        config["line_a_norm"] = _clean_norm_points(config.get("line_a_norm"), max_points=2)
        config["line_b_norm"] = _clean_norm_points(config.get("line_b_norm"), max_points=2)
        config["line_a"] = _denormalize_to_absolute(config["line_a_norm"], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
        config["line_b"] = _denormalize_to_absolute(config["line_b_norm"], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    return config


@app.post("/api/analytics/{camera_id}/speed-lines")
def post_analytics_speed_lines(camera_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    analytics_identity(camera_id)
    try:
        distance_m = float(payload.get("distance_m", 57.0))
    except Exception:
        raise HTTPException(status_code=400, detail="distance_m must be a number")
    if distance_m <= 0:
        raise HTTPException(status_code=400, detail="distance_m must be > 0")
    enabled = bool(payload.get("enabled", True))
    # accept normalized first
    la_norm = _clean_norm_points(payload.get("line_a_norm") or payload.get("line_a") or [], max_points=2)
    lb_norm = _clean_norm_points(payload.get("line_b_norm") or payload.get("line_b") or [], max_points=2)
    if la_norm and lb_norm:
        ref_w = int(payload.get("reference_width") or payload.get("referenceWidth") or DEFAULT_ROI_REF_W)
        ref_h = int(payload.get("reference_height") or payload.get("referenceHeight") or DEFAULT_ROI_REF_H)
    else:
        la = clean_points_list(payload.get("line_a"), max_points=2)
        lb = clean_points_list(payload.get("line_b"), max_points=2)
        if enabled and (len(la) != 2 or len(lb) != 2):
            raise HTTPException(status_code=400, detail="line_a and line_b must contain exactly 2 points each")
        if la and lb:
            ref_w, ref_h = _infer_legacy_ref_w_h(la + lb)
            ref_w = int(payload.get("reference_width") or ref_w)
            ref_h = int(payload.get("reference_height") or ref_h)
            la_norm = _normalize_from_absolute(la, ref_w, ref_h)
            lb_norm = _normalize_from_absolute(lb, ref_w, ref_h)
        else:
            la_norm, lb_norm, ref_w, ref_h = [], [], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H
    if enabled and (len(la_norm) != 2 or len(lb_norm) != 2):
        raise HTTPException(status_code=400, detail="line_a and line_b must contain exactly 2 points each")
    line_a = _denormalize_to_absolute(la_norm, DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    line_b = _denormalize_to_absolute(lb_norm, DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    config = {"ok": True, "camera_id": camera_id, "enabled": enabled, "distance_m": distance_m,
              "line_a": line_a, "line_b": line_b, "line_a_norm": la_norm, "line_b_norm": lb_norm, "reference_width": ref_w, "reference_height": ref_h, "updated_at": now_iso()}
    write_json_file(analytics_data_file(camera_id, "speed_lines"), {k: v for k, v in config.items() if k not in ("ok", "camera_id")})
    return config


def get_analytics_crossing_line(camera_id: str) -> Dict[str, Any]:
    analytics_identity(camera_id)
    default_config = {"ok": True, "camera_id": camera_id, "enabled": False, "line": [], "line_norm": [], "reference_width": DEFAULT_ROI_REF_W, "reference_height": DEFAULT_ROI_REF_H, "updated_at": None}
    try:
        config = read_json_file(analytics_data_file(camera_id, "crossing_line"), default_config)
    except store.JSON_READ_ERRORS as exc:
        raise HTTPException(status_code=500, detail="crossing-line storage is corrupted") from exc
    config["ok"] = True
    config["camera_id"] = camera_id
    config.setdefault("enabled", False)
    config.setdefault("updated_at", None)
    if not config.get("line_norm"):
        legacy = clean_points_list(config.get("line", []), max_points=2)
        if legacy:
            ref_w, ref_h = _infer_legacy_ref_w_h(legacy)
            ref_w = int(config.get("reference_width", ref_w))
            ref_h = int(config.get("reference_height", ref_h))
            config["line_norm"] = _normalize_from_absolute(legacy, ref_w, ref_h)
            config["reference_width"] = ref_w
            config["reference_height"] = ref_h
            config["line"] = _denormalize_to_absolute(config["line_norm"], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
            write_json_file(analytics_data_file(camera_id, "crossing_line"), {k: v for k, v in config.items() if k not in ("ok", "camera_id")})
        else:
            config.setdefault("line", [])
            config.setdefault("line_norm", [])
            config.setdefault("reference_width", DEFAULT_ROI_REF_W)
            config.setdefault("reference_height", DEFAULT_ROI_REF_H)
    else:
        ref_w = int(config.get("reference_width", DEFAULT_ROI_REF_W))
        ref_h = int(config.get("reference_height", DEFAULT_ROI_REF_H))
        config["line_norm"] = _clean_norm_points(config.get("line_norm"), max_points=2)
        config["line"] = _denormalize_to_absolute(config["line_norm"], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    return config


def post_analytics_crossing_line(camera_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    analytics_identity(camera_id)
    enabled = bool(payload.get("enabled", True))
    norm = _clean_norm_points(payload.get("line_norm") or payload.get("line") or [], max_points=2)
    if norm:
        ref_w = int(payload.get("reference_width") or payload.get("referenceWidth") or DEFAULT_ROI_REF_W)
        ref_h = int(payload.get("reference_height") or payload.get("referenceHeight") or DEFAULT_ROI_REF_H)
        line_norm = norm
    else:
        legacy = clean_points_list(payload.get("line"), max_points=2)
        if enabled and len(legacy) != 2:
            raise HTTPException(status_code=400, detail="line must contain exactly 2 points")
        if legacy:
            ref_w, ref_h = _infer_legacy_ref_w_h(legacy)
            ref_w = int(payload.get("reference_width") or ref_w)
            ref_h = int(payload.get("reference_height") or ref_h)
            line_norm = _normalize_from_absolute(legacy, ref_w, ref_h)
        else:
            line_norm, ref_w, ref_h = [], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H
            if enabled:
                raise HTTPException(status_code=400, detail="line must contain exactly 2 points")
    if enabled and len(line_norm) != 2:
        raise HTTPException(status_code=400, detail="line must contain exactly 2 points")
    line = _denormalize_to_absolute(line_norm, DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    config = {"ok": True, "camera_id": camera_id, "enabled": enabled,
              "line": line, "line_norm": line_norm, "reference_width": ref_w, "reference_height": ref_h, "updated_at": now_iso()}
    write_json_file(analytics_data_file(camera_id, "crossing_line"), {k: v for k, v in config.items() if k not in ("ok", "camera_id")})
    return config


CROSSING_DIRECTIONS = ("left_to_right", "right_to_left")


def append_crossing_record(camera_id: str, record: Dict[str, Any]) -> None:
    store.append_crossing(STATE_DB_FILE, camera_id, record, CROSSINGS_STORE_LIMIT)


def post_analytics_crossing(camera_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    identity = analytics_identity(camera_id)
    direction = str(data.get("direction") or "")
    if direction not in CROSSING_DIRECTIONS:
        raise HTTPException(status_code=400, detail="direction must be left_to_right or right_to_left")
    object_type = str(data.get("object_type") or data.get("class_name") or "").strip()
    if not object_type:
        raise HTTPException(status_code=400, detail="object_type is required")
    event_id = str(data.get("event_id") or f"{int(time.time())}-{uuid.uuid4().hex[:8]}")
    created_at = str(data.get("created_at") or now_iso())
    track_id = optional_int(data.get("track_id"))
    record = {
        "event_id": event_id,
        "camera_id": camera_id,
        "analytics_profile": identity["analytics_profile"],
        "domain": identity["domain"],
        "object_type": object_type,
        "class_name": object_type,
        "model_class": str(data.get("model_class") or object_type),
        "direction": direction,
        "track_id": track_id,
        "confidence": optional_float(data.get("confidence")),
        "speed_kmh": optional_float(data.get("speed_kmh")),
        "kind": "line_crossing",
        "created_at": created_at,
    }
    # Road-domain person crossings feed counters/summary only; the objects
    # registry and the event feed remain person-free (Issue #263 contract).
    if not (identity["domain"] == "road" and object_type == "person"):
        persist_object_event(record)
    append_crossing_record(camera_id, record)
    return {"ok": True, "event_id": event_id}


VLZ_TIMEZONE = timezone(timedelta(hours=10))


def _vlz_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time()).replace(tzinfo=VLZ_TIMEZONE)
    return start, start + timedelta(days=1)


def get_analytics_crossings_summary(
    camera_id: str, hours: int = 24,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
) -> Dict[str, Any]:
    identity = analytics_identity(camera_id)
    records = store.read_crossings(STATE_DB_FILE, camera_id)
    window: Dict[str, Any] = {"mode": "rolling_hours", "hours": max(1, min(int(hours), 168))}
    if date_from or date_to:
        try:
            from_day = date.fromisoformat(date_from) if date_from else None
            to_day = date.fromisoformat(date_to) if date_to else None
        except ValueError:
            raise HTTPException(status_code=400, detail="dates must be YYYY-MM-DD")
        if from_day and to_day and from_day > to_day:
            raise HTTPException(status_code=400, detail="date_from must not exceed date_to")
        start = _vlz_day_bounds(from_day)[0] if from_day else datetime.min.replace(tzinfo=timezone.utc)
        end = _vlz_day_bounds(to_day)[1] if to_day else datetime.max.replace(tzinfo=timezone.utc)
        window = {"mode": "vlz_days", "date_from": str(from_day) if from_day else None,
                  "date_to": str(to_day) if to_day else None}
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window["hours"])
    totals = {"left_to_right": 0, "right_to_left": 0}
    by_class: Dict[str, Dict[str, int]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        created_at = str(record.get("created_at") or "")
        try:
            moment = datetime.fromisoformat(created_at)
        except ValueError:
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        if window["mode"] == "vlz_days":
            if moment < start or moment >= end:
                continue
        elif moment < cutoff:
            continue
        direction = str(record.get("direction") or "")
        if direction not in CROSSING_DIRECTIONS:
            continue
        class_name = str(record.get("object_type") or record.get("class_name") or "object")
        totals[direction] += 1
        class_counts = by_class.setdefault(class_name, {"left_to_right": 0, "right_to_left": 0})
        class_counts[direction] += 1
    return {
        "ok": True,
        "camera_id": camera_id,
        "domain": identity["domain"],
        "window": window,
        "totals": totals,
        "by_class": by_class,
        "generated_at": now_iso(),
    }


@app.get("/api/analytics/{camera_id}/crossing-line")
def api_get_crossing_line(camera_id: str) -> Dict[str, Any]:
    return get_analytics_crossing_line(camera_id)


@app.post("/api/analytics/{camera_id}/crossing-line")
def api_post_crossing_line(camera_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return post_analytics_crossing_line(camera_id, payload)


@app.post("/api/analytics/{camera_id}/crossings")
async def api_post_crossing(
    camera_id: str,
    metadata: str = Form(...),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    require_auth(authorization)
    try:
        data = json.loads(metadata)
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="metadata must be valid JSON")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="metadata must be a JSON object")
    return post_analytics_crossing(camera_id, data)


@app.get("/api/analytics/{camera_id}/crossings/summary")
def api_get_crossings_summary(
    camera_id: str, hours: int = 24,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
) -> Dict[str, Any]:
    return get_analytics_crossings_summary(camera_id, hours, date_from, date_to)


@app.get("/api/analytics/{camera_id}/objects")
def get_analytics_objects(
    camera_id: str, limit: int = 50, offset: int = 0, date_from: Optional[str] = None,
    date_to: Optional[str] = None, class_name: Optional[str] = None, status: Optional[str] = None,
    speed_min: Optional[float] = None, speed_max: Optional[float] = None, search: Optional[str] = None,
    include_deleted: bool = False, object_type: Optional[str] = None,
) -> Dict[str, Any]:
    identity = analytics_identity(camera_id)
    return get_objects(limit, offset, date_from, date_to, class_name, status, speed_min, speed_max, search,
                       include_deleted, camera_id, identity["domain"], identity["analytics_profile"], object_type)


@app.get("/api/objects")
def get_objects(
    limit: int = 50, offset: int = 0, date_from: Optional[str] = None, date_to: Optional[str] = None,
    class_name: Optional[str] = None, status: Optional[str] = None, speed_min: Optional[float] = None,
    speed_max: Optional[float] = None, search: Optional[str] = None, include_deleted: bool = False,
    camera_id: Optional[str] = None, domain: Optional[str] = None, analytics_profile: Optional[str] = None,
    object_type: Optional[str] = None,
) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    if camera_id:
        analytics_identity(camera_id)
    if speed_min is not None and speed_min < 0:
        raise HTTPException(status_code=400, detail="speed_min must be >= 0")
    if speed_max is not None and speed_max < 0:
        raise HTTPException(status_code=400, detail="speed_max must be >= 0")
    if speed_min is not None and speed_max is not None and speed_min > speed_max:
        raise HTTPException(status_code=400, detail="speed_min must be <= speed_max")
    where_sql, values = build_objects_where(
        date_from, date_to, class_name, status, speed_min, speed_max, search, include_deleted,
        camera_id, domain, analytics_profile, object_type,
    )
    with open_objects_db() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM objects WHERE {where_sql}", values).fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM objects WHERE {where_sql} ORDER BY detected_at DESC, object_id DESC LIMIT ? OFFSET ?",
            [*values, limit, offset],
        ).fetchall()
    return {"ok": True, "count": len(rows), "total": total, "limit": limit, "offset": offset,
            "objects": [object_row_to_dict(row) for row in rows]}


@app.get("/api/objects/{object_id}")
def get_object(object_id: str) -> Dict[str, Any]:
    with open_objects_db() as connection:
        row = connection.execute("SELECT * FROM objects WHERE object_id = ? AND deleted_at IS NULL", (object_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return {"ok": True, "object": object_row_to_dict(row, include_original=True)}


@app.patch("/api/objects/{object_id}")
def patch_object(object_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return patch_object_record(object_id, payload)


@app.delete("/api/objects/{object_id}")
def delete_object(object_id: str) -> Dict[str, Any]:
    return delete_object_record(object_id)


@app.get("/api/worker/control")
def get_worker_control(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("GET", "/v1/status")
    payload["requested_by"] = username
    return payload


@app.post("/api/worker/control/start")
def start_worker_control(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("POST", "/v1/start")
    payload["requested_by"] = username
    return payload


@app.post("/api/worker/control/stop")
def stop_worker_control(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("POST", "/v1/stop")
    payload["requested_by"] = username
    return payload


@app.get("/api/worker/control/road1")
def get_road_worker_control(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("GET", "/v1/road1/status")
    payload["requested_by"] = username
    return payload


@app.post("/api/worker/control/road1/start")
def start_road_worker_control(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("POST", "/v1/road1/start")
    payload["requested_by"] = username
    return payload


@app.post("/api/worker/control/road1/stop")
def stop_road_worker_control(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("POST", "/v1/road1/stop")
    payload["requested_by"] = username
    return payload


@app.get("/api/session")
def get_session_identity(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = (x_authentik_username or "").strip()
    if not username:
        raise HTTPException(status_code=503, detail="Trusted Authentik identity is unavailable")
    return {"ok": True, "username": username}


ROAD_LIVE_MAX = 120
ROAD_LIVE: deque = deque(maxlen=ROAD_LIVE_MAX)
ROAD_LIVE_SEQ = 0
ROAD_LIVE_LOCK = threading.Lock()

def _validate_road_live_envelope(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="live envelope must be object")
    if payload.get("schema") not in {"sea_speed_road_live_v1", "sea_speed_road_live_v2"}:
        raise HTTPException(status_code=400, detail="schema must be sea_speed_road_live_v1/v2")
    if payload.get("camera_id") != "road1":
        raise HTTPException(status_code=400, detail="camera_id must be road1")
    if payload.get("analytics_profile") != "road-v1":
        raise HTTPException(status_code=400, detail="analytics_profile must be road-v1")
    if payload.get("domain") != "road":
        raise HTTPException(status_code=400, detail="domain must be road")
    for field in ("frame_no", "generation", "frame_width", "frame_height"):
        if not isinstance(payload.get(field), int):
            raise HTTPException(status_code=400, detail=f"{field} must be int")
    # v2 timing contract
    if payload.get("schema") == "sea_speed_road_live_v2":
        for field in ("capture_time_unix_ms", "processed_time_unix_ms"):
            if not isinstance(payload.get(field), int):
                raise HTTPException(status_code=400, detail=f"{field} must be int")
        if payload.get("timestamp_semantics") != "worker_receive_utc":
            raise HTTPException(status_code=400, detail="timestamp_semantics must be worker_receive_utc")
    else:
        if not isinstance(payload.get("observed_mono"), (int, float)):
            raise HTTPException(status_code=400, detail="observed_mono must be number")
    detections = payload.get("detections")
    if not isinstance(detections, list):
        raise HTTPException(status_code=400, detail="detections must be list")
    if len(detections) > 64:
        raise HTTPException(status_code=400, detail="too many detections")
    for det in detections:
        if not isinstance(det, dict):
            raise HTTPException(status_code=400, detail="detection must be object")
        for coord in ("x1_norm", "y1_norm", "x2_norm", "y2_norm"):
            val = det.get(coord)
            if not isinstance(val, (int, float)) or not (0.0 <= float(val) <= 1.0):
                raise HTTPException(status_code=400, detail=f"{coord} must be 0..1")
        try:
            if float(det.get("x2_norm")) <= float(det.get("x1_norm")) or float(det.get("y2_norm")) <= float(det.get("y1_norm")):
                raise HTTPException(status_code=400, detail="invalid box")
        except Exception:
            raise HTTPException(status_code=400, detail="invalid box")
    if payload.get("crossings") is not None and not isinstance(payload.get("crossings"), dict):
        raise HTTPException(status_code=400, detail="crossings must be object")
    # size guard
    try:
        raw = json.dumps(payload, ensure_ascii=False)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")
    if len(raw) > 64 * 1024:
        raise HTTPException(status_code=400, detail="payload too large")
    return payload

@app.post("/api/analytics/road1/live")
async def post_road_live(payload: Dict[str, Any], authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    require_auth(authorization)
    env = _validate_road_live_envelope(payload)
    # deep copy and enrich with server receipt
    import copy as _copy
    stored = _copy.deepcopy(env)
    global ROAD_LIVE_SEQ
    with ROAD_LIVE_LOCK:
        ROAD_LIVE_SEQ += 1
        stored["_live_seq"] = ROAD_LIVE_SEQ
        stored["_received_at"] = datetime.now(timezone.utc).isoformat()
        ROAD_LIVE.append(stored)
        seq = ROAD_LIVE_SEQ
        queued = len(ROAD_LIVE)
    return {"ok": True, "queued": queued, "live_seq": seq}

@app.get("/api/analytics/road1/live")
def get_road_live(limit: int = 20) -> Dict[str, Any]:
    lim = max(1, min(int(limit), ROAD_LIVE_MAX))
    items = list(ROAD_LIVE)[-lim:]
    return {"camera_id": "road1", "items": items}

def _road_live_stream_gen(last_seq: int):
    import time as _time, json as _json
    yield "data: {}\n\n"
    cursor = last_seq
    while True:
        with ROAD_LIVE_LOCK:
            items = [e for e in list(ROAD_LIVE) if int(e.get("_live_seq", 0)) > cursor]
            if items:
                cursor = int(items[-1].get("_live_seq", cursor))
        if items:
            for env in items:
                yield f"id: {env.get('_live_seq')}\ndata: {_json.dumps(env, ensure_ascii=False)}\n\n"
        else:
            yield ": keepalive\n\n"
        _time.sleep(0.1)

@app.get("/api/analytics/road1/live/stream")
def road_live_stream_internal():
    with ROAD_LIVE_LOCK:
        last = ROAD_LIVE_SEQ
    return StreamingResponse(_road_live_stream_gen(last), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/sea-speed/api/analytics/road1/live/stream")
def road_live_stream():
    # public Authentik-protected alias — same sequence-aware stream
    with ROAD_LIVE_LOCK:
        last = ROAD_LIVE_SEQ
    return StreamingResponse(_road_live_stream_gen(last), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

WATER_LIVE_MAX = 120
WATER_LIVE: deque = deque(maxlen=WATER_LIVE_MAX)
WATER_LIVE_SEQ = 0
WATER_LIVE_LOCK = threading.Lock()

def _validate_water_live_envelope(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="live envelope must be object")
    if payload.get("schema") not in {"sea_speed_water_live_v1", "sea_speed_water_live_v2"}:
        raise HTTPException(status_code=400, detail="schema must be sea_speed_water_live_v1/v2")
    if payload.get("camera_id") != "cam1":
        raise HTTPException(status_code=400, detail="camera_id must be cam1")
    if payload.get("analytics_profile") != "water-v1":
        raise HTTPException(status_code=400, detail="analytics_profile must be water-v1")
    if payload.get("domain") != "water":
        raise HTTPException(status_code=400, detail="domain must be water")
    for field in ("frame_no", "generation", "frame_width", "frame_height"):
        if not isinstance(payload.get(field), int):
            raise HTTPException(status_code=400, detail=f"{field} must be int")
    if payload.get("schema") == "sea_speed_water_live_v2":
        for field in ("capture_time_unix_ms", "processed_time_unix_ms"):
            if not isinstance(payload.get(field), int):
                raise HTTPException(status_code=400, detail=f"{field} must be int")
        if payload.get("timestamp_semantics") != "worker_receive_utc":
            raise HTTPException(status_code=400, detail="timestamp_semantics must be worker_receive_utc")
    else:
        if not isinstance(payload.get("observed_mono"), (int, float)):
            raise HTTPException(status_code=400, detail="observed_mono must be number")
    detections = payload.get("detections")
    if not isinstance(detections, list):
        raise HTTPException(status_code=400, detail="detections must be list")
    if len(detections) > 64:
        raise HTTPException(status_code=400, detail="too many detections")
    for det in detections:
        if not isinstance(det, dict):
            raise HTTPException(status_code=400, detail="detection must be object")
        for coord in ("x1_norm", "y1_norm", "x2_norm", "y2_norm"):
            val = det.get(coord)
            if not isinstance(val, (int, float)) or not (0.0 <= float(val) <= 1.0):
                raise HTTPException(status_code=400, detail=f"{coord} must be 0..1")
        try:
            if float(det.get("x2_norm")) <= float(det.get("x1_norm")) or float(det.get("y2_norm")) <= float(det.get("y1_norm")):
                raise HTTPException(status_code=400, detail="invalid box")
        except Exception:
            raise HTTPException(status_code=400, detail="invalid box")
    if len(json.dumps(payload, ensure_ascii=False)) > 64 * 1024:
        raise HTTPException(status_code=400, detail="payload too large")
    return payload

@app.post("/api/cam1/live")
async def post_water_live(payload: Dict[str, Any], authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    require_auth(authorization)
    env = _validate_water_live_envelope(payload)
    import copy as _copy
    stored = _copy.deepcopy(env)
    global WATER_LIVE_SEQ
    with WATER_LIVE_LOCK:
        WATER_LIVE_SEQ += 1
        stored["_live_seq"] = WATER_LIVE_SEQ
        stored["_received_at"] = datetime.now(timezone.utc).isoformat()
        WATER_LIVE.append(stored)
        seq = WATER_LIVE_SEQ
        queued = len(WATER_LIVE)
    return {"ok": True, "queued": queued, "live_seq": seq}

@app.get("/api/cam1/live")
def get_water_live(limit: int = 20) -> Dict[str, Any]:
    lim = max(1, min(int(limit), WATER_LIVE_MAX))
    items = list(WATER_LIVE)[-lim:]
    return {"camera_id": "cam1", "items": items}

def _water_live_stream_gen(last_seq: int):
    import time as _time, json as _json
    yield "data: {}\n\n"
    cursor = last_seq
    while True:
        with WATER_LIVE_LOCK:
            items = [e for e in list(WATER_LIVE) if int(e.get("_live_seq", 0)) > cursor]
            if items:
                cursor = int(items[-1].get("_live_seq", cursor))
        if items:
            for env in items:
                yield f"id: {env.get('_live_seq')}\ndata: {_json.dumps(env, ensure_ascii=False)}\n\n"
        else:
            yield ": keepalive\n\n"
        _time.sleep(0.1)

@app.get("/api/cam1/live/stream")
def water_live_stream_internal():
    with WATER_LIVE_LOCK:
        last = WATER_LIVE_SEQ
    return StreamingResponse(_water_live_stream_gen(last), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/sea-speed/api/cam1/live/stream")
def water_live_stream():
    with WATER_LIVE_LOCK:
        last = WATER_LIVE_SEQ
    return StreamingResponse(_water_live_stream_gen(last), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "service": "sea-speed-api", "api_schema": API_SCHEMA,
            "source_commit": deployed_source_commit(), "time": now_iso()}
