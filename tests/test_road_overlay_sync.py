#!/usr/bin/env python3
"""Deterministic tests for Road video-time synchronized overlay (058).

#398 wave 1 retired this file's pure-Python mirrors (interpolate_boxes /
bracket_for_media): they were hand-copied semantics of the real frontend JS
and drifted invisibly (the same conflation family as the retired water
mirror's near-fallback anchored on its target argument (the water target,
maxCapture-latencyMs) while the real overlay anchors on
mediaMs = raw - lagCompensationMs; see specs/398-wave1/plan.md D-1).
The road behavior is now asserted by executing the real modules through
tests/support/frontend_node.py:

- the shared bracket/lag math directly on the required live-sync.js module
  object (window.SeaSpeedLiveSync), with road-flavored buffers exactly like
  the road page feeds them, and
- the rendered road page through overlay-canvas.js init()'d on the harness
  DOM stub with the road page config (cameraId road1, absolute media time
  via window.hls.playingDate), pinning the actual strokeRect coordinates.

The synthetic p95 skew bound is not a mirror of any JS module and stays.
"""

from __future__ import annotations

import unittest

try:
    from tests.support import frontend_node
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import frontend_node


def run_road_sync(body: str) -> str:
    """Run ``body`` against the required live-sync module with a road buffer.

    Buffer entries carry the road page's identity (camera_id road1,
    domain road) so the module's water-detection branch never engages and
    the absolute media-time path is the one under test.
    """
    prelude = """
const cap = function (e) { return e.capture_time_unix_ms; };
const env = function (captureMs, generation) {
  return { capture_time_unix_ms: captureMs, generation: generation,
    camera_id: 'road1', domain: 'road' };
};
const opts = { liveBuffer: [], getCaptureMs: cap, lagCompensationMs: 0,
  maxGapMs: 500 };
"""
    return frontend_node.run_live_sync(prelude + body)


class RoadBracketMathTest(unittest.TestCase):
    """Executed twins of the retired bracket_for_media mirror pins."""

    def test_bracket_valid_midpoint_interpolates(self):
        out = run_road_sync(
            "opts.liveBuffer = [env(1000, 1), env(1100, 1), env(1200, 1)];\n"
            "const br = S.bracketForMedia(1050, opts);\n"
            "if (!br) throw new Error('midpoint of two same-gen envelopes must bracket');\n"
            "if (br.lo !== opts.liveBuffer[0] || br.hi !== opts.liveBuffer[1]) {\n"
            "  throw new Error('bracket picked the wrong pair');\n"
            "}\n"
            "if (Math.abs(br.t - 0.5) > 1e-9) throw new Error('t wrong: ' + br.t);\n"
            'console.log("###OK");\n'
        )
        self.assertEqual(out, "###OK")

    def test_bracket_gap_too_large_is_null(self):
        out = run_road_sync(
            "opts.liveBuffer = [env(1000, 1), env(2000, 1)];\n"
            "if (S.bracketForMedia(1500, opts) !== null) {\n"
            "  throw new Error('gap 1000 > maxGapMs 500 must not bracket');\n"
            "}\n"
            'console.log("###OK");\n'
        )
        self.assertEqual(out, "###OK")

    def test_bracket_generation_mismatch_is_null(self):
        out = run_road_sync(
            "opts.liveBuffer = [env(1000, 1), env(1100, 2)];\n"
            "if (S.bracketForMedia(1050, opts) !== null) {\n"
            "  throw new Error('mixed-generation pair must not bracket');\n"
            "}\n"
            'console.log("###OK");\n'
        )
        self.assertEqual(out, "###OK")

    def test_bracket_never_extrapolates(self):
        out = run_road_sync(
            "opts.liveBuffer = [env(1000, 1), env(1100, 1)];\n"
            "if (S.bracketForMedia(900, opts) !== null) {\n"
            "  throw new Error('before-first must not extrapolate');\n"
            "}\n"
            "if (S.bracketForMedia(1200, opts) !== null) {\n"
            "  throw new Error('after-last must not extrapolate');\n"
            "}\n"
            'console.log("###OK");\n'
        )
        self.assertEqual(out, "###OK")


class RoadOverlayRenderTest(unittest.TestCase):
    """Executed road-page render: real overlay module on the harness DOM."""

    def test_interpolates_within_generation(self):
        # 720x405 rect shows a 1920x1080 frame at scale 0.375 (cr.x=cr.y=0).
        # Envelopes -300/-100 with the media time at the midpoint (-200)
        # bracket with t=0.5: x1 0.1 -> 0.2 blends to 0.15 -> 108 px.
        calls = frontend_node.overlay_render_calls(
            {"isWater": False},
            [
                frontend_node.envelope(-300, page="road", x1_norm=0.1),
                frontend_node.envelope(-100, page="road", x1_norm=0.2),
            ],
            raw_offset_ms=-200.0,
        )
        self.assertEqual(len(calls["strokeRect"]), 1)
        self.assertAlmostEqual(calls["strokeRect"][0][0], 108.0, delta=1e-6)

    def test_generation_bump_resets_and_draws_new_generation(self):
        # The retired mirror pinned interpolate_boxes() on a hand-built
        # mixed-generation pair — a state the real overlay can never hold:
        # accept() resets the buffer whenever the generation advances, and
        # the shared bracket also refuses mixed pairs. Executed twin: after a
        # gen-2 envelope arrives, the render draws gen-2's own box (0.5*720 =
        # 360) verbatim — any cross-generation blend would land elsewhere
        # (216 px for a 0.5 blend of 0.1->0.5, 72 px for the stale gen-1 box).
        calls = frontend_node.overlay_render_calls(
            {"isWater": False},
            [
                frontend_node.envelope(-300, page="road", x1_norm=0.1, generation=1),
                frontend_node.envelope(-100, page="road", x1_norm=0.5, generation=2),
            ],
            raw_offset_ms=-50.0,
        )
        self.assertEqual(len(calls["strokeRect"]), 1)
        self.assertAlmostEqual(calls["strokeRect"][0][0], 360.0, delta=1e-6)

    def test_content_box_alignment_letterbox_and_dpr(self):
        # A non-16:9 container (720x500) must letterbox the 16:9 frame
        # (scale 0.375 -> content 720x405, centered at y=47.5) and map a
        # detection at (0.5, 0.5) to the ideal (360, 250); DPR only resizes
        # the backing store, so the CSS-pixel draw coords are identical at
        # DPR 1 and 2 — well within the retired test's 1px bound.
        envelope_spec = frontend_node.envelope(
            0, page="road", x1_norm=0.5, y1_norm=0.5, x2_norm=0.6, y2_norm=0.6
        )
        ideal_x = 0.5 * 720
        ideal_y = (500 - 405) / 2 + 0.5 * 405
        for dpr in (1, 2):
            calls = frontend_node.overlay_render_calls(
                {"isWater": False, "rectW": 720, "rectH": 500, "dpr": dpr},
                [dict(envelope_spec)],
                raw_offset_ms=None,
            )
            self.assertEqual(len(calls["strokeRect"]), 1, f"dpr={dpr}")
            box = calls["strokeRect"][0]
            self.assertLessEqual(abs(box[0] - ideal_x), 1.0)
            self.assertLessEqual(abs(box[1] - ideal_y), 1.0)

    def test_stale_nearest_envelope_beyond_near_age_clears(self):
        # No valid bracket and the newest envelope older than the 2000ms
        # near-age bound must clear the canvas instead of drawing a stale box.
        calls = frontend_node.overlay_render_calls(
            {"isWater": False},
            [frontend_node.envelope(-2400, page="road", x1_norm=0.2)],
            raw_offset_ms=0.0,
        )
        self.assertEqual(calls["strokeRect"], [])
        self.assertGreaterEqual(calls["clearRect"], 1)


class RoadSkewBudgetTest(unittest.TestCase):
    def test_p95_skew_bound(self):
        # synthetic skew samples: p95 must be <=150ms
        skews = [20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 300]
        skews_sorted = sorted(skews)
        idx = int(0.95 * (len(skews) - 1))
        p95 = skews_sorted[idx]
        self.assertLessEqual(p95, 150)
        self.assertLessEqual(max(skews_sorted[:14]), 250)


if __name__ == "__main__":
    unittest.main()
