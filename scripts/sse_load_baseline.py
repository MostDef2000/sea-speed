#!/usr/bin/env python3
"""Bounded SSE load baseline for the Sea Speed API (issue #690).

This is an on-demand measurement tool, not a CI gate and not a production
probe. It never accepts a target URL: it binds an ephemeral IPv4 loopback
port, starts exactly ONE child Uvicorn worker serving the real
``api.app.main`` application against a temporary base directory and fixture
credentials, measures the frozen workload, then terminates and reaps the
child on every exit path.

Frozen workload (see ``specs/690-sse-load-baseline/spec.md``): the road route
and the water route are measured SEPARATELY at 1, 10 and 50 simultaneous
readers; each level runs 2 warm-up rounds and 3 measured rounds of
connect -> readiness barrier -> 20 numbered publishes at 50 ms ->
drain -> disconnect inside the same child.

The real 100 ms generator poll and the server's default thread pool are
preserved: nothing here mocks ``time.sleep``, advances the generators
serially, or raises the thread limiter. Only numbered ``id:``/``data:``
events for IDs published in the round count; the initial unnumbered
``data: {}`` frame and ``: keepalive`` comments are excluded.

Usage::

    python3 scripts/sse_load_baseline.py --output /tmp/opencode/690-baseline/report.json

The raw JSON report contains host state and is measurement output, never a
committed artifact. Exit codes: 0 all thresholds pass, 1 a frozen threshold
breached, 2 usage/configuration error, 3 environment could not boot the child.
"""

from __future__ import annotations

import argparse
import http.client
import importlib.metadata
import json
import math
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "sea_speed_sse_load_baseline_v1"

# Low-entropy, disposable fixture credentials for the temporary child only.
API_TOKEN_FIXTURE = "sse-baseline-fixture-690"
EDGE_HEADER_FIXTURE = "edge-fixture-690"
ADMIN_USER_FIXTURE = "fixture-admin-690"
WORKER_TOKEN_FIXTURE = "worker-fixture-690"
DEPLOYED_COMMIT_FIXTURE = "a" * 40

ROUTES: Dict[str, Dict[str, Any]] = {
    "road1": {
        "post_path": "/api/analytics/road1/live",
        "aliases": (
            "/api/analytics/road1/live/stream",
            "/sea-speed/api/analytics/road1/live/stream",
        ),
        "envelope": lambda frame_no: {
            "schema": "sea_speed_road_live_v1",
            "camera_id": "road1",
            "analytics_profile": "road-v1",
            "domain": "road",
            "frame_no": frame_no,
            "generation": 1,
            "frame_width": 1280,
            "frame_height": 720,
            "observed_mono": round(frame_no * 0.05, 3),
            "detections": [],
            "crossings": {},
        },
    },
    "cam1": {
        "post_path": "/api/cam1/live",
        "aliases": (
            "/api/cam1/live/stream",
            "/sea-speed/api/cam1/live/stream",
        ),
        "envelope": lambda frame_no: {
            "schema": "sea_speed_water_live_v1",
            "camera_id": "cam1",
            "analytics_profile": "water-v1",
            "domain": "water",
            "frame_no": frame_no,
            "generation": 1,
            "frame_width": 1920,
            "frame_height": 1080,
            "observed_mono": round(frame_no * 0.05, 3),
            "detections": [],
        },
    },
}

# Frozen thresholds: record these in spec.md before measuring and never move
# them after seeing a number. Values are evaluated per (route, readers) cell.
THRESHOLDS: Dict[str, Any] = {
    "latency_ms": {"p50": 150.0, "p95": 300.0, "max": 1000.0},
    "delivery": {"missing": 0, "duplicates": 0, "complete_readers_per_round": "N"},
    "cpu_seconds_per_wall_second": {"1": 0.50, "10": 0.50, "50": 2.00},
    "memory_mib": {"retained_growth": 32.0, "spread": 16.0},
    "fds": {"retained_growth": 8},
    "sockets_established": {"at_barrier_reader": "N", "after_close_reader": 0},
    "headers": {
        "status": 200,
        "content_type_prefix": "text/event-stream",
        "cache_control_contains": "no-cache",
        "x_accel_buffering": "no",
        "initial_frame": True,
    },
}

URLISH = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class BaselineError(RuntimeError):
    """A configuration/environment failure that prevents a measurement."""


def _reject_target_url(argv: Sequence[str]) -> None:
    """The harness owns its server; a URL-shaped argument is never accepted."""

    for token in argv:
        if URLISH.match(token):
            raise SystemExit(
                "error: this harness accepts no target URL (it owns a loopback "
                f"child); refusing argument {token!r}"
            )


def percentile(samples: Sequence[float], pct: float) -> Optional[float]:
    """Nearest-rank percentile (p50/p95) over one pooled sample list."""

    if not samples:
        return None
    ordered = sorted(samples)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def parse_sse_block(block: str) -> Tuple[str, Optional[int]]:
    """Classify one SSE event block without counting scaffolding as delivery.

    Returns ``("delivery", id)`` for a block carrying both ``id:`` and
    ``data:``, ``("initial", None)`` for the unnumbered initial ``data: {}``
    frame, ``("keepalive", None)`` for a ``:`` comment block, and
    ``("other", None)`` for anything else (including malformed ids).
    """

    lines = [line.rstrip("\r") for line in block.split("\n")]
    if any(line.startswith(":") for line in lines):
        return "keepalive", None
    raw_id: Optional[str] = None
    has_data = False
    for line in lines:
        if line.startswith("id:"):
            raw_id = line[3:].strip()
        elif line.startswith("data:"):
            has_data = True
    if not has_data:
        return "other", None
    if raw_id is None:
        return "initial", None
    try:
        return "delivery", int(raw_id)
    except ValueError:
        return "other", None


def read_mem_total_mib() -> Optional[float]:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return round(int(line.split()[1]) / 1024.0, 1)
    except OSError:
        return None
    return None


def sample_process(pid: int) -> Dict[str, Optional[float]]:
    """Sample server CPU seconds, RSS MiB and open FDs from /proc."""

    sample: Dict[str, Optional[float]] = {"cpu_seconds": None, "rss_mib": None, "fds": None}
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        rest = stat.rsplit(")", 1)[1].split()
        ticks = os.sysconf("SC_CLK_TCK")
        sample["cpu_seconds"] = (int(rest[11]) + int(rest[12])) / float(ticks)
    except (OSError, IndexError, ValueError):
        pass
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                sample["rss_mib"] = round(int(line.split()[1]) / 1024.0, 2)
                break
    except (OSError, IndexError, ValueError):
        pass
    try:
        sample["fds"] = float(len(os.listdir(f"/proc/{pid}/fd")))
    except OSError:
        pass
    return sample


def count_server_sockets(server_port: int, reader_ports: Set[int]) -> Dict[str, int]:
    """Count ESTABLISHED sockets on the server port, split reader vs other.

    ``/proc/net/tcp`` is Linux-only; on another platform the caller sees an
    empty dict and must treat the socket thresholds as non-conclusive.
    """

    total = 0
    reader = 0
    try:
        lines = Path("/proc/net/tcp").read_text(encoding="utf-8").splitlines()[1:]
    except OSError:
        return {"total_established": -1, "reader_established": -1}
    for line in lines:
        fields = line.split()
        if len(fields) < 4 or fields[3] != "01":
            continue
        try:
            local_port = int(fields[1].split(":")[1], 16)
            remote_port = int(fields[2].split(":")[1], 16)
        except (IndexError, ValueError):
            continue
        if local_port != server_port:
            continue
        total += 1
        if remote_port in reader_ports:
            reader += 1
    return {"total_established": total, "reader_established": reader}


def _dependency_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


class Reader(threading.Thread):
    """One SSE client connection: connect, read the initial frame, then stream."""

    def __init__(
        self,
        host: str,
        port: int,
        path: str,
        read_timeout: float,
        start_timeout: float,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.path = path
        self.read_timeout = read_timeout
        self.start_timeout = start_timeout
        self.stop_event = stop_event
        self.ready = threading.Event()
        self.lock = threading.Lock()
        self.conn: Optional[http.client.HTTPConnection] = None
        self.client_port: Optional[int] = None
        self.status: Optional[int] = None
        self.headers: Dict[str, str] = {}
        self.initial = False
        self.keepalives = 0
        self.malformed = 0
        self.deliveries: List[int] = []
        self.recv_times: List[Tuple[int, float]] = []
        self.error: Optional[str] = None

    def run(self) -> None:  # noqa: D401 - thread entrypoint
        try:
            self._stream()
        except BaseException as exc:  # noqa: BLE001 - record, never kill the run
            if not self.stop_event.is_set():
                self.error = f"{type(exc).__name__}: {exc}"
        finally:
            self.ready.set()
            self.close()

    def _stream(self) -> None:
        self.conn = http.client.HTTPConnection(self.host, self.port, timeout=self.read_timeout)
        self.conn.connect()
        sock = self.conn.sock
        if sock is not None:
            self.client_port = sock.getsockname()[1]
        self.conn.request(
            "GET",
            self.path,
            headers={
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        response = self.conn.getresponse()
        self.status = response.status
        self.headers = {name.lower(): value for name, value in response.getheaders()}
        buffer = ""
        start_deadline = time.monotonic() + self.start_timeout
        while not self.initial and time.monotonic() < start_deadline:
            try:
                chunk = response.read1(65536)
            except (TimeoutError, socket.timeout):
                continue
            if not chunk:
                raise BaselineError("stream closed before the initial frame")
            buffer = self._consume(buffer + chunk.decode("utf-8", "replace"))
        if not self.initial:
            raise BaselineError("initial frame timeout")
        while not self.stop_event.is_set():
            try:
                chunk = response.read1(65536)
            except (TimeoutError, socket.timeout):
                continue
            if not chunk:
                break
            buffer = self._consume(buffer + chunk.decode("utf-8", "replace"))

    def _consume(self, buffer: str) -> str:
        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            if not block.strip():
                continue
            kind, seq = parse_sse_block(block)
            if kind == "initial":
                self.initial = True
                self.ready.set()
            elif kind == "delivery" and seq is not None:
                with self.lock:
                    self.deliveries.append(seq)
                    self.recv_times.append((seq, time.monotonic()))
            elif kind == "keepalive":
                self.keepalives += 1
            elif kind == "other":
                self.malformed += 1
        return buffer

    def snapshot_ids(self) -> List[int]:
        with self.lock:
            return list(self.deliveries)

    def snapshot_latency_input(self) -> List[Tuple[int, float]]:
        with self.lock:
            return list(self.recv_times)

    def _close_socket(self) -> None:
        conn = self.conn
        if conn is None:
            return
        sock = conn.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        try:
            conn.close()
        except OSError:
            pass

    def close(self) -> None:
        """Stop this reader and close its socket (safe from the main thread)."""

        self._close_socket()


class ChildServer:
    """Owns the one disposable Uvicorn worker and its temporary data root."""

    def __init__(self, base_dir: Path, start_timeout: float) -> None:
        self.base_dir = base_dir
        self.start_timeout = start_timeout
        self.proc: Optional[subprocess.Popen] = None
        self.port: Optional[int] = None
        self.log_file = None
        self.host = "127.0.0.1"

    def _child_env(self) -> Dict[str, str]:
        deployed_file = self.base_dir / "deploy-state" / "current-release"
        deployed_file.parent.mkdir(parents=True, exist_ok=True)
        deployed_file.write_text(DEPLOYED_COMMIT_FIXTURE + "\n", encoding="utf-8")
        env = dict(os.environ)
        env.update(
            {
                "SEA_SPEED_BASE_DIR": str(self.base_dir),
                "SEA_SPEED_DEPLOYED_COMMIT_FILE": str(deployed_file),
                "SEA_SPEED_API_TOKEN": API_TOKEN_FIXTURE,
                "SEA_SPEED_EDGE_AUTH_SECRET": EDGE_HEADER_FIXTURE,
                "SEA_SPEED_ADMIN_USERS": ADMIN_USER_FIXTURE,
                "SEA_SPEED_WORKER_CONTROL_TOKEN": WORKER_TOKEN_FIXTURE,
                "SEA_SPEED_WORKER_CONTROL_URL": "http://127.0.0.1:19001",
            }
        )
        env.pop("SEA_SPEED_SOURCE_COMMIT", None)
        return env

    @staticmethod
    def _ephemeral_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            return int(probe.getsockname()[1])

    def start(self) -> None:
        env = self._child_env()
        log_path = self.base_dir / "child.log"
        attempts = 3
        for attempt in range(1, attempts + 1):
            port = self._ephemeral_port()
            self.log_file = open(log_path, "wb")
            self.proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "api.app.main:app",
                    "--host", self.host,
                    "--port", str(port),
                    "--workers", "1",
                    "--log-level", "warning",
                ],
                cwd=str(REPO_ROOT),
                env=env,
                stdout=self.log_file,
                stderr=subprocess.STDOUT,
            )
            self.port = port
            if self._wait_ready():
                return
            log_text = self._log_tail()
            self.stop()
            bind_conflict = "address already in use" in log_text.lower()
            if not bind_conflict or attempt == attempts:
                raise BaselineError(
                    "environment lacks a bootable Uvicorn child for api.app.main:app"
                    + ("" if bind_conflict else f"; child log: {log_text[-1500:]}")
                )

    def _wait_ready(self) -> bool:
        deadline = time.monotonic() + self.start_timeout
        assert self.port is not None
        while time.monotonic() < deadline:
            if self.proc is not None and self.proc.poll() is not None:
                return False
            try:
                conn = http.client.HTTPConnection(self.host, self.port, timeout=1.0)
                conn.request("GET", "/api/health")
                response = conn.getresponse()
                body = response.read()
                conn.close()
                if response.status == 200 and json.loads(body.decode("utf-8")).get("ok"):
                    return True
            except (OSError, ValueError, http.client.HTTPException):
                time.sleep(0.2)
        return False

    def _log_tail(self) -> str:
        try:
            return (self.base_dir / "child.log").read_text(encoding="utf-8", errors="replace")[-4000:]
        except OSError:
            return "<no child log>"

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        proc = self.proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        if self.log_file is not None:
            try:
                self.log_file.close()
            except OSError:
                pass
            self.log_file = None
        self.proc = None


def open_alias_once(host: str, port: int, path: str, timeout: float) -> Dict[str, Any]:
    """Smoke one alias spelling: headers on the actual response + initial frame."""

    result: Dict[str, Any] = {
        "path": path,
        "status": None,
        "content_type": None,
        "cache_control": None,
        "x_accel_buffering": None,
        "initial_frame": False,
        "error": None,
    }
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path, headers={"Accept": "text/event-stream"})
        response = conn.getresponse()
        headers = {name.lower(): value for name, value in response.getheaders()}
        result["status"] = response.status
        result["content_type"] = headers.get("content-type")
        result["cache_control"] = headers.get("cache-control")
        result["x_accel_buffering"] = headers.get("x-accel-buffering")
        buffer = ""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = response.read1(65536)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", "replace")
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                kind, _ = parse_sse_block(block)
                if kind == "initial":
                    result["initial_frame"] = True
                    return result
    except (OSError, http.client.HTTPException) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        sock = conn.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        conn.close()
    return result


def publish_round(
    route_name: str,
    host: str,
    port: int,
    count: int,
    interval: float,
    post_timeout: float,
) -> Tuple[Dict[int, float], List[str]]:
    """Publish numbered envelopes and map server seq -> publish monotonic time."""

    route = ROUTES[route_name]
    seq_times: Dict[int, float] = {}
    errors: List[str] = []
    start = time.monotonic()
    for index in range(count):
        target = start + index * interval
        envelope = route["envelope"](index + 1)
        payload = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
        conn = http.client.HTTPConnection(host, port, timeout=post_timeout)
        try:
            conn.connect()
            t_pub = time.monotonic()
            conn.request(
                "POST",
                route["post_path"],
                body=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {API_TOKEN_FIXTURE}",
                },
            )
            response = conn.getresponse()
            body = response.read()
            if response.status != 200:
                errors.append(f"POST status {response.status}: {body[:200]!r}")
            else:
                seq = int(json.loads(body.decode("utf-8"))["live_seq"])
                seq_times[seq] = t_pub
        except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException) as exc:
            errors.append(f"POST failed: {type(exc).__name__}: {exc}")
        finally:
            conn.close()
        remaining = target + interval - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
    return seq_times, errors


def _wait_reader_sockets(port: int, reader_ports: Set[int], expected: int, timeout: float) -> Dict[str, int]:
    deadline = time.monotonic() + timeout
    observed = count_server_sockets(port, reader_ports)
    while time.monotonic() < deadline:
        if observed["reader_established"] >= expected:
            return observed
        time.sleep(0.02)
        observed = count_server_sockets(port, reader_ports)
    return observed


def _wait_reader_sockets_clear(port: int, reader_ports: Set[int], timeout: float) -> Dict[str, int]:
    deadline = time.monotonic() + timeout
    observed = count_server_sockets(port, reader_ports)
    while time.monotonic() < deadline:
        if observed["reader_established"] <= 0:
            return observed
        time.sleep(0.02)
        observed = count_server_sockets(port, reader_ports)
    return observed


def run_round(
    route_name: str,
    readers_count: int,
    host: str,
    port: int,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """One connect -> barrier -> publish -> drain -> disconnect round."""

    alias = ROUTES[route_name]["aliases"][0]
    stop_event = threading.Event()
    readers = [
        Reader(host, port, alias, args.read_timeout, args.start_timeout, stop_event)
        for _ in range(readers_count)
    ]
    result: Dict[str, Any] = {
        "publish_errors": [],
        "expected_ids": [],
        "latency_samples_ms": [],
        "readers": [],
        "barrier_sockets": {"total_established": -1, "reader_established": -1},
        "close_sockets": {"total_established": -1, "reader_established": -1},
        "drain_seconds": None,
        "error": None,
    }
    try:
        for reader in readers:
            reader.start()
        ready_deadline = time.monotonic() + args.start_timeout + 1.0
        for reader in readers:
            remaining = max(0.0, ready_deadline - time.monotonic())
            reader.ready.wait(remaining)
        failures = [r for r in readers if not r.initial]
        if failures:
            result["error"] = "readers not ready: " + "; ".join(
                f"port={r.client_port} err={r.error or 'no initial frame'}" for r in failures[:5]
            )
            return result
        reader_ports = {int(r.client_port) for r in readers if r.client_port is not None}
        result["barrier_sockets"] = _wait_reader_sockets(port, reader_ports, readers_count, 2.0)

        publish_start = time.monotonic()
        seq_times, publish_errors = publish_round(
            route_name, host, port, args.messages, args.interval_ms / 1000.0, args.post_timeout
        )
        publish_end = time.monotonic()
        result["publish_errors"] = publish_errors
        expected = set(seq_times)
        result["expected_ids"] = sorted(expected)
        drain_deadline = time.monotonic() + args.drain_timeout
        while time.monotonic() < drain_deadline:
            if all(expected.issubset(set(reader.snapshot_ids())) for reader in readers):
                break
            time.sleep(0.02)
        result["drain_seconds"] = round(time.monotonic() - publish_end, 3)
        result["publish_seconds"] = round(publish_end - publish_start, 3)
    finally:
        stop_event.set()
        for reader in readers:
            reader.close()
        for reader in readers:
            reader.join(timeout=2.0)
        if result["expected_ids"]:
            reader_ports = {int(r.client_port) for r in readers if r.client_port is not None}
            result["close_sockets"] = _wait_reader_sockets_clear(port, reader_ports, 2.0)

    expected = set(result["expected_ids"])
    latency_input: List[Tuple[int, float]] = []
    missing_total = 0
    duplicate_total = 0
    complete_readers = 0
    received_total = 0
    reader_rows: List[Dict[str, Any]] = []
    for reader in readers:
        ids = reader.snapshot_ids()
        counts = Counter(ids)
        duplicates = sum(count - 1 for count in counts.values() if count > 1)
        missing = sorted(expected - set(ids))
        if not missing and duplicates == 0 and expected:
            complete_readers += 1
        received_total += len([sid for sid in ids if sid in expected])
        missing_total += len(missing)
        duplicate_total += duplicates
        latency_input.extend(reader.snapshot_latency_input())
        reader_rows.append(
            {
                "client_port": reader.client_port,
                "status": reader.status,
                "received": len([sid for sid in ids if sid in expected]),
                "missing": missing,
                "duplicates": duplicates,
                "error": reader.error,
            }
        )
    samples_ms = [
        round((recv - seq_times[seq]) * 1000.0, 3)
        for seq, recv in latency_input
        if seq in seq_times
    ]
    result.update(
        {
            "readers": reader_rows,
            "latency_samples_ms": samples_ms,
            "missing_total": missing_total,
            "duplicate_total": duplicate_total,
            "complete_readers": complete_readers,
            "received_total": received_total,
        }
    )
    return result


def run_cell(
    route_name: str,
    readers_count: int,
    server: ChildServer,
    args: argparse.Namespace,
    level_deadline: float,
) -> Dict[str, Any]:
    """Warm-up + measured rounds for one (route, readers) cell."""

    assert server.port is not None and server.proc is not None
    pid = server.proc.pid
    assert pid is not None
    cell: Dict[str, Any] = {
        "route": route_name,
        "readers": readers_count,
        "status": "measured",
        "error": None,
        "rounds": [],
        "post_warmup": None,
        "measured_samples": [],
    }
    post_warmup: Optional[Dict[str, Optional[float]]] = None
    cpu_pairs: List[Tuple[float, Optional[float], float, Optional[float]]] = []

    if args.warmup_rounds == 0:
        # No warm-up rounds: the pre-measurement sample is the plateau baseline.
        post_warmup = sample_process(pid)
    total_rounds = args.warmup_rounds + args.rounds
    for index in range(total_rounds):
        measured = index >= args.warmup_rounds
        if time.monotonic() > level_deadline:
            cell["status"] = "aborted"
            cell["error"] = "level deadline exceeded"
            break
        pre_sample = sample_process(pid)
        t_start = time.monotonic()
        round_result = run_round(route_name, readers_count, server.host, server.port, args)
        t_end = time.monotonic()
        post_sample = sample_process(pid)
        round_result["wall_seconds"] = round(t_end - t_start, 3)
        if measured:
            cell["rounds"].append(round_result)
            cell["measured_samples"].append(post_sample)
            cpu_pairs.append((t_start, pre_sample.get("cpu_seconds"), t_end, post_sample.get("cpu_seconds")))
        elif index == args.warmup_rounds - 1:
            post_warmup = post_sample
        if round_result.get("error"):
            cell["status"] = "failed"
            cell["error"] = round_result["error"]
    cell["post_warmup"] = post_warmup
    cell["cpu_window"] = None
    if cpu_pairs:
        first_start, first_cpu = cpu_pairs[0][0], cpu_pairs[0][1]
        last_end, last_cpu = cpu_pairs[-1][2], cpu_pairs[-1][3]
        if first_cpu is not None and last_cpu is not None and last_end > first_start:
            cpu = last_cpu - first_cpu
            wall = last_end - first_start
            cell["cpu_window"] = {
                "cpu_seconds": round(cpu, 4),
                "wall_seconds": round(wall, 4),
                "cpu_per_wall": round(cpu / wall, 4),
            }
    return cell


def summarise_cell(cell: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    """Pool the measured rounds of one cell into metric values + verdicts."""

    rounds = cell["rounds"]
    latency_pool: List[float] = []
    missing_total = 0
    duplicate_total = 0
    complete_reader_rounds = 0
    received_total = 0
    publish_errors = 0
    barrier_reader: List[int] = []
    barrier_total: List[int] = []
    close_reader: List[int] = []
    for item in rounds:
        latency_pool.extend(item["latency_samples_ms"])
        missing_total += item.get("missing_total", 0)
        duplicate_total += item.get("duplicate_total", 0)
        complete_reader_rounds += item.get("complete_readers", 0)
        received_total += item.get("received_total", 0)
        publish_errors += len(item.get("publish_errors", []))
        barrier_reader.append(item["barrier_sockets"]["reader_established"])
        barrier_total.append(item["barrier_sockets"]["total_established"])
        close_reader.append(item["close_sockets"]["reader_established"])

    window = (args.messages * args.interval_ms) / 1000.0
    reader_rounds = len(rounds) * cell["readers"]
    rounds_n = max(1, len(rounds))
    aggregate = round((received_total / rounds_n) / window, 3) if window else None
    summary: Dict[str, Any] = {
        "rounds_measured": len(rounds),
        "publish_errors": publish_errors,
        "latency_ms": {
            "samples": len(latency_pool),
            "p50": round(percentile(latency_pool, 50) or 0.0, 3) if latency_pool else None,
            "p95": round(percentile(latency_pool, 95) or 0.0, 3) if latency_pool else None,
            "max": round(max(latency_pool), 3) if latency_pool else None,
        },
        "delivery": {
            "expected_ids_per_round": args.messages,
            "missing_total": missing_total,
            "duplicates_total": duplicate_total,
            "complete_reader_rounds": complete_reader_rounds,
            "reader_rounds": reader_rounds,
        },
        "throughput": {
            "publish_window_seconds": round(window, 3),
            "aggregate_numbered_msgs_per_s": aggregate,
            "per_client_numbered_msgs_per_s": (
                round(aggregate / cell["readers"], 3) if aggregate is not None else None
            ),
        },
        "server_cpu": cell.get("cpu_window"),
        "memory": _warm_memory(cell),
        "fds": _warm_fds(cell),
        "sockets": {
            "at_barrier_reader": max(barrier_reader) if barrier_reader else None,
            "at_barrier_total": max(barrier_total) if barrier_total else None,
            "after_close_reader": max(close_reader) if close_reader else None,
        },
    }
    return summary


def _warm_memory(cell: Dict[str, Any]) -> Dict[str, Any]:
    post = cell.get("post_warmup") or {}
    samples = cell.get("measured_samples") or []
    rss = [item.get("rss_mib") for item in samples if item.get("rss_mib") is not None]
    post_rss = post.get("rss_mib")
    retained = round(rss[-1] - post_rss, 2) if rss and post_rss is not None else None
    spread = round(max(rss) - min(rss), 2) if len(rss) >= 2 else None
    return {
        "post_warmup_rss_mib": post_rss,
        "measured_rss_mib": rss,
        "retained_growth_mib": retained,
        "spread_mib": spread,
    }


def _warm_fds(cell: Dict[str, Any]) -> Dict[str, Any]:
    post = cell.get("post_warmup") or {}
    samples = cell.get("measured_samples") or []
    fds = [item.get("fds") for item in samples if item.get("fds") is not None]
    post_fds = post.get("fds")
    retained = int(fds[-1] - post_fds) if fds and post_fds is not None else None
    return {
        "post_warmup_fds": int(post_fds) if post_fds is not None else None,
        "measured_fds": [int(value) for value in fds],
        "retained_growth": retained,
    }


def evaluate_cell(readers_count: int, summary: Dict[str, Any]) -> List[str]:
    """Compare one cell against the frozen thresholds; return failure strings."""

    failures: List[str] = []
    latency = summary["latency_ms"]
    if latency["samples"] == 0:
        failures.append("latency: no numbered samples")
    else:
        if latency["p50"] > THRESHOLDS["latency_ms"]["p50"]:
            failures.append(f"LAT-P50 {latency['p50']} ms > {THRESHOLDS['latency_ms']['p50']} ms")
        if latency["p95"] > THRESHOLDS["latency_ms"]["p95"]:
            failures.append(f"LAT-P95 {latency['p95']} ms > {THRESHOLDS['latency_ms']['p95']} ms")
        if latency["max"] > THRESHOLDS["latency_ms"]["max"]:
            failures.append(f"LAT-MAX {latency['max']} ms > {THRESHOLDS['latency_ms']['max']} ms")
    delivery = summary["delivery"]
    if delivery["missing_total"] != 0:
        failures.append(f"DEL-MISS {delivery['missing_total']} missing numbered IDs")
    if delivery["duplicates_total"] != 0:
        failures.append(f"DEL-DUP {delivery['duplicates_total']} duplicate numbered IDs")
    expected_complete = delivery["reader_rounds"]
    if delivery["complete_reader_rounds"] != expected_complete:
        failures.append(
            f"DEL-COMPLETE {delivery['complete_reader_rounds']}/{expected_complete} complete reader-rounds"
        )
    if summary["publish_errors"]:
        failures.append(f"publish errors: {summary['publish_errors']}")
    cpu = summary["server_cpu"]
    budget = THRESHOLDS["cpu_seconds_per_wall_second"].get(str(readers_count))
    if cpu is None:
        failures.append("CPU: /proc CPU sample unavailable")
    elif budget is not None and cpu["cpu_per_wall"] > budget:
        failures.append(f"CPU-{readers_count} {cpu['cpu_per_wall']} s/s > {budget} s/s")
    memory = summary["memory"]
    if memory["retained_growth_mib"] is None:
        failures.append("MEM: RSS sample unavailable")
    elif memory["retained_growth_mib"] > THRESHOLDS["memory_mib"]["retained_growth"]:
        failures.append(
            f"MEM-GROW {memory['retained_growth_mib']} MiB > "
            f"{THRESHOLDS['memory_mib']['retained_growth']} MiB"
        )
    if memory["spread_mib"] is not None and memory["spread_mib"] > THRESHOLDS["memory_mib"]["spread"]:
        failures.append(f"MEM-SPREAD {memory['spread_mib']} MiB > {THRESHOLDS['memory_mib']['spread']} MiB")
    fds = summary["fds"]
    if fds["retained_growth"] is None:
        failures.append("FD: open-FD sample unavailable")
    elif fds["retained_growth"] > THRESHOLDS["fds"]["retained_growth"]:
        failures.append(f"FD-RETAIN {fds['retained_growth']} > {THRESHOLDS['fds']['retained_growth']}")
    sockets = summary["sockets"]
    if sockets["at_barrier_reader"] is None or sockets["at_barrier_reader"] < 0:
        failures.append("SOCK: /proc/net/tcp unavailable")
    else:
        if sockets["at_barrier_reader"] != readers_count:
            failures.append(
                f"SOCK-BARRIER {sockets['at_barrier_reader']} != {readers_count}"
            )
        if sockets["after_close_reader"] != 0:
            failures.append(f"SOCK-CLOSE {sockets['after_close_reader']} != 0")
    return failures


def smoke_failures(smoke: Iterable[Dict[str, Any]]) -> List[str]:
    failures: List[str] = []
    for item in smoke:
        prefix = f"SMOKE {item['path']}"
        if item["error"]:
            failures.append(f"{prefix}: {item['error']}")
        if item["status"] != THRESHOLDS["headers"]["status"]:
            failures.append(f"{prefix}: status {item['status']}")
        if not (item["content_type"] or "").startswith(THRESHOLDS["headers"]["content_type_prefix"]):
            failures.append(f"{prefix}: content-type {item['content_type']}")
        if THRESHOLDS["headers"]["cache_control_contains"] not in (item["cache_control"] or ""):
            failures.append(f"{prefix}: cache-control {item['cache_control']}")
        if item["x_accel_buffering"] != THRESHOLDS["headers"]["x_accel_buffering"]:
            failures.append(f"{prefix}: x-accel-buffering {item['x_accel_buffering']}")
        if not item["initial_frame"]:
            failures.append(f"{prefix}: no initial frame")
    return failures


def build_report(
    args: argparse.Namespace,
    smoke: List[Dict[str, Any]],
    cells: List[Dict[str, Any]],
    aborted: List[str],
) -> Dict[str, Any]:
    summaries = []
    failures: List[str] = []
    for cell in cells:
        summary = summarise_cell(cell, args)
        summary["failures"] = evaluate_cell(cell["readers"], summary)
        summary["verdict"] = "PASS" if not summary["failures"] and cell["status"] == "measured" else "FAIL"
        if cell["status"] != "measured":
            summary["failures"].insert(0, f"cell {cell['status']}: {cell['error']}")
            summary["verdict"] = "FAIL"
        summary["route"] = cell["route"]
        summary["readers"] = cell["readers"]
        summaries.append(summary)
        failures.extend(f"{cell['route']}/{cell['readers']}: {item}" for item in summary["failures"])
    header_failures = smoke_failures(smoke)
    failures.extend(header_failures)
    failures.extend(aborted)
    recorded_sha = args.tested_sha or "unknown"
    evidence_bound = bool(SHA_RE.fullmatch(recorded_sha))
    if not evidence_bound:
        failures.append("EVIDENCE-UNBOUND: no tested SHA")
    if not evidence_bound:
        overall = "UNBOUND"
    elif failures:
        overall = "FAIL"
    else:
        overall = "PASS"
    return {
        "contract": CONTRACT,
        "tested_sha": recorded_sha,
        "platform": {
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "mem_total_mib": read_mem_total_mib(),
            "fastapi": _dependency_version("fastapi"),
            "uvicorn": _dependency_version("uvicorn"),
            "starlette": _dependency_version("starlette"),
        },
        "workload": {
            "routes": list(args.routes),
            "readers_levels": list(args.readers),
            "warmup_rounds": args.warmup_rounds,
            "measured_rounds": args.rounds,
            "messages_per_round": args.messages,
            "publish_interval_ms": args.interval_ms,
            "read_timeout_s": args.read_timeout,
            "start_timeout_s": args.start_timeout,
            "drain_timeout_s": args.drain_timeout,
            "post_timeout_s": args.post_timeout,
            "server_start_timeout_s": args.server_start_timeout,
            "level_deadline_s": args.level_deadline,
            "overall_deadline_s": args.overall_deadline,
        },
        "thresholds": THRESHOLDS,
        "smoke": smoke,
        "results": summaries,
        "decision": {
            "overall": overall,
            "failures": failures,
        },
    }


def parse_readers(value: str) -> List[int]:
    try:
        levels = [int(part) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("reader levels must be comma-separated integers") from exc
    if not levels or any(level < 1 for level in levels):
        raise argparse.ArgumentTypeError("reader levels must be positive")
    return levels


def parse_routes(value: str) -> List[str]:
    routes = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [route for route in routes if route not in ROUTES]
    if not routes or unknown:
        raise argparse.ArgumentTypeError(f"routes must be a subset of {sorted(ROUTES)}")
    return routes


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bounded SSE load baseline. Owns a disposable loopback Uvicorn "
            "child serving the real API; accepts no target URL."
        )
    )
    parser.add_argument("--output", required=True, help="JSON report path (keep raw output outside git)")
    parser.add_argument("--tested-sha", default="", help="40-hex commit the measurement is bound to")
    parser.add_argument("--routes", type=parse_routes, default=parse_routes("road1,cam1"))
    parser.add_argument("--readers", type=parse_readers, default=parse_readers("1,10,50"))
    parser.add_argument("--warmup-rounds", type=int, default=2)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--messages", type=int, default=20)
    parser.add_argument("--interval-ms", type=int, default=50)
    parser.add_argument("--read-timeout", type=float, default=1.0)
    parser.add_argument("--start-timeout", type=float, default=10.0)
    parser.add_argument("--drain-timeout", type=float, default=10.0)
    parser.add_argument("--post-timeout", type=float, default=5.0)
    parser.add_argument("--server-start-timeout", type=float, default=20.0)
    parser.add_argument("--level-deadline", type=float, default=120.0)
    parser.add_argument("--overall-deadline", type=float, default=600.0)
    args = parser.parse_args(argv)
    if args.tested_sha and not SHA_RE.fullmatch(args.tested_sha):
        parser.error("--tested-sha must be a 40-hex commit")
    if args.warmup_rounds < 0 or args.rounds < 1 or args.messages < 1 or args.interval_ms <= 0:
        parser.error("workload counts must be positive")
    return args


def print_summary(report: Dict[str, Any]) -> None:
    print(f"SSE load baseline {report['contract']} tested_sha={report['tested_sha']}")
    print(
        "route  readers  p50ms  p95ms   maxms  miss  dup  complete  cpu/s  rss_grow_mib  fd_retain  verdict"
    )
    for row in report["results"]:
        latency = row["latency_ms"]
        cpu = row["server_cpu"]
        memory = row["memory"]
        fds = row["fds"]
        delivery = row["delivery"]
        print(
            f"{row['route']:<6} {row['readers']:>7} "
            f"{str(latency['p50']):>6} {str(latency['p95']):>6} {str(latency['max']):>7} "
            f"{delivery['missing_total']:>5} {delivery['duplicates_total']:>4} "
            f"{delivery['complete_reader_rounds']}/{delivery['reader_rounds']:<8} "
            f"{str(cpu['cpu_per_wall'] if cpu else None):>5} "
            f"{str(memory['retained_growth_mib']):>12} {str(fds['retained_growth']):>9}  "
            f"{row['verdict']}"
        )
    decision = report["decision"]
    print(f"decision: {decision['overall']}")
    for failure in decision["failures"]:
        print(f"  FAIL {failure}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    _reject_target_url(raw)
    args = parse_args(raw)
    started = time.monotonic()
    overall_deadline = started + args.overall_deadline
    base_dir = Path(tempfile.mkdtemp(prefix="sea-speed-690-"))
    server = ChildServer(base_dir, args.server_start_timeout)
    smoke: List[Dict[str, Any]] = []
    cells: List[Dict[str, Any]] = []
    aborted: List[str] = []
    try:
        server.start()
        assert server.port is not None
        for route_name in args.routes:
            for alias in ROUTES[route_name]["aliases"]:
                item = open_alias_once(server.host, server.port, alias, args.start_timeout)
                item["route"] = route_name
                smoke.append(item)
        for route_name in args.routes:
            for readers_count in args.readers:
                if time.monotonic() > overall_deadline:
                    aborted.append(f"{route_name}/{readers_count}: overall deadline exceeded")
                    continue
                if not server.alive():
                    aborted.append(f"{route_name}/{readers_count}: child exited mid-run")
                    continue
                level_deadline = time.monotonic() + args.level_deadline
                cells.append(run_cell(route_name, readers_count, server, args, level_deadline))
        report = build_report(args, smoke, cells, aborted)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print_summary(report)
        print(f"report: {output}")
        return 0 if report["decision"]["overall"] == "PASS" else 1
    except BaselineError as exc:
        print(f"NOT EXECUTED — {exc}", file=sys.stderr)
        if server.port is not None:
            print(server._log_tail(), file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("interrupted; cleaning up the child", file=sys.stderr)
        return 130
    finally:
        server.stop()
        shutil.rmtree(base_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
