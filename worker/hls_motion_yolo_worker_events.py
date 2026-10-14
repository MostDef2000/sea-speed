import json
import os
import time
import uuid
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from analytics_profiles import get_profile, normalize_model_class
from water_passage import PassageEngine, build_two_gate_estimator

try:
    from detection_performance import PerformanceTracker
except Exception:
    PerformanceTracker = None  # type: ignore[assignment]


# Issue #397 wave 1: pure helpers moved verbatim to worker_kernel.py
# (stdlib-only module). The re-export keeps main() global-name resolution
# and the test monkeypatch surface intact.
from worker_kernel import (  # noqa: F401
    bbox_center,
    crossed_line,
    env_float,
    env_int,
    env_str,
    format_detection_label,
    get_crossing_line_url,
    get_roi_url,
    get_speed_config_url,
    get_speed_lines_url,
    is_motion_gate_always_on,
    is_yolo_classes_filter_enabled,
    is_yolo_half_enabled,
    media_basic_auth_for_input,
    now_iso,
    overlay_label_opacity,
    roi_basic_auth,
    safe_media_input_label,
    side_of_line,
    sign_with_deadzone,
    water_recall_diagnostics_enabled,
    _media_input_scheme,
    _maybe_scale_legacy_absolute,
    _scale_norm_points,
)
# Issue #397 wave 2: media/reader layer moved verbatim to worker_media.py
# (cv2/subprocess-allowed module). The re-export keeps the supervision seam
# (worker.start_media_reader) and main() global-name resolution intact.
from worker_media import (  # noqa: F401
    FFmpegFrameReader,
    RtspFrameReader,
    _frame_time_seconds,
    _resolve_frame_size,
    read_exact,
    start_ffmpeg,
    start_media_reader,
)


# Issue #397 wave 3: cv2 render/snapshot layer moved verbatim to worker_render.py.
# The re-export keeps main() global-name resolution and the monkeypatch surface
# intact (per-module resolution: internal calls bind to the defining module).
from worker_render import (  # noqa: F401
    crop_sharpness,
    draw_overlay,
    write_passage_snapshot,
)

# Issue #397 wave 4: requests transport/posting layer moved verbatim to
# worker_transport.py. The re-export keeps main()/staying-caller global-name
# resolution and the ns-injection/monkeypatch surface intact (per-module
# resolution: internal calls bind to the defining module). The three TTL
# caches are re-exported as OBJECTS (identity, not copies): every access is
# an in-place mutation, so mover/staying reads stay coherent (wave-4 trio).
# Issue #397 wave 5: the crossing/speed-config posting surface joined the
# same transport module verbatim (fetch_speed_config + _speed_config_cache,
# post_crossing/flush_crossing_posts + _crossing_pending_posts,
# _post_live_envelope_sync). Same object-identity contract: the two moved
# state objects are re-exported as OBJECTS; staying mutators
# (update_crossing_counts/reset_crossing_counts) act through the SAME list.
from worker_transport import (  # noqa: F401
    _crossing_line_cache,
    _crossing_pending_posts,
    _post_live_envelope_sync,
    _roi_cache,
    _speed_config_cache,
    _speed_lines_cache,
    fetch_crossing_line_config,
    fetch_remote_roi,
    fetch_speed_config,
    fetch_speed_lines_config,
    flush_crossing_posts,
    post_crossing,
    post_event,
    post_passage,
    post_state,
)

# Issue #397 wave 6: the crossing-domain cluster moved verbatim to
# worker_crossings.py (crossing counters/track-sides/VLZ daily-reset state +
# the six crossing functions). The re-export keeps main()/staying-caller
# global-name resolution and the ns-injection/monkeypatch surface intact.
# Object-identity coupling: worker_crossings mutates the transport-owned
# _crossing_line_cache/_crossing_pending_posts objects IN PLACE (they are
# imported from worker_transport, not redefined), and _crossing_vlz_date
# moved WITH its sole rebinder maybe_reset_daily_crossings (never split).
# State names are NOT re-exported: the worker has zero staying readers.
from worker_crossings import (  # noqa: F401
    crossing_overlay_summary,
    maybe_reset_daily_crossings,
    prune_crossing_tracks,
    reset_crossing_counts,
    update_crossing_counts,
    vlz_date,
)

# Issue #397 wave 7: the live-publisher family moved verbatim to
# worker_live.py (the publish queue/lock/thread state + the publisher loop,
# its starter and the post entry point). The re-export keeps main()/
# staying-caller global-name resolution and the ns-injection/monkeypatch
# surface intact. Object-identity coupling: _LIVE_PUBLISH_QUEUE and
# _LIVE_PUBLISH_LOCK are defined ONCE in worker_live and re-exported BY
# IDENTITY (the worker never rebinds them); _LIVE_PUBLISH_THREAD is the one
# rebinding name - it is rebound ONLY inside _ensure_live_publisher, which
# moved WITH the state (never split).
from worker_live import (  # noqa: F401
    _LIVE_PUBLISH_LOCK,
    _LIVE_PUBLISH_QUEUE,
    _LIVE_PUBLISH_THREAD,
    _ensure_live_publisher,
    _live_publisher_loop,
    post_live_envelope,
)

# Issue #397 wave 8: the tracking cluster moved verbatim to
# worker_tracking.py (the per-track speed state + the speed estimators +
# the event-posting bookkeeping). The re-export keeps main()/staying-caller
# global-name resolution and the ns-injection/monkeypatch surface intact.
# Object-identity coupling: _speed_track/_track_states/_line_speed_state
# are defined ONCE in worker_tracking and re-exported BY IDENTITY (the
# worker never rebinds them - every access is an in-place mutation or a
# read of the same dicts; strict no-rebinding guards live in
# tests/test_worker_tracking_module.py).
from worker_tracking import (  # noqa: F401
    _line_speed_state,
    _speed_track,
    _track_states,
    convert_px_s_to_kmh,
    detection_center_px,
    mark_track_event_posted,
    prune_track_states,
    track_event_posted,
    update_speed_estimate,
    update_speed_lines_estimate,
    water_event_candidates,
)

ROAD_LIVE_SCHEMA = "sea_speed_road_live_v2"
ROAD_LIVE_GENERATION = int(time.time() * 1000)
WATER_LIVE_SCHEMA = "sea_speed_water_live_v2"
WATER_LIVE_GENERATION = int(time.time() * 1000)
_LAST_FRAME_CAPTURE_MS: int | None = None
_WATER_RECALL_DIAGNOSTIC_STATE = {"last_emit_mono": 0.0}

def build_road_live_envelope(frame_no: int, generation: int, observed_mono: float, detections, frame_w: int, frame_h: int, worker_commit: str, capture_time_unix_ms: int | None = None, processed_time_unix_ms: int | None = None):
    # normalized boxes, immutable — v2 carries honest worker-receive timestamps
    import copy
    boxes = []
    for d in detections or []:
        try:
            coords = d.get("bbox_xyxy")
            if not isinstance(coords, (list, tuple)) or len(coords) != 4:
                coords = [d.get("x1", 0), d.get("y1", 0), d.get("x2", 0), d.get("y2", 0)]
            x1, y1, x2, y2 = [float(value) for value in coords]
            x1 = min(1.0, max(0.0, x1 / max(1, frame_w)))
            y1 = min(1.0, max(0.0, y1 / max(1, frame_h)))
            x2 = min(1.0, max(0.0, x2 / max(1, frame_w)))
            y2 = min(1.0, max(0.0, y2 / max(1, frame_h)))
            if x2 <= x1 or y2 <= y1:
                continue
            boxes.append({"track_id": d.get("track_id"), "class_name": d.get("class_name"), "confidence": d.get("confidence"), "x1_norm": x1, "y1_norm": y1, "x2_norm": x2, "y2_norm": y2, "speed_kmh": d.get("speed_kmh")})
        except Exception:
            continue
    now_ms = int(time.time() * 1000)
    if capture_time_unix_ms is None:
        capture_time_unix_ms = now_ms
    if processed_time_unix_ms is None:
        processed_time_unix_ms = now_ms
    env = {"schema": ROAD_LIVE_SCHEMA, "camera_id": "road1", "analytics_profile": "road-v1", "domain": "road", "frame_no": int(frame_no), "generation": int(generation), "observed_mono": float(observed_mono), "capture_time_unix_ms": int(capture_time_unix_ms), "processed_time_unix_ms": int(processed_time_unix_ms), "timestamp_semantics": "worker_receive_utc", "frame_width": int(frame_w), "frame_height": int(frame_h), "worker_source_commit": worker_commit, "detections": boxes, "crossings": copy.deepcopy(crossing_overlay_summary()) if "crossing_overlay_summary" in globals() else {}}
    return copy.deepcopy(env)

def build_water_live_envelope(frame_no: int, generation: int, observed_mono: float, detections, frame_w: int, frame_h: int, worker_commit: str, capture_time_unix_ms: int | None = None, processed_time_unix_ms: int | None = None):
    import copy
    boxes = []
    for d in detections or []:
        try:
            coords = d.get("bbox_xyxy")
            if not isinstance(coords, (list, tuple)) or len(coords) != 4:
                coords = [d.get("x1", 0), d.get("y1", 0), d.get("x2", 0), d.get("y2", 0)]
            x1, y1, x2, y2 = [float(value) for value in coords]
            x1 = min(1.0, max(0.0, x1 / max(1, frame_w)))
            y1 = min(1.0, max(0.0, y1 / max(1, frame_h)))
            x2 = min(1.0, max(0.0, x2 / max(1, frame_w)))
            y2 = min(1.0, max(0.0, y2 / max(1, frame_h)))
            if x2 <= x1 or y2 <= y1:
                continue
            boxes.append({"track_id": d.get("track_id"), "class_name": d.get("class_name"), "confidence": d.get("confidence"), "x1_norm": x1, "y1_norm": y1, "x2_norm": x2, "y2_norm": y2, "speed_kmh": d.get("speed_kmh"), "passage_id": d.get("passage_id")})
        except Exception:
            continue
    now_ms = int(time.time() * 1000)
    if capture_time_unix_ms is None:
        capture_time_unix_ms = now_ms
    if processed_time_unix_ms is None:
        processed_time_unix_ms = now_ms
    env = {"schema": WATER_LIVE_SCHEMA, "camera_id": "cam1", "analytics_profile": "water-v1", "domain": "water", "frame_no": int(frame_no), "generation": int(generation), "observed_mono": float(observed_mono), "capture_time_unix_ms": int(capture_time_unix_ms), "processed_time_unix_ms": int(processed_time_unix_ms), "timestamp_semantics": "worker_receive_utc", "frame_width": int(frame_w), "frame_height": int(frame_h), "worker_source_commit": worker_commit, "detections": boxes}
    return copy.deepcopy(env)

VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle"}

OUTPUT_DIR = Path("output")
LATEST_DIR = OUTPUT_DIR / "latest"
EVENTS_DIR = OUTPUT_DIR / "events"
PASSAGES_DIR = OUTPUT_DIR / "passages"

LATEST_DIR.mkdir(parents=True, exist_ok=True)
EVENTS_DIR.mkdir(parents=True, exist_ok=True)
PASSAGES_DIR.mkdir(parents=True, exist_ok=True)


class MotionDetector:
    def __init__(self):
        self.threshold = env_int("MOTION_THRESHOLD", 10)
        self.min_area = env_int("MOTION_MIN_AREA", 250)
        self.active_seconds = env_float("MOTION_ACTIVE_SECONDS", 8.0)
        self.prev = None
        self.active_until = 0.0
        self.last_boxes = []
        self.last_area = 0.0

    def process(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        if self.prev is None:
            self.prev = gray
            self.last_boxes = []
            self.last_area = 0.0
            return False, 0.0, []
        diff = cv2.absdiff(self.prev, gray)
        _, th = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)
        th = cv2.dilate(th, None, iterations=2)
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        area_sum = 0.0
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            boxes.append((int(x), int(y), int(w), int(h)))
            area_sum += float(area)
        self.prev = gray
        self.last_boxes = boxes
        self.last_area = area_sum
        instant_motion = len(boxes) > 0
        if instant_motion:
            self.active_until = time.time() + self.active_seconds
        return instant_motion, area_sum, boxes

    def is_ai_active(self):
        return time.time() <= self.active_until


def detect_vehicles(model, frame, diagnostics=None):
    profile_name = env_str("ANALYTICS_PROFILE", "").strip()
    profile = get_profile(profile_name) if profile_name else None
    if profile is None:
        confidence_default = 0.25
        image_size_default = 960
        tracker_default = "bytetrack.yaml"
    else:
        confidence_default = profile.confidence
        image_size_default = profile.image_size
        tracker_default = profile.tracker
    confidence = env_float("YOLO_CONFIDENCE", confidence_default)
    image_size = env_int("YOLO_IMAGE_SIZE", image_size_default)
    tracker = env_str("YOLO_TRACKER", tracker_default).strip() or tracker_default
    results = model.track(frame, persist=True, tracker=tracker, imgsz=image_size, conf=confidence, verbose=False)
    detections = []
    if not results:
        return detections
    r = results[0]
    names = r.names
    if r.boxes is None:
        return detections
    track_ids = getattr(r.boxes, "id", None)
    for index, box in enumerate(r.boxes):
        cls_id = int(box.cls[0].item())
        model_class = str(names.get(cls_id, cls_id))
        conf = float(box.conf[0].item())
        track_id = None
        if track_ids is not None:
            try:
                track_id = int(track_ids[index].item())
            except Exception:
                track_id = None
        xyxy = box.xyxy[0].tolist()
        x1, y1, x2, y2 = [int(round(v)) for v in xyxy]
        if profile is None:
            semantic = {"class_name": model_class} if model_class in VEHICLE_CLASSES else None
        else:
            semantic = normalize_model_class(model_class, profile.name)
        if diagnostics is not None:
            diagnostics.append({
                "model_class": model_class,
                "confidence": round(conf, 4),
                "bbox_xyxy": [x1, y1, x2, y2],
                "bbox_width_px": max(0, x2 - x1),
                "bbox_height_px": max(0, y2 - y1),
                "bbox_area_px": max(0, x2 - x1) * max(0, y2 - y1),
                "track_id": track_id,
                "track_assigned": track_id is not None,
                "class_mapping_accepted": semantic is not None,
                "semantic_class": None if semantic is None else semantic.get("class_name"),
            })
        if semantic is None:
            continue
        detections.append({
            "track_id": track_id,
            "confidence": conf,
            "bbox_xyxy": [x1, y1, x2, y2],
            **semantic,
        })
    return detections


def bbox_intersects_motion(det, motion_boxes):
    if not motion_boxes:
        return False
    x1, y1, x2, y2 = det["bbox_xyxy"]
    det_area = max(1.0, float((x2 - x1) * (y2 - y1)))
    for mx, my, mw, mh in motion_boxes:
        mx1, my1, mx2, my2 = mx, my, mx + mw, my + mh
        ix1, iy1, ix2, iy2 = max(x1, mx1), max(y1, my1), min(x2, mx2), min(y2, my2)
        if ix2 <= ix1 or iy2 <= iy1:
            continue
        inter_area = float((ix2 - ix1) * (iy2 - iy1))
        if inter_area / det_area >= 0.03:
            return True
    return False


def filter_detections_by_motion(detections, motion_boxes):
    return [det for det in detections if bbox_intersects_motion(det, motion_boxes)]


def select_profile_detections(profile, model, processing_frame, motion_ai_active, motion_boxes, roi_points):
    if profile is not None and profile.domain == "water":
        raw_detections = detect_vehicles(model, processing_frame)
        return True, filter_detections_by_roi(raw_detections, roi_points)
    if not motion_ai_active:
        return False, []
    raw_detections = detect_vehicles(model, processing_frame)
    detections = filter_detections_by_motion(raw_detections, motion_boxes)
    return True, filter_detections_by_roi(detections, roi_points)


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


def draw_speed_lines_overlay(frame):
    cfg = fetch_speed_lines_config()
    if not cfg.get("enabled"):
        return
    line_a = cfg.get("line_a") or []
    line_b = cfg.get("line_b") or []
    if len(line_a) == 2:
        cv2.line(frame, line_a[0], line_a[1], (0, 128, 255), 2)
        cv2.putText(frame, "A", line_a[0], cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 128, 255), 2, cv2.LINE_AA)
    if len(line_b) == 2:
        cv2.line(frame, line_b[0], line_b[1], (255, 0, 255), 2)
        cv2.putText(frame, "B", line_b[0], cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2, cv2.LINE_AA)


def build_event(best_det, motion_area, speed_info=None, line_speed_info=None):
    event_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    if speed_info is None:
        speed_info = {}
    if line_speed_info is None:
        line_speed_info = {}
    speed_px_s = speed_info.get("speed_px_s")
    speed_kmh = best_det.get("speed_kmh")
    speed_source = best_det.get("speed_source")
    if speed_kmh is None:
        speed_kmh = line_speed_info.get("speed_kmh")
        speed_source = line_speed_info.get("speed_source")
    if speed_kmh is None and not line_speed_info.get("speed_lines_enabled"):
        try:
            speed_kmh = convert_px_s_to_kmh(speed_px_s)
            if speed_kmh is not None:
                speed_source = "px_factor"
        except Exception:
            speed_kmh = None
    is_water = best_det.get("domain") == "water" or best_det.get("analytics_profile") == "water-v1"
    return {
        "event_id": event_id,
        "created_at": now_iso(),
        "track_id": best_det.get("track_id"),
        "class_name": best_det["class_name"],
        "analytics_profile": best_det.get("analytics_profile") or env_str("ANALYTICS_PROFILE", "").strip() or None,
        "domain": best_det.get("domain"),
        "object_type": best_det.get("object_type") or best_det.get("class_name"),
        "model_class": best_det.get("model_class") or best_det.get("class_name"),
        "confidence": best_det["confidence"],
        "bbox": best_det["bbox_xyxy"],
        "center_x": speed_info.get("center_x"),
        "center_y": speed_info.get("center_y"),
        "dx_px": speed_info.get("dx_px"),
        "dy_px": speed_info.get("dy_px"),
        "dt_sec": speed_info.get("dt_sec"),
        "distance_px": speed_info.get("distance_px"),
        "speed_px_s": speed_px_s,
        "speed_kmh": speed_kmh,
        "speed_source": speed_source,
        "speed_distance_m": line_speed_info.get("speed_distance_m"),
        "speed_travel_time_sec": line_speed_info.get("speed_travel_time_sec"),
        "speed_start_line": line_speed_info.get("speed_start_line"),
        "speed_end_line": line_speed_info.get("speed_end_line"),
        "motion_area": int(motion_area),
        "model_name": env_str("MODEL_NAME", "yolo11s.pt"),
        "message": "tracked Water vessel detection" if is_water else "motion-filtered tracked object detection with speed lines",
    }


def main():
    profile_name = env_str("ANALYTICS_PROFILE", "").strip()
    profile = get_profile(profile_name) if profile_name else None
    model_name = env_str("MODEL_NAME", profile.model_name if profile else "yolo11s.pt")
    tracker_name = env_str("YOLO_TRACKER", profile.tracker if profile else "bytetrack.yaml").strip() or (profile.tracker if profile else "bytetrack.yaml")
    print(f"Loading model: {model_name}")
    print(f"Tracking: {tracker_name}")
    if profile is not None:
        print(f"Analytics profile: {profile.name} domain={profile.domain}")
    model = YOLO(model_name)
    state_interval = env_float("STATE_POST_INTERVAL_SEC", 1.0)
    event_cooldown = env_float("EVENT_COOLDOWN_SEC", 12.0)
    motion_detector = MotionDetector()
    reader = start_media_reader()
    last_state_post = 0.0
    last_event_post = 0.0
    frame_no = 0
    latest_overlay_path = LATEST_DIR / "latest_overlay.jpg"
    is_water = profile is not None and profile.domain == "water"
    passage_engine = None
    passage_last_post = {}
    passage_snapshot_paths = {}
    passage_pending_snapshot = set()
    passage_post_interval = max(0.2, env_float("PASSAGE_POST_INTERVAL_SEC", 1.0))
    if is_water:
        passage_engine = PassageEngine(
            lambda: build_two_gate_estimator(fetch_speed_lines_config()),
            max_observations=env_int("WATER_PASSAGE_MAX_OBSERVATIONS", 256),
            max_active_passages=env_int("WATER_PASSAGE_MAX_ACTIVE", 32),
            stitch_window_sec=env_float("WATER_PASSAGE_STITCH_GAP_SEC", 2.5),
            passage_end_gap_sec=env_float("WATER_PASSAGE_TIMEOUT_SEC", 5.0),
            stitch_distance_px=env_float("WATER_PASSAGE_STITCH_MAX_DISTANCE_PX", 120.0),
            calibrated_min_samples=env_int("DETECTION_SPEED_MIN_SAMPLES", 3),
            calibrated_smooth_samples=env_int("DETECTION_SPEED_SMOOTH_SAMPLES", 5),
        )
        print(
            "Water passage engine: strategy=two_gate+calibrated_fallback "
            f"max_observations={passage_engine.max_observations} "
            f"max_active={passage_engine.max_active_passages}"
        )
    print("Worker started")
    print(f"State interval: {state_interval}s")
    print(f"Event cooldown: {event_cooldown}s")
    try:
        while True:
            frame = reader.read_frame()
            if frame is None:
                print("Media stream ended")
                break
            frame_no += 1
            # honest worker-receive timestamp for live envelope v2
            try:
                _LAST_FRAME_CAPTURE_MS = int(time.time() * 1000)  # type: ignore[assignment]
                globals()["_LAST_FRAME_CAPTURE_MS"] = _LAST_FRAME_CAPTURE_MS
            except Exception:
                pass
            processing_frame, roi_points = prepare_roi_processing_frame(frame, motion_detector)
            motion_now, motion_area, motion_boxes = motion_detector.process(processing_frame)
            _always_on = is_motion_gate_always_on()
            motion_ai_active = motion_detector.is_ai_active() or _always_on
            water_recall_raw = []
            if is_water:
                ai_active = True
                detections = detect_vehicles(model, processing_frame, diagnostics=water_recall_raw)
            elif motion_ai_active:
                ai_active = True
                detections = detect_vehicles(model, processing_frame)
                if not _always_on:
                    detections = filter_detections_by_motion(detections, motion_boxes)
            else:
                ai_active = False
                detections = []
            detections = filter_detections_by_roi(detections)
            if is_water:
                try:
                    maybe_emit_water_recall_diagnostics(frame_no, water_recall_raw, roi_points, detections, profile)
                except Exception as exc:
                    print(f"Water recall diagnostics skipped: {exc}")
            now = time.time()
            active_track_ids = {int(det["track_id"]) for det in detections if det.get("track_id") is not None}
            update_crossing_counts(detections, now)
            passage_updates = []
            if is_water and passage_engine is not None:
                # Compute fresh calibrated telemetry before PassageEngine so the
                # passage, not the live renderer, owns the published speed state.
                for det in detections:
                    try:
                        det["_line_speed_info"] = update_speed_lines_estimate(det)
                    except Exception:
                        det["_line_speed_info"] = {}
                # Inject per-detection sharpness for sharpness-aware best-frame selection.
                for det in detections:
                    try:
                        x1, y1, x2, y2 = [int(round(float(v))) for v in det.get("bbox_xyxy") or []]
                        if x2 > x1 and y2 > y1:
                            x1c = max(0, min(x1, frame.shape[1] - 1))
                            x2c = max(0, min(x2, frame.shape[1]))
                            y1c = max(0, min(y1, frame.shape[0] - 1))
                            y2c = max(0, min(y2, frame.shape[0]))
                            if x2c > x1c and y2c > y1c:
                                crop = frame[y1c:y2c, x1c:x2c]
                                det["_sharpness"] = float(crop_sharpness(crop))
                    except Exception:
                        pass
                passage_updates = passage_engine.update(detections, now)
                passage_by_track = {}
                for update in passage_updates:
                    passage = update.get("passage") or {}
                    for track_id in update.get("observed_track_ids") or []:
                        passage_by_track[int(track_id)] = passage
                for det in detections:
                    track_id = det.get("track_id")
                    passage = passage_by_track.get(int(track_id)) if track_id is not None else None
                    if passage is None:
                        det["speed_kmh"] = None
                        det["speed_source"] = "two_gate"
                        det["speed_ready"] = False
                        continue
                    det["passage_id"] = passage["passage_id"]
                    det["speed_kmh"] = passage.get("speed_kmh")
                    det["speed_source"] = passage.get("speed_method")
                    det["speed_ready"] = passage.get("speed_status") == "measured"
            else:
                for det in detections:
                    speed_info = update_speed_estimate(det)
                    line_speed_info = update_speed_lines_estimate(det)
                    speed_px_s = speed_info.get("speed_px_s")
                    speed_kmh = line_speed_info.get("speed_kmh")
                    speed_source = line_speed_info.get("speed_source")
                    speed_lines_enabled = bool(line_speed_info.get("speed_lines_enabled"))
                    if speed_kmh is None and not speed_lines_enabled:
                        try:
                            speed_kmh = convert_px_s_to_kmh(speed_px_s)
                            if speed_kmh is not None:
                                speed_source = "px_factor"
                        except Exception:
                            speed_kmh = None
                    det["speed_px_s"] = speed_px_s
                    det["speed_kmh"] = speed_kmh
                    det["speed_source"] = speed_source
                    det["speed_ready"] = bool(line_speed_info.get("speed_ready")) or (not speed_lines_enabled and speed_kmh is not None)
                    det["_speed_info"] = speed_info
                    det["_line_speed_info"] = line_speed_info
                prune_track_states(now)

            if not is_water:
                try:
                    h, w = frame.shape[:2]
                    wc = os.environ.get("SEA_SPEED_SOURCE_COMMIT", "unknown")
                    # capture_time is worker-receive UTC; main loop captures after read_frame
                    # Use dedicated per-frame timestamp if available via thread-local, else now
                    ct_ms = int(getattr(frame, "_capture_time_unix_ms", int(time.time() * 1000))) if hasattr(frame, "_capture_time_unix_ms") else int(time.time() * 1000)
                    # fallback to frame_no-based ingest time stored in global last capture
                    try:
                        _last_cap = globals().get("_LAST_FRAME_CAPTURE_MS")
                        if isinstance(_last_cap, int):
                            ct_ms = _last_cap
                    except Exception:
                        pass
                    pt_ms = int(time.time() * 1000)
                    env_live = build_road_live_envelope(
                        frame_no,
                        ROAD_LIVE_GENERATION,
                        time.monotonic(),
                        detections,
                        w,
                        h,
                        wc,
                        capture_time_unix_ms=ct_ms,
                        processed_time_unix_ms=pt_ms,
                    )
                    post_live_envelope(env_live)
                except Exception as e:
                    print(f"live envelope post skipped: {e}")
            else:
                # Water live publishes the canonical passage speed already
                # attached above; there is no independent post-passage overwrite.
                try:
                    h, w = frame.shape[:2]
                    wc = os.environ.get("SEA_SPEED_SOURCE_COMMIT", "unknown")
                    ct_ms = int(time.time() * 1000)
                    try:
                        _last_cap = globals().get("_LAST_FRAME_CAPTURE_MS")
                        if isinstance(_last_cap, int):
                            ct_ms = _last_cap
                    except Exception:
                        pass
                    pt_ms = int(time.time() * 1000)
                    env_live = build_water_live_envelope(
                        frame_no,
                        WATER_LIVE_GENERATION,
                        time.monotonic(),
                        detections,
                        w,
                        h,
                        wc,
                        capture_time_unix_ms=ct_ms,
                        processed_time_unix_ms=pt_ms,
                    )
                    post_live_envelope(env_live)
                except Exception as e:
                    print(f"water live envelope post skipped: {e}")

            crossing_snapshot = crossing_overlay_summary()
            overlay = draw_overlay(frame=frame, motion_now=motion_now, motion_area=motion_area, ai_active=ai_active, detections=detections, motion_boxes=motion_boxes, crossing_summary=crossing_snapshot)
            cv2.imwrite(str(latest_overlay_path), overlay, [cv2.IMWRITE_JPEG_QUALITY, 85])
            flush_crossing_posts()

            if profile is not None and profile.domain == "water":
                for vessel in water_event_candidates(profile, detections):
                    if vessel.get("passage_id") is None:
                        print(f'Water passage mapping missing track={vessel.get("track_id")}')
                for update in passage_updates:
                    passage = update.get("passage") or {}
                    passage_id = str(passage.get("passage_id") or "")
                    if not passage_id:
                        continue
                    snapshot_path = passage_snapshot_paths.get(passage_id)
                    if snapshot_path is None:
                        snapshot_path = PASSAGES_DIR / f"{passage_id}.jpg"
                        passage_snapshot_paths[passage_id] = snapshot_path
                    if update.get("snapshot_candidate"):
                        snapshot_detection = update.get("snapshot_detection")
                        if snapshot_detection is not None and write_passage_snapshot(frame, snapshot_detection, snapshot_path):
                            passage_pending_snapshot.add(passage_id)
                    upload_snapshot = snapshot_path if passage_id in passage_pending_snapshot and snapshot_path.is_file() else None
                    completed = passage.get("status") == "completed"
                    due = now - float(passage_last_post.get(passage_id, 0.0)) >= passage_post_interval
                    should_post = bool(update.get("snapshot_candidate") or completed or due)
                    if should_post and post_passage(passage, upload_snapshot):
                        passage_last_post[passage_id] = now
                        passage_pending_snapshot.discard(passage_id)
                        if completed:
                            passage_last_post.pop(passage_id, None)
                            passage_snapshot_paths.pop(passage_id, None)
                            try:
                                snapshot_path.unlink(missing_ok=True)
                            except OSError:
                                pass
            elif detections:
                best = max(detections, key=lambda d: d["confidence"])
                speed_info = best.get("_speed_info") or {}
                line_speed_info = best.get("_line_speed_info") or {}
                speed_px_s = speed_info.get("speed_px_s")
                min_speed = env_float("MIN_EVENT_SPEED_PX_PER_SEC", 10.0)
                speed_lines_enabled = bool(line_speed_info.get("speed_lines_enabled"))
                canonical_speed_kmh = best.get("speed_kmh")
                speed_ready = bool(line_speed_info.get("speed_ready")) and canonical_speed_kmh is not None
                track_id = best.get("track_id")
                publishable = track_id is not None and best.get("object_type") != "person"
                event_already_posted = track_event_posted(track_id)
                has_px_speed = speed_px_s is not None
                cooldown_ok = now - last_event_post >= event_cooldown
                legacy_event_ready = speed_ready or (has_px_speed and speed_px_s >= min_speed and cooldown_ok)
                if speed_lines_enabled:
                    should_post_event = publishable and speed_ready and not event_already_posted
                else:
                    should_post_event = publishable and not event_already_posted and legacy_event_ready
                if should_post_event:
                    event = build_event(best, motion_area, speed_info, line_speed_info)
                    event_snapshot_path = EVENTS_DIR / f'{event["event_id"]}.jpg'
                    wrote = cv2.imwrite(str(event_snapshot_path), overlay, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    if not wrote or not event_snapshot_path.is_file():
                        print(f"event snapshot write failed for {event['event_id']}")
                    elif post_event(event, event_snapshot_path):
                        last_event_post = now
                        mark_track_event_posted(track_id)
            if now - last_state_post >= state_interval:
                track_count = len(active_track_ids)
                # single snapshot reused for overlay already; ensure sync
                try:
                    cw, ch = _resolve_frame_size()
                except Exception:
                    cw, ch = 1920, 1080
                try:
                    sample_fps_val = float(env_float("SAMPLE_FPS", profile.sample_fps if profile else 10.0))
                except Exception:
                    sample_fps_val = 10.0
                eff_fps = None
                p95_ms = None
                try:
                    # try to get global tracker from entrypoint if available
                    import sys as _sys
                    _entry = _sys.modules.get("ubuntu_worker_entrypoint")
                    _tracker = getattr(_entry, "_perf_tracker", None) if _entry else None
                    if _tracker is not None:
                        snap = _tracker.snapshot()
                        eff_fps = float(snap.get("effective_fps", 0) or 0)
                        p95_ms = float(snap.get("p95_inference_ms", 0) or 0)
                except Exception:
                    pass
                metadata = {
                    "camera_id": env_str("CAMERA_ID", profile.default_camera_id if profile else "cam1_road_test"),
                    "analytics_profile": profile.name if profile else None,
                    "domain": profile.domain if profile else None,
                    "motion_now": bool(motion_now),
                    "motion_area": int(motion_area),
                    "ai_active": bool(ai_active),
                    "detections": len(detections),
                    "tracks": track_count,
                    "active_passages": passage_engine.active_count if passage_engine is not None else None,
                    "crossings": crossing_snapshot,
                    "frame_no": frame_no,
                    "frame_width": int(cw),
                    "frame_height": int(ch),
                    "sample_fps": float(sample_fps_val),
                    "effective_fps": eff_fps,
                    "p95_inference_ms": p95_ms,
                    "overlay_rev": int(frame_no),
                    "model_name": model_name,
                    "message": "event-worker running with persistent tracking",
                }
                ok = post_state(metadata, latest_overlay_path)
                last_state_post = now
                if ok:
                    print(f"POST state ok motion={motion_now} ai={ai_active} detections={len(detections)} tracks={track_count}")
    except KeyboardInterrupt:
        print("Stopped by user")
    finally:
        reader.close()


if __name__ == "__main__":
    main()