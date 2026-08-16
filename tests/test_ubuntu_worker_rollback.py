from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLLBACK = ROOT / "deploy/worker/ubuntu/rollback-exact.sh"
UPDATER = ROOT / "deploy/worker/ubuntu/update-exact.sh"
DOC = ROOT / "docs/operations/UBUNTU_WORKER_ROLLBACK.md"


class UbuntuWorkerRollbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rollback = ROLLBACK.read_text(encoding="utf-8")
        self.updater = UPDATER.read_text(encoding="utf-8")

    def test_shell_syntax_is_valid(self) -> None:
        subprocess.run(["bash", "-n", str(ROLLBACK)], check=True)
        subprocess.run(["bash", "-n", str(UPDATER)], check=True)

    def test_updater_records_exact_quality_approval(self) -> None:
        self.assertIn('quality_marker="$release_root/quality-approved"', self.updater)
        self.assertIn("source_commit=%s", self.updater)
        self.assertIn("quality_check=quality-integration", self.updater)
        self.assertIn('chown root:root "$quality_marker"', self.updater)
        self.assertIn('chmod 0644 "$quality_marker"', self.updater)

    def test_rollback_requires_exact_current_and_target_identity(self) -> None:
        self.assertIn('^[0-9a-f]{40}$', self.rollback)
        self.assertIn("--expected-current", self.rollback)
        self.assertIn("active source commit does not match --expected-current", self.rollback)
        self.assertIn("installed unit and active source marker disagree", self.rollback)
        self.assertIn("worker unit and active source marker disagree", self.rollback)
        self.assertIn("target commit is already active", self.rollback)

    def test_target_must_be_prepared_and_quality_approved(self) -> None:
        for marker in (
            'target_provenance="$target_root/source-commit"',
            'target_quality="$target_root/quality-approved"',
            "quality_check=quality-integration",
            "rollback target provenance mismatch",
            "rollback target is not exact quality-approved",
        ):
            self.assertIn(marker, self.rollback)
        self.assertIn("target quality marker ownership or mode is invalid", self.rollback)

    def test_new_target_requires_recorded_ready_runtime(self) -> None:
        self.assertIn('target_runtime_file="$target_root/runtime-id"', self.rollback)
        self.assertIn('target_runtime_root="$install_root/runtimes/$target_runtime_id"', self.rollback)
        self.assertIn('target_runtime_root/venv/bin/python', self.rollback)
        self.assertIn("rollback target runtime ID is invalid", self.rollback)
        self.assertIn("rollback target shared runtime is not ready", self.rollback)
        self.assertIn('/runtimes/$target_runtime_id/venv/bin/python', self.rollback)

    def test_legacy_per_release_target_remains_supported_during_migration(self) -> None:
        self.assertIn('$target_root/venv/bin/python', self.rollback)
        self.assertIn("rollback target legacy runtime is missing", self.rollback)
        self.assertIn("legacy-per-release", self.rollback)

    def test_target_control_capability_is_explicit_and_partial_state_fails_closed(self) -> None:
        self.assertIn('target_control_template="$target_source/deploy/worker/ubuntu/sea-speed-worker-control.service.template"', self.rollback)
        self.assertIn('target_control_agent="$target_source/deploy/worker/ubuntu/worker-control-agent.py"', self.rollback)
        self.assertIn("target_has_control=false", self.rollback)
        self.assertIn("rollback target has incomplete worker-control components", self.rollback)
        self.assertIn("rollback target installer does not manage its worker-control unit", self.rollback)
        self.assertIn("target_has_control=true", self.rollback)

    def test_update_and_rollback_share_root_only_lock(self) -> None:
        for source in (self.updater, self.rollback):
            self.assertIn('updater_root="$install_root/updater"', source)
            self.assertIn('exec 9>"$updater_root/update.lock"', source)
            self.assertIn("flock -n 9", source)
        self.assertIn("another worker update or rollback is already running", self.rollback)

    def test_current_units_and_control_topology_are_backed_up_before_target_activation(self) -> None:
        backup = self.rollback.index('install -o root -g root -m 0600 "$unit_target" "$unit_backup"')
        activation = self.rollback.index("if ! activate_target; then")
        self.assertLess(backup, activation)
        self.assertIn("current_control_present=false", self.rollback)
        self.assertIn("current_control_enabled=false", self.rollback)
        self.assertIn("current_control_active=false", self.rollback)
        self.assertIn("control-unit-backup", self.rollback)
        self.assertIn("installed control unit and active source marker disagree", self.rollback)
        self.assertIn("running control service and active source marker disagree", self.rollback)
        self.assertIn("worker control service state exists without an installed control unit", self.rollback)

    def test_failed_target_restores_previous_exact_source_runtime_intent_and_control_topology(self) -> None:
        self.assertIn("restore_previous()", self.rollback)
        self.assertIn("restore_current_control()", self.rollback)
        self.assertIn('install -o root -g root -m 0644 "$unit_backup" "$unit_target"', self.rollback)
        self.assertIn('apply_desired_state', self.rollback)
        self.assertIn('systemctl restart "$service_name"', self.rollback)
        self.assertIn('systemctl stop "$service_name"', self.rollback)
        self.assertIn('[[ "$restored_exec" == *"$current_commit"* ]]', self.rollback)
        self.assertIn("current_runtime_id", self.rollback)
        self.assertIn("ROLLBACK_ABORTED", self.rollback)
        self.assertIn("CRITICAL previous service restoration failed", self.rollback)
        restore_control = self.rollback.split("restore_current_control() {", 1)[1].split("restore_previous() {", 1)[0]
        self.assertIn('systemctl stop "$control_service_name"', restore_control)
        self.assertIn('systemctl disable "$control_service_name"', restore_control)
        self.assertIn('rm -f "$control_unit_target"', restore_control)
        self.assertIn('[[ ! -e "$control_unit_target" ]]', restore_control)
        self.assertIn('! systemctl is-enabled --quiet "$control_service_name"', restore_control)

    def test_legacy_target_removes_modern_control_service(self) -> None:
        self.assertIn("remove_control_for_legacy_target()", self.rollback)
        remove_control = self.rollback.split("remove_control_for_legacy_target() {", 1)[1].split("activate_target() {", 1)[0]
        self.assertIn('systemctl stop "$control_service_name"', remove_control)
        self.assertIn('systemctl disable "$control_service_name"', remove_control)
        self.assertIn('rm -f "$control_unit_target"', remove_control)
        self.assertIn('[[ ! -e "$control_unit_target" ]]', remove_control)
        self.assertIn('! systemctl is-enabled --quiet "$control_service_name"', remove_control)
        self.assertIn("CONTROL_SERVICE_ABSENT", self.rollback)

    def test_modern_target_requires_active_exact_control_service(self) -> None:
        activate = self.rollback.split("activate_target() {", 1)[1].split("if ! activate_target; then", 1)[0]
        self.assertIn('if [[ "$target_has_control" == true ]]', activate)
        self.assertIn('systemctl restart "$control_service_name"', activate)
        self.assertIn('systemctl is-active --quiet "$control_service_name"', activate)
        self.assertIn('[[ "$control_exec" == *"$target_commit"* ]]', activate)
        self.assertIn("CONTROL_SERVICE_ACTIVE", self.rollback)

    def test_intentional_stopped_state_is_preserved(self) -> None:
        self.assertIn('desired_state_file="$install_root/shared/runtime/operator-desired-state"', self.rollback)
        self.assertIn('desired_state="running"', self.rollback)
        self.assertIn('if [[ "$desired_state" == "running" ]]', self.rollback)
        self.assertIn("SERVICE_STOPPED", self.rollback)

    def test_active_marker_changes_only_after_target_acceptance(self) -> None:
        acceptance = self.rollback.index("if ! activate_target; then")
        marker_write = self.rollback.index("active-marker.XXXXXX")
        self.assertLess(acceptance, marker_write)
        self.assertIn('mv -f "$marker_tmp" "$active_marker"', self.rollback)
        self.assertIn("ACTIVE_SOURCE_COMMIT", self.rollback)
        self.assertIn("TARGET_RUNTIME_ID", self.rollback)

    def test_shared_state_releases_and_runtimes_are_preserved(self) -> None:
        self.assertNotIn('rm -rf "$install_root/shared', self.rollback)
        self.assertNotIn('rm -rf "$install_root/releases', self.rollback)
        self.assertNotIn('rm -rf "$install_root/runtimes', self.rollback)
        self.assertIn("PRESERVED shared_config_models_datasets_output_releases_runtimes=true", self.rollback)
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("Runtime remains `UNKNOWN`", doc)
        self.assertIn("Stage 7", doc)
        self.assertIn("legacy target", doc)
        self.assertIn("CONTROL_SERVICE_ABSENT", doc)


if __name__ == "__main__":
    unittest.main()
