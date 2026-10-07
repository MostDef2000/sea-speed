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

    def test_watchdog_copy_is_refreshed_from_release_source(self) -> None:
        # Deferred from #384 / tracked in #389: the watchdog is not one of the three
        # deploy-managed units, so its installed copy must be refreshed from the exact
        # release source during activation to avoid a stale copy across deploys.
        for marker in (
            'watchdog_src="$release_root/source/deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py"',
            'watchdog_dst="/usr/local/sbin/sea-speed-camera1-h264-freshness-watchdog"',
            'abort_activation "watchdog refresh source missing from release"',
            'abort_activation "watchdog script install failed"',
            'abort_activation "watchdog timer enable failed"',
        ):
            self.assertIn(marker, self.source)


class UbuntuWorkerWatchdogTransactionalRefreshTests(unittest.TestCase):
    # Issue #412: the watchdog refresh step is transactional — the pre-state is
    # captured before the first watchdog mutation, every activation abort after
    # the refresh started restores that captured pre-state, and the timer
    # enablement is reapplied from the captured state instead of being forced.
    def setUp(self) -> None: self.source = UPDATER.read_text(encoding="utf-8")

    def test_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(UPDATER)], check=True)

    def test_unconditional_timer_enable_is_removed(self) -> None:
        self.assertNotIn("systemctl enable --now sea-speed-camera1-h264-freshness.timer", self.source)
        self.assertNotIn('systemctl enable --now "$watchdog_timer_name"', self.source)

    def test_prestate_capture_precedes_first_watchdog_mutation(self) -> None:
        for marker in (
            'watchdog_unit_dst="/etc/systemd/system/sea-speed-camera1-h264-freshness.service"',
            'watchdog_timer_dst="/etc/systemd/system/sea-speed-camera1-h264-freshness.timer"',
            'watchdog_timer_name="sea-speed-camera1-h264-freshness.timer"',
            "previous_watchdog_script_present=false",
            "previous_watchdog_unit_present=false",
            "previous_watchdog_timer_present=false",
            "previous_watchdog_timer_enabled=false",
            "previous_watchdog_timer_active=false",
            'watchdog_script_backup="$(mktemp "$updater_root/watchdog-script-backup.XXXXXX")"',
            'watchdog_unit_backup="$(mktemp "$updater_root/watchdog-unit-backup.XXXXXX")"',
            'watchdog_timer_backup="$(mktemp "$updater_root/watchdog-timer-backup.XXXXXX")"',
            'if systemctl is-enabled --quiet "$watchdog_timer_name"; then',
            'if systemctl is-active --quiet "$watchdog_timer_name"; then',
            'abort_activation "watchdog pre-state capture failed"',
            "watchdog_prestate_captured=true",
        ):
            self.assertIn(marker, self.source)
        self.assertLess(
            self.source.index("watchdog_prestate_captured=true"),
            self.source.index('install -o root -g root -m 0755 "$watchdog_src" "$watchdog_dst"'),
        )

    def test_restore_previous_watchdog_restores_captured_prestate(self) -> None:
        for marker in (
            "restore_previous_watchdog()",
            'install -o root -g root -m 0755 "$watchdog_script_backup" "$watchdog_dst" || return 1',
            'install -o root -g root -m 0644 "$watchdog_unit_backup" "$watchdog_unit_dst" || return 1',
            'install -o root -g root -m 0644 "$watchdog_timer_backup" "$watchdog_timer_dst" || return 1',
            'rm -f "$watchdog_dst" || return 1',
            'rm -f "$watchdog_unit_dst" || return 1',
            'rm -f "$watchdog_timer_dst" || return 1',
            "RESTORED watchdog_script_present=",
        ):
            self.assertIn(marker, self.source)
        self.assertLess(
            self.source.index("restore_previous_watchdog()"),
            self.source.index("abort_activation()"),
        )

    def test_abort_paths_restore_watchdog_prestate(self) -> None:
        abort_body = self.source[self.source.index("abort_activation() {"):self.source.index("if ! (")]
        for marker in (
            "restore_previous_watchdog",
            "watchdog_prestate_restored",
            "CRITICAL watchdog pre-state could not be restored",
            "ACTIVATION_ABORTED target=%s restored=%s watchdog_prestate_restored=%s",
            "ACTIVE_MARKER_UNCHANGED source_commit=%s watchdog_prestate_restored=%s",
        ):
            self.assertIn(marker, abort_body)

    def test_timer_reapply_is_gated_on_captured_prestate(self) -> None:
        for marker in (
            'if [[ "$previous_watchdog_timer_enabled" == true ]]; then',
            'systemctl enable "$watchdog_timer_name" >/dev/null || abort_activation "watchdog timer enable failed"',
            'systemctl disable "$watchdog_timer_name" >/dev/null || abort_activation "watchdog timer disable failed"',
            'systemctl start "$watchdog_timer_name" >/dev/null || abort_activation "watchdog timer start failed"',
            "WATCHDOG_TIMER_REAPPLIED timer_present=",
        ):
            self.assertIn(marker, self.source)
        self.assertLess(
            self.source.index("WATCHDOG_TIMER_REAPPLIED timer_present="),
            self.source.index('if ! systemctl restart "$control_service_name"'),
        )

    def test_fresh_host_timer_stays_not_enabled(self) -> None:
        # A timer that did not exist before the deploy must not end up freshly
        # enabled: the absent-timer branch of the reapply only stops/disables.
        absent_branch = self.source[
            self.source.index('else\n  systemctl stop "$watchdog_timer_name"'):self.source.index("WATCHDOG_TIMER_REAPPLIED")
        ]
        self.assertIn('systemctl disable "$watchdog_timer_name" >/dev/null 2>&1 || true', absent_branch)
        self.assertNotIn("systemctl enable", absent_branch)

    def test_cleanup_covers_watchdog_backups(self) -> None:
        cleanup = self.source[self.source.index("cleanup() {"):self.source.index("trap cleanup EXIT")]
        for marker in ("watchdog_script_backup", "watchdog_unit_backup", "watchdog_timer_backup"):
            self.assertIn(marker, cleanup)


if __name__ == "__main__":
    unittest.main()
