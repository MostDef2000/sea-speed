import hashlib
import http.client
import ipaddress
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


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

app = FastAPI(title="Sea Speed API")
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def deployed_source_commit() -> str:
    configured = os.environ.get("SEA_SPEED_SOURCE_COMMIT", "").strip()
    if SHA_RE.fullmatch(configured):
        return configured.lower()
    try:
        value = DEPLOYED_COMMIT_FILE.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return "unknown"
    return value.lower() if SHA_RE.fullmatch(value) else "unknown"


def require_auth(authorization: Optional[str]) -> None:
    if not API_TOKEN:
        raise HTTPException(status_code=500, detail="SEA_SPEED_API_TOKEN is not set")
    expected = f"Bearer {API_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


def require_operator_identity(x_authentik_username: Optional[str]) -> str:
    username = (x_authentik_username or "").strip()
    if not username:
        raise HTTPException(status_code=503, detail="Trusted Authentik identity is unavailable")
    return username


def worker_control_origin() -> tuple[str, int]:
    parsed = urlsplit(WORKER_CONTROL_URL)
    if parsed.scheme != "http" or parsed.username or parsed.password:
        raise HTTPException(status_code=503, detail="Worker control origin is invalid")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise HTTPException(status_code=503, detail="Worker control origin is invalid")
    if not parsed.hostname or parsed.port is None:
        raise HTTPException(status_code=503, detail="Worker control origin is invalid")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Worker control origin is invalid") from exc
    if (
        address.version != 4
        or address.is_loopback
        or not any(address in network for network in CAMERA_PREVIEW_RFC1918)
        or not 1024 <= parsed.port <= 65535
    ):
        raise HTTPException(status_code=503, detail="Worker control origin is invalid")
    return str(address), parsed.port


def call_worker_control(method: str, path: str) -> Dict[str, Any]:
    allowed = {
        ("GET", "/v1/status"),
        ("POST", "/v1/start"),
        ("POST", "/v1/stop"),
        ("GET", "/v1/road1/status"),
        ("POST", "/v1/road1/start"),
        ("POST", "/v1/road1/stop"),
    }
    if (method, path) not in allowed:
        raise HTTPException(status_code=500, detail="Unsupported worker control operation")
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="Worker control authentication is unavailable")
    host, port = worker_control_origin()
    connection = http.client.HTTPConnection(host, port, timeout=WORKER_CONTROL_TIMEOUT_SEC)
    try:
        headers = {"Authorization": f"Bearer {API_TOKEN}", "Accept": "application/json"}
        if method == "POST":
            headers["Content-Length"] = "0"
        connection.request(method, path, body=None, headers=headers)
        response = connection.getresponse()
        body = response.read(65537)
        if len(body) > 65536:
            raise HTTPException(status_code=503, detail="Worker control response is too large")
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=503, detail="Worker control response is invalid") from exc
        if response.status != 200 or not isinstance(payload, dict) or payload.get("ok") is not True:
            raise HTTPException(status_code=503, detail="Worker control operation failed")
        if payload.get("protocol") != WORKER_CONTROL_PROTOCOL:
            raise HTTPException(status_code=503, detail="Worker control protocol mismatch")
        return payload
    except HTTPException:
        raise
    except (OSError, http.client.HTTPException) as exc:
        raise HTTPException(status_code=503, detail="Worker control agent is unavailable") from exc
    finally:
        connection.close()


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json_file(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


@contextmanager
def open_objects_db():
    connection = sqlite3.connect(str(OBJECTS_DB_FILE), timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def prune_objects_registry(connection: sqlite3.Connection) -> List[str]:
    retention = max(0, int(OBJECTS_RETENTION_LIMIT))
    eviction_subquery = """
        SELECT object_id FROM (
            SELECT object_id, ROW_NUMBER() OVER (
                PARTITION BY domain
                ORDER BY detected_at DESC, object_id DESC
            ) AS rn
            FROM objects
        )
        WHERE rn > ?
    """
    evicted = connection.execute(
        f"SELECT object_id, snapshot_url FROM objects WHERE object_id IN ({eviction_subquery})",
        (retention,),
    ).fetchall()
    if not evicted:
        return []
    connection.execute(
        f"DELETE FROM objects WHERE object_id IN ({eviction_subquery})",
        (retention,),
    )
    return [str(row["snapshot_url"]) for row in evicted if row["snapshot_url"]]


def initialize_objects_db() -> None:
    with open_objects_db() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS objects (
                object_id TEXT PRIMARY KEY,
                camera_id TEXT NOT NULL,
                track_id INTEGER,
                detected_at TEXT NOT NULL,
                class_name TEXT,
                analytics_profile TEXT,
                domain TEXT,
                object_type TEXT,
                model_class TEXT,
                confidence REAL,
                speed_kmh REAL,
                snapshot_url TEXT,
                comment TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new', 'reviewed', 'ignored')),
                original_event_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            )
            """
        )
        existing = {row[1] for row in connection.execute("PRAGMA table_info(objects)")}
        for name in ("analytics_profile", "domain", "object_type", "model_class"):
            if name not in existing:
                connection.execute(f"ALTER TABLE objects ADD COLUMN {name} TEXT")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_detected_at ON objects(detected_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_class_name ON objects(class_name)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_speed_kmh ON objects(speed_kmh)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_status ON objects(status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_deleted_at ON objects(deleted_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_camera_id ON objects(camera_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_domain ON objects(domain)")
        prune_objects_registry(connection)
        try:
            prune_snapshotless_objects(connection)
        except Exception:
            pass


def optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def stable_object_id(event: Dict[str, Any]) -> str:
    explicit_id = event.get("event_id") or event.get("object_id")
    if explicit_id not in (None, ""):
        return str(explicit_id)
    canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return f"legacy-{digest}"


def prune_snapshotless_objects(connection: sqlite3.Connection) -> int:
    now = now_iso()
    cursor = connection.execute(
        "UPDATE objects SET deleted_at = ?, updated_at = ? WHERE deleted_at IS NULL AND (snapshot_url IS NULL OR TRIM(snapshot_url) = '')",
        (now, now),
    )
    return int(cursor.rowcount)


def persist_object_event(event: Dict[str, Any]) -> bool:
    snapshot_url = event.get("snapshot_url")
    if not snapshot_url or not str(snapshot_url).strip():
        return False
    if not str(snapshot_url).strip().startswith("/sea-speed/media/"):
        return False
    object_id = stable_object_id(event)
    detected_at = str(event.get("created_at") or event.get("detected_at") or now_iso())
    created_at = str(event.get("created_at") or now_iso())
    camera_id = str(event.get("camera_id") or "cam1")
    profile = event.get("analytics_profile")
    domain = event.get("domain")
    if camera_id == "cam1":
        profile = profile or "water-v1"
        domain = domain or "water"
    elif camera_id == "road1":
        profile = profile or "road-v1"
        domain = domain or "road"
    object_type = event.get("object_type") or event.get("class_name") or event.get("class") or "object"
    model_class = event.get("model_class") or event.get("class_name") or event.get("class") or "object"
    original_event_json = json.dumps(event, ensure_ascii=False, sort_keys=True)
    with open_objects_db() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO objects (
                object_id, camera_id, track_id, detected_at, class_name,
                analytics_profile, domain, object_type, model_class,
                confidence, speed_kmh, snapshot_url, comment, status,
                original_event_json, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'new', ?, ?, ?, NULL)
            """,
            (
                object_id,
                camera_id,
                optional_int(event.get("track_id")),
                detected_at,
                str(event.get("class_name") or event.get("class") or object_type),
                profile,
                domain,
                str(object_type),
                str(model_class),
                optional_float(event.get("confidence")),
                optional_float(event.get("speed_kmh")),
                event.get("snapshot_url"),
                original_event_json,
                created_at,
                now_iso(),
            ),
        )
        inserted = cursor.rowcount > 0
        if inserted:
            prune_objects_registry(connection)
        return inserted


def import_existing_events() -> int:
    events = read_json_file(EVENTS_FILE, [])
    if not isinstance(events, list):
        return 0
    imported = 0
    for event in events:
        if isinstance(event, dict) and persist_object_event(event):
            imported += 1
    return imported


def persist_passage_object(passage: Dict[str, Any]) -> bool:
    snapshot_url = passage.get("snapshot_url")
    if not snapshot_url or not str(snapshot_url).strip().startswith("/sea-speed/media/"):
        return False
    passage_id = str(passage.get("passage_id") or "").strip()
    if not passage_id:
        return False
    object_id = f"passage-{passage_id}"
    started_at = str(passage.get("started_at") or passage.get("last_seen_at") or now_iso())
    class_name = str(passage.get("class_name") or "vessel")
    fragments = passage.get("track_fragments")
    track_id = None
    if isinstance(fragments, list):
        for value in fragments:
            track_id = optional_int(value)
            if track_id is not None:
                break
    original_event_json = json.dumps(
        {"registry_mirror_schema": "sea_speed_water_passage_registry_mirror_v1", "passage": passage},
        ensure_ascii=False,
        sort_keys=True,
    )
    with open_objects_db() as connection:
        cursor = connection.execute(
            """
            INSERT INTO objects (
                object_id, camera_id, track_id, detected_at, class_name,
                analytics_profile, domain, object_type, model_class,
                confidence, speed_kmh, snapshot_url, comment, status,
                original_event_json, created_at, updated_at, deleted_at
            ) VALUES (?, 'cam1', ?, ?, ?, 'water-v1', 'water', ?, ?, ?, ?, ?, '', 'new', ?, ?, ?, NULL)
            ON CONFLICT(object_id) DO UPDATE SET
                track_id=excluded.track_id,
                class_name=excluded.class_name,
                object_type=excluded.object_type,
                model_class=excluded.model_class,
                confidence=excluded.confidence,
                speed_kmh=excluded.speed_kmh,
                snapshot_url=excluded.snapshot_url,
                original_event_json=excluded.original_event_json,
                updated_at=excluded.updated_at
            """,
            (
                object_id,
                track_id,
                started_at,
                class_name,
                class_name,
                class_name,
                optional_float(passage.get("confidence")),
                optional_float(passage.get("speed_kmh")),
                passage.get("snapshot_url"),
                original_event_json,
                started_at,
                now_iso(),
            ),
        )
        inserted_or_updated = cursor.rowcount > 0
        if inserted_or_updated:
            prune_objects_registry(connection)
        return inserted_or_updated


def import_existing_passages() -> int:
    try:
        with open_passages_db() as connection:
            rows = connection.execute("SELECT * FROM water_passages").fetchall()
    except Exception:
        return 0
    mirrored = 0
    for row in rows:
        try:
            if persist_passage_object(dict(row)):
                mirrored += 1
        except Exception as error:
            print(f"passage registry mirror failed for {row['passage_id']}: {error}", file=sys.stderr)
    return mirrored


EVENTS_MEDIA_GRACE_SECONDS = 24 * 3600
EVENTS_SWEEP_INTERVAL_SECONDS = 3600
_events_sweep_state = {"last": 0.0}


def _delete_passage_mirrors(passage_ids: List[str]) -> int:
    ids = [str(value) for value in passage_ids if str(value or "").strip()]
    if not ids:
        return 0
    targets = [f"passage-{value}" for value in ids]
    placeholders = ",".join("?" for _ in targets)
    try:
        with open_objects_db() as connection:
            cursor = connection.execute(
                f"DELETE FROM objects WHERE object_id IN ({placeholders})", targets
            )
            return max(0, cursor.rowcount)
    except Exception as error:
        print(f"passage mirror sync failed: {error}", file=sys.stderr)
        return 0


def reconcile_passage_mirrors() -> int:
    try:
        with open_passages_db() as connection:
            rows = connection.execute("SELECT passage_id FROM water_passages").fetchall()
    except Exception:
        return 0
    live = {f"passage-{str(row['passage_id'])}" for row in rows}
    with open_objects_db() as connection:
        mirrors = connection.execute(
            "SELECT object_id FROM objects WHERE object_id LIKE 'passage-%'"
        ).fetchall()
        orphans = [str(row["object_id"]) for row in mirrors if str(row["object_id"]) not in live]
        if not orphans:
            return 0
        placeholders = ",".join("?" for _ in orphans)
        cursor = connection.execute(
            f"DELETE FROM objects WHERE object_id IN ({placeholders})", orphans
        )
        return max(0, cursor.rowcount)


def sweep_events_media(force: bool = False, now: Optional[float] = None) -> int:
    current = time.time() if now is None else float(now)
    last = float(_events_sweep_state.get("last") or 0.0)
    if not force and current - last < EVENTS_SWEEP_INTERVAL_SECONDS:
        return 0
    _events_sweep_state["last"] = current
    try:
        candidates = list(EVENTS_MEDIA_DIR.iterdir())
    except OSError:
        return 0
    try:
        with open_objects_db() as connection:
            referenced = {
                str(row[0]) for row in connection.execute("SELECT DISTINCT snapshot_url FROM objects")
            }
    except Exception as error:
        print(f"events media sweep skipped: {error}", file=sys.stderr)
        return 0
    deleted = 0
    for path in candidates:
        if not path.is_file():
            continue
        name = path.name
        if not name.endswith(".jpg") or name != Path(name).name:
            continue
        if f"/sea-speed/media/events/{name}" in referenced:
            continue
        try:
            age = current - path.stat().st_mtime
        except OSError:
            continue
        if age <= EVENTS_MEDIA_GRACE_SECONDS:
            continue
        try:
            path.unlink()
            deleted += 1
        except OSError as error:
            print(f"events media sweep failed for {name}: {error}", file=sys.stderr)
    return deleted


@contextmanager
def open_passages_db():
    connection = sqlite3.connect(str(PASSAGES_DB_FILE), timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def cleanup_passage_media(snapshot_url: Optional[str]) -> None:
    if not snapshot_url:
        return
    prefix = "/sea-speed/media/passages/"
    value = str(snapshot_url)
    if not value.startswith(prefix):
        return
    filename = value[len(prefix):]
    if not filename or filename != Path(filename).name or not filename.endswith(".jpg"):
        return
    try:
        (PASSAGE_MEDIA_DIR / filename).unlink(missing_ok=True)
    except OSError:
        pass


def prune_water_passages(connection: sqlite3.Connection, target_limit: int = PASSAGES_RETENTION_LIMIT) -> List[str]:
    target_limit = max(0, int(target_limit))
    count = int(connection.execute("SELECT COUNT(*) FROM water_passages").fetchone()[0])
    excess = max(0, count - target_limit)
    if excess == 0:
        return []
    rows = connection.execute(
        """
        SELECT passage_id, snapshot_url
        FROM water_passages
        WHERE status = 'completed'
        ORDER BY COALESCE(completed_at, last_seen_at, started_at) ASC, passage_id ASC
        LIMIT ?
        """,
        (excess,),
    ).fetchall()
    if not rows:
        return []
    passage_ids = [str(row["passage_id"]) for row in rows]
    placeholders = ",".join("?" for _ in passage_ids)
    connection.execute(f"DELETE FROM water_passages WHERE passage_id IN ({placeholders})", passage_ids)
    _delete_passage_mirrors(passage_ids)
    return [str(row["snapshot_url"]) for row in rows if row["snapshot_url"]]


def initialize_water_passages_db() -> None:
    orphan_urls: List[str] = []
    with open_passages_db() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS water_passages (
                passage_id TEXT PRIMARY KEY,
                camera_id TEXT NOT NULL,
                class_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                completed_at TEXT,
                track_fragments_json TEXT NOT NULL,
                vessel_id TEXT,
                confidence REAL,
                direction TEXT,
                speed_status TEXT NOT NULL,
                speed_kmh REAL,
                speed_method TEXT,
                measurement_meta_json TEXT NOT NULL,
                snapshot_url TEXT,
                snapshot_score REAL NOT NULL DEFAULT 0,
                observation_count INTEGER NOT NULL DEFAULT 0,
                worker_source_commit TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_water_passages_last_seen ON water_passages(last_seen_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_water_passages_completed ON water_passages(status, completed_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_water_passages_speed ON water_passages(speed_status, speed_kmh)")
        orphan_urls.extend(prune_water_passages(connection, target_limit=PASSAGES_RETENTION_LIMIT))
        count = int(connection.execute("SELECT COUNT(*) FROM water_passages").fetchone()[0])
        if count > PASSAGES_RETENTION_LIMIT:
            raise RuntimeError("water passage registry exceeds hard limit with non-prunable active rows")
    for snapshot_url in orphan_urls:
        cleanup_passage_media(snapshot_url)


def _validate_passage_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="passage payload must be an object")
    passage_id = str(payload.get("passage_id") or "").strip()
    if not PASSAGE_ID_RE.fullmatch(passage_id):
        raise HTTPException(status_code=400, detail="passage_id is invalid")
    status = str(payload.get("status") or "tracking").strip()
    if status not in PASSAGE_STATUSES:
        raise HTTPException(status_code=400, detail="passage status is invalid")
    speed_status = str(payload.get("speed_status") or "unknown").strip()
    if speed_status not in PASSAGE_SPEED_STATUSES:
        raise HTTPException(status_code=400, detail="speed_status is invalid")
    started_at = str(payload.get("started_at") or "").strip()
    last_seen_at = str(payload.get("last_seen_at") or started_at).strip()
    completed_at = str(payload.get("completed_at") or "").strip() or None
    if not started_at or len(started_at) > 80 or not last_seen_at or len(last_seen_at) > 80:
        raise HTTPException(status_code=400, detail="passage timestamps are invalid")
    class_name = str(payload.get("class_name") or "vessel").strip()
    if class_name != "vessel":
        raise HTTPException(status_code=400, detail="Water passage class_name must be vessel")
    raw_fragments = payload.get("track_fragments") or []
    if not isinstance(raw_fragments, list) or len(raw_fragments) > 64:
        raise HTTPException(status_code=400, detail="track_fragments is invalid")
    track_fragments: List[int] = []
    for value in raw_fragments:
        track_id = optional_int(value)
        if track_id is None:
            raise HTTPException(status_code=400, detail="track_fragments is invalid")
        if track_id not in track_fragments:
            track_fragments.append(track_id)
    speed_kmh = optional_float(payload.get("speed_kmh"))
    if speed_kmh is not None and speed_kmh < 0:
        raise HTTPException(status_code=400, detail="speed_kmh must be >= 0")
    if speed_status == "measured" and speed_kmh is None:
        raise HTTPException(status_code=400, detail="measured passage requires speed_kmh")
    measurement_meta = payload.get("measurement_meta") or {}
    if not isinstance(measurement_meta, dict):
        raise HTTPException(status_code=400, detail="measurement_meta must be an object")
    measurement_meta_json = json.dumps(measurement_meta, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(measurement_meta_json.encode("utf-8")) > 8192:
        raise HTTPException(status_code=400, detail="measurement_meta is too large")
    confidence = optional_float(payload.get("confidence"))
    snapshot_score = optional_float(payload.get("snapshot_score")) or 0.0
    observation_count = optional_int(payload.get("observation_count")) or 0
    if snapshot_score < 0 or observation_count < 0:
        raise HTTPException(status_code=400, detail="passage counters are invalid")
    vessel_id = payload.get("vessel_id")
    vessel_id = str(vessel_id).strip() if vessel_id not in (None, "") else None
    if vessel_id is not None and len(vessel_id) > 128:
        raise HTTPException(status_code=400, detail="vessel_id is invalid")
    direction = payload.get("direction")
    direction = str(direction).strip() if direction not in (None, "") else None
    if direction is not None and len(direction) > 32:
        raise HTTPException(status_code=400, detail="direction is invalid")
    speed_method = payload.get("speed_method")
    speed_method = str(speed_method).strip() if speed_method not in (None, "") else None
    if speed_method is not None and len(speed_method) > 64:
        raise HTTPException(status_code=400, detail="speed_method is invalid")
    worker_source_commit = payload.get("worker_source_commit")
    worker_source_commit = str(worker_source_commit).strip().lower() if worker_source_commit not in (None, "") else None
    if worker_source_commit is not None and (len(worker_source_commit) != 40 or any(ch not in "0123456789abcdef" for ch in worker_source_commit)):
        raise HTTPException(status_code=400, detail="worker_source_commit is invalid")
    snapshot_url = payload.get("snapshot_url")
    snapshot_url = str(snapshot_url).strip() if snapshot_url not in (None, "") else None
    if snapshot_url is not None and not snapshot_url.startswith("/sea-speed/media/passages/"):
        raise HTTPException(status_code=400, detail="snapshot_url is invalid")
    return {
        "passage_id": passage_id,
        "camera_id": "cam1",
        "class_name": "vessel",
        "status": status,
        "started_at": started_at,
        "last_seen_at": last_seen_at,
        "completed_at": completed_at,
        "track_fragments": track_fragments,
        "vessel_id": vessel_id,
        "confidence": confidence,
        "direction": direction,
        "speed_status": speed_status,
        "speed_kmh": speed_kmh,
        "speed_method": speed_method,
        "measurement_meta": measurement_meta,
        "measurement_meta_json": measurement_meta_json,
        "snapshot_url": snapshot_url,
        "snapshot_score": snapshot_score,
        "observation_count": observation_count,
        "worker_source_commit": worker_source_commit,
    }


def passage_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    try:
        data["track_fragments"] = json.loads(data.pop("track_fragments_json", "[]"))
    except Exception:
        data["track_fragments"] = []
    try:
        data["measurement_meta"] = json.loads(data.pop("measurement_meta_json", "{}"))
    except Exception:
        data["measurement_meta"] = {}
    return data


def upsert_water_passage(payload: Dict[str, Any], snapshot_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    incoming = _validate_passage_payload(payload)
    orphan_urls: List[str] = []
    snapshot_path: Optional[Path] = None
    snapshot_data: Optional[bytes] = None
    with open_passages_db() as connection:
        existing_row = connection.execute(
            "SELECT * FROM water_passages WHERE passage_id = ?", (incoming["passage_id"],)
        ).fetchone()
        if existing_row is None:
            count = int(connection.execute("SELECT COUNT(*) FROM water_passages").fetchone()[0])
            if count >= PASSAGES_RETENTION_LIMIT:
                orphan_urls.extend(prune_water_passages(connection, target_limit=PASSAGES_RETENTION_LIMIT - 1))
                count = int(connection.execute("SELECT COUNT(*) FROM water_passages").fetchone()[0])
                if count >= PASSAGES_RETENTION_LIMIT:
                    raise RuntimeError("water passage registry is full with active passages")
            current: Dict[str, Any] = {}
            existing_fragments: List[int] = []
            existing_meta: Dict[str, Any] = {}
        else:
            current = dict(existing_row)
            try:
                existing_fragments = json.loads(current.get("track_fragments_json") or "[]")
            except Exception:
                existing_fragments = []
            try:
                existing_meta = json.loads(current.get("measurement_meta_json") or "{}")
            except Exception:
                existing_meta = {}
        fragments: List[int] = []
        for value in [*existing_fragments, *incoming["track_fragments"]]:
            track_id = optional_int(value)
            if track_id is not None and track_id not in fragments:
                fragments.append(track_id)
        status_rank = {"tracking": 0, "measuring": 1, "measured": 2, "completed": 3}
        speed_rank = {"unknown": 0, "measuring": 1, "incomplete": 2, "measured": 3}
        current_status = str(current.get("status") or "tracking")
        status = incoming["status"] if status_rank.get(incoming["status"], -1) >= status_rank.get(current_status, -1) else current_status
        current_speed_status = str(current.get("speed_status") or "unknown")
        use_incoming_speed = speed_rank.get(incoming["speed_status"], -1) >= speed_rank.get(current_speed_status, -1)
        speed_status = incoming["speed_status"] if use_incoming_speed else current_speed_status
        speed_kmh = incoming["speed_kmh"] if use_incoming_speed else optional_float(current.get("speed_kmh"))
        direction = incoming["direction"] if use_incoming_speed and incoming["direction"] else current.get("direction")
        speed_method = incoming["speed_method"] or current.get("speed_method")
        measurement_meta = incoming["measurement_meta"] if use_incoming_speed else existing_meta
        existing_snapshot_score = optional_float(current.get("snapshot_score")) or 0.0
        snapshot_score = max(existing_snapshot_score, incoming["snapshot_score"])
        snapshot_url = incoming["snapshot_url"] or current.get("snapshot_url")
        if snapshot_bytes is not None and incoming["snapshot_score"] >= existing_snapshot_score:
            if len(snapshot_bytes) > 5 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="passage snapshot is too large")
            filename = f'{incoming["passage_id"]}.jpg'
            snapshot_path = PASSAGE_MEDIA_DIR / filename
            snapshot_data = bytes(snapshot_bytes)
            snapshot_url = f"/sea-speed/media/passages/{filename}"
        if not snapshot_url or not str(snapshot_url).strip().startswith("/sea-speed/media/"):
            raise HTTPException(status_code=422, detail="passage snapshot is required")
        now = now_iso()
        merged = {
            **incoming,
            "status": status,
            "started_at": str(current.get("started_at") or incoming["started_at"]),
            "last_seen_at": max(str(current.get("last_seen_at") or incoming["last_seen_at"]), incoming["last_seen_at"]),
            "completed_at": incoming["completed_at"] or current.get("completed_at"),
            "track_fragments": fragments,
            "confidence": max(optional_float(current.get("confidence")) or 0.0, incoming["confidence"] or 0.0),
            "direction": direction,
            "speed_status": speed_status,
            "speed_kmh": speed_kmh,
            "speed_method": speed_method,
            "measurement_meta": measurement_meta,
            "measurement_meta_json": json.dumps(measurement_meta, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "snapshot_url": snapshot_url,
            "snapshot_score": snapshot_score,
            "observation_count": max(optional_int(current.get("observation_count")) or 0, incoming["observation_count"]),
            "worker_source_commit": incoming["worker_source_commit"] or current.get("worker_source_commit"),
        }
        values = (
            merged["passage_id"], "cam1", "vessel", merged["status"], merged["started_at"], merged["last_seen_at"],
            merged["completed_at"], json.dumps(merged["track_fragments"]), merged["vessel_id"], merged["confidence"],
            merged["direction"], merged["speed_status"], merged["speed_kmh"], merged["speed_method"],
            merged["measurement_meta_json"], merged["snapshot_url"], merged["snapshot_score"],
            merged["observation_count"], merged["worker_source_commit"],
            str(current.get("created_at") or now), now,
        )
        connection.execute(
            """
            INSERT INTO water_passages (
                passage_id, camera_id, class_name, status, started_at, last_seen_at, completed_at,
                track_fragments_json, vessel_id, confidence, direction, speed_status, speed_kmh,
                speed_method, measurement_meta_json, snapshot_url, snapshot_score, observation_count,
                worker_source_commit, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(passage_id) DO UPDATE SET
                status=excluded.status, last_seen_at=excluded.last_seen_at, completed_at=excluded.completed_at,
                track_fragments_json=excluded.track_fragments_json, vessel_id=excluded.vessel_id,
                confidence=excluded.confidence, direction=excluded.direction,
                speed_status=excluded.speed_status, speed_kmh=excluded.speed_kmh,
                speed_method=excluded.speed_method, measurement_meta_json=excluded.measurement_meta_json,
                snapshot_url=excluded.snapshot_url, snapshot_score=excluded.snapshot_score,
                observation_count=excluded.observation_count, worker_source_commit=excluded.worker_source_commit,
                updated_at=excluded.updated_at
            """,
            values,
        )
        orphan_urls.extend(prune_water_passages(connection, target_limit=PASSAGES_RETENTION_LIMIT))
        row = connection.execute("SELECT * FROM water_passages WHERE passage_id = ?", (merged["passage_id"],)).fetchone()
    if snapshot_path is not None and snapshot_data is not None:
        try:
            PASSAGE_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
            temp_path = snapshot_path.with_suffix(".jpg.tmp")
            temp_path.write_bytes(snapshot_data)
            temp_path.replace(snapshot_path)
        except OSError as exc:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise HTTPException(status_code=503, detail="passage snapshot storage is unavailable") from exc
    for snapshot_url in orphan_urls:
        cleanup_passage_media(snapshot_url)
    if row is None:
        raise RuntimeError("water passage persistence failed")
    return passage_row_to_dict(row)


def list_water_passages(limit: int = 50) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    with open_passages_db() as connection:
        rows = connection.execute(
            "SELECT * FROM water_passages ORDER BY last_seen_at DESC, passage_id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [passage_row_to_dict(row) for row in rows]

def object_row_to_dict(row: sqlite3.Row, include_original: bool = False) -> Dict[str, Any]:
    data = dict(row)
    raw = data.pop("original_event_json", "{}")
    if include_original:
        try:
            data["original_event"] = json.loads(raw)
        except Exception:
            data["original_event"] = {}
    return data


def build_objects_where(
    date_from: Optional[str],
    date_to: Optional[str],
    class_name: Optional[str],
    status: Optional[str],
    speed_min: Optional[float],
    speed_max: Optional[float],
    search: Optional[str],
    include_deleted: bool,
    camera_id: Optional[str] = "cam1",
    domain: Optional[str] = None,
    analytics_profile: Optional[str] = None,
    object_type: Optional[str] = None,
) -> tuple[str, List[Any]]:
    clauses: List[str] = []
    values: List[Any] = []
    if camera_id:
        clauses.append("camera_id = ?")
        values.append(camera_id)
    if domain:
        clauses.append("domain = ?")
        values.append(domain)
    if analytics_profile:
        clauses.append("analytics_profile = ?")
        values.append(analytics_profile)
    if object_type:
        clauses.append("object_type = ?")
        values.append(object_type)
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if date_from:
        clauses.append("detected_at >= ?")
        values.append(date_from)
    if date_to:
        clauses.append("detected_at <= ?")
        values.append(date_to)
    if class_name:
        clauses.append("class_name = ?")
        values.append(class_name.strip())
    if status:
        if status not in OBJECT_STATUSES:
            raise HTTPException(status_code=400, detail="status must be new, reviewed or ignored")
        clauses.append("status = ?")
        values.append(status)
    if speed_min is not None:
        clauses.append("speed_kmh >= ?")
        values.append(speed_min)
    if speed_max is not None:
        clauses.append("speed_kmh <= ?")
        values.append(speed_max)
    if search:
        term = f"%{search.strip()}%"
        clauses.append("(object_id LIKE ? OR class_name LIKE ? OR comment LIKE ?)")
        values.extend([term, term, term])
    return " AND ".join(clauses) if clauses else "1=1", values


def default_state() -> Dict[str, Any]:
    return {
        "camera_id": "cam1",
        "analytics_profile": "water-v1",
        "domain": "water",
        "state_schema": WORKER_STATE_SCHEMA,
        "telemetry_schema": TELEMETRY_SCHEMA,
        "worker_source_commit": None,
        "updated_at": None,
        "worker_online": False,
        "motion_now": False,
        "motion_area": 0,
        "ai_active": False,
        "detections": 0,
        "tracks": 0,
        "frame_no": 0,
        "frame_width": 1920,
        "frame_height": 1080,
        "sample_fps": 10.0,
        "effective_fps": None,
        "p95_inference_ms": None,
        "overlay_rev": 0,
        "last_overlay_url": None,
        "message": "No worker state received yet",
    }


def analytics_identity(camera_id: str) -> Dict[str, str]:
    identity = ANALYTICS_IDENTITIES.get(camera_id)
    if identity is None:
        raise HTTPException(status_code=404, detail="Unknown analytics camera")
    return dict(identity)


def analytics_data_file(camera_id: str, kind: str) -> Path:
    analytics_identity(camera_id)
    legacy = {
        "state": STATE_FILE,
        "events": EVENTS_FILE,
        "roi": ROI_FILE,
        "speed_config": SPEED_CONFIG_FILE,
        "speed_lines": SPEED_LINES_FILE,
    }
    if camera_id == "cam1" and kind in legacy:
        return legacy[kind]
    return DATA_DIR / f"{camera_id}_{kind}.json"


def analytics_default_state(camera_id: str) -> Dict[str, Any]:
    identity = analytics_identity(camera_id)
    data = default_state() if camera_id == "cam1" else {
        "camera_id": camera_id,
        "state_schema": WORKER_STATE_SCHEMA,
        "telemetry_schema": TELEMETRY_SCHEMA,
        "worker_source_commit": None,
        "updated_at": None,
        "worker_online": False,
        "motion_now": False,
        "motion_area": 0,
        "ai_active": False,
        "detections": 0,
        "tracks": 0,
        "frame_no": 0,
        "frame_width": 1920,
        "frame_height": 1080,
        "sample_fps": 10.0,
        "effective_fps": None,
        "p95_inference_ms": None,
        "overlay_rev": 0,
        "last_overlay_url": None,
        "message": "No worker state received yet",
    }
    data.update(identity)
    data["camera_id"] = camera_id
    return data


def analytics_state(camera_id: str) -> Dict[str, Any]:
    state = read_json_file(analytics_data_file(camera_id, "state"), analytics_default_state(camera_id))
    identity = analytics_identity(camera_id)
    state["camera_id"] = camera_id
    state.setdefault("analytics_profile", identity["analytics_profile"])
    state.setdefault("domain", identity["domain"])
    state.setdefault("state_schema", WORKER_STATE_SCHEMA)
    state.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    state.setdefault("worker_source_commit", None)
    state.setdefault("frame_no", 0)
    state.setdefault("frame_width", 1920)
    state.setdefault("frame_height", 1080)
    state.setdefault("sample_fps", 10.0)
    state.setdefault("effective_fps", None)
    state.setdefault("p95_inference_ms", None)
    state.setdefault("overlay_rev", state.get("frame_no", 0))
    updated_at = state.get("updated_at")
    if not updated_at:
        state["worker_online"] = False
        return state
    try:
        dt = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        state["worker_online"] = time.time() - dt.timestamp() <= 30
    except Exception:
        state["worker_online"] = False
    return state


def clean_points_list(raw_points: Any, max_points: int = 2) -> List[Dict[str, int]]:
    clean = []
    if not isinstance(raw_points, list):
        return clean
    for point in raw_points[:max_points]:
        if not isinstance(point, dict):
            continue
        try:
            x = int(round(float(point.get("x"))))
            y = int(round(float(point.get("y"))))
        except Exception:
            continue
        clean.append({"x": x, "y": y})
    return clean


# Normalized ROI geometry — 0..1 + reference, scale-on-read to current frame size
DEFAULT_ROI_REF_W = 1920
DEFAULT_ROI_REF_H = 1080
LEGACY_ROI_W = 704
LEGACY_ROI_H = 576


def _is_normalized_point(point: Any) -> bool:
    return isinstance(point, dict) and ("x_norm" in point or "y_norm" in point)


def _clean_norm_points(raw_points: Any, max_points: int = 1000) -> List[Dict[str, float]]:
    clean: List[Dict[str, float]] = []
    if not isinstance(raw_points, list):
        return clean
    for p in raw_points[:max_points]:
        if not isinstance(p, dict):
            continue
        try:
            xn = float(p.get("x_norm", p.get("x", 0)))
            yn = float(p.get("y_norm", p.get("y", 0)))
        except Exception:
            continue
        # if caller passed absolute x 0..1920 already treat as norm only when explicitly x_norm present
        if "x_norm" not in p and "y_norm" not in p:
            continue
        xn = max(0.0, min(1.0, xn))
        yn = max(0.0, min(1.0, yn))
        clean.append({"x_norm": xn, "y_norm": yn})
    return clean


def _infer_legacy_ref_w_h(polygon: List[Dict[str, int]]) -> tuple[int, int]:
    if not polygon:
        return DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H
    max_x = max((p.get("x", 0) for p in polygon), default=0)
    max_y = max((p.get("y", 0) for p in polygon), default=0)
    if max_x <= LEGACY_ROI_W and max_y <= LEGACY_ROI_H and max_x > 0 and max_y > 0:
        return LEGACY_ROI_W, LEGACY_ROI_H
    return DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H


def _normalize_from_absolute(polygon: List[Dict[str, int]], ref_w: int, ref_h: int) -> List[Dict[str, float]]:
    return [{"x_norm": p["x"] / ref_w, "y_norm": p["y"] / ref_h} for p in polygon]


def _denormalize_to_absolute(polygon_norm: List[Dict[str, float]], dst_w: int, dst_h: int) -> List[Dict[str, int]]:
    return [{"x": int(round(p["x_norm"] * dst_w)), "y": int(round(p["y_norm"] * dst_h))} for p in polygon_norm]


def _normalize_legacy_polygon(legacy: List[Dict[str, int]], raw: Dict[str, Any]) -> tuple[List[Dict[str, float]], int, int]:
    ref_w, ref_h = _infer_legacy_ref_w_h(legacy)
    ref_w = int(raw.get("reference_width") or raw.get("referenceWidth") or ref_w)
    ref_h = int(raw.get("reference_height") or raw.get("referenceHeight") or ref_h)
    return _normalize_from_absolute(legacy, ref_w, ref_h), ref_w, ref_h


def validate_camera_preview_source(camera_id: str, source: str) -> str:
    if not CAMERA_PREVIEW_ID_RE.fullmatch(camera_id):
        raise ValueError("invalid camera preview identity")
    try:
        parsed = urlsplit(source)
        address = ipaddress.ip_address(parsed.hostname or "")
        _ = parsed.port
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid camera preview relay source") from exc
    if (
        parsed.scheme.lower() != "rtsp"
        or address.version != 4
        or not any(address in network for network in CAMERA_PREVIEW_RFC1918)
        or parsed.port is None
    ):
        raise ValueError("invalid camera preview relay source")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("camera preview relay source must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("camera preview relay source must not contain query or fragment")
    if parsed.path.rstrip("/") != f"/preview_{camera_id}":
        raise ValueError("camera preview relay path does not match camera identity")
    return source


def load_camera_preview_catalog() -> List[Dict[str, str]]:
    if not CAMERA_PREVIEW_CATALOG_FILE.exists():
        return []
    try:
        payload = json.loads(CAMERA_PREVIEW_CATALOG_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Camera preview catalog is invalid") from exc
    if payload.get("schema") != CAMERA_PREVIEW_CATALOG_SCHEMA or not isinstance(payload.get("cameras"), list):
        raise HTTPException(status_code=500, detail="Camera preview catalog is invalid")
    cameras: List[Dict[str, str]] = []
    seen = set()
    try:
        for item in payload["cameras"]:
            if not isinstance(item, dict):
                raise ValueError("invalid camera entry")
            camera_id = str(item.get("camera_id") or "").strip()
            display_name = str(item.get("display_name") or camera_id).strip()
            source = str(item.get("source") or "").strip()
            if not CAMERA_PREVIEW_ID_RE.fullmatch(camera_id) or camera_id in seen:
                raise ValueError("invalid camera id")
            if not display_name or len(display_name) > 120:
                raise ValueError("invalid camera display name")
            validate_camera_preview_source(camera_id, source)
            seen.add(camera_id)
            cameras.append({"camera_id": camera_id, "display_name": display_name, "source": source})
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Camera preview catalog is invalid") from exc
    return cameras


def camera_snapshot_path(camera_id: str) -> Path:
    if not CAMERA_PREVIEW_ID_RE.fullmatch(camera_id):
        raise ValueError("invalid camera snapshot identity")
    return CAMERA_SNAPSHOT_DIR / f"{camera_id}.jpg"


def camera_snapshot_public_metadata(camera_id: str) -> Dict[str, Any]:
    path = camera_snapshot_path(camera_id)
    try:
        stat = path.stat()
    except OSError:
        return {"available": False, "url": None, "updated_at": None}
    updated_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    return {"available": True, "url": f"/sea-speed/api/cameras/{camera_id}/snapshot?v={stat.st_mtime_ns}", "updated_at": updated_at}


def build_camera_snapshot_extract_args(playlist: Path, output_path: Path) -> List[str]:
    return [
        CAMERA_PREVIEW_FFMPEG_BIN, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-live_start_index", "-1", "-i", str(playlist), "-map", "0:v:0", "-frames:v", "1",
        "-vf", "scale=640:-2", "-q:v", "3", "-y", str(output_path),
    ]


def camera_snapshot_luma_spread(path: Path) -> Optional[float]:
    args = [
        CAMERA_PREVIEW_FFMPEG_BIN, "-nostdin", "-hide_banner", "-loglevel", "info",
        "-i", str(path), "-frames:v", "1", "-vf", "signalstats,metadata=print", "-f", "null", "-",
    ]
    try:
        result = subprocess.run(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, timeout=CAMERA_SNAPSHOT_EXTRACT_TIMEOUT_SEC, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    values: Dict[str, float] = {}
    for name in ("YLOW", "YHIGH"):
        match = re.search(rf"lavfi\.signalstats\.{name}=([0-9.]+)", result.stderr)
        if match:
            values[name] = float(match.group(1))
    if "YLOW" not in values or "YHIGH" not in values:
        return None
    return values["YHIGH"] - values["YLOW"]


def camera_snapshot_candidate_is_usable(path: Path) -> bool:
    try:
        if path.stat().st_size < CAMERA_SNAPSHOT_MIN_BYTES:
            return False
        payload = path.read_bytes()
    except OSError:
        return False
    if not payload.startswith(b"\xff\xd8") or not payload.endswith(b"\xff\xd9"):
        return False
    spread = camera_snapshot_luma_spread(path)
    return spread is not None and spread >= CAMERA_SNAPSHOT_MIN_LUMA_SPREAD


def commit_camera_snapshot_locked(state: Dict[str, Any]) -> Dict[str, Any]:
    camera_id = str(state.get("camera_id") or "")
    session_id = str(state.get("session_id") or "")
    if not CAMERA_PREVIEW_ID_RE.fullmatch(camera_id) or not CAMERA_PREVIEW_SESSION_RE.fullmatch(session_id):
        raise HTTPException(status_code=409, detail="Camera preview session is not eligible for snapshot commit")
    output_dir = CAMERA_PREVIEW_DIR / session_id
    playlist = output_dir / "index.m3u8"
    if Path(str(state.get("output_dir") or "")) != output_dir or not playlist.is_file():
        raise HTTPException(status_code=409, detail="Camera preview session is not eligible for snapshot commit")
    final_path = camera_snapshot_path(camera_id)
    temp_path = CAMERA_SNAPSHOT_DIR / f".{camera_id}.{uuid.uuid4().hex}.jpg"
    try:
        result = subprocess.run(
            build_camera_snapshot_extract_args(playlist, temp_path), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=CAMERA_SNAPSHOT_EXTRACT_TIMEOUT_SEC, check=False,
        )
        if result.returncode != 0 or not camera_snapshot_candidate_is_usable(temp_path):
            raise HTTPException(status_code=422, detail="Camera snapshot did not pass the last-good quality gate")
        os.chmod(temp_path, 0o644)
        os.replace(temp_path, final_path)
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=422, detail="Camera snapshot extraction timed out") from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Camera snapshot storage is unavailable") from exc
    finally:
        temp_path.unlink(missing_ok=True)
    return camera_snapshot_public_metadata(camera_id)


def camera_preview_public_state(state: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not state:
        return None
    return {
        "camera_id": state.get("camera_id"), "display_name": state.get("display_name"),
        "session_id": state.get("session_id"), "hls_url": state.get("hls_url"),
        "started_at": state.get("started_at"), "expires_at": state.get("expires_at"),
        "ttl_sec": state.get("ttl_sec", CAMERA_PREVIEW_TTL_SEC),
    }


def camera_preview_pid_matches(state: Dict[str, Any]) -> bool:
    try:
        pid = int(state.get("pid") or 0)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        cmdline = (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="replace")
    except (OSError, PermissionError):
        return False
    output_dir = str(state.get("output_dir") or "")
    expected_playlist = str(Path(output_dir) / "index.m3u8")
    return Path(CAMERA_PREVIEW_FFMPEG_BIN).name in cmdline and expected_playlist in cmdline


def cleanup_camera_preview_media(state: Dict[str, Any]) -> None:
    session_id = str(state.get("session_id") or "")
    if not CAMERA_PREVIEW_SESSION_RE.fullmatch(session_id):
        return
    output_dir = CAMERA_PREVIEW_DIR / session_id
    try:
        for child in output_dir.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
        output_dir.rmdir()
    except OSError:
        pass


def terminate_camera_preview_locked() -> Optional[str]:
    state = read_json_file(CAMERA_PREVIEW_STATE_FILE, {})
    if not isinstance(state, dict) or not state:
        return None
    camera_id = str(state.get("camera_id") or "") or None
    try:
        pid = int(state.get("pid") or 0)
    except (TypeError, ValueError):
        pid = 0
    if pid > 0 and camera_preview_pid_matches(state):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and camera_preview_pid_matches(state):
            time.sleep(0.05)
        if camera_preview_pid_matches(state):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    cleanup_camera_preview_media(state)
    write_json_file(CAMERA_PREVIEW_STATE_FILE, {})
    return camera_id


def active_camera_preview_locked() -> Optional[Dict[str, Any]]:
    state = read_json_file(CAMERA_PREVIEW_STATE_FILE, {})
    if not isinstance(state, dict) or not state:
        return None
    try:
        expires_epoch = float(state.get("expires_epoch") or 0)
    except (TypeError, ValueError):
        expires_epoch = 0
    if expires_epoch <= time.time() or not camera_preview_pid_matches(state):
        terminate_camera_preview_locked()
        return None
    return state


def build_camera_preview_ffmpeg_args(source: str, output_dir: Path) -> List[str]:
    return [
        CAMERA_PREVIEW_FFMPEG_BIN, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-rtsp_transport", "tcp", "-i", source, "-map", "0:v:0", "-an",
        "-vf", "scale=640:-2,fps=8", "-c:v", "libx264", "-preset", "veryfast",
        "-tune", "zerolatency", "-profile:v", "baseline", "-pix_fmt", "yuv420p",
        "-g", "16", "-keyint_min", "16", "-sc_threshold", "0", "-t", str(CAMERA_PREVIEW_TTL_SEC),
        "-f", "hls", "-hls_time", "1", "-hls_list_size", "4",
        "-hls_flags", "delete_segments+independent_segments+omit_endlist", "-hls_segment_type", "fmp4",
        "-hls_fmp4_init_filename", "init.mp4", "-hls_segment_filename", str(output_dir / "segment_%05d.m4s"),
        str(output_dir / "index.m3u8"),
    ]


def start_camera_preview_locked(camera: Dict[str, str]) -> Dict[str, Any]:
    terminate_camera_preview_locked()
    ffmpeg_path = Path(CAMERA_PREVIEW_FFMPEG_BIN)
    if not ffmpeg_path.is_file() or not os.access(ffmpeg_path, os.X_OK):
        raise HTTPException(status_code=503, detail="Camera preview transcoder is unavailable")
    session_id = uuid.uuid4().hex[:12]
    output_dir = CAMERA_PREVIEW_DIR / session_id
    output_dir.mkdir(mode=0o755, parents=False, exist_ok=False)
    playlist = output_dir / "index.m3u8"
    started_epoch = time.time()
    expires_epoch = started_epoch + CAMERA_PREVIEW_TTL_SEC
    started_at = datetime.fromtimestamp(started_epoch, timezone.utc).isoformat()
    expires_at = datetime.fromtimestamp(expires_epoch, timezone.utc).isoformat()
    hls_url = f"/sea-speed/media/camera-preview/{session_id}/index.m3u8"
    args = build_camera_preview_ffmpeg_args(camera["source"], output_dir)
    try:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    except OSError as exc:
        cleanup_camera_preview_media({"session_id": session_id})
        raise HTTPException(status_code=503, detail="Camera preview transcoder failed to start") from exc
    state: Dict[str, Any] = {
        "camera_id": camera["camera_id"], "display_name": camera["display_name"], "session_id": session_id,
        "pid": process.pid, "output_dir": str(output_dir), "hls_url": hls_url, "started_at": started_at,
        "expires_at": expires_at, "expires_epoch": expires_epoch, "ttl_sec": CAMERA_PREVIEW_TTL_SEC,
    }
    write_json_file(CAMERA_PREVIEW_STATE_FILE, state)
    deadline = time.monotonic() + CAMERA_PREVIEW_START_TIMEOUT_SEC
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            if playlist.is_file() and "#EXTM3U" in playlist.read_text(encoding="utf-8", errors="ignore"):
                return state
        except OSError:
            pass
        time.sleep(0.2)
    terminate_camera_preview_locked()
    raise HTTPException(status_code=502, detail="Camera preview did not become ready")


initialize_objects_db()
import_existing_events()
import_existing_passages()
reconcile_passage_mirrors()
sweep_events_media(force=True)
initialize_water_passages_db()


@app.get("/api/cameras")
def get_cameras() -> Dict[str, Any]:
    cameras = load_camera_preview_catalog()
    with CAMERA_PREVIEW_LOCK:
        active = camera_preview_public_state(active_camera_preview_locked())
    public_cameras = [
        {"camera_id": camera["camera_id"], "display_name": camera["display_name"], "available": True,
         "snapshot": camera_snapshot_public_metadata(camera["camera_id"])} for camera in cameras
    ]
    return {"ok": True, "schema": CAMERA_PREVIEW_CATALOG_SCHEMA, "count": len(public_cameras), "cameras": public_cameras,
            "active": active, "preview_policy": {"max_active": 1, "ttl_sec": CAMERA_PREVIEW_TTL_SEC}}


@app.get("/api/cameras/{camera_id}/snapshot")
def get_camera_snapshot(camera_id: str):
    cameras = load_camera_preview_catalog()
    if not any(entry["camera_id"] == camera_id for entry in cameras):
        raise HTTPException(status_code=404, detail="Camera is not present in the preview catalog")
    path = camera_snapshot_path(camera_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Camera snapshot is not available")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"})


@app.post("/api/cameras/{camera_id}/snapshot/commit")
def commit_camera_snapshot(camera_id: str, session_id: str) -> Dict[str, Any]:
    cameras = load_camera_preview_catalog()
    if not any(entry["camera_id"] == camera_id for entry in cameras):
        raise HTTPException(status_code=404, detail="Camera is not present in the preview catalog")
    if not CAMERA_PREVIEW_SESSION_RE.fullmatch(session_id):
        raise HTTPException(status_code=409, detail="Camera preview session is stale")
    with CAMERA_PREVIEW_LOCK:
        state = active_camera_preview_locked()
        if not state or state.get("camera_id") != camera_id or state.get("session_id") != session_id:
            raise HTTPException(status_code=409, detail="Camera preview session is stale")
        snapshot = commit_camera_snapshot_locked(state)
    return {"ok": True, "camera_id": camera_id, "snapshot": snapshot}


@app.get("/api/cameras/preview")
def get_camera_preview() -> Dict[str, Any]:
    with CAMERA_PREVIEW_LOCK:
        active = camera_preview_public_state(active_camera_preview_locked())
    return {"ok": True, "active": active}


@app.post("/api/cameras/{camera_id}/preview/start")
def start_camera_preview(camera_id: str) -> Dict[str, Any]:
    cameras = load_camera_preview_catalog()
    camera = next((entry for entry in cameras if entry["camera_id"] == camera_id), None)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera is not present in the preview catalog")
    with CAMERA_PREVIEW_LOCK:
        state = start_camera_preview_locked(camera)
    return {"ok": True, "preview": camera_preview_public_state(state)}


@app.post("/api/cameras/preview/stop")
def stop_camera_preview() -> Dict[str, Any]:
    with CAMERA_PREVIEW_LOCK:
        stopped_camera_id = terminate_camera_preview_locked()
    return {"ok": True, "stopped_camera_id": stopped_camera_id, "active": None}


@app.get("/api/cam1/state")
def get_cam1_state() -> Dict[str, Any]:
    state = read_json_file(STATE_FILE, default_state())
    state.setdefault("analytics_profile", "water-v1")
    state.setdefault("domain", "water")
    state.setdefault("state_schema", WORKER_STATE_SCHEMA)
    state.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    state.setdefault("worker_source_commit", None)
    state.setdefault("frame_no", 0)
    updated_at = state.get("updated_at")
    if not updated_at:
        state["worker_online"] = False
        return state
    try:
        dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        age = time.time() - dt.timestamp()
        state["worker_online"] = age <= 30
    except Exception:
        state["worker_online"] = False
    return state


@app.post("/api/cam1/state")
async def post_cam1_state(metadata: str = Form(...), overlay: Optional[UploadFile] = File(None), authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    return await post_analytics_state("cam1", metadata, overlay, authorization)


@app.get("/api/cam1/events")
def get_cam1_events(limit: int = 50) -> Dict[str, Any]:
    return get_analytics_events("cam1", limit)


@app.post("/api/cam1/events")
async def post_cam1_event(metadata: str = Form(...), snapshot: Optional[UploadFile] = File(None), authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    return await post_analytics_event("cam1", metadata, snapshot, authorization)


@app.get("/api/cam1/passages")
def get_cam1_passages(limit: int = 50) -> Dict[str, Any]:
    passages = list_water_passages(limit)
    return {"ok": True, "camera_id": "cam1", "count": len(passages), "passages": passages}


@app.post("/api/cam1/passages")
async def post_cam1_passage(
    metadata: str = Form(...),
    snapshot: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    require_auth(authorization)
    try:
        payload = json.loads(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="metadata must be a JSON object")
    snapshot_bytes = await snapshot.read() if snapshot is not None else None
    try:
        passage = upsert_water_passage(payload, snapshot_bytes=snapshot_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc
    try:
        persist_passage_object(passage)
    except Exception as error:
        print(f"passage registry mirror failed for {passage.get('passage_id')}: {error}", file=sys.stderr)
    sweep_events_media()
    return {"ok": True, "passage": passage}


@app.get("/api/cam1/objects")
def get_cam1_objects(
    limit: int = 50, offset: int = 0, date_from: Optional[str] = None, date_to: Optional[str] = None,
    class_name: Optional[str] = None, status: Optional[str] = None, speed_min: Optional[float] = None,
    speed_max: Optional[float] = None, search: Optional[str] = None, include_deleted: bool = False,
) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    if speed_min is not None and speed_min < 0:
        raise HTTPException(status_code=400, detail="speed_min must be >= 0")
    if speed_max is not None and speed_max < 0:
        raise HTTPException(status_code=400, detail="speed_max must be >= 0")
    if speed_min is not None and speed_max is not None and speed_min > speed_max:
        raise HTTPException(status_code=400, detail="speed_min must be <= speed_max")
    where_sql, values = build_objects_where(date_from, date_to, class_name, status, speed_min, speed_max, search, include_deleted)
    with open_objects_db() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM objects WHERE {where_sql}", values).fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM objects WHERE {where_sql} ORDER BY detected_at DESC, object_id DESC LIMIT ? OFFSET ?",
            [*values, limit, offset],
        ).fetchall()
    return {"ok": True, "camera_id": "cam1", "count": len(rows), "total": total, "limit": limit, "offset": offset,
            "objects": [object_row_to_dict(row) for row in rows]}


@app.get("/api/cam1/objects/{object_id}")
def get_cam1_object(object_id: str) -> Dict[str, Any]:
    with open_objects_db() as connection:
        row = connection.execute("SELECT * FROM objects WHERE object_id = ? AND camera_id = ? AND deleted_at IS NULL", (object_id, "cam1")).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return {"ok": True, "object": object_row_to_dict(row, include_original=True)}


@app.patch("/api/cam1/objects/{object_id}")
def patch_cam1_object(object_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return patch_object_record(object_id, payload, "cam1")


@app.delete("/api/cam1/objects/{object_id}")
def delete_cam1_object(object_id: str) -> Dict[str, Any]:
    return delete_object_record(object_id, "cam1")


@app.get("/api/cam1/roi")
def get_cam1_roi() -> Dict[str, Any]:
    return get_analytics_roi("cam1")


@app.post("/api/cam1/roi")
def post_cam1_roi(payload: Dict[str, Any]) -> Dict[str, Any]:
    return post_analytics_roi("cam1", payload)


@app.get("/api/cam1/speed-config")
def get_cam1_speed_config() -> Dict[str, Any]:
    return get_analytics_speed_config("cam1")


@app.post("/api/cam1/speed-config")
def post_cam1_speed_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    return post_analytics_speed_config("cam1", payload)


@app.get("/api/cam1/speed-lines")
def get_cam1_speed_lines() -> Dict[str, Any]:
    return get_analytics_speed_lines("cam1")


@app.post("/api/cam1/speed-lines")
def post_cam1_speed_lines(payload: Dict[str, Any]) -> Dict[str, Any]:
    return post_analytics_speed_lines("cam1", payload)


@app.get("/api/cam1/crossing-line")
def get_cam1_crossing_line() -> Dict[str, Any]:
    return get_analytics_crossing_line("cam1")


@app.post("/api/cam1/crossing-line")
def post_cam1_crossing_line(payload: Dict[str, Any]) -> Dict[str, Any]:
    return post_analytics_crossing_line("cam1", payload)


@app.post("/api/cam1/crossings")
async def post_cam1_crossing(
    metadata: str = Form(...),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return await api_post_crossing("cam1", metadata=metadata, authorization=authorization)


@app.get("/api/cam1/crossings/summary")
def get_cam1_crossings_summary(
    hours: int = 24, date_from: Optional[str] = None, date_to: Optional[str] = None,
) -> Dict[str, Any]:
    return get_analytics_crossings_summary("cam1", hours, date_from, date_to)


def patch_object_record(object_id: str, payload: Dict[str, Any], camera_id: Optional[str] = None) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    if "class_name" in payload:
        class_name = str(payload.get("class_name") or "").strip()
        if not class_name or len(class_name) > 80:
            raise HTTPException(status_code=400, detail="class_name must contain 1 to 80 characters")
        updates["class_name"] = class_name
    if "speed_kmh" in payload:
        value = payload.get("speed_kmh")
        if value in (None, ""):
            updates["speed_kmh"] = None
        else:
            try:
                speed_kmh = float(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="speed_kmh must be a number or null")
            if speed_kmh < 0:
                raise HTTPException(status_code=400, detail="speed_kmh must be >= 0")
            updates["speed_kmh"] = speed_kmh
    if "comment" in payload:
        comment = str(payload.get("comment") or "").strip()
        if len(comment) > 2000:
            raise HTTPException(status_code=400, detail="comment must contain at most 2000 characters")
        updates["comment"] = comment
    if "status" in payload:
        object_status = str(payload.get("status") or "")
        if object_status not in OBJECT_STATUSES:
            raise HTTPException(status_code=400, detail="status must be new, reviewed or ignored")
        updates["status"] = object_status
    if not updates:
        raise HTTPException(status_code=400, detail="No editable fields supplied")
    updates["updated_at"] = now_iso()
    set_sql = ", ".join(f"{name} = ?" for name in updates)
    where = "object_id = ? AND deleted_at IS NULL"
    values: List[Any] = [*updates.values(), object_id]
    if camera_id:
        where += " AND camera_id = ?"
        values.append(camera_id)
    with open_objects_db() as connection:
        cursor = connection.execute(f"UPDATE objects SET {set_sql} WHERE {where}", values)
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Object not found")
        row = connection.execute("SELECT * FROM objects WHERE object_id = ?", (object_id,)).fetchone()
    return {"ok": True, "object": object_row_to_dict(row, include_original=True)}


def delete_object_record(object_id: str, camera_id: Optional[str] = None) -> Dict[str, Any]:
    deleted_at = now_iso()
    where = "object_id = ? AND deleted_at IS NULL"
    values: List[Any] = [deleted_at, deleted_at, object_id]
    if camera_id:
        where += " AND camera_id = ?"
        values.append(camera_id)
    with open_objects_db() as connection:
        cursor = connection.execute(f"UPDATE objects SET deleted_at = ?, updated_at = ? WHERE {where}", values)
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Object not found")
    return {"ok": True, "object_id": object_id, "deleted_at": deleted_at}


@app.get("/api/analytics/{camera_id}/state")
def get_analytics_state(camera_id: str) -> Dict[str, Any]:
    return analytics_state(camera_id)


@app.post("/api/analytics/{camera_id}/state")
async def post_analytics_state(
    camera_id: str,
    metadata: str = Form(...),
    overlay: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    require_auth(authorization)
    identity = analytics_identity(camera_id)
    try:
        data = json.loads(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON")
    data["camera_id"] = camera_id
    data["analytics_profile"] = identity["analytics_profile"]
    data["domain"] = identity["domain"]
    data.setdefault("state_schema", WORKER_STATE_SCHEMA)
    data.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    data.setdefault("worker_source_commit", None)
    data["updated_at"] = now_iso()
    data["worker_online"] = True
    path = analytics_data_file(camera_id, "state")
    if overlay is not None:
        overlay_path = OVERLAY_DIR / f"{camera_id}_latest_overlay.jpg"
        overlay_bytes = await overlay.read()
        # atomic replace to avoid readers seeing partial JPEG
        overlay_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = overlay_path.with_suffix(".tmp")
        tmp_path.write_bytes(overlay_bytes)
        os.replace(tmp_path, overlay_path)
        data["last_overlay_url"] = f"/sea-speed/media/overlays/{camera_id}_latest_overlay.jpg"
        # ensure overlay_rev bound to frame_no if not already
        if data.get("overlay_rev") is None:
            try:
                data["overlay_rev"] = int(data.get("frame_no", 0))
            except Exception:
                data["overlay_rev"] = 0
    else:
        old_state = read_json_file(path, analytics_default_state(camera_id))
        data["last_overlay_url"] = old_state.get("last_overlay_url")
        if data.get("overlay_rev") is None:
            data["overlay_rev"] = old_state.get("overlay_rev", old_state.get("frame_no", 0))
    write_json_file(path, data)
    return {"ok": True, "state": data}


@app.get("/api/analytics/{camera_id}/events")
def get_analytics_events(camera_id: str, limit: int = 50) -> Dict[str, Any]:
    analytics_identity(camera_id)
    events = read_json_file(analytics_data_file(camera_id, "events"), [])
    events = events[: max(1, min(limit, 200))]
    return {"ok": True, "camera_id": camera_id, "count": len(events), "events": events}


@app.post("/api/analytics/{camera_id}/events")
async def post_analytics_event(
    camera_id: str,
    metadata: str = Form(...),
    snapshot: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    require_auth(authorization)
    identity = analytics_identity(camera_id)
    try:
        event = json.loads(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON")
    event_id = str(event.get("event_id") or uuid.uuid4())
    event["event_id"] = event_id
    event["camera_id"] = camera_id
    event["analytics_profile"] = identity["analytics_profile"]
    event["domain"] = identity["domain"]
    person_blocked = (
        identity["domain"] == "road"
        and str(event.get("object_type") or "").strip().lower() == "person"
    )
    if person_blocked:
        return {"ok": True, "event": None}
    event.setdefault("object_type", event.get("class_name") or event.get("class") or "object")
    event.setdefault("model_class", event.get("class_name") or event.get("class") or "object")
    event.setdefault("event_schema", VEHICLE_EVENT_SCHEMA)
    event.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    event.setdefault("worker_source_commit", None)
    event.setdefault("calibration_version", None)
    event["created_at"] = event.get("created_at") or now_iso()
    if snapshot is None:
        raise HTTPException(status_code=422, detail="snapshot is required")
    filename = f"{camera_id}-{event_id}.jpg"
    snapshot_path = EVENTS_MEDIA_DIR / filename
    snapshot_path.write_bytes(await snapshot.read())
    event["snapshot_url"] = f"/sea-speed/media/events/{filename}"
    if not persist_object_event(event):
        raise HTTPException(status_code=422, detail="snapshot is required")
    sweep_events_media()
    events_path = analytics_data_file(camera_id, "events")
    events: List[Dict[str, Any]] = read_json_file(events_path, [])
    events.insert(0, event)
    write_json_file(events_path, events[:500])
    return {"ok": True, "event": event}


@app.get("/api/analytics/{camera_id}/roi")
def get_analytics_roi(camera_id: str) -> Dict[str, Any]:
    analytics_identity(camera_id)
    default_roi = {"ok": True, "camera_id": camera_id, "enabled": False, "polygon": [], "polygon_norm": [], "reference_width": DEFAULT_ROI_REF_W, "reference_height": DEFAULT_ROI_REF_H, "updated_at": None}
    roi_path = analytics_data_file(camera_id, "roi")
    if roi_path.exists():
        try:
            roi = json.loads(roi_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=500, detail="ROI storage is corrupted") from exc
        if not isinstance(roi, dict):
            raise HTTPException(status_code=500, detail="ROI storage is corrupted")
    else:
        roi = dict(default_roi)
    roi["ok"] = True
    roi["camera_id"] = camera_id
    roi.setdefault("enabled", False)
    roi.setdefault("updated_at", None)
    # migrate legacy absolute polygon to normalized if needed
    if roi.get("polygon_norm") is None or not isinstance(roi.get("polygon_norm"), list) or not roi.get("polygon_norm"):
        legacy = clean_points_list(roi.get("polygon", []), max_points=1000)
        if legacy:
            norm, ref_w, ref_h = _normalize_legacy_polygon(legacy, roi)
            roi["polygon_norm"] = norm
            roi["reference_width"] = ref_w
            roi["reference_height"] = ref_h
            # keep legacy polygon but also ensure denormalized to default for compat
            roi["polygon"] = _denormalize_to_absolute(norm, DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
            write_json_file(analytics_data_file(camera_id, "roi"), {k: v for k, v in roi.items() if k not in ("ok", "camera_id")})
        else:
            roi.setdefault("polygon_norm", [])
            roi.setdefault("reference_width", DEFAULT_ROI_REF_W)
            roi.setdefault("reference_height", DEFAULT_ROI_REF_H)
            roi.setdefault("polygon", [])
    else:
        # ensure polygon absolute is in sync with norm for legacy clients
        norm = _clean_norm_points(roi.get("polygon_norm"), max_points=1000)
        ref_w = int(roi.get("reference_width", DEFAULT_ROI_REF_W))
        ref_h = int(roi.get("reference_height", DEFAULT_ROI_REF_H))
        roi["polygon_norm"] = norm
        roi["reference_width"] = ref_w
        roi["reference_height"] = ref_h
        roi["polygon"] = _denormalize_to_absolute(norm, DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    return roi


@app.post("/api/analytics/{camera_id}/roi")
def post_analytics_roi(camera_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    analytics_identity(camera_id)
    enabled = bool(payload.get("enabled", True))
    # accept either normalized or legacy
    norm = _clean_norm_points(payload.get("polygon_norm") or payload.get("polygon") or [], max_points=1000)
    if norm:
        ref_w = int(payload.get("reference_width") or payload.get("referenceWidth") or DEFAULT_ROI_REF_W)
        ref_h = int(payload.get("reference_height") or payload.get("referenceHeight") or DEFAULT_ROI_REF_H)
        polygon_norm = norm
    else:
        legacy = clean_points_list(payload.get("polygon", []), max_points=1000)
        if enabled and len(legacy) < 3:
            raise HTTPException(status_code=400, detail="ROI polygon must contain at least 3 points")
        if legacy:
            polygon_norm, ref_w, ref_h = _normalize_legacy_polygon(legacy, payload)
        else:
            polygon_norm, ref_w, ref_h = [], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H
            if enabled:
                raise HTTPException(status_code=400, detail="ROI polygon must contain at least 3 points")
    if enabled and len(polygon_norm) < 3:
        raise HTTPException(status_code=400, detail="ROI polygon must contain at least 3 points")
    polygon = _denormalize_to_absolute(polygon_norm, DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    roi = {"ok": True, "camera_id": camera_id, "enabled": enabled, "polygon": polygon, "polygon_norm": polygon_norm, "reference_width": ref_w, "reference_height": ref_h, "updated_at": now_iso()}
    write_json_file(analytics_data_file(camera_id, "roi"), {k: v for k, v in roi.items() if k not in ("ok", "camera_id")})
    return roi


@app.get("/api/analytics/{camera_id}/speed-config")
def get_analytics_speed_config(camera_id: str) -> Dict[str, Any]:
    analytics_identity(camera_id)
    default_config = {"ok": True, "camera_id": camera_id, "enabled": False, "kmh_per_px_s": 0.0, "updated_at": None}
    config = read_json_file(analytics_data_file(camera_id, "speed_config"), default_config)
    config["ok"] = True
    config["camera_id"] = camera_id
    config.setdefault("enabled", False)
    config.setdefault("kmh_per_px_s", 0.0)
    config.setdefault("updated_at", None)
    return config


@app.post("/api/analytics/{camera_id}/speed-config")
def post_analytics_speed_config(camera_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    analytics_identity(camera_id)
    enabled = bool(payload.get("enabled", True))
    try:
        kmh_per_px_s = float(payload.get("kmh_per_px_s", 0.0))
    except Exception:
        raise HTTPException(status_code=400, detail="kmh_per_px_s must be a number")
    if kmh_per_px_s < 0:
        raise HTTPException(status_code=400, detail="kmh_per_px_s must be >= 0")
    config = {"ok": True, "camera_id": camera_id, "enabled": enabled and kmh_per_px_s > 0,
              "kmh_per_px_s": kmh_per_px_s, "updated_at": now_iso()}
    write_json_file(analytics_data_file(camera_id, "speed_config"), config)
    return config


@app.get("/api/analytics/{camera_id}/speed-lines")
def get_analytics_speed_lines(camera_id: str) -> Dict[str, Any]:
    analytics_identity(camera_id)
    default_config = {"ok": True, "camera_id": camera_id, "enabled": False, "distance_m": 57.0,
                      "line_a": [], "line_b": [], "line_a_norm": [], "line_b_norm": [], "reference_width": DEFAULT_ROI_REF_W, "reference_height": DEFAULT_ROI_REF_H, "updated_at": None}
    config = read_json_file(analytics_data_file(camera_id, "speed_lines"), default_config)
    config["ok"] = True
    config["camera_id"] = camera_id
    config.setdefault("enabled", False)
    config.setdefault("distance_m", 57.0)
    config.setdefault("updated_at", None)
    # migrate legacy
    if not config.get("line_a_norm") or not config.get("line_b_norm"):
        la = clean_points_list(config.get("line_a", []), max_points=2)
        lb = clean_points_list(config.get("line_b", []), max_points=2)
        if la and lb:
            ref_w, ref_h = _infer_legacy_ref_w_h(la + lb)
            ref_w = int(config.get("reference_width", ref_w))
            ref_h = int(config.get("reference_height", ref_h))
            config["line_a_norm"] = _normalize_from_absolute(la, ref_w, ref_h)
            config["line_b_norm"] = _normalize_from_absolute(lb, ref_w, ref_h)
            config["reference_width"] = ref_w
            config["reference_height"] = ref_h
            config["line_a"] = _denormalize_to_absolute(config["line_a_norm"], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
            config["line_b"] = _denormalize_to_absolute(config["line_b_norm"], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
            write_json_file(analytics_data_file(camera_id, "speed_lines"), {k: v for k, v in config.items() if k not in ("ok", "camera_id")})
        else:
            config.setdefault("line_a", [])
            config.setdefault("line_b", [])
            config.setdefault("line_a_norm", [])
            config.setdefault("line_b_norm", [])
            config.setdefault("reference_width", DEFAULT_ROI_REF_W)
            config.setdefault("reference_height", DEFAULT_ROI_REF_H)
    else:
        # sync absolute for legacy clients
        ref_w = int(config.get("reference_width", DEFAULT_ROI_REF_W))
        ref_h = int(config.get("reference_height", DEFAULT_ROI_REF_H))
        config["line_a_norm"] = _clean_norm_points(config.get("line_a_norm"), max_points=2)
        config["line_b_norm"] = _clean_norm_points(config.get("line_b_norm"), max_points=2)
        config["line_a"] = _denormalize_to_absolute(config["line_a_norm"], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
        config["line_b"] = _denormalize_to_absolute(config["line_b_norm"], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    return config


@app.post("/api/analytics/{camera_id}/speed-lines")
def post_analytics_speed_lines(camera_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    analytics_identity(camera_id)
    try:
        distance_m = float(payload.get("distance_m", 57.0))
    except Exception:
        raise HTTPException(status_code=400, detail="distance_m must be a number")
    if distance_m <= 0:
        raise HTTPException(status_code=400, detail="distance_m must be > 0")
    enabled = bool(payload.get("enabled", True))
    # accept normalized first
    la_norm = _clean_norm_points(payload.get("line_a_norm") or payload.get("line_a") or [], max_points=2)
    lb_norm = _clean_norm_points(payload.get("line_b_norm") or payload.get("line_b") or [], max_points=2)
    if la_norm and lb_norm:
        ref_w = int(payload.get("reference_width") or payload.get("referenceWidth") or DEFAULT_ROI_REF_W)
        ref_h = int(payload.get("reference_height") or payload.get("referenceHeight") or DEFAULT_ROI_REF_H)
    else:
        la = clean_points_list(payload.get("line_a"), max_points=2)
        lb = clean_points_list(payload.get("line_b"), max_points=2)
        if enabled and (len(la) != 2 or len(lb) != 2):
            raise HTTPException(status_code=400, detail="line_a and line_b must contain exactly 2 points each")
        if la and lb:
            ref_w, ref_h = _infer_legacy_ref_w_h(la + lb)
            ref_w = int(payload.get("reference_width") or ref_w)
            ref_h = int(payload.get("reference_height") or ref_h)
            la_norm = _normalize_from_absolute(la, ref_w, ref_h)
            lb_norm = _normalize_from_absolute(lb, ref_w, ref_h)
        else:
            la_norm, lb_norm, ref_w, ref_h = [], [], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H
    if enabled and (len(la_norm) != 2 or len(lb_norm) != 2):
        raise HTTPException(status_code=400, detail="line_a and line_b must contain exactly 2 points each")
    line_a = _denormalize_to_absolute(la_norm, DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    line_b = _denormalize_to_absolute(lb_norm, DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    config = {"ok": True, "camera_id": camera_id, "enabled": enabled, "distance_m": distance_m,
              "line_a": line_a, "line_b": line_b, "line_a_norm": la_norm, "line_b_norm": lb_norm, "reference_width": ref_w, "reference_height": ref_h, "updated_at": now_iso()}
    write_json_file(analytics_data_file(camera_id, "speed_lines"), {k: v for k, v in config.items() if k not in ("ok", "camera_id")})
    return config


def get_analytics_crossing_line(camera_id: str) -> Dict[str, Any]:
    analytics_identity(camera_id)
    default_config = {"ok": True, "camera_id": camera_id, "enabled": False, "line": [], "line_norm": [], "reference_width": DEFAULT_ROI_REF_W, "reference_height": DEFAULT_ROI_REF_H, "updated_at": None}
    config = read_json_file(analytics_data_file(camera_id, "crossing_line"), default_config)
    config["ok"] = True
    config["camera_id"] = camera_id
    config.setdefault("enabled", False)
    config.setdefault("updated_at", None)
    if not config.get("line_norm"):
        legacy = clean_points_list(config.get("line", []), max_points=2)
        if legacy:
            ref_w, ref_h = _infer_legacy_ref_w_h(legacy)
            ref_w = int(config.get("reference_width", ref_w))
            ref_h = int(config.get("reference_height", ref_h))
            config["line_norm"] = _normalize_from_absolute(legacy, ref_w, ref_h)
            config["reference_width"] = ref_w
            config["reference_height"] = ref_h
            config["line"] = _denormalize_to_absolute(config["line_norm"], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
            write_json_file(analytics_data_file(camera_id, "crossing_line"), {k: v for k, v in config.items() if k not in ("ok", "camera_id")})
        else:
            config.setdefault("line", [])
            config.setdefault("line_norm", [])
            config.setdefault("reference_width", DEFAULT_ROI_REF_W)
            config.setdefault("reference_height", DEFAULT_ROI_REF_H)
    else:
        ref_w = int(config.get("reference_width", DEFAULT_ROI_REF_W))
        ref_h = int(config.get("reference_height", DEFAULT_ROI_REF_H))
        config["line_norm"] = _clean_norm_points(config.get("line_norm"), max_points=2)
        config["line"] = _denormalize_to_absolute(config["line_norm"], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    return config


def post_analytics_crossing_line(camera_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    analytics_identity(camera_id)
    enabled = bool(payload.get("enabled", True))
    norm = _clean_norm_points(payload.get("line_norm") or payload.get("line") or [], max_points=2)
    if norm:
        ref_w = int(payload.get("reference_width") or payload.get("referenceWidth") or DEFAULT_ROI_REF_W)
        ref_h = int(payload.get("reference_height") or payload.get("referenceHeight") or DEFAULT_ROI_REF_H)
        line_norm = norm
    else:
        legacy = clean_points_list(payload.get("line"), max_points=2)
        if enabled and len(legacy) != 2:
            raise HTTPException(status_code=400, detail="line must contain exactly 2 points")
        if legacy:
            ref_w, ref_h = _infer_legacy_ref_w_h(legacy)
            ref_w = int(payload.get("reference_width") or ref_w)
            ref_h = int(payload.get("reference_height") or ref_h)
            line_norm = _normalize_from_absolute(legacy, ref_w, ref_h)
        else:
            line_norm, ref_w, ref_h = [], DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H
            if enabled:
                raise HTTPException(status_code=400, detail="line must contain exactly 2 points")
    if enabled and len(line_norm) != 2:
        raise HTTPException(status_code=400, detail="line must contain exactly 2 points")
    line = _denormalize_to_absolute(line_norm, DEFAULT_ROI_REF_W, DEFAULT_ROI_REF_H)
    config = {"ok": True, "camera_id": camera_id, "enabled": enabled,
              "line": line, "line_norm": line_norm, "reference_width": ref_w, "reference_height": ref_h, "updated_at": now_iso()}
    write_json_file(analytics_data_file(camera_id, "crossing_line"), {k: v for k, v in config.items() if k not in ("ok", "camera_id")})
    return config


CROSSINGS_STORE_LIMIT = 5000
CROSSING_DIRECTIONS = ("left_to_right", "right_to_left")


def crossings_store_path(camera_id: str) -> Path:
    return analytics_data_file(camera_id, "crossings")


def append_crossing_record(camera_id: str, record: Dict[str, Any]) -> None:
    path = crossings_store_path(camera_id)
    records = read_json_file(path, [])
    if not isinstance(records, list):
        records = []
    records.insert(0, record)
    write_json_file(path, records[:CROSSINGS_STORE_LIMIT])


def post_analytics_crossing(camera_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    identity = analytics_identity(camera_id)
    direction = str(data.get("direction") or "")
    if direction not in CROSSING_DIRECTIONS:
        raise HTTPException(status_code=400, detail="direction must be left_to_right or right_to_left")
    object_type = str(data.get("object_type") or data.get("class_name") or "").strip()
    if not object_type:
        raise HTTPException(status_code=400, detail="object_type is required")
    event_id = str(data.get("event_id") or f"{int(time.time())}-{uuid.uuid4().hex[:8]}")
    created_at = str(data.get("created_at") or now_iso())
    track_id = optional_int(data.get("track_id"))
    record = {
        "event_id": event_id,
        "camera_id": camera_id,
        "analytics_profile": identity["analytics_profile"],
        "domain": identity["domain"],
        "object_type": object_type,
        "class_name": object_type,
        "model_class": str(data.get("model_class") or object_type),
        "direction": direction,
        "track_id": track_id,
        "confidence": optional_float(data.get("confidence")),
        "speed_kmh": optional_float(data.get("speed_kmh")),
        "kind": "line_crossing",
        "created_at": created_at,
    }
    # Road-domain person crossings feed counters/summary only; the objects
    # registry and the event feed remain person-free (Issue #263 contract).
    if not (identity["domain"] == "road" and object_type == "person"):
        persist_object_event(record)
    append_crossing_record(camera_id, record)
    return {"ok": True, "event_id": event_id}


VLZ_TIMEZONE = timezone(timedelta(hours=10))


def _vlz_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time()).replace(tzinfo=VLZ_TIMEZONE)
    return start, start + timedelta(days=1)


def get_analytics_crossings_summary(
    camera_id: str, hours: int = 24,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
) -> Dict[str, Any]:
    identity = analytics_identity(camera_id)
    records = read_json_file(crossings_store_path(camera_id), [])
    if not isinstance(records, list):
        records = []
    window: Dict[str, Any] = {"mode": "rolling_hours", "hours": max(1, min(int(hours), 168))}
    if date_from or date_to:
        try:
            from_day = date.fromisoformat(date_from) if date_from else None
            to_day = date.fromisoformat(date_to) if date_to else None
        except ValueError:
            raise HTTPException(status_code=400, detail="dates must be YYYY-MM-DD")
        if from_day and to_day and from_day > to_day:
            raise HTTPException(status_code=400, detail="date_from must not exceed date_to")
        start = _vlz_day_bounds(from_day)[0] if from_day else datetime.min.replace(tzinfo=timezone.utc)
        end = _vlz_day_bounds(to_day)[1] if to_day else datetime.max.replace(tzinfo=timezone.utc)
        window = {"mode": "vlz_days", "date_from": str(from_day) if from_day else None,
                  "date_to": str(to_day) if to_day else None}
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window["hours"])
    totals = {"left_to_right": 0, "right_to_left": 0}
    by_class: Dict[str, Dict[str, int]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        created_at = str(record.get("created_at") or "")
        try:
            moment = datetime.fromisoformat(created_at)
        except ValueError:
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        if window["mode"] == "vlz_days":
            if moment < start or moment >= end:
                continue
        elif moment < cutoff:
            continue
        direction = str(record.get("direction") or "")
        if direction not in CROSSING_DIRECTIONS:
            continue
        class_name = str(record.get("object_type") or record.get("class_name") or "object")
        totals[direction] += 1
        class_counts = by_class.setdefault(class_name, {"left_to_right": 0, "right_to_left": 0})
        class_counts[direction] += 1
    return {
        "ok": True,
        "camera_id": camera_id,
        "domain": identity["domain"],
        "window": window,
        "totals": totals,
        "by_class": by_class,
        "generated_at": now_iso(),
    }


@app.get("/api/analytics/{camera_id}/crossing-line")
def api_get_crossing_line(camera_id: str) -> Dict[str, Any]:
    return get_analytics_crossing_line(camera_id)


@app.post("/api/analytics/{camera_id}/crossing-line")
def api_post_crossing_line(camera_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return post_analytics_crossing_line(camera_id, payload)


@app.post("/api/analytics/{camera_id}/crossings")
async def api_post_crossing(
    camera_id: str,
    metadata: str = Form(...),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    require_auth(authorization)
    try:
        data = json.loads(metadata)
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="metadata must be valid JSON")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="metadata must be a JSON object")
    return post_analytics_crossing(camera_id, data)


@app.get("/api/analytics/{camera_id}/crossings/summary")
def api_get_crossings_summary(
    camera_id: str, hours: int = 24,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
) -> Dict[str, Any]:
    return get_analytics_crossings_summary(camera_id, hours, date_from, date_to)


@app.get("/api/analytics/{camera_id}/objects")
def get_analytics_objects(
    camera_id: str, limit: int = 50, offset: int = 0, date_from: Optional[str] = None,
    date_to: Optional[str] = None, class_name: Optional[str] = None, status: Optional[str] = None,
    speed_min: Optional[float] = None, speed_max: Optional[float] = None, search: Optional[str] = None,
    include_deleted: bool = False, object_type: Optional[str] = None,
) -> Dict[str, Any]:
    identity = analytics_identity(camera_id)
    return get_objects(limit, offset, date_from, date_to, class_name, status, speed_min, speed_max, search,
                       include_deleted, camera_id, identity["domain"], identity["analytics_profile"], object_type)


@app.get("/api/objects")
def get_objects(
    limit: int = 50, offset: int = 0, date_from: Optional[str] = None, date_to: Optional[str] = None,
    class_name: Optional[str] = None, status: Optional[str] = None, speed_min: Optional[float] = None,
    speed_max: Optional[float] = None, search: Optional[str] = None, include_deleted: bool = False,
    camera_id: Optional[str] = None, domain: Optional[str] = None, analytics_profile: Optional[str] = None,
    object_type: Optional[str] = None,
) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    if camera_id:
        analytics_identity(camera_id)
    if speed_min is not None and speed_min < 0:
        raise HTTPException(status_code=400, detail="speed_min must be >= 0")
    if speed_max is not None and speed_max < 0:
        raise HTTPException(status_code=400, detail="speed_max must be >= 0")
    if speed_min is not None and speed_max is not None and speed_min > speed_max:
        raise HTTPException(status_code=400, detail="speed_min must be <= speed_max")
    where_sql, values = build_objects_where(
        date_from, date_to, class_name, status, speed_min, speed_max, search, include_deleted,
        camera_id, domain, analytics_profile, object_type,
    )
    with open_objects_db() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM objects WHERE {where_sql}", values).fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM objects WHERE {where_sql} ORDER BY detected_at DESC, object_id DESC LIMIT ? OFFSET ?",
            [*values, limit, offset],
        ).fetchall()
    return {"ok": True, "count": len(rows), "total": total, "limit": limit, "offset": offset,
            "objects": [object_row_to_dict(row) for row in rows]}


@app.get("/api/objects/{object_id}")
def get_object(object_id: str) -> Dict[str, Any]:
    with open_objects_db() as connection:
        row = connection.execute("SELECT * FROM objects WHERE object_id = ? AND deleted_at IS NULL", (object_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return {"ok": True, "object": object_row_to_dict(row, include_original=True)}


@app.patch("/api/objects/{object_id}")
def patch_object(object_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return patch_object_record(object_id, payload)


@app.delete("/api/objects/{object_id}")
def delete_object(object_id: str) -> Dict[str, Any]:
    return delete_object_record(object_id)


@app.get("/api/worker/control")
def get_worker_control(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("GET", "/v1/status")
    payload["requested_by"] = username
    return payload


@app.post("/api/worker/control/start")
def start_worker_control(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("POST", "/v1/start")
    payload["requested_by"] = username
    return payload


@app.post("/api/worker/control/stop")
def stop_worker_control(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("POST", "/v1/stop")
    payload["requested_by"] = username
    return payload


@app.get("/api/worker/control/road1")
def get_road_worker_control(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("GET", "/v1/road1/status")
    payload["requested_by"] = username
    return payload


@app.post("/api/worker/control/road1/start")
def start_road_worker_control(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("POST", "/v1/road1/start")
    payload["requested_by"] = username
    return payload


@app.post("/api/worker/control/road1/stop")
def stop_road_worker_control(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("POST", "/v1/road1/stop")
    payload["requested_by"] = username
    return payload


@app.get("/api/session")
def get_session_identity(x_authentik_username: Optional[str] = Header(None)) -> Dict[str, Any]:
    username = (x_authentik_username or "").strip()
    if not username:
        raise HTTPException(status_code=503, detail="Trusted Authentik identity is unavailable")
    return {"ok": True, "username": username}


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "service": "sea-speed-api", "api_schema": API_SCHEMA,
            "source_commit": deployed_source_commit(), "time": now_iso()}
