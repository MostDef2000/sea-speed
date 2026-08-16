from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "deploy/worker/ubuntu/update-exact.sh"


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

    def test_main_desired_state_stays_main_worker_specific(self) -> None:
        self.assertIn('desired_state_file="$install_root/shared/runtime/operator-desired-state"', self.source)
        self.assertIn('if [[ "$desired_state" == "stopped" ]]', self.source)
        self.assertIn('systemctl stop "$service_name"', self.source)
        self.assertIn("RUNTIME_GATE skipped_reason=operator_desired_stopped", self.source)
        road_block = self.source[self.source.index('if [[ -f "$road_env_file" ]]'):]
        self.assertNotIn('desired_state == "stopped"', road_block)

    def test_road_topology_is_backup_bound_and_runtime_gated(self) -> None:
        for marker in (
            'road_service_name="sea-speed-road-worker.service"', "road-unit-backup.XXXXXX",
            "restore_previous_road()", "road-worker-heartbeat.json", "ROAD_RUNTIME_GATE frame_and_state_progression=PASS",
            'systemctl restart "$road_service_name"', "road worker unit does not reference requested runtime ID",
        ):
            self.assertIn(marker, self.source)

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
