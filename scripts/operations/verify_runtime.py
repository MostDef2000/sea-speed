#!/usr/bin/env python3
"""Collect non-secret Sea Speed runtime acceptance evidence."""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "sea-speed-runtime-verifier"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def age_seconds(value: str) -> float:
    observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.now(timezone.utc).timestamp() - observed.timestamp()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://mostdef.ru/sea-speed/api")
    parser.add_argument("--expected-api-commit", default="")
    parser.add_argument("--expected-worker-commit", default="")
    parser.add_argument("--sample-delay", type=float, default=3.0)
    parser.add_argument("--max-age", type=float, default=30.0)
    parser.add_argument("--require-event", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    health = get_json(base + "/health")
    first = get_json(base + "/cam1/state")
    time.sleep(max(0.0, args.sample_delay))
    second = get_json(base + "/cam1/state")
    checks: list[dict] = []

    def check(name: str, passed: bool, observed=None) -> None:
        checks.append({"name": name, "status": "passed" if passed else "failed", "observed": observed})

    check("api_health", health.get("ok") is True, health.get("ok"))
    check("api_schema", health.get("api_schema") == "sea_speed_api_v1", health.get("api_schema"))
    if args.expected_api_commit:
        check("api_commit", health.get("source_commit") == args.expected_api_commit.lower(), health.get("source_commit"))
    check("worker_online", second.get("worker_online") is True, second.get("worker_online"))
    check("worker_state_schema", second.get("state_schema") == "sea_speed_worker_state_v1", second.get("state_schema"))
    if args.expected_worker_commit:
        check("worker_commit", second.get("worker_source_commit") == args.expected_worker_commit.lower(), second.get("worker_source_commit"))
    updated_at = second.get("updated_at")
    check("state_freshness", isinstance(updated_at, str) and age_seconds(updated_at) <= args.max_age, updated_at)
    first_frame = first.get("frame_no")
    second_frame = second.get("frame_no")
    check("frame_progress", isinstance(first_frame, int) and isinstance(second_frame, int) and second_frame > first_frame, [first_frame, second_frame])
    check("overlay", bool(second.get("last_overlay_url")), second.get("last_overlay_url"))

    if args.require_event:
        event_data = get_json(base + "/cam1/events?limit=1")
        events = event_data.get("events") or []
        event = events[0] if events else None
        check("event_available", bool(event), event.get("event_id") if event else None)
        if event:
            check("event_schema", event.get("event_schema") == "sea_speed_vehicle_event_v1", event.get("event_schema"))
            check("event_worker_commit", event.get("worker_source_commit") == second.get("worker_source_commit"), event.get("worker_source_commit"))

    passed = all(item["status"] == "passed" for item in checks)
    report = {
        "schema": "sea_speed_runtime_acceptance_v1",
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "baseUrl": args.base_url,
        "checks": checks,
        "verdict": "accepted" if passed else "regressed",
    }
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
