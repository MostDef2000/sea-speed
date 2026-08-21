from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/worker/ubuntu/authentik/reconcile-blueprint.sh"

NEW_BLUEPRINT = """version: 1
entries:
  - model: authentik_core.group
    identifiers:
      name: Sea Speed Owner
    attrs:
      is_superuser: true
  - model: authentik_policies_password.passwordpolicy
    identifiers:
      name: sea-speed-password-policy
    attrs:
      length_min: 15
  - model: authentik_stages_authenticator_validate.authenticatorvalidatestage
    identifiers:
      name: sea-speed-owner-totp
    attrs:
      not_configured_action: deny
  - model: authentik_stages_user_login.userloginstage
    identifiers:
      name: sea-speed-authentication-login
    attrs:
      session_duration: days=30
      remember_me_offset: seconds=0
      remember_device: seconds=0
  - model: authentik_stages_user_login.userloginstage
    identifiers:
      name: sea-speed-enrollment-login
    attrs:
      session_duration: days=30
      remember_me_offset: seconds=0
      remember_device: seconds=0
"""

OLD_BLUEPRINT = NEW_BLUEPRINT.replace("session_duration: days=30", "session_duration: hours=12")


class UbuntuAuthentikBlueprintReconcileTests(unittest.TestCase):
    def _sandbox(self, old: str = OLD_BLUEPRINT, *, active_mode: int = 0o644):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        runtime = root / "runtime"
        (runtime / "blueprints").mkdir(parents=True)
        (runtime / "compose.yml").write_text("name: fake-authentik\n", encoding="utf-8")
        active = runtime / "blueprints/sea-speed-auth-v1.yaml"
        active.write_text(old, encoding="utf-8")
        active.chmod(active_mode)
        source = root / "source.yaml"
        source.write_text(NEW_BLUEPRINT, encoding="utf-8")
        apply_marker = root / "explicit-apply.marker"
        bindir = root / "bin"
        bindir.mkdir()
        docker = bindir / "docker"
        docker.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
blueprint=\"${SEA_SPEED_AUTHENTIK_FAKE_BLUEPRINT:?}\"
apply_marker=\"${SEA_SPEED_AUTHENTIK_FAKE_APPLY_MARKER:?}\"
if [[ \"$*\" == *\"ak apply_blueprint /blueprints/sea-speed-auth-v1.yaml\"* ]]; then
  : > \"$apply_marker\"
  exit 0
fi
mode=\"$(stat -c '%a' \"$blueprint\")\"
if [[ \"${SEA_SPEED_AUTHENTIK_FAKE_STUCK:-0}\" == 1 ]] || grep -q 'session_duration: hours=12' \"$blueprint\"; then
  duration=hours=12
elif [[ \"${SEA_SPEED_AUTHENTIK_FAKE_REQUIRE_APPLY:-0}\" == 1 && ! -f \"$apply_marker\" ]]; then
  duration=hours=12
elif [[ \"$mode\" != 644 ]]; then
  # Reproduce the production failure mode where the bind-mounted file was
  # chmod 0600 and Authentik discovery could not read it across Docker's
  # user-namespace boundary. ORM state therefore never advanced to days=30.
  duration=hours=12
else
  duration=days=30
fi
printf 'SEA_SPEED_SESSION_STAGE=sea-speed-authentication-login|%s|seconds=0|seconds=0\\n' \"$duration\"
printf 'SEA_SPEED_SESSION_STAGE=sea-speed-enrollment-login|%s|seconds=0|seconds=0\\n' \"$duration\"
""",
            encoding="utf-8",
        )
        docker.chmod(0o755)
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{bindir}:{env['PATH']}",
                "SEA_SPEED_AUTHENTIK_RECONCILE_TEST_MODE": "1",
                "SEA_SPEED_AUTHENTIK_RECONCILE_ATTEMPTS": "1",
                "SEA_SPEED_AUTHENTIK_RECONCILE_SLEEP_SECONDS": "0",
                "SEA_SPEED_AUTHENTIK_FAKE_BLUEPRINT": str(active),
                "SEA_SPEED_AUTHENTIK_FAKE_APPLY_MARKER": str(apply_marker),
            }
        )
        return temp, runtime, active, source, apply_marker, env

    def test_shell_syntax_and_fixed_mutation_boundary(self) -> None:
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('/blueprints/sea-speed-auth-v1.yaml', text)
        self.assertIn('docker compose exec -T worker ak apply_blueprint "$container_blueprint"', text)
        self.assertIn('docker compose exec -T worker ak shell -c', text)
        self.assertIn('AUTHENTIK_SESSION_DURATION=days=30', text)
        self.assertIn('AUTHENTIK_BLUEPRINT_MODE=0644', text)
        self.assertIn('AUTHENTIK_BLUEPRINT_APPLY=EXPLICIT', text)
        self.assertIn('WATER_ROAD_SERVICES_MUTATED=NO', text)
        self.assertNotIn('docker compose pull', text)
        self.assertNotIn('systemctl restart sea-speed-worker', text)
        self.assertNotIn('systemctl restart sea-speed-road-worker', text)
        self.assertNotIn('systemctl restart postgresql', text)

    def test_reconcile_updates_existing_mount_and_verifies_two_login_stages(self) -> None:
        temp, runtime, active, source, apply_marker, env = self._sandbox()
        with temp:
            result = subprocess.run(
                ["bash", str(SCRIPT), "--source", str(source), "--runtime-root", str(runtime)],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(active.read_text(encoding="utf-8"), NEW_BLUEPRINT)
            self.assertEqual(active.stat().st_mode & 0o777, 0o644)
            self.assertTrue(apply_marker.exists())
            self.assertIn("AUTHENTIK_BLUEPRINT_RECONCILE=PASS", result.stdout)
            self.assertIn("AUTHENTIK_LOGIN_STAGES_VERIFIED=2", result.stdout)
            self.assertIn("AUTHENTIK_BLUEPRINT_CHANGED=YES", result.stdout)
            self.assertIn("AUTHENTIK_BLUEPRINT_MODE=0644", result.stdout)
            self.assertIn("AUTHENTIK_BLUEPRINT_APPLY=EXPLICIT", result.stdout)
            self.assertIn("AUTHENTIK_WORKER_RESTARTED=NO", result.stdout)

    def test_reconcile_explicitly_applies_when_watcher_is_inert(self) -> None:
        temp, runtime, active, source, apply_marker, env = self._sandbox()
        with temp:
            env["SEA_SPEED_AUTHENTIK_FAKE_REQUIRE_APPLY"] = "1"
            result = subprocess.run(
                ["bash", str(SCRIPT), "--source", str(source), "--runtime-root", str(runtime)],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertTrue(apply_marker.exists())
            self.assertEqual(active.read_text(encoding="utf-8"), NEW_BLUEPRINT)
            self.assertIn("AUTHENTIK_BLUEPRINT_APPLY=EXPLICIT", result.stdout)
            self.assertIn("AUTHENTIK_SESSION_DURATION=days=30", result.stdout)

    def test_reconcile_repairs_unreadable_bind_mount_mode(self) -> None:
        temp, runtime, active, source, _apply_marker, env = self._sandbox(active_mode=0o600)
        with temp:
            result = subprocess.run(
                ["bash", str(SCRIPT), "--source", str(source), "--runtime-root", str(runtime)],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(active.read_text(encoding="utf-8"), NEW_BLUEPRINT)
            self.assertEqual(active.stat().st_mode & 0o777, 0o644)
            self.assertIn("AUTHENTIK_BLUEPRINT_RECONCILE=PASS", result.stdout)
            self.assertIn("AUTHENTIK_SESSION_DURATION=days=30", result.stdout)

    def test_idempotent_runtime_does_not_rewrite_or_restart(self) -> None:
        temp, runtime, active, source, apply_marker, env = self._sandbox(NEW_BLUEPRINT)
        with temp:
            before = active.stat().st_ino
            result = subprocess.run(
                ["bash", str(SCRIPT), "--source", str(source), "--runtime-root", str(runtime)],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(active.stat().st_ino, before)
            self.assertEqual(active.stat().st_mode & 0o777, 0o644)
            self.assertFalse(apply_marker.exists())
            self.assertIn("AUTHENTIK_BLUEPRINT_CHANGED=NO", result.stdout)
            self.assertIn("AUTHENTIK_BLUEPRINT_APPLY=NOT_REQUIRED", result.stdout)
            self.assertIn("AUTHENTIK_WORKER_RESTARTED=NO", result.stdout)

    def test_failed_runtime_apply_restores_previous_blueprint_and_fails_closed(self) -> None:
        temp, runtime, active, source, apply_marker, env = self._sandbox(active_mode=0o600)
        with temp:
            env["SEA_SPEED_AUTHENTIK_FAKE_STUCK"] = "1"
            result = subprocess.run(
                ["bash", str(SCRIPT), "--source", str(source), "--runtime-root", str(runtime)],
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 20)
            self.assertEqual(active.read_text(encoding="utf-8"), OLD_BLUEPRINT)
            self.assertEqual(active.stat().st_mode & 0o777, 0o644)
            self.assertTrue(apply_marker.exists())
            self.assertIn("AUTHENTIK_BLUEPRINT_ROLLBACK=PASS", result.stderr)
            self.assertIn("AUTHENTIK_BLUEPRINT_MODE=0644", result.stderr)

    def test_source_guard_rejects_legacy_session_duration(self) -> None:
        temp, runtime, _active, source, _apply_marker, env = self._sandbox()
        with temp:
            source.write_text(OLD_BLUEPRINT, encoding="utf-8")
            result = subprocess.run(
                ["bash", str(SCRIPT), "--source", str(source), "--runtime-root", str(runtime)],
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("expected 2, found 0", result.stderr)


if __name__ == "__main__":
    unittest.main()
