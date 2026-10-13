from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

import analytics_profiles as profiles
from water_passage import WaterPassageEngine, build_two_gate_estimator

try:
    from tests.support import worker_source
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import worker_source


class FrameQualityTests(unittest.TestCase):
    def test_water_and_road_frame_defaults_are_hd(self) -> None:
        water = profiles.get_profile("water-v1")
        road = profiles.get_profile("road-v1")
        self.assertEqual(water.frame_width, 1920)
        self.assertEqual(water.frame_height, 1080)
        self.assertEqual(road.frame_width, 1920)
        self.assertEqual(road.frame_height, 1080)

    def test_profile_defaults_includes_frame_size(self) -> None:
        defaults = profiles.profile_defaults("water-v1")
        self.assertEqual(defaults["FRAME_WIDTH"], 1920)
        self.assertEqual(defaults["FRAME_HEIGHT"], 1080)
        defaults_road = profiles.profile_defaults("road-v1")
        self.assertEqual(defaults_road["FRAME_WIDTH"], 1920)
        self.assertEqual(defaults_road["FRAME_HEIGHT"], 1080)

    def test_worker_env_example_is_hd(self) -> None:
        text = (ROOT / "deploy/worker/ubuntu/worker.env.example").read_text(encoding="utf-8")
        self.assertIn("FRAME_WIDTH=1920", text)
        self.assertIn("FRAME_HEIGHT=1080", text)

    def test_hls_worker_uses_profile_frame_size_by_default(self) -> None:
        # 398-wave-a: converted from source-text pin (was L38-43) — the
        # worker must resolve its frame size through the analytics profile:
        # _resolve_frame_size and crop_sharpness stay defined and
        # _resolve_frame_size consults get_profile; the retired fixed
        # 704-px default must stay removed (any env_int FRAME_WIDTH 704
        # read, not just the historical spelling).
        worker_source.module_trees()  # loads live worker sources (fail-closed on missing file)
        worker_source.function_nodes({"_resolve_frame_size", "crop_sharpness"})  # raises if either disappears
        resolve_node = worker_source.function_node("_resolve_frame_size")
        self.assertTrue(
            worker_source.calls_named(resolve_node, "get_profile"),
            "_resolve_frame_size must resolve the profile-driven frame size",
        )
        for tree in worker_source.module_trees():
            for call in worker_source.calls_named(tree, "env_int"):
                args = call.args
                if (
                    len(args) >= 2
                    and isinstance(args[0], ast.Constant)
                    and args[0].value == "FRAME_WIDTH"
                    and isinstance(args[1], ast.Constant)
                    and args[1].value == 704
                ):
                    self.fail("retired fixed 704-px FRAME_WIDTH default re-introduced")

    def test_ubuntu_worker_entrypoint_uses_profile_frame_size(self) -> None:
        text = (ROOT / "worker/ubuntu_worker_entrypoint.py").read_text(encoding="utf-8")
        self.assertIn("profile.frame_width", text)
        self.assertIn("profile.frame_height", text)

    def test_passage_sharpness_aware_best_frame(self) -> None:
        engine = WaterPassageEngine(
            lambda: build_two_gate_estimator({"line_a": [[0, 0], [0, 10]], "line_b": [[10, 0], [10, 10]], "distance_m": 10, "enabled": False}),
            snapshot_improvement_ratio=1.15,
        )
        # First detection with high sharpness becomes best
        first = {"track_id": 1, "bbox_xyxy": [0, 0, 100, 50], "confidence": 0.8, "class_name": "vessel", "_sharpness": 200.0}
        updates = engine.update([first], ts=1000.0)
        self.assertEqual(len(updates), 1)
        self.assertTrue(updates[0]["snapshot_candidate"])
        # Second detection with slightly larger area but blurry should NOT replace sharp best
        second = {"track_id": 1, "bbox_xyxy": [0, 0, 110, 55], "confidence": 0.8, "class_name": "vessel", "_sharpness": 30.0}
        updates2 = engine.update([second], ts=1001.0)
        self.assertFalse(updates2[0]["snapshot_candidate"])
        # Without sharpness field, old behavior preserved (area-driven)
        engine2 = WaterPassageEngine(
            lambda: build_two_gate_estimator({"line_a": [[0, 0], [0, 10]], "line_b": [[10, 0], [10, 10]], "distance_m": 10, "enabled": False}),
            snapshot_improvement_ratio=1.15,
        )
        engine2.update([{"track_id": 2, "bbox_xyxy": [0, 0, 100, 50], "confidence": 0.8, "class_name": "vessel"}], ts=2000.0)
        bigger = {"track_id": 2, "bbox_xyxy": [0, 0, 120, 60], "confidence": 0.9, "class_name": "vessel"}
        upd = engine2.update([bigger], ts=2001.0)
        self.assertTrue(upd[0]["snapshot_candidate"])

    def test_crop_sharpness_helper_handles_empty(self) -> None:
        # 398-wave-a: converted from source-text pin (was L74-77) —
        # crop_sharpness must stay defined and compute Laplacian variance;
        # the behavioral empty-crop check (import-level) is kept.
        crop_node = worker_source.function_node("crop_sharpness")
        self.assertTrue(
            worker_source.method_calls(crop_node, "cv2", "Laplacian"),
            "crop_sharpness must measure Laplacian variance",
        )
        # Functional check via import when cv2 available; skip in env without cv2
        try:
            import sys

            sys.path.insert(0, str(ROOT / "worker"))
            import hls_motion_yolo_worker_events as worker_mod  # type: ignore

            self.assertEqual(worker_mod.crop_sharpness(None), 0.0)
        except ModuleNotFoundError:
            self.skipTest("cv2 not available in local env")

    def test_frame_quality_does_not_change_detector_params(self) -> None:
        water = profiles.get_profile("water-v1")
        self.assertEqual(water.image_size, 960)
        self.assertEqual(water.confidence, 0.10)
        road = profiles.get_profile("road-v1")
        self.assertEqual(road.image_size, 960)
        self.assertEqual(road.confidence, 0.15)


if __name__ == "__main__":
    unittest.main()
