from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "deploy" / "worker" / "ubuntu" / "update-exact.sh"


class UbuntuWorkerExactUpdaterTests(unittest.TestCase):
    def setUp(self) -> None: self.source = UPDATER.read_text(encoding="utf-8")

    def test_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(UPDATER)], check=True)

    def test_exact_main_quality_and_shared_runtime_gates_remain(self) -> None:
        for marker in (
            "origin main:refs/remotes/origin/main", "merge-base --is-ancestor", "verify_quality_status.py",
            "--workflow-file quality-integration.yml", "runtime_id_file=", "RUNTIME_BOUND source_commit=",
            "quality-approved", "quality_check=quality-integration", "active-source-commit",
        ):
            self.assertIn(marker, self.source)
        self.assertNotIn("-m pip install", self.source)
        self.assertNotIn("download.pytorch.org", self.source)

    def test_water_and_road_desired_states_are_independent(self) -> None:
        for marker in (
            'desired_state_file="$install_root/shared/runtime/operator-desired-state"',
            'road_desired_state_file="$install_root/shared/road-runtime/operator-desired-state"',
            'desired_state="running"', 'road_desired_state="running"',
            'ERROR operator desired state is invalid', 'ERROR road operator desired state is invalid',
            'if [[ "$desired_state" == "stopped" ]]',
            'if [[ "$road_desired_state" == "stopped" ]]',
        ):
            self.assertIn(marker, self.source)
        self.assertIn('systemctl stop "$service_name"', self.source)
        self.assertIn('systemctl stop "$road_service_name"', self.source)
        self.assertIn('systemctl restart "$service_name"', self.source)
        self.assertIn('systemctl restart "$road_service_name"', self.source)

    def test_road_desired_state_controls_runtime_gate(self) -> None:
        self.assertIn('if [[ "$road_configured" == true && "$road_desired_state" == "running" ]]', self.source)
        self.assertIn("ROAD_RUNTIME_GATE frame_and_state_progression=PASS", self.source)
        self.assertIn("ROAD_RUNTIME_GATE skipped_reason=operator_desired_stopped", self.source)
        self.assertIn("ROAD_SERVICE_STOPPED", self.source)
        self.assertIn("ROAD_SERVICE_ACTIVE", self.source)

    def test_road_topology_is_backup_bound_and_runtime_gated(self) -> None:
        for marker in (
            'road_service_name="sea-speed-road-worker.service"', "road-unit-backup.XXXXXX",
            "restore_previous_road()", "road-worker-heartbeat.json", "ROAD_RUNTIME_GATE frame_and_state_progression=PASS",
            "road worker unit does not reference requested runtime ID",
        ):
            self.assertIn(marker, self.source)

    def test_pre_activation_state_validation_is_independent(self) -> None:
        self.assertIn("desired running worker is not active before activation", self.source)
        self.assertIn("desired stopped worker is unexpectedly active before activation", self.source)
        self.assertIn("desired running road worker is not active before activation", self.source)
        self.assertIn("desired stopped road worker is unexpectedly active before activation", self.source)

    def test_cleanup_covers_main_road_control_and_marker(self) -> None:
        cleanup = self.source[self.source.index("cleanup() {"):self.source.index("trap cleanup EXIT")]
        for marker in ("staging_root", "unit_backup", "road_unit_backup", "control_unit_backup", "marker_tmp"):
            self.assertIn(marker, cleanup)
        self.assertIn("return \"$status\"", cleanup)

    def test_failure_restores_previous_release_and_both_service_topologies(self) -> None:
        for marker in ("restore_previous()", "restore_previous_road()", "restore_previous_control()", "ACTIVATION_ABORTED", "ACTIVE_MARKER_UNCHANGED"):
            self.assertIn(marker, self.source)


if __name__ == "__main__":
    unittest.main()
