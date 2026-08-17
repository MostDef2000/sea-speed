from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "deploy/vps/deploy.sh"
OLD = "a" * 40
CANDIDATE = "b" * 40
OLDER = "c" * 40


class VpsDeployTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.deploy_root = self.root / "deploy"
        self.releases = self.deploy_root / "releases"
        self.state = self.deploy_root / "state"
        self.live = self.root / "live"
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir(parents=True)
        self.state.mkdir(parents=True)
        self.api = self.live / "api/app/main.py"
        self.operator = self.live / "frontend/sea-speed/index.html"
        self.objects = self.live / "frontend/sea-speed/objects/index.html"
        self.cameras = self.live / "frontend/sea-speed/cameras/index.html"
        self.road = self.live / "frontend/sea-speed/road/index.html"
        self.root_frontend = self.live / "frontend/root/index.html"
        for sha in (OLD, CANDIDATE, OLDER):
            self.write_release(sha)
        self.install_live(OLD)
        (self.state / "current-release").write_text(OLD + "\n", encoding="utf-8")
        (self.state / "previous-release").write_text(OLDER + "\n", encoding="utf-8")
        self.write_fakes()

    def write_release(self, sha: str) -> None:
        release = self.releases / sha
        files = {
            "api/app/main.py": f"SOURCE_COMMIT = '{sha}'\n",
            "frontend/sea-speed/index.html": f"operator {sha}\n",
            "frontend/sea-speed/objects/index.html": f"objects {sha}\n",
            "frontend/sea-speed/cameras/index.html": f"cameras {sha}\n",
            "frontend/sea-speed/road/index.html": f"road {sha}\n",
            "frontend/root/index.html": f"root {sha}\n",
            "deploy/vps/sea-speed-auth-cutover.sh": "#!/usr/bin/env bash\nexit 0\n",
            "deploy/vps/install-auth-privilege-boundary.sh": "#!/usr/bin/env bash\nexit 0\n",
            "deploy/vps/sea-speed-auth-privileged-helper.py": "# helper source fixture\n",
            "scripts/operations/nginx_cam1_direct_h264.py": "# renderer fixture\n",
            "scripts/operations/nginx_sea_speed_auth.py": "# renderer fixture\n",
            "commit-sha": sha + "\n",
            "archive-sha256": (sha[0] * 64) + "\n",
        }
        for relative, content in files.items():
            path = release / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            if path.suffix == ".sh":
                path.chmod(0o755)

    def install_live(self, sha: str) -> None:
        release = self.releases / sha
        mapping = {
            self.api: release / "api/app/main.py",
            self.operator: release / "frontend/sea-speed/index.html",
            self.objects: release / "frontend/sea-speed/objects/index.html",
            self.cameras: release / "frontend/sea-speed/cameras/index.html",
            self.road: release / "frontend/sea-speed/road/index.html",
            self.root_frontend: release / "frontend/root/index.html",
        }
        for target, source in mapping.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())

    def write_executable(self, name: str, content: str) -> Path:
        path = self.fake_bin / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
        return path

    def write_fakes(self) -> None:
        self.systemctl = self.write_executable(
            "systemctl",
            "#!/usr/bin/env bash\nset -euo pipefail\nprintf '%s\\n' \"$*\" >> \"$FAKE_SYSTEMCTL_LOG\"\n",
        )
        self.write_executable(
            "sudo",
            "#!/usr/bin/env bash\nset -euo pipefail\nif [[ \"${1:-}\" == '-n' ]]; then shift; fi\nexec \"$@\"\n",
        )
        self.write_executable("sleep", "#!/usr/bin/env bash\nexit 0\n")
        self.write_executable(
            "curl",
            """#!/usr/bin/env bash
set -euo pipefail
url="${@: -1}"
if [[ "$url" == "$SEA_SPEED_ORIGIN_HEALTH_URL" ]]; then
  case "${FAKE_ORIGIN_MODE:-success}" in
    success) exit 0 ;;
    transient)
      count=0; [[ -f "$FAKE_CURL_COUNT_FILE" ]] && count="$(cat "$FAKE_CURL_COUNT_FILE")"
      count=$((count + 1)); printf '%s\n' "$count" > "$FAKE_CURL_COUNT_FILE"
      (( count <= ${FAKE_ORIGIN_FAILS:-2} )) && exit 7 || exit 0 ;;
    fail-candidate) grep -Fq "$FAKE_OLD_SHA" "$SEA_SPEED_API_TARGET" && exit 0 || exit 7 ;;
    *) exit 64 ;;
  esac
fi
printf '200'
""",
        )
        self.write_executable(
            "rm",
            """#!/usr/bin/env bash
set -euo pipefail
fail_name="${FAKE_RM_FAIL_BASENAME:-}"
for arg in "$@"; do
  if [[ -n "$fail_name" && "${arg##*/}" == "$fail_name" && "$arg" == "$SEA_SPEED_DEPLOY_ROOT/releases/"* ]]; then exit 1; fi
done
exec /bin/rm "$@"
""",
        )
        self.privileged_helper = self.write_executable(
            "sea-speed-auth-privileged-helper",
            """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
request = json.loads(Path(os.environ['FAKE_PRIV_REQUEST']).read_text())
action = request['action']
mode = os.environ.get('FAKE_PRIV_MODE', 'success')
if action == 'status' and mode in {'missing', 'mismatch'}:
    print('ERROR privileged bundle source SHA mismatch')
    raise SystemExit(42)
print('SEA_SPEED_AUTH_PRIVILEGE_BOUNDARY=PASS')
print('SOURCE_SHA=' + request['source_sha'])
print('ACTION=' + action)
print('PRIVILEGED_TOPOLOGY=FIXED')
print('ARBITRARY_ROOT_EXECUTION=NO')
if action == 'reconcile':
    if mode == 'auth-fail':
        print('SEA_SPEED_AUTH_ROLLBACK=PASS')
        print('AUTOMATIC_ROLLBACK=PASS')
        raise SystemExit(35)
    print('SEA_SPEED_AUTH_CUTOVER=PASS')
    print('WORKER_PRIVATE_ROAD_API_BASE=http://10.123.239.101:18080/api/analytics/road1')
    print('ROLLBACK_CAPABILITY=VERIFIED')
    print('SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS')
""",
        )

    def env(self, *, mode: str = "success", priv_mode: str = "success", prune_failure: str = "") -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "PATH": str(self.fake_bin) + os.pathsep + env.get("PATH", ""),
                "SEA_SPEED_DEPLOY_ROOT": str(self.deploy_root),
                "SEA_SPEED_API_TARGET": str(self.api),
                "SEA_SPEED_FRONTEND_TARGET": str(self.operator),
                "SEA_SPEED_OBJECTS_FRONTEND_TARGET": str(self.objects),
                "SEA_SPEED_CAMERAS_FRONTEND_TARGET": str(self.cameras),
                "SEA_SPEED_ROAD_FRONTEND_TARGET": str(self.road),
                "SEA_SPEED_ROOT_FRONTEND_TARGET": str(self.root_frontend),
                "SEA_SPEED_SYSTEMCTL_BIN": str(self.systemctl),
                "SEA_SPEED_ORIGIN_HEALTH_URL": "http://127.0.0.1:8010/api/health",
                "SEA_SPEED_HEALTH_URL": "https://example.invalid/sea-speed/api/health",
                "SEA_SPEED_FRONTEND_URL": "https://example.invalid/sea-speed/",
                "SEA_SPEED_OBJECTS_FRONTEND_URL": "https://example.invalid/sea-speed/objects/",
                "SEA_SPEED_CAMERAS_FRONTEND_URL": "https://example.invalid/sea-speed/cameras/",
                "SEA_SPEED_ROAD_FRONTEND_URL": "https://example.invalid/sea-speed/road/",
                "SEA_SPEED_ROOT_FRONTEND_URL": "https://example.invalid/",
                "SEA_SPEED_REQUIRE_AUTH_BOUNDARY": "1",
                "SEA_SPEED_AUTHENTIK_UPSTREAM": "http://10.123.239.102:19000",
                "SEA_SPEED_WORKER_PRIVATE_LISTEN": "10.123.239.101:18080",
                "SEA_SPEED_WORKER_PRIVATE_PEER": "10.123.239.102",
                "SEA_SPEED_AUTH_PRIVILEGED_HELPER": str(self.privileged_helper),
                "FAKE_PRIV_REQUEST": str(self.state / "auth-privileged-request.json"),
                "FAKE_PRIV_MODE": priv_mode,
                "FAKE_ORIGIN_MODE": mode,
                "FAKE_ORIGIN_FAILS": "2",
                "FAKE_CURL_COUNT_FILE": str(self.root / "curl-count"),
                "FAKE_OLD_SHA": OLD,
                "FAKE_SYSTEMCTL_LOG": str(self.root / "systemctl.log"),
                "FAKE_RM_FAIL_BASENAME": prune_failure,
            }
        )
        return env

    def run_deploy(self, *, mode: str = "success", priv_mode: str = "success", prune_failure: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(DEPLOY_SCRIPT), CANDIDATE],
            cwd=ROOT,
            env=self.env(mode=mode, priv_mode=priv_mode, prune_failure=prune_failure),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def current(self) -> str:
        return (self.state / "current-release").read_text().strip()

    def manifest(self) -> dict[str, object]:
        return json.loads((self.state / "deployment-manifest.json").read_text())

    def test_success_commits_all_frontends_boundary_and_state(self) -> None:
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.current(), CANDIDATE)
        self.assertIn(CANDIDATE, self.road.read_text())
        self.assertIn("SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS", result.stdout)
        checks = {item["name"]: item["status"] for item in self.manifest()["checks"]}
        self.assertEqual(checks["auth_v1_road_private_m2m"], "passed")

    def test_privilege_boundary_mismatch_fails_before_live_source_mutation(self) -> None:
        before_api = self.api.read_bytes()
        before_road = self.road.read_bytes()
        result = self.run_deploy(priv_mode="mismatch")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.api.read_bytes(), before_api)
        self.assertEqual(self.road.read_bytes(), before_road)
        self.assertEqual(self.current(), OLD)
        self.assertIn("PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES", result.stdout)
        self.assertFalse((self.state / "deployment-manifest.json").exists())

    def test_missing_helper_fails_before_live_source_mutation(self) -> None:
        before = self.api.read_bytes()
        env = self.env()
        env["SEA_SPEED_AUTH_PRIVILEGED_HELPER"] = str(self.root / "missing-helper")
        result = subprocess.run(["bash", str(DEPLOY_SCRIPT), CANDIDATE], cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.api.read_bytes(), before)
        self.assertEqual(self.current(), OLD)
        self.assertIn("PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES", result.stdout)

    def test_candidate_failure_rolls_back_road_with_other_frontends(self) -> None:
        result = self.run_deploy(mode="fail-candidate")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(OLD, self.api.read_text())
        self.assertIn(OLD, self.road.read_text())
        self.assertEqual(self.current(), OLD)
        self.assertEqual(self.manifest()["state"], "rolled_back")

    def test_auth_boundary_failure_rolls_source_back_after_boundary_self_rollback(self) -> None:
        result = self.run_deploy(priv_mode="auth-fail")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("SEA_SPEED_AUTH_ROLLBACK=PASS", result.stdout)
        self.assertIn(OLD, self.api.read_text())
        self.assertEqual(self.current(), OLD)
        self.assertEqual(self.manifest()["state"], "rolled_back")

    def test_already_deployed_source_fails_closed_when_boundary_is_not_accepted(self) -> None:
        self.install_live(CANDIDATE)
        (self.state / "current-release").write_text(CANDIDATE + "\n", encoding="utf-8")
        result = self.run_deploy(priv_mode="auth-fail")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(self.current(), CANDIDATE)
        self.assertEqual(self.manifest()["state"], "failed")

    def test_transient_health_recovers(self) -> None:
        result = self.run_deploy(mode="transient")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertGreaterEqual(int((self.root / "curl-count").read_text()), 3)

    def test_stale_prune_failure_is_warning_only(self) -> None:
        result = self.run_deploy(prune_failure=OLDER)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.current(), CANDIDATE)
        self.assertTrue((self.releases / OLDER).is_dir())


if __name__ == "__main__":
    unittest.main()
