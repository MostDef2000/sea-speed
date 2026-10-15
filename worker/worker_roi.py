"""Sea Speed worker ROI/analytics module (issue #397, wave 9).

The ROI family and the water-recall diagnostics moved VERBATIM
(move-only refactor, byte-identical bodies) from
hls_motion_yolo_worker_events.py: the water-recall diagnostic state
(_WATER_RECALL_DIAGNOSTIC_STATE, wave-8-era module-level literal) and
the nine ROI/analytics defs (road_roi_enabled, parse_road_roi_polygon,
roi_processing_signature, mask_frame_to_roi,
prepare_roi_processing_frame, detection_inside_road_roi,
filter_detections_by_roi, maybe_emit_water_recall_diagnostics,
draw_roi_polygon). Deliberate STAYS in the worker:
select_profile_detections (it calls the staying detect_vehicles and
filter_detections_by_motion alongside the moved
filter_detections_by_roi - moving it would create an import cycle) and
draw_speed_lines_overlay (render surface, no production callers); the
supervision main loop resolves the moved defs through the worker's
flat re-export.

Rebinder coupling: _roi_processing_points REBINDS via `global` +
assignment and moved WITH its sole rebinder - it is rebound ONLY
inside prepare_roi_processing_frame (the only `global` statement
naming it, the only non-literal Assign, and the reader
detection_inside_road_roi live in the SAME module): rebinder + state
+ reader are never split. The worker's re-export copy is a frozen
import-time snapshot, so no Load-context read of
_roi_processing_points may exist outside this module (guarded by
tests/test_worker_roi_module.py, the wave-7 idiom).

Object-identity coupling: _WATER_RECALL_DIAGNOSTIC_STATE is defined
here ONCE and re-exported BY IDENTITY - it is mutated IN PLACE only
(dict item assignment; the name is never rebound), so
maybe_emit_water_recall_diagnostics and any staying reader share ONE
state.

Import policy (guarded by tests/test_worker_roi_module.py): stdlib
json/time plus cv2/numpy ALLOWED here - this module OWNS the polygon
math and frame masking (unlike the wave-8 pure-Python tracking
sibling) - plus the repo siblings worker_kernel (bbox_center, the
env_* readers, water_recall_diagnostics_enabled) and worker_transport
(fetch_remote_roi). Acyclic: roi -> transport -> kernel.
"""

import json
import time

import cv2
import numpy as np

from worker_kernel import (
    bbox_center,
    env_float,
    env_int,
    env_str,
    water_recall_diagnostics_enabled,
)
from worker_transport import fetch_remote_roi


_WATER_RECALL_DIAGNOSTIC_STATE = {"last_emit_mono": 0.0}

_roi_processing_points = None


def road_roi_enabled():
    enabled, points = fetch_remote_roi()
    return enabled and len(points) >= 3


def parse_road_roi_polygon():
    enabled, points = fetch_remote_roi()
    if not enabled:
        return []
    return points


def roi_processing_signature(enabled, points):
    if not enabled or len(points) < 3:
        return "full-frame"
    normalized = tuple((int(x), int(y)) for x, y in points)
    return f"roi:{normalized}"


def mask_frame_to_roi(frame, points):
    if len(points) < 3:
        return frame
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    polygon = np.array(points, dtype=np.int32)
    cv2.fillPoly(mask, [polygon], 255)
    return cv2.bitwise_and(frame, frame, mask=mask)


def prepare_roi_processing_frame(frame, motion_detector):
    global _roi_processing_points
    enabled, points = fetch_remote_roi()
    points = list(points) if enabled and len(points) >= 3 else []
    signature = roi_processing_signature(bool(points), points)
    previous_signature = getattr(motion_detector, "_roi_processing_signature", None)
    if previous_signature != signature:
        motion_detector.prev = None
        motion_detector.active_until = 0.0
        motion_detector.last_boxes = []
        motion_detector.last_area = 0.0
        motion_detector._roi_processing_signature = signature
    _roi_processing_points = list(points)
    return mask_frame_to_roi(frame, points), points


def detection_inside_road_roi(det, points=None):
    if points is None:
        points = _roi_processing_points
    if points is None:
        points = parse_road_roi_polygon()
    if len(points) < 3:
        return True
    polygon = np.array(points, dtype=np.int32)
    cx, cy = bbox_center(det)
    return cv2.pointPolygonTest(polygon, (float(cx), float(cy)), False) >= 0


def filter_detections_by_roi(detections, points=None):
    return [det for det in detections if detection_inside_road_roi(det, points)]


def maybe_emit_water_recall_diagnostics(frame_no, raw_records, roi_points, accepted_detections, profile):
    if profile is None or profile.domain != "water" or not water_recall_diagnostics_enabled():
        return False
    now_mono = time.monotonic()
    interval_sec = max(1.0, env_float("WATER_RECALL_DIAGNOSTICS_INTERVAL_SEC", 10.0))
    if now_mono - float(_WATER_RECALL_DIAGNOSTIC_STATE.get("last_emit_mono", 0.0)) < interval_sec:
        return False
    _WATER_RECALL_DIAGNOSTIC_STATE["last_emit_mono"] = now_mono
    accepted_keys = {
        (det.get("track_id"), tuple(det.get("bbox_xyxy") or []), det.get("class_name"))
        for det in accepted_detections or []
    }
    max_records = max(1, min(50, env_int("WATER_RECALL_DIAGNOSTICS_MAX_RECORDS", 12)))
    records = []
    for raw in raw_records or []:
        record = dict(raw)
        if record.get("class_mapping_accepted"):
            probe = {
                "bbox_xyxy": list(record.get("bbox_xyxy") or []),
                "track_id": record.get("track_id"),
                "class_name": record.get("semantic_class"),
            }
            try:
                record["roi_center_inside"] = bool(detection_inside_road_roi(probe, roi_points))
            except Exception:
                record["roi_center_inside"] = None
            key = (record.get("track_id"), tuple(record.get("bbox_xyxy") or []), record.get("semantic_class"))
            record["accepted_after_roi"] = key in accepted_keys
        else:
            record["roi_center_inside"] = None
            record["accepted_after_roi"] = False
        records.append(record)
    payload = {
        "schema": "sea_speed_water_recall_diagnostic_v1",
        "frame_no": int(frame_no),
        "analytics_profile": profile.name,
        "detector": {
            "model_name": env_str("MODEL_NAME", profile.model_name),
            "image_size": env_int("YOLO_IMAGE_SIZE", profile.image_size),
            "confidence_threshold": env_float("YOLO_CONFIDENCE", profile.confidence),
            "tracker": env_str("YOLO_TRACKER", profile.tracker).strip() or profile.tracker,
        },
        "roi": {
            "enabled": len(roi_points or []) >= 3,
            "processing_mode": "masked_before_inference" if len(roi_points or []) >= 3 else "full_frame",
            "point_count": len(roi_points or []),
            "post_filter": "bbox_center",
        },
        "counts": {
            "post_threshold_raw": len(raw_records or []),
            "class_mapping_accepted": sum(1 for item in raw_records or [] if item.get("class_mapping_accepted")),
            "track_assigned": sum(1 for item in raw_records or [] if item.get("track_assigned")),
            "accepted_after_roi": len(accepted_detections or []),
        },
        "records_truncated": len(records) > max_records,
        "records": records[:max_records],
    }
    print("WATER_RECALL_DIAGNOSTIC " + json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
    return True


def draw_roi_polygon(frame):
    points = parse_road_roi_polygon()
    if len(points) < 3:
        return
    polygon = np.array(points, dtype=np.int32)
    cv2.polylines(frame, [polygon], True, (255, 0, 0), 2)
