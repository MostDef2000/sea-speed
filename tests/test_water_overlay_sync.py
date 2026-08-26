#!/usr/bin/env python3
"""Deterministic tests for Water live overlay sync alignment (064)."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SOURCE = ROOT / "frontend" / "sea-speed" / "index.html"


def clamp_lag(median_lag_ms: float) -> float:
    """Mirror of updateLag clamp in frontend/sea-speed/index.html (Water)."""
    return max(0.0, min(1200.0, median_lag_ms))


def closest_earlier_envelope(buffer, comp_ms):
    """Mirror of closestEarlierEnvelope: last envelope at or before comp."""
    lo = None
    for env in sorted(buffer, key=lambda e: e["capture_time_unix_ms"]):
        t = env["capture_time_unix_ms"]
        if t <= comp_ms:
            lo = env
        else:
            break
    return lo


def render_fallback_on_bracket_failure(buffer, media_ms, lag_ms):
    """Mirror of renderForVideoFrame fallback branch on Water."""
    comp = media_ms - lag_ms
    near = closest_earlier_envelope(buffer, comp)
    if near is not None and near["capture_time_unix_ms"] >= comp - 2000:
        return near["id"]
    return buffer[-1]["id"]


class WaterOverlaySyncTest(unittest.TestCase):
    def test_lag_clamp_allows_up_to_1200ms(self):
        self.assertEqual(clamp_lag(900.0), 900.0)
        self.assertEqual(clamp_lag(1200.0), 1200.0)
        self.assertEqual(clamp_lag(1500.0), 1200.0)
        self.assertEqual(clamp_lag(-50.0), 0.0)

    def test_fallback_prefers_closest_earlier_over_stale_latest(self):
        buffer = [
            {"id": "old", "capture_time_unix_ms": 1000},
            {"id": "near", "capture_time_unix_ms": 5000},
            {"id": "latest", "capture_time_unix_ms": 6800},
        ]
        chosen = render_fallback_on_bracket_failure(buffer, media_ms=6000, lag_ms=0)
        self.assertEqual(chosen, "near")

    def test_fallback_beyond_two_seconds_uses_latest(self):
        buffer = [
            {"id": "old", "capture_time_unix_ms": 1000},
            {"id": "latest", "capture_time_unix_ms": 6800},
        ]
        chosen = render_fallback_on_bracket_failure(buffer, media_ms=6000, lag_ms=0)
        self.assertEqual(chosen, "latest")

    def test_frontend_source_contains_sync_markers(self):
        source = FRONTEND_SOURCE.read_text(encoding="utf-8")
        for marker in (
            "SeaSpeedLiveSync.clampLag(",
            "function closestEarlierEnvelope(compMs)",
            "mediaMs-2000",
        ):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
