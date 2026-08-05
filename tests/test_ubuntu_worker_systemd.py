from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "deploy/worker/ubuntu/sea-speed-worker.service.template"
INSTALLER = ROOT / "deploy/worker/ubuntu/install-systemd.sh"
DOC = ROOT / "docs/operations/UBUNTU_WORKER_SYSTEMD.md"


class UbuntuWorkerSystemdTests(unittest.TestCase):
    def test_unit_is_bound_to_exact_release(self) -> None:
        source = UNIT.read_text(encoding="utf-8")
        self.assertIn("releases/__SOURCE_COMMIT__/venv/bin/python", source)
        self.assertIn("releases/__SOURCE_COMMIT__/source/worker/", source)
        self.assertNotIn("/main/", source)
        self.assertNotIn("git pull", source)

    def test_unit_uses_protected_environment_and_service_user(self) -> None:
        source = UNIT.read_text(encoding="utf-8")
        self.assertIn("User=__SERVICE_USER__", source)
        self.assertIn("EnvironmentFile=__INSTALL_ROOT__/shared/config/worker.env", source)
        self.assertNotIn("SEA_SPEED_API_TOKEN=", source)
        self.assertIn("NoNewPrivileges=true", source)

    def test_restart_and_graceful_stop_contract(self) -> None:
        source = UNIT.read_text(encoding="utf-8")
        self.assertIn("Restart=on-failure", source)
        self.assertIn("RestartSec=10s", source)
        self.assertIn("KillSignal=SIGTERM", source)
        self.assertIn("TimeoutStopSec=30s", source)
        self.assertIn("StandardOutput=journal", source)

    def test_installer_is_idempotent_and_does_not_start(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('id "$service_user"', source)
        self.assertIn("systemctl daemon-reload", source)
        self.assertIn("systemctl enable", source)
        self.assertNotIn("systemctl start", source)
        self.assertNotIn("systemctl restart", source)
        self.assertIn("NOT_STARTED", source)

    def test_shared_runtime_paths_are_used(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        for name in ("models", "output", "datasets"):
            self.assertIn(f'$runtime_root/{name}', source)
            self.assertIn(f'$install_root/shared/{name}', source)
        self.assertIn("WorkingDirectory=__INSTALL_ROOT__/shared/runtime", UNIT.read_text(encoding="utf-8"))

    def test_documentation_preserves_runtime_boundary(self) -> None:
        source = DOC.read_text(encoding="utf-8")
        self.assertIn("Runtime remains `UNKNOWN`", source)
        self.assertIn("does not start the service", source)
        self.assertIn("journalctl", source)


if __name__ == "__main__":
    unittest.main()
