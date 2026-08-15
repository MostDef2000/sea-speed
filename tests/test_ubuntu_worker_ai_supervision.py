from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "worker/ubuntu_worker_entrypoint.py"
AI_CHILD = ROOT / "worker/ubuntu_ai_inference_worker.py"
RUNNER = ROOT / "deploy/worker/ubuntu/observed-worker-runner.py"
GATE = ROOT / "deploy/worker/ubuntu/verify-runtime-progression.py"
COMMIT = "b" * 40


class UbuntuWorkerAiSupervisionTests(unittest.TestCase):
    def test_python_syntax(self) -> None:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "py_compile",
                str(ENTRYPOINT),
                str(AI_CHILD),
                str(RUNNER),
                str(GATE),
            ],
            check=True,
        )

    def test_entrypoint_bounds_model_track_in_child_process(self) -> None:
        source = ENTRYPOINT.read_text(encoding="utf-8")
        child = AI_CHILD.read_text(encoding="utf-8")

        self.assertIn("class BoundedYoloSupervisor", source)
        self.assertIn("AI_INFERENCE_TIMEOUT_SEC", source)
        self.assertIn("AI_INFERENCE_BACKOFF_SEC", source)
        self.assertIn("AI_INFERENCE_STARTUP_TIMEOUT_SEC", source)
        self.assertIn('worker.env_str("YOLO_DEVICE", "0")', source)
        self.assertIn("select.select", source)
        self.assertIn("proc.kill()", source)
        self.assertIn("AI inference degraded", source)
        self.assertIn("AI inference self-test ok sequence=", source)
        self.assertIn('self._spawn("post_self_test_tracker_reset")', source)
        self.assertIn("worker.detect_vehicles = supervised_detect_vehicles", source)
        self.assertIn("worker.YOLO = _ModelSentinel", source)

        self.assertIn("model.track(", child)
        self.assertIn("persist=True", child)
        self.assertIn("tracker=args.tracker", child)
        self.assertIn("device=args.device", child)
        self.assertIn("VEHICLE_CLASSES", child)
        self.assertIn("track_id", child)
        self.assertNotIn("HLS_URL", child)
        self.assertNotIn("SEA_SPEED_API_TOKEN", child)

    def test_media_and_ai_failures_are_separate_boundaries(self) -> None:
        source = ENTRYPOINT.read_text(encoding="utf-8")
        self.assertIn("class ResilientFFmpegRtspReader", source)
        self.assertIn("class BoundedYoloSupervisor", source)
        self.assertIn("return []", source)
        self.assertIn("self.degraded_until", source)
        self.assertNotIn("systemctl", source)

    def test_runner_records_ai_progress_without_secrets(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        for marker in (
            "ai_inference_ready",
            "ai_inference_success_count",
            "ai_inference_failure_count",
            "ai_inference_restart_count",
            "AI inference self-test ok",
            "AI inference degraded",
        ):
            self.assertIn(marker, source)
        for forbidden in ("HLS_URL", "SEA_SPEED_API_TOKEN", "worker.env"):
            self.assertNotIn(forbidden, source)

    def test_activation_gate_requires_two_ai_successes_and_frame_state_growth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            heartbeat = Path(temp_dir) / "worker-heartbeat.json"

            def write_payload(frame: int, state: int, ai: int) -> None:
                heartbeat.write_text(
                    json.dumps(
                        {
                            "source_commit": COMMIT,
                            "phase": "running",
                            "frame_progress_sequence": frame,
                            "state_post_success_count": state,
                            "last_state_post_ok": True,
                            "ai_inference_ready": True,
                            "ai_inference_success_count": ai,
                        }
                    ),
                    encoding="utf-8",
                )

            write_payload(1, 1, 2)

            def advance() -> None:
                time.sleep(1.0)
                write_payload(2, 2, 2)

            thread = threading.Thread(target=advance, daemon=True)
            thread.start()
            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "--heartbeat",
                    str(heartbeat),
                    "--expected-commit",
                    COMMIT,
                    "--timeout-sec",
                    "5",
                    "--poll-sec",
                    "0.1",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
            )
            thread.join(timeout=1)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RUNTIME_GATE_PASS", result.stdout)
            self.assertIn("ai_inference_success_count=2", result.stdout)

    def test_activation_gate_rejects_missing_ai_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            heartbeat = Path(temp_dir) / "worker-heartbeat.json"
            heartbeat.write_text(
                json.dumps(
                    {
                        "source_commit": COMMIT,
                        "phase": "running",
                        "frame_progress_sequence": 8,
                        "state_post_success_count": 8,
                        "last_state_post_ok": True,
                        "ai_inference_ready": False,
                        "ai_inference_success_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "--heartbeat",
                    str(heartbeat),
                    "--expected-commit",
                    COMMIT,
                    "--timeout-sec",
                    "5",
                    "--poll-sec",
                    "0.1",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("ai_inference_ready=false", result.stdout)
            self.assertIn("ai_inference_success_count=1", result.stdout)


if __name__ == "__main__":
    unittest.main()
