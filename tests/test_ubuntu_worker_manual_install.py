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

    def test_pytorch_is_not_version_guessed(self) -> None:
        requirements = REQUIREMENTS.read_text(encoding="utf-8")
        self.assertNotRegex(requirements, re.compile(r"^torch(?:[=<>]|$)", re.MULTILINE))
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("hardware-compatible PyTorch", installer)
        self.assertNotIn("cu12", installer.lower())

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
