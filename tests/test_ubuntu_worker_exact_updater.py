from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "deploy/worker/ubuntu/update-exact.sh"
QUALITY_VERIFIER = ROOT / "scripts/quality/verify_quality_status.py"
DOC = ROOT / "docs/operations/UBUNTU_WORKER_EXACT_UPDATE.md"


class UbuntuWorkerExactUpdaterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = UPDATER.read_text(encoding="utf-8")

    def test_shell_syntax_is_valid(self) -> None:
        subprocess.run(["bash", "-n", str(UPDATER)], check=True)

    def test_only_exact_main_commit_is_accepted(self) -> None:
        self.assertIn('^[0-9a-f]{40}$', self.source)
        self.assertIn("origin main:refs/remotes/origin/main", self.source)
        self.assertIn("merge-base --is-ancestor", self.source)
        self.assertIn("refs/remotes/origin/main", self.source)
        self.assertIn("staged checkout commit mismatch", self.source)

    def test_quality_gate_cli_matches_real_verifier(self) -> None:
        help_result = subprocess.run(
            [sys.executable, str(QUALITY_VERIFIER), "--help"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("--workflow-file WORKFLOW_FILE", help_result.stdout)
        self.assertIn("verify_quality_status.py", self.source)
        self.assertIn("--workflow-file quality-integration.yml", self.source)
        self.assertNotIn("--required-name", self.source)
        self.assertIn("GitHub token file mode must be 600", self.source)
        self.assertIn("GitHub token file must be owned by root", self.source)
        self.assertIn('IFS= read -r github_token < "$token_file"', self.source)
        self.assertIn('GITHUB_TOKEN="$github_token" python3', self.source)
        self.assertNotIn('echo "$github_token"', self.source)
        self.assertNotIn('cat "$token_file"', self.source)

    def test_updates_are_serialized_and_staged(self) -> None:
        self.assertIn("update.lock", self.source)
        self.assertIn("flock -n 9", self.source)
        self.assertIn("staging.XXXXXX", self.source)
        self.assertIn("trap cleanup EXIT", self.source)
        self.assertIn('cd "$staging_root"', self.source)
        self.assertIn("install-manual.sh", self.source)

    def test_updater_binds_prepared_shared_runtime_without_installing_packages(self) -> None:
        self.assertIn('runtime_id_file="$release_root/runtime-id"', self.source)
        self.assertIn('runtime_root="$install_root/runtimes/$runtime_id"', self.source)
        self.assertIn("RUNTIME_BOUND source_commit=", self.source)
        self.assertIn("runtime_id=%s", self.source)
        self.assertNotIn("-m pip install", self.source)
        self.assertNotIn("download.pytorch.org", self.source)

    def test_running_activation_requires_complete_control_target_and_runtime_progression(self) -> None:
        self.assertIn("--activate", self.source)
        self.assertIn("NOT_ACTIVATED explicit_flag_required=--activate", self.source)
        self.assertIn('target_control_template="$release_root/source/deploy/worker/ubuntu/sea-speed-worker-control.service.template"', self.source)
        self.assertIn('target_control_agent="$release_root/source/deploy/worker/ubuntu/worker-control-agent.py"', self.source)
        self.assertIn("activation target lacks complete worker-control components", self.source)
        self.assertIn("verify-runtime-progression.py", self.source)
        self.assertIn("--heartbeat", self.source)
        self.assertIn("--expected-commit", self.source)
        self.assertIn("frame/state progression gate failed", self.source)
        self.assertIn("RUNTIME_GATE frame_and_state_progression=PASS", self.source)
        self.assertIn("active-source-commit", self.source)
        self.assertIn('/runtimes/$runtime_id/venv/bin/python', self.source)
        self.assertIn("worker unit does not reference requested runtime ID", self.source)

    def test_intentional_stopped_state_is_preserved_without_runtime_gate(self) -> None:
        self.assertIn('desired_state_file="$install_root/shared/runtime/operator-desired-state"', self.source)
        self.assertIn('desired_state="running"', self.source)
        self.assertIn('if [[ "$desired_state" == "stopped" ]]', self.source)
        self.assertIn('systemctl stop "$service_name"', self.source)
        self.assertIn("RUNTIME_GATE skipped_reason=operator_desired_stopped", self.source)
        self.assertIn("SERVICE_STOPPED", self.source)
        self.assertIn('control_service_name="sea-speed-worker-control.service"', self.source)
        self.assertIn('systemctl restart "$control_service_name"', self.source)
        self.assertIn("CONTROL_SERVICE_ACTIVE", self.source)

    def test_failed_activation_restores_previous_release_runtime_and_desired_state(self) -> None:
        self.assertIn("unit-backup.XXXXXX", self.source)
        self.assertIn("control-unit-backup.XXXXXX", self.source)
        self.assertIn("restore_previous()", self.source)
        self.assertIn("RESTORE previous_source_commit=", self.source)
        self.assertIn("RESTORED previous_source_commit=", self.source)
        self.assertIn("previous_runtime_id", self.source)
        self.assertIn("ACTIVATION_ABORTED target=", self.source)
        self.assertIn("ACTIVE_MARKER_UNCHANGED", self.source)
        self.assertIn("automatic_on_activation_failure=true", self.source)
        restore = self.source.split("restore_previous() {", 1)[1].split("abort_activation() {", 1)[0]
        self.assertIn('if [[ "$desired_state" == "running" ]]', restore)
        self.assertIn('systemctl restart "$service_name"', restore)
        self.assertIn('systemctl stop "$service_name"', restore)

    def test_failed_activation_restores_legacy_absent_control_topology(self) -> None:
        self.assertIn("previous_control_present=false", self.source)
        self.assertIn("previous_control_enabled=false", self.source)
        self.assertIn("previous_control_active=false", self.source)
        self.assertIn("restore_previous_control()", self.source)
        control_restore = self.source.split("restore_previous_control() {", 1)[1].split("restore_previous() {", 1)[0]
        self.assertIn('systemctl stop "$control_service_name"', control_restore)
        self.assertIn('systemctl disable "$control_service_name"', control_restore)
        self.assertIn('rm -f "$control_unit_target"', control_restore)
        self.assertIn('[[ ! -e "$control_unit_target" ]]', control_restore)
        self.assertIn('! systemctl is-enabled --quiet "$control_service_name"', control_restore)
        self.assertIn('! systemctl is-active --quiet "$control_service_name"', control_restore)
        self.assertIn("control_present=%s", self.source)

    def test_existing_control_topology_is_exact_source_checked_before_mutation(self) -> None:
        self.assertIn("installed control unit and active source marker disagree", self.source)
        self.assertIn("running control service and active source marker disagree", self.source)
        self.assertIn("worker control service state exists without an installed control unit", self.source)
        self.assertIn('systemctl is-enabled --quiet "$control_service_name"', self.source)
        self.assertIn('systemctl is-active --quiet "$control_service_name"', self.source)

    def test_shared_state_releases_and_runtimes_are_preserved(self) -> None:
        self.assertIn("PRESERVED shared_config_models_datasets_output=true", self.source)
        self.assertNotIn('rm -rf "$install_root/shared', self.source)
        self.assertNotIn('rm -rf "$install_root/releases', self.source)
        self.assertNotIn('rm -rf "$install_root/runtimes', self.source)
        self.assertNotIn("git pull", self.source)

    def test_prepared_release_is_marked_for_explicit_rollback(self) -> None:
        self.assertIn("quality-approved", self.source)
        self.assertIn("quality_check=quality-integration", self.source)
        self.assertIn("rollback-exact.sh", self.source)
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("UBUNTU_WORKER_ROLLBACK.md", doc)
        self.assertIn("Runtime remains `UNKNOWN`", doc)
        self.assertIn("--workflow-file quality-integration.yml", doc)
        self.assertIn("legacy baseline", doc)


if __name__ == "__main__":
    unittest.main()
