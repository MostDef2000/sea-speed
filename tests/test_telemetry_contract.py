from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    def test_installed_commit_and_calibration_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = Path(temp_dir)
            (install_dir / ".sea-speed-worker-version").write_text("a" * 40 + "\n", encoding="utf-8")
            previous = os.environ.pop("SEA_SPEED_WORKER_SOURCE_COMMIT", None)
            try:
                self.assertEqual(RUNTIME.installed_source_commit(install_dir), "a" * 40)
            finally:
                if previous is not None:
                    os.environ["SEA_SPEED_WORKER_SOURCE_COMMIT"] = previous

        first = RUNTIME.calibration_version(
            {"enabled": True, "kmh_per_px_s": 0.4},
            {"enabled": True, "distance_m": 57, "line_a": [(0, 0), (0, 1)], "line_b": [(2, 0), (2, 1)]},
        )
        second = RUNTIME.calibration_version(
            {"kmh_per_px_s": 0.4, "enabled": True},
            {"line_b": [(2, 0), (2, 1)], "line_a": [(0, 0), (0, 1)], "distance_m": 57, "enabled": True},
        )
        self.assertEqual(first, second)
        self.assertRegex(first, r"^sha256:[0-9a-f]{16}$")

    def test_state_enrichment_and_validation(self) -> None:
        state = RUNTIME.enrich_state(
            {"camera_id": "cam1", "frame_no": 12, "worker_online": True, "updated_at": "2026-08-02T00:00:00+00:00"},
            "b" * 40,
        )
        self.assertEqual(state["state_schema"], "sea_speed_worker_state_v1")
        self.assertEqual(VALIDATOR.validate_payload(state), "state")

    def test_event_enrichment_and_validation(self) -> None:
        event = RUNTIME.enrich_event(
            {
                "event_id": "event-1",
                "created_at": "2026-08-02T00:00:00+00:00",
                "camera_id": "cam1",
                "class_name": "car",
                "confidence": 0.9,
                "speed_kmh": 42.0,
            },
            "c" * 40,
            "sha256:" + "d" * 16,
        )
        self.assertEqual(event["event_schema"], "sea_speed_vehicle_event_v1")
        self.assertEqual(VALIDATOR.validate_payload(event), "event")

    def test_invalid_event_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            VALIDATOR.validate_payload({"event_schema": "sea_speed_vehicle_event_v1"}, "event")


if __name__ == "__main__":
    unittest.main()
