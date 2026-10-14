"""Sea Speed worker crossing-domain module (issue #397, wave 6).

Crossing analytics moved VERBATIM (move-only refactor, byte-identical
bodies) from hls_motion_yolo_worker_events.py: the crossing counters and
track-side maps (_crossing_track_sides/_crossing_counts/_crossings_by_class),
the VLZ (UTC+10) daily-reset state (VLZ_TIMEZONE/_crossing_vlz_date) and the
six crossing functions (vlz_date, reset_crossing_counts,
maybe_reset_daily_crossings, prune_crossing_tracks, update_crossing_counts,
crossing_overlay_summary).

Object-identity coupling with worker_transport: _crossing_line_cache and
_crossing_pending_posts are transport-OWNED objects (their defining literals
stay in worker_transport.py); this module imports them and every access is
an IN-PLACE mutation (.clear/.append/.get) or a read - nothing here may
rebind them, so the wave-4/5 identity contract holds unchanged and the
ImportFrom in this module keeps ONE object visible everywhere.

_crossing_vlz_date moved WITH its sole rebinder maybe_reset_daily_crossings
(the only ast.Global naming it sits in that def) - the pair must never be
split apart; the rebinding/rebinder-coupling guards live in
tests/test_worker_crossings_module.py.

Import policy (guarded by tests/test_worker_crossings_module.py): top-level
imports are limited to time, datetime and the repo-pure siblings
worker_kernel (env_float, side_of_line, sign_with_deadzone) and
worker_transport (the two shared crossing objects + fetch_crossing_line_config).
NO cv2/numpy/ultralytics/av, NO subprocess/socket, NO requests/json - the
crossing layer is offline except through the transport fetcher.
"""

import time
from datetime import datetime, timedelta, timezone

from worker_kernel import env_float, side_of_line, sign_with_deadzone
from worker_transport import _crossing_line_cache, _crossing_pending_posts, fetch_crossing_line_config


_crossing_track_sides = {}
_crossing_counts = {"left_to_right": 0, "right_to_left": 0}
_crossings_by_class = {}
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
        # Copy both mapping levels.  The snapshot is queued asynchronously and
        # must not retain references to live per-class count dictionaries.
        "by_class": {
            class_name: dict(counts)
            for class_name, counts in _crossings_by_class.items()
        },
        "line_enabled": bool(_crossing_line_cache.get("enabled")),
        "line": [list(point) for point in line],
    }
