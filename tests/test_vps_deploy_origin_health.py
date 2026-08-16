from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "deploy/vps/deploy.sh"


class VpsDeployOriginHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    def test_default_origin_health_matches_accepted_auth_v1_origin(self) -> None:
        self.assertIn(
            'ORIGIN_HEALTH_URL="${SEA_SPEED_ORIGIN_HEALTH_URL:-http://127.0.0.1:8010/api/health}"',
            self.text,
        )
        self.assertNotIn("http://127.0.0.1:8000/api/health", self.text)

    def test_deploy_and_rollback_share_the_same_origin_verifier(self) -> None:
        self.assertIn("if restart_and_verify; then", self.text)
        self.assertIn("if ! restart_and_verify; then", self.text)
        self.assertIn(
            'curl --fail --silent --show-error --max-time 10 "$ORIGIN_HEALTH_URL"',
            self.text,
        )

    def test_stale_release_pruning_is_best_effort_and_protects_rollback_pair(self) -> None:
        self.assertIn(
            'if [[ "$name" != "$current" && "$name" != "$previous" ]]; then',
            self.text,
        )
        self.assertIn('if rm -rf -- "$path"; then', self.text)
        self.assertIn(
            'log "WARNING: unable to prune stale release ${name}; leaving remaining files in place"',
            self.text,
        )
        self.assertNotIn('then rm -rf "$path"; fi', self.text)

    def test_verified_state_is_persisted_before_stale_release_pruning(self) -> None:
        success = self.text.index("if restart_and_verify; then")
        previous_write = self.text.index('> "$PREVIOUS_FILE"', success)
        current_write = self.text.index('> "$CURRENT_FILE"', previous_write)
        manifest_write = self.text.index(
            'write_deployment_manifest "$COMMIT_SHA" "$old_current" "runtime_verified" "true"',
            current_write,
        )
        prune = self.text.index("prune_releases", manifest_write)
        self.assertLess(previous_write, current_write)
        self.assertLess(current_write, manifest_write)
        self.assertLess(manifest_write, prune)


if __name__ == "__main__":
    unittest.main()
