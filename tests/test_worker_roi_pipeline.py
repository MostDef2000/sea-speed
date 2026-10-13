from __future__ import annotations

import ast
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "worker/hls_motion_yolo_worker_events.py"

try:
    from tests.support import worker_source
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import worker_source


def load_nodes(names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    # 398-wave-a: shared AST-slice+exec harness (was a private duplicate pinned
    # to one path) — tests/support/worker_source.py resolves the worker source
    # so the #397 decomposition can move functions/classes between files.
    return worker_source.load_functions(names, namespace)


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

    def test_roi_change_resets_motion_baseline_and_binds_snapshot_once(self) -> None:
        points = [(10, 10), (500, 10), (500, 400), (10, 400)]
        detector = FakeDetector()
        fetches = [(True, points), (True, points)]

        def fetch_remote_roi() -> tuple[bool, list[tuple[int, int]]]:
            return fetches.pop(0)

        ns: dict[str, Any] = {
            "fetch_remote_roi": fetch_remote_roi,
            "mask_frame_to_roi": lambda frame, roi_points: ("masked", frame, tuple(roi_points)),
            "_roi_processing_points": None,
        }
        load_nodes({"roi_processing_signature", "prepare_roi_processing_frame"}, ns)

        first_frame, first_points = ns["prepare_roi_processing_frame"]("frame-a", detector)
        self.assertEqual(first_points, points)
        self.assertEqual(first_frame[0], "masked")
        self.assertEqual(ns["_roi_processing_points"], points)
        self.assertIsNone(detector.prev)
        self.assertEqual(detector.active_until, 0.0)
        self.assertEqual(detector.last_boxes, [])
        self.assertEqual(detector.last_area, 0.0)

        detector.prev = "new-baseline"
        detector.active_until = 7.0
        second_frame, second_points = ns["prepare_roi_processing_frame"]("frame-b", detector)
        self.assertEqual(second_points, points)
        self.assertEqual(second_frame[0], "masked")
        self.assertEqual(ns["_roi_processing_points"], points)
        self.assertEqual(detector.prev, "new-baseline")
        self.assertEqual(detector.active_until, 7.0)

    def test_main_uses_same_roi_bounded_frame_for_motion_and_ai(self) -> None:
        # 398-wave-a: converted from source-text pin (was L142-158) — main()
        # must run motion detection and AI inference on the same ROI-bounded
        # frame snapshot, in that order, with the final ROI guard applied to
        # the detections; the un-bounded detect_vehicles(model, frame) call
        # must stay removed.
        main_node = worker_source.function_node("main")
        prepare_assigns = [
            a for a in worker_source.find_assignments(main_node, "processing_frame")
            if worker_source.dump(a.value) == worker_source.expr_dump("prepare_roi_processing_frame(frame, motion_detector)")
        ]
        self.assertEqual(len(prepare_assigns), 1, "main() must bind the processing frame exactly once")
        motion_calls = worker_source.expr_nodes(main_node, "motion_detector.process(processing_frame)")
        self.assertTrue(motion_calls, "motion detection must run on the processing frame")
        inference_assigns = [
            a for a in worker_source.find_assignments(main_node, "detections")
            if worker_source.dump(a.value) == worker_source.expr_dump("detect_vehicles(model, processing_frame)")
        ]
        self.assertEqual(len(inference_assigns), 1, "AI inference must run on the processing frame")
        guard_calls = [
            a for a in worker_source.find_assignments(main_node, "detections")
            if worker_source.dump(a.value) == worker_source.expr_dump("filter_detections_by_roi(detections)")
        ]
        self.assertTrue(guard_calls, "the final ROI guard must filter detections")
        self.assertLess(prepare_assigns[0].lineno, motion_calls[0].lineno, "ROI snapshot must be bound before motion processing")
        self.assertLess(motion_calls[0].lineno, inference_assigns[0].lineno, "motion must be processed before AI inference")
        self.assertLess(inference_assigns[0].lineno, guard_calls[0].lineno, "the final ROI guard must run after inference")
        legacy_calls: list[ast.Call] = []
        for call in worker_source.calls_named(main_node, "detect_vehicles"):
            if len(call.args) != 2:
                continue
            names = [arg.id for arg in call.args if isinstance(arg, ast.Name)]
            if names == ["model", "frame"]:
                legacy_calls.append(call)
        self.assertEqual(legacy_calls, [], "detect_vehicles(model, frame) must stay removed from main()")

    def test_final_roi_guard_uses_bound_frame_snapshot_before_remote_fallback(self) -> None:
        # 398-wave-a: converted from source-text pin (was L160-176) —
        # prepare_roi_processing_frame must publish the bound ROI snapshot to
        # the module-level _roi_processing_points global, and the ROI guard
        # must prefer that snapshot before falling back to the remote
        # parse_road_roi_polygon() config.
        prepare_node = worker_source.function_node("prepare_roi_processing_frame")
        guard_node = worker_source.function_node("detection_inside_road_roi")
        self.assertTrue(
            any(isinstance(node, ast.Global) and "_roi_processing_points" in node.names for node in ast.walk(prepare_node)),
            "prepare_roi_processing_frame must declare the _roi_processing_points global",
        )
        snapshot_assigns = worker_source.find_assignments(prepare_node, "_roi_processing_points")
        self.assertTrue(
            any(worker_source.dump(a.value) == worker_source.expr_dump("list(points)") for a in snapshot_assigns),
            "the ROI snapshot must be published as a defensive list(points) copy",
        )
        fallback_assigns = worker_source.find_assignments(guard_node, "points")
        snapshot_fallbacks = [a for a in fallback_assigns if worker_source.dump(a.value) == worker_source.expr_dump("_roi_processing_points")]
        remote_fallbacks = [a for a in fallback_assigns if worker_source.dump(a.value) == worker_source.expr_dump("parse_road_roi_polygon()")]
        self.assertTrue(snapshot_fallbacks, "the ROI guard must fall back to the bound frame snapshot")
        self.assertTrue(remote_fallbacks, "the ROI guard must fall back to parse_road_roi_polygon()")
        self.assertLess(
            snapshot_fallbacks[0].lineno,
            remote_fallbacks[0].lineno,
            "the bound frame snapshot must be consulted before the remote fallback",
        )

    def test_operator_overlay_keeps_ai_boxes_but_not_motion_boxes(self) -> None:
        # 398-wave-a: converted from source-text pin (was L178-190) —
        # draw_overlay must not iterate motion boxes, must keep exactly one
        # yellow (0, 255, 255) tuple (reserved for the counting line), and
        # must keep the AI box rendering path (green box, detection labels,
        # crossing-summary gated line drawing).
        draw = worker_source.function_node("draw_overlay")
        motion_loops = [
            node
            for node in ast.walk(draw)
            if isinstance(node, ast.For)
            and isinstance(node.target, ast.Tuple)
            and [elt.id for elt in node.target.elts if isinstance(elt, ast.Name)] == ["x", "y", "w", "h"]
            and worker_source.dump(node.iter) == worker_source.expr_dump("motion_boxes")
        ]
        self.assertEqual(motion_loops, [], "motion boxes must stay out of draw_overlay")
        self.assertEqual(worker_source.tuple_constants(draw).count((0, 255, 255)), 1)
        self.assertTrue(worker_source.contains_expr(draw, 'summary.get("line_enabled")'))
        self.assertTrue(
            any(
                isinstance(node, ast.For)
                and isinstance(node.target, ast.Name)
                and node.target.id == "det"
                and worker_source.dump(node.iter) == worker_source.expr_dump("detections")
                for node in ast.walk(draw)
            ),
            "AI box rendering must iterate detections",
        )
        self.assertIn((0, 255, 0), worker_source.tuple_constants(draw), "AI boxes must render green")
        self.assertTrue(worker_source.contains_expr(draw, "format_detection_label(det)"))

    def test_roi_filter_accepts_explicit_frame_snapshot(self) -> None:
        # 398-wave-a: converted from source-text pin (was L192-196) — both ROI
        # guard signatures must keep their optional points parameter, and the
        # guard must bind the module-level snapshot when no points are passed.
        inside_node = worker_source.function_node("detection_inside_road_roi")
        filter_node = worker_source.function_node("filter_detections_by_roi")
        self.assertEqual([arg.arg for arg in inside_node.args.args], ["det", "points"])
        self.assertEqual(len(inside_node.args.defaults), 1)
        self.assertEqual(worker_source.dump(inside_node.args.defaults[0]), worker_source.expr_dump("None"))
        self.assertEqual([arg.arg for arg in filter_node.args.args], ["detections", "points"])
        self.assertEqual(len(filter_node.args.defaults), 1)
        self.assertEqual(worker_source.dump(filter_node.args.defaults[0]), worker_source.expr_dump("None"))
        self.assertTrue(
            worker_source.contains_stmt(inside_node, "if points is None:\n        points = _roi_processing_points"),
            "the ROI guard must default to the bound frame snapshot",
        )


if __name__ == "__main__":
    unittest.main()
