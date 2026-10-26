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
        self.live_sync = self.live / "frontend/sea-speed/live-sync.js"
        self.overlay_canvas = self.live / "frontend/sea-speed/overlay-canvas.js"
        self.root_frontend = self.live / "frontend/root/index.html"
        self.fallback = self.live / "frontend/sea-speed-unavailable.html"
        for sha in (OLD, CANDIDATE, OLDER):
            self.write_release(sha)
        self.install_live(OLD)
        (self.state / "current-release").write_text(OLD + "\n", encoding="utf-8")
        (self.state / "previous-release").write_text(OLDER + "\n", encoding="utf-8")
        self.write_fakes()

    def write_release(self, sha: str, with_store: bool = True) -> None:
        release = self.releases / sha
        files = {
            "api/app/main.py": f"SOURCE_COMMIT = '{sha}'\n",
            "api/app/store.py": f"# store fixture {sha}\n",
            "api/app/config.py": f"# config fixture {sha}\n",
            "api/app/identity.py": f"# identity fixture {sha}\n",
            # Issue #396 wave 2: release_complete requires the objects-registry
            # modules, so synthetic releases carry them like the real tree does.
            "api/app/objects_registry.py": f"# objects registry fixture {sha}\n",
            "api/app/passage_mirrors.py": f"# passage mirrors fixture {sha}\n",
            # Issue #396 wave 3: release_complete requires the water-passages
            # store module too, so synthetic releases carry it as well.
            "api/app/water_passages.py": f"# water passages fixture {sha}\n",
            # Issue #396 wave 4: release_complete requires the camera-preview
            # service module as well, so synthetic releases carry it too.
            "api/app/camera_preview.py": f"# camera preview fixture {sha}\n",
            # Issue #396 wave 5: release_complete requires the analytics
            # services module as well, so synthetic releases carry it too.
            "api/app/analytics.py": f"# analytics services fixture {sha}\n",
            # Issue #396 wave 6: release_complete requires the live-feeds
            # module as well, so synthetic releases carry it too.
            "api/app/live_feeds.py": f"# live feeds fixture {sha}\n",
            "frontend/sea-speed/index.html": f"operator {sha}\n",
            "frontend/sea-speed/objects/index.html": f"objects {sha}\n",
            "frontend/sea-speed/cameras/index.html": f"cameras {sha}\n",
            "frontend/sea-speed/road/index.html": f"road {sha}\n",
            "frontend/sea-speed/live-sync.js": f"live-sync {sha}\n",
            "frontend/sea-speed/overlay-canvas.js": f"overlay-canvas {sha}\n",
            "frontend/root/index.html": f"root {sha}\n",
            "frontend/sea-speed/unavailable.html": f"fallback {sha}\n",
            "deploy/vps/sea-speed-auth-cutover.sh": "#!/usr/bin/env bash\nexit 0\n",
            "deploy/vps/install-auth-privilege-boundary.sh": "#!/usr/bin/env bash\nexit 0\n",
            "deploy/vps/sea-speed-auth-privileged-helper.py": "# helper source fixture\n",
            "scripts/operations/nginx_cam1_direct_h264.py": "# renderer fixture\n",
            "scripts/operations/nginx_sea_speed_auth.py": "# renderer fixture\n",
            "commit-sha": sha + "\n",
            "archive-sha256": (sha[0] * 64) + "\n",
        }
        if not with_store:
            # Store-less release (pre-#394 shape): activation must treat the
            # live store.py as a clean downgrade and remove it.
            files.pop("api/app/store.py")
        for relative, content in files.items():
            path = release / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            if path.suffix == ".sh":
                path.chmod(0o755)

    def install_live(self, sha: str) -> None:
        release = self.releases / sha
        self.fallback = self.live / "frontend/sea-speed-unavailable.html"
        mapping = {
            self.api: release / "api/app/main.py",
            self.operator: release / "frontend/sea-speed/index.html",
            self.objects: release / "frontend/sea-speed/objects/index.html",
            self.cameras: release / "frontend/sea-speed/cameras/index.html",
            self.road: release / "frontend/sea-speed/road/index.html",
            self.live_sync: release / "frontend/sea-speed/live-sync.js",
            self.overlay_canvas: release / "frontend/sea-speed/overlay-canvas.js",
            self.root_frontend: release / "frontend/root/index.html",
            self.fallback: release / "frontend/sea-speed/unavailable.html",
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
# Private Authentik health endpoint: healthy modes answer, the degraded/outage
# scenarios fail the private health probe closed.
if [[ "$url" == *"/-/health/ready/"* ]]; then
  [[ " degraded-503 healthy-auth-down degraded-500-fallback " == *" ${FAKE_PUBLIC_MODE:-healthy} "* ]] && exit 7 || exit 0
fi
if [[ "$url" == "$SEA_SPEED_FRONTEND_URL" ]]; then
  body=""
  fallback_body='<html><body><h1>Sea Speed временно недоступен</h1><button>Повторить подключение</button></body></html>'
  case "${FAKE_PUBLIC_MODE:-healthy}" in
    # healthy-auth-down/root-broken keep the operator gate healthy; only the
    # private Authentik health probe / root frontend smoke fail in those modes.
    healthy | healthy-auth-down | root-broken) printf '302'; exit 0 ;;
    broken-500)
      [[ -f "$FAKE_RECOVERY_MARKER" ]] && printf '302' || printf '500'
      exit 0
      ;;
    bad-502) printf '502'; exit 0 ;;
    degraded-503) body="$fallback_body" ;;
    # Degraded-500 admissible baseline: the two pre-mutation probes (boundary
    # verifier + recovery stage) see the broken 500; after the restart the
    # staged fallback outage page is live and the deploy completes degraded.
    degraded-500-fallback)
      fcount=0
      [[ -n "${FAKE_FRONTEND_COUNT_FILE:-}" && -f "$FAKE_FRONTEND_COUNT_FILE" ]] && fcount="$(cat "$FAKE_FRONTEND_COUNT_FILE")"
      fcount=$((fcount + 1))
      [[ -n "${FAKE_FRONTEND_COUNT_FILE:-}" ]] && printf '%s\n' "$fcount" > "$FAKE_FRONTEND_COUNT_FILE"
      if (( fcount <= 2 )); then printf '500'; exit 0; fi
      body="$fallback_body"
      ;;
    # Post-mutation strict-500: the candidate release breaks the protected
    # gate while the previous release serves it fine (sha-keyed on the live
    # API source, so the rollback verification sees the healthy 302 again).
    candidate-500)
      grep -Fq "$FAKE_CANDIDATE_SHA" "$SEA_SPEED_API_TARGET" && printf '500' || printf '302'
      exit 0
      ;;
    *) printf '000'; exit 0 ;;
  esac
  if [[ " ${*} " == *" --include "* ]]; then
    printf 'HTTP/1.1 503 Service Unavailable\\r\\nCache-Control: no-store\\r\\nRetry-After: 30\\r\\nContent-Type: text/html; charset=utf-8\\r\\nConnection: close\\r\\n\\r\\n%s' "$body"
  else
    out=""
    prev=""
    for a in "$@"; do
      [[ "$prev" == "--output" ]] && out="$a"
      prev="$a"
    done
    [[ -n "$out" ]] && printf '%s' "$body" > "$out"
    printf '503'
  fi
  exit 0
fi
if [[ "$url" == "$SEA_SPEED_ROOT_FRONTEND_URL" ]]; then
  [[ "${FAKE_PUBLIC_MODE:-healthy}" == "root-broken" ]] && printf '500' || printf '200'
  exit 0
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
        self.write_executable(
            "ss",
            """#!/usr/bin/env bash
set -euo pipefail
# Fake ss for the unprivileged Caddy-boundary verifier: emits a LISTEN line
# carrying the pinned private M2M listen unless the scenario suppresses it.
mode="${FAKE_SS_MODE:-bound}"
count=0
if [[ -n "${FAKE_SS_COUNT_FILE:-}" && -f "$FAKE_SS_COUNT_FILE" ]]; then
  count="$(cat "$FAKE_SS_COUNT_FILE")"
fi
count=$((count + 1))
if [[ -n "${FAKE_SS_COUNT_FILE:-}" ]]; then
  printf '%s\n' "$count" > "$FAKE_SS_COUNT_FILE"
fi
if [[ "$mode" == "absent" ]]; then
  exit 0
fi
if [[ "$mode" == "first-only" && "$count" -gt 1 ]]; then
  exit 0
fi
printf 'LISTEN 0 128 %s 0.0.0.0:*\n' "$SEA_SPEED_WORKER_PRIVATE_LISTEN"
""",
        )

    def env(
        self,
        *,
        mode: str = "success",
        ss_mode: str = "bound",
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
                "SEA_SPEED_LIVE_SYNC_TARGET": str(self.live_sync),
                "SEA_SPEED_OVERLAY_CANVAS_TARGET": str(self.overlay_canvas),
                "SEA_SPEED_ROOT_FRONTEND_TARGET": str(self.root_frontend),
                "SEA_SPEED_FALLBACK_FRONTEND_TARGET": str(self.fallback),
                "SEA_SPEED_SYSTEMCTL_BIN": str(self.systemctl),
                "SEA_SPEED_ORIGIN_HEALTH_URL": "http://127.0.0.1:8010/api/health",
                "SEA_SPEED_HEALTH_URL": "https://example.invalid/sea-speed/api/health",
                "SEA_SPEED_FRONTEND_URL": "https://example.invalid/sea-speed/",
                "SEA_SPEED_OBJECTS_FRONTEND_URL": "https://example.invalid/sea-speed/objects/",
                "SEA_SPEED_CAMERAS_FRONTEND_URL": "https://example.invalid/sea-speed/cameras/",
                "SEA_SPEED_ROAD_FRONTEND_URL": "https://example.invalid/sea-speed/road/",
                "SEA_SPEED_LIVE_SYNC_URL": "https://example.invalid/sea-speed/live-sync.js",
                "SEA_SPEED_ROOT_FRONTEND_URL": "https://example.invalid/",
                "SEA_SPEED_REQUIRE_AUTH_BOUNDARY": "1",
                "SEA_SPEED_AUTHENTIK_UPSTREAM": "http://10.123.239.102:19000",
                "SEA_SPEED_WORKER_PRIVATE_LISTEN": "10.123.239.29:18080",
                "SEA_SPEED_WORKER_PRIVATE_PEER": "10.123.239.102",
                "FAKE_PUBLIC_MODE": public_mode,
                "FAKE_RECOVERY_MARKER": str(self.root / "auth-recovered"),
                "FAKE_SS_MODE": ss_mode,
                "FAKE_SS_COUNT_FILE": str(self.root / "ss-count"),
                "FAKE_ORIGIN_MODE": mode,
                "FAKE_ORIGIN_FAILS": "2",
                "FAKE_CURL_COUNT_FILE": str(self.root / "curl-count"),
                "FAKE_FRONTEND_COUNT_FILE": str(self.root / "frontend-count"),
                "FAKE_OLD_SHA": OLD,
                "FAKE_CANDIDATE_SHA": CANDIDATE,
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
        ss_mode: str = "bound",
        prune_failure: str = "",
        public_mode: str = "healthy",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(DEPLOY_SCRIPT), CANDIDATE],
            cwd=ROOT,
            env=self.env(
                mode=mode,
                ss_mode=ss_mode,
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
        self.assertIn("SEA_SPEED_AUTH_CUTOVER=PASS", result.stdout)
        self.assertIn(
            "WORKER_PRIVATE_ROAD_API_BASE=http://10.123.239.29:18080/api/analytics/road1",
            result.stdout,
        )
        manifest = self.manifest()
        self.assertTrue(manifest["runtimeVerified"])
        self.assertEqual(manifest["state"], "runtime_verified")
        checks = {item["name"]: item["status"] for item in manifest["checks"]}
        self.assertEqual(checks["auth_v1_road_private_m2m"], "passed")

    def test_m2m_bind_absent_fails_closed_before_live_source_mutation(self) -> None:
        before_api = self.api.read_bytes()
        result = self.run_deploy(ss_mode="absent")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.api.read_bytes(), before_api)
        self.assertEqual(self.current(), OLD)
        self.assertIn(
            "ERROR Road private M2M boundary is not bound at 10.123.239.29:18080 on this VPS",
            result.stdout,
        )
        self.assertFalse((self.state / "deployment-manifest.json").exists())

    def test_post_mutation_boundary_failure_rolls_source_back(self) -> None:
        # The private M2M bind is present for the pre-mutation verification and
        # disappears before the post-mutation verification: the deploy must
        # roll the source back to the previous release and fail closed.
        result = self.run_deploy(ss_mode="first-only")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(self.current(), OLD)
        self.assertIn(OLD, self.api.read_text())
        self.assertIn(
            "ERROR Road private M2M boundary is not bound at 10.123.239.29:18080 on this VPS",
            result.stdout,
        )
        self.assertEqual(self.manifest()["state"], "rolled_back")

    def test_degraded_503_fallback_succeeds_without_boundary_checks(self) -> None:
        result = self.run_deploy(public_mode="degraded-503")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.current(), CANDIDATE)
        self.assertIn("SEA_SPEED_AUTH_CUTOVER=PASS", result.stdout)
        self.assertIn("DEGRADED_FALLBACK_VERIFIED=PASS", result.stdout)
        manifest = self.manifest()
        self.assertTrue(manifest["runtimeVerified"])
        checks = {item["name"]: item["status"] for item in manifest["checks"]}
        self.assertEqual(checks["auth_v1_road_private_m2m"], "passed")
        # The degraded fallback branch verifies the outage page without any
        # post-mutation ss check: only the single pre-mutation ss call ran.
        self.assertEqual(int((self.root / "ss-count").read_text()), 1)

    def test_public_500_fails_closed_before_live_source_mutation(self) -> None:
        before_api = self.api.read_bytes()
        before_operator = self.operator.read_bytes()
        result = self.run_deploy(public_mode="broken-500")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.api.read_bytes(), before_api)
        self.assertEqual(self.operator.read_bytes(), before_operator)
        self.assertEqual(self.current(), OLD)
        self.assertIn(
            "Protected Operator boundary reports HTTP 500 and no bounded Caddy-topology recovery exists; deployment fails closed",
            result.stdout,
        )
        self.assertFalse((self.state / "deployment-manifest.json").exists())

    def test_nonrecoverable_public_status_stops_before_live_source_mutation(self) -> None:
        before_api = self.api.read_bytes()
        result = self.run_deploy(public_mode="bad-502")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.api.read_bytes(), before_api)
        self.assertEqual(self.current(), OLD)
        self.assertIn("non-recoverable HTTP 502", result.stdout)
        self.assertFalse((self.state / "deployment-manifest.json").exists())

    def test_m2m_private_authentik_health_fail_aborts_pre_mutation_with_rc_47(self) -> None:
        # Gate 302 and root 200 are fine, but the private Authentik health
        # probe fails: the pre-mutation boundary verification must abort with
        # its non-recoverable rc 47 before any live source mutation.
        before_api = self.api.read_bytes()
        result = self.run_deploy(public_mode="healthy-auth-down")
        self.assertEqual(result.returncode, 47, result.stdout)
        self.assertEqual(self.api.read_bytes(), before_api)
        self.assertEqual(self.current(), OLD)
        self.assertIn("ERROR private Authentik health check failed", result.stdout)
        self.assertFalse((self.state / "deployment-manifest.json").exists())

    def test_m2m_root_frontend_smoke_fail_aborts_pre_mutation_with_rc_48(self) -> None:
        # Gate 302 and private health PASS, but the public root frontend smoke
        # fails: the boundary verifier must abort with rc 48 before any live
        # source mutation.
        before_api = self.api.read_bytes()
        result = self.run_deploy(public_mode="root-broken")
        self.assertEqual(result.returncode, 48, result.stdout)
        self.assertEqual(self.api.read_bytes(), before_api)
        self.assertEqual(self.current(), OLD)
        self.assertIn("Root frontend public smoke check failed with HTTP 500", result.stdout)
        self.assertFalse((self.state / "deployment-manifest.json").exists())

    def test_degraded_500_admissible_baseline_completes_deployment(self) -> None:
        # The protected gate serves a broken 500 and private Authentik is
        # unreachable while the target release stages the fallback page: the
        # degraded 500 baseline is admissible, the deploy proceeds, and after
        # the restart the fallback outage page is live (degraded success).
        result = self.run_deploy(public_mode="degraded-500-fallback")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.current(), CANDIDATE)
        self.assertIn("DEGRADED_BASELINE=500_UNAVAILABLE_AUTHENTIK_ADMISSIBLE", result.stdout)
        self.assertIn("SEA_SPEED_AUTH_CUTOVER=PASS", result.stdout)
        self.assertIn("DEGRADED_FALLBACK_VERIFIED=PASS", result.stdout)
        manifest = self.manifest()
        self.assertTrue(manifest["runtimeVerified"])
        checks = {item["name"]: item["status"] for item in manifest["checks"]}
        self.assertEqual(checks["auth_v1_road_private_m2m"], "passed")

    def test_degraded_500_without_admissible_baseline_fails_closed_pre_mutation(self) -> None:
        # The protected gate serves a broken 500 with no admissible degraded
        # baseline (private Authentik healthy, no recovery to attempt): the
        # recovery stage owns the degraded verdict and fails closed with rc 43
        # before any live source mutation.
        before_api = self.api.read_bytes()
        result = self.run_deploy(public_mode="broken-500")
        self.assertEqual(result.returncode, 43, result.stdout)
        self.assertEqual(self.api.read_bytes(), before_api)
        self.assertEqual(self.current(), OLD)
        self.assertIn("no bounded Caddy-topology recovery exists", result.stdout)
        self.assertNotIn("DEGRADED_BASELINE", result.stdout)
        self.assertFalse((self.state / "deployment-manifest.json").exists())

    def test_post_mutation_strict_500_fails_closed_and_rolls_back(self) -> None:
        # The boundary gate answers 302 for the pre-mutation probes, but the
        # candidate release breaks it to a 500 post-mutation: the post-mutation
        # verification is strict (no degraded pass-through), so the deploy
        # fails closed, rolls the live source back to the previous release and
        # records the rolled_back manifest state.
        result = self.run_deploy(public_mode="candidate-500")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(self.current(), OLD)
        self.assertIn(OLD, self.api.read_text())
        self.assertNotIn("SEA_SPEED_AUTH_CUTOVER=PASS", result.stdout)
        self.assertEqual(self.manifest()["state"], "rolled_back")

    def test_candidate_failure_rolls_back_road_with_other_frontends(self) -> None:
        result = self.run_deploy(mode="fail-candidate")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(OLD, self.api.read_text())
        self.assertIn(OLD, self.road.read_text())
        self.assertEqual(self.current(), OLD)
        self.assertEqual(self.manifest()["state"], "rolled_back")

    def test_candidate_failure_rolls_back_legacy_release_without_fallback_state(self) -> None:
        old_fallback = self.releases / OLD / "frontend/sea-speed/unavailable.html"
        old_fallback.unlink()
        self.fallback.unlink()

        result = self.run_deploy(mode="fail-candidate")

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(OLD, self.api.read_text())
        self.assertEqual(self.current(), OLD)
        self.assertFalse(self.fallback.exists())
        self.assertTrue(
            (self.releases / OLD / "frontend/sea-speed/unavailable.html.absent").is_file()
        )
        self.assertEqual(self.manifest()["state"], "rolled_back")

    def test_already_deployed_source_fails_closed_when_boundary_is_not_accepted(self) -> None:
        # The private M2M bind verifies pre-mutation and is gone by the
        # post-mutation boundary verification: the already-deployed source
        # fails closed with no rollback (nothing changed) and manifest failed.
        self.install_live(CANDIDATE)
        (self.state / "current-release").write_text(CANDIDATE + "\n", encoding="utf-8")
        result = self.run_deploy(ss_mode="first-only")
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

    # T-E — activation is bound to the selected release's content, never to
    # the presence of a staged .next file: a stale .next from an interrupted
    # install must never be promoted, and a store-less rollback removes the
    # live store.py for a clean downgrade.
    def test_store_less_rollback_removes_live_store_and_stale_next(self) -> None:
        self.write_release(OLD, with_store=False)
        (self.releases / OLD / "api/app/store.py").unlink()
        store_target = self.live / "api/app/store.py"
        store_next = self.live / "api/app/store.py.next"
        store_target.parent.mkdir(parents=True, exist_ok=True)
        store_target.write_text("# live store from the previous #394 install\n", encoding="utf-8")
        store_next.write_text("# STALE staged store from an interrupted install\n", encoding="utf-8")

        result = self.run_deploy(mode="fail-candidate")

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(self.current(), OLD)
        self.assertIn(OLD, self.api.read_text(), "rollback must restore the store-less release")
        self.assertFalse(store_next.exists(), "stale .next must not survive activation")
        self.assertFalse(
            store_target.exists(),
            "store-less rollback must not keep (or promote) a store.py",
        )
        self.assertEqual(self.manifest()["state"], "rolled_back")

    def test_store_release_stages_and_promotes_normally(self) -> None:
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stdout)
        store_target = self.live / "api/app/store.py"
        self.assertEqual(store_target.read_text(), f"# store fixture {CANDIDATE}\n")
        self.assertFalse((self.live / "api/app/store.py.next").exists())


if __name__ == "__main__":
    unittest.main()