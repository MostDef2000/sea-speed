from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from support import relay_shell  # noqa: E402

COMPAT = ROOT / "deploy/vps/mediamtx-systemd-v247-runner.sh"
FINAL = ROOT / "deploy/vps/camera1-final-cutover.sh"


def embedded_python_program(source: str) -> str:
    """Extract the runner's heredoc patcher program VERBATIM from the real
    script bytes: the executed twin runs exactly the shipped program."""
    start = source.index("<<'PY'\n") + len("<<'PY'\n")
    end = source.index("\nPY\n", start)
    return source[start : end + 1]


class MediaMTXSystemdV247RunnerTests(unittest.TestCase):
    def test_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(COMPAT)], check=True)
        subprocess.run(["bash", "-n", str(FINAL)], check=True)

    def test_compatibility_launcher_is_exact_and_fail_closed(self) -> None:
        source = COMPAT.read_text(encoding="utf-8")
        # 398-wave3: SP pin — the approved-core digest is the byte contract
        # for the audited Issue #87 core; its literal presence is the policy.
        self.assertIn(
            'EXPECTED_CORE_SHA256="9783b12136e7d1dbc9fbeb27155a3faea13f573e6c61252bac3ac73b568c69fb"',
            source,
        )
        # The needle/replacement/count/round-trip literals are no longer pinned
        # as text: test_embedded_substitution_program_runs_verbatim executes
        # the shipped patcher program against fixture bytes (398-wave3).
        self.assertIn("SYSTEMD_PRIVATE_USERS_COMPAT=SELF_TO_YES", source)
        self.assertIn("EFFECTIVE_COMPATIBILITY_TOOL_SHA256", source)
        # 398-wave3: SP pin — sed -i must never patch the audited core in
        # place; the launcher's byte-exact runtime copy is the deploy contract.
        self.assertNotIn("sed -i", source)

    def test_prepare_has_exact_transient_sandbox_property_preflight(self) -> None:
        # 398-wave3: SP pin — this property list IS the transient-sandbox
        # policy (fail-closed systemd contract); textual presence is the pin
        # (the executed preflight needs a real systemd-run, out of scope for
        # an offline battery).
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

    def _run_final_runner(self, config_text: str, command: str) -> subprocess.CompletedProcess:
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
            config.write_text(config_text, encoding="utf-8")
            # 398-wave3: executed under an unprivileged user namespace so the
            # root-by-design runner bytes really run in this battery (the
            # historical variant skipped everywhere the suite is not root).
            return relay_shell.run_shell(
                runner,
                [command, "--config", str(config)],
                root,
                with_stubs=False,
            )

    def test_final_runner_treats_fmp4_as_already_applied(self) -> None:
        relay_shell.skip_without_user_namespace(self)
        result = self._run_final_runner(
            "hls: true\nhlsVariant: fmp4\npaths: {}\n", "prepare"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HLS_VARIANT_REMEDIATION=ALREADY_APPLIED", result.stdout)
        self.assertIn("CAMERA1_FINAL_CUTOVER_STAGE=PREPARE", result.stdout)
        self.assertIn("FAKE_COMPAT_CALLED=prepare", result.stdout)

    def test_final_runner_refuses_to_repeat_mpegts_remediation(self) -> None:
        relay_shell.skip_without_user_namespace(self)
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
            result = relay_shell.run_shell(
                runner,
                ["prepare", "--config", str(config)],
                root,
                with_stubs=False,
            )
            self.assertEqual(result.returncode, 5)
            self.assertIn("HLS_VARIANT_REMEDIATION=REQUIRED", result.stderr)
            self.assertFalse(marker.exists())

    def test_embedded_substitution_program_runs_verbatim(self) -> None:
        # 398-wave3: converted from source-text pin (was L26-L29) — the
        # executed twin extracts the runner's embedded patcher program
        # byte-for-byte and runs it against fixture cores: the approved
        # exactly-one substitution applies, round-trips, and every other
        # shape fails closed without writing the destination.
        program = embedded_python_program(COMPAT.read_text(encoding="utf-8"))
        needle = b"    --property=PrivateUsers=self\n"
        replacement = b"    --property=PrivateUsers=yes\n"
        scenarios = {
            "exactly-one": (
                b"#!/usr/bin/env bash\n" + needle + b"    --property=ProtectSystem=strict\n",
                0,
            ),
            "zero-needles": (b"#!/usr/bin/env bash\n    --property=ProtectSystem=strict\n", 1),
            "two-needles": (b"x\n" + needle + needle + b"\n", 1),
            "already-patched": (b"#!/usr/bin/env bash\n" + replacement + b"\n", 1),
        }
        for name, (core_bytes, expected_sign) in scenarios.items():
            with self.subTest(scenario=name):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    core = root / "core.sh"
                    core.write_bytes(core_bytes)
                    dst = root / "patched.sh"
                    program_file = root / "patcher.py"
                    program_file.write_text(program, encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, str(program_file), str(core), str(dst)],
                        capture_output=True,
                    )
                    if expected_sign == 0:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(dst.read_bytes(), core_bytes.replace(needle, replacement, 1))
                        # The runner's own round-trip guarantee: reverting the
                        # single substitution reproduces the audited core.
                        self.assertEqual(
                            dst.read_bytes().replace(replacement, needle, 1),
                            core_bytes,
                        )
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("PrivateUsers", result.stderr.decode("utf-8", "replace"))
                        self.assertFalse(dst.exists())

    def test_new_runners_do_not_expand_runtime_scope(self) -> None:
        # 398-wave3: SP pin — these bans are the runtime-scope boundary
        # policy (worker/nginx/sudo/ssh-trust/rollback must stay out of the
        # MediaMTX runners); byte-verbatim retention is the contract.
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
