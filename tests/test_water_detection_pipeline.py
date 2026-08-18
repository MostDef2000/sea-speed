from __future__ import annotations

import ast
import copy
import unittest
from pathlib import Path
from types import SimpleNamespace
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


class WaterDetectionPolicyTests(unittest.TestCase):
    def test_water_runs_detection_without_motion_and_does_not_motion_filter(self) -> None:
        calls: list[tuple[str, object]] = []
        vessel = {
            "track_id": 17,
            "class_name": "vessel",
            "analytics_profile": "water-v1",
            "domain": "water",
            "bbox_xyxy": [20, 20, 40, 40],
            "confidence": 0.8,
        }

        def detect_vehicles(_model: object, frame: object) -> list[dict[str, object]]:
            calls.append(("detect", frame))
            return [dict(vessel)]

        def filter_detections_by_motion(_detections: object, _boxes: object) -> list[dict[str, object]]:
            calls.append(("motion-filter", _boxes))
            return []

        def filter_detections_by_roi(detections: object, points: object) -> object:
            calls.append(("roi-filter", points))
            return detections

        ns = load_nodes(
            {"select_profile_detections"},
            {
                "detect_vehicles": detect_vehicles,
                "filter_detections_by_motion": filter_detections_by_motion,
                "filter_detections_by_roi": filter_detections_by_roi,
            },
        )
        profile = SimpleNamespace(name="water-v1", domain="water")

        ai_active, detections = ns["select_profile_detections"](
            profile,
            object(),
            "roi-frame",
            False,
            [],
            [(0, 0), (100, 0), (100, 100)],
        )

        self.assertTrue(ai_active)
        self.assertEqual(detections, [vessel])
        self.assertIn(("detect", "roi-frame"), calls)
        self.assertFalse(any(kind == "motion-filter" for kind, _value in calls))

    def test_road_remains_motion_gated_and_motion_filtered(self) -> None:
        detect_calls: list[object] = []
        motion_filter_calls: list[object] = []

        def detect_vehicles(_model: object, frame: object) -> list[dict[str, object]]:
            detect_calls.append(frame)
            return [{"track_id": 4, "class_name": "car", "bbox_xyxy": [1, 1, 10, 10]}]

        def filter_detections_by_motion(detections: object, boxes: object) -> object:
            motion_filter_calls.append(boxes)
            return detections

        ns = load_nodes(
            {"select_profile_detections"},
            {
                "detect_vehicles": detect_vehicles,
                "filter_detections_by_motion": filter_detections_by_motion,
                "filter_detections_by_roi": lambda detections, _points: detections,
            },
        )
        profile = SimpleNamespace(name="road-v1", domain="road")

        ai_active, detections = ns["select_profile_detections"](
            profile,
            object(),
            "roi-frame",
            False,
            [],
            [],
        )
        self.assertFalse(ai_active)
        self.assertEqual(detections, [])
        self.assertEqual(detect_calls, [])

        ai_active, detections = ns["select_profile_detections"](
            profile,
            object(),
            "roi-frame",
            True,
            [(1, 1, 5, 5)],
            [],
        )
        self.assertTrue(ai_active)
        self.assertEqual(len(detections), 1)
        self.assertEqual(detect_calls, ["roi-frame"])
        self.assertEqual(motion_filter_calls, [[(1, 1, 5, 5)]])

    def test_water_event_is_once_per_tracked_vessel_without_speed_requirement(self) -> None:
        track_states: dict[int, dict[str, object]] = {}

        def track_event_posted(track_id: int | None) -> bool:
            if track_id is None:
                return False
            return bool(track_states.get(int(track_id), {}).get("event_posted"))

        def mark_track_event_posted(track_id: int | None) -> None:
            if track_id is not None:
                track_states.setdefault(int(track_id), {})["event_posted"] = True

        ns = load_nodes(
            {"water_event_candidates"},
            {"track_event_posted": track_event_posted},
        )
        profile = SimpleNamespace(name="water-v1", domain="water")
        vessel = {
            "track_id": 21,
            "class_name": "vessel",
            "speed_ready": False,
            "speed_kmh": None,
            "_speed_info": {"speed_px_s": None},
            "_line_speed_info": {"speed_ready": False},
        }

        first = ns["water_event_candidates"](profile, [vessel])
        self.assertEqual(first, [vessel])
        mark_track_event_posted(21)
        second = ns["water_event_candidates"](profile, [vessel])
        self.assertEqual(second, [])

    def test_water_event_candidates_require_a_bytetrack_id(self) -> None:
        ns = load_nodes(
            {"water_event_candidates"},
            {"track_event_posted": lambda _track_id: False},
        )
        profile = SimpleNamespace(name="water-v1", domain="water")
        self.assertEqual(
            ns["water_event_candidates"](
                profile,
                [{"track_id": None, "class_name": "vessel", "speed_ready": False}],
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
