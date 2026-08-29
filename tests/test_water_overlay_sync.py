#!/usr/bin/env python3
"""Deterministic tests for Water live overlay sync alignment (064/071/073)."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SOURCE = ROOT / "frontend/sea-speed" / "index.html"
LIVE_SYNC_SOURCE = ROOT / "frontend/sea-speed" / "live-sync.js"


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


def water_target_capture_ms(buffer, playback_latency_ms):
    """Map HLS distance-to-live-edge onto the Worker capture timeline."""
    if playback_latency_ms is None or playback_latency_ms < 0 or playback_latency_ms > 30000:
        return None
    captures = [float(env["capture_time_unix_ms"]) for env in buffer if env.get("capture_time_unix_ms") is not None]
    if not captures:
        return None
    return max(captures) - float(playback_latency_ms)


def bracket_for_target(buffer, target_ms, max_gap_ms=500):
    if target_ms is None:
        return None
    lo = None
    hi = None
    for env in sorted(buffer, key=lambda e: e["capture_time_unix_ms"]):
        t = env["capture_time_unix_ms"]
        if t <= target_ms:
            lo = env
        else:
            hi = env
            break
    if lo is None or hi is None or lo.get("generation") != hi.get("generation"):
        return None
    gap = hi["capture_time_unix_ms"] - lo["capture_time_unix_ms"]
    if gap <= 0 or gap > max_gap_ms:
        return None
    fraction = (target_ms - lo["capture_time_unix_ms"]) / gap
    if fraction < 0 or fraction > 1:
        return None
    return lo["id"], hi["id"], fraction


def render_fallback_on_bracket_failure(buffer, target_ms):
    """Mirror the bounded no-bracket continuity rule when target is known."""
    if target_ms is None:
        return None
    near = closest_earlier_envelope(buffer, target_ms)
    if (
        near is not None
        and near["capture_time_unix_ms"] >= target_ms - 2000
        and near["capture_time_unix_ms"] <= target_ms
    ):
        return near["id"]
    return None


class WaterOverlaySyncTest(unittest.TestCase):
    def test_live_edge_latency_selects_worker_timeline_bracket_without_absolute_clock(self):
        buffer = [
            {"id": "a", "generation": 9, "capture_time_unix_ms": 10000},
            {"id": "b", "generation": 9, "capture_time_unix_ms": 10200},
            {"id": "c", "generation": 9, "capture_time_unix_ms": 10400},
            {"id": "latest", "generation": 9, "capture_time_unix_ms": 10600},
        ]
        target = water_target_capture_ms(buffer, playback_latency_ms=500)
        self.assertEqual(target, 10100)
        bracket = bracket_for_target(buffer, target)
        self.assertIsNotNone(bracket)
        self.assertEqual(bracket[:2], ("a", "b"))
        self.assertAlmostEqual(bracket[2], 0.5)

    def test_relative_mapping_is_invariant_to_worker_browser_clock_offset(self):
        base = [
            {"id": "a", "generation": 1, "capture_time_unix_ms": 10000},
            {"id": "b", "generation": 1, "capture_time_unix_ms": 10200},
            {"id": "latest", "generation": 1, "capture_time_unix_ms": 10600},
        ]
        shifted = [{**env, "capture_time_unix_ms": env["capture_time_unix_ms"] + 86400000} for env in base]
        target_a = water_target_capture_ms(base, 500)
        target_b = water_target_capture_ms(shifted, 500)
        bracket_a = bracket_for_target(base, target_a)
        bracket_b = bracket_for_target(shifted, target_b)
        self.assertEqual(bracket_a[:2], bracket_b[:2])
        self.assertAlmostEqual(bracket_a[2], bracket_b[2])

    def test_missing_or_invalid_latency_fails_closed(self):
        buffer = [{"id": "latest", "generation": 1, "capture_time_unix_ms": 10000}]
        self.assertIsNone(water_target_capture_ms(buffer, None))
        self.assertIsNone(water_target_capture_ms(buffer, -1))
        self.assertIsNone(water_target_capture_ms(buffer, 30001))

    def test_fallback_prefers_closest_earlier_over_stale_latest(self):
        buffer = [
            {"id": "old", "capture_time_unix_ms": 1000},
            {"id": "near", "capture_time_unix_ms": 5000},
            {"id": "latest", "capture_time_unix_ms": 6800},
        ]
        chosen = render_fallback_on_bracket_failure(buffer, target_ms=6000)
        self.assertEqual(chosen, "near")

    def test_fallback_beyond_two_seconds_clears(self):
        buffer = [
            {"id": "old", "capture_time_unix_ms": 1000},
            {"id": "future", "capture_time_unix_ms": 6800},
        ]
        chosen = render_fallback_on_bracket_failure(buffer, target_ms=6000)
        self.assertIsNone(chosen)

    def test_future_only_metadata_clears(self):
        buffer = [
            {"id": "future-a", "capture_time_unix_ms": 6100},
            {"id": "future-b", "capture_time_unix_ms": 6800},
        ]
        chosen = render_fallback_on_bracket_failure(buffer, target_ms=6000)
        self.assertIsNone(chosen)

    def test_frontend_source_contains_relative_sync_markers(self):
        source = FRONTEND_SOURCE.read_text(encoding="utf-8")
        live_sync = LIVE_SYNC_SOURCE.read_text(encoding="utf-8")
        for marker in (
            "function ssWaterPlaybackLatencyMs()",
            "function ssWaterTargetCaptureMs(opts)",
            "return Math.max(...captures) - latencyMs;",
            "latest.camera_id === \"cam1\"",
            "ssInstallWaterMediaTimeProbe();",
        ):
            self.assertIn(marker, live_sync)
        self.assertIn("const LIVE_NEAR_MAX_AGE_MS=2000;", source)
        self.assertIn("const br=bracketForMedia(raw);", source)
        self.assertNotIn("drawLive(liveBuffer[liveBuffer.length-1])", source)
        self.assertNotIn(
            "Math.abs(raw-(liveBuffer.length?Math.max(...liveBuffer.map(e=>getCaptureMs(e)||0)):0))>6000",
            source,
        )


if __name__ == "__main__":
    unittest.main()
