from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
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


class PrivilegeInstallerContractTests(unittest.TestCase):
    def test_sudoers_is_one_fixed_helper_with_explicit_no_arguments(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('NOPASSWD: ${HELPER_PATH#${PREFIX}} ""', text)
        for forbidden in ("NOPASSWD: ALL", "NOPASSWD: /bin/bash", "NOPASSWD: /usr/bin/python", "NOPASSWD: /usr/sbin/nginx"):
            self.assertNotIn(forbidden, text)
        self.assertIn("visudo -cf", text)
        self.assertIn("deployment user must not be root", text)
        self.assertIn("SEA_SPEED_AUTH_PRIVILEGE_INSTALL_ROLLBACK=PASS", text)

    def test_installer_requires_exact_checkout_and_repository_identity(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('git -C "$REPO_ROOT" rev-parse HEAD', text)
        self.assertIn("MostDef2000/sea-speed", text)
        self.assertIn("installer source checkout is not the authorized exact SHA", text)


if __name__ == "__main__":
    unittest.main()
