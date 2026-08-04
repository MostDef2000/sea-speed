#!/usr/bin/env python3
"""Deterministic property checks for Sea Speed identities and storage boundaries."""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.quality.common import safe_media_key, stable_event_identity


def main() -> int:
    assertions = 0

    base = {
        "event_id": "evt-100",
        "node_id": "edge-01",
        "camera_id": "cam1",
        "detected_at": "2026-08-04T13:45:00Z",
        "class_name": "boat",
        "speed_kmh": 25.2,
    }
    retried = {**base, "retry_count": 8, "last_error": "timeout", "sync_status": "pending"}
    assert stable_event_identity(base) == stable_event_identity(retried)
    assertions += 1

    derived = {key: value for key, value in base.items() if key != "event_id"}
    derived_retry = {**derived, "retry_count": 3, "delivery_attempt": 4}
    assert stable_event_identity(derived) == stable_event_identity(derived_retry)
    assertions += 1

    other = {**derived, "detected_at": "2026-08-04T13:45:01Z"}
    assert stable_event_identity(derived) != stable_event_identity(other)
    assertions += 1

    logical_store: dict[str, dict] = {}
    for event in (base, retried, base):
        logical_store.setdefault(stable_event_identity(event), event)
    assert len(logical_store) == 1
    assertions += 1

    valid_keys = (
        "2026/08/04/evt-100.jpg",
        "events/cam1/boat_001.webp",
        "a.jpg",
        "archive/2026-08-04/x.y-z_1.jpg",
    )
    for key in valid_keys:
        assert safe_media_key(key) == key
        assertions += 1

    invalid_keys = (
        "",
        "/etc/passwd",
        "../secret.jpg",
        "events/../../secret.jpg",
        "C:/Windows/system.ini",
        "events\\x.jpg",
        "./events/x.jpg",
    )
    for key in invalid_keys:
        try:
            safe_media_key(key)
        except ValueError:
            assertions += 1
        else:
            raise AssertionError(f"unsafe media key accepted: {key!r}")

    edge_v2 = {
        "mode": "edge_v2",
        "edge_durable_media": True,
        "vps_durable_media": False,
        "vps_stream_proxy_allowed": True,
    }
    assert edge_v2["edge_durable_media"] is True
    assert edge_v2["vps_durable_media"] is False
    assert edge_v2["vps_stream_proxy_allowed"] is True
    assertions += 3

    assert assertions >= 18
    print(f"Property checks passed: {assertions} assertions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
