"""Live-envelope validator size guard parity (issue #470).

Issue #396 wave 6 extracted both live-envelope validators verbatim into
``api/app/live_feeds.py``, preserving a pre-existing asymmetry documented in
the wave-6 trio: ``_validate_road_live_envelope`` guards its json.dumps size
check with try/except and returns 400 "invalid json" for non-serializable
payloads, while ``_validate_water_live_envelope`` called json.dumps
unguarded, letting TypeError escape the staying ``post_water_live`` route as
a 500. Issue #470 aligns the water validator with the road pattern.

The staying route bodies delegate their whole validation to these two
validators (api/app/main.py ``post_road_live``/``post_water_live`` call
``_validate_*_live_envelope(payload)`` immediately after ``require_auth``),
so asserting the validators' behavior asserts the routes' failure path for a
payload that reaches the size check. The suite has no TestClient harness by
design (the app boots against /opt state); the module is loaded direct-file,
which is supported: live_feeds.py resolves only stdlib and
``fastapi.HTTPException`` (no intra-package imports, see its docstring).
"""

from __future__ import annotations

import copy
import importlib.util
import types
import unittest
from pathlib import Path
from typing import Any, Dict

try:
    from fastapi import HTTPException  # type: ignore[no-redef]
except ModuleNotFoundError:
    # CI behavioral suite is deliberately import-free of app dependencies
    # (fastapi is not installed there). The validators only use the
    # HTTPException(status_code=..., detail=...) contract, so a minimal stub
    # with the same constructor surface is contract-equivalent for these
    # tests; live_feeds.py resolves its own fastapi import from sys.modules.
    class HTTPException(Exception):
        def __init__(self, status_code: int | None = None, detail: str | None = None) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    sys_modules_fastapi = types.ModuleType("fastapi")
    sys_modules_fastapi.HTTPException = HTTPException  # type: ignore[attr-defined]
    import sys as _sys

    _sys.modules.setdefault("fastapi", sys_modules_fastapi)

ROOT = Path(__file__).resolve().parents[1]
LIVE_FEEDS = ROOT / "api" / "app" / "live_feeds.py"

spec = importlib.util.spec_from_file_location("live_feeds_contract_test", LIVE_FEEDS)
assert spec and spec.loader
live_feeds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live_feeds)

# Minimal envelopes that pass every structural check of their validator up to
# (and through) the size guard: only json.dumps of the extra field fails.
ROAD_ENVELOPE: Dict[str, Any] = {
    "schema": "sea_speed_road_live_v1",
    "camera_id": "road1",
    "analytics_profile": "road-v1",
    "domain": "road",
    "frame_no": 7,
    "generation": 0,
    "frame_width": 1920,
    "frame_height": 1080,
    "observed_mono": 123.5,
    "detections": [
        {"x1_norm": 0.1, "y1_norm": 0.1, "x2_norm": 0.2, "y2_norm": 0.2},
    ],
}

WATER_ENVELOPE: Dict[str, Any] = {
    "schema": "sea_speed_water_live_v1",
    "camera_id": "cam1",
    "analytics_profile": "water-v1",
    "domain": "water",
    "frame_no": 7,
    "generation": 0,
    "frame_width": 1920,
    "frame_height": 1080,
    "observed_mono": 123.5,
    "detections": [
        {"x1_norm": 0.1, "y1_norm": 0.1, "x2_norm": 0.2, "y2_norm": 0.2},
    ],
}


class LiveEnvelopeValidatorGuardTests(unittest.TestCase):
    def test_road_live_envelope_rejects_non_serializable_payload_as_400(self) -> None:
        # Control: the envelope without the offending field is accepted.
        live_feeds._validate_road_live_envelope(copy.deepcopy(ROAD_ENVELOPE))
        payload = copy.deepcopy(ROAD_ENVELOPE)
        payload["tags"] = {"road", "v1"}  # a set: json.dumps raises TypeError
        with self.assertRaises(HTTPException) as ctx:
            live_feeds._validate_road_live_envelope(payload)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "invalid json")

    def test_water_live_envelope_rejects_non_serializable_payload_as_400(self) -> None:
        # Control: the envelope without the offending field is accepted.
        live_feeds._validate_water_live_envelope(copy.deepcopy(WATER_ENVELOPE))
        payload = copy.deepcopy(WATER_ENVELOPE)
        payload["tags"] = {"water", "v1"}  # a set: json.dumps raises TypeError
        with self.assertRaises(HTTPException) as ctx:
            live_feeds._validate_water_live_envelope(payload)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "invalid json")


if __name__ == "__main__":
    unittest.main()
