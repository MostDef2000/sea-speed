from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class UbuntuZeroTouchTransportTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_workflow_uses_vps_proxyjump_and_zero_operator_fallback(self):
        workflow = self.read(".github/workflows/deploy-ubuntu-worker.yml")
        for marker in (
            "UBUNTU_DEPLOY_SSH_PRIVATE_KEY",
            "UBUNTU_DEPLOY_SSH_KNOWN_HOSTS",
            "VPS_SSH_PRIVATE_KEY",
            "VPS_SSH_KNOWN_HOSTS",
            "ProxyJump sea-speed-vps-jump",
            "HostName 10.123.239.102",
            "User sea-speed-deploy",
            "StrictHostKeyChecking yes",
            "ClearAllForwardings yes",
            "sea-speed-ubuntu-deploy-v1",
            "Operator actions expected: 0",
        ):
            self.assertIn(marker, workflow)
        self.assertNotIn("ubuntu-worker-one-command.sh", workflow)
        self.assertNotIn("Build one-command fallback", workflow)
        self.assertNotIn("StrictHostKeyChecking=no", workflow)

    def test_gate_is_exact_forced_command_and_recomputes_artifact(self):
        gate = self.read("scripts/operations/sea_speed_ubuntu_zero_touch_gate.sh")
        self.assertIn("SSH_ORIGINAL_COMMAND", gate)
        self.assertIn("^sea-speed-ubuntu-deploy-v1", gate)
        self.assertIn("target is not on current main first-parent history", gate)
        self.assertIn("build_exact_artifacts.py", gate)
        self.assertIn("artifact SHA-256 does not match deterministic exact Ubuntu artifact", gate)
        self.assertIn("deploy/worker/ubuntu/deploy-authorized.sh", gate)
        self.assertIn('exec sudo -n "$GATE_PATH" --execute', gate)
        self.assertNotIn("eval ", gate)
        self.assertNotIn("bash -c \"$SSH_ORIGINAL_COMMAND\"", gate)

    def test_bootstrap_installs_only_dedicated_restricted_boundary(self):
        bootstrap = self.read("scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh")
        self.assertIn('readonly DEPLOY_USER="sea-speed-deploy"', bootstrap)
        self.assertIn('restrict,command="%s"', bootstrap)
        self.assertIn("visudo -cf", bootstrap)
        self.assertIn("NOPASSWD:", bootstrap)
        self.assertIn("sea-speed-ubuntu-zero-touch-gate --execute *", bootstrap)
        self.assertNotIn("NOPASSWD: ALL", bootstrap)
        self.assertNotIn("ssh-keygen -t", bootstrap)
        self.assertIn("--remove", bootstrap)

    def test_bootstrap_disables_password_without_locking_public_key_account(self):
        bootstrap = self.read("scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh")
        self.assertIn("usermod --password '*NP*' \"$DEPLOY_USER\"", bootstrap)
        self.assertIn('getent shadow "$DEPLOY_USER"', bootstrap)
        self.assertIn("PASSWORD_AUTH=DISABLED_PUBLICKEY_ACCOUNT=ACCESSIBLE", bootstrap)
        self.assertIn("deploy account password-auth boundary mismatch", bootstrap)
        self.assertNotIn('passwd -l "$DEPLOY_USER"', bootstrap)
        self.assertIn('usermod -L "$DEPLOY_USER"', bootstrap)

    def test_bootstrap_transactionally_admits_deploy_user_to_existing_sshd_allowlist(self):
        bootstrap = self.read("scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh")
        self.assertIn('/etc/ssh/sshd_config.d/00-sea-speed-hardening.conf', bootstrap)
        self.assertIn("set_allowusers_membership add", bootstrap)
        self.assertIn("set_allowusers_membership remove", bootstrap)
        self.assertIn("restore_sshd_hardening", bootstrap)
        self.assertIn("AllowUsers", bootstrap)
        self.assertIn("sshd -t", bootstrap)
        self.assertIn("systemctl reload ssh", bootstrap)
        self.assertIn("systemctl reload sshd", bootstrap)
        self.assertIn("original config restored", bootstrap)
        self.assertIn("deploy principal missing from effective AllowUsers", bootstrap)
        self.assertIn("existing AllowUsers principal missing after reload", bootstrap)
        self.assertIn("SSHD_ALLOWUSERS=", bootstrap)
        self.assertIn('new_users+=("$DEPLOY_USER")', bootstrap)
        self.assertIn('new_users+=("$principal")', bootstrap)
        self.assertNotIn("AllowUsers sea-speed-deploy\n", bootstrap)

    def test_effective_allowusers_parser_accumulates_all_sshd_rows(self):
        bootstrap = self.read("scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh")
        start = bootstrap.index("effective_allowusers() {")
        end = bootstrap.index("\n}\n\nallowusers_contains()", start)
        parser = bootstrap[start:end]
        self.assertIn("BEGIN { emitted = 0 }", parser)
        self.assertIn('printf "%s%s", (emitted ? " " : ""), $i', parser)
        self.assertIn("emitted = 1", parser)
        self.assertIn("if (emitted)", parser)
        self.assertNotIn("\n      exit\n", parser)

    def test_source_protection_is_checked_before_transport(self):
        for path in (
            ".github/workflows/deploy-runtime-autonomous.yml",
            ".github/workflows/deploy-vps.yml",
            ".github/workflows/deploy-ubuntu-worker.yml",
        ):
            source = self.read(path)
            self.assertIn("verify_source_protection.py", source, path)
            self.assertIn("Repository validation", source, path)
            self.assertIn("quality-integration", source, path)
        ubuntu = self.read(".github/workflows/deploy-ubuntu-worker.yml")
        self.assertLess(ubuntu.index("verify_source_protection.py"), ubuntu.index("Configure restricted VPS ProxyJump"))


if __name__ == "__main__":
    unittest.main()
