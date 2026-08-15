from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "deploy/worker/ubuntu/sea-speed-worker.service.template"
CONTROL_UNIT = ROOT / "deploy/worker/ubuntu/sea-speed-worker-control.service.template"
INSTALLER = ROOT / "deploy/worker/ubuntu/install-systemd.sh"
DOC = ROOT / "docs/operations/UBUNTU_WORKER_SYSTEMD.md"


class UbuntuWorkerSystemdTests(unittest.TestCase):
    def test_unit_is_bound_to_exact_source_and_runtime(self) -> None:
        source = UNIT.read_text(encoding="utf-8")
        self.assertIn("runtimes/__RUNTIME_ID__/venv/bin/python", source)
        self.assertIn("releases/__SOURCE_COMMIT__/source/worker/", source)
        self.assertIn("Environment=SEA_SPEED_SOURCE_COMMIT=__SOURCE_COMMIT__", source)
        self.assertIn("Environment=SEA_SPEED_RUNTIME_ID=__RUNTIME_ID__", source)
        self.assertNotIn("releases/__SOURCE_COMMIT__/venv/bin/python", source)
        self.assertNotIn("/main/", source)
        self.assertNotIn("git pull", source)

    def test_installer_validates_recorded_ready_runtime(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('runtime_id_file="$release_root/runtime-id"', source)
        self.assertIn('runtime_root="$install_root/runtimes/$runtime_id"', source)
        self.assertIn('runtime_python="$runtime_root/venv/bin/python"', source)
        self.assertIn('runtime_ready="$runtime_root/ready"', source)
        self.assertIn("shared runtime ready marker mismatch", source)
        self.assertIn('s|__RUNTIME_ID__|$runtime_id|g', source)

    def test_unit_uses_protected_environment_and_service_user(self) -> None:
        source = UNIT.read_text(encoding="utf-8")
        self.assertIn("User=__SERVICE_USER__", source)
        self.assertIn("EnvironmentFile=__INSTALL_ROOT__/shared/config/worker.env", source)
        self.assertNotIn("SEA_SPEED_API_TOKEN=", source)
        self.assertIn("NoNewPrivileges=true", source)
        self.assertIn("Environment=PYTHONDONTWRITEBYTECODE=1", source)

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

    def test_shared_runtime_state_paths_are_preserved(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        for name in ("models", "output", "datasets"):
            self.assertIn(f'$runtime_state_root/{name}', source)
            self.assertIn(f'$install_root/shared/{name}', source)
        self.assertIn(
            "WorkingDirectory=__INSTALL_ROOT__/shared/runtime",
            UNIT.read_text(encoding="utf-8"),
        )

    def test_control_service_is_independent_and_exact_source_bound(self) -> None:
        control = CONTROL_UNIT.read_text(encoding="utf-8")
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("Description=Sea Speed bounded AI worker control agent", control)
        self.assertIn("User=root", control)
        self.assertIn("EnvironmentFile=__INSTALL_ROOT__/shared/config/worker.env", control)
        self.assertIn("releases/__SOURCE_COMMIT__/source/deploy/worker/ubuntu/worker-control-agent.py", control)
        self.assertNotIn("PartOf=sea-speed-worker.service", control)
        self.assertNotIn("Requires=sea-speed-worker.service", control)
        self.assertIn('control_service_name="sea-speed-worker-control.service"', installer)
        self.assertIn('systemctl enable "$control_service_name"', installer)
        self.assertIn('systemd-analyze verify "$unit_target" "$control_unit_target"', installer)

    def test_documentation_preserves_runtime_boundary(self) -> None:
        source = DOC.read_text(encoding="utf-8")
        self.assertIn("Runtime remains `UNKNOWN`", source)
        self.assertIn("does not start the service", source)
        self.assertIn("journalctl", source)


if __name__ == "__main__":
    unittest.main()
