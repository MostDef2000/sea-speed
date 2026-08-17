from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLLBACK = ROOT / "deploy" / "worker" / "ubuntu" / "rollback-exact.sh"
UPDATER = ROOT / "deploy" / "worker" / "ubuntu" / "update-exact.sh"


class UbuntuWorkerRollbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rollback = ROLLBACK.read_text(encoding="utf-8")
        self.updater = UPDATER.read_text(encoding="utf-8")

    def test_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(ROLLBACK)], check=True)
        subprocess.run(["bash", "-n", str(UPDATER)], check=True)

    def test_exact_identity_quality_and_runtime_admission_remain(self) -> None:
        for marker in ("--expected-current", "quality_check=quality-integration", "rollback target provenance mismatch", "rollback target runtime ID is invalid", "active source commit does not match --expected-current"):
            self.assertIn(marker, self.rollback)

    def test_control_and_road_capabilities_are_explicit(self) -> None:
        for marker in (
            "target_has_control", "target_control_template", "target_has_road", "target_road_template",
            'road_service_name="sea-speed-road-worker.service"', "road-unit-backup", "restore_current_road()",
        ):
            self.assertIn(marker, self.rollback)

    def test_road_desired_state_is_preserved_through_target_activation(self) -> None:
        for marker in (
            'road_desired_state_file="$install_root/shared/road-runtime/operator-desired-state"',
            'road_desired_state="running"', 'ERROR road operator desired state is invalid',
            'apply_road_desired_state()', 'if [[ "$road_desired_state" == "running" ]]',
            'systemctl stop "$road_service_name"', 'ROAD_SERVICE_STOPPED', 'ROAD_SERVICE_ACTIVE',
            'road_desired_state=%s',
        ):
            self.assertIn(marker, self.rollback)
        self.assertIn('apply_road_desired_state || return 1', self.rollback)

    def test_legacy_target_removes_modern_optional_services(self) -> None:
        self.assertIn("remove_control_for_legacy_target()", self.rollback)
        self.assertIn("remove_road_for_legacy_target()", self.rollback)
        self.assertIn("CONTROL_SERVICE_ABSENT", self.rollback)
        self.assertIn("ROAD_SERVICE_ABSENT", self.rollback)

    def test_failed_target_restores_previous_main_road_and_control(self) -> None:
        for marker in ("restore_previous()", "restore_current_road()", "restore_current_control()", "ROLLBACK_ABORTED", "CRITICAL previous service restoration failed"):
            self.assertIn(marker, self.rollback)

    def test_shared_state_is_preserved(self) -> None:
        self.assertNotIn('rm -rf "$install_root/shared', self.rollback)
        self.assertNotIn('rm -rf "$install_root/releases', self.rollback)
        self.assertNotIn('rm -rf "$install_root/runtimes', self.rollback)
        self.assertIn("PRESERVED shared_config_models_datasets_output_releases_runtimes=true", self.rollback)


if __name__ == "__main__":
    unittest.main()
