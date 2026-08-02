#!/usr/bin/env python3
"""Validate Sea Speed state or vehicle-event telemetry without external packages."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CALIBRATION_RE = re.compile(r"^sha256:[0-9a-f]{16}$")


def fail(message: str) -> None:
    raise ValueError(message)


def validate_commit(value: Any) -> None:
    if value is None or value == "unknown":
        return
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        fail("worker_source_commit must be a lowercase full Git SHA, unknown, or null")


def validate_state(payload: dict[str, Any]) -> None:
    if payload.get("state_schema") != "sea_speed_worker_state_v1":
        fail("invalid state_schema")
    if payload.get("telemetry_schema") != "sea_speed_telemetry_v1":
        fail("invalid telemetry_schema")
    validate_commit(payload.get("worker_source_commit"))
    if not isinstance(payload.get("camera_id"), str) or not payload["camera_id"]:
        fail("camera_id is required")
    frame_no = payload.get("frame_no")
    if not isinstance(frame_no, int) or isinstance(frame_no, bool) or frame_no < 0:
        fail("frame_no must be a non-negative integer")
    if not isinstance(payload.get("worker_online"), bool):
        fail("worker_online must be boolean")
    updated_at = payload.get("updated_at")
    if updated_at is not None and not isinstance(updated_at, str):
        fail("updated_at must be a string or null")


def validate_event(payload: dict[str, Any]) -> None:
    if payload.get("event_schema") != "sea_speed_vehicle_event_v1":
        fail("invalid event_schema")
    if payload.get("telemetry_schema") != "sea_speed_telemetry_v1":
        fail("invalid telemetry_schema")
    validate_commit(payload.get("worker_source_commit"))
    calibration = payload.get("calibration_version")
    if calibration is not None and (not isinstance(calibration, str) or not CALIBRATION_RE.fullmatch(calibration)):
        fail("calibration_version must be sha256:<16 hex> or null")
    for field in ("event_id", "created_at", "camera_id", "class_name"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            fail(f"{field} is required")
    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        fail("confidence must be between 0 and 1")
    speed = payload.get("speed_kmh")
    if speed is not None and (not isinstance(speed, (int, float)) or isinstance(speed, bool) or speed < 0):
        fail("speed_kmh must be non-negative or null")


def validate_payload(payload: dict[str, Any], kind: str = "auto") -> str:
    resolved = kind
    if resolved == "auto":
        if "state_schema" in payload:
            resolved = "state"
        elif "event_schema" in payload:
            resolved = "event"
        else:
            fail("cannot infer telemetry kind")
    if resolved == "state":
        validate_state(payload)
    elif resolved == "event":
        validate_event(payload)
    else:
        fail(f"unsupported telemetry kind: {resolved}")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--kind", choices=("auto", "state", "event"), default="auto")
    args = parser.parse_args()
    try:
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            fail("payload root must be an object")
        kind = validate_payload(payload, args.kind)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Sea Speed {kind} telemetry valid: {args.payload}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
