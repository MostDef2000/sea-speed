from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "worker" / "check_ubuntu_compatibility.py"
PREFLIGHT = ROOT / "deploy" / "worker" / "ubuntu" / "preflight.sh"
WORKER = ROOT / "worker" / "hls_motion_yolo_worker_events.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("ubuntu_worker_compatibility", CHECKER)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load compatibility checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UbuntuWorkerCompatibilityTests(unittest.TestCase):
    def test_current_worker_satisfies_static_contract(self) -> None:
        module = load_checker()
        result = module.inspect_worker(WORKER)
        self.assertTrue(result["compatible"], result)
        self.assertTrue(result["uses_pathlib"])
        self.assertTrue(result["subprocess_uses_argument_list"])
        self.assertEqual(result["missing_required_environment_names"], [])
        self.assertEqual(result["forbidden_markers"], [])

    def test_windows_only_worker_is_rejected(self) -> None:
        module = load_checker()
        source = """
import subprocess
from pathlib import Path

def env_str(name, default=''):
    return default

for name in ('HLS_URL', 'SEA_SPEED_API_URL', 'SEA_SPEED_API_TOKEN', 'MODEL_NAME'):
    env_str(name)

cmd = ['ffmpeg']
subprocess.Popen(cmd)
worker_home = 'D:\\\\sea-speed'
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "worker.py"
            path.write_text(source, encoding="utf-8")
            result = module.inspect_worker(path)
        self.assertFalse(result["compatible"])
        self.assertIn("D:\\\\sea-speed", result["forbidden_markers"])

    def test_preflight_is_shell_valid_and_does_not_print_secret_values(self) -> None:
        subprocess.run(["bash", "-n", str(PREFLIGHT)], check=True)
        source = PREFLIGHT.read_text(encoding="utf-8")
        self.assertIn("present_not_read", source)
        self.assertNotIn("printenv", source)
        self.assertNotIn("cat .env", source)
        self.assertNotIn("echo $SEA_SPEED_API_TOKEN", source)
        self.assertIn("worker_runtime=requires_installed_server", source)


if __name__ == "__main__":
    unittest.main()
