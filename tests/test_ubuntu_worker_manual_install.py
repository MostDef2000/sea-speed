from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy/worker/ubuntu/install-manual.sh"
ENV_EXAMPLE = ROOT / "deploy/worker/ubuntu/worker.env.example"
REQUIREMENTS = ROOT / "deploy/worker/ubuntu/requirements-runtime.txt"
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

    def test_cuda_pair_and_critical_runtime_versions_are_exact(self) -> None:
        requirements = REQUIREMENTS.read_text(encoding="utf-8")
        self.assertNotRegex(requirements, re.compile(r"^torch(?:[=<>]|$)", re.MULTILINE))
        self.assertNotRegex(requirements, re.compile(r"^torchvision(?:[=<>]|$)", re.MULTILINE))
        self.assertNotIn("av==", requirements)
        for requirement in (
            "ultralytics==8.4.117",
            "opencv-python==5.0.0.93",
            "opencv-python-headless==5.0.0.93",
            "numpy==2.4.4",
            "requests==2.34.2",
            "python-dotenv==1.2.2",
        ):
            self.assertIn(requirement, requirements)

        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("torch==2.13.0+cu130", installer)
        self.assertIn("torchvision==0.28.0+cu130", installer)
        self.assertIn("https://download.pytorch.org/whl/cu130", installer)
        self.assertIn("runtime version mismatch", installer)
        self.assertNotIn("import av", installer)

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
