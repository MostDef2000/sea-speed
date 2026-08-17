from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "deploy/vps/sea-speed-auth-privileged-helper.py"
INSTALLER = ROOT / "deploy/vps/install-auth-privilege-boundary.sh"
SOURCE_SHA = "a" * 40

spec = importlib.util.spec_from_file_location("sea_speed_auth_privileged_helper", HELPER_PATH)
assert spec and spec.loader
helper = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helper
spec.loader.exec_module(helper)


class PrivilegedHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.releases = self.root / "opt/sea-speed-deploy/releases"
        self.release = self.releases / SOURCE_SHA
        self.bundle = self.root / "usr/local/lib/sea-speed-auth-privileged"
        self.installed_helper = self.root / "usr/local/sbin/sea-speed-auth-privileged-helper"
        self.request = self.root / "opt/sea-speed-deploy/state/auth-privileged-request.json"
        self.request.parent.mkdir(parents=True)
        self.release.mkdir(parents=True)
        (self.bundle / "repo").mkdir(parents=True)
        self.installed_helper.parent.mkdir(parents=True)
        shutil.copy2(HELPER_PATH, self.installed_helper)
        self.installed_helper.chmod(0o755)
        assets = {}
        for relative in helper.ASSET_PATHS:
            source = ROOT / relative
            installed = self.bundle / "repo" / relative
            staged = self.release / relative
            installed.parent.mkdir(parents=True, exist_ok=True)
            staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, installed)
            shutil.copy2(source, staged)
            installed.chmod(0o755 if relative.endswith(".sh") else 0o644)
            assets[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
        manifest = {
            "schema": "sea_speed_auth_privileged_bundle_v1",
            "source_sha": SOURCE_SHA,
            "helper_sha256": hashlib.sha256(self.installed_helper.read_bytes()).hexdigest(),
            "assets": assets,
        }
        (self.bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (self.bundle / "manifest.json").chmod(0o644)
        self.paths = helper.RuntimePaths(
            request_file=self.request,
            releases_root=self.releases,
            bundle_root=self.bundle,
            helper_path=self.installed_helper,
        )

    def write_request(self, action: str = "status", release_path: str | None = None) -> None:
        self.request.write_text(
            json.dumps(
                {
                    "schema": "sea_speed_auth_privileged_request_v1",
                    "action": action,
                    "source_sha": SOURCE_SHA,
                    "release_path": release_path or str(self.release),
                }
            ),
            encoding="utf-8",
        )
        self.request.chmod(0o600)

    def execute(self, action: str = "status", runner=subprocess.run) -> list[str]:
        self.write_request(action)
        return helper.execute_request(self.paths, required_uid=os.getuid(), runner=runner)

    def test_status_binds_exact_release_and_fixed_topology(self) -> None:
        lines = self.execute()
        self.assertIn("SEA_SPEED_AUTH_PRIVILEGE_BOUNDARY=PASS", lines)
        self.assertIn(f"SOURCE_SHA={SOURCE_SHA}", lines)
        self.assertIn("ACTION=status", lines)
        self.assertIn("PRIVILEGED_TOPOLOGY=FIXED", lines)
        self.assertIn("ARBITRARY_ROOT_EXECUTION=NO", lines)
        self.assertEqual(helper.AUTHENTIK_UPSTREAM, "http://10.123.239.102:19000")
        self.assertEqual(helper.WORKER_PRIVATE_LISTEN, "10.123.239.101:18080")
        self.assertEqual(helper.WORKER_PRIVATE_PEER, "10.123.239.102")

    def test_release_asset_tamper_fails_closed(self) -> None:
        target = self.release / "scripts/operations/nginx_sea_speed_auth.py"
        target.write_text(target.read_text(encoding="utf-8") + "\n# tamper\n", encoding="utf-8")
        self.write_request()
        with self.assertRaises(helper.BoundaryError):
            helper.execute_request(self.paths, required_uid=os.getuid())

    def test_release_path_escape_fails_closed(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        self.write_request(release_path=str(outside))
        with self.assertRaises(helper.BoundaryError):
            helper.execute_request(self.paths, required_uid=os.getuid())

    def test_release_asset_symlink_fails_closed(self) -> None:
        target = self.release / "scripts/operations/nginx_sea_speed_auth.py"
        target.unlink()
        target.symlink_to(ROOT / "scripts/operations/nginx_sea_speed_auth.py")
        self.write_request()
        with self.assertRaises(helper.BoundaryError):
            helper.execute_request(self.paths, required_uid=os.getuid())

    def test_request_symlink_fails_closed(self) -> None:
        actual = self.request.with_name("actual-request.json")
        self.request = actual
        self.paths = helper.RuntimePaths(
            request_file=actual.with_name("auth-privileged-request.json"),
            releases_root=self.releases,
            bundle_root=self.bundle,
            helper_path=self.installed_helper,
        )
        self.write_request()
        link = self.paths.request_file
        link.symlink_to(actual)
        with self.assertRaises(helper.BoundaryError):
            helper.execute_request(self.paths, required_uid=os.getuid())

    def test_unknown_action_fails_closed(self) -> None:
        self.write_request(action="shell")
        with self.assertRaises(helper.BoundaryError):
            helper.execute_request(self.paths, required_uid=os.getuid())

    def test_reconcile_runs_only_root_owned_cutover_with_fixed_arguments(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(argv, **kwargs):
            calls.append(list(argv))
            if "prepare" in argv:
                return subprocess.CompletedProcess(argv, 0, stdout="CANDIDATE_SHA256=" + "b" * 64 + "\nROLLBACK_CAPABILITY=VERIFIED\n")
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=(
                    "SEA_SPEED_AUTH_CUTOVER=PASS\n"
                    "WORKER_PRIVATE_ROAD_API_BASE=http://10.123.239.101:18080/api/analytics/road1\n"
                    "ROLLBACK_CAPABILITY=VERIFIED\n"
                ),
            )

        lines = self.execute("reconcile", runner=fake_runner)
        self.assertEqual(len(calls), 2)
        for argv in calls:
            self.assertEqual(argv[0], "bash")
            self.assertTrue(argv[1].startswith(str(self.bundle / "repo")))
            self.assertIn("http://10.123.239.102:19000", argv)
            self.assertIn("10.123.239.101:18080", argv)
            self.assertIn("10.123.239.102", argv)
            self.assertNotIn(str(self.release / "deploy/vps/sea-speed-auth-cutover.sh"), argv)
        self.assertIn("SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS", lines)


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

    def test_installer_creates_fixed_helper_bundle_and_minimal_sudoers(self) -> None:
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout)
        helper_path = self.test_root / "usr/local/sbin/sea-speed-auth-privileged-helper"
        manifest_path = self.test_root / "usr/local/lib/sea-speed-auth-privileged/manifest.json"
        sudoers_path = self.test_root / "etc/sudoers.d/sea-speed-auth-privileged"
        self.assertTrue(helper_path.is_file())
        self.assertTrue(manifest_path.is_file())
        self.assertTrue(sudoers_path.is_file())
        self.assertEqual(stat.S_IMODE(helper_path.stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE(sudoers_path.stat().st_mode), 0o440)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_sha"], SOURCE_SHA)
        sudoers = sudoers_path.read_text(encoding="utf-8")
        self.assertEqual(
            sudoers.strip(),
            'deployuser ALL=(root) NOPASSWD: /usr/local/sbin/sea-speed-auth-privileged-helper ""',
        )
        self.assertIn("SEA_SPEED_AUTH_PRIVILEGE_INSTALL=PASS", result.stdout)
        self.assertIn("SUDO_COMMAND_SCOPE=FIXED_HELPER_NO_ARGS", result.stdout)
        self.assertIn("ROOT_SHELL_GRANTED=NO", result.stdout)

    def test_injected_post_install_failure_restores_prior_boundary(self) -> None:
        helper_path = self.test_root / "usr/local/sbin/sea-speed-auth-privileged-helper"
        bundle_root = self.test_root / "usr/local/lib/sea-speed-auth-privileged"
        sudoers_path = self.test_root / "etc/sudoers.d/sea-speed-auth-privileged"
        helper_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_root.mkdir(parents=True, exist_ok=True)
        sudoers_path.parent.mkdir(parents=True, exist_ok=True)
        helper_path.write_text("old-helper\n", encoding="utf-8")
        (bundle_root / "old.txt").write_text("old-bundle\n", encoding="utf-8")
        sudoers_path.write_text("old-sudoers\n", encoding="utf-8")

        result = self.run_installer(fail_after_install=True)
        self.assertEqual(result.returncode, 90, result.stdout)
        self.assertEqual(helper_path.read_text(encoding="utf-8"), "old-helper\n")
        self.assertEqual((bundle_root / "old.txt").read_text(encoding="utf-8"), "old-bundle\n")
        self.assertEqual(sudoers_path.read_text(encoding="utf-8"), "old-sudoers\n")
        self.assertIn("SEA_SPEED_AUTH_PRIVILEGE_INSTALL_ROLLBACK=PASS", result.stdout)

    def test_sudoers_is_one_fixed_helper_with_explicit_no_arguments(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('NOPASSWD: ${HELPER_PATH#${PREFIX}} ""', text)
        for forbidden in ("NOPASSWD: ALL", "NOPASSWD: /bin/bash", "NOPASSWD: /usr/bin/python", "NOPASSWD: /usr/sbin/nginx"):
            self.assertNotIn(forbidden, text)
        self.assertIn("visudo -cf", text)
        self.assertIn("deployment user must not be root", text)

    def test_installer_requires_exact_checkout_and_repository_identity(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('git -C "$REPO_ROOT" rev-parse HEAD', text)
        self.assertIn("MostDef2000/sea-speed", text)
        self.assertIn("installer source checkout is not the authorized exact SHA", text)


if __name__ == "__main__":
    unittest.main()
