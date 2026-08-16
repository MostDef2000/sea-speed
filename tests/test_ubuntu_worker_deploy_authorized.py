from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/worker/ubuntu/deploy-authorized.sh"
TARGET = "a" * 40
BASELINE = "b" * 40
RUNTIME = "c" * 64
ARTIFACT = "d" * 64


def executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class UbuntuAuthorizedDeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.install_root = self.base / "worker"
        self.systemd_root = self.base / "systemd"
        self.fixture = self.base / "fixture"
        self.fakebin = self.base / "bin"
        for path in (self.systemd_root, self.fixture, self.fakebin):
            path.mkdir(parents=True, exist_ok=True)
        (self.install_root / "shared/runtime").mkdir(parents=True, exist_ok=True)
        (self.install_root / "shared/config").mkdir(parents=True, exist_ok=True)
        (self.install_root / "shared/runtime/active-source-commit").write_text(BASELINE + "\n", encoding="utf-8")
        self.token = self.base / "github-token"
        self.token.write_text("test-token\n", encoding="utf-8")
        self.token.chmod(0o600)
        self._build_fixture()
        self._build_fake_commands()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _build_fixture(self) -> None:
        (self.fixture / "scripts/release").mkdir(parents=True)
        (self.fixture / "deploy/worker/ubuntu").mkdir(parents=True)
        executable(
            self.fixture / "scripts/release/verify_production_authorization.py",
            r'''
            #!/usr/bin/env python3
            import json, os, sys
            if os.environ.get("AUTH_FAIL") == "1":
                raise SystemExit(1)
            if "--require-execution-intent" not in sys.argv:
                raise SystemExit(2)
            if "--evidence-output" in sys.argv:
                p = sys.argv[sys.argv.index("--evidence-output") + 1]
                open(p, "w", encoding="utf-8").write(json.dumps({"executionIntent":"EXECUTE"}) + "\n")
            ''',
        )
        executable(
            self.fixture / "deploy/worker/ubuntu/update-exact.sh",
            r'''
            #!/usr/bin/env bash
            set -euo pipefail
            target="$1"; shift
            root=""
            while [[ $# -gt 0 ]]; do
              case "$1" in
                --install-root) root="$2"; shift 2 ;;
                --service-user|--token-file) shift 2 ;;
                --activate) shift ;;
                *) shift ;;
              esac
            done
            [[ -n "$root" ]]
            runtime="${TEST_RUNTIME_ID:?}"
            mkdir -p "$root/releases/$target" "$SEA_SPEED_SYSTEMD_UNIT_ROOT"
            printf '%s\n' "$runtime" > "$root/releases/$target/runtime-id"
            printf '%s\n' "$target" > "$root/shared/runtime/active-source-commit"
            printf 'ExecStart=/runtimes/%s/venv/bin/python /releases/%s/worker.py\n' "$runtime" "$target" > "$SEA_SPEED_SYSTEMD_UNIT_ROOT/sea-speed-worker.service"
            printf 'ExecStart=/releases/%s/worker-control-agent.py\n' "$target" > "$SEA_SPEED_SYSTEMD_UNIT_ROOT/sea-speed-worker-control.service"
            ''',
        )
        executable(
            self.fixture / "deploy/worker/ubuntu/rollback-exact.sh",
            r'''
            #!/usr/bin/env bash
            set -euo pipefail
            baseline="$1"; shift
            root=""
            while [[ $# -gt 0 ]]; do
              case "$1" in
                --install-root) root="$2"; shift 2 ;;
                --service-user|--expected-current) shift 2 ;;
                *) shift ;;
              esac
            done
            printf '%s\n' "$baseline" > "$root/shared/runtime/active-source-commit"
            rm -f "$SEA_SPEED_SYSTEMD_UNIT_ROOT/sea-speed-worker-control.service"
            printf 'ExecStart=/releases/%s/worker.py\n' "$baseline" > "$SEA_SPEED_SYSTEMD_UNIT_ROOT/sea-speed-worker.service"
            echo "ROLLBACK_ACCEPTED target=$baseline"
            ''',
        )

    def _build_fake_commands(self) -> None:
        executable(
            self.fakebin / "git",
            r'''
            #!/usr/bin/env python3
            import os, shutil, sys
            args = sys.argv[1:]
            stage = args[args.index("-C") + 1] if "-C" in args else ""
            if "fetch" in args:
                fixture = os.environ["SEA_SPEED_DEPLOY_FIXTURE"]
                shutil.copytree(fixture, stage, dirs_exist_ok=True)
                raise SystemExit(0)
            if "rev-list" in args:
                print(os.environ["TEST_TARGET_SHA"])
                raise SystemExit(0)
            if "rev-parse" in args:
                print(os.environ["TEST_TARGET_SHA"])
                raise SystemExit(0)
            raise SystemExit(0)
            ''',
        )
        executable(
            self.fakebin / "systemctl",
            r'''
            #!/usr/bin/env python3
            import os, sys
            from pathlib import Path
            args = sys.argv[1:]
            root = Path(os.environ["TEST_INSTALL_ROOT"])
            units = Path(os.environ["SEA_SPEED_SYSTEMD_UNIT_ROOT"])
            active = (root / "shared/runtime/active-source-commit").read_text().strip()
            desired_file = root / "shared/runtime/operator-desired-state"
            desired = desired_file.read_text().strip() if desired_file.exists() else "running"
            service = args[-1] if args else ""
            if args and args[0] == "show":
                if service == "sea-speed-worker.service":
                    runtime_file = root / "releases" / active / "runtime-id"
                    runtime = runtime_file.read_text().strip() if runtime_file.exists() else "legacy"
                    print(f"/runtimes/{runtime}/venv/bin/python /releases/{active}/worker.py")
                    raise SystemExit(0)
                if service == "sea-speed-worker-control.service":
                    print(f"/releases/{active}/worker-control-agent.py")
                    raise SystemExit(0)
            if args and args[0] == "is-active":
                if service == "sea-speed-worker-control.service":
                    if os.environ.get("POST_VERIFY_FAIL") == "1" and active == os.environ["TEST_TARGET_SHA"]:
                        raise SystemExit(3)
                    raise SystemExit(0 if (units / service).exists() else 3)
                if service == "sea-speed-worker.service":
                    raise SystemExit(0 if desired == "running" else 3)
            raise SystemExit(0)
            ''',
        )

    def run_deploy(self, **extra_env: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "PATH": str(self.fakebin) + os.pathsep + env["PATH"],
                "SEA_SPEED_DEPLOY_TEST_MODE": "1",
                "SEA_SPEED_SYSTEMD_UNIT_ROOT": str(self.systemd_root),
                "SEA_SPEED_DEPLOY_FIXTURE": str(self.fixture),
                "TEST_INSTALL_ROOT": str(self.install_root),
                "TEST_TARGET_SHA": TARGET,
                "TEST_RUNTIME_ID": RUNTIME,
            }
        )
        env.update(extra_env)
        return subprocess.run(
            [
                "bash", str(SCRIPT), TARGET, "--issue", "178",
                "--install-root", str(self.install_root),
                "--token-file", str(self.token),
                "--artifact-sha256", ARTIFACT,
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_success_executes_real_launcher_and_records_runtime_verified_manifest(self) -> None:
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(f"DEPLOYMENT_ACCEPTED target={TARGET} previous={BASELINE}", result.stdout)
        self.assertEqual((self.install_root / "shared/runtime/active-source-commit").read_text().strip(), TARGET)
        manifest = json.loads((self.install_root / "updater/deployment-manifest-ubuntu-worker.json").read_text())
        self.assertEqual(manifest["sourceCommit"], TARGET)
        self.assertEqual(manifest["previousVersion"], BASELINE)
        self.assertEqual(manifest["artifactSha256"], ARTIFACT)
        self.assertTrue(manifest["runtimeVerified"])
        self.assertEqual(manifest["state"], "runtime_verified")

    def test_intentionally_stopped_worker_remains_stopped(self) -> None:
        (self.install_root / "shared/runtime/operator-desired-state").write_text("stopped\n", encoding="utf-8")
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stdout)
        manifest = json.loads((self.install_root / "updater/deployment-manifest-ubuntu-worker.json").read_text())
        names = {item["name"] for item in manifest["checks"]}
        self.assertIn("operator-desired-state-stopped", names)

    def test_post_activation_verification_failure_rolls_back_previous_source(self) -> None:
        result = self.run_deploy(POST_VERIFY_FAIL="1")
        self.assertEqual(result.returncode, 30, result.stdout)
        self.assertIn(f"DEPLOY_ROLLED_BACK target={TARGET} restored={BASELINE}", result.stdout)
        self.assertEqual((self.install_root / "shared/runtime/active-source-commit").read_text().strip(), BASELINE)
        self.assertFalse((self.systemd_root / "sea-speed-worker-control.service").exists())

    def test_authorization_failure_stops_before_mutation(self) -> None:
        result = self.run_deploy(AUTH_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.install_root / "shared/runtime/active-source-commit").read_text().strip(), BASELINE)
        self.assertFalse((self.systemd_root / "sea-speed-worker-control.service").exists())


if __name__ == "__main__":
    unittest.main()
