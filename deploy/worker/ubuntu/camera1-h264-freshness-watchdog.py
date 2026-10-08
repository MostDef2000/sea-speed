#!/usr/bin/env python3
"""Continuous bounded freshness supervision for the Ubuntu Camera 1 H264 transcode.

The production entry point accepts no arguments and no environment overrides. It
observes only the fixed local MediaMTX path cam1-h264 via the MediaMTX v1.19.1
REST API (GET /v3/paths/get/{name}) and may restart only the fixed local Camera 1
H264 transcode producer service. Producer liveness is proven by requiring the
path to be ready and available and its inboundBytes to strictly grow between two
samples taken SAMPLE_SECONDS apart; readyTime is the path start time, not frame
age. The source probe targets the same fixed product path cam1-h264; the legacy
cam1 relay leg is not consulted.

Fail-safe liveness contract (issue #407): the loopback REST API is the ONLY
freshness input. A liveness input that is unavailable (connection refused,
timeout, unresolvable host) or uninterpretable (non-JSON / non-object body,
corrupt freshness fields) must NEVER drive a restart: it reports
CAMERA1_H264_FRESHNESS=UNKNOWN with CAMERA1_H264_RECOVERY=NOOP instead of
assuming stale. Only an affirmative answer from a LIVE API (valid path object:
ready/available false, or ready+available true without inboundBytes growth, or
an HTTP-level not-found from the live endpoint) classifies the path STALE and
may drive recovery.
"""
from __future__ import annotations

import fcntl
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

CAMERA1_H264_PATH = "cam1-h264"
CAMERA1_H264_SOURCE = "rtsp://10.123.239.102:8554/cam1-h264"
MEDIAMTX_API = "http://127.0.0.1:9997"
CAMERA1_H264_SERVICE = "sea-speed-camera1-h264.service"
STATE_ROOT = Path("/var/lib/sea-speed-camera1-h264-freshness")
STATE_FILE = STATE_ROOT / "state.json"
LOCK_FILE = STATE_ROOT / "watchdog.lock"
SAMPLE_SECONDS = 3
COOLDOWN_SECONDS = 300
PATH_READY = "READY"
PATH_STALE = "STALE"
LIVENESS_UNAVAILABLE = "UNAVAILABLE"
# curl exit codes that mean the request never completed at the transport
# layer: 6 resolve failure, 7 connection refused, 28 timeout, 35 TLS handshake,
# 56 recv failure. Any of these means the liveness input is unavailable.
CONNECTION_UNAVAILABLE_EXIT_CODES = frozenset({6, 7, 28, 35, 56})


class WatchdogError(RuntimeError):
    pass


def _run_fixed(
    runner: Callable[..., subprocess.CompletedProcess[str]],
    argv: list[str],
    *,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return runner(
        argv,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
    )


def _path_state(
    runner: Callable[..., subprocess.CompletedProcess[str]],
    sleeper: Callable[[float], None],
) -> str:
    """Classify the fixed path against a LIVE API: READY, STALE or UNAVAILABLE.

    UNAVAILABLE (input down/uninterpretable) is fail-safe: the caller must not
    restart. STALE requires an affirmative answer from the live API: a valid
    path object that is not ready/available, that does not grow inboundBytes
    between samples, or an HTTP-level error response from the live endpoint.
    """
    argv = [
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "--max-time",
        "8",
        f"{MEDIAMTX_API}/v3/paths/get/{CAMERA1_H264_PATH}",
    ]
    samples: list[int] = []
    for index in range(2):
        if index:
            sleeper(SAMPLE_SECONDS)
        completed = _run_fixed(runner, argv, timeout=10)
        if completed.returncode != 0:
            if completed.returncode in CONNECTION_UNAVAILABLE_EXIT_CODES:
                return LIVENESS_UNAVAILABLE
            # Any other non-zero code with --fail is an HTTP-level response
            # (e.g. 404 path not found): the API is live and answered.
            return PATH_STALE
        try:
            data = json.loads(completed.stdout or "")
        except ValueError:
            return LIVENESS_UNAVAILABLE
        if not isinstance(data, dict):
            return LIVENESS_UNAVAILABLE
        ready = data.get("ready")
        available = data.get("available")
        if (ready is not True and ready is not False) or (
            available is not True and available is not False
        ):
            # Corrupt freshness fields are not an affirmative staleness answer.
            return LIVENESS_UNAVAILABLE
        if ready is not True or available is not True:
            return PATH_STALE
        raw = data.get("inboundBytes")
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            return LIVENESS_UNAVAILABLE
        samples.append(raw)
    return PATH_READY if samples[1] > samples[0] else PATH_STALE


def _probe_source(runner: Callable[..., subprocess.CompletedProcess[str]]) -> None:
    argv = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-timeout",
        "10000000",
        "-i",
        CAMERA1_H264_SOURCE,
        "-frames:v",
        "1",
        "-f",
        "null",
        "-",
    ]
    completed = _run_fixed(runner, argv, timeout=15)
    if completed.returncode != 0:
        raise WatchdogError("Camera 1 source did not produce a decodable frame for Ubuntu transcode")


def _ensure_state_root(state_root: Path) -> None:
    state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = state_root.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise WatchdogError("watchdog state root must be a real directory")
    if metadata.st_uid != os.geteuid():
        raise WatchdogError("watchdog state root has unexpected owner")
    if metadata.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        os.chmod(state_root, 0o700)


def _read_last_attempt(state_file: Path) -> float | None:
    try:
        metadata = state_file.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise WatchdogError("watchdog state file must be a regular non-symlink file")
    if metadata.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise WatchdogError("watchdog state file must not be accessible to group/other")
    try:
        payload = json.loads(state_file.read_text(encoding="utf-8"))
        raw = payload["last_restart_attempt"]
        value = float(raw)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise WatchdogError("watchdog state file is invalid") from exc
    if value < 0:
        raise WatchdogError("watchdog restart timestamp is invalid")
    return value


def _write_last_attempt(state_file: Path, timestamp: float) -> None:
    temp = state_file.with_name(state_file.name + ".tmp")
    payload = {"last_restart_attempt": timestamp}
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(temp, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, state_file)
    finally:
        try:
            if temp.exists() or temp.is_symlink():
                temp.unlink()
        except OSError:
            pass


def _cooldown_remaining(last_attempt: float | None, now: float) -> int:
    if last_attempt is None:
        return 0
    elapsed = now - last_attempt
    if elapsed < 0:
        return COOLDOWN_SECONDS
    remaining = COOLDOWN_SECONDS - elapsed
    return max(0, int(remaining + 0.999))


def run_once(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
    state_root: Path = STATE_ROOT,
) -> list[str]:
    _ensure_state_root(state_root)
    lock_path = state_root / LOCK_FILE.name
    state_file = state_root / STATE_FILE.name
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    lock_fd = os.open(lock_path, flags, 0o600)
    with os.fdopen(lock_fd, "a+", encoding="utf-8") as lock_handle:
        os.chmod(lock_path, 0o600)
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WatchdogError("Camera 1 H264 freshness watchdog is already running") from exc

        state = _path_state(runner, sleeper)
        lines = [
            f"CAMERA1_H264_SERVICE={CAMERA1_H264_SERVICE}",
            f"CAMERA1_H264_PATH={CAMERA1_H264_PATH}",
        ]
        if state == PATH_READY:
            lines.extend(
                (
                    "CAMERA1_H264_FRESHNESS=PASS",
                    "CAMERA1_H264_RECOVERY=NOOP",
                    "CAMERA1_SOURCE=NOT_CHECKED",
                )
            )
            return lines

        if state == LIVENESS_UNAVAILABLE:
            # Fail-safe (issue #407): the liveness input is down or
            # uninterpretable. Never assume stale; never restart.
            lines.extend(
                (
                    "CAMERA1_H264_FRESHNESS=UNKNOWN",
                    "CAMERA1_H264_LIVENESS_INPUT=UNAVAILABLE",
                    "CAMERA1_H264_RECOVERY=NOOP",
                    "CAMERA1_SOURCE=NOT_CHECKED",
                )
            )
            return lines

        now = clock()
        remaining = _cooldown_remaining(_read_last_attempt(state_file), now)
        if remaining > 0:
            lines.extend(
                (
                    "CAMERA1_H264_FRESHNESS=STALE",
                    "CAMERA1_H264_RECOVERY=COOLDOWN",
                    f"CAMERA1_H264_COOLDOWN_REMAINING_SECONDS={remaining}",
                    "CAMERA1_SOURCE=NOT_CHECKED",
                )
            )
            return lines

        _probe_source(runner)
        _write_last_attempt(state_file, now)
        restarted = _run_fixed(
            runner,
            ["systemctl", "restart", CAMERA1_H264_SERVICE],
            timeout=20,
        )
        if restarted.returncode != 0:
            raise WatchdogError("fixed Camera 1 H264 transcode service restart failed")
        active = _run_fixed(
            runner,
            ["systemctl", "is-active", "--quiet", CAMERA1_H264_SERVICE],
            timeout=10,
        )
        if active.returncode != 0:
            raise WatchdogError("fixed Camera 1 H264 transcode service is not active after restart")

        sleeper(SAMPLE_SECONDS)
        state = _path_state(runner, sleeper)
        if state == LIVENESS_UNAVAILABLE:
            raise WatchdogError("Camera 1 H264 liveness input is unavailable after transcode restart")
        if state != PATH_READY:
            raise WatchdogError("Camera 1 H264 path is still not ready after transcode restart")
        lines.extend(
            (
                "CAMERA1_H264_FRESHNESS=PASS",
                "CAMERA1_H264_RECOVERY=RESTARTED",
                "CAMERA1_SOURCE=PASS",
            )
        )
        return lines


def main() -> int:
    if os.geteuid() != 0:
        print("ERROR Camera 1 H264 freshness watchdog must run as root", file=sys.stderr)
        return 1
    if len(sys.argv) != 1:
        print("ERROR Camera 1 H264 freshness watchdog accepts no arguments", file=sys.stderr)
        return 2
    try:
        for line in run_once():
            print(line)
    except WatchdogError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
