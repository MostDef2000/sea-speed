import hashlib
import http.client
import ipaddress
import json
import os
import re
import signal
import sqlite3
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
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
CAMERA_PREVIEW_DIR = MEDIA_DIR / "camera-preview"
CAMERA_SNAPSHOT_DIR = DATA_DIR / "camera-preview-snapshots"
DEPLOYED_COMMIT_FILE = Path("/opt/sea-speed-deploy/state/current-release")

STATE_FILE = DATA_DIR / "cam1_state.json"
EVENTS_FILE = DATA_DIR / "events.json"
OBJECTS_DB_FILE = DATA_DIR / "objects.sqlite3"
ROI_FILE = DATA_DIR / "cam1_roi.json"
SPEED_CONFIG_FILE = DATA_DIR / "cam1_speed_config.json"
SPEED_LINES_FILE = DATA_DIR / "cam1_speed_lines.json"
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
        raise HTTPException(
            status_code=503,
            detail="Trusted Authentik identity is unavailable",
        )
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
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_objects_detected_at ON objects(detected_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_objects_class_name ON objects(class_name)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_objects_speed_kmh ON objects(speed_kmh)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_objects_status ON objects(status)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_objects_deleted_at ON objects(deleted_at)"
        )


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


def persist_object_event(event: Dict[str, Any]) -> bool:
    object_id = stable_object_id(event)
    detected_at = str(event.get("created_at") or event.get("detected_at") or now_iso())
    created_at = str(event.get("created_at") or now_iso())
    original_event_json = json.dumps(event, ensure_ascii=False, sort_keys=True)
    with open_objects_db() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO objects (
                object_id, camera_id, track_id, detected_at, class_name,
                confidence, speed_kmh, snapshot_url, comment, status,
                original_event_json, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', 'new', ?, ?, ?, NULL)
            """,
            (
                object_id,
                str(event.get("camera_id") or "cam1"),
                optional_int(event.get("track_id")),
                detected_at,
                str(event.get("class_name") or event.get("class") or "object"),
                optional_float(event.get("confidence")),
                optional_float(event.get("speed_kmh")),
                event.get("snapshot_url"),
                original_event_json,
                created_at,
                now_iso(),
            ),
        )
        return cursor.rowcount > 0


def import_existing_events() -> int:
    events = read_json_file(EVENTS_FILE, [])
    if not isinstance(events, list):
        return 0
    imported = 0
    for event in events:
        if isinstance(event, dict) and persist_object_event(event):
            imported += 1
    return imported


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
) -> tuple[str, List[Any]]:
    clauses = ["camera_id = ?"]
    values: List[Any] = ["cam1"]
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
    return " AND ".join(clauses), values


def default_state() -> Dict[str, Any]:
    return {
        "camera_id": "cam1",
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
        "last_overlay_url": None,
        "message": "No worker state received yet",
    }


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
    return {
        "available": True,
        "url": f"/sea-speed/api/cameras/{camera_id}/snapshot?v={stat.st_mtime_ns}",
        "updated_at": updated_at,
    }


def build_camera_snapshot_extract_args(playlist: Path, output_path: Path) -> List[str]:
    return [
        CAMERA_PREVIEW_FFMPEG_BIN,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-live_start_index",
        "-1",
        "-i",
        str(playlist),
        "-map",
        "0:v:0",
        "-frames:v",
        "1",
        "-vf",
        "scale=640:-2",
        "-q:v",
        "3",
        "-y",
        str(output_path),
    ]


def camera_snapshot_luma_spread(path: Path) -> Optional[float]:
    args = [
        CAMERA_PREVIEW_FFMPEG_BIN,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-vf",
        "signalstats,metadata=print",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=CAMERA_SNAPSHOT_EXTRACT_TIMEOUT_SEC,
            check=False,
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
            build_camera_snapshot_extract_args(playlist, temp_path),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=CAMERA_SNAPSHOT_EXTRACT_TIMEOUT_SEC,
            check=False,
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
        "camera_id": state.get("camera_id"),
        "display_name": state.get("display_name"),
        "session_id": state.get("session_id"),
        "hls_url": state.get("hls_url"),
        "started_at": state.get("started_at"),
        "expires_at": state.get("expires_at"),
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
        cmdline = (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\x00", b" ").decode(
            "utf-8", errors="replace"
        )
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
        CAMERA_PREVIEW_FFMPEG_BIN,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        source,
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        "scale=640:-2,fps=8",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "zerolatency",
        "-profile:v",
        "baseline",
        "-pix_fmt",
        "yuv420p",
        "-g",
        "16",
        "-keyint_min",
        "16",
        "-sc_threshold",
        "0",
        "-t",
        str(CAMERA_PREVIEW_TTL_SEC),
        "-f",
        "hls",
        "-hls_time",
        "1",
        "-hls_list_size",
        "4",
        "-hls_flags",
        "delete_segments+independent_segments+omit_endlist",
        "-hls_segment_type",
        "fmp4",
        "-hls_fmp4_init_filename",
        "init.mp4",
        "-hls_segment_filename",
        str(output_dir / "segment_%05d.m4s"),
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
        process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        cleanup_camera_preview_media({"session_id": session_id})
        raise HTTPException(status_code=503, detail="Camera preview transcoder failed to start") from exc
    state: Dict[str, Any] = {
        "camera_id": camera["camera_id"],
        "display_name": camera["display_name"],
        "session_id": session_id,
        "pid": process.pid,
        "output_dir": str(output_dir),
        "hls_url": hls_url,
        "started_at": started_at,
        "expires_at": expires_at,
        "expires_epoch": expires_epoch,
        "ttl_sec": CAMERA_PREVIEW_TTL_SEC,
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


@app.get("/api/cameras")
def get_cameras() -> Dict[str, Any]:
    cameras = load_camera_preview_catalog()
    with CAMERA_PREVIEW_LOCK:
        active = camera_preview_public_state(active_camera_preview_locked())
    public_cameras = [
        {
            "camera_id": camera["camera_id"],
            "display_name": camera["display_name"],
            "available": True,
            "snapshot": camera_snapshot_public_metadata(camera["camera_id"]),
        }
        for camera in cameras
    ]
    return {
        "ok": True,
        "schema": CAMERA_PREVIEW_CATALOG_SCHEMA,
        "count": len(public_cameras),
        "cameras": public_cameras,
        "active": active,
        "preview_policy": {"max_active": 1, "ttl_sec": CAMERA_PREVIEW_TTL_SEC},
    }

@app.get("/api/cameras/{camera_id}/snapshot")
def get_camera_snapshot(camera_id: str):
    cameras = load_camera_preview_catalog()
    if not any(entry["camera_id"] == camera_id for entry in cameras):
        raise HTTPException(status_code=404, detail="Camera is not present in the preview catalog")
    path = camera_snapshot_path(camera_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Camera snapshot is not available")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )


@app.post("/api/cameras/{camera_id}/snapshot/commit")
def commit_camera_snapshot(camera_id: str, session_id: str) -> Dict[str, Any]:
    cameras = load_camera_preview_catalog()
    if not any(entry["camera_id"] == camera_id for entry in cameras):
        raise HTTPException(status_code=404, detail="Camera is not present in the preview catalog")
    if not CAMERA_PREVIEW_SESSION_RE.fullmatch(session_id):
        raise HTTPException(status_code=409, detail="Camera preview session is stale")
    with CAMERA_PREVIEW_LOCK:
        state = active_camera_preview_locked()
        if (
            not state
            or state.get("camera_id") != camera_id
            or state.get("session_id") != session_id
        ):
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
async def post_cam1_state(
    metadata: str = Form(...),
    overlay: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    require_auth(authorization)
    try:
        data = json.loads(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON")
    data["camera_id"] = "cam1"
    data.setdefault("state_schema", WORKER_STATE_SCHEMA)
    data.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    data.setdefault("worker_source_commit", None)
    data["updated_at"] = now_iso()
    data["worker_online"] = True
    if overlay is not None:
        overlay_path = OVERLAY_DIR / "cam1_latest_overlay.jpg"
        content = await overlay.read()
        overlay_path.write_bytes(content)
        data["last_overlay_url"] = "/sea-speed/media/overlays/cam1_latest_overlay.jpg"
    else:
        old_state = read_json_file(STATE_FILE, default_state())
        data["last_overlay_url"] = old_state.get("last_overlay_url")
    write_json_file(STATE_FILE, data)
    return {"ok": True, "state": data}


@app.get("/api/cam1/events")
def get_cam1_events(limit: int = 50) -> Dict[str, Any]:
    events = read_json_file(EVENTS_FILE, [])
    events = events[: max(1, min(limit, 200))]
    return {"ok": True, "camera_id": "cam1", "count": len(events), "events": events}


@app.post("/api/cam1/events")
async def post_cam1_event(
    metadata: str = Form(...),
    snapshot: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    require_auth(authorization)
    try:
        event = json.loads(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON")
    event_id = str(event.get("event_id") or uuid.uuid4())
    event["event_id"] = event_id
    event["camera_id"] = "cam1"
    event.setdefault("event_schema", VEHICLE_EVENT_SCHEMA)
    event.setdefault("telemetry_schema", TELEMETRY_SCHEMA)
    event.setdefault("worker_source_commit", None)
    event.setdefault("calibration_version", None)
    event["created_at"] = event.get("created_at") or now_iso()
    if snapshot is not None:
        filename = f"{event_id}.jpg"
        snapshot_path = EVENTS_MEDIA_DIR / filename
        content = await snapshot.read()
        snapshot_path.write_bytes(content)
        event["snapshot_url"] = f"/sea-speed/media/events/{filename}"
    persist_object_event(event)
    events: List[Dict[str, Any]] = read_json_file(EVENTS_FILE, [])
    events.insert(0, event)
    events = events[:500]
    write_json_file(EVENTS_FILE, events)
    return {"ok": True, "event": event}


@app.get("/api/cam1/objects")
def get_cam1_objects(
    limit: int = 50,
    offset: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    class_name: Optional[str] = None,
    status: Optional[str] = None,
    speed_min: Optional[float] = None,
    speed_max: Optional[float] = None,
    search: Optional[str] = None,
    include_deleted: bool = False,
) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    if speed_min is not None and speed_min < 0:
        raise HTTPException(status_code=400, detail="speed_min must be >= 0")
    if speed_max is not None and speed_max < 0:
        raise HTTPException(status_code=400, detail="speed_max must be >= 0")
    if speed_min is not None and speed_max is not None and speed_min > speed_max:
        raise HTTPException(status_code=400, detail="speed_min must be <= speed_max")
    where_sql, values = build_objects_where(
        date_from, date_to, class_name, status, speed_min, speed_max, search, include_deleted
    )
    with open_objects_db() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM objects WHERE {where_sql}", values
        ).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT * FROM objects
            WHERE {where_sql}
            ORDER BY detected_at DESC, object_id DESC
            LIMIT ? OFFSET ?
            """,
            [*values, limit, offset],
        ).fetchall()
    return {
        "ok": True,
        "camera_id": "cam1",
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "objects": [object_row_to_dict(row) for row in rows],
    }


@app.get("/api/cam1/objects/{object_id}")
def get_cam1_object(object_id: str) -> Dict[str, Any]:
    with open_objects_db() as connection:
        row = connection.execute(
            "SELECT * FROM objects WHERE object_id = ? AND camera_id = ? AND deleted_at IS NULL",
            (object_id, "cam1"),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return {"ok": True, "object": object_row_to_dict(row, include_original=True)}


@app.patch("/api/cam1/objects/{object_id}")
def patch_cam1_object(object_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
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
    values = [*updates.values(), object_id, "cam1"]
    with open_objects_db() as connection:
        cursor = connection.execute(
            f"UPDATE objects SET {set_sql} WHERE object_id = ? AND camera_id = ? AND deleted_at IS NULL",
            values,
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Object not found")
        row = connection.execute(
            "SELECT * FROM objects WHERE object_id = ? AND camera_id = ?",
            (object_id, "cam1"),
        ).fetchone()
    return {"ok": True, "object": object_row_to_dict(row, include_original=True)}


@app.delete("/api/cam1/objects/{object_id}")
def delete_cam1_object(object_id: str) -> Dict[str, Any]:
    deleted_at = now_iso()
    with open_objects_db() as connection:
        cursor = connection.execute(
            """
            UPDATE objects
            SET deleted_at = ?, updated_at = ?
            WHERE object_id = ? AND camera_id = ? AND deleted_at IS NULL
            """,
            (deleted_at, deleted_at, object_id, "cam1"),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Object not found")
    return {"ok": True, "object_id": object_id, "deleted_at": deleted_at}


@app.get("/api/cam1/roi")
def get_cam1_roi() -> Dict[str, Any]:
    default_roi = {"ok": True, "camera_id": "cam1", "enabled": False, "polygon": [], "updated_at": None}
    roi = read_json_file(ROI_FILE, default_roi)
    roi["ok"] = True
    roi["camera_id"] = "cam1"
    roi.setdefault("enabled", False)
    roi.setdefault("polygon", [])
    roi.setdefault("updated_at", None)
    return roi


@app.post("/api/cam1/roi")
def post_cam1_roi(payload: Dict[str, Any]) -> Dict[str, Any]:
    polygon = payload.get("polygon", [])
    enabled = bool(payload.get("enabled", True))
    clean_polygon = []
    if isinstance(polygon, list):
        for point in polygon:
            if not isinstance(point, dict):
                continue
            try:
                x = int(round(float(point.get("x"))))
                y = int(round(float(point.get("y"))))
            except Exception:
                continue
            clean_polygon.append({"x": x, "y": y})
    if enabled and len(clean_polygon) < 3:
        raise HTTPException(status_code=400, detail="ROI polygon must contain at least 3 points")
    roi = {
        "ok": True,
        "camera_id": "cam1",
        "enabled": enabled,
        "polygon": clean_polygon,
        "updated_at": now_iso(),
    }
    write_json_file(ROI_FILE, roi)
    return roi


@app.get("/api/cam1/speed-config")
def get_cam1_speed_config() -> Dict[str, Any]:
    default_config = {
        "ok": True,
        "camera_id": "cam1",
        "enabled": False,
        "kmh_per_px_s": 0.0,
        "updated_at": None,
    }
    config = read_json_file(SPEED_CONFIG_FILE, default_config)
    config["ok"] = True
    config["camera_id"] = "cam1"
    config.setdefault("enabled", False)
    config.setdefault("kmh_per_px_s", 0.0)
    config.setdefault("updated_at", None)
    return config


@app.post("/api/cam1/speed-config")
def post_cam1_speed_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    enabled = bool(payload.get("enabled", True))
    try:
        kmh_per_px_s = float(payload.get("kmh_per_px_s", 0.0))
    except Exception:
        raise HTTPException(status_code=400, detail="kmh_per_px_s must be a number")
    if kmh_per_px_s < 0:
        raise HTTPException(status_code=400, detail="kmh_per_px_s must be >= 0")
    config = {
        "ok": True,
        "camera_id": "cam1",
        "enabled": enabled and kmh_per_px_s > 0,
        "kmh_per_px_s": kmh_per_px_s,
        "updated_at": now_iso(),
    }
    write_json_file(SPEED_CONFIG_FILE, config)
    return config


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


@app.get("/api/cam1/speed-lines")
def get_cam1_speed_lines() -> Dict[str, Any]:
    default_config = {
        "ok": True,
        "camera_id": "cam1",
        "enabled": False,
        "distance_m": 57.0,
        "line_a": [],
        "line_b": [],
        "updated_at": None,
    }
    config = read_json_file(SPEED_LINES_FILE, default_config)
    config["ok"] = True
    config["camera_id"] = "cam1"
    config.setdefault("enabled", False)
    config.setdefault("distance_m", 57.0)
    config.setdefault("line_a", [])
    config.setdefault("line_b", [])
    config.setdefault("updated_at", None)
    return config


@app.post("/api/cam1/speed-lines")
def post_cam1_speed_lines(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        distance_m = float(payload.get("distance_m", 57.0))
    except Exception:
        raise HTTPException(status_code=400, detail="distance_m must be a number")
    if distance_m <= 0:
        raise HTTPException(status_code=400, detail="distance_m must be > 0")
    line_a = clean_points_list(payload.get("line_a"), max_points=2)
    line_b = clean_points_list(payload.get("line_b"), max_points=2)
    enabled = bool(payload.get("enabled", True))
    if enabled and (len(line_a) != 2 or len(line_b) != 2):
        raise HTTPException(status_code=400, detail="line_a and line_b must contain exactly 2 points each")
    config = {
        "ok": True,
        "camera_id": "cam1",
        "enabled": enabled,
        "distance_m": distance_m,
        "line_a": line_a,
        "line_b": line_b,
        "updated_at": now_iso(),
    }
    write_json_file(SPEED_LINES_FILE, config)
    return config


@app.get("/api/worker/control")
def get_worker_control(
    x_authentik_username: Optional[str] = Header(None),
) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("GET", "/v1/status")
    payload["requested_by"] = username
    return payload


@app.post("/api/worker/control/start")
def start_worker_control(
    x_authentik_username: Optional[str] = Header(None),
) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("POST", "/v1/start")
    payload["requested_by"] = username
    return payload


@app.post("/api/worker/control/stop")
def stop_worker_control(
    x_authentik_username: Optional[str] = Header(None),
) -> Dict[str, Any]:
    username = require_operator_identity(x_authentik_username)
    payload = call_worker_control("POST", "/v1/stop")
    payload["requested_by"] = username
    return payload


@app.get("/api/session")
def get_session_identity(
    x_authentik_username: Optional[str] = Header(None),
) -> Dict[str, Any]:
    username = (x_authentik_username or "").strip()
    if not username:
        raise HTTPException(
            status_code=503,
            detail="Trusted Authentik identity is unavailable",
        )
    return {"ok": True, "username": username}


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "sea-speed-api",
        "api_schema": API_SCHEMA,
        "source_commit": deployed_source_commit(),
        "time": now_iso(),
    }
