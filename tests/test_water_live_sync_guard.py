from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "sea-speed"
WATER_SOURCE = FRONTEND / "index.html"
LIVE_SYNC_SOURCE = FRONTEND / "live-sync.js"
OVERLAY_MODULE = FRONTEND / "overlay-canvas.js"

try:
    from tests.support import frontend_node
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import frontend_node


class WaterLiveSyncGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WATER_SOURCE.read_text(encoding="utf-8-sig")
        cls.live_sync = LIVE_SYNC_SOURCE.read_text(encoding="utf-8-sig")
        cls.overlay = OVERLAY_MODULE.read_text(encoding="utf-8-sig")

    def test_unresolved_absolute_media_time_reaches_relative_selector(self) -> None:
        # The Water page still fails closed if no target can be resolved, but
        # live-sync installs a Water-video sentinel so missing/invalid absolute
        # program time reaches the relative live-edge selector instead of
        # returning before bracket selection. Executed against the real module:
        # after require(), the Water video carries the probe sentinel
        # (invalid-Date fallback for absent/null native getStartDate, native
        # passthrough otherwise), and the overlay module owns the null-media
        # fallback (draw latest envelope) instead of the page IIFE.
        body = (
            "const p = " + frontend_node.js_literal(str(LIVE_SYNC_SOURCE)) + ";\n"
            "delete require.cache[p];  // re-execute module level with document present\n"
            "const video = { readyState: 2 };\n"
            "global.document = { getElementById: function (id) { return id === 'waterMainVideo' ? video : null; } };\n"
            "require(p);\n"
            "if (typeof video.getStartDate !== 'function') throw new Error('probe not installed');\n"
            "if (video.__seaSpeedMediaTimeProbeInstalled !== true) throw new Error('probe flag missing');\n"
            "const sentinel = video.getStartDate();\n"
            "if (!(sentinel instanceof Date) || !Number.isNaN(sentinel.getTime())) throw new Error('expected invalid-Date sentinel, got ' + sentinel);\n"
            "delete require.cache[p];\n"
            "const v2 = { getStartDate: function () { return new Date(42); } };\n"
            "global.document = { getElementById: function (id) { return id === 'waterMainVideo' ? v2 : null; } };\n"
            "require(p);\n"
            "if (v2.getStartDate().getTime() !== 42) throw new Error('native passthrough broken');\n"
            "if (v2.__seaSpeedMediaTimeProbeInstalled !== true) throw new Error('probe flag missing on native video');\n"
            "delete require.cache[p];\n"
            "const v3 = { getStartDate: function () { return null; } };\n"
            "global.document = { getElementById: function (id) { return id === 'waterMainVideo' ? v3 : null; } };\n"
            "require(p);\n"
            "const nullSentinel = v3.getStartDate();\n"
            "if (!Number.isNaN(nullSentinel.getTime())) throw new Error('null native value must yield invalid-Date sentinel');\n"
            'console.log("###OK");\n'
        )
        self.assertEqual(frontend_node.run_live_sync(body), "###OK")
        # Overlay side of the sentinel: raw == null reaches the null-media
        # fallback, which draws the most recent buffered envelope.
        calls = frontend_node.overlay_render_calls(
            {"isWater": True},
            [frontend_node.envelope(-600, x1_norm=0.3), frontend_node.envelope(-300, x1_norm=0.9)],
            raw_offset_ms=None,
            water_latency_s=None,
        )
        self.assertEqual(len(calls["strokeRect"]), 1)
        self.assertAlmostEqual(calls["strokeRect"][0][0], 648.0, delta=1e-6)

    def test_water_uses_hls_live_edge_latency_before_absolute_clock(self) -> None:
        # Executed: the relative live-edge projection wins BEFORE the absolute
        # media clock is consulted (raw playingDate is deliberately garbage),
        # and an unavailable latency falls through to the absolute path.
        out = frontend_node.run_live_sync(
            "const buf = [\n"
            "  { camera_id: 'cam1', domain: 'sea', generation: 1, capture_time_unix_ms: 10000 },\n"
            "  { camera_id: 'cam1', domain: 'sea', generation: 1, capture_time_unix_ms: 10200 },\n"
            "  { camera_id: 'cam1', domain: 'sea', generation: 1, capture_time_unix_ms: 10600 }\n"
            "];\n"
            "const cap = function (e) { return e.capture_time_unix_ms; };\n"
            "const opts = { liveBuffer: buf, getCaptureMs: cap, lagCompensationMs: 300, maxGapMs: 500 };\n"
            "window.waterHls = { latency: 0.5 };\n"
            "const relative = S.resolvedTargetMs(999999, opts);\n"
            "if (relative !== 10100) throw new Error('relative live-edge target must win: ' + relative);\n"
            "window.waterHls = {};\n"
            "const absolute = S.resolvedTargetMs(9000, opts);\n"
            "if (absolute !== 8700) throw new Error('latency-less water must fall back to absolute minus lag: ' + absolute);\n"
            'console.log("###OK");\n'
        )
        self.assertEqual(out, "###OK")

    def test_seekable_fallback_latency_is_last_seekable_end_minus_current_time(self) -> None:
        # Executed twin of the retired text pin
        # "video.seekable.end(video.seekable.length - 1)" (old L33): with
        # window.waterHls unavailable (hls-latency branch skipped), the real
        # ssWaterPlaybackLatencyMs reads the Water video's seekable range and
        # returns (end(length - 1) - currentTime) seconds * 1000, failing
        # closed outside 0..30s or without a seekable range. Two ranges with
        # distinct ends make end(length - 1) observable: end(0) would yield a
        # negative latency and fail.
        out = frontend_node.run_live_sync(
            "const endsCalled = [];\n"
            "const video = {\n"
            "  currentTime: 41,\n"
            "  seekable: { length: 2, end: function (i) { endsCalled.push(i); return i === 1 ? 43.5 : 4; } }\n"
            "};\n"
            "global.document = { getElementById: function (id) { return id === 'waterMainVideo' ? video : null; } };\n"
            "const latency = S.waterPlaybackLatencyMs();\n"
            "if (latency !== (43.5 - 41) * 1000) throw new Error('seekable fallback must return (end(length-1) - currentTime) * 1000, got ' + latency);\n"
            "if (endsCalled.length !== 1 || endsCalled[0] !== video.seekable.length - 1) throw new Error('must read the last seekable range end, called with: ' + endsCalled);\n"
            "video.currentTime = 45;\n"
            "if (S.waterPlaybackLatencyMs() !== null) throw new Error('negative seekable latency (currentTime past the edge) must fail closed');\n"
            "video.currentTime = 0;\n"
            "if (S.waterPlaybackLatencyMs() !== null) throw new Error('seekable latency beyond the 30s bound must fail closed');\n"
            "const bare = { currentTime: 1 };\n"
            "global.document = { getElementById: function (id) { return id === 'waterMainVideo' ? bare : null; } };\n"
            "if (S.waterPlaybackLatencyMs() !== null) throw new Error('video without seekable must fail closed');\n"
            'console.log("###OK");\n'
        )
        self.assertEqual(out, "###OK")

    def test_relative_mapping_is_water_only(self) -> None:
        # Executed: only cam1/non-road buffers take the relative mapping (and
        # ignore lagCompensationMs); road envelopes — and a cam1 envelope with
        # road domain — keep the absolute media-time path minus lag.
        out = frontend_node.run_live_sync(
            "const cap = function (e) { return e.capture_time_unix_ms; };\n"
            "const waterBuf = [\n"
            "  { camera_id: 'cam1', domain: 'sea', generation: 1, capture_time_unix_ms: 10000 },\n"
            "  { camera_id: 'cam1', domain: 'sea', generation: 1, capture_time_unix_ms: 10600 }\n"
            "];\n"
            "const roadBuf = [\n"
            "  { camera_id: 'road1', domain: 'road', generation: 1, capture_time_unix_ms: 10000 },\n"
            "  { camera_id: 'road1', domain: 'road', generation: 1, capture_time_unix_ms: 10600 }\n"
            "];\n"
            "const cam1RoadDomainBuf = [\n"
            "  { camera_id: 'cam1', domain: 'road', generation: 1, capture_time_unix_ms: 10000 },\n"
            "  { camera_id: 'cam1', domain: 'road', generation: 1, capture_time_unix_ms: 10600 }\n"
            "];\n"
            "window.waterHls = { latency: 0.5 };\n"
            "if (S.resolvedTargetMs(999999, { liveBuffer: waterBuf, getCaptureMs: cap, lagCompensationMs: 300, maxGapMs: 500 }) !== 10100) throw new Error('water must map relatively, ignoring lag compensation');\n"
            "if (S.resolvedTargetMs(9000, { liveBuffer: roadBuf, getCaptureMs: cap, lagCompensationMs: 300, maxGapMs: 500 }) !== 8700) throw new Error('road must keep absolute media time minus lag');\n"
            "if (S.resolvedTargetMs(9000, { liveBuffer: cam1RoadDomainBuf, getCaptureMs: cap, lagCompensationMs: 300, maxGapMs: 500 }) !== 8700) throw new Error('cam1 envelopes with road domain must stay on the absolute path');\n"
            'console.log("###OK");\n'
        )
        self.assertEqual(out, "###OK")

    def test_closest_earlier_fallback_is_explicitly_bounded(self) -> None:
        # Executed on the real overlay module (road page config, absolute media
        # time, lagCompensationMs 0 -> mediaMs == raw): the closest-earlier
        # envelope is drawn only inside the LIVE_NEAR_MAX_AGE_MS=2000 bound.
        # Two runs: a near envelope 1900ms older than mediaMs draws; one
        # 2100ms older clears.
        near_calls = frontend_node.overlay_render_calls(
            {"isWater": False},
            [
                frontend_node.envelope(-6000, page="road", x1_norm=0.1),
                frontend_node.envelope(-2400, page="road", x1_norm=0.2),
            ],
            raw_offset_ms=-500.0,
        )
        self.assertEqual(len(near_calls["strokeRect"]), 1)
        self.assertAlmostEqual(near_calls["strokeRect"][0][0], 144.0, delta=1e-6)
        stale_calls = frontend_node.overlay_render_calls(
            {"isWater": False},
            [
                frontend_node.envelope(-6000, page="road", x1_norm=0.1),
                frontend_node.envelope(-2600, page="road", x1_norm=0.2),
            ],
            raw_offset_ms=-500.0,
        )
        self.assertEqual(stale_calls["strokeRect"], [])
        self.assertGreaterEqual(stale_calls["clearRect"], 1)

    def test_unmatched_metadata_never_uses_latest_buffer_item(self) -> None:
        # Executed: with no valid bracket and a near envelope older than the
        # bound, the real module clears the canvas instead of drawing the
        # latest buffer item.
        calls = frontend_node.overlay_render_calls(
            {"isWater": False},
            [
                frontend_node.envelope(-6000, page="road", x1_norm=0.1),
                frontend_node.envelope(-300, page="road", x1_norm=0.9),
            ],
            raw_offset_ms=-3500.0,
        )
        self.assertEqual(calls["strokeRect"], [])
        self.assertGreaterEqual(calls["clearRect"], 1)
        self.assertNotIn("drawLive(liveBuffer[liveBuffer.length-1])", self.overlay)
        self.assertNotIn("drawLive(liveBuffer[liveBuffer.length-1])", self.source)

    def test_media_time_matching_is_not_blocked_by_newest_envelope_age(self) -> None:
        # Executed: the newest buffered envelope is 6800ms older than raw
        # (beyond the retired 6000ms blocker) and the real module still
        # brackets and interpolates on the Water relative timeline.
        calls = frontend_node.overlay_render_calls(
            {"isWater": True},
            [
                frontend_node.envelope(-7000, x1_norm=0.1),
                frontend_node.envelope(-6800, x1_norm=0.2),
            ],
            raw_offset_ms=0.0,
            water_latency_s=0.1,
        )
        self.assertEqual(len(calls["strokeRect"]), 1)
        self.assertAlmostEqual(calls["strokeRect"][0][0], 108.0, delta=1e-6)
        self.assertNotIn(
            "Math.abs(raw-(liveBuffer.length?Math.max(...liveBuffer.map(e=>getCaptureMs(e)||0)):0))>6000",
            self.overlay,
        )

    def test_valid_bracket_interpolation_and_single_hls_remain(self) -> None:
        # Executed: a valid same-generation bracket interpolates the drawn box
        # between the two envelopes (x1_norm 0.1 -> 0.2 at t=0.5 -> px 108).
        calls = frontend_node.overlay_render_calls(
            {"isWater": True},
            [
                frontend_node.envelope(-600, x1_norm=0.1),
                frontend_node.envelope(-300, x1_norm=0.2),
            ],
            raw_offset_ms=0.0,
            water_latency_s=0.15,
        )
        self.assertEqual(len(calls["strokeRect"]), 1)
        self.assertAlmostEqual(calls["strokeRect"][0][0], 108.0, delta=1e-6)
        self.assertEqual(self.source.count("new Hls("), 1)
        self.assertIn("instance.attachMedia(waterMainVideo)", self.source)


if __name__ == "__main__":
    unittest.main()
