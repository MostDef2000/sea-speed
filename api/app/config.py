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
from pathlib import Path

__all__ = [
    "BASE_DIR",
    "DATA_DIR",
    "MEDIA_DIR",
    "OVERLAY_DIR",
    "EVENTS_MEDIA_DIR",
    "PASSAGES_MEDIA_DIR",
    "PASSAGE_MEDIA_DIR",
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
    "CAMERA_CATALOG_SCHEMA",
    "API_TOKEN",
    "EDGE_AUTH_SECRET",
    "ADMIN_USERS",
    "OPERATOR_USERS",
    "WORKER_CONTROL_TOKEN",
    "WORKER_CONTROL_URL",
    "WORKER_CONTROL_PROTOCOL",
    "API_SCHEMA",
    "WORKER_STATE_SCHEMA",
    "VEHICLE_EVENT_SCHEMA",
    "TELEMETRY_SCHEMA",
    "OBJECT_STATUSES",
    "OBJECTS_RETENTION_LIMIT",
    "PASSAGES_RETENTION_LIMIT",
    "PASSAGE_STATUSES",
    "PASSAGE_SPEED_STATUSES",
    "PASSAGE_ID_RE",
    "SHA_RE",
    "RFC1918_NETWORKS",
    "WORKER_CONTROL_TIMEOUT_SEC",
]


# Issue #582: SEA_SPEED_BASE_DIR redirects the whole data/media tree (every
# derived path below keeps deriving from BASE_DIR, and the import-time
# mkdirs land in the override target). Unset behavior is byte-for-byte
# identical to the pre-#582 hardcoded default; the override exists so the
# HTTP-integration tests can boot the real app against a disposable root.
BASE_DIR = Path(os.environ.get("SEA_SPEED_BASE_DIR", "/opt/sea-speed-api"))
DATA_DIR = BASE_DIR / "data"
MEDIA_DIR = BASE_DIR / "media"
OVERLAY_DIR = MEDIA_DIR / "overlays"
EVENTS_MEDIA_DIR = MEDIA_DIR / "events"
PASSAGES_MEDIA_DIR = MEDIA_DIR / "passages"
PASSAGE_MEDIA_DIR = PASSAGES_MEDIA_DIR
DEPLOYED_COMMIT_FILE = Path(
    os.environ.get(
        "SEA_SPEED_DEPLOYED_COMMIT_FILE",
        "/opt/sea-speed-deploy/state/current-release",
    )
)

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
# Issue #637: the camera catalog is static — both cameras play permanent
# protected HLS streams; the on-demand preview catalog file is gone.
CAMERA_CATALOG_SCHEMA = "sea_speed_camera_catalog_v1"


def _parse_user_set(env_name: str) -> frozenset:
    """Parse a whitespace/comma-separated username list (issue #530).

    Tokens are compared exactly and case-sensitively by consumers; empty
    tokens are discarded so unset, blank or only-separator values yield an
    empty set. Any whitespace run or comma is a separator, so a username
    containing whitespace cannot be represented in a list.
    """
    raw = os.environ.get(env_name, "")
    return frozenset(token for token in re.split(r"[,\s]+", raw) if token)


ADMIN_USERS = _parse_user_set("SEA_SPEED_ADMIN_USERS")
OPERATOR_USERS = _parse_user_set("SEA_SPEED_OPERATOR_USERS")

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
OBJECT_STATUSES = {"new", "reviewed", "ignored"}
OBJECTS_RETENTION_LIMIT = 100
PASSAGES_RETENTION_LIMIT = 300
PASSAGE_STATUSES = {"tracking", "measuring", "measured", "completed"}
PASSAGE_SPEED_STATUSES = {"unknown", "measuring", "measured", "incomplete"}
PASSAGE_ID_RE = re.compile(r"^P-[A-Za-z0-9][A-Za-z0-9._-]{1,78}$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
# Worker-control origin validation (identity.py): the worker control URL host
# must be a private RFC1918 IPv4 address. Formerly CAMERA_PREVIEW_RFC1918.
RFC1918_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
DATA_DIR.mkdir(parents=True, exist_ok=True)
OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
EVENTS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
PASSAGES_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
