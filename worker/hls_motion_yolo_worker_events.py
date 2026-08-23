import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import cv2
import numpy as np
import requests
from ultralytics import YOLO

from analytics_profiles import get_profile, normalize_model_class
from water_passage import WaterPassageEngine, build_two_gate_estimator


VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle"}

OUTPUT_DIR = Path("output")
LATEST_DIR = OUTPUT_DIR / "latest"
EVENTS_DIR = OUTPUT_DIR / "events"
PASSAGES_DIR = OUTPUT_DIR / "passages"

LATEST_DIR.mkdir(parents=True, exist_ok=True)
EVENTS_DIR.mkdir(parents=True, exist_ok=True)
PASSAGES_DIR.mkdir(parents=True, exist_ok=True)


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


def _media_input_scheme(input_url):
    try:
        return urlsplit(input_url).scheme.lower()
    except Exception:
        return ""


def safe_media_input_label(input_url):
    try:
        parsed = urlsplit(input_url)
        scheme = parsed.scheme.lower()
        host = parsed.hostname
        if not scheme or not host:
            return "<configured>"
        try:
            port = parsed.port
        except ValueError:
            port = None
        authority = host if port is None else f"{host}:{port}"
        return f"{scheme}://{authority}"
    except Exception:
        return "<configured>"


def media_basic_auth_for_input(input_url):
    explicit = env_str("HLS_MEDIA_BASIC_AUTH_BASE64", "").strip()
    if explicit:
        return explicit
    if _media_input_scheme(input_url) in {"http", "https"}:
        return env_str("HLS_BASIC_AUTH_BASE64", "").strip()
    return ""


def roi_basic_auth():
    explicit = env_str("SEA_SPEED_ROI_BASIC_AUTH_BASE64", "").strip()
    if explicit:
        return explicit
    return env_str("HLS_BASIC_AUTH_BASE64", "").strip()


def _resolve_frame_size() -> tuple[int, int]:
    profile_name = env_str("ANALYTICS_PROFILE", "water-v1")
    try:
        profile = get_profile(profile_name)
        default_w, default_h = int(profile.frame_width), int(profile.frame_height)
    except Exception:
        default_w, default_h = 1920, 1080
    return env_int("FRAME_WIDTH", default_w), env_int("FRAME_HEIGHT", default_h)


def crop_sharpness(crop) -> float:
    """Laplacian variance sharpness for a BGR crop; 0 for empty."""
    try:
        if crop is None or getattr(crop, "size", 0) == 0:
            return 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except Exception:
        return 0.0


def start_ffmpeg():
    hls_url = env_str("HLS_URL")
    if not hls_url:
        raise RuntimeError("HLS_URL is not set")

    try:
        from analytics_profiles import get_profile as _get_profile

        _profile = _get_profile(env_str("ANALYTICS_PROFILE", "water-v1"))
        _default_w, _default_h = int(_profile.frame_width), int(_profile.frame_height)
    except Exception:
        _default_w, _default_h = 1920, 1080
    width = env_int("FRAME_WIDTH", _default_w)
    height = env_int("FRAME_HEIGHT", _default_h)
    sample_fps = env_float("SAMPLE_FPS", 5.0)
    auth = media_basic_auth_for_input(hls_url)

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
    print(f"HLS: {safe_media_input_label(hls_url)}")
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


def _frame_time_seconds(frame):
    pts = getattr(frame, "pts", None)
    time_base = getattr(frame, "time_base", None)
    if pts is not None and time_base is not None:
        try:
            return float(pts * time_base)
        except Exception:
            pass
    return time.monotonic()


class FFmpegFrameReader:
    def __init__(self, proc, width, height):
        self.proc = proc
        self.width = width
        self.height = height
        self.frame_size = width * height * 3

    def read_frame(self):
        raw = read_exact(self.proc.stdout, self.frame_size)
        if raw is None:
            return None
        return np.frombuffer(raw, np.uint8).reshape((self.height, self.width, 3))

    def close(self):
        try:
            self.proc.kill()
        except Exception:
            pass


class RtspFrameReader:
    def __init__(self, input_url, width, height, sample_fps, av_module=None):
        if sample_fps <= 0:
            raise RuntimeError("SAMPLE_FPS must be greater than zero")
        if av_module is None:
            try:
                import av as av_module
            except ImportError:
                raise RuntimeError("RTSP input requires the PyAV runtime dependency") from None
        self._av = av_module
        self._input_label = safe_media_input_label(input_url)
        self._width = width
        self._height = height
        self._sample_interval = 1.0 / float(sample_fps)
        self._next_sample_ts = None
        try:
            with self._av.logging.Capture(local=False):
                self._container = self._av.open(input_url, mode="r")
            self._frames = self._container.decode(video=0)
        except Exception:
            raise RuntimeError(f"RTSP media open failed: {self._input_label}") from None

    def read_frame(self):
        while True:
            try:
                with self._av.logging.Capture(local=False):
                    frame = next(self._frames)
            except StopIteration:
                return None
            except Exception:
                raise RuntimeError(f"RTSP media read failed: {self._input_label}") from None
            frame_ts = _frame_time_seconds(frame)
            if self._next_sample_ts is None:
                self._next_sample_ts = frame_ts
            if frame_ts + 1e-9 < self._next_sample_ts:
                continue
            while self._next_sample_ts <= frame_ts + 1e-9:
                self._next_sample_ts += self._sample_interval
            try:
                return frame.reformat(width=self._width, height=self._height, format="bgr24").to_ndarray()
            except Exception:
                raise RuntimeError(f"RTSP frame conversion failed: {self._input_label}") from None

    def close(self):
        try:
            self._container.close()
        except Exception:
            pass


def start_media_reader(av_module=None):
    input_url = env_str("HLS_URL")
    if not input_url:
        raise RuntimeError("HLS_URL is not set")
    width, height = _resolve_frame_size()
    sample_fps = env_float("SAMPLE_FPS", 5.0)
    if _media_input_scheme(input_url) == "rtsp":
        print("Starting in-process RTSP reader")
        print(f"HLS: {safe_media_input_label(input_url)}")
        print(f"Frame: {width}x{height}")
        print(f"Sample FPS: {sample_fps}")
        return RtspFrameReader(input_url, width, height, sample_fps, av_module=av_module)
    return FFmpegFrameReader(start_ffmpeg(), width, height)


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
        if profile is None:
            if model_class not in VEHICLE_CLASSES:
                continue
            semantic = {"class_name": model_class}
        else:
            semantic = normalize_model_class(model_class, profile.name)
            if semantic is None:
                continue
        track_id = None
        if track_ids is not None:
            try:
                track_id = int(track_ids[index].item())
            except Exception:
                track_id = None
        xyxy = box.xyxy[0].tolist()
        x1, y1, x2, y2 = [int(round(v)) for v in xyxy]
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


_roi_cache = {"ts": 0.0, "enabled": False, "points": [], "signature": ""}
_roi_processing_points = None


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
    basic_auth = roi_basic_auth()
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


def bbox_center(det):
    x1, y1, x2, y2 = det["bbox_xyxy"]
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


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


def draw_roi_polygon(frame):
    points = parse_road_roi_polygon()
    if len(points) < 3:
        return
    polygon = np.array(points, dtype=np.int32)
    cv2.polylines(frame, [polygon], True, (255, 0, 0), 2)


def format_detection_label(det):
    track_id = det.get("track_id")
    passage_id = det.get("passage_id")
    if passage_id:
        id_text = str(passage_id)
    else:
        id_text = f"ID {int(track_id)}" if track_id is not None else "ID --"
    class_name = str(det.get("class_name", "object"))
    confidence = float(det.get("confidence") or 0.0)
    speed_kmh = det.get("speed_kmh")
    speed_text = "speed: --" if speed_kmh is None else f"{float(speed_kmh):.1f} km/h"
    return f"{id_text} | {class_name} {confidence:.2f} | {speed_text}"


def overlay_label_opacity():
    configured = env_float("OVERLAY_LABEL_OPACITY", 0.38)
    return max(0.15, min(0.85, float(configured)))


def draw_overlay(frame, motion_now, motion_area, ai_active, detections, motion_boxes, crossing_summary=None):
    out = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = det["bbox_xyxy"]
        label = format_detection_label(det)
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 2
        (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
        label_x = max(0, x1)
        label_y = max(text_height + 8, y1 - 7)
        label_right = min(out.shape[1] - 1, label_x + text_width + 8)
        label_top = max(0, label_y - text_height - 7)
        label_bottom = min(out.shape[0] - 1, label_y + baseline + 2)
        label_layer = out.copy()
        cv2.rectangle(label_layer, (label_x, label_top), (label_right, label_bottom), (0, 18, 18), -1)
        opacity = overlay_label_opacity()
        cv2.addWeighted(label_layer, opacity, out, 1.0 - opacity, 0.0, dst=out)
        cv2.rectangle(out, (label_x, label_top), (label_right, label_bottom), (0, 210, 140), 1)
        cv2.putText(out, label, (label_x + 4, label_y), font, font_scale, (0, 255, 0), thickness, cv2.LINE_AA)
    active_track_ids = {int(det["track_id"]) for det in detections if det.get("track_id") is not None}
    height, width = out.shape[:2]
    lines = [
        f"motion_now: {motion_now}",
        f"motion_area: {int(motion_area)}",
        f"ai_active: {ai_active}",
        f"detections: {len(detections)}",
        f"tracks: {len(active_track_ids)}",
        f"posted_to: mostdef.ru/sea-speed",
    ]
    line_height = 25
    block_height = line_height * len(lines) + 10
    y = height - block_height + line_height - 4
    for line in lines:
        cv2.putText(out, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv2.LINE_AA)
        y += line_height
    summary = crossing_summary or {}
    if summary.get("line_enabled"):
        line_points = summary.get("line") or []
        if len(line_points) == 2:
            cv2.line(out, tuple(line_points[0]), tuple(line_points[1]), (0, 255, 255), 2, cv2.LINE_AA)
        ltr = int(summary.get("left_to_right") or 0)
        rtl = int(summary.get("right_to_left") or 0)
        counter_lines = [f"CROSSINGS -> {ltr}   <- {rtl}"]
        by_class = summary.get("by_class") or {}
        for class_name, counts in sorted(by_class.items(), key=lambda kv: -(kv[1].get("left_to_right", 0) + kv[1].get("right_to_left", 0))):
            total = int(counts.get("left_to_right", 0)) + int(counts.get("right_to_left", 0))
            counter_lines.append(f"{class_name}: {total}")
        font = cv2.FONT_HERSHEY_SIMPLEX
        c_line_height = 24
        c_block_height = c_line_height * len(counter_lines) + 10
        max_text_width = max(cv2.getTextSize(line, font, 0.58, 2)[0][0] for line in counter_lines)
        c_y = height - c_block_height + c_line_height - 4
        for line in counter_lines:
            (tw, th), baseline = cv2.getTextSize(line, font, 0.58, 2)
            layer = out.copy()
            top = max(0, c_y - th - 6)
            bottom = min(height - 1, c_y + baseline + 4)
            right = width - 10
            left = max(0, right - tw - 12)
            cv2.rectangle(layer, (left, top), (right, bottom), (0, 18, 18), -1)
            cv2.addWeighted(layer, 0.45, out, 0.55, 0.0, dst=out)
            cv2.putText(out, line, (width - 16 - tw, c_y), font, 0.58, (120, 220, 255), 2, cv2.LINE_AA)
            c_y += c_line_height
    return out


def post_state(metadata, overlay_path):
    state_url = env_str("SEA_SPEED_API_URL")
    token = env_str("SEA_SPEED_API_TOKEN")
    if not state_url or not token:
        print("POST state skipped: SEA_SPEED_API_URL or SEA_SPEED_API_TOKEN is not set")
        return False
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with open(overlay_path, "rb") as f:
            files = {"overlay": ("overlay.jpg", f, "image/jpeg")}
            data = {"metadata": json.dumps(metadata, ensure_ascii=False)}
            r = requests.post(state_url, headers=headers, data=data, files=files, timeout=10)
        if r.status_code >= 300:
            print(f"POST state failed: HTTP {r.status_code} {r.text[:300]}")
            return False
        return True
    except Exception as e:
        print(f"POST state error: {e}")
        return False


def post_event(event, snapshot_path):
    if snapshot_path is None or not Path(snapshot_path).is_file():
        print(f"POST event skipped: snapshot missing for {event.get('event_id')}")
        return False
    state_url = env_str("SEA_SPEED_API_URL")
    event_url = env_str("SEA_SPEED_EVENT_API_URL")
    if not event_url and state_url:
        event_url = state_url.rsplit("/", 1)[0] + "/events"
    token = env_str("SEA_SPEED_API_TOKEN")
    if not event_url or not token:
        print("POST event skipped: event URL or token is not set")
        return False
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with open(snapshot_path, "rb") as f:
            files = {"snapshot": ("event.jpg", f, "image/jpeg")}
            data = {"metadata": json.dumps(event, ensure_ascii=False)}
            r = requests.post(event_url, headers=headers, data=data, files=files, timeout=10)
        if r.status_code >= 300:
            print(f"POST event failed: HTTP {r.status_code} {r.text[:300]}")
            return False
        print(f'POST event ok id={event["event_id"]} class={event["class_name"]} conf={event["confidence"]:.2f}')
        return True
    except Exception as e:
        print(f"POST event error: {e}")
        return False


def post_passage(passage, snapshot_path=None):
    state_url = env_str("SEA_SPEED_API_URL")
    passage_url = env_str("SEA_SPEED_PASSAGE_API_URL", "").strip()
    if not passage_url and state_url:
        passage_url = state_url.rsplit("/", 1)[0] + "/passages"
    token = env_str("SEA_SPEED_API_TOKEN")
    if not passage_url or not token:
        print("POST passage skipped: passage URL or token is not set")
        return False
    payload = dict(passage)
    payload.setdefault("camera_id", env_str("CAMERA_ID", "cam1"))
    payload.setdefault("analytics_profile", env_str("ANALYTICS_PROFILE", "water-v1"))
    payload.setdefault("domain", "water")
    payload.setdefault("worker_source_commit", env_str("SEA_SPEED_SOURCE_COMMIT", "").strip() or None)
    headers = {"Authorization": f"Bearer {token}"}
    data = {"metadata": json.dumps(payload, ensure_ascii=False)}
    try:
        if snapshot_path is not None and Path(snapshot_path).is_file():
            with open(snapshot_path, "rb") as snapshot_file:
                files = {"snapshot": ("passage.jpg", snapshot_file, "image/jpeg")}
                response = requests.post(passage_url, headers=headers, data=data, files=files, timeout=10)
        else:
            response = requests.post(passage_url, headers=headers, data=data, timeout=10)
        if response.status_code >= 300:
            print(f"POST passage failed: HTTP {response.status_code} {response.text[:300]}")
            return False
        speed = payload.get("speed_kmh")
        speed_text = "-" if speed is None else f"{float(speed):.3f}"
        print(
            f'POST passage ok id={payload["passage_id"]} status={payload.get("status")} '
            f'speed_status={payload.get("speed_status")} speed_kmh={speed_text}'
        )
        return True
    except Exception as exc:
        print(f"POST passage error: {exc}")
        return False


def write_passage_snapshot(frame, det, path):
    x1, y1, x2, y2 = [int(value) for value in det["bbox_xyxy"]]
    height, width = frame.shape[:2]
    box_w = max(1, x2 - x1)
    box_h = max(1, y2 - y1)
    pad_x = max(4, int(round(box_w * 0.12)))
    pad_y = max(4, int(round(box_h * 0.12)))
    left = max(0, x1 - pad_x)
    top = max(0, y1 - pad_y)
    right = min(width, x2 + pad_x)
    bottom = min(height, y2 + pad_y)
    if right <= left or bottom <= top:
        return False
    crop = frame[top:bottom, left:right]
    return bool(cv2.imwrite(str(path), crop, [cv2.IMWRITE_JPEG_QUALITY, 90]))


_speed_track = {"center": None, "ts": None, "class_name": None}
_track_states = {}


def detection_center_px(det):
    x1, _y1, x2, y2 = det["bbox_xyxy"]
    return ((x1 + x2) / 2.0, y2)


def update_speed_estimate(det):
    now = time.time()
    cx, cy = detection_center_px(det)
    track_id = det.get("track_id")
    if track_id is None:
        state = _speed_track
        track_state = None
    else:
        track_id = int(track_id)
        track_state = _track_states.setdefault(track_id, {})
        track_state["last_seen"] = now
        state = track_state.setdefault("pixel_speed", {})
    info = {"center_x": round(cx, 2), "center_y": round(cy, 2), "dx_px": None, "dy_px": None, "dt_sec": None, "distance_px": None, "speed_px_s": None}
    prev_center = state.get("center")
    prev_ts = state.get("ts")
    prev_class = state.get("class_name")
    if prev_center is not None and prev_ts is not None and prev_class == det["class_name"]:
        dt = now - prev_ts
        if 0.05 <= dt <= 3.0:
            dx = cx - prev_center[0]
            dy = cy - prev_center[1]
            distance = (dx * dx + dy * dy) ** 0.5
            speed = distance / dt
            info.update({"dx_px": round(dx, 2), "dy_px": round(dy, 2), "dt_sec": round(dt, 3), "distance_px": round(distance, 2), "speed_px_s": round(speed, 2)})
    state["center"] = (cx, cy)
    state["ts"] = now
    state["class_name"] = det["class_name"]
    if track_state is not None:
        track_state["pixel_speed_info"] = dict(info)
    return info


_speed_config_cache = {"ts": 0.0, "enabled": False, "kmh_per_px_s": 0.0}


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


_speed_lines_cache = {"ts": 0.0, "enabled": False, "distance_m": 57.0, "line_a": [], "line_b": [], "signature": ""}
_line_speed_state = {"prev_center": None, "prev_ts": None, "prev_side_a": None, "prev_side_b": None, "pending": None}


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
        _speed_lines_cache.update({"enabled": enabled, "distance_m": distance_m, "line_a": line_a, "line_b": line_b, "signature": signature})
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


_crossing_line_cache = {"ts": 0.0, "enabled": False, "line": [], "signature": ""}
_crossing_track_sides = {}
_crossing_counts = {"left_to_right": 0, "right_to_left": 0}
_crossings_by_class = {}
_crossing_pending_posts = []
VLZ_TIMEZONE = timezone(timedelta(hours=10))
_crossing_vlz_date = None


def vlz_date(now=None):
    if now is None:
        now = time.time()
    return datetime.fromtimestamp(now, VLZ_TIMEZONE).date()


def reset_crossing_counts(clear_pending=True):
    _crossing_counts.update({"left_to_right": 0, "right_to_left": 0})
    _crossings_by_class.clear()
    _crossing_track_sides.clear()
    if clear_pending:
        _crossing_pending_posts.clear()


def maybe_reset_daily_crossings(now=None):
    """Reset live crossing counters at 00:00 Asia/Vladivostok (UTC+10)."""
    global _crossing_vlz_date
    today = vlz_date(now)
    if _crossing_vlz_date == today:
        return False
    _crossing_vlz_date = today
    reset_crossing_counts(clear_pending=False)
    return True


def get_crossing_line_url():
    url = env_str("SEA_SPEED_CROSSING_LINE_URL", "").strip()
    if url:
        return url
    state_url = env_str("SEA_SPEED_API_URL", "").strip()
    if not state_url:
        return ""
    # SEA_SPEED_API_URL targets the exact state path (…/api/cam1/state or
    # …/api/analytics/road1/state); drop the final segment and append the resource.
    return state_url.rsplit("/", 1)[0] + "/crossing-line"


def fetch_crossing_line_config():
    refresh_sec = env_float("CROSSING_LINE_REFRESH_SEC", 1.0)
    now = time.time()
    if now - _crossing_line_cache["ts"] < refresh_sec:
        return _crossing_line_cache
    _crossing_line_cache["ts"] = now
    url = get_crossing_line_url()
    if not url:
        _crossing_line_cache["enabled"] = False
        return _crossing_line_cache
    headers = {}
    basic_auth = env_str("HLS_BASIC_AUTH_BASE64", "").strip()
    if basic_auth:
        headers["Authorization"] = f"Basic {basic_auth}"
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code >= 300:
            print(f"Crossing line fetch failed: HTTP {r.status_code} {r.text[:160]}")
            return _crossing_line_cache
        data = r.json()
        raw_line = data.get("line") or []
        line = []
        for p in raw_line[:2]:
            if not isinstance(p, dict):
                continue
            try:
                line.append((int(round(float(p.get("x")))), int(round(float(p.get("y"))))))
            except Exception:
                continue
        enabled = bool(data.get("enabled")) and len(line) == 2
        signature = f"{enabled}:{line}"
        if signature != _crossing_line_cache.get("signature"):
            print(f"Crossing line loaded: enabled={enabled} line={line}")
        _crossing_line_cache.update({"enabled": enabled, "line": line, "signature": signature})
        return _crossing_line_cache
    except Exception as e:
        print(f"Crossing line fetch error: {e}")
        return _crossing_line_cache


def prune_crossing_tracks(now=None):
    if now is None:
        now = time.time()
    max_gap_sec = env_float("DETECTION_TRACK_MAX_GAP_SEC", 2.0)
    for track_id in list(_crossing_track_sides.keys()):
        state = _crossing_track_sides[track_id]
        if now - float(state.get("last_seen", 0.0)) > max_gap_sec:
            _crossing_track_sides.pop(track_id, None)


def update_crossing_counts(detections, now=None):
    """Detect line crossings from tracked centroids.

    Direction is derived from horizontal displacement across the line so that
    left_to_right always means the object moved rightward in frame coordinates.
    A per-track cooldown prevents double counting on centroid wobble.
    """
    if now is None:
        now = time.time()
    maybe_reset_daily_crossings(now)
    cfg = fetch_crossing_line_config()
    if not cfg.get("enabled") or len(cfg.get("line") or []) != 2:
        prune_crossing_tracks(now)
        return []
    line = cfg["line"]
    cooldown_sec = env_float("CROSSING_MIN_INTERVAL_SEC", 2.0)
    crossings = []
    for det in detections:
        track_id = det.get("track_id")
        if track_id is None:
            continue
        object_type = str(det.get("object_type") or det.get("class_name") or "object")
        x1, y1, x2, y2 = det["bbox_xyxy"]
        cx = (float(x1) + float(x2)) / 2.0
        cy = (float(y1) + float(y2)) / 2.0
        side = sign_with_deadzone(side_of_line((cx, cy), line))
        state = _crossing_track_sides.get(int(track_id))
        if state is None:
            _crossing_track_sides[int(track_id)] = {"side": side, "cx": cx, "last_seen": now, "last_cross": 0.0}
            continue
        prev_side = int(state.get("side") or 0)
        prev_cx = float(state.get("cx") or cx)
        state["last_seen"] = now
        if side == 0 or prev_side == 0 or side == prev_side:
            state["side"] = side if side != 0 else prev_side
            state["cx"] = cx
            continue
        if now - float(state.get("last_cross", 0.0)) < cooldown_sec:
            state["side"] = side
            state["cx"] = cx
            continue
        direction = "left_to_right" if cx > prev_cx else "right_to_left"
        state["side"] = side
        state["cx"] = cx
        state["last_cross"] = now
        _crossing_counts[direction] = _crossing_counts.get(direction, 0) + 1
        class_counts = _crossings_by_class.setdefault(object_type, {"left_to_right": 0, "right_to_left": 0})
        class_counts[direction] = class_counts.get(direction, 0) + 1
        crossing = {
            "track_id": int(track_id),
            "object_type": object_type,
            "class_name": object_type,
            "direction": direction,
            "confidence": det.get("confidence"),
            "speed_kmh": det.get("speed_kmh"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _crossing_pending_posts.append(crossing)
        crossings.append(crossing)
    prune_crossing_tracks(now)
    return crossings


def crossing_overlay_summary():
    line = _crossing_line_cache.get("line") or []
    return {
        "left_to_right": _crossing_counts.get("left_to_right", 0),
        "right_to_left": _crossing_counts.get("right_to_left", 0),
        "by_class": dict(_crossings_by_class),
        "line_enabled": bool(_crossing_line_cache.get("enabled")),
        "line": [list(point) for point in line],
    }


def post_crossing(crossing):
    state_url = env_str("SEA_SPEED_API_URL")
    token = env_str("SEA_SPEED_API_TOKEN")
    if not state_url or not token:
        return False
    camera_id = env_str("CAMERA_ID", "cam1").strip() or "cam1"
    url = state_url.rsplit("/", 1)[0] + "/crossings"
    payload = dict(crossing)
    payload.setdefault("camera_id", camera_id)
    payload.setdefault(
        "analytics_profile",
        env_str("ANALYTICS_PROFILE", "water-v1" if camera_id == "cam1" else "road-v1"),
    )
    payload.setdefault("domain", "water" if camera_id == "cam1" else "road")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.post(url, headers=headers, data={"metadata": json.dumps(payload, ensure_ascii=False)}, timeout=10)
        if r.status_code >= 300:
            print(f"POST crossing failed: HTTP {r.status_code} {r.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"POST crossing error: {e}")
        return False


def flush_crossing_posts(max_per_frame=4):
    posted = 0
    while _crossing_pending_posts and posted < max_per_frame:
        crossing = _crossing_pending_posts[0]
        if not post_crossing(crossing):
            break
        _crossing_pending_posts.pop(0)
        posted += 1


def update_speed_lines_estimate(det):
    cfg = fetch_speed_lines_config()
    now = time.time()
    point = detection_center_px(det)
    track_id = det.get("track_id")
    if track_id is None:
        state = _line_speed_state
        track_state = None
    else:
        track_id = int(track_id)
        track_state = _track_states.setdefault(track_id, {})
        track_state["last_seen"] = now
        track_state.setdefault("event_posted", False)
        state = track_state.setdefault("line_speed", {})
    speed_lines_enabled = bool(cfg.get("enabled"))
    info = {
        "line_speed_kmh": None,
        "speed_kmh": None,
        "speed_source": "detection_first",
        "speed_lines_enabled": speed_lines_enabled,
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
    state.setdefault("prev_point", None)
    state.setdefault("prev_progress_m", None)
    state.setdefault("prev_ts", None)
    state.setdefault("samples", [])
    state.setdefault("track_started_ts", now)
    state.setdefault("last_seen_ts", now)
    state.setdefault("display_speed_kmh", None)
    state.setdefault("display_speed_ts", None)
    max_gap_sec = env_float("DETECTION_TRACK_MAX_GAP_SEC", 2.0)
    display_hold_sec = max(0.0, env_float("DETECTION_SPEED_DISPLAY_HOLD_SEC", 2.0))
    min_dt = env_float("DETECTION_SPEED_MIN_DT_SEC", 0.05)
    max_dt = env_float("DETECTION_SPEED_MAX_DT_SEC", 1.5)
    min_kmh = env_float("DETECTION_SPEED_MIN_KMH", 1.0)
    max_kmh = env_float("DETECTION_SPEED_MAX_KMH", 180.0)
    configured_min_samples = max(1, int(env_float("DETECTION_SPEED_MIN_SAMPLES", 3)))
    min_samples = 1 if track_id is None else configured_min_samples
    smooth_samples = max(min_samples, int(env_float("DETECTION_SPEED_SMOOTH_SAMPLES", 5)))

    def median_value(values):
        ordered = sorted(float(value) for value in values)
        count = len(ordered)
        middle = count // 2
        if count % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2.0

    def update_sample_metadata():
        samples = list(state.get("samples") or [])
        info["speed_sample_count"] = len(samples)
        if not samples:
            return
        info["speed_kmh_min"] = round(min(samples), 1)
        info["speed_kmh_max"] = round(max(samples), 1)
        info["speed_kmh_avg"] = round(sum(samples) / len(samples), 1)

    def apply_held_speed():
        display_speed = state.get("display_speed_kmh")
        display_ts = state.get("display_speed_ts")
        if display_speed is None or display_ts is None:
            return False
        if now - float(display_ts) > display_hold_sec:
            return False
        display_speed = round(float(display_speed), 1)
        info.update({"line_speed_kmh": display_speed, "speed_kmh": display_speed, "speed_source": "detection_first_calibrated_held", "speed_segment_kmh": display_speed, "speed_travel_time_sec": round(now - float(state.get("track_started_ts", now)), 3), "speed_ready": True})
        update_sample_metadata()
        return True

    prev_ts = state.get("prev_ts")
    if prev_ts is not None and now - float(prev_ts) > max_gap_sec:
        state["prev_point"] = None
        state["prev_progress_m"] = None
        state["prev_ts"] = None
        state["samples"] = []
        state["track_started_ts"] = now
        state["display_speed_kmh"] = None
        state["display_speed_ts"] = None
        if track_state is not None:
            track_state["event_posted"] = False
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
        return ((float(line[0][0]) + float(line[1][0])) / 2.0, (float(line[0][1]) + float(line[1][1])) / 2.0)

    def progress_m_from_calibration(p):
        if not speed_lines_enabled or not valid_line(line_a) or not valid_line(line_b):
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
        state["prev_point"] = point
        state["prev_progress_m"] = None
        state["prev_ts"] = now
        state["last_seen_ts"] = now
        apply_held_speed()
        update_sample_metadata()
        if track_state is not None:
            track_state["line_speed_info"] = dict(info)
        return info
    prev_progress_m = state.get("prev_progress_m")
    prev_ts = state.get("prev_ts")
    if prev_progress_m is not None and prev_ts is not None:
        dt = now - float(prev_ts)
        if min_dt <= dt <= max_dt:
            dm = float(progress_m) - float(prev_progress_m)
            inst_kmh = abs(dm / dt) * 3.6
            if min_kmh <= inst_kmh <= max_kmh:
                inst_kmh = round(inst_kmh, 1)
                state["samples"].append(inst_kmh)
                if len(state["samples"]) > 120:
                    state["samples"] = state["samples"][-120:]
                samples = list(state["samples"])
                recent = samples[-smooth_samples:]
                update_sample_metadata()
                if len(samples) >= min_samples:
                    canonical_kmh = round(median_value(recent), 1)
                    state["display_speed_kmh"] = canonical_kmh
                    state["display_speed_ts"] = now
                    info.update({"line_speed_kmh": canonical_kmh, "speed_kmh": canonical_kmh, "speed_source": "detection_first_calibrated", "speed_trigger_point": "bottom_center", "speed_segment_kmh": canonical_kmh, "speed_travel_time_sec": round(now - float(state.get("track_started_ts", now)), 3), "speed_ready": True})
                    print(f"Detection-first speed track={track_id}: {canonical_kmh} km/h instant={inst_kmh} min={info['speed_kmh_min']} avg={info['speed_kmh_avg']} max={info['speed_kmh_max']} samples={len(samples)} trigger=bottom_center")
    state["prev_point"] = point
    state["prev_progress_m"] = progress_m
    state["prev_ts"] = now
    state["last_seen_ts"] = now
    if not info["speed_ready"]:
        apply_held_speed()
        update_sample_metadata()
    if track_state is not None:
        track_state["line_speed_info"] = dict(info)
    return info


def track_event_posted(track_id):
    if track_id is None:
        return False
    state = _track_states.get(int(track_id)) or {}
    return bool(state.get("event_posted"))


def mark_track_event_posted(track_id):
    if track_id is None:
        return
    state = _track_states.setdefault(int(track_id), {})
    state["event_posted"] = True


def water_event_candidates(profile, detections):
    if profile is None or profile.domain != "water":
        return []
    candidates = []
    for det in detections:
        track_id = det.get("track_id")
        if track_id is None or det.get("class_name") != "vessel":
            continue
        if not track_event_posted(track_id):
            candidates.append(det)
    return candidates


def prune_track_states(now=None):
    if now is None:
        now = time.time()
    max_gap_sec = env_float("DETECTION_TRACK_MAX_GAP_SEC", 2.0)
    stale_track_ids = []
    for track_id, state in list(_track_states.items()):
        last_seen = state.get("last_seen")
        if last_seen is None or now - float(last_seen) > max_gap_sec:
            stale_track_ids.append(track_id)
            _track_states.pop(track_id, None)
    return stale_track_ids


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
        passage_engine = WaterPassageEngine(
            lambda: build_two_gate_estimator(fetch_speed_lines_config()),
            max_observations=env_int("WATER_PASSAGE_MAX_OBSERVATIONS", 256),
            max_active_passages=env_int("WATER_PASSAGE_MAX_ACTIVE", 32),
            stitch_window_sec=env_float("WATER_PASSAGE_STITCH_GAP_SEC", 2.5),
            passage_end_gap_sec=env_float("WATER_PASSAGE_TIMEOUT_SEC", 5.0),
            stitch_distance_px=env_float("WATER_PASSAGE_STITCH_MAX_DISTANCE_PX", 120.0),
        )
        print(
            "Water passage engine: strategy=two_gate "
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
            processing_frame, roi_points = prepare_roi_processing_frame(frame, motion_detector)
            motion_now, motion_area, motion_boxes = motion_detector.process(processing_frame)
            motion_ai_active = motion_detector.is_ai_active()
            if is_water:
                ai_active = True
                detections = detect_vehicles(model, processing_frame)
            elif motion_ai_active:
                ai_active = True
                detections = detect_vehicles(model, processing_frame)
                detections = filter_detections_by_motion(detections, motion_boxes)
            else:
                ai_active = False
                detections = []
            detections = filter_detections_by_roi(detections)
            now = time.time()
            active_track_ids = {int(det["track_id"]) for det in detections if det.get("track_id") is not None}
            update_crossing_counts(detections, now)

            passage_updates = []
            if is_water and passage_engine is not None:
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

            overlay = draw_overlay(frame=frame, motion_now=motion_now, motion_area=motion_area, ai_active=ai_active, detections=detections, motion_boxes=motion_boxes, crossing_summary=crossing_overlay_summary())
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
                    "crossings": crossing_overlay_summary(),
                    "frame_no": frame_no,
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
