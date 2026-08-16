from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "deploy/vps/deploy.sh"
OLD = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CANDIDATE = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
OLDER = "cccccccccccccccccccccccccccccccccccccccc"


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
            "frontend/root/index.html": f"root {sha}\n",
            "commit-sha": sha + "\n",
            "archive-sha256": (sha[0] * 64) + "\n",
        }
        for relative, content in files.items():
            path = release / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def install_live(self, sha: str) -> None:
        release = self.releases / sha
        mapping = {
            self.api: release / "api/app/main.py",
            self.operator: release / "frontend/sea-speed/index.html",
            self.objects: release / "frontend/sea-speed/objects/index.html",
            self.cameras: release / "frontend/sea-speed/cameras/index.html",
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
        self.write_executable(
            "sleep",
            "#!/usr/bin/env bash\nexit 0\n",
        )
        self.write_executable(
            "curl",
            """#!/usr/bin/env bash
set -euo pipefail
url="${@: -1}"
if [[ "$url" == "$SEA_SPEED_ORIGIN_HEALTH_URL" ]]; then
  case "${FAKE_ORIGIN_MODE:-success}" in
    success)
      exit 0
      ;;
    transient)
      count=0
      if [[ -f "$FAKE_CURL_COUNT_FILE" ]]; then count="$(cat "$FAKE_CURL_COUNT_FILE")"; fi
      count=$((count + 1))
      printf '%s\n' "$count" > "$FAKE_CURL_COUNT_FILE"
      if (( count <= ${FAKE_ORIGIN_FAILS:-2} )); then exit 7; fi
      exit 0
      ;;
    fail-candidate)
      if grep -Fq "$FAKE_OLD_SHA" "$SEA_SPEED_API_TARGET"; then exit 0; fi
      exit 7
      ;;
    *)
      exit 64
      ;;
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
  if [[ -n "$fail_name" && "${arg##*/}" == "$fail_name" && "$arg" == "$SEA_SPEED_DEPLOY_ROOT/releases/"* ]]; then
    echo "fake rm denied: $arg" >&2
    exit 1
  fi
done
exec /bin/rm "$@"
""",
        )

    def env(self, *, mode: str = "success", prune_failure: str = "") -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "PATH": str(self.fake_bin) + os.pathsep + env.get("PATH", ""),
                "SEA_SPEED_DEPLOY_ROOT": str(self.deploy_root),
                "SEA_SPEED_API_TARGET": str(self.api),
                "SEA_SPEED_FRONTEND_TARGET": str(self.operator),
                "SEA_SPEED_OBJECTS_FRONTEND_TARGET": str(self.objects),
                "SEA_SPEED_CAMERAS_FRONTEND_TARGET": str(self.cameras),
                "SEA_SPEED_ROOT_FRONTEND_TARGET": str(self.root_frontend),
                "SEA_SPEED_SYSTEMCTL_BIN": str(self.systemctl),
                "SEA_SPEED_ORIGIN_HEALTH_URL": "http://127.0.0.1:8010/api/health",
                "SEA_SPEED_HEALTH_URL": "https://example.invalid/sea-speed/api/health",
                "SEA_SPEED_FRONTEND_URL": "https://example.invalid/sea-speed/",
                "SEA_SPEED_OBJECTS_FRONTEND_URL": "https://example.invalid/sea-speed/objects/",
                "SEA_SPEED_CAMERAS_FRONTEND_URL": "https://example.invalid/sea-speed/cameras/",
                "SEA_SPEED_ROOT_FRONTEND_URL": "https://example.invalid/",
                "FAKE_ORIGIN_MODE": mode,
                "FAKE_ORIGIN_FAILS": "2",
                "FAKE_CURL_COUNT_FILE": str(self.root / "curl-count"),
                "FAKE_OLD_SHA": OLD,
                "FAKE_SYSTEMCTL_LOG": str(self.root / "systemctl.log"),
                "FAKE_RM_FAIL_BASENAME": prune_failure,
            }
        )
        return env

    def run_deploy(self, target: str = CANDIDATE, *, mode: str = "success", prune_failure: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(DEPLOY_SCRIPT), target],
            cwd=ROOT,
            env=self.env(mode=mode, prune_failure=prune_failure),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def current(self) -> str:
        return (self.state / "current-release").read_text(encoding="utf-8").strip()

    def previous(self) -> str:
        return (self.state / "previous-release").read_text(encoding="utf-8").strip()

    def manifest(self) -> dict[str, object]:
        return json.loads((self.state / "deployment-manifest.json").read_text(encoding="utf-8"))

    def test_success_commits_state_then_preserves_current_and_previous(self) -> None:
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.current(), CANDIDATE)
        self.assertEqual(self.previous(), OLD)
        self.assertIn(CANDIDATE, self.api.read_text(encoding="utf-8"))
        manifest = self.manifest()
        self.assertEqual(manifest["sourceCommit"], CANDIDATE)
        self.assertEqual(manifest["previousVersion"], OLD)
        self.assertEqual(manifest["state"], "runtime_verified")
        self.assertTrue(manifest["runtimeVerified"])
        self.assertTrue((self.releases / CANDIDATE).is_dir())
        self.assertTrue((self.releases / OLD).is_dir())
        self.assertFalse((self.releases / OLDER).exists())

    def test_transient_origin_failure_recovers_without_rollback(self) -> None:
        result = self.run_deploy(mode="transient")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.current(), CANDIDATE)
        self.assertEqual(self.previous(), OLD)
        self.assertGreaterEqual(int((self.root / "curl-count").read_text(encoding="utf-8")), 3)
        self.assertNotIn("rolling back", result.stdout.lower())

    def test_candidate_verification_failure_rolls_back_and_keeps_committed_state_old(self) -> None:
        result = self.run_deploy(mode="fail-candidate")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("rolling back", result.stdout.lower())
        self.assertIn(OLD, self.api.read_text(encoding="utf-8"))
        self.assertEqual(self.current(), OLD)
        self.assertEqual(self.previous(), OLDER)
        manifest = self.manifest()
        self.assertEqual(manifest["sourceCommit"], OLD)
        self.assertEqual(manifest["previousVersion"], CANDIDATE)
        self.assertEqual(manifest["state"], "rolled_back")
        self.assertTrue(manifest["runtimeVerified"])

    def test_stale_prune_failure_is_warning_only_after_verified_state_commit(self) -> None:
        result = self.run_deploy(prune_failure=OLDER)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.current(), CANDIDATE)
        self.assertEqual(self.previous(), OLD)
        self.assertTrue((self.releases / OLDER).is_dir())
        self.assertIn("WARNING: unable to prune stale release", result.stdout)
        self.assertEqual(self.manifest()["state"], "runtime_verified")

    def test_idempotent_retry_verifies_without_rotating_rollback_pair(self) -> None:
        self.install_live(CANDIDATE)
        (self.state / "current-release").write_text(CANDIDATE + "\n", encoding="utf-8")
        (self.state / "previous-release").write_text(OLD + "\n", encoding="utf-8")
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("already deployed; verifying runtime", result.stdout)
        self.assertEqual(self.current(), CANDIDATE)
        self.assertEqual(self.previous(), OLD)
        self.assertTrue((self.releases / CANDIDATE).is_dir())
        self.assertTrue((self.releases / OLD).is_dir())
        self.assertEqual(self.manifest()["sourceCommit"], CANDIDATE)


if __name__ == "__main__":
    unittest.main()
