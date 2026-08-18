from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "deploy/vps/deploy.sh"
HELPER_SOURCE = ROOT / "deploy/vps/sea-speed-auth-privileged-helper.py"
OLD = "a" * 40
CANDIDATE = "b" * 40
OLDER = "c" * 40

helper_spec = importlib.util.spec_from_file_location("sea_speed_auth_privileged_helper_test", HELPER_SOURCE)
assert helper_spec and helper_spec.loader
privileged_helper = importlib.util.module_from_spec(helper_spec)
sys.modules[helper_spec.name] = privileged_helper
helper_spec.loader.exec_module(privileged_helper)


class SequenceRunner:
    def __init__(self, responses: list[tuple[int, str]]) -> None:
        self.responses = list(responses)
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        if not self.responses:
            raise AssertionError(f"unexpected command: {args}")
        returncode, stdout = self.responses.pop(0)
        return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout)


class PrivilegedAuthRecoveryTests(unittest.TestCase):
    def test_http_500_prepare_failure_uses_narrow_recovery_without_protected_flag(self) -> None:
        candidate = "d" * 64
        runner = SequenceRunner(
            [
                (22, "NGINX_SITE=/etc/nginx/sites-available/mostdef.ru\nERROR /sea-speed/ is not auth-gated: HTTP 500\nERROR existing protected Auth v1 rollback baseline is not valid\n"),
                (0, f"NGINX_SITE=/etc/nginx/sites-available/mostdef.ru\nCANDIDATE_SHA256={candidate}\nROLLBACK_CAPABILITY=MANUAL\n"),
                (0, "SEA_SPEED_AUTH_CUTOVER=PASS\nWORKER_PRIVATE_ROAD_API_BASE=http://10.123.239.101:18080/api/analytics/road1\nROLLBACK_CAPABILITY=MANUAL\n"),
            ]
        )
        restorer_called: list[str] = []

        output = privileged_helper.run_cutover(
            Path("/root/exact"),
            runner,
            restorer=lambda text, _runner: restorer_called.append(text) or "SEA_SPEED_AUTH_RECOVERY_ROLLBACK=PASS",
        )

        self.assertIn("SEA_SPEED_AUTH_RECOVERY=PASS", output)
        self.assertEqual(restorer_called, [])
        self.assertIn("--require-protected-baseline", runner.calls[0])
        self.assertNotIn("--require-protected-baseline", runner.calls[1])
        self.assertNotIn("--require-protected-baseline", runner.calls[2])
        self.assertEqual(runner.responses, [])

    def test_non_500_protected_baseline_failure_does_not_enter_recovery(self) -> None:
        runner = SequenceRunner(
            [(22, "ERROR public root expected 200, got 503\nERROR existing protected Auth v1 rollback baseline is not valid\n")]
        )
        with self.assertRaises(privileged_helper.BoundaryError):
            privileged_helper.run_cutover(Path("/root/exact"), runner)
        self.assertEqual(len(runner.calls), 1)

    def test_failed_recovery_activation_requires_exact_baseline_restorer(self) -> None:
        candidate = "e" * 64
        runner = SequenceRunner(
            [
                (22, "NGINX_SITE=/etc/nginx/sites-available/mostdef.ru\nERROR /sea-speed/ is not auth-gated: HTTP 500\nERROR existing protected Auth v1 rollback baseline is not valid\n"),
                (0, f"CANDIDATE_SHA256={candidate}\n"),
                (35, "NGINX_SITE=/etc/nginx/sites-available/mostdef.ru\nNGINX_BACKUP=/var/lib/sea-speed-auth-v1/backups/pre.conf\nERROR Auth v1 candidate post-mutation verification failed rc=35\n"),
            ]
        )
        restored: list[str] = []

        def restorer(text: str, _runner: object) -> str:
            restored.append(text)
            return "SEA_SPEED_AUTH_RECOVERY_ROLLBACK=PASS"

        with self.assertRaises(privileged_helper.BoundaryError) as raised:
            privileged_helper.run_cutover(Path("/root/exact"), runner, restorer=restorer)
        self.assertEqual(len(restored), 1)
        self.assertIn("SEA_SPEED_AUTH_RECOVERY_ROLLBACK=PASS", str(raised.exception))


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
if [[ "$url" == "$SEA_SPEED_FRONTEND_URL" ]]; then
  case "${FAKE_PUBLIC_MODE:-healthy}" in
    healthy) printf '302'; exit 0 ;;
    broken-500)
      [[ -f "$FAKE_RECOVERY_MARKER" ]] && printf '302' || printf '500'
      exit 0
      ;;
    bad-502) printf '502'; exit 0 ;;
    *) printf '000'; exit 0 ;;
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
  if [[ -n "$fail_name" && "$arg" == "$SEA_SPEED_DEPLOY_ROOT/releases/$fail_name" ]]; then
    echo "FAKE_RM_REJECTED=$arg" >> "$FAKE_RM_LOG"
    exit 1
  fi
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
public_mode = os.environ.get('FAKE_PUBLIC_MODE', 'healthy')
recovery_marker = Path(os.environ['FAKE_RECOVERY_MARKER'])
if action == 'status' and mode in {'missing', 'mismatch'}:
    print('ERROR privileged bundle source SHA mismatch')
    raise SystemExit(42)
print('SEA_SPEED_AUTH_PRIVILEGE_BOUNDARY=PASS')
print('SOURCE_SHA=' + request['source_sha'])
print('ACTION=' + action)
print('PRIVILEGED_TOPOLOGY=FIXED')
print('ARBITRARY_ROOT_EXECUTION=NO')
if action == 'reconcile':
    if public_mode == 'broken-500' and not recovery_marker.exists():
        if mode == 'recovery-fail':
            print('SEA_SPEED_AUTH_RECOVERY_ROLLBACK=PASS')
            raise SystemExit(35)
        Path(os.environ['FAKE_RECOVERY_API_OBSERVED']).write_text(Path(os.environ['SEA_SPEED_API_TARGET']).read_text())
        recovery_marker.write_text('recovered\n')
        print('SEA_SPEED_AUTH_CUTOVER=PASS')
        print('WORKER_PRIVATE_ROAD_API_BASE=http://10.123.239.101:18080/api/analytics/road1')
        print('SEA_SPEED_AUTH_RECOVERY=PASS')
        print('SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS')
        raise SystemExit(0)
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

    def env(
        self,
        *,
        mode: str = "success",
        priv_mode: str = "success",
        prune_failure: str = "",
        public_mode: str = "healthy",
    ) -> dict[str, str]:
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
                "FAKE_PUBLIC_MODE": public_mode,
                "FAKE_RECOVERY_MARKER": str(self.root / "auth-recovered"),
                "FAKE_RECOVERY_API_OBSERVED": str(self.root / "recovery-api-observed"),
                "FAKE_ORIGIN_MODE": mode,
                "FAKE_ORIGIN_FAILS": "2",
                "FAKE_CURL_COUNT_FILE": str(self.root / "curl-count"),
                "FAKE_OLD_SHA": OLD,
                "FAKE_SYSTEMCTL_LOG": str(self.root / "systemctl.log"),
                "FAKE_RM_FAIL_BASENAME": prune_failure,
                "FAKE_RM_LOG": str(self.root / "rm.log"),
            }
        )
        return env

    def run_deploy(
        self,
        *,
        mode: str = "success",
        priv_mode: str = "success",
        prune_failure: str = "",
        public_mode: str = "healthy",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(DEPLOY_SCRIPT), CANDIDATE],
            cwd=ROOT,
            env=self.env(
                mode=mode,
                priv_mode=priv_mode,
                prune_failure=prune_failure,
                public_mode=public_mode,
            ),
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

    def test_public_500_is_recovered_before_live_source_mutation(self) -> None:
        result = self.run_deploy(public_mode="broken-500")
        self.assertEqual(result.returncode, 0, result.stdout)
        observed = (self.root / "recovery-api-observed").read_text(encoding="utf-8")
        self.assertIn(OLD, observed)
        self.assertNotIn(CANDIDATE, observed)
        self.assertIn("AUTH_V1_RECOVERY_PRE_SOURCE=PASS", result.stdout)
        self.assertEqual(self.current(), CANDIDATE)

    def test_public_500_recovery_failure_stops_before_live_source_mutation(self) -> None:
        before_api = self.api.read_bytes()
        before_operator = self.operator.read_bytes()
        result = self.run_deploy(public_mode="broken-500", priv_mode="recovery-fail")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.api.read_bytes(), before_api)
        self.assertEqual(self.operator.read_bytes(), before_operator)
        self.assertEqual(self.current(), OLD)
        self.assertIn("SEA_SPEED_AUTH_RECOVERY_ROLLBACK=PASS", result.stdout)
        self.assertFalse((self.state / "deployment-manifest.json").exists())

    def test_nonrecoverable_public_status_stops_before_live_source_mutation(self) -> None:
        before_api = self.api.read_bytes()
        result = self.run_deploy(public_mode="bad-502")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.api.read_bytes(), before_api)
        self.assertEqual(self.current(), OLD)
        self.assertIn("non-recoverable HTTP 502", result.stdout)
        self.assertFalse((self.state / "deployment-manifest.json").exists())

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
        self.assertTrue((self.releases / OLDER).is_dir(), result.stdout)
        self.assertIn("WARNING: unable to prune stale release", result.stdout)
        self.assertIn(f"FAKE_RM_REJECTED={self.releases / OLDER}", (self.root / "rm.log").read_text())


if __name__ == "__main__":
    unittest.main()
