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
        self.assertIn('IFS= read -r GITHUB_TOKEN < "$token_file"', self.source)
        self.assertNotIn('echo "$GITHUB_TOKEN"', self.source)
        self.assertNotIn('cat "$token_file"', self.source)

    def test_updates_are_serialized_and_staged(self) -> None:
        self.assertIn("update.lock", self.source)
        self.assertIn("flock -n 9", self.source)
        self.assertIn("mktemp -d", self.source)
        self.assertIn("trap cleanup EXIT", self.source)
        self.assertIn("install-manual.sh", self.source)

    def test_activation_is_explicit_and_exact(self) -> None:
        self.assertIn("--activate", self.source)
        self.assertIn("NOT_ACTIVATED explicit_flag_required=--activate", self.source)
        self.assertIn("install-systemd.sh", self.source)
        self.assertIn('systemctl restart "$service_name"', self.source)
        self.assertIn('systemctl is-active --quiet "$service_name"', self.source)
        self.assertIn("active-source-commit", self.source)
        self.assertIn("active unit does not reference requested commit", self.source)

    def test_shared_state_and_previous_releases_are_preserved(self) -> None:
        self.assertIn("PRESERVED shared_config_models_datasets_output=true", self.source)
        self.assertNotIn('rm -rf "$install_root/shared', self.source)
        self.assertNotIn('rm -rf "$install_root/releases', self.source)
        self.assertNotIn("git pull", self.source)

    def test_rollback_is_explicitly_out_of_scope(self) -> None:
        self.assertIn("automatic rollback is not implemented", self.source)
        self.assertNotIn("rollback-exact.sh", self.source)
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("Stage 5", doc)
        self.assertIn("Runtime remains `UNKNOWN`", doc)


if __name__ == "__main__":
    unittest.main()
