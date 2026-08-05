#!/usr/bin/env python3
"""Run the worker while emitting a non-secret local heartbeat."""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

SHA40_RE = re.compile(r"^[0-9a-f]{40}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o644)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--heartbeat", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--heartbeat-interval-sec", type=float, default=5.0)
    parser.add_argument("worker_script", type=Path)
    args = parser.parse_args()

    if not SHA40_RE.fullmatch(args.source_commit):
        raise SystemExit("source commit must be a lowercase 40-character SHA")
    if args.heartbeat_interval_sec < 1.0:
        raise SystemExit("heartbeat interval must be at least 1 second")
    if not args.worker_script.is_file():
        raise SystemExit(f"worker script missing: {args.worker_script}")

    lock = threading.Lock()
    state: dict[str, Any] = {
        "schema_version": 1,
        "source_commit": args.source_commit,
        "observed_at": utc_now(),
        "phase": "starting",
        "frame_progress_sequence": 0,
        "last_frame_at": None,
        "last_output_at": None,
        "last_state_post_at": None,
        "last_state_post_ok": None,
        "state_post_success_count": 0,
        "state_post_failure_count": 0,
        "last_event_post_at": None,
        "event_post_success_count": 0,
        "exit_code": None,
    }

    process = subprocess.Popen(
        [sys.executable, str(args.worker_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    def snapshot() -> dict[str, Any]:
        with lock:
            state["observed_at"] = utc_now()
            return dict(state)

    def record_line(line: str) -> None:
        now = utc_now()
        with lock:
            state["last_output_at"] = now
            if line.startswith("Worker started"):
                state["phase"] = "running"
            elif line.startswith("FFmpeg stream ended"):
                state["phase"] = "stream_ended"
            elif line.startswith("POST state ok"):
                state["last_state_post_at"] = now
                state["last_state_post_ok"] = True
                state["state_post_success_count"] += 1
            elif line.startswith(("POST state failed", "POST state error", "POST state skipped")):
                state["last_state_post_at"] = now
                state["last_state_post_ok"] = False
                state["state_post_failure_count"] += 1
            elif line.startswith("POST event ok"):
                state["last_event_post_at"] = now
                state["event_post_success_count"] += 1

    def forward(pipe: IO[str] | None, target: IO[str]) -> None:
        if pipe is None:
            return
        for line in iter(pipe.readline, ""):
            target.write(line)
            target.flush()
            record_line(line.rstrip("\n"))
        pipe.close()

    stdout_thread = threading.Thread(
        target=forward,
        args=(process.stdout, sys.stdout),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=forward,
        args=(process.stderr, sys.stderr),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    def forward_signal(signum: int, _frame: object) -> None:
        with lock:
            state["phase"] = "stopping"
        if process.poll() is None:
            process.send_signal(signum)

    signal.signal(signal.SIGTERM, forward_signal)
    signal.signal(signal.SIGINT, forward_signal)

    last_overlay_mtime_ns: int | None = None
    next_heartbeat = 0.0

    while process.poll() is None:
        try:
            overlay_mtime_ns = args.overlay.stat().st_mtime_ns
        except FileNotFoundError:
            overlay_mtime_ns = None
        except OSError:
            overlay_mtime_ns = None

        if overlay_mtime_ns is not None and overlay_mtime_ns != last_overlay_mtime_ns:
            last_overlay_mtime_ns = overlay_mtime_ns
            with lock:
                state["frame_progress_sequence"] += 1
                state["last_frame_at"] = datetime.fromtimestamp(
                    overlay_mtime_ns / 1_000_000_000,
                    timezone.utc,
                ).isoformat()

        now_monotonic = time.monotonic()
        if now_monotonic >= next_heartbeat:
            atomic_write_json(args.heartbeat, snapshot())
            next_heartbeat = now_monotonic + args.heartbeat_interval_sec
        time.sleep(0.25)

    return_code = process.wait()
    stdout_thread.join(timeout=2.0)
    stderr_thread.join(timeout=2.0)
    with lock:
        state["phase"] = "exited"
        state["exit_code"] = return_code
    atomic_write_json(args.heartbeat, snapshot())

    if return_code < 0:
        return 128 + abs(return_code)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
