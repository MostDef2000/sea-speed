from __future__ import annotations

import ast
import copy
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "worker/hls_motion_yolo_worker_events.py"


def load_nodes(names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"), filename=str(SOURCE))
    selected = []
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            selected.append(copy.deepcopy(node))
            found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing worker nodes: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


class FakeNumpy:
    uint8 = "uint8"
    int32 = "int32"

    @staticmethod
    def zeros(shape: tuple[int, ...], dtype: object) -> dict[str, object]:
        return {"shape": tuple(shape), "dtype": dtype}

    @staticmethod
    def array(values: object, dtype: object) -> dict[str, object]:
        return {"values": list(values), "dtype": dtype}


class FakeCv2:
    fill_calls: list[tuple[object, object, int]] = []
    bitwise_calls: list[tuple[object, object, object]] = []

    @classmethod
    def reset(cls) -> None:
        cls.fill_calls = []
        cls.bitwise_calls = []

    @classmethod
    def fillPoly(cls, mask: object, polygons: object, value: int) -> None:
        cls.fill_calls.append((mask, polygons, value))

    @classmethod
    def bitwise_and(cls, left: object, right: object, mask: object) -> object:
        cls.bitwise_calls.append((left, right, mask))
        return {"masked": True, "frame": left, "mask": mask}


class FakeFrame:
    shape = (576, 704, 3)


class FakeDetector:
    def __init__(self) -> None:
        self.prev = "old-baseline"
        self.active_until = 99.0
        self.last_boxes = [(1, 2, 3, 4)]
        self.last_area = 123.0
        self._roi_processing_signature = "roi:old"


class RoiBoundedWorkerTests(unittest.TestCase):
    def test_roi_mask_keeps_full_frame_when_roi_is_disabled(self) -> None:
        FakeCv2.reset()
        ns = load_nodes(
            {"mask_frame_to_roi"},
            {"np": FakeNumpy, "cv2": FakeCv2},
        )
        frame = FakeFrame()

        result = ns["mask_frame_to_roi"](frame, [])

        self.assertIs(result, frame)
        self.assertEqual(FakeCv2.fill_calls, [])
        self.assertEqual(FakeCv2.bitwise_calls, [])

    def test_roi_mask_preserves_dimensions_and_blacks_outside_polygon(self) -> None:
        FakeCv2.reset()
        ns = load_nodes(
            {"mask_frame_to_roi"},
            {"np": FakeNumpy, "cv2": FakeCv2},
        )
        frame = FakeFrame()
        points = [(10, 10), (500, 10), (500, 400), (10, 400)]

        result = ns["mask_frame_to_roi"](frame, points)

        self.assertTrue(result["masked"])
        self.assertEqual(FakeCv2.fill_calls[0][0]["shape"], (576, 704))
        self.assertEqual(FakeCv2.fill_calls[0][2], 255)
        polygon = FakeCv2.fill_calls[0][1][0]
        self.assertEqual(polygon["values"], points)
        self.assertEqual(FakeCv2.bitwise_calls[0][0], frame)
        self.assertEqual(FakeCv2.bitwise_calls[0][1], frame)

    def test_roi_change_resets_motion_baseline_and_active_window_once(self) -> None:
        points = [(10, 10), (500, 10), (500, 400), (10, 400)]
        detector = FakeDetector()
        fetches = [(True, points), (True, points)]

        def fetch_remote_roi() -> tuple[bool, list[tuple[int, int]]]:
            return fetches.pop(0)

        ns: dict[str, Any] = {
            "fetch_remote_roi": fetch_remote_roi,
            "mask_frame_to_roi": lambda frame, roi_points: ("masked", frame, tuple(roi_points)),
        }
        load_nodes({"roi_processing_signature", "prepare_roi_processing_frame"}, ns)

        first_frame, first_points = ns["prepare_roi_processing_frame"]("frame-a", detector)
        self.assertEqual(first_points, points)
        self.assertEqual(first_frame[0], "masked")
        self.assertIsNone(detector.prev)
        self.assertEqual(detector.active_until, 0.0)
        self.assertEqual(detector.last_boxes, [])
        self.assertEqual(detector.last_area, 0.0)

        detector.prev = "new-baseline"
        detector.active_until = 7.0
        second_frame, second_points = ns["prepare_roi_processing_frame"]("frame-b", detector)
        self.assertEqual(second_points, points)
        self.assertEqual(second_frame[0], "masked")
        self.assertEqual(detector.prev, "new-baseline")
        self.assertEqual(detector.active_until, 7.0)

    def test_main_uses_same_roi_bounded_frame_for_motion_and_ai(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        start = source.index("def main():")
        main_source = source[start:]

        prepare = "processing_frame, roi_points = prepare_roi_processing_frame(frame, motion_detector)"
        motion = "motion_detector.process(processing_frame)"
        inference = "detect_vehicles(model, processing_frame)"
        final_guard = "filter_detections_by_roi(detections, roi_points)"

        self.assertIn(prepare, main_source)
        self.assertIn(motion, main_source)
        self.assertIn(inference, main_source)
        self.assertIn(final_guard, main_source)
        self.assertLess(main_source.index(prepare), main_source.index(motion))
        self.assertLess(main_source.index(motion), main_source.index(inference))
        self.assertNotIn("detect_vehicles(model, frame)", main_source)

    def test_operator_overlay_keeps_ai_boxes_but_not_motion_boxes(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        start = source.index("def draw_overlay(")
        end = source.index("def post_state(", start)
        draw_source = source[start:end]

        self.assertNotIn("for x, y, w, h in motion_boxes:", draw_source)
        self.assertNotIn("(0, 255, 255)", draw_source)
        self.assertIn('for det in detections:', draw_source)
        self.assertIn("(0, 255, 0)", draw_source)
        self.assertIn("format_detection_label(det)", draw_source)

    def test_roi_filter_accepts_explicit_frame_snapshot(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        self.assertIn("def detection_inside_road_roi(det, points=None):", source)
        self.assertIn("def filter_detections_by_roi(detections, points=None):", source)
        self.assertIn("if points is None:\n        points = parse_road_roi_polygon()", source)


if __name__ == "__main__":
    unittest.main()
