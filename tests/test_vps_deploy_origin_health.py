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


if __name__ == "__main__":
    unittest.main()
