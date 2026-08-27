from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "deploy/vps/sea-speed-nginx-zerotier-wait.sh"
DROPIN = ROOT / "deploy/vps/sea-speed-nginx-zerotier.conf"
INSTALLER = ROOT / "deploy/vps/install-auth-privilege-boundary.sh"
SOURCE_SHA = "a" * 40
FIXED_ADDRESS = "10.123.239.101"


class WaitHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fake_bin = Path(self.temp.name) / "bin"
        self.fake_bin.mkdir()

    def write_fake(self, name: str, content: str) -> Path:
        path = self.fake_bin / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
        return path

    def run_helper(self, *, args: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PATH"] = str(self.fake_bin) + os.pathsep + env.get("PATH", "")
        return subprocess.run(
            [shutil.which("bash") or "/bin/bash", str(HELPER), *args],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_immediate_address_success(self) -> None:
        self.write_fake(
            "ip",
            f"""#!/usr/bin/env bash
echo "1: lo inet 127.0.0.1/8 scope host lo"
echo "2: zt0 inet {FIXED_ADDRESS}/24 brd 10.123.239.255 scope global zt0"
""",
        )
        self.write_fake("sleep", "#!/usr/bin/env bash\nexit 0\n")
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("NGINX_ZEROTIER_ADDRESS_READY=PASS", result.stdout)
        self.assertIn(f"FIXED_ADDRESS={FIXED_ADDRESS}", result.stdout)
        self.assertIn("ATTEMPTS=1", result.stdout)

    def test_delayed_address_success(self) -> None:
        state_file = Path(self.temp.name) / "attempts.txt"
        state_file.write_text("0", encoding="utf-8")
        self.write_fake(
            "ip",
            f"""#!/usr/bin/env bash
count=$(cat {state_file})
next=$((count + 1))
echo "$next" > {state_file}
if [[ "$next" -lt 4 ]]; then
  echo "1: lo inet 127.0.0.1/8 scope host lo"
else
  echo "1: lo inet 127.0.0.1/8 scope host lo"
  echo "2: zt0 inet {FIXED_ADDRESS}/24 brd 10.123.239.255 scope global zt0"
fi
""",
        )
        self.write_fake("sleep", "#!/usr/bin/env bash\nexit 0\n")
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("NGINX_ZEROTIER_ADDRESS_READY=PASS", result.stdout)
        self.assertIn("ATTEMPTS=4", result.stdout)

    def test_timeout_returns_service_failure(self) -> None:
        state_file = Path(self.temp.name) / "attempts.txt"
        state_file.write_text("0", encoding="utf-8")
        self.write_fake(
            "ip",
            f"""#!/usr/bin/env bash
count=$(cat {state_file})
echo $((count + 1)) > {state_file}
echo "1: lo inet 127.0.0.1/8 scope host lo"
""",
        )
        self.write_fake("sleep", "#!/usr/bin/env bash\nexit 0\n")
        result = self.run_helper()
        self.assertEqual(result.returncode, 255, result.stdout)
        self.assertEqual(state_file.read_text(encoding="utf-8").strip(), "24")
        self.assertIn("ERROR fixed ZeroTier address", result.stdout)
        self.assertIn("24 attempts", result.stdout)

    def test_arguments_rejected(self) -> None:
        self.write_fake("ip", "#!/usr/bin/env bash\nexit 0\n")
        self.write_fake("sleep", "#!/usr/bin/env bash\nexit 0\n")
        result = self.run_helper(args=("unexpected",))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("accepts no arguments", result.stdout)

    def test_missing_required_command_is_service_failure(self) -> None:
        self.write_fake("ip", "#!/usr/bin/env bash\nexit 0\n")
        env = {"PATH": str(self.fake_bin)}
        result = subprocess.run(
            [shutil.which("bash") or "/bin/bash", str(HELPER)],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 255, result.stdout)
        self.assertIn("command is required", result.stdout)

    def test_fixed_topology_and_no_selectable_runtime(self) -> None:
        text = HELPER.read_text(encoding="utf-8")
        self.assertIn(f'FIXED_ADDRESS="{FIXED_ADDRESS}"', text)
        self.assertIn("MAX_ATTEMPTS=24", text)
        self.assertIn("INTERVAL_SECONDS=5", text)
        for forbidden in ("argparse", "getopt", "os.environ", "sys.argv", "0.0.0.0", "wildcard"):
            self.assertNotIn(forbidden, text)


class SystemdDropInTests(unittest.TestCase):
    def test_required_directives_present(self) -> None:
        text = DROPIN.read_text(encoding="utf-8")
        self.assertIn("Wants=zerotier-one.service", text)
        self.assertIn("After=zerotier-one.service", text)
        self.assertIn("ExecCondition=/usr/local/sbin/sea-speed-nginx-zerotier-wait", text)
        self.assertIn("Restart=on-failure", text)
        self.assertIn("RestartSec=10s", text)
        self.assertIn("StartLimitIntervalSec=0", text)
        timeout_line = next(line for line in text.splitlines() if line.startswith("TimeoutStartSec="))
        seconds = int(timeout_line.split("=", 1)[1].rstrip("s"))
        self.assertGreaterEqual(seconds, 120)
        unit, service = text.split("[Service]", 1)
        self.assertIn("StartLimitIntervalSec=0", unit)
        self.assertNotIn("StartLimitIntervalSec", service)
        for directive in (
            "ExecCondition=/usr/local/sbin/sea-speed-nginx-zerotier-wait",
            "Restart=on-failure",
            "RestartSec=10s",
            "TimeoutStartSec=130s",
        ):
            self.assertIn(directive, service)

    def test_systemd_accepts_unit_and_dropin_syntax(self) -> None:
        analyzer = shutil.which("systemd-analyze")
        if analyzer is None:
            self.skipTest("systemd-analyze is unavailable")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "nginx.service.d").mkdir()
            (root / "nginx.service").write_text(
                "[Unit]\nDescription=test nginx\n"
                "[Service]\nType=oneshot\nExecStart=/bin/true\n",
                encoding="utf-8",
            )
            (root / "zerotier-one.service").write_text(
                "[Unit]\nDescription=test zerotier\n"
                "[Service]\nType=oneshot\nExecStart=/bin/true\n",
                encoding="utf-8",
            )
            shutil.copy2(DROPIN, root / "nginx.service.d" / DROPIN.name)
            env = os.environ.copy()
            env["SYSTEMD_UNIT_PATH"] = str(root)
            result = subprocess.run(
                [analyzer, "verify", "nginx.service"],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_forbidden_directives_absent(self) -> None:
        text = DROPIN.read_text(encoding="utf-8")
        self.assertNotIn("Requires=", text)
        self.assertNotIn("0.0.0.0", text)
        self.assertNotIn("Restart=no", text)


class PrivilegeInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.test_root = self.root / "target"
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.write_fakes()

    def write_executable(self, name: str, content: str) -> Path:
        path = self.fake_bin / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
        return path

    def write_fakes(self) -> None:
        current_uid = os.getuid()
        current_gid = os.getgid()
        deployment_uid = current_uid if current_uid != 0 else 1000
        self.write_executable(
            "id",
            f"""#!/usr/bin/env bash
set -euo pipefail
if [[ "${{1:-}}" == "-u" && $# -eq 1 ]]; then echo {current_uid}; exit 0; fi
if [[ "${{1:-}}" == "-g" && $# -eq 1 ]]; then echo {current_gid}; exit 0; fi
if [[ "${{1:-}}" == "-u" && "${{2:-}}" == "deployuser" ]]; then echo {deployment_uid}; exit 0; fi
exit 1
""",
        )
        self.write_executable(
            "git",
            f"""#!/usr/bin/env bash
set -euo pipefail
case "$*" in
  *" rev-parse HEAD") echo {SOURCE_SHA} ;;
  *" remote get-url origin") echo https://github.com/MostDef2000/sea-speed.git ;;
  *) echo "unexpected fake git invocation: $*" >&2; exit 64 ;;
esac
""",
        )
        self.write_executable("visudo", "#!/usr/bin/env bash\nset -euo pipefail\n[[ \"${1:-}\" == '-cf' && -f \"${2:-}\" ]]\n")

    def env(self, *, fail_after_install: bool = False) -> dict[str, str]:
        env = os.environ.copy()
        env["PATH"] = str(self.fake_bin) + os.pathsep + env.get("PATH", "")
        env["SEA_SPEED_PRIVILEGE_BOUNDARY_TEST_ROOT"] = str(self.test_root)
        if fail_after_install:
            env["SEA_SPEED_PRIVILEGE_BOUNDARY_TEST_FAIL_AFTER_INSTALL"] = "1"
        return env

    def run_installer(self, *, fail_after_install: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(INSTALLER), SOURCE_SHA, "deployuser"],
            cwd=ROOT,
            env=self.env(fail_after_install=fail_after_install),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_installer_creates_zerotier_wait_helper_and_dropin(self) -> None:
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout)
        helper_path = self.test_root / "usr/local/sbin/sea-speed-nginx-zerotier-wait"
        dropin_path = self.test_root / "etc/systemd/system/nginx.service.d/sea-speed-nginx-zerotier.conf"
        self.assertTrue(helper_path.is_file())
        self.assertTrue(dropin_path.is_file())
        self.assertEqual(stat.S_IMODE(helper_path.stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE(dropin_path.stat().st_mode), 0o644)
        self.assertEqual(helper_path.read_text(encoding="utf-8"), HELPER.read_text(encoding="utf-8"))
        self.assertEqual(dropin_path.read_text(encoding="utf-8"), DROPIN.read_text(encoding="utf-8"))
        self.assertIn("NGINX_ZEROTIER_WAIT_HELPER=INSTALLED", result.stdout)
        self.assertIn("NGINX_ZEROTIER_DROPIN=INSTALLED", result.stdout)
        self.assertIn("NGINX_ZEROTIER_STARTUP=TEST_ROOT_NOT_ACTIVATED", result.stdout)

    def test_injected_failure_restores_prior_zerotier_assets(self) -> None:
        helper_path = self.test_root / "usr/local/sbin/sea-speed-nginx-zerotier-wait"
        dropin_path = self.test_root / "etc/systemd/system/nginx.service.d/sea-speed-nginx-zerotier.conf"
        helper_path.parent.mkdir(parents=True, exist_ok=True)
        dropin_path.parent.mkdir(parents=True, exist_ok=True)
        helper_path.write_text("old-wait-helper\n", encoding="utf-8")
        dropin_path.write_text("old-dropin\n", encoding="utf-8")

        result = self.run_installer(fail_after_install=True)
        self.assertEqual(result.returncode, 90, result.stdout)
        self.assertEqual(helper_path.read_text(encoding="utf-8"), "old-wait-helper\n")
        self.assertEqual(dropin_path.read_text(encoding="utf-8"), "old-dropin\n")
        self.assertIn("SEA_SPEED_AUTH_PRIVILEGE_INSTALL_ROLLBACK=PASS", result.stdout)

    def test_sudoers_remains_one_fixed_helper_with_explicit_no_arguments(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('NOPASSWD: ${HELPER_PATH#${PREFIX}} ""', text)
        for forbidden in ("NOPASSWD: ALL", "NOPASSWD: /bin/bash", "NOPASSWD: /usr/bin/python", "NOPASSWD: /usr/sbin/nginx"):
            self.assertNotIn(forbidden, text)

    def test_production_path_reloads_restarts_and_verifies_nginx(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        preflight = text.index('bash "$NGINX_WAIT_SOURCE"')
        mutation = text.index("MUTATED=1")
        self.assertLess(preflight, mutation)
        self.assertIn("NGINX_ZEROTIER_PREMUTATION=PASS", text)
        self.assertIn("systemctl daemon-reload", text)
        self.assertIn("systemctl restart nginx.service", text)
        self.assertIn("systemctl is-active --quiet nginx.service", text)
        self.assertIn("NGINX_ZEROTIER_STARTUP=ACTIVE", text)

    def test_rollback_restores_prior_nginx_state(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("PREV_NGINX_ENABLED", text)
        self.assertIn("PREV_NGINX_ACTIVE", text)
        self.assertIn("restore_nginx_runtime", text)
        self.assertIn("systemctl start nginx.service", text)
        self.assertIn("systemctl stop nginx.service", text)
        self.assertIn('restore_path "$NGINX_WAIT_HELPER_PATH" nginx-wait-helper', text)
        self.assertIn('restore_path "$NGINX_DROPIN_PATH" nginx-dropin', text)


class ExactArtifactTests(unittest.TestCase):
    def test_new_assets_are_in_vps_artifact_inventory(self) -> None:
        text = (ROOT / "scripts/quality/build_exact_artifacts.py").read_text(encoding="utf-8")
        self.assertIn("deploy/vps/sea-speed-nginx-zerotier-wait.sh", text)
        self.assertIn("deploy/vps/sea-speed-nginx-zerotier.conf", text)
        text = (ROOT / "scripts/quality/validate_exact_artifacts.py").read_text(encoding="utf-8")
        self.assertIn("deploy/vps/sea-speed-nginx-zerotier-wait.sh", text)
        self.assertIn("deploy/vps/sea-speed-nginx-zerotier.conf", text)
        self.assertIn("sea-speed-nginx-zerotier-wait.sh", text)


if __name__ == "__main__":
    unittest.main()
