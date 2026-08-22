#!/usr/bin/env python3
"""Continuous bounded freshness supervision for Camera 1 H264 HLS.

The production entry point accepts no arguments and no environment overrides. It
observes only the fixed local HLS playlist and fixed credential-free Ubuntu RTSP
relay, and may restart only the fixed Camera 1 H264 producer service.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

HLS_MEDIA_SEQUENCE_RE = re.compile(r"(?m)^#EXT-X-MEDIA-SEQUENCE:(\d+)\s*$")
CAMERA1_PRIVATE_RELAY = "rtsp://10.123.239.102:8554/cam1"
CAMERA1_LOCAL_HLS = "http://127.0.0.1:18889/cam1/index.m3u8"
CAMERA1_H264_SERVICE = "sea-speed-camera1-h264.service"
STATE_ROOT = Path("/var/lib/sea-speed-camera1-freshness")
STATE_FILE = STATE_ROOT / "state.json"
LOCK_FILE = STATE_ROOT / "watchdog.lock"
SAMPLE_SECONDS = 3
COOLDOWN_SECONDS = 300


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


def _hls_sequence(runner: Callable[..., subprocess.CompletedProcess[str]]) -> int:
    argv = [
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "--max-time",
        "8",
        CAMERA1_LOCAL_HLS,
    ]
    completed = _run_fixed(runner, argv, timeout=10)
    if completed.returncode != 0:
        raise WatchdogError("Camera 1 local HLS playlist is unavailable")
    match = HLS_MEDIA_SEQUENCE_RE.search(completed.stdout or "")
    if match is None:
        raise WatchdogError("Camera 1 local HLS playlist has no media sequence")
    return int(match.group(1))


def _hls_advancing(
    runner: Callable[..., subprocess.CompletedProcess[str]],
    sleeper: Callable[[float], None],
) -> tuple[bool, int, int]:
    first = _hls_sequence(runner)
    sleeper(SAMPLE_SECONDS)
    second = _hls_sequence(runner)
    return second > first, first, second


def _probe_private_relay(runner: Callable[..., subprocess.CompletedProcess[str]]) -> None:
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
        CAMERA1_PRIVATE_RELAY,
        "-frames:v",
        "1",
        "-f",
        "null",
        "-",
    ]
    completed = _run_fixed(runner, argv, timeout=15)
    if completed.returncode != 0:
        raise WatchdogError("Camera 1 private Ubuntu relay did not produce a decodable frame")


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
            raise WatchdogError("Camera 1 freshness watchdog is already running") from exc

        advancing, first, second = _hls_advancing(runner, sleeper)
        lines = [
            f"CAMERA1_H264_SERVICE={CAMERA1_H264_SERVICE}",
            f"CAMERA1_HLS_SEQUENCE_FIRST={first}",
            f"CAMERA1_HLS_SEQUENCE_SECOND={second}",
        ]
        if advancing:
            lines.extend(
                (
                    "CAMERA1_H264_FRESHNESS=PASS",
                    "CAMERA1_H264_RECOVERY=NOOP",
                    "CAMERA1_PRIVATE_RELAY=NOT_CHECKED",
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
                    "CAMERA1_PRIVATE_RELAY=NOT_CHECKED",
                )
            )
            return lines

        _probe_private_relay(runner)
        _write_last_attempt(state_file, now)
        restarted = _run_fixed(
            runner,
            ["systemctl", "restart", CAMERA1_H264_SERVICE],
            timeout=20,
        )
        if restarted.returncode != 0:
            raise WatchdogError("fixed Camera 1 H264 service restart failed")
        active = _run_fixed(
            runner,
            ["systemctl", "is-active", "--quiet", CAMERA1_H264_SERVICE],
            timeout=10,
        )
        if active.returncode != 0:
            raise WatchdogError("fixed Camera 1 H264 service is not active after restart")

        sleeper(SAMPLE_SECONDS)
        post_advancing, post_first, post_second = _hls_advancing(runner, sleeper)
        if not post_advancing:
            raise WatchdogError("Camera 1 local HLS is still not advancing after fixed H264 restart")
        lines.extend(
            (
                "CAMERA1_H264_FRESHNESS=PASS",
                "CAMERA1_H264_RECOVERY=RESTARTED",
                "CAMERA1_PRIVATE_RELAY=PASS",
                f"CAMERA1_POST_RESTART_SEQUENCE_FIRST={post_first}",
                f"CAMERA1_POST_RESTART_SEQUENCE_SECOND={post_second}",
            )
        )
        return lines


def main() -> int:
    if os.geteuid() != 0:
        print("ERROR Camera 1 freshness watchdog must run as root", file=sys.stderr)
        return 1
    if len(sys.argv) != 1:
        print("ERROR Camera 1 freshness watchdog accepts no arguments", file=sys.stderr)
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
