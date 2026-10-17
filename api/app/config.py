"""Shared configuration kernel for the Sea Speed API (issue #396, wave 1).

Paths, environment-derived knobs and validation constants, extracted
verbatim from ``api/app/main.py``. Standard library only; no module in this
package may import ``main`` (import-cycle rule).

Exactly-one-owner decision: the import-time creation of the data and media
directories lives HERE at module top, and ``main.py`` imports this module
first (before creating the FastAPI app or mounting /media), so the boot
side effects run exactly once and in the same order as before the
extraction.

Single canonical import identity: consumers must import this module through
the same dual idiom ``main.py`` uses for the store seam (relative
``from . import config`` in package context; sys.path-anchored absolute
``import config`` for direct-file loads) so one process never holds two
module instances with two independent sets of module globals.
"""

import ipaddress
import os
import re
import threading
from pathlib import Path

__all__ = [
    "BASE_DIR",
    "DATA_DIR",
    "MEDIA_DIR",
    "OVERLAY_DIR",
    "EVENTS_MEDIA_DIR",
    "PASSAGES_MEDIA_DIR",
    "PASSAGE_MEDIA_DIR",
    "CAMERA_PREVIEW_DIR",
    "CAMERA_SNAPSHOT_DIR",
    "DEPLOYED_COMMIT_FILE",
    "STATE_FILE",
    "EVENTS_FILE",
    "OBJECTS_DB_FILE",
    "PASSAGES_DB_FILE",
    "STATE_DB_FILE",
    "EVENTS_FEED_LIMIT",
    "CROSSINGS_STORE_LIMIT",
    "ROI_FILE",
    "SPEED_CONFIG_FILE",
    "SPEED_LINES_FILE",
    "ANALYTICS_IDENTITIES",
    "CAMERA_PREVIEW_CATALOG_FILE",
    "CAMERA_PREVIEW_STATE_FILE",
    "CAMERA_PREVIEW_FFMPEG_BIN",
    "API_TOKEN",
    "EDGE_AUTH_SECRET",
    "WORKER_CONTROL_TOKEN",
    "WORKER_CONTROL_URL",
    "WORKER_CONTROL_PROTOCOL",
    "API_SCHEMA",
    "WORKER_STATE_SCHEMA",
    "VEHICLE_EVENT_SCHEMA",
    "TELEMETRY_SCHEMA",
    "CAMERA_PREVIEW_CATALOG_SCHEMA",
    "OBJECT_STATUSES",
    "OBJECTS_RETENTION_LIMIT",
    "PASSAGES_RETENTION_LIMIT",
    "PASSAGE_STATUSES",
    "PASSAGE_SPEED_STATUSES",
    "PASSAGE_ID_RE",
    "SHA_RE",
    "CAMERA_PREVIEW_ID_RE",
    "CAMERA_PREVIEW_SESSION_RE",
    "CAMERA_PREVIEW_RFC1918",
    "CAMERA_PREVIEW_LOCK",
    "CAMERA_PREVIEW_START_TIMEOUT_SEC",
    "CAMERA_SNAPSHOT_EXTRACT_TIMEOUT_SEC",
    "CAMERA_SNAPSHOT_MIN_BYTES",
    "CAMERA_SNAPSHOT_MIN_LUMA_SPREAD",
    "WORKER_CONTROL_TIMEOUT_SEC",
    "CAMERA_PREVIEW_TTL_SEC",
]


BASE_DIR = Path("/opt/sea-speed-api")
DATA_DIR = BASE_DIR / "data"
MEDIA_DIR = BASE_DIR / "media"
OVERLAY_DIR = MEDIA_DIR / "overlays"
EVENTS_MEDIA_DIR = MEDIA_DIR / "events"
PASSAGES_MEDIA_DIR = MEDIA_DIR / "passages"
PASSAGE_MEDIA_DIR = PASSAGES_MEDIA_DIR
CAMERA_PREVIEW_DIR = MEDIA_DIR / "camera-preview"
CAMERA_SNAPSHOT_DIR = DATA_DIR / "camera-preview-snapshots"
DEPLOYED_COMMIT_FILE = Path("/opt/sea-speed-deploy/state/current-release")

STATE_FILE = DATA_DIR / "cam1_state.json"
EVENTS_FILE = DATA_DIR / "events.json"
OBJECTS_DB_FILE = DATA_DIR / "objects.sqlite3"
PASSAGES_DB_FILE = DATA_DIR / "water_passages.sqlite3"
STATE_DB_FILE = DATA_DIR / "state.sqlite3"
EVENTS_FEED_LIMIT = 500
CROSSINGS_STORE_LIMIT = 5000
ROI_FILE = DATA_DIR / "cam1_roi.json"
SPEED_CONFIG_FILE = DATA_DIR / "cam1_speed_config.json"
SPEED_LINES_FILE = DATA_DIR / "cam1_speed_lines.json"
ANALYTICS_IDENTITIES = {
    "cam1": {"analytics_profile": "water-v1", "domain": "water"},
    "road1": {"analytics_profile": "road-v1", "domain": "road"},
}
CAMERA_PREVIEW_CATALOG_FILE = Path(
    os.environ.get(
        "SEA_SPEED_CAMERA_PREVIEW_CATALOG",
        str(DATA_DIR / "camera-preview-catalog.json"),
    )
)
CAMERA_PREVIEW_STATE_FILE = DATA_DIR / "camera-preview-state.json"
CAMERA_PREVIEW_FFMPEG_BIN = os.environ.get("SEA_SPEED_CAMERA_PREVIEW_FFMPEG", "/usr/bin/ffmpeg")

API_TOKEN = os.environ.get("SEA_SPEED_API_TOKEN", "")
EDGE_AUTH_SECRET = os.environ.get("SEA_SPEED_EDGE_AUTH_SECRET", "")
WORKER_CONTROL_TOKEN = os.environ.get("SEA_SPEED_WORKER_CONTROL_TOKEN", "")
WORKER_CONTROL_URL = os.environ.get(
    "SEA_SPEED_WORKER_CONTROL_URL", "http://10.123.239.102:19001"
).strip()
try:
    WORKER_CONTROL_TIMEOUT_SEC = max(
        1.0,
        min(float(os.environ.get("SEA_SPEED_WORKER_CONTROL_TIMEOUT_SEC", "3")), 5.0),
    )
except ValueError:
    WORKER_CONTROL_TIMEOUT_SEC = 3.0
WORKER_CONTROL_PROTOCOL = "sea_speed_worker_control_v1"
API_SCHEMA = "sea_speed_api_v1"
WORKER_STATE_SCHEMA = "sea_speed_worker_state_v1"
VEHICLE_EVENT_SCHEMA = "sea_speed_vehicle_event_v1"
TELEMETRY_SCHEMA = "sea_speed_telemetry_v1"
CAMERA_PREVIEW_CATALOG_SCHEMA = "sea_speed_camera_preview_catalog_v1"
OBJECT_STATUSES = {"new", "reviewed", "ignored"}
OBJECTS_RETENTION_LIMIT = 100
PASSAGES_RETENTION_LIMIT = 300
PASSAGE_STATUSES = {"tracking", "measuring", "measured", "completed"}
PASSAGE_SPEED_STATUSES = {"unknown", "measuring", "measured", "incomplete"}
PASSAGE_ID_RE = re.compile(r"^P-[A-Za-z0-9][A-Za-z0-9._-]{1,78}$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
CAMERA_PREVIEW_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
CAMERA_PREVIEW_SESSION_RE = re.compile(r"^[0-9a-f]{12}$")
CAMERA_PREVIEW_RFC1918 = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
CAMERA_PREVIEW_LOCK = threading.Lock()
try:
    CAMERA_PREVIEW_TTL_SEC = max(
        30,
        min(int(os.environ.get("SEA_SPEED_CAMERA_PREVIEW_TTL_SEC", "120")), 600),
    )
except ValueError:
    CAMERA_PREVIEW_TTL_SEC = 120
CAMERA_PREVIEW_START_TIMEOUT_SEC = 12
CAMERA_SNAPSHOT_EXTRACT_TIMEOUT_SEC = 8
CAMERA_SNAPSHOT_MIN_BYTES = 4096
CAMERA_SNAPSHOT_MIN_LUMA_SPREAD = 12.0
DATA_DIR.mkdir(parents=True, exist_ok=True)
OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
EVENTS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
PASSAGES_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
CAMERA_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
CAMERA_SNAPSHOT_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
