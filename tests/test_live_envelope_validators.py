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
import sys
import types
import unittest
import unittest.mock as mock
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
LIVE_FEEDS = ROOT / "api" / "app" / "live_feeds.py"


class _StubHTTPException(Exception):
    """Contract-equivalent stand-in for fastapi.HTTPException.

    CI behavioral suite is deliberately import-free of app dependencies
    (fastapi is not installed there). The validators only use the
    HTTPException(status_code=..., detail=...) contract, so a stub with the
    same constructor surface is contract-equivalent for these assertions.
    """

    def __init__(self, status_code: int | None = None, detail: str | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _load_live_feeds():
    """Load api/app/live_feeds.py direct-file, fastapi-stubbed when absent.

    The stub is injected under ``mock.patch.dict`` for the duration of the
    module exec only, so nothing leaks into sys.modules and other tests that
    legitimately stub fastapi themselves (e.g. test_roi_normalization loading
    api/app/main.py) are unaffected, matching the pre-#470 CI environment.
    """

    try:
        import fastapi  # noqa: F401
        stub = None
    except ModuleNotFoundError:
        stub = types.ModuleType("fastapi")
        stub.HTTPException = _StubHTTPException  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("live_feeds_contract_test", LIVE_FEEDS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    with _LoaderCtx(stub):
        spec.loader.exec_module(module)
    return module


class _LoaderCtx:
    def __init__(self, stub: types.ModuleType | None) -> None:
        self._stub = stub
        self._cm: Any = None

    def __enter__(self):
        if self._stub is not None:
            self._cm = mock.patch.dict(sys.modules, {"fastapi": self._stub})
            self._cm.__enter__()
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._cm is not None:
            self._cm.__exit__(*exc_info)


live_feeds = _load_live_feeds()

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
        with self.assertRaises(Exception) as ctx:
            live_feeds._validate_road_live_envelope(payload)
        self.assertEqual(getattr(ctx.exception, "status_code", None), 400)
        self.assertEqual(getattr(ctx.exception, "detail", None), "invalid json")

    def test_water_live_envelope_rejects_non_serializable_payload_as_400(self) -> None:
        # Control: the envelope without the offending field is accepted.
        live_feeds._validate_water_live_envelope(copy.deepcopy(WATER_ENVELOPE))
        payload = copy.deepcopy(WATER_ENVELOPE)
        payload["tags"] = {"water", "v1"}  # a set: json.dumps raises TypeError
        with self.assertRaises(Exception) as ctx:
            live_feeds._validate_water_live_envelope(payload)
        self.assertEqual(getattr(ctx.exception, "status_code", None), 400)
        self.assertEqual(getattr(ctx.exception, "detail", None), "invalid json")


if __name__ == "__main__":
    unittest.main()
