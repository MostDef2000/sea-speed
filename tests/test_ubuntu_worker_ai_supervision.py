from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "worker/ubuntu_worker_entrypoint.py"
AI_CHILD = ROOT / "worker/ubuntu_ai_inference_worker.py"
RUNNER = ROOT / "deploy/worker/ubuntu/observed-worker-runner.py"
GATE = ROOT / "deploy/worker/ubuntu/verify-runtime-progression.py"
UPDATER = ROOT / "deploy/worker/ubuntu/update-exact.sh"


class UbuntuWorkerAiSupervisionTests(unittest.TestCase):
    def test_python_syntax(self) -> None:
        subprocess.run([sys.executable, "-m", "py_compile", str(ENTRYPOINT), str(AI_CHILD), str(RUNNER), str(GATE)], check=True)

    def test_bounded_child_and_profile_arguments(self) -> None:
        source = ENTRYPOINT.read_text(encoding="utf-8")
        child = AI_CHILD.read_text(encoding="utf-8")
        for marker in ("class BoundedYoloSupervisor", "AI_INFERENCE_TIMEOUT_SEC", "select.select", "proc.kill()", "AI inference degraded", "worker.detect_vehicles = supervised_detect_vehicles"):
            self.assertIn(marker, source)
        self.assertIn('os.environ.setdefault("ANALYTICS_PROFILE", "water-v1")', source)
        self.assertIn('profile = get_profile', source)
        self.assertIn('"--analytics-profile"', source)
        self.assertIn("model.track(", child)
        self.assertIn("persist=True", child)
        self.assertIn("tracker=args.tracker", child)
        self.assertIn("normalize_model_class", child)
        self.assertIn('parser.add_argument("--analytics-profile"', child)
        self.assertIn("**semantic", child)
        self.assertNotIn("HLS_URL", child)
        self.assertNotIn("SEA_SPEED_API_TOKEN", child)

    def test_ai_request_uses_one_absolute_deadline(self) -> None:
        source = ENTRYPOINT.read_text(encoding="utf-8")
        for marker in ("def _write_all_bounded", "os.set_blocking(self.proc.stdin.fileno(), False)", "deadline = time.monotonic() + timeout_sec", "self._write_all_bounded(raw, deadline)"):
            self.assertIn(marker, source)
        self.assertNotIn("proc.stdin.write(raw)", source)

    def test_activation_budget_and_road_gate_are_explicit(self) -> None:
        source = UPDATER.read_text(encoding="utf-8")
        self.assertIn("--timeout-sec 90", source)
        self.assertIn("ROAD_RUNTIME_GATE frame_and_state_progression=PASS", source)
        self.assertIn("road-worker-heartbeat.json", source)


if __name__ == "__main__":
    unittest.main()
