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
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from fastapi import HTTPException

try:  # package context (api.app.identity) and direct-file load both supported
    from .config import (
        ADMIN_USERS,
        ANALYTICS_IDENTITIES,
        API_TOKEN,
        CAMERA_PREVIEW_RFC1918,
        DEPLOYED_COMMIT_FILE,
        EDGE_AUTH_SECRET,
        OPERATOR_USERS,
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
        ADMIN_USERS,
        ANALYTICS_IDENTITIES,
        API_TOKEN,
        CAMERA_PREVIEW_RFC1918,
        DEPLOYED_COMMIT_FILE,
        EDGE_AUTH_SECRET,
        OPERATOR_USERS,
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
    "require_role",
    "resolve_role",
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


# Issue #520: module logger. Private: never part of __all__.
_LOGGER = logging.getLogger(__name__)

# Issue #530: authentik group names are exact, case-sensitive whole-token
# matches against the groups defined in
# deploy/vps/authentik/blueprints/sea-speed-auth-v1.yaml. Tokens are split on
# commas only, trimmed, and never matched by substring, case folding or any
# other delimiter; unknown tokens grant nothing. Multiple recognized
# memberships resolve the highest role; none resolves viewer.
AUTHENTIK_GROUP_OWNER = "Sea Speed Owner"
AUTHENTIK_GROUP_ADMIN = "Sea Speed Admin"
AUTHENTIK_GROUP_OPERATOR = "Sea Speed Operator"
AUTHENTIK_GROUP_VIEWER = "Sea Speed Viewer"

_GROUP_ROLES = {
    AUTHENTIK_GROUP_OWNER: "admin",
    AUTHENTIK_GROUP_ADMIN: "admin",
    AUTHENTIK_GROUP_OPERATOR: "operator",
    AUTHENTIK_GROUP_VIEWER: "viewer",
}
_ROLE_RANK = {"viewer": 0, "operator": 1, "admin": 2}

# Audit rendering escapes C0/C1 control characters (including newline and
# ANSI escapes) so one record stays one single-line, log-safe entry.
_AUDIT_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _escape_audit_text(value: str) -> str:
    return _AUDIT_CONTROL_CHARS_RE.sub(
        lambda match: f"\\x{ord(match.group(0)):02x}", value
    )


def require_operator_identity(
    x_authentik_username: Optional[str],
    x_sea_speed_edge_auth: Optional[str] = None,
) -> str:
    # Issue #520: strict mode (secret set) requires the edge-injected shared
    # secret to match BEFORE any username handling, so a forged
    # X-Authentik-Username reveals nothing. When the secret is unset or blank
    # (#520 residual, approved in the #537 batch 2026-10-19) the endpoint
    # fails closed with 503: operator identity is unavailable rather than
    # accepted without edge verification. The secret value is never logged
    # or echoed.
    expected = EDGE_AUTH_SECRET.strip()
    if expected:
        # Compare UTF-8 bytes: hmac.compare_digest rejects non-ASCII str
        # operands with TypeError, and the edge header is client-controlled —
        # a forged value must surface as 403, never as a comparison crash.
        provided = (x_sea_speed_edge_auth or "").encode("utf-8")
        if not hmac.compare_digest(expected.encode("utf-8"), provided):
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        raise HTTPException(status_code=503, detail="Trusted Authentik identity is unavailable")
    username = (x_authentik_username or "").strip()
    if not username:
        raise HTTPException(status_code=503, detail="Trusted Authentik identity is unavailable")
    return username


def resolve_role(username: str, x_authentik_groups: Optional[str]) -> str:
    """Resolve the application role for a VERIFIED username (issue #530).

    Precondition: ``username`` is the trimmed value returned by
    ``require_operator_identity`` — never a raw client header; it is used
    exactly and case-sensitively as-is. Env override tiers are authoritative
    (not additive): the admin list resolves admin; else the operator list
    resolves operator — an operator-list match therefore overrides admin
    group membership, and membership in both lists resolves admin. Without an
    env match, X-Authentik-Groups is split on commas only, each token is
    trimmed and matched exactly against the recognized group names, and the
    highest recognized role wins. Absent, blank or wholly unrecognized groups
    resolve viewer.
    """
    if username in ADMIN_USERS:
        return "admin"
    if username in OPERATOR_USERS:
        return "operator"
    highest: Optional[str] = None
    for token in (x_authentik_groups or "").split(","):
        token = token.strip()
        role = _GROUP_ROLES.get(token)
        if role is None:
            continue
        if highest is None or _ROLE_RANK[role] > _ROLE_RANK[highest]:
            highest = role
    return highest if highest is not None else "viewer"


def require_role(
    x_authentik_username: Optional[str],
    x_sea_speed_edge_auth: Optional[str],
    x_authentik_groups: Optional[str],
    *,
    minimum: str,
    action: str,
) -> str:
    """Verify identity, resolve the role and enforce the minimum (issue #530).

    Identity verification always runs first via the unchanged
    ``require_operator_identity`` (strict edge check, existing 403/503
    ordering; unconfigured secret fails closed with 503). An unsupported
    ``minimum``
    fails closed as a programming/configuration error (HTTP 500) and never
    authorizes. Insufficient role raises HTTP 403 "Forbidden"; failure paths
    never log raw headers, groups, edge secrets, payloads or unverified
    usernames. On success an authorized mutation-ATTEMPT record (not a claim
    of downstream mutation success) is emitted with the verified username
    (control characters escaped), the resolved role and the static action
    name. Returns the verified username for requested_by attribution.
    """
    username = require_operator_identity(x_authentik_username, x_sea_speed_edge_auth)
    role = resolve_role(username, x_authentik_groups)
    if minimum not in ("operator", "admin"):
        raise HTTPException(status_code=500, detail="Role minimum is misconfigured")
    if _ROLE_RANK[role] < _ROLE_RANK[minimum]:
        raise HTTPException(status_code=403, detail="Forbidden")
    _LOGGER.info(
        "authorized mutation attempt: user=%s role=%s action=%s",
        _escape_audit_text(username),
        role,
        action,
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
