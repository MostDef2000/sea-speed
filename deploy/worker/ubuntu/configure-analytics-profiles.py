#!/usr/bin/env python3
"""Prepare protected water/road worker configuration without exposing secrets."""
from __future__ import annotations

import argparse
import ipaddress
import math
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

# Canonical analytics profile values are owned by worker/analytics_profiles.py;
# this configure step derives its non-secret env-file defaults from that module
# and must fail closed rather than drift by carrying its own copies.
_CANONICAL_WORKER_DIR = Path(__file__).resolve().parents[3] / "worker"
if str(_CANONICAL_WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(_CANONICAL_WORKER_DIR))
try:
    import analytics_profiles
except Exception as exc:
    raise SystemExit(f"ERROR canonical analytics profile module unavailable: {exc}") from exc

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

# Issue #739: SEA_SPEED_RECORDER_* settings are operator-owned protected
# configuration. The deploy rewrites the protected env files wholesale, so it
# must carry the recorder block across instead of dropping every key the
# analytics whitelist does not name. Defaults and bounds mirror
# worker/recorder.py (_bounded_int/_bounded_float) so a preserved value is
# always one the recorder accepts unchanged; an invalid preserved value falls
# back to the safe default instead of failing the deploy.
RECORDER_PREFIX = "SEA_SPEED_RECORDER_"
RECORDER_DEFAULT_DESTINATION = "root@10.123.239.127:./"
RECORDER_DEFAULTS = {
    f"{RECORDER_PREFIX}ENABLED": "0",
    f"{RECORDER_PREFIX}SOURCE_TYPE": "hls",
    f"{RECORDER_PREFIX}HLS_URL": "",
    f"{RECORDER_PREFIX}SPOOL_DIR": "recorder-spool",
    f"{RECORDER_PREFIX}DESTINATION": RECORDER_DEFAULT_DESTINATION,
    f"{RECORDER_PREFIX}POLL_SEC": "2",
    f"{RECORDER_PREFIX}OBJECT_MAX_BYTES": "67108864",
    f"{RECORDER_PREFIX}MIN_FREE_BYTES": "12884901888",
    f"{RECORDER_PREFIX}HTTP_TIMEOUT_SEC": "30",
    f"{RECORDER_PREFIX}RSYNC_TIMEOUT_SEC": "60",
    f"{RECORDER_PREFIX}RSYNC_RETRIES": "3",
    f"{RECORDER_PREFIX}RSYNC_BACKOFF_SEC": "5",
}
RECORDER_BOUNDS = {
    f"{RECORDER_PREFIX}POLL_SEC": (0.5, 30.0, float),
    f"{RECORDER_PREFIX}OBJECT_MAX_BYTES": (1024 * 1024, 512 * 1024 * 1024, int),
    f"{RECORDER_PREFIX}MIN_FREE_BYTES": (0, 1024 * 1024 * 1024 * 1024, int),
    f"{RECORDER_PREFIX}HTTP_TIMEOUT_SEC": (1.0, 600.0, float),
    f"{RECORDER_PREFIX}RSYNC_TIMEOUT_SEC": (1.0, 3600.0, float),
    f"{RECORDER_PREFIX}RSYNC_RETRIES": (1, 20, int),
    f"{RECORDER_PREFIX}RSYNC_BACKOFF_SEC": (0.0, 300.0, float),
}
_RECORDER_HOST_RE = re.compile(r"(?:[A-Za-z0-9._-]+@)?[A-Za-z0-9.-]+")
_RECORDER_SPOOL_RE = re.compile(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*")


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


def _recorder_number(key: str, raw: str) -> str:
    """Return a preserved numeric recorder value that is inside its bounds."""
    default = RECORDER_DEFAULTS[key]
    low, high, kind = RECORDER_BOUNDS[key]
    try:
        value = kind(raw.strip())
    except (TypeError, ValueError):
        return default
    if kind is float and not math.isfinite(value):
        return default
    if not low <= value <= high:
        return default
    return raw.strip()


def _recorder_choice(raw: str, allowed: set[str], default: str) -> str:
    value = raw.strip().lower()
    return value if value in allowed else default


def _recorder_hls_url(raw: str) -> str:
    """Preserve only an explicit HTTP(S) playlist URL; never echo it."""
    value = raw.strip()
    if not value or any(character.isspace() for character in value):
        return RECORDER_DEFAULTS[f"{RECORDER_PREFIX}HLS_URL"]
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return RECORDER_DEFAULTS[f"{RECORDER_PREFIX}HLS_URL"]
    return value


def _recorder_spool_dir(raw: str) -> str:
    """Preserve only a relative spool path under the service WorkingDirectory."""
    default = RECORDER_DEFAULTS[f"{RECORDER_PREFIX}SPOOL_DIR"]
    value = raw.strip()
    if not _RECORDER_SPOOL_RE.fullmatch(value):
        return default
    if any(part in {".", ".."} for part in value.split("/")):
        return default
    return value


def _recorder_destination(raw: str) -> str:
    """Preserve only a RELATIVE rsync target.

    The dacha endpoint runs the restricted ``rrsync -wo
    /mnt/fleet-backup/sea-speed``, which already pins the writable root. An
    absolute destination is appended to that root and doubled by rrsync, so
    only a relative path is accepted; anything else falls back to the safe
    relative default.
    """
    value = raw.strip()
    host, separator, path = value.partition(":")
    if (
        not separator
        or not _RECORDER_HOST_RE.fullmatch(host)
        or not path
        or path.startswith("/")
        or ":" in path
        or any(character.isspace() for character in path)
        or any(part == ".." for part in path.split("/"))
    ):
        return RECORDER_DEFAULT_DESTINATION
    return value


def preserved_recorder_env(source: dict[str, str]) -> dict[str, str]:
    """Carry the validated recorder block of one protected env file forward.

    Known keys are always present (preserved-or-safe-default), unknown
    ``SEA_SPEED_RECORDER_*`` extras are preserved verbatim, and no value is
    ever printed. A malformed preserved value never aborts the deploy.
    """
    preserved = {
        key: value
        for key, value in source.items()
        if key.startswith(RECORDER_PREFIX) and key not in RECORDER_DEFAULTS
    }
    preserved[f"{RECORDER_PREFIX}ENABLED"] = _recorder_choice(
        source.get(f"{RECORDER_PREFIX}ENABLED", ""),
        {"0", "1"},
        RECORDER_DEFAULTS[f"{RECORDER_PREFIX}ENABLED"],
    )
    preserved[f"{RECORDER_PREFIX}SOURCE_TYPE"] = _recorder_choice(
        source.get(f"{RECORDER_PREFIX}SOURCE_TYPE", ""),
        {"hls", "rtsp"},
        RECORDER_DEFAULTS[f"{RECORDER_PREFIX}SOURCE_TYPE"],
    )
    preserved[f"{RECORDER_PREFIX}HLS_URL"] = _recorder_hls_url(
        source.get(f"{RECORDER_PREFIX}HLS_URL", "")
    )
    preserved[f"{RECORDER_PREFIX}SPOOL_DIR"] = _recorder_spool_dir(
        source.get(f"{RECORDER_PREFIX}SPOOL_DIR", "")
    )
    preserved[f"{RECORDER_PREFIX}DESTINATION"] = _recorder_destination(
        source.get(f"{RECORDER_PREFIX}DESTINATION", "")
    )
    for key in RECORDER_BOUNDS:
        preserved[key] = _recorder_number(key, source.get(key, ""))
    return preserved


def road_relay_source(road_relay_url: str) -> str:
    """Validate the operator-supplied permanent road1 relay URL (issue #637).

    The road worker pulls the permanent relay path directly: scheme rtsp,
    private RFC1918 IPv4 host with explicit port, no credentials (reader
    authorization is IP-based on the relay), exact /road1 path.
    """
    source = str(road_relay_url or "").strip()
    parsed = urlsplit(source)
    try:
        address = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise SystemExit("ERROR road relay URL must use a private IPv4 relay") from exc
    private = any(address in network for network in PRIVATE_NETWORKS)
    if parsed.scheme != "rtsp" or address.version != 4 or not private or port is None or parsed.username is not None or parsed.password is not None:
        raise SystemExit("ERROR road relay URL must be a sanitized private RTSP relay URL")
    if parsed.path.rstrip("/") != "/road1" or parsed.query or parsed.fragment:
        raise SystemExit("ERROR road relay URL path mismatch")
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


def derived_profile_defaults() -> dict[str, dict[str, str]]:
    """Derive water/road env-file defaults from the canonical profile module."""
    return {
        profile_name: analytics_profiles.get_profile(profile_name).env_file_defaults()
        for profile_name in ("water-v1", "road-v1")
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", type=Path, default=Path("/opt/sea-speed-worker"))
    parser.add_argument("--road-relay-url", required=True)
    args = parser.parse_args()

    config_root = args.install_root / "shared/config"
    worker_env = config_root / "worker.env"
    road_env = config_root / "road-worker.env"
    if not worker_env.is_file() or worker_env.is_symlink():
        raise SystemExit("ERROR protected worker.env is missing")
    if worker_env.stat().st_mode & 0o777 != 0o600:
        raise SystemExit("ERROR worker.env must be mode 600")

    water = read_env(worker_env)
    token = water.get("SEA_SPEED_API_TOKEN", "")
    if not token:
        raise SystemExit("ERROR protected SEA_SPEED_API_TOKEN is missing")
    road_source = road_relay_source(args.road_relay_url)
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

    water_defaults = derived_profile_defaults()["water-v1"]
    water.update(
        {
            **water_defaults,
            # Issue #739: protected recorder settings survive the rewrite.
            **preserved_recorder_env(water),
            "SAMPLE_FPS": _preserve_float("SAMPLE_FPS", water_defaults["SAMPLE_FPS"]),
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

    road_defaults = derived_profile_defaults()["road-v1"]
    road = {
        **road_defaults,
        # Issue #739: the Road worker keeps its own recorder block; a missing
        # key falls back to the same safe default as the Water worker.
        **preserved_recorder_env(existing_road),
        "HLS_URL": road_source,
        "SEA_SPEED_API_URL": road_state_url,
        "SEA_SPEED_EVENT_API_URL": road_event_url,
        "SEA_SPEED_API_TOKEN": token,
        "FRAME_WIDTH": water_frame_w,
        "FRAME_HEIGHT": water_frame_h,
        "SAMPLE_FPS": _road_float("SAMPLE_FPS", road_defaults["SAMPLE_FPS"]),
        "YOLO_HALF": (existing_road.get("YOLO_HALF", "") or water.get("YOLO_HALF", "1")).strip() or "1",
        "YOLO_CLASSES_FILTER": (existing_road.get("YOLO_CLASSES_FILTER", "") or water.get("YOLO_CLASSES_FILTER", "0")).strip() or "0",
        "MOTION_GATE_MODE": (existing_road.get("MOTION_GATE_MODE", "") or water.get("MOTION_GATE_MODE", "gated")).strip() or "gated",
        "LATEST_FRAME_BOUNDED": (existing_road.get("LATEST_FRAME_BOUNDED", "") or water.get("LATEST_FRAME_BOUNDED", "1")).strip() or "1",
    }
    write_env(road_env, road)
    write_env(worker_env, water)
    print("ANALYTICS_PROFILES_CONFIGURED=YES")
    print("WATER_PROFILE=water-v1 CAMERA_ID=cam1")
    print("ROAD_PROFILE=road-v1 CAMERA_ID=road1 SOURCE=permanent_relay_road1")
    print("ROAD_API=protected_private_worker_ingress")
    print("RECORDER_CONFIG_PRESERVED=YES")
    print("SECRETS_DISPLAYED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
