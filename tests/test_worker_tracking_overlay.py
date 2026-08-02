from __future__ import annotations

import ast
import copy
import time as real_time
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "worker/hls_motion_yolo_worker_events.py"


def load_functions(names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"), filename=str(SOURCE))
    selected = []
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            selected.append(copy.deepcopy(node))
            found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing worker functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


class FakeTime:
    current = 0.0

    @classmethod
    def time(cls) -> float:
        return cls.current


class Scalar:
    def __init__(self, value: float):
        self.value = value

    def item(self) -> float:
        return self.value


class XYXY:
    def __init__(self, values: list[float]):
        self.values = values

    def __getitem__(self, _index: int) -> "XYXY":
        return self

    def tolist(self) -> list[float]:
        return list(self.values)


class FakeBox:
    def __init__(self):
        self.cls = [Scalar(2)]
        self.conf = [Scalar(0.91)]
        self.xyxy = XYXY([10.2, 20.4, 40.6, 60.8])


class FakeBoxes(list):
    def __init__(self):
        super().__init__([FakeBox()])
        self.id = [Scalar(17)]


class FakeResult:
    names = {2: "car"}
    boxes = FakeBoxes()


class FakeModel:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def track(self, _frame: object, **kwargs: Any) -> list[FakeResult]:
        self.calls.append(kwargs)
        return [FakeResult()]


class WorkerTrackingOverlayTests(unittest.TestCase):
    def test_bytetrack_persistent_id_is_attached_to_detection(self) -> None:
        ns: dict[str, Any] = {
            "env_float": lambda name, default: default,
            "env_int": lambda name, default: default,
            "env_str": lambda name, default="": default,
            "VEHICLE_CLASSES": {"car", "truck", "bus", "motorcycle", "bicycle"},
        }
        load_functions({"detect_vehicles"}, ns)

        model = FakeModel()
        detections = ns["detect_vehicles"](model, object())

        self.assertEqual(len(model.cals, 1)
        self.assertTrue(model.calls[0]["persist"])
        self.assertEqual(model.calls[0]["tracker"], "bytetrack.yaml")
        self.assertEqual(detections[0]["track_id"], 17)
        self.assertEqual(detections[0]["bbox_xyxy"], [10, 20, 41, 61])

    def test_two_tracks_require_three_samples_and_keep_independent_state(self) -> None:
        FakeTime.current = 0.0
        ns: dict[str, Any] = {
            "time": FakeTime,
            "_track_states": {},
            "_speed_track": {},
            "_line_speed_state": {},
            "fetch_speed_lines_config": lambda: {
                "enabled": True,
                "distance_m": 100.0,
                "line_a": [(0, -5), (0, 5)],
                "line_b": [(10, -5), (10, 5)],
            },
            "env_float": lambda name, default: default,
        }
        load_functions(
            {"detection_center_px", "update_speed_estimate", "update_speed_lines_estimate"},
            ns,
        )

        track_a = {"track_id": 7, "bbox_xyxy": [-1, -1, 1, 1], "class_name": "car"}
        track_b = {"track_id": 12, "bbox_xxy": [4, -1, 6, 1], "class_name": "truck"}
        ns["update_speed_estimate"](track_a)
        ns["update_speed_lines_estimate"](track_a)
        ns["update_speed_estimate"](track_b)
        ns["update_speed_lines_estimate"](track_b)

        result_a = result_b = None
        for second in (1.0, 2.0, 3.0):
            FakeTime.current = second
            track_a = {
                "track_id": 7,
                "bbox_xxy": [second - 1, -1, second + 1, 1],
                "class_name": "car",
            }
            track_b = {
                "track_id": 12,
                "bbox_xxy": [4 + second * 2 - 1, -1, 4 + second * 2 + 1, 1],
                "class_name": "truck",
            }
            ns["update_speed_estimate"](track_a)
            result_a = ns["update_speed_lines_estimate"](track_a)
            ns["update_speed_estimate"](track_b)
            result_b = ns["update_speed_lines_estimate"](track_b)
            if second < 3.0:
                self.assertFalse(result_a["speed_ready"])
                self.assertFalse(result_b["speed_ready"])

        self.assertEqual(result_a["speed_kmh"], 36.0)
        self.assertEqual(result_b["speed_kmh"], 72.0)
        self.assertEqual(result_a["speed_sample_count"], 3)
        self.assertEqual(result_b["speed_sample_count"], 3)
        self.assertEqual(set(ns["_track_states"]), {7, 12})

    def test_confirmed_speed_is_held_across_one_invalid_frame(self) -> None:
        FakeTime.current = 0.0
        ns: dict[str, Any] = {
            "time": FakeTime,
            "_track_states": {},
            "_line_speed_state": {},
            "fetch_speed_lines_config": lambda: {
                "enabled": True,
                "distance_m": 100.0,
                "line_a": [(0, -5), (0, 5)],
                "line_b": [(10, -5), (10, 5)],
            },
            "env_float": lambda name, default: default,
        }
        load_functions({"detection_center_px", "update_speed_lines_estimate"}, ns)

        ns["update_speed_lines_estimate"](
            {"track_id": 9, "bbox_xyxy": [-1, -1, 1, 1], "class_name": "car"}
        )
        ready = None
        for second in (1.0, 2.0, 3.0):
            FakeTime.current = second
            ready = ns["update_speed_lines_estimate"]({
                "track_id": 9,
                "bbox_xyxy": [second - 1, -1, second + 1, 1],
                "class_name": "car",
            })

        self.assertEqual(ready["speed_kmh"], 36.0)
        self.assertTrue(ready["speed_ready"])

        FakeTime.current = 3.2
        held = ns["update_speed_lines_estimate"]({
            "track_id": 9,
            "bbox_xyxy": [2, -1, 4, 1],
            "class_name": "car",
        })

        self.assertEqual(held["speed_kmh"], 36.0)
        self.assertTrue(held["speed_ready"])
        self.assertEqual(held["speed_source"], "detection_first_calibrated_held")

    def test_overlay_label_contains_id_and_speed_or_pending_marker(self) -> None:
        ns = load_functions({"format_detection_label"}, {})

        ready = ns["format_detection_label"]({
            "track_id": 23,
            "class_name": "car",
            "confidence": 0.874,
            "speed_kmh": 31.4,
        })
        pending = ns["format_detection_label"]({
            "track_id": 24,
            "class_name": "truck",
            "confidence": 0.8,
            "speed_kmh": None,
        })

        self.assertEqual(ready, "ID 23 | car 0.87 | 31.4 km/h")
        self.assertEqual(pending, "ID 24 | truck 0.80 | speed: --")

    def test_overlay_label_opacity_defaults_and_clamps(self) -> None:
        configured = {"value": None}

        def env_float(_name: str, default: float) -> float:
            value = configured["value"]
            return default if value is None else float(value)

        ns = load_functions({"overlay_label_opacity"}, {"env_float": env_float})

        self.assertEqual(ns["overlay_label_opacity"](), 0.38)
        configured["value"] = -1
        self.assertEqual(ns["overlay_label_opacity"](), 0.15)
        configured["value"] = 2
        self.assertEqual(ns["overlay_label_opacity"](), 0.85)

    def test_overlay_uses_translucent_blending_not_opaque_label_fill(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        start = source.index("def draw_overlay(")
        end = source.index("def post_state(", start)
        draw_source = source[start:end]

        self.assertIn("label_layer = out.copy()", draw_source)
        self.assertIn("cv2.addWeighted(", draw_source)
        self.assertIn("opacity = overlay_label_opacity()", draw_source)
        self.assertNotIn(
            "(label_x, max(0, label_y - text_height - 7))",
            draw_source,
        )

    def test_event_uses_displayed_speed_and_skips_px_fallback_when_lines_enabled(self) -> None:
        ns: dict[str, Any] = {
            "fetch_speed_config": lambda: {"enabled": True, "kmh_per_px_s": 99.0},
            "time": real_time,
            "uuid": uuid,
            "now_iso": lambda: datetime.now(timezone.utc).isoformat(),
            "env_str": lambda name, default="": default,
        }
        load_functions({"convert_px_s_to_kmh", "build_event"}, ns)

        event = ns["build_event"](
            {
                "track_id": 31,
                "class_name": "car",
                "confidence": 0.9,
                "bbox_xyxy": [1, 2, 3, 4],
                "speed_kmh": 24.6,
                "speed_source": "detection_first_calibrated",
            },
            100,
            {"center_x": 2, "center_y": 4, "speed_px_s": 20},
            {"speed_lines_enabled": True, "speed_kmh": None},
        )

        self.assertEqual(event["speed_kmh"], 24.6)
        self.assertEqual(event["speed_source"], "detection_first_calibrated")

    def test_track_event_is_marked_once_until_state_is_pruned(self) -> None:
        states = {44: {"last_seen": 10.0, "event_posted": False}}
        ns: dict[str, Any] = {"_track_states": states}
        load_functions({"track_event_posted", "mark_track_event_posted"}, ns)

        self.assertFalse(ns["track_event_posted"](44))
        ns["mark_track_event_posted"](44)
        self.assertTrue(ns["track_event_posted"](44))
        self.assertFalse(ns["track_event_posted"](None))

    def test_stale_track_state_is_pruned_by_max_gap(self) -> None:
        states = {
            7: {"last_seen": 7.9},
            12: {"last_seen": 8.1},
        }
        ns: dict[str, Any] = {
            "_track_states": states,
            "time": FakeTime,
            "env_float": lambda name, default: 2.0 if name == "DETECTION_TRACK_MAX_GAP_SEC" else default,
        }
        load_functions({"prune_track_states"}, ns)

        removed = ns["prune_track_states"](now=10.0)

        self.assertEqual(removed, [7])
        self.assertEqual(set(states), {12})

    def test_event_metadata_contains_track_id(self) -> None:
        ns: dict[str, Any] = {
            "fetch_speed_config": lambda: {"enabled": True, "kmh_per_px_s": 0.5},
            "time": real_time,
            "uuid": uuid,
            "now_iso": lambda: datetime.now(timezone.utc).isoformat(),
            "env_str": lambda name, default="": default,
        }
        load_functions({"convert_px_s_to_kmh", "build_event"}, ns)

        event = ns["build_event"](
            {
                "track_id": 31,
                "class_name": "car",
                "confidence": 0.9,
                "bbox_xyxy": [1, 2, 3, 4],
            },
            100,
            {"center_x": 2, "center_y": 4, "speed_px_s": 20},
            {},
        )

        self.assertEqual(event["track_id"], 31)
        self.assertEqual(event["speed_kmh"], 10.0)

    def test_source_reports_unique_visible_track_count(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        self.assertEqual(source.count("def detection_center_px"), 1)
        self.assertIn('active_track_ids.add(int(track_id))', source)
        self.assertIn('"tracks": track_count', source)
        self.assertIn('det["speed_kmh"] = speed_kmh', source)
        self.assertIn('DETECTION_SPEED_MIN_SAMPLES", 3', source)
        self.assertIn('DETECTION_SPEED_DISPLAY_HOLD_SEC", 2.0', source)
        self.assertIn('event_already_posted = track_event_posted(track_id)', source)
        self.assertIn('if speed_kmh is None and not speed_lines_enabled:', source)


if __name__ == "__main__":
    unittest.main()
