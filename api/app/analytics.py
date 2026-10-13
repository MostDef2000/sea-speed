"""Analytics services for the Sea Speed API (issue #396, wave 5).

Functions extracted verbatim from ``api/app/main.py``: the events-media sweep
(``sweep_events_media`` with its grace/interval constants and the
``_events_sweep_state`` throttle record), the per-camera analytics state layer
(``default_state``, ``analytics_data_file``, ``analytics_default_state``,
``analytics_state``), the ROI/points normalization helpers wave 3 deferred to
this slice (``clean_points_list``, ``_is_normalized_point``,
``_clean_norm_points``, ``_infer_legacy_ref_w_h``, ``_normalize_from_absolute``,
``_denormalize_to_absolute``, ``_normalize_legacy_polygon`` plus the ROI
reference constants) and the crossing/passage record services
(``get_analytics_crossing_line``, ``post_analytics_crossing_line``,
``CROSSING_DIRECTIONS``, ``append_crossing_record``, ``post_analytics_crossing``,
``VLZ_TIMEZONE``, ``_vlz_day_bounds``, ``get_analytics_crossings_summary``).

Module-state decision (wave-5 contract hazard check): the ONLY mutable module
state in the slice is ``_events_sweep_state`` (the sweep throttle record) and
its exclusive consumer is ``sweep_events_media``, so it moved with the slice
under the wave-4 exclusive-state rule; no locks or deques live in the slice
(the road/water live-stream locks and deques stay in ``main.py``) and all
persistence goes through ``store`` (stateless JSON helpers plus the SQLite
state/event/crossing stores). The routes in ``main.py`` keep calling these
services through the wave-5 re-export seam, byte-identical. The wave-3-deferred
ROI helpers moved only after re-verifying that their remaining callers are
exclusively the analytics ROI / speed-lines / crossing-line handlers in
``main.py``. Same dual import idiom as the other ``api/app`` modules: one
canonical instance per import mode.
"""

import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

try:  # package context (api.app.analytics) and direct-file load both supported
    from . import config  # noqa: F401  # explicit re-export seam (issue #396 wave 5)
    from .config import (  # noqa: F401  # explicit re-export seam (issue #396 wave 5)
        CROSSINGS_STORE_LIMIT,
        DATA_DIR,
        EVENTS_FILE,
        EVENTS_MEDIA_DIR,
        ROI_FILE,
        SPEED_CONFIG_FILE,
        SPEED_LINES_FILE,
        STATE_DB_FILE,
        STATE_FILE,
        TELEMETRY_SCHEMA,
        WORKER_STATE_SCHEMA,
    )
    from . import identity  # noqa: F401  # explicit re-export seam (issue #396 wave 5)
    from .identity import analytics_identity, now_iso
    from . import objects_registry  # noqa: F401  # explicit re-export seam (issue #396 wave 5)
    from .objects_registry import (
        open_objects_db,
        optional_float,
        optional_int,
        persist_object_event,
    )
    from . import store  # noqa: F401  # explicit re-export seam (issue #396 wave 5)
    from .store import read_json_file, write_json_file
except ImportError:  # direct uvicorn app-dir / spec_from_file_location execution
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config  # noqa: F401  # explicit re-export seam (issue #396 wave 5)
    from config import (  # noqa: F401  # explicit re-export seam (issue #396 wave 5)
        CROSSINGS_STORE_LIMIT,
        DATA_DIR,
        EVENTS_FILE,
        EVENTS_MEDIA_DIR,
        ROI_FILE,
        SPEED_CONFIG_FILE,
        SPEED_LINES_FILE,
        STATE_DB_FILE,
        STATE_FILE,
        TELEMETRY_SCHEMA,
        WORKER_STATE_SCHEMA,
    )
    import identity  # noqa: F401  # explicit re-export seam (issue #396 wave 5)
    from identity import analytics_identity, now_iso
    import objects_registry  # noqa: F401  # explicit re-export seam (issue #396 wave 5)
    from objects_registry import (
        open_objects_db,
        optional_float,
        optional_int,
        persist_object_event,
    )
    import store  # noqa: F401  # explicit re-export seam (issue #396 wave 5)
    from store import read_json_file, write_json_file

__all__ = [
    "EVENTS_MEDIA_GRACE_SECONDS",
    "EVENTS_SWEEP_INTERVAL_SECONDS",
    "_events_sweep_state",
    "sweep_events_media",
    "default_state",
    "analytics_data_file",
    "analytics_default_state",
    "analytics_state",
    "clean_points_list",
    "DEFAULT_ROI_REF_W",
    "DEFAULT_ROI_REF_H",
    "LEGACY_ROI_W",
    "LEGACY_ROI_H",
    "_is_normalized_point",
    "_clean_norm_points",
    "_infer_legacy_ref_w_h",
    "_normalize_from_absolute",
    "_denormalize_to_absolute",
    "_normalize_legacy_polygon",
    "get_analytics_crossing_line",
    "post_analytics_crossing_line",
    "CROSSING_DIRECTIONS",
    "append_crossing_record",
    "post_analytics_crossing",
    "VLZ_TIMEZONE",
    "_vlz_day_bounds",
    "get_analytics_crossings_summary",
]

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
