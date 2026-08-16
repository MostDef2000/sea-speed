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


class WorkerContractTests(unittest.TestCase):
    def test_line_geometry_and_deadzone(self) -> None:
        ns = load_functions({"side_of_line", "sign_with_deadzone", "crossed_line"}, {})
        line = [(0, 0), (10, 0)]
        self.assertGreater(ns["side_of_line"]((5, 2), line), 0)
        self.assertLess(ns["side_of_line"]((5, -2), line), 0)
        self.assertEqual(ns["sign_with_deadzone"](0.5), 0)
        self.assertTrue(ns["crossed_line"](-2, 2))
        self.assertFalse(ns["crossed_line"](-0.5, 2))

    def test_detection_first_calibration_produces_expected_speed(self) -> None:
        FakeTime.current = 0.0
        ns: dict[str, Any] = {"time": FakeTime, "_line_speed_state": {}, "fetch_speed_lines_config": lambda: {"enabled": True, "distance_m": 100.0, "line_a": [(0, -5), (0, 5)], "line_b": [(10, -5), (10, 5)]}, "env_float": lambda name, default: default}
        load_functions({"detection_center_px", "update_speed_lines_estimate"}, ns)
        first = {"bbox_xyxy": [-1, -1, 1, 1], "class_name": "car"}
        second = {"bbox_xyxy": [0, -1, 2, 1], "class_name": "car"}
        self.assertFalse(ns["update_speed_lines_estimate"](first)["speed_ready"])
        FakeTime.current = 1.0
        result = ns["update_speed_lines_estimate"](second)
        self.assertTrue(result["speed_ready"])
        self.assertEqual(result["speed_kmh"], 36.0)
        self.assertEqual(result["speed_source"], "detection_first_calibrated")

    def test_px_factor_conversion_and_event_identity(self) -> None:
        ns: dict[str, Any] = {"fetch_speed_config": lambda: {"enabled": True, "kmh_per_px_s": 0.5}, "time": real_time, "uuid": uuid, "now_iso": lambda: datetime.now(timezone.utc).isoformat(), "env_str": lambda name, default="": default}
        load_functions({"convert_px_s_to_kmh", "build_event"}, ns)
        self.assertEqual(ns["convert_px_s_to_kmh"](20), 10.0)
        det = {"class_name": "car", "confidence": 0.9, "bbox_xyxy": [1, 2, 3, 4]}
        speed = {"center_x": 2, "center_y": 4, "speed_px_s": 20}
        first = ns["build_event"](det, 100, speed, {})
        second = ns["build_event"](det, 100, speed, {})
        self.assertNotEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["speed_kmh"], 10.0)
        self.assertEqual(first["speed_source"], "px_factor")
        self.assertEqual(first["model_name"], "yolo11s.pt")

    def test_event_cooldown_contract_is_present(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        self.assertIn('EVENT_COOLDOWN_SEC', source)
        self.assertIn('cooldown_ok = now - last_event_post >= event_cooldown', source)
        self.assertIn('has_px_speed', source)
        self.assertIn('speed_ready or (', source)

    def test_profiled_event_preserves_domain_semantics(self) -> None:
        ns: dict[str, Any] = {"fetch_speed_config": lambda: {"enabled": False, "kmh_per_px_s": 0.0}, "time": real_time, "uuid": uuid, "now_iso": lambda: datetime.now(timezone.utc).isoformat(), "env_str": lambda name, default="": default}
        load_functions({"convert_px_s_to_kmh", "build_event"}, ns)
        det = {"class_name":"vessel","object_type":"vessel","model_class":"boat","analytics_profile":"water-v1","domain":"water","confidence":0.91,"bbox_xyxy":[1,2,3,4]}
        event = ns["build_event"](det, 5, {}, {})
        self.assertEqual(event["analytics_profile"], "water-v1")
        self.assertEqual(event["domain"], "water")
        self.assertEqual(event["class_name"], "vessel")
        self.assertEqual(event["model_class"], "boat")
        self.assertEqual(event["model_name"], "yolo11s.pt")

    def test_no_profile_environment_keeps_legacy_windows_defaults(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        self.assertIn('profile_name = env_str("ANALYTICS_PROFILE", "").strip()', source)
        self.assertIn('confidence_default = 0.25', source)
        self.assertIn('profile.model_name if profile_is_explicit() else "yolo11s.pt"', source)


if __name__ == "__main__":
    unittest.main()
