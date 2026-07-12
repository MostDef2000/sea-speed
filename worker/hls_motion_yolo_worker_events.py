import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import requests
from ultralytics import YOLO


VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle"}

OUTPUT_DIR = Path("output")
LATEST_DIR = OUTPUT_DIR / "latest"
EVENTS_DIR = OUTPUT_DIR / "events"

LATEST_DIR.mkdir(parents=True, exist_ok=True)
EVENTS_DIR.mkdir(parents=True, exist_ok=True)


def env_str(name, default=""):
    return os.environ.get(name, default)


def env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


def env_float(name, default):
    try:
        return float(os.environ.get(name, str(default)))
    except Exception:
        return default


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def start_ffmpeg():
    hls_url = env_str("HLS_URL")
    if not hls_url:
        raise RuntimeError("HLS_URL is not set")

    width = env_int("FRAME_WIDTH", 704)
    height = env_int("FRAME_HEIGHT", 576)
    sample_fps = env_float("SAMPLE_FPS", 5.0)
    auth = env_str("HLS_BASIC_AUTH_BASE64")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
    ]

    if auth:
        cmd += [
            "-headers",
            f"Authorization: Basic {auth}\r\n",
        ]

    cmd += [
        "-i",
        hls_url,
        "-vf",
        f"fps={sample_fps},scale={width}:{height}",
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]

    print("Starting FFmpeg HLS reader")
    print(f"HLS: {hls_url}")
    print(f"Frame: {width}x{height}")
    print(f"Sample FPS: {sample_fps}")

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=10**8,
    )


def read_exact(pipe, size):
    data = bytearray()

    while len(data) < size:
        chunk = pipe.read(size - len(data))
        if not chunk:
            return None
        data.extend(chunk)

    return bytes(data)


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


def detect_vehicles(model, frame):
    confidence = env_float("YOLO_CONFIDENCE", 0.25)
    image_size = env_int("YOLO_IMAGE_SIZE", 960)

    results = model(frame, imgsz=image_size, conf=confidence, verbose=False)

    detections = []

    if not results:
        return detections

    r = results[0]
    names = r.names

    if r.boxes is None:
        return detections

    for box in r.boxes:
        cls_id = int(box.cls[0].item())
        class_name = str(names.get(cls_id, cls_id))
        conf = float(box.conf[0].item())

        if class_name not in VEHICLE_CLASSES:
            continue

        xyxy = box.xyxy[0].tolist()
        x1, y1, x2, y2 = [int(round(v)) for v in xyxy]

        detections.append({
            "class_name": class_name,
            "confidence": conf,
            "bbox_xyxy": [x1, y1, x2, y2],
        })

    return detections


def bbox_intersects_motion(det, motion_boxes):
    if not motion_boxes:
        return False

    x1, y1, x2, y2 = det["bbox_xyxy"]
    det_area = max(1.0, float((x2 - x1) * (y2 - y1)))

    for mx, my, mw, mh in motion_boxes:
        mx1 = mx
        my1 = my
        mx2 = mx + mw
        my2 = my + mh

        ix1 = max(x1, mx1)
        iy1 = max(y1, my1)
        ix2 = min(x2, mx2)
        iy2 = min(y2, my2)

        if ix2 <= ix1 or iy2 <= iy1:
            continue

        inter_area = float((ix2 - ix1) * (iy2 - iy1))

        if inter_area / det_area >= 0.03:
            return True

    return False


def filter_detections_by_motion(detections, motion_boxes):
    return [
        det for det in detections
        if bbox_intersects_motion(det, motion_boxes)
    ]




_roi_cache = {
    "ts": 0.0,
    "enabled": False,
    "points": [],
    "signature": "",
}


def get_roi_url():
    url = env_str("SEA_SPEED_ROI_URL", "").strip()

    if url:
        return url

    state_url = env_str("SEA_SPEED_API_URL", "").strip()

    if state_url:
        return state_url.rsplit("/", 1)[0] + "/roi"

    return ""


def fetch_remote_roi():
    refresh_sec = env_float("ROI_REFRESH_SEC", 5.0)
    now = time.time()

    if now - _roi_cache["ts"] < refresh_sec:
        return _roi_cache["enabled"], _roi_cache["points"]

    _roi_cache["ts"] = now

    url = get_roi_url()

    if not url:
        _roi_cache["enabled"] = False
        _roi_cache["points"] = []
        return False, []

    headers = {}
    basic_auth = env_str("HLS_BASIC_AUTH_BASE64", "").strip()

    if basic_auth:
        headers["Authorization"] = f"Basic {basic_auth}"

    try:
        r = requests.get(url, headers=headers, timeout=5)

        if r.status_code >= 300:
            print(f"ROI fetch failed: HTTP {r.status_code} {r.text[:160]}")
            return _roi_cache["enabled"], _roi_cache["points"]

        data = r.json()
        raw_points = data.get("polygon", [])
        points = []

        if isinstance(raw_points, list):
            for p in raw_points:
                if not isinstance(p, dict):
                    continue

                try:
                    x = int(round(float(p.get("x"))))
                    y = int(round(float(p.get("y"))))
                except Exception:
                    continue

                points.append((x, y))

        enabled = bool(data.get("enabled")) and len(points) >= 3

        signature = f"{enabled}:{points}"

        if signature != _roi_cache.get("signature"):
            print(f"ROI loaded from VPS: enabled={enabled} points={len(points)}")

        _roi_cache["enabled"] = enabled
        _roi_cache["points"] = points
        _roi_cache["signature"] = signature

        return enabled, points

    except Exception as e:
        print(f"ROI fetch error: {e}")
        return _roi_cache["enabled"], _roi_cache["points"]


def road_roi_enabled():
    enabled, points = fetch_remote_roi()
    return enabled and len(points) >= 3


def parse_road_roi_polygon():
    enabled, points = fetch_remote_roi()

    if not enabled:
        return []

    return points


def bbox_center(det):
    x1, y1, x2, y2 = det["bbox_xyxy"]
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def detection_inside_road_roi(det):
    points = parse_road_roi_polygon()

    if len(points) < 3:
        return True

    polygon = np.array(points, dtype=np.int32)
    cx, cy = bbox_center(det)

    return cv2.pointPolygonTest(polygon, (float(cx), float(cy)), False) >= 0


def filter_detections_by_roi(detections):
    return [
        det for det in detections
        if detection_inside_road_roi(det)
    ]


def draw_roi_polygon(frame):
    points = parse_road_roi_polygon()

    if len(points) < 3:
        return

    polygon = np.array(points, dtype=np.int32)
    cv2.polylines(frame, [polygon], True, (255, 0, 0), 2)


def draw_overlay(frame, motion_now, motion_area, ai_active, detections, motion_boxes):
    out = frame.copy()

    for x, y, w, h in motion_boxes:
        cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 255), 2)

    for det in detections:
        x1, y1, x2, y2 = det["bbox_xyxy"]
        label = f'{det["class_name"]} {det["confidence"]:.2f}'

        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            out,
            label,
            (x1, max(18, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

    lines = [
        f"motion_now: {motion_now}",
        f"motion_area: {int(motion_area)}",
        f"ai_active: {ai_active}",
        f"detections: {len(detections)}",
        f"posted_to: mostdef.ru/sea-speed",
    ]

    y = 24
    for line in lines:
        cv2.putText(
            out,
            line,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        y += 25

    return out


def post_state(metadata, overlay_path):
    state_url = env_str("SEA_SPEED_API_URL")
    token = env_str("SEA_SPEED_API_TOKEN")

    if not state_url or not token:
        print("POST state skipped: SEA_SPEED_API_URL or SEA_SPEED_API_TOKEN is not set")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        with open(overlay_path, "rb") as f:
            files = {
                "overlay": ("overlay.jpg", f, "image/jpeg"),
            }
            data = {
                "metadata": json.dumps(metadata, ensure_ascii=False),
            }

            r = requests.post(
                state_url,
                headers=headers,
                data=data,
                files=files,
                timeout=10,
            )

        if r.status_code >= 300:
            print(f"POST state failed: HTTP {r.status_code} {r.text[:300]}")
            return False

        return True

    except Exception as e:
        print(f"POST state error: {e}")
        return False


def post_event(event, snapshot_path):
    state_url = env_str("SEA_SPEED_API_URL")
    event_url = env_str("SEA_SPEED_EVENT_API_URL")

    if not event_url and state_url:
        event_url = state_url.rsplit("/", 1)[0] + "/events"

    token = env_str("SEA_SPEED_API_TOKEN")

    if not event_url or not token:
        print("POST event skipped: event URL or token is not set")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        with open(snapshot_path, "rb") as f:
            files = {
                "snapshot": ("event.jpg", f, "image/jpeg"),
            }
            data = {
                "metadata": json.dumps(event, ensure_ascii=False),
            }

            r = requests.post(
                event_url,
                headers=headers,
                data=data,
                files=files,
                timeout=10,
            )

        if r.status_code >= 300:
            print(f"POST event failed: HTTP {r.status_code} {r.text[:300]}")
            return False

        print(f'POST event ok id={event["event_id"]} class={event["class_name"]} conf={event["confidence"]:.2f}')
        return True

    except Exception as e:
        print(f"POST event error: {e}")
        return False



_speed_track = {
    "center": None,
    "ts": None,
    "class_name": None,
}




def detection_center_px(det):
    # Detection-first speed trigger point:
    # bottom-center of bbox, not the geometric center.
    #
    # bbox_xyxy = [x1, y1, x2, y2]
    # point = ((x1 + x2) / 2, y2)
    x1, y1, x2, y2 = det["bbox_xyxy"]
    return ((x1 + x2) / 2.0, y2)

def update_speed_estimate(det):
    now = time.time()
    cx, cy = detection_center_px(det)

    info = {
        "center_x": round(cx, 2),
        "center_y": round(cy, 2),
        "dx_px": None,
        "dy_px": None,
        "dt_sec": None,
        "distance_px": None,
        "speed_px_s": None,
    }

    prev_center = _speed_track.get("center")
    prev_ts = _speed_track.get("ts")
    prev_class = _speed_track.get("class_name")

    if prev_center is not None and prev_ts is not None and prev_class == det["class_name"]:
        dt = now - prev_ts

        if 0.05 <= dt <= 3.0:
            dx = cx - prev_center[0]
            dy = cy - prev_center[1]
            distance = (dx * dx + dy * dy) ** 0.5
            speed = distance / dt

            info.update({
                "dx_px": round(dx, 2),
                "dy_px": round(dy, 2),
                "dt_sec": round(dt, 3),
                "distance_px": round(distance, 2),
                "speed_px_s": round(speed, 2),
            })

    _speed_track["center"] = (cx, cy)
    _speed_track["ts"] = now
    _speed_track["class_name"] = det["class_name"]

    return info





_speed_config_cache = {
    "ts": 0.0,
    "enabled": False,
    "kmh_per_px_s": 0.0,
}


def get_speed_config_url():
    url = env_str("SEA_SPEED_SPEED_CONFIG_URL", "").strip()

    if url:
        return url

    state_url = env_str("SEA_SPEED_API_URL", "").strip()

    if state_url:
        return state_url.rsplit("/", 1)[0] + "/speed-config"

    return ""


def fetch_speed_config():
    refresh_sec = env_float("SPEED_CONFIG_REFRESH_SEC", 10.0)
    now = time.time()

    if now - _speed_config_cache["ts"] < refresh_sec:
        return _speed_config_cache

    _speed_config_cache["ts"] = now

    url = get_speed_config_url()

    if not url:
        return _speed_config_cache

    headers = {}
    basic_auth = env_str("HLS_BASIC_AUTH_BASE64", "").strip()

    if basic_auth:
        headers["Authorization"] = f"Basic {basic_auth}"

    try:
        r = requests.get(url, headers=headers, timeout=5)

        if r.status_code >= 300:
            print(f"Speed config fetch failed: HTTP {r.status_code} {r.text[:160]}")
            return _speed_config_cache

        data = r.json()

        _speed_config_cache["enabled"] = bool(data.get("enabled"))
        _speed_config_cache["kmh_per_px_s"] = float(data.get("kmh_per_px_s") or 0.0)

        return _speed_config_cache

    except Exception as e:
        print(f"Speed config fetch error: {e}")
        return _speed_config_cache


def convert_px_s_to_kmh(speed_px_s):
    if speed_px_s is None:
        return None

    config = fetch_speed_config()

    if not config.get("enabled"):
        return None

    factor = float(config.get("kmh_per_px_s") or 0.0)

    if factor <= 0:
        return None

    return round(float(speed_px_s) * factor, 1)




_speed_lines_cache = {
    "ts": 0.0,
    "enabled": False,
    "distance_m": 57.0,
    "line_a": [],
    "line_b": [],
    "signature": "",
}

_line_speed_state = {
    "prev_center": None,
    "prev_ts": None,
    "prev_side_a": None,
    "prev_side_b": None,
    "pending": None,
}


def detection_center_px(det):
    x1, y1, x2, y2 = det["bbox_xyxy"]
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def get_speed_lines_url():
    url = env_str("SEA_SPEED_SPEED_LINES_URL", "").strip()

    if url:
        return url

    state_url = env_str("SEA_SPEED_API_URL", "").strip()

    if state_url:
        return state_url.rsplit("/", 1)[0] + "/speed-lines"

    return ""


def fetch_speed_lines_config():
    refresh_sec = env_float("SPEED_LINES_REFRESH_SEC", 5.0)
    now = time.time()

    if now - _speed_lines_cache["ts"] < refresh_sec:
        return _speed_lines_cache

    _speed_lines_cache["ts"] = now
    url = get_speed_lines_url()

    if not url:
        _speed_lines_cache["enabled"] = False
        return _speed_lines_cache

    headers = {}
    basic_auth = env_str("HLS_BASIC_AUTH_BASE64", "").strip()

    if basic_auth:
        headers["Authorization"] = f"Basic {basic_auth}"

    try:
        r = requests.get(url, headers=headers, timeout=5)

        if r.status_code >= 300:
            print(f"Speed lines fetch failed: HTTP {r.status_code} {r.text[:160]}")
            return _speed_lines_cache

        data = r.json()

        def clean_line(raw):
            points = []
            if isinstance(raw, list):
                for p in raw[:2]:
                    if not isinstance(p, dict):
                        continue
                    try:
                        points.append((int(round(float(p.get("x")))), int(round(float(p.get("y"))))))
                    except Exception:
                        continue
            return points

        line_a = clean_line(data.get("line_a", []))
        line_b = clean_line(data.get("line_b", []))
        enabled = bool(data.get("enabled")) and len(line_a) == 2 and len(line_b) == 2

        try:
            distance_m = float(data.get("distance_m") or 57.0)
        except Exception:
            distance_m = 57.0

        signature = f"{enabled}:{distance_m}:{line_a}:{line_b}"

        if signature != _speed_lines_cache.get("signature"):
            print(f"Speed lines loaded: enabled={enabled} distance_m={distance_m} A={line_a} B={line_b}")

        _speed_lines_cache["enabled"] = enabled
        _speed_lines_cache["distance_m"] = distance_m
        _speed_lines_cache["line_a"] = line_a
        _speed_lines_cache["line_b"] = line_b
        _speed_lines_cache["signature"] = signature

        return _speed_lines_cache

    except Exception as e:
        print(f"Speed lines fetch error: {e}")
        return _speed_lines_cache


def side_of_line(point, line):
    if not line or len(line) != 2:
        return None

    x, y = point
    x1, y1 = line[0]
    x2, y2 = line[1]

    return (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)


def sign_with_deadzone(value, deadzone=1.0):
    if value is None:
        return 0
    if value > deadzone:
        return 1
    if value < -deadzone:
        return -1
    return 0


def crossed_line(prev_side, current_side):
    ps = sign_with_deadzone(prev_side)
    cs = sign_with_deadzone(current_side)

    if ps == 0 or cs == 0:
        return False

    return ps != cs




def update_speed_lines_estimate(det):
    # Detection-first speed model.
    #
    # Line A / Line B are NOT start/finish gates anymore.
    # They are only calibration anchors:
    #   distance_m = real road distance between midpoint(Line A) and midpoint(Line B)
    #
    # For every detection frame:
    #   1. Take bottom-center of bbox.
    #   2. Project it onto A->B road axis.
    #   3. Compare with previous detection point.
    #   4. Calculate instant km/h.
    #   5. Maintain min / max / avg stats for the active track.
    #
    # This means speed is calculated from detection movement itself,
    # not from waiting for line crossing.
    cfg = fetch_speed_lines_config()
    now = time.time()
    point = detection_center_px(det)

    info = {
        "line_speed_kmh": None,
        "speed_kmh": None,
        "speed_source": "detection_first",
        "speed_distance_m": None,
        "speed_travel_time_sec": None,
        "speed_start_line": None,
        "speed_end_line": None,
        "speed_trigger_point": "bottom_center",
        "speed_segment_kmh": None,
        "speed_kmh_min": None,
        "speed_kmh_max": None,
        "speed_kmh_avg": None,
        "speed_sample_count": 0,
        "speed_ready": False,
    }

    _line_speed_state.setdefault("prev_point", None)
    _line_speed_state.setdefault("prev_progress_m", None)
    _line_speed_state.setdefault("prev_ts", None)
    _line_speed_state.setdefault("samples", [])
    _line_speed_state.setdefault("track_started_ts", now)
    _line_speed_state.setdefault("last_seen_ts", now)

    max_gap_sec = env_float("DETECTION_TRACK_MAX_GAP_SEC", 2.0)
    min_dt = env_float("DETECTION_SPEED_MIN_DT_SEC", 0.05)
    max_dt = env_float("DETECTION_SPEED_MAX_DT_SEC", 1.5)
    min_kmh = env_float("DETECTION_SPEED_MIN_KMH", 1.0)
    max_kmh = env_float("DETECTION_SPEED_MAX_KMH", 180.0)
    smooth_samples = int(env_float("DETECTION_SPEED_SMOOTH_SAMPLES", 5))

    prev_ts = _line_speed_state.get("prev_ts")
    if prev_ts is not None and now - float(prev_ts) > max_gap_sec:
        _line_speed_state["prev_point"] = None
        _line_speed_state["prev_progress_m"] = None
        _line_speed_state["prev_ts"] = None
        _line_speed_state["samples"] = []
        _line_speed_state["track_started_ts"] = now

    line_a = cfg.get("line_a") or []
    line_b = cfg.get("line_b") or []

    try:
        distance_m = float(cfg.get("distance_m") or 57.0)
    except Exception:
        distance_m = 57.0

    info["speed_distance_m"] = round(distance_m, 2)

    def valid_line(line):
        return isinstance(line, list) and len(line) == 2

    def midpoint(line):
        return (
            (float(line[0][0]) + float(line[1][0])) / 2.0,
            (float(line[0][1]) + float(line[1][1])) / 2.0,
        )

    def progress_m_from_calibration(p):
        if not valid_line(line_a) or not valid_line(line_b):
            return None

        ma = midpoint(line_a)
        mb = midpoint(line_b)

        vx = mb[0] - ma[0]
        vy = mb[1] - ma[1]
        denom = vx * vx + vy * vy

        if denom <= 1e-6:
            return None

        px = float(p[0]) - ma[0]
        py = float(p[1]) - ma[1]
        t = (px * vx + py * vy) / denom

        return t * distance_m

    progress_m = progress_m_from_calibration(point)

    if progress_m is None:
        _line_speed_state["prev_point"] = point
        _line_speed_state["prev_progress_m"] = None
        _line_speed_state["prev_ts"] = now
        _line_speed_state["last_seen_ts"] = now
        return info

    prev_progress_m = _line_speed_state.get("prev_progress_m")
    prev_ts = _line_speed_state.get("prev_ts")

    if prev_progress_m is not None and prev_ts is not None:
        dt = now - float(prev_ts)

        if min_dt <= dt <= max_dt:
            dm = float(progress_m) - float(prev_progress_m)
            inst_kmh = abs(dm / dt) * 3.6

            if min_kmh <= inst_kmh <= max_kmh:
                inst_kmh = round(inst_kmh, 1)
                _line_speed_state["samples"].append(inst_kmh)

                if len(_line_speed_state["samples"]) > 120:
                    _line_speed_state["samples"] = _line_speed_state["samples"][-120:]

                samples = list(_line_speed_state["samples"])
                recent = samples[-smooth_samples:] if smooth_samples > 0 else samples

                avg_recent = round(sum(recent) / len(recent), 1)
                avg_all = round(sum(samples) / len(samples), 1)
                min_all = round(min(samples), 1)
                max_all = round(max(samples), 1)

                info.update({
                    "line_speed_kmh": avg_recent,
                    "speed_kmh": avg_recent,
                    "speed_source": "detection_first_calibrated",
                    "speed_trigger_point": "bottom_center",
                    "speed_segment_kmh": avg_recent,
                    "speed_kmh_min": min_all,
                    "speed_kmh_max": max_all,
                    "speed_kmh_avg": avg_all,
                    "speed_sample_count": len(samples),
                    "speed_travel_time_sec": round(now - float(_line_speed_state.get("track_started_ts", now)), 3),
                    "speed_ready": True,
                })

                print(
                    f"Detection-first speed: {avg_recent} km/h "
                    f"instant={inst_kmh} min={min_all} avg={avg_all} max={max_all} "
                    f"samples={len(samples)} trigger=bottom_center"
                )

    _line_speed_state["prev_point"] = point
    _line_speed_state["prev_progress_m"] = progress_m
    _line_speed_state["prev_ts"] = now
    _line_speed_state["last_seen_ts"] = now

    return info

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

    speed_kmh = line_speed_info.get("speed_kmh")
    speed_source = line_speed_info.get("speed_source")

    if speed_kmh is None:
        try:
            speed_kmh = convert_px_s_to_kmh(speed_px_s)
            if speed_kmh is not None:
                speed_source = "px_factor"
        except Exception:
            speed_kmh = None

    return {
        "event_id": event_id,
        "created_at": now_iso(),
        "class_name": best_det["class_name"],
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
        "message": "motion-filtered vehicle detection with speed lines",
    }


def main():
    width = env_int("FRAME_WIDTH", 704)
    height = env_int("FRAME_HEIGHT", 576)
    frame_size = width * height * 3

    model_name = env_str("MODEL_NAME", "yolo11s.pt")
    print(f"Loading model: {model_name}")
    model = YOLO(model_name)

    state_interval = env_float("STATE_POST_INTERVAL_SEC", 1.0)
    event_cooldown = env_float("EVENT_COOLDOWN_SEC", 12.0)

    motion_detector = MotionDetector()
    proc = start_ffmpeg()

    last_state_post = 0.0
    last_event_post = 0.0
    frame_no = 0

    latest_overlay_path = LATEST_DIR / "latest_overlay.jpg"

    print("Worker started")
    print(f"State interval: {state_interval}s")
    print(f"Event cooldown: {event_cooldown}s")

    try:
        while True:
            raw = read_exact(proc.stdout, frame_size)

            if raw is None:
                print("FFmpeg stream ended")
                break

            frame_no += 1

            frame = np.frombuffer(raw, np.uint8).reshape((height, width, 3))

            motion_now, motion_area, motion_boxes = motion_detector.process(frame)
            ai_active = motion_detector.is_ai_active()

            detections = []

            if ai_active:
                raw_detections = detect_vehicles(model, frame)
                detections = filter_detections_by_motion(raw_detections, motion_boxes)
                detections = filter_detections_by_roi(detections)

            overlay = draw_overlay(
                frame=frame,
                motion_now=motion_now,
                motion_area=motion_area,
                ai_active=ai_active,
                detections=detections,
                motion_boxes=motion_boxes,
            )

            draw_roi_polygon(overlay)
            draw_speed_lines_overlay(overlay)

            cv2.imwrite(
                str(latest_overlay_path),
                overlay,
                [cv2.IMWRITE_JPEG_QUALITY, 85],
            )

            now = time.time()

            if detections:
                best = max(detections, key=lambda d: d["confidence"])
                speed_info = update_speed_estimate(best)
                line_speed_info = update_speed_lines_estimate(best)
                speed_px_s = speed_info.get("speed_px_s")
                min_speed = env_float("MIN_EVENT_SPEED_PX_PER_SEC", 10.0)

                line_speed_kmh = line_speed_info.get("speed_kmh")
                speed_ready = bool(line_speed_info.get("speed_ready")) or line_speed_kmh is not None

                has_px_speed = speed_px_s is not None
                cooldown_ok = now - last_event_post >= event_cooldown

                # Detection-first event policy:
                # - Do not post empty events with no px speed and no km/h.
                # - Post calibrated km/h event immediately when ready.
                # - Otherwise post px-speed event by cooldown.
                should_post_event = speed_ready or (
                    has_px_speed
                    and speed_px_s >= min_speed
                    and cooldown_ok
                )

                if should_post_event:
                    event = build_event(best, motion_area, speed_info, line_speed_info)

                    event_snapshot_path = EVENTS_DIR / f'{event["event_id"]}.jpg'

                    cv2.imwrite(
                        str(event_snapshot_path),
                        overlay,
                        [cv2.IMWRITE_JPEG_QUALITY, 90],
                    )

                    last_event_post = now
                    post_event(event, event_snapshot_path)

            if now - last_state_post >= state_interval:
                metadata = {
                    "camera_id": env_str("CAMERA_ID", "cam1_road_test"),
                    "motion_now": bool(motion_now),
                    "motion_area": int(motion_area),
                    "ai_active": bool(ai_active),
                    "detections": len(detections),
                    "tracks": len(detections),
                    "frame_no": frame_no,
                    "model_name": model_name,
                    "message": "event-worker running",
                }

                ok = post_state(metadata, latest_overlay_path)
                last_state_post = now

                if ok:
                    print(
                        f"POST state ok motion={motion_now} "
                        f"ai={ai_active} detections={len(detections)} tracks={len(detections)}"
                    )

    except KeyboardInterrupt:
        print("Stopped by user")

    finally:
        try:
            proc.kill()
        except Exception:
            pass


if __name__ == "__main__":
    main()
