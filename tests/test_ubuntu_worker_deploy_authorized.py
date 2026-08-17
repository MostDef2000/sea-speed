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

    def test_authorization_config_reconciliation_activation_and_verification_order(self) -> None:
        authorization = self.source.index("verify_production_authorization.py")
        backup = self.source.index("if ! backup_protected_config")
        configure = self.source.index('python3 "$stage/deploy/worker/ubuntu/configure-analytics-profiles.py"')
        mutation = self.source.index('bash "$stage/deploy/worker/ubuntu/update-exact.sh"')
        verification = self.source.index("if ! verify_active_target")
        manifest = self.source.index('manifest="$updater_root/deployment-manifest-ubuntu-worker.json"')
        self.assertLess(authorization, backup)
        self.assertLess(backup, configure)
        self.assertLess(configure, mutation)
        self.assertLess(mutation, verification)
        self.assertLess(verification, manifest)
        for marker in (
            "--require-execution-intent",
            "--first-parent",
            "deploy/worker/ubuntu/configure-analytics-profiles.py",
            "deploy/worker/ubuntu/update-exact.sh",
            "deploy/worker/ubuntu/rollback-exact.sh",
        ):
            self.assertIn(marker, self.source)

    def test_protected_config_backup_and_restore_are_explicit(self) -> None:
        for marker in (
            'worker_env="$install_root/shared/config/worker.env"',
            'road_env="$install_root/shared/config/road-worker.env"',
            'worker_env_backup="$(mktemp "$updater_root/worker-env-backup.XXXXXX")"',
            'road_env_backup="$(mktemp "$updater_root/road-env-backup.XXXXXX")"',
            "backup_protected_config()",
            "restore_protected_config()",
            "restore_predeployment_service_state()",
            "PROTECTED_CONFIG_BACKUP=PASS",
            "PROTECTED_CONFIG_RESTORED=YES",
            "PREDEPLOYMENT_SERVICE_STATE_RESTORED=YES",
        ):
            self.assertIn(marker, self.source)
        self.assertIn('road_env_existed=false', self.source)
        self.assertIn('rm -f "$road_env"', self.source)

    def test_configure_failure_restores_protected_config_without_activation(self) -> None:
        configure_call = self.source.index('python3 "$stage/deploy/worker/ubuntu/configure-analytics-profiles.py"')
        configure_failure = self.source.index('DEPLOY_CONFIG_ROLLED_BACK reason=configure_failed')
        updater_call = self.source.index('bash "$stage/deploy/worker/ubuntu/update-exact.sh"')
        self.assertLess(configure_call, configure_failure)
        self.assertLess(configure_failure, updater_call)
        configure_failure_block = self.source[configure_call:updater_call]
        self.assertIn("restore_protected_config", configure_failure_block)
        self.assertNotIn("systemctl restart", configure_failure_block)

    def test_updater_failure_restores_config_and_predeployment_service_state(self) -> None:
        updater_call = self.source.index('bash "$stage/deploy/worker/ubuntu/update-exact.sh"')
        verify_call = self.source.index("if ! verify_active_target")
        updater_failure_block = self.source[updater_call:verify_call]
        self.assertIn("restore_protected_config && restore_predeployment_service_state", updater_failure_block)
        self.assertIn("DEPLOY_CONFIG_ROLLED_BACK reason=updater_failed", updater_failure_block)
        self.assertIn("exact updater failed and protected predeployment state could not be restored", updater_failure_block)

    def test_post_activation_failure_restores_config_before_source_rollback(self) -> None:
        verify_call = self.source.index("if ! verify_active_target")
        runtime_manifest = self.source.index('manifest="$updater_root/deployment-manifest-ubuntu-worker.json"')
        failure_block = self.source[verify_call:runtime_manifest]
        restore = failure_block.index("restore_protected_config")
        rollback = failure_block.index('bash "$stage/deploy/worker/ubuntu/rollback-exact.sh"')
        self.assertLess(restore, rollback)
        self.assertIn("DEPLOY_ROLLED_BACK", failure_block)
        self.assertIn("config_restored=true", failure_block)
        self.assertIn("restore_predeployment_service_state", failure_block)

    def test_water_desired_state_and_prior_road_state_are_preserved(self) -> None:
        for marker in (
            'desired="$(cat "$desired_file" 2>/dev/null || echo running)"',
            'worker_was_active=false',
            'road_was_active=false',
            'if [[ "$desired" == "stopped" && "$worker_was_active" == true ]]',
            'if [[ "$road_was_active" == true ]]',
            'if [[ "$worker_was_active" == true ]]',
        ):
            self.assertIn(marker, self.source)

    def test_exact_post_activation_identity_requires_reconciled_road_worker(self) -> None:
        for marker in (
            'road_service="sea-speed-road-worker.service"',
            'road_env="$install_root/shared/config/road-worker.env"',
            'road_exec',
            'systemctl is-active --quiet "$road_service"',
            '[[ -f "$road_env" && "$(stat -c \'%a\' "$road_env")" == "600" ]]',
        ):
            self.assertIn(marker, self.source)

    def test_manifest_records_protected_config_reconciliation_without_secret_values(self) -> None:
        self.assertIn('"protected-road-profile-config-reconciled"', self.source)
        self.assertIn("protected_config_reconciled", self.source)
        self.assertIn('"road-worker-active"', self.source)
        self.assertNotIn("HLS_URL=", self.source)
        self.assertNotIn("SEA_SPEED_API_TOKEN=", self.source)

    def test_road_config_is_reconciled_from_private_runtime_inputs(self) -> None:
        configure = CONFIGURE.read_text(encoding="utf-8")
        example = ROAD_ENV_EXAMPLE.read_text(encoding="utf-8")
        self.assertIn("road_worker_api_urls", configure)
        self.assertIn("/api/cam1/state", configure)
        self.assertIn('road_env="$install_root/shared/config/road-worker.env"', self.source)
        self.assertIn('preview_catalog="/var/lib/sea-speed-camera-preview/active/camera-preview-catalog.json"', self.source)
        self.assertIn('configure-analytics-profiles.py', self.source)
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
