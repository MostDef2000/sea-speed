#!/usr/bin/env python3
"""Deterministic tests for Water live overlay sync alignment (064/071)."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SOURCE = ROOT / "frontend/sea-speed" / "index.html"


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


def bracket_for_media(buffer, media_ms, lag_ms=0, max_gap_ms=500):
    """Mirror the same-generation bracket contract without newest-age gating."""
    comp = media_ms - lag_ms
    lo = None
    hi = None
    for env in sorted(buffer, key=lambda e: e["capture_time_unix_ms"]):
        t = env["capture_time_unix_ms"]
        if t <= comp:
            lo = env
        else:
            hi = env
            break
    if lo is None or hi is None or lo.get("generation") != hi.get("generation"):
        return None
    gap = hi["capture_time_unix_ms"] - lo["capture_time_unix_ms"]
    if gap <= 0 or gap > max_gap_ms:
        return None
    fraction = (comp - lo["capture_time_unix_ms"]) / gap
    if fraction < 0 or fraction > 1:
        return None
    return lo["id"], hi["id"], fraction


def render_fallback_on_bracket_failure(buffer, media_ms, lag_ms):
    """Mirror of SDD 071 fail-closed Water no-bracket branch."""
    comp = media_ms - lag_ms
    near = closest_earlier_envelope(buffer, comp)
    if (
        near is not None
        and near["capture_time_unix_ms"] >= comp - 2000
        and near["capture_time_unix_ms"] <= comp
    ):
        return near["id"]
    return None


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

    def test_matching_bracket_survives_newest_envelope_more_than_six_seconds_ahead(self):
        buffer = [
            {"id": "lo", "generation": 9, "capture_time_unix_ms": 10000},
            {"id": "hi", "generation": 9, "capture_time_unix_ms": 10200},
            {"id": "latest", "generation": 9, "capture_time_unix_ms": 18000},
        ]
        bracket = bracket_for_media(buffer, media_ms=10100)
        self.assertIsNotNone(bracket)
        self.assertEqual(bracket[:2], ("lo", "hi"))
        self.assertAlmostEqual(bracket[2], 0.5)

    def test_fallback_beyond_two_seconds_clears(self):
        buffer = [
            {"id": "old", "capture_time_unix_ms": 1000},
            {"id": "future", "capture_time_unix_ms": 6800},
        ]
        chosen = render_fallback_on_bracket_failure(buffer, media_ms=6000, lag_ms=0)
        self.assertIsNone(chosen)

    def test_future_only_metadata_clears(self):
        buffer = [
            {"id": "future-a", "capture_time_unix_ms": 6100},
            {"id": "future-b", "capture_time_unix_ms": 6800},
        ]
        chosen = render_fallback_on_bracket_failure(buffer, media_ms=6000, lag_ms=0)
        self.assertIsNone(chosen)

    def test_frontend_source_contains_sync_markers(self):
        source = FRONTEND_SOURCE.read_text(encoding="utf-8")
        for marker in (
            "SeaSpeedLiveSync.clampLag(",
            "function closestEarlierEnvelope(compMs)",
            "const LIVE_NEAR_MAX_AGE_MS=2000;",
            "nearCapture>=mediaMs-LIVE_NEAR_MAX_AGE_MS&&nearCapture<=mediaMs",
            "if(raw==null){clearLive();return}",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("drawLive(liveBuffer[liveBuffer.length-1])", source)
        self.assertNotIn(
            "Math.abs(raw-(liveBuffer.length?Math.max(...liveBuffer.map(e=>getCaptureMs(e)||0)):0))>6000",
            source,
        )


if __name__ == "__main__":
    unittest.main()
