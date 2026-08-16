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
    water.update(
        {
            "ANALYTICS_PROFILE": "water-v1",
            "CAMERA_ID": "cam1",
            "MODEL_NAME": "models/yolo26x.pt",
            "YOLO_TRACKER": "bytetrack.yaml",
            "YOLO_IMAGE_SIZE": "960",
            "YOLO_CONFIDENCE": "0.15",
            "SAMPLE_FPS": "5",
        }
    )
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
        "FRAME_WIDTH": water.get("FRAME_WIDTH", "704"),
        "FRAME_HEIGHT": water.get("FRAME_HEIGHT", "576"),
        "SAMPLE_FPS": "5",
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
