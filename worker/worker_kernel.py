"""Sea Speed worker kernel — wave-1 pure helpers (issue #397, wave 1).

Functions moved VERBATIM (move-only refactor, AST-identical bodies) from
hls_motion_yolo_worker_events.py so the #397 decomposition can evolve the
runtime worker separately from these pure helpers.

STDLIB-ONLY contract: this module must stay importable in a bare CPython
environment (no cv2/numpy/requests/ultralytics). The runtime worker
re-exports every name below at module level, preserving main() global-name
resolution and the test monkeypatch surface. Guardianship:
tests/test_worker_kernel_module.py.
"""

import os
from datetime import datetime, timezone
from urllib.parse import urlsplit


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


def is_motion_gate_always_on() -> bool:
    """Road motion gate mode — always_on bypasses motion gating for recall."""
    mode = env_str("MOTION_GATE_MODE", env_str("ROAD_MOTION_GATE_MODE", "gated")).strip().lower()
    return mode in {"always_on", "always-on", "1", "true", "yes"}


def is_yolo_half_enabled() -> bool:
    return env_str("YOLO_HALF", "0").strip().lower() in {"1", "true", "yes", "on"}


def is_yolo_classes_filter_enabled() -> bool:
    if env_str("YOLO_CLASSES_FILTER", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return bool(env_str("YOLO_CLASSES", "").strip())


def water_recall_diagnostics_enabled() -> bool:
    return env_str("WATER_RECALL_DIAGNOSTICS", "1").strip().lower() not in {"0", "false", "no", "off"}


def _scale_norm_points(norm_points, dst_w: int, dst_h: int):
    scaled = []
    for p in norm_points or []:
        if not isinstance(p, dict):
            continue
        try:
            xn = float(p.get("x_norm", p.get("x", 0)))
            yn = float(p.get("y_norm", p.get("y", 0)))
            # detect legacy absolute mistakenly passed as norm: values >1.0 are absolute, skip as not normalized
            if xn > 1.0 or yn > 1.0:
                continue
            scaled.append((int(round(xn * dst_w)), int(round(yn * dst_h))))
        except Exception:
            continue
    return scaled


def _maybe_scale_legacy_absolute(points, dst_w: int, dst_h: int):
    """Fallback for legacy absolute polygons recorded on 704×576."""
    if not points:
        return points
    max_x = max(x for x, _ in points)
    max_y = max(y for _, y in points)
    if max_x <= 704 and max_y <= 576 and (dst_w == 1920 or dst_h == 1080):
        # heuristic: legacy 704×576 → scale to HD
        return [(int(round(x * dst_w / 704)), int(round(y * dst_h / 576))) for x, y in points]
    return points


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


def get_roi_url():
    url = env_str("SEA_SPEED_ROI_URL", "").strip()
    if url:
        return url
    state_url = env_str("SEA_SPEED_API_URL", "").strip()
    if state_url:
        return state_url.rsplit("/", 1)[0] + "/roi"
    return ""


def bbox_center(det):
    x1, y1, x2, y2 = det["bbox_xyxy"]
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


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


def get_speed_config_url():
    url = env_str("SEA_SPEED_SPEED_CONFIG_URL", "").strip()
    if url:
        return url
    state_url = env_str("SEA_SPEED_API_URL", "").strip()
    if state_url:
        return state_url.rsplit("/", 1)[0] + "/speed-config"
    return ""


def get_speed_lines_url():
    url = env_str("SEA_SPEED_SPEED_LINES_URL", "").strip()
    if url:
        return url
    state_url = env_str("SEA_SPEED_API_URL", "").strip()
    if state_url:
        return state_url.rsplit("/", 1)[0] + "/speed-lines"
    return ""


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
