from __future__ import annotations

import time as real_time
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

try:
    from tests.support import worker_source
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import worker_source


def load_functions(names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    # 398-wave-a: shared AST-slice+exec harness (was a private duplicate; now
    # tests/support/worker_source.py resolves the worker source by path so the
    # #397 decomposition can move functions between files).
    return worker_source.load_functions(names, namespace)


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
        # 398-wave-a: converted from source-text pin (was L77-82) — the event
        # cooldown contract must hold structurally inside the live main() flow:
        # the cooldown window is configurable, the cooldown gate compares
        # elapsed time against it, the px-speed fallback feeds the legacy gate,
        # and the legacy gate ORs in the calibrated speed.
        main_node = worker_source.function_node("main")
        cooldown_calls = worker_source.calls_with_constant_arg(main_node, "env_float", "EVENT_COOLDOWN_SEC")
        self.assertEqual(len(cooldown_calls), 1, "main() must read the event cooldown exactly once")
        self.assertEqual(worker_source.dump(cooldown_calls[0].args[1]), worker_source.expr_dump("12.0"), "EVENT_COOLDOWN_SEC default must stay 12.0s")
        cooldown_assignments = worker_source.find_assignments(main_node, "cooldown_ok")
        self.assertEqual(len(cooldown_assignments), 1, "cooldown_ok must be computed exactly once in main()")
        self.assertEqual(
            worker_source.dump(cooldown_assignments[0].value),
            worker_source.dump(worker_source._snippet_expr("now - last_event_post >= event_cooldown")),
        )
        px_assignments = worker_source.find_assignments(main_node, "has_px_speed")
        self.assertEqual(len(px_assignments), 1, "the px-speed fallback must be computed exactly once in main()")
        self.assertEqual(worker_source.dump(px_assignments[0].value), worker_source.dump(worker_source._snippet_expr("speed_px_s is not None")))
        legacy_assignments = worker_source.find_assignments(main_node, "legacy_event_ready")
        self.assertEqual(len(legacy_assignments), 1, "legacy_event_ready must be computed exactly once in main()")
        self.assertEqual(
            worker_source.dump(legacy_assignments[0].value),
            worker_source.dump(worker_source._snippet_expr("speed_ready or (has_px_speed and speed_px_s >= min_speed and cooldown_ok)")),
        )

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

    def test_no_profile_environment_keeps_portable_legacy_defaults(self) -> None:
        # 398-wave-a: converted from source-text pin (was L95-102) — without a
        # configured analytics profile the worker must keep the portable legacy
        # defaults (legacy yolo11s model, bytetrack tracker, cam1_road_test
        # camera id, 0.25 confidence) as structural fallbacks.
        main_node = worker_source.function_node("main")
        profile_name_assignments = worker_source.find_assignments(main_node, "profile_name")
        self.assertTrue(
            any(worker_source.dump(a.value) == worker_source.expr_dump('env_str("ANALYTICS_PROFILE", "").strip()') for a in profile_name_assignments),
            "main() must read ANALYTICS_PROFILE with an empty no-profile default",
        )
        profile_assignments = worker_source.find_assignments(main_node, "profile")
        self.assertTrue(
            any(worker_source.dump(a.value) == worker_source.expr_dump("get_profile(profile_name) if profile_name else None") for a in profile_assignments),
            "main() must fall back to profile=None when no profile is configured",
        )
        model_assignments = worker_source.find_assignments(main_node, "model_name")
        self.assertTrue(
            any(worker_source.dump(a.value) == worker_source.expr_dump('env_str("MODEL_NAME", profile.model_name if profile else "yolo11s.pt")') for a in model_assignments),
            "no-profile model default must stay yolo11s.pt",
        )
        tracker_assignments = worker_source.find_assignments(main_node, "tracker_name")
        self.assertTrue(
            any(worker_source.contains_expr(a.value, 'profile.tracker if profile else "bytetrack.yaml"') for a in tracker_assignments),
            "no-profile tracker default must stay bytetrack.yaml",
        )
        camera_assignments = worker_source.contains_expr(
            main_node,
            'profile.default_camera_id if profile else "cam1_road_test"',
        )
        self.assertTrue(
            camera_assignments,
            "no-profile camera default must stay cam1_road_test",
        )
        # The whole-file text pin for confidence_default matched the
        # no-profile branch of detect_vehicles() (the model-selection path);
        # the AST equivalent scopes to that function instead of the file.
        detect_node = worker_source.function_node("detect_vehicles")
        confidence_assignments = worker_source.find_assignments(detect_node, "confidence_default")
        self.assertTrue(
            any(worker_source.dump(a.value) == worker_source.expr_dump("0.25") for a in confidence_assignments),
            "no-profile detector confidence default must stay 0.25",
        )


if __name__ == "__main__":
    unittest.main()
