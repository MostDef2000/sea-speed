from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/worker/ubuntu/deploy-authorized.sh"
CONFIGURE = ROOT / "deploy/worker/ubuntu/configure-analytics-profiles.py"
ROAD_ENV_EXAMPLE = ROOT / "deploy/worker/ubuntu/road-worker.env.example"


class UbuntuAuthorizedDeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SCRIPT.read_text(encoding="utf-8")

    def test_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_authorization_and_exact_main_gates_precede_mutation(self) -> None:
        authorization = self.source.index("verify_production_authorization.py")
        mutation = self.source.index("DEPLOY_MUTATION")
        self.assertLess(authorization, mutation)
        for marker in (
            "--require-execution-intent",
            "--first-parent",
            "deploy/worker/ubuntu/update-exact.sh",
            "deploy/worker/ubuntu/rollback-exact.sh",
        ):
            self.assertIn(marker, self.source)

    def test_exact_post_activation_identity_includes_optional_road_worker(self) -> None:
        for marker in (
            'road_service="sea-speed-road-worker.service"',
            'road_env="$install_root/shared/config/road-worker.env"',
            'road_exec',
            'systemctl is-active --quiet "$road_service"',
        ):
            self.assertIn(marker, self.source)

    def test_manifest_records_road_configuration_without_secret_values(self) -> None:
        self.assertIn(
            '{"name": "road-worker-" + ("active" if os.environ["ROAD_CONFIGURED"] == "true" else "config-pending")',
            self.source,
        )
        self.assertIn("road_configured", self.source)
        self.assertNotIn("HLS_URL=", self.source)
        self.assertNotIn("SEA_SPEED_API_TOKEN=", self.source)

    def test_road_config_is_protected_predeployment_input_not_public_api_default(self) -> None:
        configure = CONFIGURE.read_text(encoding="utf-8")
        example = ROAD_ENV_EXAMPLE.read_text(encoding="utf-8")
        self.assertIn("road_worker_api_urls", configure)
        self.assertIn("/api/cam1/state", configure)
        self.assertIn('road_env="$install_root/shared/config/road-worker.env"', self.source)
        public = "https://mostdef.ru/sea-speed/api/analytics/road1"
        self.assertNotIn(public, configure)
        self.assertNotIn(public, example)
        self.assertIn("private Worker->VPS M2M endpoint", example)

    def test_rollback_remains_automatic_on_post_activation_failure(self) -> None:
        self.assertIn("DEPLOY_ROLLED_BACK", self.source)
        self.assertIn("rollback-exact.sh", self.source)
        self.assertIn("runtimeVerified", self.source)
        self.assertIn('"state": "runtime_verified"', self.source)


if __name__ == "__main__":
    unittest.main()
