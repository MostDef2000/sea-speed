"""Sea Speed worker render/snapshot layer (issue #397, wave 3).

cv2 render/snapshot code moved VERBATIM (move-only refactor, AST-identical
bodies) from hls_motion_yolo_worker_events.py: the frame overlay renderer,
the passage snapshot writer and the sharpness metric.

Import policy (guarded by tests/test_worker_render_module.py): top-level
imports are limited to the render allowlist - cv2/numpy/os/time/datetime/
pathlib/typing plus the repo-pure siblings worker_kernel (label/opacity/env
helpers) and analytics_profiles (profile detection). NO network imports are
permitted in this module (requests/ultralytics/av would fail the import
allowlist gate) - config fetches and posting stay in the runtime worker and
pass their results in as arguments or via the worker's supervision flow.
"""

import cv2

from analytics_profiles import get_profile
from worker_kernel import (
    env_str,
    format_detection_label,
    overlay_label_opacity,
)


def crop_sharpness(crop) -> float:
    """Laplacian variance sharpness for a BGR crop; 0 for empty."""
    try:
        if crop is None or getattr(crop, "size", 0) == 0:
            return 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except Exception:
        return 0.0


def draw_overlay(frame, motion_now, motion_area, ai_active, detections, motion_boxes, crossing_summary=None):
    out = frame.copy()
    # Road clean-overlay: do not bake AI boxes/IDs into JPEG, live canvas is sole source
    try:
        _profile = get_profile(env_str("ANALYTICS_PROFILE", "water-v1"))
        _is_water = getattr(_profile, "name", "") == "water-v1"
    except Exception:
        _is_water = False
    _clean = env_str("ROAD_CLEAN_OVERLAY", "1" if not _is_water else "0").strip().lower() in {"1","true","yes","on"}
    _skip_boxes = _clean and not _is_water
    if not _skip_boxes:
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
        "posted_to: mostdef.ru/sea-speed",
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
        font = cv2.FONT_HERSHEY_SIMPLEX
        c_line_height = 24
        c_block_height = c_line_height * len(counter_lines) + 10
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
