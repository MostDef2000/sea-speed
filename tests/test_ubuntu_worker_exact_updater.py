from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "deploy/worker/ubuntu/update-exact.sh"
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

    def test_quality_gate_fails_closed_with_protected_token(self) -> None:
        self.assertIn("verify_quality_status.py", self.source)
        self.assertIn("--required-name quality-integration", self.source)
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

    def test_activation_requires_exact_runtime_progression_and_dual_binding(self) -> None:
        self.assertIn("--activate", self.source)
        self.assertIn("NOT_ACTIVATED explicit_flag_required=--activate", self.source)
        self.assertIn("verify-runtime-progression.py", self.source)
        self.assertIn("--heartbeat", self.source)
        self.assertIn("--expected-commit", self.source)
        self.assertIn("frame/state progression gate failed", self.source)
        self.assertIn("RUNTIME_GATE frame_and_state_progression=PASS", self.source)
        self.assertIn("active-source-commit", self.source)
        self.assertIn('/runtimes/$runtime_id/venv/bin/python', self.source)
        self.assertIn("active unit does not reference requested runtime ID", self.source)

    def test_failed_activation_restores_previous_release_and_runtime_binding(self) -> None:
        self.assertIn("unit-backup.XXXXXX", self.source)
        self.assertIn("restore_previous()", self.source)
        self.assertIn("RESTORE previous_source_commit=", self.source)
        self.assertIn("RESTORED previous_source_commit=", self.source)
        self.assertIn("previous_runtime_id", self.source)
        self.assertIn("ACTIVATION_ABORTED target=", self.source)
        self.assertIn("ACTIVE_MARKER_UNCHANGED", self.source)
        self.assertIn("automatic_on_activation_failure=true", self.source)

        restore = self.source.split("restore_previous() {", 1)[1].split(
            "abort_activation() {", 1
        )[0]
        reset = 'systemctl reset-failed "$service_name"'
        restart = 'systemctl restart "$service_name"'
        self.assertIn(reset, restore)
        self.assertIn(restart, restore)
        self.assertLess(restore.index(reset), restore.index(restart))

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


if __name__ == "__main__":
    unittest.main()
