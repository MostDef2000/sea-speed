#!/usr/bin/env python3
"""Bounded private HTTP control surface for the two fixed Sea Speed AI workers."""
from __future__ import annotations

import hmac
import ipaddress
import json
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

SERVICE_NAME = "sea-speed-worker.service"
ROAD_SERVICE_NAME = "sea-speed-road-worker.service"
WORKER_CONTROL_PROTOCOL = "sea_speed_worker_control_v1"
DEFAULT_INSTALL_ROOT = "/opt/sea-speed-worker"
DEFAULT_LISTEN = "10.123.239.102:19001"
CONTROL_TARGETS = {
    "water": {
        "service": SERVICE_NAME,
        "desired_state": ("shared", "runtime", "operator-desired-state"),
        "paths": ("/v1/status", "/v1/start", "/v1/stop"),
    },
    "road1": {
        "service": ROAD_SERVICE_NAME,
        "desired_state": ("shared", "road-runtime", "operator-desired-state"),
        "paths": ("/v1/road1/status", "/v1/road1/start", "/v1/road1/stop"),
    },
}
ALLOWED_PATHS = {
    path
    for target in CONTROL_TARGETS.values()
    for path in target["paths"]
}
PATH_TARGET_ACTION = {
    "/v1/status": ("water", "status"),
    "/v1/start": ("water", "start"),
    "/v1/stop": ("water", "stop"),
    "/v1/road1/status": ("road1", "status"),
    "/v1/road1/start": ("road1", "start"),
    "/v1/road1/stop": ("road1", "stop"),
}


def parse_private_listen(value: str) -> tuple[str, int]:
    raw = value.strip()
    if raw.count(":") != 1:
        raise ValueError("control listen must be literal IPv4:port")
    host, raw_port = raw.rsplit(":", 1)
    address = ipaddress.ip_address(host)
    port = int(raw_port)
    private = tuple(ipaddress.ip_network(x) for x in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
    if address.version != 4 or address.is_loopback or not any(address in network for network in private):
        raise ValueError("control listen must use non-loopback RFC1918 IPv4")
    if not 1024 <= port <= 65535:
        raise ValueError("control listen port must be 1024..65535")
    return str(address), port


def target_config(target: str = "water") -> dict[str, Any]:
    try:
        return CONTROL_TARGETS[target]
    except KeyError as exc:
        raise ValueError("unsupported worker control target") from exc


def service_name(target: str = "water") -> str:
    return str(target_config(target)["service"])


def desired_state_path(target: str = "water") -> Path:
    install_root = os.environ.get("SEA_SPEED_WORKER_INSTALL_ROOT", DEFAULT_INSTALL_ROOT).strip() or DEFAULT_INSTALL_ROOT
    return Path(install_root).joinpath(*target_config(target)["desired_state"])


def read_desired_state(target: str = "water") -> str:
    path = desired_state_path(target)
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "running"
    return value if value in {"running", "stopped"} else "running"


def write_desired_state(value: str, target: str = "water") -> None:
    if value not in {"running", "stopped"}:
        raise ValueError("invalid desired state")
    path = desired_state_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="operator-desired-state.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o644)
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def systemctl(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    allowed = set()
    for target in CONTROL_TARGETS:
        fixed_service = service_name(target)
        allowed.update(
            {
                ("is-active", "--quiet", fixed_service),
                ("is-enabled", fixed_service),
                ("show", "--property=ActiveState,SubState", "--value", fixed_service),
                ("start", fixed_service),
                ("stop", fixed_service),
            }
        )
    if tuple(args) not in allowed:
        raise RuntimeError("unsupported systemctl operation")
    return subprocess.run(
        ["/bin/systemctl", *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=check,
    )


def service_status(target: str = "water") -> dict[str, Any]:
    fixed_service = service_name(target)
    active = systemctl("is-active", "--quiet", fixed_service).returncode == 0
    enabled_result = systemctl("is-enabled", fixed_service)
    enabled = enabled_result.returncode == 0 and enabled_result.stdout.strip() == "enabled"
    state_result = systemctl("show", "--property=ActiveState,SubState", "--value", fixed_service)
    values = [line.strip() for line in state_result.stdout.splitlines() if line.strip()]
    active_state = values[0] if values else ("active" if active else "inactive")
    sub_state = values[1] if len(values) > 1 else "unknown"
    return {
        "ok": True,
        "protocol": WORKER_CONTROL_PROTOCOL,
        "target": target,
        "service": fixed_service,
        "active": active,
        "enabled": enabled,
        "active_state": active_state,
        "sub_state": sub_state,
        "desired_state": read_desired_state(target),
    }


def stop_worker(target: str = "water") -> dict[str, Any]:
    fixed_service = service_name(target)
    write_desired_state("stopped", target)
    result = systemctl("stop", fixed_service)
    if result.returncode != 0:
        raise RuntimeError("worker stop failed")
    status = service_status(target)
    if status["active"]:
        raise RuntimeError("worker remained active after stop")
    return status


def start_worker(target: str = "water") -> dict[str, Any]:
    fixed_service = service_name(target)
    previous = read_desired_state(target)
    write_desired_state("running", target)
    result = systemctl("start", fixed_service)
    if result.returncode != 0:
        write_desired_state(previous, target)
        raise RuntimeError("worker start failed")
    status = service_status(target)
    if not status["active"]:
        write_desired_state(previous, target)
        raise RuntimeError("worker did not become active")
    return status


def token() -> str:
    return os.environ.get("SEA_SPEED_API_TOKEN", "")


def authorized(header: str | None) -> bool:
    expected = token()
    if not expected or not header or not header.startswith("Bearer "):
        return False
    supplied = header[7:]
    return hmac.compare_digest(supplied, expected)


class Handler(BaseHTTPRequestHandler):
    server_version = "SeaSpeedWorkerControl/1"

    def log_message(self, fmt: str, *args: object) -> None:
        print("worker-control", self.address_string(), fmt % args, flush=True)

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _guard(self) -> bool:
        if self.path not in ALLOWED_PATHS:
            self._send(404, {"ok": False, "error": "not_found"})
            return False
        if not authorized(self.headers.get("Authorization")):
            self._send(403, {"ok": False, "error": "forbidden"})
            return False
        return True

    def do_GET(self) -> None:
        if not self._guard():
            return
        target, action = PATH_TARGET_ACTION[self.path]
        if action != "status":
            self._send(405, {"ok": False, "error": "method_not_allowed"})
            return
        try:
            self._send(200, service_status(target))
        except Exception as exc:
            self._send(503, {"ok": False, "error": type(exc).__name__})

    def do_POST(self) -> None:
        if not self._guard():
            return
        target, action = PATH_TARGET_ACTION[self.path]
        if action not in {"start", "stop"}:
            self._send(405, {"ok": False, "error": "method_not_allowed"})
            return
        if self.headers.get("Content-Length") not in {None, "0"}:
            self._send(400, {"ok": False, "error": "request_body_not_allowed"})
            return
        try:
            payload = start_worker(target) if action == "start" else stop_worker(target)
            self._send(200, payload)
        except Exception as exc:
            self._send(503, {"ok": False, "error": type(exc).__name__})


if __name__ == "__main__":
    if not token():
        raise SystemExit("SEA_SPEED_API_TOKEN is required")
    host, port = parse_private_listen(os.environ.get("SEA_SPEED_WORKER_CONTROL_LISTEN", DEFAULT_LISTEN))
    print(
        f"worker-control listen={host}:{port} services={SERVICE_NAME},{ROAD_SERVICE_NAME}",
        flush=True,
    )
    ThreadingHTTPServer((host, port), Handler).serve_forever()
