from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy/worker/ubuntu/install-manual.sh"
PREPARE_RUNTIME = ROOT / "deploy/worker/ubuntu/prepare-runtime.sh"
RUNTIME_LOCK = ROOT / "deploy/worker/ubuntu/runtime-lock.json"
ENV_EXAMPLE = ROOT / "deploy/worker/ubuntu/worker.env.example"
REQUIREMENTS = ROOT / "deploy/worker/ubuntu/requirements-runtime.txt"
SERVICE_TEMPLATE = ROOT / "deploy/worker/ubuntu/sea-speed-worker.service.template"
DOC = ROOT / "docs/operations/UBUNTU_WORKER_MANUAL_INSTALL.md"


class UbuntuWorkerManualInstallTests(unittest.TestCase):
    def test_installer_requires_exact_commit_and_verifies_head(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('^[0-9a-f]{40}$', source)
        self.assertIn('git rev-parse HEAD', source)
        self.assertIn('checkout commit mismatch', source)
        self.assertIn('git archive "$expected_commit"', source)

    def test_protected_paths_are_outside_release_source(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        for name in ("config", "models", "datasets", "output"):
            self.assertIn(f'$install_root/shared/{name}', source)
        self.assertNotIn('rm -rf "$install_root/shared', source)
        self.assertIn('Do not remove `shared/`', DOC.read_text(encoding="utf-8"))

    def test_source_release_binds_shared_runtime_instead_of_own_venv(self) -> None:
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("prepare-runtime.sh", installer)
        self.assertIn('runtime_id_file="$release_root/runtime-id"', installer)
        self.assertIn('runtime_root="$install_root/runtimes/$runtime_id"', installer)
        self.assertNotIn('venv_root="$release_root/venv"', installer)
        self.assertNotIn("-m pip install", installer)
        self.assertIn("RUNTIME_ID %s", installer)

    def test_cuda_pair_and_critical_runtime_versions_are_exact(self) -> None:
        requirements = REQUIREMENTS.read_text(encoding="utf-8")
        self.assertNotRegex(requirements, re.compile(r"^torch(?:[=<>]|$)", re.MULTILINE))
        self.assertNotRegex(requirements, re.compile(r"^torchvision(?:[=<>]|$)", re.MULTILINE))
        self.assertNotIn("av==", requirements)
        for requirement in (
            "ultralytics==8.4.117",
            "lap==0.5.13",
            "opencv-python==5.0.0.93",
            "opencv-python-headless==5.0.0.93",
            "numpy==2.4.4",
            "requests==2.34.2",
            "python-dotenv==1.2.2",
        ):
            self.assertIn(requirement, requirements)

        lock = json.loads(RUNTIME_LOCK.read_text(encoding="utf-8"))
        self.assertEqual(lock["pytorch"]["packages"]["torch"], "2.13.0+cu130")
        self.assertEqual(
            lock["pytorch"]["packages"]["torchvision"], "0.28.0+cu130"
        )
        self.assertEqual(
            lock["pytorch"]["index_url"], "https://download.pytorch.org/whl/cu130"
        )
        prepare = PREPARE_RUNTIME.read_text(encoding="utf-8")
        self.assertIn("runtime version mismatch", prepare)
        self.assertIn("importlib.import_module", prepare)
        self.assertNotIn("import av", prepare)

    def test_service_disables_ultralytics_runtime_autoinstall(self) -> None:
        source = SERVICE_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Environment=YOLO_AUTOINSTALL=false", source)

    def test_environment_template_contains_names_not_secrets(self) -> None:
        source = ENV_EXAMPLE.read_text(encoding="utf-8")
        self.assertIn("HLS_URL=", source)
        self.assertIn("SEA_SPEED_API_TOKEN=", source)
        forbidden = ("http://", "https://", "Bearer ", "Basic ", "password=")
        for marker in forbidden:
            self.assertNotIn(marker, source)

    def test_scope_excludes_service_and_activation(self) -> None:
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertNotIn("systemctl", installer)
        self.assertNotIn("ln -s", installer)
        self.assertIn("UNKNOWN worker_runtime=server_not_commissioned", installer)


if __name__ == "__main__":
    unittest.main()
