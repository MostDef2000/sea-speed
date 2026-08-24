#!/usr/bin/env python3
"""Prepare protected water/road worker configuration without exposing secrets."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

SAFE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
PROFILE_KEYS = {
    "ANALYTICS_PROFILE",
    "CAMERA_ID",
    "MODEL_NAME",
    "YOLO_TRACKER",
    "YOLO_IMAGE_SIZE",
    "YOLO_CONFIDENCE",
    "SAMPLE_FPS",
}
PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if SAFE_KEY_RE.fullmatch(key):
            values[key] = value
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text("".join(f"{key}={value}\n" for key, value in sorted(values.items())), encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, path)


def road_relay_source(catalog_path: Path) -> str:
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "sea_speed_camera_preview_catalog_v1":
        raise SystemExit("ERROR unsupported camera preview catalog schema")
    entry = next((item for item in payload.get("cameras", []) if item.get("camera_id") == "road1"), None)
    if not isinstance(entry, dict):
        raise SystemExit("ERROR logical road1 is absent from protected preview catalog")
    source = str(entry.get("source") or "").strip()
    parsed = urlsplit(source)
    try:
        address = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise SystemExit("ERROR road1 catalog source must use a private IPv4 relay") from exc
    private = any(address in network for network in PRIVATE_NETWORKS)
    if parsed.scheme != "rtsp" or address.version != 4 or not private or port is None or parsed.username is not None or parsed.password is not None:
        raise SystemExit("ERROR road1 catalog source must use a sanitized private RTSP relay URL")
    if parsed.path.rstrip("/") != "/preview_road1" or parsed.query or parsed.fragment:
        raise SystemExit("ERROR road1 catalog source path mismatch")
    return source


def road_worker_api_urls(water: dict[str, str]) -> tuple[str, str]:
    """Derive road1 M2M URLs only from the protected Camera 1 private ingress."""
    raw = water.get("SEA_SPEED_API_URL", "").strip()
    parsed = urlsplit(raw)
    try:
        address = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise SystemExit("ERROR protected SEA_SPEED_API_URL must use the private worker M2M ingress") from exc
    private = any(address in network for network in PRIVATE_NETWORKS)
    if (
        parsed.scheme != "http"
        or address.version != 4
        or address.is_loopback
        or not private
        or port is None
        or not 1024 <= port <= 65535
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise SystemExit("ERROR protected SEA_SPEED_API_URL must be credential-free private HTTP IPv4:port")
    if parsed.path.rstrip("/") != "/api/cam1/state" or parsed.query or parsed.fragment:
        raise SystemExit("ERROR protected SEA_SPEED_API_URL must target exact /api/cam1/state M2M path")
    origin = f"http://{address}:{port}"
    return (
        f"{origin}/api/analytics/road1/state",
        f"{origin}/api/analytics/road1/events",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", type=Path, default=Path("/opt/sea-speed-worker"))
    parser.add_argument(
        "--preview-catalog",
        type=Path,
        default=Path("/var/lib/sea-speed-camera-preview/active/camera-preview-catalog.json"),
    )
    args = parser.parse_args()

    config_root = args.install_root / "shared/config"
    worker_env = config_root / "worker.env"
    road_env = config_root / "road-worker.env"
    if not worker_env.is_file() or worker_env.is_symlink():
        raise SystemExit("ERROR protected worker.env is missing")
    if worker_env.stat().st_mode & 0o777 != 0o600:
        raise SystemExit("ERROR worker.env must be mode 600")
    if not args.preview_catalog.is_file() or args.preview_catalog.is_symlink():
        raise SystemExit("ERROR protected preview catalog is missing")

    water = read_env(worker_env)
    token = water.get("SEA_SPEED_API_TOKEN", "")
    if not token:
        raise SystemExit("ERROR protected SEA_SPEED_API_TOKEN is missing")
    road_source = road_relay_source(args.preview_catalog)
    road_state_url, road_event_url = road_worker_api_urls(water)
    # Preserve allowlisted tuning knobs already present in protected env
    def _preserve_int(key: str, default: str) -> str:
        raw = water.get(key, "").strip()
        try:
            int(raw)
            return raw
        except Exception:
            return default

    def _preserve_float(key: str, default: str) -> str:
        raw = water.get(key, "").strip()
        try:
            float(raw)
            return raw
        except Exception:
            return default

    # Resolve HD — never propagate 704x576 legacy to Road
    def _resolve_hd(value: str | None, fallback: str) -> str:
        raw = (value or "").strip()
        if raw in {"1920", "1080", "704", "576"}:
            # explicit numeric but validate HD
            if raw in {"704", "576"}:
                return fallback
            return raw
        try:
            iv = int(raw)
            if iv in {704, 576}:
                return fallback
            return str(iv)
        except Exception:
            return fallback

    water_frame_w = _resolve_hd(water.get("FRAME_WIDTH"), "1920")
    water_frame_h = _resolve_hd(water.get("FRAME_HEIGHT"), "1080")
    # force HD if legacy
    water_frame_w = "1920" if water_frame_w in {"704", "576"} else water_frame_w
    water_frame_h = "1080" if water_frame_h in {"704", "576"} else water_frame_h

    water.update(
        {
            "ANALYTICS_PROFILE": "water-v1",
            "CAMERA_ID": "cam1",
            "MODEL_NAME": "models/yolo26x.pt",
            "YOLO_TRACKER": "bytetrack.yaml",
            "YOLO_IMAGE_SIZE": "960",
            "YOLO_CONFIDENCE": "0.15",
            "SAMPLE_FPS": _preserve_float("SAMPLE_FPS", "10"),
            "FRAME_WIDTH": water_frame_w,
            "FRAME_HEIGHT": water_frame_h,
            "YOLO_HALF": water.get("YOLO_HALF", "1").strip() or "1",
            "YOLO_CLASSES_FILTER": water.get("YOLO_CLASSES_FILTER", "0").strip() or "0",
            "MOTION_GATE_MODE": water.get("MOTION_GATE_MODE", "gated").strip() or "gated",
            "LATEST_FRAME_BOUNDED": water.get("LATEST_FRAME_BOUNDED", "1").strip() or "1",
        }
    )
    existing_road: dict[str, str] = {}
    if road_env.is_file() and not road_env.is_symlink():
        try:
            existing_road = read_env(road_env)
        except Exception:
            existing_road = {}

    def _road_float(key: str, default: str) -> str:
        # prefer already-persisted Road value; otherwise keep Water for first install
        for src in (existing_road, water):
            raw = str(src.get(key, "")).strip()
            try:
                v = float(raw)
                if 1 <= v <= 15:
                    # keep within validated range
                    return str(v).rstrip("0").rstrip(".") if "." in str(v) else str(int(v))
                # out-of-range in existing file — fall through to default
            except Exception:
                continue
        return default

    road = {
        "ANALYTICS_PROFILE": "road-v1",
        "CAMERA_ID": "road1",
        "HLS_URL": road_source,
        "SEA_SPEED_API_URL": road_state_url,
        "SEA_SPEED_EVENT_API_URL": road_event_url,
        "SEA_SPEED_API_TOKEN": token,
        "MODEL_NAME": "models/yolo26x.pt",
        "YOLO_TRACKER": "bytetrack.yaml",
        "YOLO_IMAGE_SIZE": "960",
        "YOLO_CONFIDENCE": "0.15",
        "FRAME_WIDTH": water_frame_w,
        "FRAME_HEIGHT": water_frame_h,
        "SAMPLE_FPS": _road_float("SAMPLE_FPS", "10"),
        "YOLO_HALF": (existing_road.get("YOLO_HALF", "") or water.get("YOLO_HALF", "1")).strip() or "1",
        "YOLO_CLASSES_FILTER": (existing_road.get("YOLO_CLASSES_FILTER", "") or water.get("YOLO_CLASSES_FILTER", "0")).strip() or "0",
        "MOTION_GATE_MODE": (existing_road.get("MOTION_GATE_MODE", "") or water.get("MOTION_GATE_MODE", "gated")).strip() or "gated",
        "LATEST_FRAME_BOUNDED": (existing_road.get("LATEST_FRAME_BOUNDED", "") or water.get("LATEST_FRAME_BOUNDED", "1")).strip() or "1",
    }
    write_env(road_env, road)
    write_env(worker_env, water)
    print("ANALYTICS_PROFILES_CONFIGURED=YES")
    print("WATER_PROFILE=water-v1 CAMERA_ID=cam1")
    print("ROAD_PROFILE=road-v1 CAMERA_ID=road1 SOURCE=protected_preview_relay")
    print("ROAD_API=protected_private_worker_ingress")
    print("SECRETS_DISPLAYED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
