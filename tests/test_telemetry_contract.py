from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "worker"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNTIME = load_module("worker_runtime_identity", ROOT / "worker/hls_motion_yolo_runtime.py")
VALIDATOR = load_module("telemetry_validator", ROOT / "scripts/ci/validate_telemetry.py")


class TelemetryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_profile = os.environ.pop("ANALYTICS_PROFILE", None)
        self.old_camera = os.environ.pop("CAMERA_ID", None)

    def tearDown(self) -> None:
        os.environ.pop("ANALYTICS_PROFILE", None)
        os.environ.pop("CAMERA_ID", None)
        if self.old_profile is not None: os.environ["ANALYTICS_PROFILE"] = self.old_profile
        if self.old_camera is not None: os.environ["CAMERA_ID"] = self.old_camera

    def test_installed_commit_and_calibration_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = Path(temp_dir)
            (install_dir / ".sea-speed-worker-version").write_text("a" * 40 + "\n", encoding="utf-8")
            self.assertEqual(RUNTIME.installed_source_commit(install_dir), "a" * 40)
        first = RUNTIME.calibration_version({"enabled": True, "kmh_per_px_s": 0.4}, {"enabled": False})
        second = RUNTIME.calibration_version({"kmh_per_px_s": 0.4, "enabled": True}, {"enabled": False})
        self.assertEqual(first, second)
        self.assertRegex(first, r"^sha256:[0-9a-f]{16}$")

    def test_legacy_unprofiled_state_and_event_remain_valid(self) -> None:
        state = RUNTIME.enrich_state({"camera_id": "cam1", "frame_no": 12, "worker_online": True, "updated_at": "2026-08-02T00:00:00+00:00"}, "b" * 40)
        event = RUNTIME.enrich_event({"event_id": "event-1", "created_at": "2026-08-02T00:00:00+00:00", "camera_id": "cam1", "class_name": "car", "confidence": 0.9}, "c" * 40, "sha256:" + "d" * 16)
        self.assertNotIn("analytics_profile", state)
        self.assertNotIn("analytics_profile", event)
        self.assertEqual(VALIDATOR.validate_payload(state), "state")
        self.assertEqual(VALIDATOR.validate_payload(event), "event")

    def test_water_profile_semantics_validate(self) -> None:
        os.environ["ANALYTICS_PROFILE"] = "water-v1"
        os.environ["CAMERA_ID"] = "cam1"
        event = RUNTIME.enrich_event({
            "event_id": "water-1", "created_at": "2026-08-02T00:00:00+00:00", "camera_id": "cam1",
            "class_name": "vessel", "object_type": "vessel", "model_class": "boat", "confidence": 0.9,
        }, "c" * 40, "sha256:" + "d" * 16)
        self.assertEqual(event["analytics_profile"], "water-v1")
        self.assertEqual(event["domain"], "water")
        self.assertEqual(VALIDATOR.validate_payload(event), "event")

    def test_road_profile_semantics_validate_and_cross_domain_fails(self) -> None:
        payload = {
            "event_schema": "sea_speed_vehicle_event_v1", "telemetry_schema": "sea_speed_telemetry_v1",
            "worker_source_commit": "c" * 40, "calibration_version": None, "event_id": "road-1",
            "created_at": "x", "camera_id": "road1", "class_name": "car", "confidence": 0.8,
            "analytics_profile": "road-v1", "domain": "road", "object_type": "car", "model_class": "car",
        }
        self.assertEqual(VALIDATOR.validate_payload(payload), "event")
        payload["model_class"] = "boat"
        with self.assertRaises(ValueError):
            VALIDATOR.validate_payload(payload, "event")


if __name__ == "__main__":
    unittest.main()
