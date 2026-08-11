from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPAT = ROOT / "deploy/vps/mediamtx-systemd-v247-runner.sh"
FINAL = ROOT / "deploy/vps/camera1-final-cutover.sh"


class MediaMTXSystemdV247RunnerTests(unittest.TestCase):
    def test_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(COMPAT)], check=True)
        subprocess.run(["bash", "-n", str(FINAL)], check=True)

    def test_compatibility_launcher_is_exact_and_fail_closed(self) -> None:
        source = COMPAT.read_text(encoding="utf-8")
        self.assertIn(
            'EXPECTED_CORE_SHA256="9783b12136e7d1dbc9fbeb27155a3faea13f573e6c61252bac3ac73b568c69fb"',
            source,
        )
        self.assertIn('needle = b"    --property=PrivateUsers=self\\n"', source)
        self.assertIn('replacement = b"    --property=PrivateUsers=yes\\n"', source)
        self.assertIn("raw.count(needle) != 1", source)
        self.assertIn("patched.replace(replacement, needle, 1) != raw", source)
        self.assertIn("SYSTEMD_PRIVATE_USERS_COMPAT=SELF_TO_YES", source)
        self.assertIn("EFFECTIVE_COMPATIBILITY_TOOL_SHA256", source)
        self.assertNotIn("sed -i", source)

    def test_prepare_has_exact_transient_sandbox_property_preflight(self) -> None:
        source = COMPAT.read_text(encoding="utf-8")
        for contract in (
            "--property=PrivateUsers=yes",
            "--property=PrivateTmp=yes",
            "--property=PrivateDevices=yes",
            "--property=PrivateIPC=yes",
            "--property=ProtectSystem=strict",
            "--property=ProtectProc=invisible",
            "--property=ProcSubset=pid",
            "--property=RestrictNamespaces=yes",
            "--property=NoExecPaths=/",
            "--property=ExecPaths=/usr/bin/true",
            "--property=PrivateNetwork=yes",
            "SYSTEMD_SANDBOX_PREFLIGHT=PASS",
            "SYSTEMD_SANDBOX_PREFLIGHT=FAIL",
        ):
            self.assertIn(contract, source)
        self.assertIn("systemd-run --quiet --wait --collect", source)

    def test_final_runner_treats_fmp4_as_already_applied(self) -> None:
        if os.geteuid() != 0:
            self.skipTest("runner requires root by design")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = root / FINAL.name
            shutil.copy2(FINAL, runner)
            runner.chmod(0o700)
            fake_compat = root / COMPAT.name
            fake_compat.write_text(
                "#!/usr/bin/env bash\nprintf 'FAKE_COMPAT_CALLED=%s\\n' \"$1\"\n",
                encoding="utf-8",
            )
            fake_compat.chmod(0o700)
            config = root / "mediamtx.yml"
            config.write_text("hls: true\nhlsVariant: fmp4\npaths: {}\n", encoding="utf-8")
            result = subprocess.run(
                [str(runner), "prepare", "--config", str(config)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("HLS_VARIANT_REMEDIATION=ALREADY_APPLIED", result.stdout)
            self.assertIn("CAMERA1_FINAL_CUTOVER_STAGE=PREPARE", result.stdout)
            self.assertIn("FAKE_COMPAT_CALLED=prepare", result.stdout)

    def test_final_runner_refuses_to_repeat_mpegts_remediation(self) -> None:
        if os.geteuid() != 0:
            self.skipTest("runner requires root by design")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = root / FINAL.name
            shutil.copy2(FINAL, runner)
            runner.chmod(0o700)
            fake_compat = root / COMPAT.name
            marker = root / "called"
            fake_compat.write_text(
                f"#!/usr/bin/env bash\ntouch {marker}\n",
                encoding="utf-8",
            )
            fake_compat.chmod(0o700)
            config = root / "mediamtx.yml"
            config.write_text("hls: true\nhlsVariant: mpegts\npaths: {{}}\n", encoding="utf-8")
            result = subprocess.run(
                [str(runner), "prepare", "--config", str(config)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 5)
            self.assertIn("HLS_VARIANT_REMEDIATION=REQUIRED", result.stderr)
            self.assertFalse(marker.exists())

    def test_new_runners_do_not_expand_runtime_scope(self) -> None:
        source = COMPAT.read_text(encoding="utf-8") + FINAL.read_text(encoding="utf-8")
        for forbidden in (
            "sea-speed-worker.service",
            "worker.env",
            "nginx",
            "sudo -S",
            "StrictHostKeyChecking=no",
            "UserKnownHostsFile=/dev/null",
            "ROLLBACK_PERFORMED=YES",
            "systemctl restart",
            "systemctl enable",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
