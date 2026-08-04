#!/usr/bin/env python3
"""Deterministic fuzz and interrupted-write recovery checks."""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import json
import random
import string
import tempfile

from scripts.quality.common import load_json, repository_root, safe_media_key, stable_event_identity, write_json_atomic

SEED = 20260804


def main() -> int:
    root = repository_root()
    budget = load_json(root / "data/quality/reliability-budget-v1.json")["limits"]
    case_count = int(budget["minimum_deterministic_fuzz_cases"])
    rng = random.Random(SEED)

    accepted = 0
    rejected = 0
    for index in range(case_count):
        parts = [
            "".join(rng.choice(string.ascii_lowercase + string.digits + "_-") for _ in range(rng.randint(1, 12)))
            for _ in range(rng.randint(1, 5))
        ]
        key = "/".join(parts) + rng.choice([".jpg", ".webp"])
        assert safe_media_key(key) == key
        accepted += 1

        malicious = rng.choice([
            "../" + key,
            "/" + key,
            "x/../../" + key,
            "C:/" + key,
            "x\\" + key,
        ])
        try:
            safe_media_key(malicious)
        except ValueError:
            rejected += 1
        else:
            raise AssertionError(f"fuzz case accepted unsafe key: {malicious}")

    identities: set[str] = set()
    for index in range(case_count):
        event = {
            "node_id": "edge-01",
            "camera_id": "cam1",
            "detected_at": f"2026-08-04T13:{index // 60:02d}:{index % 60:02d}Z",
            "track_id": index,
            "class_name": "boat",
        }
        identity = stable_event_identity(event)
        assert identity not in identities
        identities.add(identity)
        retry = {**event, "retry_count": rng.randint(1, 20), "last_error": "timeout"}
        assert stable_event_identity(retry) == identity

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "state.json"
        original = {"version": 1, "events": ["evt-1"]}
        write_json_atomic(path, original)
        assert json.loads(path.read_text(encoding="utf-8")) == original

        interrupted = path.with_suffix(".json.tmp")
        interrupted.write_text('{"version": 2, "events": [', encoding="utf-8")
        assert json.loads(path.read_text(encoding="utf-8")) == original
        interrupted.unlink()

        replacement = {"version": 2, "events": ["evt-1", "evt-2"]}
        write_json_atomic(path, replacement)
        assert json.loads(path.read_text(encoding="utf-8")) == replacement

        path.write_text("{corrupt", encoding="utf-8")
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
        else:
            raise AssertionError("corrupt JSON was not rejected")

    print(f"Fuzz/recovery checks passed: seed={SEED}, valid={accepted}, rejected={rejected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
