from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy/worker/ubuntu"
RUNNER = DEPLOY / "observed-worker-runner.py"
CHECKER = DEPLOY / "check-worker-health.py"
INSTALLER = DEPLOY / "install-observability.sh"
WORKER_UNIT = DEPLOY / "sea-speed-worker.service.template"
HEALTH_SERVICE = DEPLOY / "sea-speed-worker-health.service.template"
HEALTH_TIMER = DEPLOY / "sea-speed-worker-health.timer.template"
DOC = ROOT / "docs/operations/UBUNTU_WORKER_OBSERVABILITY.md"
COMMIT = "a" * 40


class UbuntuWorkerObservabilityTests(unittest.TestCase):
    def test_python_and_shell_syntax(self) -> None:
        subprocess.run([sys.executable, "-m", "py_compile", str(RUNNER), str(CHECKER)], check=True)
        subprocess.run(["bash", "-n", str(INSTALLER)], check=True)

    def test_worker_unit_uses_exact_observed_runner(self) -> None:
        source = WORKER_UNIT.read_text(encoding="utf-8")
        self.assertIn("observed-worker-runner.py", source)
        self.assertIn("--source-commit __SOURCE_COMMIT__", source)
        self.assertIn("worker-heartbeat.json", source)
        self.assertIn("releases/__SOURCE_COMMIT__/source/worker/", source)
        self.assertNotIn("git pull", source)

    def test_runner_emits_non_secret_atomic_heartbeat(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("os.replace(temporary, path)", source)
        self.assertIn("frame_progress_sequence", source)
        self.assertIn("last_state_post_ok", source)
        for forbidden in ("HLS_URL", "SEA_SPEED_API_TOKEN", "HLS_BASIC_AUTH_BASE64", "worker.env"):
            self.assertNotIn(forbidden, source)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            heartbeat = root / "worker-heartbeat.json"
            overlay = root / "latest_overlay.jpg"
            fake_worker = root / "fake_worker.py"
            fake_worker.write_text(
                textwrap.dedent(
                    f"""
                    import pathlib
                    import time
                    print("Worker started", flush=True)
                    pathlib.Path({str(overlay)!r}).write_bytes(b"frame")
                    print("POST state ok motion=False ai=False detections=0 tracks=0", flush=True)
                    print("POST event ok id=test class=car conf=0.90", flush=True)
                    time.sleep(1.25)
                    """
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--source-commit",
                    COMMIT,
                    "--heartbeat",
                    str(heartbeat),
                    "--overlay",
                    str(overlay),
                    "--heartbeat-interval-sec",
                    "1",
                    str(fake_worker),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(heartbeat.read_text(encoding="utf-8"))
            self.assertEqual(payload["source_commit"], COMMIT)
            self.assertGreaterEqual(payload["frame_progress_sequence"], 1)
            self.assertEqual(payload["state_post_success_count"], 1)
            self.assertTrue(payload["last_state_post_ok"])
            self.assertEqual(payload["event_post_success_count"], 1)
            self.assertEqual(payload["phase"], "exited")

    def test_health_checker_accepts_consistent_exact_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            install_root = root / "install"
            release_root = install_root / "releases" / COMMIT
            runtime_root = install_root / "shared/runtime"
            bin_root = root / "bin"
            report = install_root / "observability/worker-health-report.json"
            unit = root / "sea-speed-worker.service"
            heartbeat = runtime_root / "worker-heartbeat.json"
            release_root.mkdir(parents=True)
            runtime_root.mkdir(parents=True)
            bin_root.mkdir(parents=True)
            (release_root / "source-commit").write_text(COMMIT + "\n", encoding="utf-8")
            (release_root / "quality-approved").write_text(
                f"source_commit={COMMIT}\nquality_check=quality-integration\n",
                encoding="utf-8",
            )
            (runtime_root / "active-source-commit").write_text(COMMIT + "\n", encoding="utf-8")
            unit.write_text(
                f"ExecStart=/venv/python observed-worker-runner.py --source-commit {COMMIT}\n",
                encoding="utf-8",
            )
            now = datetime.now(timezone.utc).isoformat()
            heartbeat.write_text(
                json.dumps(
                    {
                        "source_commit": COMMIT,
                        "observed_at": now,
                        "phase": "running",
                        "frame_progress_sequence": 5,
                        "last_frame_at": now,
                        "last_state_post_at": now,
                        "last_state_post_ok": True,
                        "state_post_success_count": 5,
                        "state_post_failure_count": 0,
                        "event_post_success_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            systemctl = bin_root / "systemctl"
            systemctl.write_text(
                f"#!/usr/bin/env python3\n"
                "import sys\n"
                "if len(sys.argv) > 1 and sys.argv[1] == 'is-active':\n"
                "    raise SystemExit(0)\n"
                "if len(sys.argv) > 1 and sys.argv[1] == 'show':\n"
                f"    print('/venv/python observed-worker-runner.py --source-commit {COMMIT}')\n"
                "    raise SystemExit(0)\n"
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            nvidia = bin_root / "nvidia-smi"
            nvidia.write_text("#!/bin/sh\nprintf '0\\n'\n", encoding="utf-8")
            for executable in (systemctl, nvidia):
                executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
            environment = dict(os.environ)
            environment["PATH"] = str(bin_root) + os.pathsep + environment.get("PATH", "")
            result = subprocess.run(
                [
                    sys.executable,
                    str(CHECKER),
                    "--install-root",
                    str(install_root),
                    "--unit-path",
                    str(unit),
                    "--expected-commit",
                    COMMIT,
                    "--heartbeat",
                    str(heartbeat),
                    "--write-report",
                    str(report),
                    "--min-free-gib",
                    "0",
                    "--require-gpu",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["overall"], "healthy")
            self.assertEqual(payload["active_commit"], COMMIT)
            self.assertEqual(payload["gpu_count"], 1)
            self.assertTrue(all(check["ok"] for check in payload["checks"]))

    def test_periodic_units_and_installer_do_not_start(self) -> None:
        service = HEALTH_SERVICE.read_text(encoding="utf-8")
        timer = HEALTH_TIMER.read_text(encoding="utf-8")
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("check-worker-health.py", service)
        self.assertIn("--expected-commit __SOURCE_COMMIT__", service)
        self.assertIn("--require-gpu", service)
        self.assertIn("OnUnitActiveSec=1min", timer)
        self.assertIn("Persistent=true", timer)
        self.assertIn("systemctl enable", installer)
        self.assertIn("quality-approved marker ownership or mode is invalid", installer)
        self.assertNotIn("systemctl start", installer)
        self.assertNotIn("systemctl restart", installer)
        self.assertIn("NOT_STARTED", installer)
        self.assertNotIn('cat "$env_file"', installer)

    def test_documentation_preserves_runtime_boundary(self) -> None:
        source = DOC.read_text(encoding="utf-8")
        self.assertIn("Runtime remains `UNKNOWN`", source)
        self.assertIn("journalctl", source)
        self.assertIn("does not start the timer", source)
        self.assertNotIn("Grafana", source)


if __name__ == "__main__":
    unittest.main()
