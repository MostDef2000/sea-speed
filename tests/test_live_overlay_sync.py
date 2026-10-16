"""065 AC-001: unified live-sync module contract for Road and Water.

The live-overlay contour rendering that previously lived as duplicated
inline IIFEs in index.html and road/index.html now lives in
overlay-canvas.js, which delegates the sync math to live-sync.js
(SeaSpeedLiveSync). #398 wave 1 converted the remaining marker-based
presence/delegation checks to executions of the real modules through
tests/support/frontend_node.py: export presence is asserted on the live
module object, and page delegation is asserted with recording spies around
the shared module while the real overlay renders. The page include tags and
the anti-duplication source pins are kept verbatim as static policy.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "sea-speed"
LIVE_SYNC = FRONTEND / "live-sync.js"
OVERLAY_MODULE = FRONTEND / "overlay-canvas.js"
WATER_HTML = FRONTEND / "index.html"
ROAD_HTML = FRONTEND / "road" / "index.html"

try:
    from tests.support import frontend_node
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import frontend_node

NODE = shutil.which("node")


class LiveSyncModuleTests(unittest.TestCase):
    def test_module_exists_and_exports_shared_helpers(self) -> None:
        # Executed export presence: the real module object must expose the
        # shared helpers as functions (retired the source-text marker pin).
        # No window.SeaSpeedLiveSync !== S identity probe here: the harness
        # binds S from that same global (frontend_node PRELUDE sets
        # window = global before the require), so the comparison is
        # tautological by construction — the meaningful probe is the live
        # object's API surface itself, asserted below for all 7 exports.
        out = frontend_node.run_live_sync(
            "for (const name of ['median', 'clampLag', 'bracketForMedia', 'closestEarlierEnvelope', 'waterPlaybackLatencyMs', 'waterTargetCaptureMs', 'resolvedTargetMs']) {\n"
            "  if (typeof S[name] !== 'function') throw new Error('missing export: ' + name);\n"
            "}\n"
            'console.log("###OK");\n'
        )
        self.assertEqual(out, "###OK")

    def test_both_pages_include_overlay_and_live_sync_modules(self) -> None:
        expected = {
            WATER_HTML: ('<script src="./live-sync.js"></script>', '<script src="/sea-speed/overlay-canvas.js"></script>'),
            ROAD_HTML: ('<script src="/sea-speed/live-sync.js"></script>', '<script src="/sea-speed/overlay-canvas.js"></script>'),
        }
        for html, (live_sync_include, overlay_include) in expected.items():
            source = html.read_text(encoding="utf-8")
            self.assertIn(live_sync_include, source, f"{html.name} missing live-sync include")
            self.assertIn(overlay_include, source, f"{html.name} missing overlay-canvas include")

    def test_pages_delegate_instead_of_duplicating_sync_math(self) -> None:
        # Executed delegation: with the shared module's methods wrapped in
        # recording spies, a real overlay render must reach
        # bracketForMedia/closestEarlierEnvelope (bracket + fallback path) and
        # median/clampLag (lag compensation) instead of duplicating the math.
        out = frontend_node.run_node(
            frontend_node.PRELUDE
            + frontend_node.DOM_STUB_JS
            + "\nrequire(" + frontend_node.js_literal(str(frontend_node.LIVE_SYNC_JS)) + ");\n"
            + "require(" + frontend_node.js_literal(str(frontend_node.OVERLAY_JS)) + ");\n"
            + """
const real = window.SeaSpeedLiveSync;
const calls = { bracket: 0, closest: 0, median: 0, clamp: 0 };
for (const [name, key] of [
  ['bracketForMedia', 'bracket'],
  ['closestEarlierEnvelope', 'closest'],
  ['median', 'median'],
  ['clampLag', 'clamp']
]) {
  const original = real[name];
  real[name] = function () { calls[key]++; return original.apply(this, arguments); };
}
const NOW = Date.now();
const cap = function (e) { return e.capture_time_unix_ms; };
let frame = 0;
// __makeOverlayDom must run before init(): it installs global.document,
// which overlay init() reads immediately. Its no-op requestVideoFrameCallback
// and the PRELUDE setInterval stub keep the real render/poll loops dormant,
// so the only render is the explicit renderForVideoFrame() below — spies are
// installed above, before init, per the delegation contract.
const H = __makeOverlayDom({
  videoId: 'roadMainVideo', canvasId: 'liveOverlayCanvas',
  wrapId: 'roiEditorWrap', rectW: 720, rectH: 405, dpr: 1, video: {}
});
window.hls = { media: H.video, playingDate: new Date(NOW) };
const overlay = window.SeaSpeedOverlayCanvas.init({
  cameraId: 'road1', videoId: 'roadMainVideo', canvasId: 'liveOverlayCanvas',
  wrapId: 'roiEditorWrap', liveUrl: '/x', livePollUrl: '/poll', isWater: false
});
for (let k = 1; k <= 25; k++) {
  overlay.accept({
    id: 'e' + k, camera_id: 'road1', domain: 'road', generation: 1,
    frame_no: ++frame, capture_time_unix_ms: NOW - k * 100,
    frame_width: 1920, frame_height: 1080,
    detections: [{ track_id: 5, class_name: 'obj', x1_norm: 0.1, y1_norm: 0.1, x2_norm: 0.2, y2_norm: 0.2 }]
  });
}
// Lag math (median/clampLag) fires only once updateLag has gathered 20
// samples — one per rendered frame. A single render exercises only
// bracket/closest; 25 renders let the real accumulation reach the lag
// delegation too.
for (let r = 0; r < 25; r++) overlay.renderForVideoFrame();
if (!calls.bracket) throw new Error('overlay must delegate bracketing to the shared module');
if (!calls.closest) throw new Error('overlay must delegate closest-earlier to the shared module');
if (!calls.median || !calls.clamp) throw new Error('overlay must delegate lag math to the shared module');
console.log('###' + JSON.stringify(calls));
"""
        )
        import json

        calls = json.loads(out[out.rfind("###") + 3 :])
        self.assertGreaterEqual(calls["bracket"], 1)
        self.assertGreaterEqual(calls["closest"], 1)
        self.assertGreaterEqual(calls["median"], 1)
        self.assertGreaterEqual(calls["clamp"], 1)
        # Local duplicated implementations must be gone from both pages.
        for html in (WATER_HTML, ROAD_HTML):
            source = html.read_text(encoding="utf-8")
            self.assertNotIn("function bracketForMedia(mediaMs){ if(", source)
            self.assertNotIn("Math.min(600,m)", source)
            self.assertNotIn("window.clearWaterLiveOverlay", source)
            self.assertNotIn("window.clearRoadLiveOverlay", source)

    def test_road_uses_closest_earlier_fallback(self) -> None:
        # Executed on the real road overlay: with no valid bracket, the
        # closest-earlier fallback draws the bounded near envelope instead of
        # clearing (road page config, absolute media time).
        calls = frontend_node.overlay_render_calls(
            {"isWater": False},
            [
                frontend_node.envelope(-6000, page="road", x1_norm=0.1),
                frontend_node.envelope(-2400, page="road", x1_norm=0.2),
            ],
            raw_offset_ms=-500.0,
        )
        self.assertEqual(len(calls["strokeRect"]), 1)
        self.assertAlmostEqual(calls["strokeRect"][0][0], 144.0, delta=1e-6)


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
