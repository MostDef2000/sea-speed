#!/usr/bin/env python3
"""Run the Sea Speed worker with additive runtime identity and telemetry fields."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
from types import ModuleType
from typing import Any

try:
    from analytics_profiles import get_profile
except ModuleNotFoundError:  # importlib-based repository tests
    from worker.analytics_profiles import get_profile

STATE_SCHEMA = "sea_speed_worker_state_v1"
EVENT_SCHEMA = "sea_speed_vehicle_event_v1"
TELEMETRY_SCHEMA = "sea_speed_telemetry_v1"
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
INSTALL_DIR = Path(__file__).resolve().parent
WORKER_PATH = INSTALL_DIR / "hls_motion_yolo_worker_events.py"
VERSION_FILE = INSTALL_DIR / ".sea-speed-worker-version"


def installed_source_commit(install_dir: Path = INSTALL_DIR) -> str:
    configured = os.environ.get("SEA_SPEED_WORKER_SOURCE_COMMIT", "").strip()
    if SHA_RE.fullmatch(configured):
        return configured.lower()

    version_file = install_dir / ".sea-speed-worker-version"
    try:
        value = version_file.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return "unknown"
    return value.lower() if SHA_RE.fullmatch(value) else "unknown"


def calibration_version(speed_config: dict[str, Any], speed_lines: dict[str, Any]) -> str:
    payload = {
        "speedConfig": {
            "enabled": bool(speed_config.get("enabled")),
            "kmhPerPxS": float(speed_config.get("kmh_per_px_s") or 0.0),
        },
        "speedLines": {
            "enabled": bool(speed_lines.get("enabled")),
            "distanceM": float(speed_lines.get("distance_m") or 0.0),
            "lineA": speed_lines.get("line_a") or [],
            "lineB": speed_lines.get("line_b") or [],
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()[:16]


def enrich_state(metadata: dict[str, Any], source_commit: str) -> dict[str, Any]:
    enriched = dict(metadata)
    enriched.setdefault("state_schema", STATE_SCHEMA)
    enriched.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    enriched.setdefault("worker_source_commit", source_commit)
    profile_name = str(enriched.get("analytics_profile") or os.environ.get("ANALYTICS_PROFILE") or "").strip()
    if profile_name:
        profile = get_profile(profile_name)
        enriched.setdefault("analytics_profile", profile.name)
        enriched.setdefault("domain", profile.domain)
        enriched.setdefault("camera_id", os.environ.get("CAMERA_ID") or profile.default_camera_id)
    return enriched


def enrich_event(event: dict[str, Any], source_commit: str, calibration: str) -> dict[str, Any]:
    enriched = dict(event)
    enriched.setdefault("event_schema", EVENT_SCHEMA)
    enriched.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    enriched.setdefault("worker_source_commit", source_commit)
    enriched.setdefault("calibration_version", calibration)
    profile_name = str(enriched.get("analytics_profile") or os.environ.get("ANALYTICS_PROFILE") or "").strip()
    if profile_name:
        profile = get_profile(profile_name)
        enriched.setdefault("analytics_profile", profile.name)
        enriched.setdefault("domain", profile.domain)
        enriched.setdefault("camera_id", os.environ.get("CAMERA_ID") or profile.default_camera_id)
        enriched.setdefault("object_type", enriched.get("class_name"))
        enriched.setdefault("model_class", enriched.get("class_name"))
    return enriched


def load_worker_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sea_speed_worker_core", WORKER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load worker module: {WORKER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_instrumentation(worker: ModuleType) -> None:
    source_commit = installed_source_commit()
    original_post_state = worker.post_state
    original_build_event = worker.build_event

    def post_state(metadata: dict[str, Any], overlay_path: Path) -> bool:
        return original_post_state(enrich_state(metadata, source_commit), overlay_path)

    def build_event(best_det: dict[str, Any], motion_area: float, speed_info=None, line_speed_info=None):
        event = original_build_event(best_det, motion_area, speed_info, line_speed_info)
        calibration = calibration_version(worker.fetch_speed_config(), worker.fetch_speed_lines_config())
        return enrich_event(event, source_commit, calibration)

    worker.post_state = post_state
    worker.build_event = build_event


def main() -> int:
    worker = load_worker_module()
    install_instrumentation(worker)
    worker.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
