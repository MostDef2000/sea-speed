#!/usr/bin/env python3
"""Deterministic tests for Water live overlay sync alignment (064/071/073).

#398 wave 1 conversion: the former in-file Python mirrors of
closestEarlierEnvelope / waterTargetCaptureMs / bracketForMedia /
render-fallback executed a parallel re-implementation instead of the
frontend bytes. The checks below execute the real live-sync.js and
overlay-canvas.js through the frontend_node harness
(tests/support/frontend_node.py). The retired mirrors also conflated the
near-fallback anchor timeline (mirror anchored the bounded near-window on
the Water target, maxCapture - latencyMs; the real overlay anchors it on
mediaMs = raw - lagCompensationMs) — recorded in
specs/398-wave1/spec.md (mirror-retirement note M-2).
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from tests.support import frontend_node
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import frontend_node

FRONTEND_SOURCE = ROOT / "frontend/sea-speed" / "index.html"
LIVE_SYNC_SOURCE = ROOT / "frontend/sea-speed" / "live-sync.js"
OVERLAY_MODULE = ROOT / "frontend/sea-speed" / "overlay-canvas.js"


class WaterOverlaySyncTest(unittest.TestCase):
    def test_live_edge_latency_selects_worker_timeline_bracket_without_absolute_clock(self):
        # Executed twin of the retired water_target_capture_ms/bracket_for_target
        # mirrors: the real ssWaterTargetCaptureMs maps HLS live-edge latency
        # onto the Worker capture timeline (maxCapture - latencyMs) and the real
        # ssBracketForMedia brackets it WITHOUT consulting absolute media time
        # (the probe media time is deliberately far outside the buffer).
        buffer = [
            {"id": "a", "camera_id": "cam1", "domain": "sea", "generation": 9, "capture_time_unix_ms": 10000},
            {"id": "b", "camera_id": "cam1", "domain": "sea", "generation": 9, "capture_time_unix_ms": 10200},
            {"id": "c", "camera_id": "cam1", "domain": "sea", "generation": 9, "capture_time_unix_ms": 10400},
            {"id": "latest", "camera_id": "cam1", "domain": "sea", "generation": 9, "capture_time_unix_ms": 10600},
        ]
        out = frontend_node.run_live_sync(
            "const buf = "
            + frontend_node.js_literal(buffer)
            + ";\n"
            + "window.waterHls = { latency: 0.5 };\n"
            + "const cap = function (e) { return e.capture_time_unix_ms; };\n"
            + "const opts = { liveBuffer: buf, getCaptureMs: cap, lagCompensationMs: 0, maxGapMs: 500 };\n"
            + "const target = S.waterTargetCaptureMs(opts);\n"
            + "if (target !== 10100) throw new Error('target ' + target);\n"
            + "const br = S.bracketForMedia(999999, opts);\n"
            + "if (!br || br.lo !== buf[0] || br.hi !== buf[1]) throw new Error('bracket ' + JSON.stringify(br && [buf.indexOf(br.lo), buf.indexOf(br.hi)]));\n"
            + "if (Math.abs(br.t - 0.5) > 1e-9) throw new Error('t ' + br.t);\n"
            + 'console.log("###OK");\n'
        )
        self.assertEqual(out, "###OK")

    def test_relative_mapping_is_invariant_to_worker_browser_clock_offset(self):
        base = [
            {"id": "a", "camera_id": "cam1", "domain": "sea", "generation": 1, "capture_time_unix_ms": 10000},
            {"id": "b", "camera_id": "cam1", "domain": "sea", "generation": 1, "capture_time_unix_ms": 10200},
            {"id": "latest", "camera_id": "cam1", "domain": "sea", "generation": 1, "capture_time_unix_ms": 10600},
        ]
        shifted = [{**env, "capture_time_unix_ms": env["capture_time_unix_ms"] + 86400000} for env in base]

        def bracket_of(buffer):
            out = frontend_node.run_live_sync(
                "const buf = "
                + frontend_node.js_literal(buffer)
                + ";\n"
                + "window.waterHls = { latency: 0.5 };\n"
                + "const cap = function (e) { return e.capture_time_unix_ms; };\n"
                + "const opts = { liveBuffer: buf, getCaptureMs: cap, lagCompensationMs: 0, maxGapMs: 500 };\n"
                + "const br = S.bracketForMedia(999999, opts);\n"
                + 'console.log("###" + JSON.stringify({ lo: buf.indexOf(br.lo), hi: buf.indexOf(br.hi), t: br.t }));\n'
            )
            import json

            return json.loads(out[3:])

        bracket_a = bracket_of(base)
        bracket_b = bracket_of(shifted)
        self.assertEqual(bracket_a["lo"], bracket_b["lo"])
        self.assertEqual(bracket_a["hi"], bracket_b["hi"])
        self.assertAlmostEqual(bracket_a["t"], bracket_b["t"])

    def test_missing_or_invalid_latency_fails_closed(self):
        # Executed twin of the retired water_target_capture_ms mirror: the real
        # selector returns null when the latency probe yields nothing usable —
        # absent latency (Number(undefined) = NaN), negative, and beyond the
        # 30s bound all fail closed. (Number(null) === 0 is a VALID probe
        # result in the real module, so absence is exercised as an absent key.)
        buffer = [{"id": "latest", "camera_id": "cam1", "domain": "sea", "generation": 1, "capture_time_unix_ms": 10000}]
        out = frontend_node.run_live_sync(
            "const buf = "
            + frontend_node.js_literal(buffer)
            + ";\n"
            + "const cap = function (e) { return e.capture_time_unix_ms; };\n"
            + "const opts = { liveBuffer: buf, getCaptureMs: cap, lagCompensationMs: 0, maxGapMs: 500 };\n"
            + "function targetWith(hls) { window.waterHls = hls; return S.waterTargetCaptureMs(opts); }\n"
            + "if (targetWith({}) !== null) throw new Error('absent latency must fail closed');\n"
            + "if (targetWith({ latency: -1 }) !== null) throw new Error('negative latency must fail closed');\n"
            + "if (targetWith({ latency: 30.01 }) !== null) throw new Error('over-30s latency must fail closed');\n"
            + 'console.log("###OK");\n'
        )
        self.assertEqual(out, "###OK")

    def test_fallback_prefers_closest_earlier_over_stale_latest(self):
        # Executed twin of the retired render_fallback_on_bracket_failure
        # mirror against the real overlay render path: bracket fails (gap too
        # large), the bounded near-fallback draws the closest earlier envelope
        # (x1_norm 0.2 -> px 144), never the stale latest buffer item
        # (x1_norm 0.9 -> px 648).
        calls = frontend_node.overlay_render_calls(
            {"isWater": True},
            [
                frontend_node.envelope(-6000, x1_norm=0.1),
                frontend_node.envelope(-2000, x1_norm=0.2),
                frontend_node.envelope(-200, x1_norm=0.9),
            ],
            raw_offset_ms=-1000.0,
            water_latency_s=0.5,
        )
        self.assertEqual(len(calls["strokeRect"]), 1)
        self.assertAlmostEqual(calls["strokeRect"][0][0], 144.0, delta=1e-6)
        self.assertNotAlmostEqual(calls["strokeRect"][0][0], 648.0, delta=1.0)

    def test_fallback_beyond_two_seconds_clears(self):
        # Closest earlier envelope is 2500ms older than mediaMs -> outside the
        # LIVE_NEAR_MAX_AGE_MS bound -> the real module clears instead of drawing.
        calls = frontend_node.overlay_render_calls(
            {"isWater": True},
            [
                frontend_node.envelope(-6000, x1_norm=0.1),
                frontend_node.envelope(-300, x1_norm=0.9),
            ],
            raw_offset_ms=-3500.0,
            water_latency_s=0.5,
        )
        self.assertEqual(calls["strokeRect"], [])
        self.assertGreaterEqual(calls["clearRect"], 1)

    def test_future_only_metadata_clears(self):
        # Both envelopes capture after the resolved media time -> no closest
        # earlier envelope exists -> clear.
        calls = frontend_node.overlay_render_calls(
            {"isWater": True},
            [
                frontend_node.envelope(-200, x1_norm=0.3),
                frontend_node.envelope(-100, x1_norm=0.9),
            ],
            raw_offset_ms=-5000.0,
            water_latency_s=0.5,
        )
        self.assertEqual(calls["strokeRect"], [])
        self.assertGreaterEqual(calls["clearRect"], 1)

    def test_frontend_source_contains_relative_sync_markers(self):
        source = FRONTEND_SOURCE.read_text(encoding="utf-8")
        live_sync = LIVE_SYNC_SOURCE.read_text(encoding="utf-8")
        overlay = OVERLAY_MODULE.read_text(encoding="utf-8")
        for marker in (
            "function ssWaterPlaybackLatencyMs()",
            "function ssWaterTargetCaptureMs(opts)",
            "return Math.max(...captures) - latencyMs;",
            'latest.camera_id === "cam1"',
            "ssInstallWaterMediaTimeProbe();",
        ):
            self.assertIn(marker, live_sync)
        self.assertIn("var LIVE_NEAR_MAX_AGE_MS = 2000;", overlay)
        self.assertIn("var br = bracketForMedia(raw);", overlay)
        self.assertNotIn("drawLive(liveBuffer[liveBuffer.length-1])", overlay)
        self.assertNotIn("drawLive(liveBuffer[liveBuffer.length-1])", source)
        self.assertNotIn(
            "Math.abs(raw-(liveBuffer.length?Math.max(...liveBuffer.map(e=>getCaptureMs(e)||0)):0))>6000",
            overlay,
        )


if __name__ == "__main__":
    unittest.main()
