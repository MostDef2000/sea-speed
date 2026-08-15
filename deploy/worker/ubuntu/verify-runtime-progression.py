#!/usr/bin/env python3
"""Verify exact worker frame and state progression during activation."""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path


SHA40_RE = re.compile(r"^[0-9a-f]{40}$")


def read_heartbeat(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heartbeat", required=True, type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--timeout-sec", type=float, default=45.0)
    parser.add_argument("--poll-sec", type=float, default=1.0)
    args = parser.parse_args()

    if not SHA40_RE.fullmatch(args.expected_commit):
        raise SystemExit("expected commit must be a lowercase 40-character SHA")
    if args.timeout_sec < 5.0:
        raise SystemExit("timeout must be at least 5 seconds")
    if not 0.1 <= args.poll_sec <= 5.0:
        raise SystemExit("poll interval must be between 0.1 and 5 seconds")

    deadline = time.monotonic() + args.timeout_sec
    baseline: tuple[int, int] | None = None

    while time.monotonic() < deadline:
        heartbeat = read_heartbeat(args.heartbeat)
        source_ok = heartbeat.get("source_commit") == args.expected_commit
        phase_ok = heartbeat.get("phase") == "running"
        frame_sequence = heartbeat.get("frame_progress_sequence")
        state_success = heartbeat.get("state_post_success_count")
        state_ok = heartbeat.get("last_state_post_ok") is True

        counters_ok = (
            isinstance(frame_sequence, int)
            and frame_sequence > 0
            and isinstance(state_success, int)
            and state_success > 0
        )

        if source_ok and phase_ok and counters_ok and state_ok:
            current = (int(frame_sequence), int(state_success))
            if baseline is None:
                baseline = current
                print(
                    "RUNTIME_GATE_BASELINE "
                    f"frame_progress_sequence={current[0]} "
                    f"state_post_success_count={current[1]}"
                )
            elif current[0] > baseline[0] and current[1] > baseline[1]:
                print(
                    "RUNTIME_GATE_PASS "
                    f"source_commit={args.expected_commit} "
                    f"frame_progress_sequence={baseline[0]}->{current[0]} "
                    f"state_post_success_count={baseline[1]}->{current[1]}"
                )
                return 0

        time.sleep(args.poll_sec)

    if baseline is None:
        print(
            "RUNTIME_GATE_FAIL "
            f"source_commit={args.expected_commit} reason=no_exact_running_baseline"
        )
    else:
        print(
            "RUNTIME_GATE_FAIL "
            f"source_commit={args.expected_commit} "
            f"reason=no_progress_after_baseline "
            f"frame_progress_sequence={baseline[0]} "
            f"state_post_success_count={baseline[1]}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
