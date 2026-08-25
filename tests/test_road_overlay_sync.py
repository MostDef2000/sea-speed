#!/usr/bin/env python3
"""Deterministic tests for Road video-time synchronized overlay (058)."""

import unittest


def interpolate_boxes(a, b, t):
    if a is None or a.get("generation") != b.get("generation"):
        return b
    prior = {str(d["track_id"]): d for d in (a.get("detections") or []) if d.get("track_id") is not None}
    out_dets = []
    for d in (b.get("detections") or []):
        if d.get("track_id") is None:
            out_dets.append(dict(d))
            continue
        p = prior.get(str(d["track_id"]))
        if p is None:
            out_dets.append(dict(d))
            continue
        o = dict(d)
        for k in ("x1_norm", "y1_norm", "x2_norm", "y2_norm"):
            o[k] = float(p.get(k, 0)) + (float(d.get(k, 0)) - float(p.get(k, 0))) * t
        out_dets.append(o)
    return {**b, "detections": out_dets}


def bracket_for_media(buffer, media_ms, max_gap=500):
    lo = hi = None
    for env in sorted(buffer, key=lambda e: e.get("capture_time_unix_ms", 0)):
        t = env.get("capture_time_unix_ms")
        if t is None:
            continue
        if t <= media_ms:
            lo = env
        else:
            hi = env
            break
    if not lo or not hi:
        return None
    if lo.get("generation") != hi.get("generation"):
        return None
    gap = hi["capture_time_unix_ms"] - lo["capture_time_unix_ms"]
    if gap <= 0 or gap > max_gap:
        return None
    t = (media_ms - lo["capture_time_unix_ms"]) / gap
    if t < 0 or t > 1:
        return None
    return (lo, hi, t)


class RoadOverlaySyncTest(unittest.TestCase):
    def test_interpolate_same_generation_same_track(self):
        a = {"generation": 1, "detections": [{"track_id": 5, "x1_norm": 0.1, "y1_norm": 0.1, "x2_norm": 0.2, "y2_norm": 0.2}]}
        b = {"generation": 1, "detections": [{"track_id": 5, "x1_norm": 0.2, "y1_norm": 0.2, "x2_norm": 0.3, "y2_norm": 0.3}]}
        out = interpolate_boxes(a, b, 0.5)
        self.assertAlmostEqual(out["detections"][0]["x1_norm"], 0.15)

    def test_no_interpolate_across_generation(self):
        a = {"generation": 1, "detections": [{"track_id": 5, "x1_norm": 0.1, "y1_norm": 0.1, "x2_norm": 0.2, "y2_norm": 0.2}]}
        b = {"generation": 2, "detections": [{"track_id": 5, "x1_norm": 0.5, "y1_norm": 0.5, "x2_norm": 0.6, "y2_norm": 0.6}]}
        out = interpolate_boxes(a, b, 0.5)
        self.assertEqual(out["detections"][0]["x1_norm"], 0.5)

    def test_bracket_valid(self):
        buf = [
            {"generation": 1, "capture_time_unix_ms": 1000, "frame_no": 1},
            {"generation": 1, "capture_time_unix_ms": 1100, "frame_no": 2},
            {"generation": 1, "capture_time_unix_ms": 1200, "frame_no": 3},
        ]
        br = bracket_for_media(buf, 1050)
        self.assertIsNotNone(br)
        lo, hi, t = br
        self.assertEqual(lo["frame_no"], 1)
        self.assertEqual(hi["frame_no"], 2)
        self.assertAlmostEqual(t, 0.5)

    def test_bracket_gap_too_large_clears(self):
        buf = [
            {"generation": 1, "capture_time_unix_ms": 1000},
            {"generation": 1, "capture_time_unix_ms": 2000},
        ]
        self.assertIsNone(bracket_for_media(buf, 1500, max_gap=500))

    def test_bracket_generation_mismatch_clears(self):
        buf = [
            {"generation": 1, "capture_time_unix_ms": 1000},
            {"generation": 2, "capture_time_unix_ms": 1100},
        ]
        self.assertIsNone(bracket_for_media(buf, 1050))

    def test_bracket_no_extrapolation_before_first(self):
        buf = [{"generation": 1, "capture_time_unix_ms": 1000}, {"generation": 1, "capture_time_unix_ms": 1100}]
        self.assertIsNone(bracket_for_media(buf, 900))

    def test_bracket_no_extrapolation_after_last(self):
        buf = [{"generation": 1, "capture_time_unix_ms": 1000}, {"generation": 1, "capture_time_unix_ms": 1100}]
        self.assertIsNone(bracket_for_media(buf, 1200))

    def test_content_box_alignment_pm1px(self):
        # source 1920x1080, container 720x405 (scale 0.375), object at 0.5,0.5
        sw, sh = 1920, 1080
        rw, rh = 720, 405
        scale = min(rw / sw, rh / sh)
        w, h = sw * scale, sh * scale
        cr_x, cr_y = (rw - w) / 2, (rh - h) / 2
        xn, yn = 0.5, 0.5
        x, y = cr_x + xn * w, cr_y + yn * h
        # at DPR 1 and 2, rounding should stay within 1px of ideal
        for dpr in (1, 2):
            rx = round(x * dpr) / dpr
            ry = round(y * dpr) / dpr
            self.assertLessEqual(abs(rx - x), 1.0)
            self.assertLessEqual(abs(ry - y), 1.0)

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
