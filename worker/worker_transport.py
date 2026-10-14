"""Sea Speed worker requests transport/posting layer (issue #397, wave 4).

requests transport code moved VERBATIM (move-only refactor, AST-identical
bodies) from hls_motion_yolo_worker_events.py: the remote ROI/config fetchers,
the state/event/passage posters, and their module-level TTL cache dicts.

Import policy (guarded by tests/test_worker_transport_module.py): top-level
imports are limited to the transport allowlist - requests (REQUIRED: this
module owns the network surface) plus json/time/pathlib and the repo-pure
siblings worker_kernel (env readers, API URL builders, ROI geometry scaling)
and worker_media (_resolve_frame_size, the frame-size resolver the fetchers
scale fetched geometry against, moved here in wave 2). NO cv2/numpy/
ultralytics/av and NO subprocess/socket - drawing, model inference and
process spawning stay in their own layers.

Cache identity contract: _roi_cache, _speed_lines_cache and
_crossing_line_cache move WITH their fetchers and are re-exported to the
runtime worker. Every access anywhere is an IN-PLACE mutation (item
assignment / dict.update / .get) - verified by the wave-4 rebinding audit
(AST walk: zero Assign(Name(cache)) outside the moved literals) - so the
ImportFrom re-export keeps ONE object visible under both module namespaces;
staying readers (e.g. crossing_overlay_summary reading _crossing_line_cache)
observe mover mutations and vice versa. Nothing may rebind these names.
"""

import json
import time
from pathlib import Path

import requests

from worker_kernel import (
    env_float,
    env_str,
    get_crossing_line_url,
    get_roi_url,
    get_speed_lines_url,
    roi_basic_auth,
    _maybe_scale_legacy_absolute,
    _scale_norm_points,
)
from worker_media import _resolve_frame_size


_roi_cache = {"ts": 0.0, "enabled": False, "points": [], "signature": ""}


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
        dst_w, dst_h = _resolve_frame_size()
        # prefer normalized 0..1 geometry
        norm = data.get("polygon_norm")
        if isinstance(norm, list) and norm and any(isinstance(p, dict) and ("x_norm" in p or "y_norm" in p) for p in norm):
            points = _scale_norm_points(norm, dst_w, dst_h)
        else:
            raw_points = data.get("polygon", [])
            points = []
            if isinstance(raw_points, list):
                for p in raw_points:
                    if not isinstance(p, dict):
                        continue
                    # allow norm inside legacy polygon as fallback
                    if "x_norm" in p or "y_norm" in p:
                        try:
                            points.append((int(round(float(p.get("x_norm", 0)) * dst_w)), int(round(float(p.get("y_norm", 0)) * dst_h))))
                        except Exception:
                            continue
                        continue
                    try:
                        x = int(round(float(p.get("x"))))
                        y = int(round(float(p.get("y"))))
                    except Exception:
                        continue
                    points.append((x, y))
            # legacy absolute recorded on 704×576 → scale to current HD
            points = _maybe_scale_legacy_absolute(points, dst_w, dst_h)
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


_speed_lines_cache = {"ts": 0.0, "enabled": False, "distance_m": 57.0, "line_a": [], "line_b": [], "signature": ""}


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
        dst_w, dst_h = _resolve_frame_size()

        def clean_line(raw, raw_norm=None):
            # prefer normalized
            if isinstance(raw_norm, list) and raw_norm and any(isinstance(p, dict) and ("x_norm" in p or "y_norm" in p) for p in raw_norm):
                return _scale_norm_points(raw_norm, dst_w, dst_h)
            points = []
            if isinstance(raw, list):
                for p in raw[:2]:
                    if not isinstance(p, dict):
                        continue
                    if "x_norm" in p or "y_norm" in p:
                        try:
                            points.append((int(round(float(p.get("x_norm", 0)) * dst_w)), int(round(float(p.get("y_norm", 0)) * dst_h))))
                        except Exception:
                            continue
                        continue
                    try:
                        points.append((int(round(float(p.get("x")))), int(round(float(p.get("y"))))))
                    except Exception:
                        continue
            # legacy fallback
            return _maybe_scale_legacy_absolute(points, dst_w, dst_h)

        line_a = clean_line(data.get("line_a", []), data.get("line_a_norm"))
        line_b = clean_line(data.get("line_b", []), data.get("line_b_norm"))
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


_crossing_line_cache = {"ts": 0.0, "enabled": False, "line": [], "signature": ""}


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
        dst_w, dst_h = _resolve_frame_size()
        norm = data.get("line_norm") or data.get("polygon_norm")
        if isinstance(norm, list) and norm and any(isinstance(p, dict) and ("x_norm" in p or "y_norm" in p) for p in norm):
            line = _scale_norm_points(norm, dst_w, dst_h)
        else:
            raw_line = data.get("line") or []
            line = []
            for p in raw_line[:2]:
                if not isinstance(p, dict):
                    continue
                if "x_norm" in p or "y_norm" in p:
                    try:
                        line.append((int(round(float(p.get("x_norm", 0)) * dst_w)), int(round(float(p.get("y_norm", 0)) * dst_h))))
                    except Exception:
                        continue
                    continue
                try:
                    line.append((int(round(float(p.get("x")))), int(round(float(p.get("y"))))))
                except Exception:
                    continue
            line = _maybe_scale_legacy_absolute(line, dst_w, dst_h)
        enabled = bool(data.get("enabled")) and len(line) == 2
        signature = f"{enabled}:{line}"
        if signature != _crossing_line_cache.get("signature"):
            print(f"Crossing line loaded: enabled={enabled} line={line}")
        _crossing_line_cache.update({"enabled": enabled, "line": line, "signature": signature})
        return _crossing_line_cache
    except Exception as e:
        print(f"Crossing line fetch error: {e}")
        return _crossing_line_cache
