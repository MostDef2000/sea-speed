"""065 AC-001: unified live-sync module contract for Road and Water.

Marker-based duplication checks plus real execution of live-sync.js
through Node.js when available.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "sea-speed"
LIVE_SYNC = FRONTEND / "live-sync.js"
WATER_HTML = FRONTEND / "index.html"
ROAD_HTML = FRONTEND / "road" / "index.html"

NODE = shutil.which("node")


class LiveSyncModuleTests(unittest.TestCase):
    def test_module_exists_and_exports_shared_helpers(self) -> None:
        source = LIVE_SYNC.read_text(encoding="utf-8")
        for marker in (
            "ssMedian",
            "ssClampLag",
            "ssBracketForMedia",
            "ssClosestEarlierEnvelope",
            "window.SeaSpeedLiveSync",
        ):
            self.assertIn(marker, source)

    def test_both_pages_include_live_sync_before_main_script(self) -> None:
        for html in (WATER_HTML, ROAD_HTML):
            source = html.read_text(encoding="utf-8")
            include_at = source.find('<script src="./live-sync.js"></script>')
            self.assertGreaterEqual(include_at, 0, f"{html.name} missing include")
            main_open = source.find("<script>", include_at)
            self.assertGreater(main_open, include_at, f"{html.name} include after main script")

    def test_pages_delegate_instead_of_duplicating_sync_math(self) -> None:
        for html in (WATER_HTML, ROAD_HTML):
            source = html.read_text(encoding="utf-8")
            self.assertIn("SeaSpeedLiveSync.bracketForMedia(mediaMs,{", source)
            self.assertIn("SeaSpeedLiveSync.closestEarlierEnvelope(compMs,{", source)
            self.assertIn("SeaSpeedLiveSync.clampLag(SeaSpeedLiveSync.median(lagSamples))", source)
            # Local duplicated implementations must be gone.
            self.assertNotIn("function bracketForMedia(mediaMs){ if(", source)
            self.assertNotIn("Math.min(600,m)", source)

    def test_road_uses_closest_earlier_fallback(self) -> None:
        source = ROAD_HTML.read_text(encoding="utf-8")
        self.assertIn("closestEarlierEnvelope(mediaMs)", source)
        self.assertIn("mediaMs-2000", source)


@unittest.skipIf(NODE is None, "node not available")
class LiveSyncBehaviorTests(unittest.TestCase):
    def run_node(self, script: str) -> str:
        proc = subprocess.run(
            [NODE or "node", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    HARNESS = """
      global.window = {};
      require('%s');
      const S = window.SeaSpeedLiveSync;
      const buf = [
        { generation: 1, capture_time_unix_ms: 1000 },
        { generation: 1, capture_time_unix_ms: 1200 },
        { generation: 1, capture_time_unix_ms: 1400 }
      ];
      const cap = e => e.capture_time_unix_ms;
      const opts = { liveBuffer: buf, getCaptureMs: cap, lagCompensationMs: 0, maxGapMs: 500 };
      const br = S.bracketForMedia(1100, opts);
      if (!br || br.lo !== buf[0] || br.hi !== buf[1]) throw new Error('bracket failed');
      if (Math.abs(br.t - 0.5) > 1e-9) throw new Error('interpolation t wrong: ' + br.t);
      if (S.bracketForMedia(1500, opts) !== null) throw new Error('beyond buffer must be null');
      const gen2 = { generation: 2, capture_time_unix_ms: 1250 };
      if (S.bracketForMedia(1220, { ...opts, liveBuffer: [buf[0], gen2] }) !== null) {
        throw new Error('mixed generation must be null');
      }
      if (S.closestEarlierEnvelope(1300, opts) !== buf[1]) throw new Error('closest earlier failed');
      if (S.closestEarlierEnvelope(900, opts) !== null) throw new Error('before buffer must be null');
      if (S.clampLag(-5) !== 0 || S.clampLag(6000) !== 1200 || S.clampLag(700) !== 700) {
        throw new Error('clampLag wrong');
      }
      if (S.median([3, 1, 2]) !== 2 || S.median([1, 2, 3, 4]) !== 2.5) {
        throw new Error('median wrong');
      }
      console.log('OK');
    """

    def test_shared_sync_math_executes_correctly(self) -> None:
        module_path = str(LIVE_SYNC).replace("\\", "\\\\")
        out = self.run_node(self.HARNESS % module_path)
        self.assertEqual(out, "OK")


if __name__ == "__main__":
    unittest.main()
