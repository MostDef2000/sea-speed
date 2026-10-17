"""Deployment identity and trust primitives for the Sea Speed API (issue #396, wave 1).

Functions extracted verbatim from ``api/app/main.py``: ingestion-token
request authentication, trusted operator identity (Authentik header),
analytics camera identity and the hardened worker-control client. Depends
only on ``config`` (constants) and ``fastapi.HTTPException`` (the originals
raised it directly); never imports ``main`` (import-cycle rule).

Single canonical import identity: the ``config`` constants are imported
through the same dual idiom ``main.py`` uses for the store seam (relative
import in package context; sys.path-anchored absolute import for
direct-file loads), so ``main`` and ``identity`` always share one config
module instance per process — no split-brain globals.
"""

import hmac
import http.client
import ipaddress
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from fastapi import HTTPException

try:  # package context (api.app.identity) and direct-file load both supported
    from .config import (
        ANALYTICS_IDENTITIES,
        API_TOKEN,
        CAMERA_PREVIEW_RFC1918,
        DEPLOYED_COMMIT_FILE,
        EDGE_AUTH_SECRET,
        SHA_RE,
        WORKER_CONTROL_PROTOCOL,
        WORKER_CONTROL_TIMEOUT_SEC,
        WORKER_CONTROL_TOKEN,
        WORKER_CONTROL_URL,
    )
except ImportError:  # direct uvicorn app-dir / spec_from_file_location execution
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import (
        ANALYTICS_IDENTITIES,
        API_TOKEN,
        CAMERA_PREVIEW_RFC1918,
        DEPLOYED_COMMIT_FILE,
        EDGE_AUTH_SECRET,
        SHA_RE,
        WORKER_CONTROL_PROTOCOL,
        WORKER_CONTROL_TIMEOUT_SEC,
        WORKER_CONTROL_TOKEN,
        WORKER_CONTROL_URL,
    )

__all__ = [
    "now_iso",
    "deployed_source_commit",
    "require_auth",
    "require_operator_identity",
    "worker_control_origin",
    "call_worker_control",
    "analytics_identity",
]


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


# Issue #520: module-level latch for the transitional-mode warning (one shot
# per process) and the module logger. Both are private: never part of __all__.
_LOGGER = logging.getLogger(__name__)
_EDGE_AUTH_TRANSITIONAL_WARNING_EMITTED = False


def require_operator_identity(
    x_authentik_username: Optional[str],
    x_sea_speed_edge_auth: Optional[str] = None,
) -> str:
    # Issue #520: strict mode (secret set) requires the edge-injected shared
    # secret to match BEFORE any username handling, so a forged
    # X-Authentik-Username reveals nothing. Transitional mode (secret
    # unset/blank) keeps the legacy semantics byte-identical and warns once
    # per process. The secret value is never logged or echoed.
    global _EDGE_AUTH_TRANSITIONAL_WARNING_EMITTED
    expected = EDGE_AUTH_SECRET.strip()
    if expected:
        # Compare UTF-8 bytes: hmac.compare_digest rejects non-ASCII str
        # operands with TypeError, and the edge header is client-controlled —
        # a forged value must surface as 403, never as a comparison crash.
        provided = (x_sea_speed_edge_auth or "").encode("utf-8")
        if not hmac.compare_digest(expected.encode("utf-8"), provided):
            raise HTTPException(status_code=403, detail="Forbidden")
    elif not _EDGE_AUTH_TRANSITIONAL_WARNING_EMITTED:
        if EDGE_AUTH_SECRET:
            _LOGGER.warning(
                "SEA_SPEED_EDGE_AUTH_SECRET is set but blank: operator identity is "
                "accepted without edge verification (transitional mode)"
            )
        else:
            _LOGGER.warning(
                "SEA_SPEED_EDGE_AUTH_SECRET is not set: operator identity is "
                "accepted without edge verification (transitional mode)"
            )
        _EDGE_AUTH_TRANSITIONAL_WARNING_EMITTED = True
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
    if not WORKER_CONTROL_TOKEN:
        raise HTTPException(status_code=500, detail="SEA_SPEED_WORKER_CONTROL_TOKEN is not set")
    host, port = worker_control_origin()
    connection = http.client.HTTPConnection(host, port, timeout=WORKER_CONTROL_TIMEOUT_SEC)
    try:
        headers = {"Authorization": f"Bearer {WORKER_CONTROL_TOKEN}", "Accept": "application/json"}
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
def analytics_identity(camera_id: str) -> Dict[str, str]:
    identity = ANALYTICS_IDENTITIES.get(camera_id)
    if identity is None:
        raise HTTPException(status_code=404, detail="Unknown analytics camera")
    return dict(identity)
