from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATER_SOURCE = ROOT / "frontend/sea-speed/index.html"
LIVE_SYNC_SOURCE = ROOT / "frontend/sea-speed/live-sync.js"


class WaterLiveSyncGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WATER_SOURCE.read_text(encoding="utf-8-sig")
        cls.live_sync = LIVE_SYNC_SOURCE.read_text(encoding="utf-8-sig")

    def test_unresolved_absolute_media_time_reaches_relative_selector(self) -> None:
        # The Water page still fails closed if no target can be resolved, but
        # live-sync installs a Water-video sentinel so missing/invalid absolute
        # program time reaches the relative live-edge selector instead of
        # returning before bracket selection.
        self.assertIn('if(raw==null){clearLive();return}', self.source)
        self.assertIn('function ssInstallWaterMediaTimeProbe()', self.live_sync)
        self.assertIn('return new Date(NaN);', self.live_sync)
        self.assertIn('ssInstallWaterMediaTimeProbe();', self.live_sync)

    def test_water_uses_hls_live_edge_latency_before_absolute_clock(self) -> None:
        self.assertIn('function ssWaterPlaybackLatencyMs()', self.live_sync)
        self.assertIn('Number(hls.latency)', self.live_sync)
        self.assertIn('video.seekable.end(video.seekable.length - 1)', self.live_sync)
        self.assertIn('return Math.max(...captures) - latencyMs;', self.live_sync)
        self.assertIn('if (ssIsWaterBuffer(opts)) {', self.live_sync)
        self.assertIn('if (Number.isFinite(relativeTarget)) return relativeTarget;', self.live_sync)

    def test_relative_mapping_is_water_only(self) -> None:
        self.assertIn('latest.camera_id === "cam1"', self.live_sync)
        self.assertIn('latest.domain !== "road"', self.live_sync)
        self.assertIn('return absoluteMediaMs - Number(opts.lagCompensationMs || 0);', self.live_sync)

    def test_closest_earlier_fallback_is_explicitly_bounded(self) -> None:
        self.assertIn('const LIVE_NEAR_MAX_AGE_MS=2000;', self.source)
        self.assertIn('nearCapture>=mediaMs-LIVE_NEAR_MAX_AGE_MS&&nearCapture<=mediaMs', self.source)
        self.assertIn('const near=closestEarlierEnvelope(mediaMs),nearCapture=near?getCaptureMs(near):null;', self.source)

    def test_unmatched_metadata_never_uses_latest_buffer_item(self) -> None:
        self.assertIn('if(!br){', self.source)
        self.assertIn('else clearLive();return}', self.source)
        self.assertNotIn('else if(liveBuffer.length)drawLive(liveBuffer[liveBuffer.length-1])', self.source)
        self.assertNotIn('drawLive(liveBuffer[liveBuffer.length-1])', self.source)

    def test_media_time_matching_is_not_blocked_by_newest_envelope_age(self) -> None:
        self.assertNotIn('Math.abs(raw-(liveBuffer.length?Math.max(...liveBuffer.map(e=>getCaptureMs(e)||0)):0))>6000', self.source)
        self.assertIn('const br=bracketForMedia(raw);', self.source)

    def test_valid_bracket_interpolation_and_single_hls_remain(self) -> None:
        self.assertIn('const br=bracketForMedia(raw);', self.source)
        self.assertIn('drawLive(interpolate(br.lo,br.hi,br.t))', self.source)
        self.assertEqual(self.source.count('new Hls('), 1)
        self.assertIn('instance.attachMedia(waterMainVideo)', self.source)


if __name__ == "__main__":
    unittest.main()
