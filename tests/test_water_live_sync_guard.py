from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATER_SOURCE = ROOT / "frontend/sea-speed/index.html"


class WaterLiveSyncGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WATER_SOURCE.read_text(encoding="utf-8-sig")

    def test_unresolved_media_time_clears_overlay(self) -> None:
        self.assertIn('if(raw==null){clearLive();return}', self.source)
        self.assertNotIn('if(raw==null){if(liveBuffer.length)drawLive(liveBuffer[liveBuffer.length-1])', self.source)

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
        # HLS may legitimately trail the newest worker envelope. A matching
        # historical envelope in liveBuffer must reach bracket/near selection
        # instead of being rejected only because the newest item is >6s ahead.
        self.assertNotIn('Math.abs(raw-(liveBuffer.length?Math.max(...liveBuffer.map(e=>getCaptureMs(e)||0)):0))>6000', self.source)
        self.assertIn('const br=bracketForMedia(raw);', self.source)

    def test_valid_bracket_interpolation_and_single_hls_remain(self) -> None:
        self.assertIn('const br=bracketForMedia(raw);', self.source)
        self.assertIn('drawLive(interpolate(br.lo,br.hi,br.t))', self.source)
        self.assertEqual(self.source.count('new Hls('), 1)
        self.assertIn('instance.attachMedia(waterMainVideo)', self.source)


if __name__ == "__main__":
    unittest.main()
