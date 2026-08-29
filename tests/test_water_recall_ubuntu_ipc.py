from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
ENTRYPOINT = WORKER / "ubuntu_worker_entrypoint.py"
AI_CHILD = WORKER / "ubuntu_ai_inference_worker.py"


class _Scalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class _Vector:
    def __init__(self, values):
        self.values = list(values)

    def tolist(self):
        return list(self.values)


class _Box:
    def __init__(self, cls_id: int, confidence: float, xyxy):
        self.cls = [_Scalar(cls_id)]
        self.conf = [_Scalar(confidence)]
        self.xyxy = [_Vector(xyxy)]


class _TrackIds:
    def __init__(self, values):
        self.values = [_Scalar(value) for value in values]

    def __getitem__(self, index):
        return self.values[index]


class _Boxes(list):
    pass


class _Result:
    def __init__(self):
        boxes = _Boxes(
            [
                _Box(0, 0.81234, [10.2, 20.3, 110.4, 80.8]),
                _Box(1, 0.45678, [120.0, 30.0, 180.0, 90.0]),
            ]
        )
        boxes.id = _TrackIds([41, 42])
        self.boxes = boxes
        self.names = {0: "boat", 1: "car"}


def _load_child_module():
    sys.path.insert(0, str(WORKER))
    try:
        spec = importlib.util.spec_from_file_location("water_recall_ai_child", AI_CHILD)
        if spec is None or spec.loader is None:
            raise RuntimeError("unable to load ubuntu AI child")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        try:
            sys.path.remove(str(WORKER))
        except ValueError:
            pass


class WaterRecallUbuntuIpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.child = _load_child_module()

    def test_child_side_channel_preserves_accepted_detection_semantics(self) -> None:
        results = [_Result()]
        legacy = self.child.serialize_detections(results, "water-v1")
        accepted, diagnostics = self.child.serialize_detection_batch(results, "water-v1")

        self.assertEqual(accepted, legacy)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(
            accepted[0],
            {
                "track_id": 41,
                "analytics_profile": "water-v1",
                "domain": "water",
                "object_type": "vessel",
                "model_class": "boat",
                "class_name": "vessel",
                "confidence": 0.81234,
                "bbox_xyxy": [10, 20, 110, 81],
            },
        )

        self.assertEqual(len(diagnostics), 2)
        accepted_diag, rejected_diag = diagnostics
        self.assertTrue(accepted_diag["class_mapping_accepted"])
        self.assertEqual(accepted_diag["semantic_class"], "vessel")
        self.assertEqual(accepted_diag["track_id"], 41)
        self.assertEqual(accepted_diag["bbox_width_px"], 100)
        self.assertEqual(accepted_diag["bbox_height_px"], 61)
        self.assertEqual(accepted_diag["bbox_area_px"], 6100)

        self.assertEqual(rejected_diag["model_class"], "car")
        self.assertFalse(rejected_diag["class_mapping_accepted"])
        self.assertIsNone(rejected_diag["semantic_class"])
        self.assertEqual(rejected_diag["track_id"], 42)
        self.assertNotIn(rejected_diag, accepted)

    def test_parent_supervisor_accepts_optional_diagnostic_sink(self) -> None:
        source = ENTRYPOINT.read_text(encoding="utf-8")
        self.assertIn("def supervised_detect_vehicles(_model, frame, diagnostics=None):", source)
        self.assertIn("return _supervisor.detect(frame, diagnostics=diagnostics)", source)
        self.assertIn("def detect(self, frame: np.ndarray, diagnostics=None)", source)
        self.assertIn("detections, diagnostic_records = self._roundtrip(frame, timeout_sec)", source)
        self.assertIn("diagnostics.extend(diagnostic_records)", source)
        self.assertIn('payload.get("diagnostics", [])', source)
        self.assertIn("4 * 1024 * 1024", source)

    def test_ipc_diagnostics_do_not_add_an_inference_pass_or_secret_surface(self) -> None:
        child_source = AI_CHILD.read_text(encoding="utf-8")
        self.assertEqual(child_source.count("model.track("), 1)
        self.assertIn('"detections": detections', child_source)
        self.assertIn('"diagnostics": diagnostics', child_source)
        self.assertNotIn("HLS_URL", child_source)
        self.assertNotIn("SEA_SPEED_API_TOKEN", child_source)
        self.assertNotIn("SEA_SPEED_API_URL", child_source)

    def test_two_argument_calls_remain_backward_compatible_for_road(self) -> None:
        source = ENTRYPOINT.read_text(encoding="utf-8")
        self.assertIn("diagnostics=None", source)
        self.assertIn("worker.detect_vehicles = supervised_detect_vehicles", source)


if __name__ == "__main__":
    unittest.main()
