"""Camera preview/snapshot service for the Sea Speed API (issue #396, wave 4).

Functions extracted verbatim from ``api/app/main.py``: relay source
validation (``validate_camera_preview_source``), catalog loading
(``load_camera_preview_catalog``), snapshot path/metadata/quality gates
(``camera_snapshot_path``, ``camera_snapshot_public_metadata``,
``build_camera_snapshot_extract_args``, ``camera_snapshot_luma_spread``,
``camera_snapshot_candidate_is_usable``), snapshot commit
(``commit_camera_snapshot_locked``) and the one-active-preview process
lifecycle (``camera_preview_public_state``, ``camera_preview_pid_matches``,
``cleanup_camera_preview_media``, ``terminate_camera_preview_locked``,
``active_camera_preview_locked``, ``build_camera_preview_ffmpeg_args``,
``start_camera_preview_locked``).

Module-state decision (wave-4 contract hazard check): this slice carries NO
mutable module state. The ``*_locked`` functions require the caller to hold
``config.CAMERA_PREVIEW_LOCK`` - the lock and every camera/preview constant
stay in ``config.py`` (wave 1 exactly-one-owner decision), and the routes in
``main.py`` keep acquiring the lock around these calls exactly as before.
Runtime state persists in the JSON state file (``CAMERA_PREVIEW_STATE_FILE``)
through ``store``'s stateless ``read_json_file``/``write_json_file`` helpers.
Same dual import idiom as the other ``api/app`` modules: one canonical
instance per import mode.
"""

import ipaddress
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from fastapi import HTTPException

try:  # package context (api.app.camera_preview) and direct-file load both supported
    from . import config  # noqa: F401  # explicit re-export seam (issue #396 wave 4)
    from .config import (  # noqa: F401  # explicit re-export seam (issue #396 wave 4)
        CAMERA_PREVIEW_CATALOG_FILE,
        CAMERA_PREVIEW_CATALOG_SCHEMA,
        CAMERA_PREVIEW_DIR,
        CAMERA_PREVIEW_FFMPEG_BIN,
        CAMERA_PREVIEW_ID_RE,
        CAMERA_PREVIEW_RFC1918,
        CAMERA_PREVIEW_SESSION_RE,
        CAMERA_PREVIEW_START_TIMEOUT_SEC,
        CAMERA_PREVIEW_STATE_FILE,
        CAMERA_PREVIEW_TTL_SEC,
        CAMERA_SNAPSHOT_DIR,
        CAMERA_SNAPSHOT_EXTRACT_TIMEOUT_SEC,
        CAMERA_SNAPSHOT_MIN_BYTES,
        CAMERA_SNAPSHOT_MIN_LUMA_SPREAD,
    )
    from . import store  # noqa: F401  # explicit re-export seam (issue #396 wave 4)
    from .store import read_json_file, write_json_file
except ImportError:  # direct uvicorn app-dir / spec_from_file_location execution
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config  # noqa: F401  # explicit re-export seam (issue #396 wave 4)
    from config import (  # noqa: F401  # explicit re-export seam (issue #396 wave 4)
        CAMERA_PREVIEW_CATALOG_FILE,
        CAMERA_PREVIEW_CATALOG_SCHEMA,
        CAMERA_PREVIEW_DIR,
        CAMERA_PREVIEW_FFMPEG_BIN,
        CAMERA_PREVIEW_ID_RE,
        CAMERA_PREVIEW_RFC1918,
        CAMERA_PREVIEW_SESSION_RE,
        CAMERA_PREVIEW_START_TIMEOUT_SEC,
        CAMERA_PREVIEW_STATE_FILE,
        CAMERA_PREVIEW_TTL_SEC,
        CAMERA_SNAPSHOT_DIR,
        CAMERA_SNAPSHOT_EXTRACT_TIMEOUT_SEC,
        CAMERA_SNAPSHOT_MIN_BYTES,
        CAMERA_SNAPSHOT_MIN_LUMA_SPREAD,
    )
    import store  # noqa: F401  # explicit re-export seam (issue #396 wave 4)
    from store import read_json_file, write_json_file

__all__ = [
    "validate_camera_preview_source",
    "load_camera_preview_catalog",
    "camera_snapshot_path",
    "camera_snapshot_public_metadata",
    "build_camera_snapshot_extract_args",
    "camera_snapshot_luma_spread",
    "camera_snapshot_candidate_is_usable",
    "commit_camera_snapshot_locked",
    "camera_preview_public_state",
    "camera_preview_pid_matches",
    "cleanup_camera_preview_media",
    "terminate_camera_preview_locked",
    "active_camera_preview_locked",
    "build_camera_preview_ffmpeg_args",
    "start_camera_preview_locked",
]

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
    try:
        state = read_json_file(CAMERA_PREVIEW_STATE_FILE, {})
    except store.JSON_READ_ERRORS as exc:
        raise HTTPException(status_code=500, detail="camera preview state is unreadable") from exc
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
    try:
        state = read_json_file(CAMERA_PREVIEW_STATE_FILE, {})
    except store.JSON_READ_ERRORS as exc:
        raise HTTPException(status_code=500, detail="camera preview state is unreadable") from exc
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
        "-hls_flags", "delete_segments+independent_segments+omit_endlist+program_date_time", "-hls_segment_type", "fmp4",
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
