from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "worker/ubuntu_worker_entrypoint.py"
SOURCE_SHA = "0123456789abcdef0123456789abcdef01234567"


class UbuntuWorkerRuntimeProvenanceTests(unittest.TestCase):
    def load_entrypoint(self):
        captured_state: list[tuple[dict[str, object], object]] = []
        captured_event: list[tuple[dict[str, object], object]] = []

        worker = types.ModuleType("hls_motion_yolo_worker_events")
        worker.start_media_reader = lambda av_module=None: None

        def post_state(metadata, overlay_path):
            captured_state.append((metadata, overlay_path))
            return "state-ok"

        def post_event(metadata, snapshot_path):
            captured_event.append((metadata, snapshot_path))
            return "event-ok"

        worker.post_state = post_state
        worker.post_event = post_event

        profiles = types.ModuleType("analytics_profiles")
        profiles.get_profile = lambda _name: types.SimpleNamespace(
            sample_fps=5.0,
            model_name="models/yolo26x.pt",
            tracker="bytetrack.yaml",
            image_size=960,
            confidence=0.15,
            name="road-v1",
        )

        numpy = types.ModuleType("numpy")

        module_name = "sea_speed_ubuntu_worker_entrypoint_provenance_test"
        spec = importlib.util.spec_from_file_location(module_name, ENTRYPOINT)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(
            sys.modules,
            {
                "analytics_profiles": profiles,
                "hls_motion_yolo_worker_events": worker,
                "numpy": numpy,
            },
        ):
            spec.loader.exec_module(module)
        return module, captured_state, captured_event

    def test_exact_source_commit_is_injected_into_state_and_event_payloads(self) -> None:
        with mock.patch.dict(os.environ, {"SEA_SPEED_SOURCE_COMMIT": SOURCE_SHA}, clear=False):
            module, captured_state, captured_event = self.load_entrypoint()
            state_input = {"camera_id": "road1", "worker_source_commit": "f" * 40}
            event_input = {"event_id": "evt-1"}

            self.assertEqual(module.post_state(state_input, "overlay.jpg"), "state-ok")
            self.assertEqual(module.post_event(event_input, "event.jpg"), "event-ok")

        self.assertEqual(captured_state[0][0]["worker_source_commit"], SOURCE_SHA)
        self.assertEqual(captured_event[0][0]["worker_source_commit"], SOURCE_SHA)
        self.assertEqual(state_input["worker_source_commit"], "f" * 40)
        self.assertNotIn("worker_source_commit", event_input)

    def test_environment_identity_overrides_payload_identity(self) -> None:
        with mock.patch.dict(os.environ, {"SEA_SPEED_SOURCE_COMMIT": SOURCE_SHA}, clear=False):
            module, captured_state, captured_event = self.load_entrypoint()
            module.post_state({"worker_source_commit": "a" * 40}, "overlay.jpg")
            module.post_event({"worker_source_commit": "b" * 40}, "event.jpg")

        self.assertEqual(captured_state[0][0]["worker_source_commit"], SOURCE_SHA)
        self.assertEqual(captured_event[0][0]["worker_source_commit"], SOURCE_SHA)

    def test_missing_or_invalid_source_commit_fails_closed_before_post(self) -> None:
        bad_values = (None, "", "A" * 40, "a" * 39, "g" * 40, SOURCE_SHA + "0")
        for value in bad_values:
            with self.subTest(value=value):
                env = {} if value is None else {"SEA_SPEED_SOURCE_COMMIT": value}
                with mock.patch.dict(os.environ, env, clear=True):
                    module, captured_state, captured_event = self.load_entrypoint()
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "SEA_SPEED_SOURCE_COMMIT must be an exact lowercase 40-character Git SHA",
                    ):
                        module.post_state({"camera_id": "road1"}, "overlay.jpg")
                    with self.assertRaises(RuntimeError):
                        module.post_event({"event_id": "evt-1"}, "event.jpg")
                self.assertEqual(captured_state, [])
                self.assertEqual(captured_event, [])

    def test_provenance_injection_does_not_copy_protected_environment_values(self) -> None:
        protected = {
            "SEA_SPEED_SOURCE_COMMIT": SOURCE_SHA,
            "SEA_SPEED_API_TOKEN": "secret-token-value",
            "HLS_URL": "rtsp://user:password@private.invalid/live",
            "SEA_SPEED_API_URL": "http://10.0.0.1:18080/api/analytics/road1/state",
        }
        with mock.patch.dict(os.environ, protected, clear=True):
            module, captured_state, _captured_event = self.load_entrypoint()
            module.post_state({"camera_id": "road1"}, "overlay.jpg")

        payload = captured_state[0][0]
        self.assertEqual(payload, {"camera_id": "road1", "worker_source_commit": SOURCE_SHA})
        serialized = repr(payload)
        self.assertNotIn("secret-token-value", serialized)
        self.assertNotIn("password", serialized)
        self.assertNotIn("10.0.0.1", serialized)

    def test_entrypoint_validates_runtime_identity_before_starting_supervisor(self) -> None:
        source = ENTRYPOINT.read_text(encoding="utf-8")
        main_block = source[source.index('if __name__ == "__main__":'):]
        self.assertLess(
            main_block.index("runtime_source_commit()"),
            main_block.index("BoundedYoloSupervisor()"),
        )


if __name__ == "__main__":
    unittest.main()
