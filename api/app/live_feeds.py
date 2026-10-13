"""Live-feed ring buffers and stream services for the Sea Speed API (issue #396, wave 6).

Extracted verbatim from ``api/app/main.py`` (base b9a956b9): the road (road1)
and water (cam1) live-feed ring buffers with their capacity constants and
threading locks, the live-envelope validators and the sequence-aware SSE
stream generators. The ``@app.*`` live routes stay in ``main.py`` (61-endpoint
route table frozen); they consume the moved state and services through the
wave-6 explicit re-export seam, so deque/lock object identity is shared —
one canonical instance per import mode.

State-closure decision (wave-6 contract hazard): the ring buffers, locks,
capacity constants, validators and generators are slice-exclusive and move
with the slice. The per-camera sequence counters (``ROAD_LIVE_SEQ``,
``WATER_LIVE_SEQ``) stay in ``main.py``: the staying route handlers increment
them via ``global`` statements, and a Python ``global`` rebinds the defining
module's namespace — moving the counters while keeping the routes
byte-identical would fork the counters per module namespace (duplicated
state). The generators deliberately never read the module-level counters
(they sequence off the per-envelope ``_live_seq`` field), so this split is
closure-clean. Do NOT "complete" the move by relocating the counters unless
the route handlers move with them.

No intra-package imports: the slice resolves only stdlib and
``fastapi.HTTPException``, so plain imports load identically in package
context (``api.app.live_feeds``) and direct-file loads (top-level
``live_feeds``) — no dual try/except idiom is needed and none is used.
"""

import json
import threading
from collections import deque
from typing import Any, Dict

from fastapi import HTTPException

__all__ = [
    "ROAD_LIVE_MAX",
    "ROAD_LIVE",
    "ROAD_LIVE_LOCK",
    "_validate_road_live_envelope",
    "_road_live_stream_gen",
    "WATER_LIVE_MAX",
    "WATER_LIVE",
    "WATER_LIVE_LOCK",
    "_validate_water_live_envelope",
    "_water_live_stream_gen",
]


ROAD_LIVE_MAX = 120
ROAD_LIVE: deque = deque(maxlen=ROAD_LIVE_MAX)
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


WATER_LIVE_MAX = 120
WATER_LIVE: deque = deque(maxlen=WATER_LIVE_MAX)
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
    # size guard
    try:
        raw = json.dumps(payload, ensure_ascii=False)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")
    if len(raw) > 64 * 1024:
        raise HTTPException(status_code=400, detail="payload too large")
    return payload


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
