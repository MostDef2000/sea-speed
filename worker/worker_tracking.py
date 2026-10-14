"""Sea Speed worker tracking module (issue #397, wave 8).

The tracking cluster moved VERBATIM (move-only refactor, byte-identical
bodies) from hls_motion_yolo_worker_events.py: the per-track speed state
(_speed_track/_track_states/_line_speed_state) and the eight tracking defs
(detection_center_px, update_speed_estimate, convert_px_s_to_kmh,
update_speed_lines_estimate - whose nested helpers moved with it -
track_event_posted, mark_track_event_posted, water_event_candidates,
prune_track_states). draw_speed_lines_overlay STAYS in the worker (render
surface, no production callers); build_event stays in the worker and
resolves convert_px_s_to_kmh through the flat re-export.

Object-identity coupling with the worker: the three state dicts are defined
here ONCE and re-exported BY IDENTITY - nothing in the whole worker source
set rebinds them (every access is an in-place mutation or a read of the
same dicts; the strict no-rebinding/global-statement guards live in
tests/test_worker_tracking_module.py). The worker re-exports all 11 moved
names (3 state + 8 defs): the supervision main loop and build_event keep
resolving them through the worker's flat namespace.

Import policy (guarded by tests/test_worker_tracking_module.py): top-level
imports are limited to stdlib time and the repo siblings worker_kernel
(env_float) and worker_transport (fetch_speed_config,
fetch_speed_lines_config). NO cv2/numpy (the tracking math is pure Python
over detection dicts and transport-provided calibration configs), NO
datetime/threading/queue, NO ultralytics/av/subprocess/socket, NO
requests/json/pathlib/os.
"""

import time

from worker_kernel import env_float
from worker_transport import fetch_speed_config, fetch_speed_lines_config


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


_line_speed_state = {"prev_center": None, "prev_ts": None, "prev_side_a": None, "prev_side_b": None, "pending": None}


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
        "speed_instant_kmh": None,
        "speed_sample_fresh": False,
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
                info["speed_instant_kmh"] = inst_kmh
                info["speed_sample_fresh"] = True
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
