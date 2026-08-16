from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "deploy/worker/ubuntu/sea-speed-worker.service.template"
ROAD_UNIT = ROOT / "deploy/worker/ubuntu/sea-speed-road-worker.service.template"
CONTROL_UNIT = ROOT / "deploy/worker/ubuntu/sea-speed-worker-control.service.template"
INSTALLER = ROOT / "deploy/worker/ubuntu/install-systemd.sh"


class UbuntuWorkerSystemdTests(unittest.TestCase):
    def test_installer_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(INSTALLER)], check=True)

    def test_main_unit_remains_exact_and_protected(self) -> None:
        source = UNIT.read_text(encoding="utf-8")
        self.assertIn("runtimes/__RUNTIME_ID__/venv/bin/python", source)
        self.assertIn("releases/__SOURCE_COMMIT__/source/worker/", source)
        self.assertIn("EnvironmentFile=__INSTALL_ROOT__/shared/config/worker.env", source)
        self.assertIn("NoNewPrivileges=true", source)
        self.assertNotIn("git pull", source)

    def test_road_unit_is_exact_isolated_and_profile_bound(self) -> None:
        road = ROAD_UNIT.read_text(encoding="utf-8")
        for marker in (
            "sea-speed-road-worker", "runtimes/__RUNTIME_ID__/venv/bin/python",
            "releases/__SOURCE_COMMIT__/source/worker/ubuntu_worker_entrypoint.py",
            "EnvironmentFile=__INSTALL_ROOT__/shared/config/road-worker.env",
            "Environment=ANALYTICS_PROFILE=road-v1", "Environment=CAMERA_ID=road1",
            "road-worker-heartbeat.json",
        ):
            self.assertIn(marker, road)
        self.assertNotIn("sea-speed-worker-control", road)

    def test_installer_manages_three_units_without_starting_them(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('road_service_name="sea-speed-road-worker.service"', source)
        self.assertIn('systemd-analyze verify "$unit_target" "$road_unit_target" "$control_unit_target"', source)
        self.assertIn('systemctl enable "$service_name"', source)
        self.assertIn('systemctl enable "$control_service_name"', source)
        self.assertIn('systemctl enable "$road_service_name"', source)
        self.assertNotIn("systemctl start", source)
        self.assertNotIn("systemctl restart", source)

    def test_road_runtime_reuses_shared_models(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('ln -sfn "$install_root/shared/models" "$road_runtime_root/models"', source)
        self.assertIn('ln -sfn "$install_root/shared/datasets" "$road_runtime_root/datasets"', source)
        self.assertIn('road_env_file="$install_root/shared/config/road-worker.env"', source)
        self.assertIn("road-worker.env must be mode 600", source)

    def test_control_service_remains_independent(self) -> None:
        control = CONTROL_UNIT.read_text(encoding="utf-8")
        self.assertIn("User=root", control)
        self.assertNotIn("PartOf=sea-speed-worker.service", control)
        self.assertNotIn("Requires=sea-speed-worker.service", control)


if __name__ == "__main__":
    unittest.main()
