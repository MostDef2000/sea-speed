from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "0123456789abcdef0123456789abcdef01234567"


class QualityArchitectureTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)

    def test_protected_workflow_admission_contracts_remain(self) -> None:
        deploy = (ROOT / ".github/workflows/deploy-vps.yml").read_text(encoding="utf-8")
        ubuntu = (ROOT / ".github/workflows/deploy-ubuntu-worker.yml").read_text(encoding="utf-8")
        for source in (deploy, ubuntu):
            self.assertIn("environment: production", source)
            self.assertIn("verify_quality_status.py", source)
            self.assertIn("verify_production_authorization.py", source)
            self.assertIn("--first-parent", source)
        self.assertIn("deploy/worker/ubuntu/deploy-authorized.sh", ubuntu)
        for marker in (
            'SEA_SPEED_REQUIRE_AUTH_BOUNDARY: "1"',
            'SEA_SPEED_AUTHENTIK_UPSTREAM: "http://10.123.239.102:19000"',
            'SEA_SPEED_WORKER_PRIVATE_LISTEN: "10.123.239.101:18080"',
            'SEA_SPEED_WORKER_PRIVATE_PEER: "10.123.239.102"',
            "Deploy exact commit and reconcile Road private M2M boundary",
            "auth_v1_road_private_m2m",
        ):
            self.assertIn(marker, deploy)

    def test_vps_deploy_uses_restricted_privilege_boundary_before_live_mutation(self) -> None:
        source = (ROOT / "deploy/vps/deploy.sh").read_text(encoding="utf-8")
        self.assertIn("check_auth_privilege_boundary", source)
        self.assertIn("PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES", source)
        self.assertIn("SEA_SPEED_AUTH_PRIVILEGE_BOUNDARY=PASS", source)
        self.assertIn("SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS", source)
        self.assertNotIn('run_root bash "$cutover"', source)
        self.assertLess(source.index("check_auth_privilege_boundary"), source.index("bootstrap_current_release"))

    def test_windows_package_remains_pre_release_only(self) -> None:
        package = (ROOT / ".github/workflows/package-worker.yml").read_text(encoding="utf-8")
        self.assertIn('- "worker/**"', package)
        self.assertIn("commit-sha.txt", package)
        self.assertIn("sea-speed-worker.zip.sha256", package)
        self.assertNotIn("release-manifest-windows-worker.json", package)

    def test_exact_artifacts_are_deterministic_and_bind_new_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first"
            second = Path(temp_dir) / "second"
            self.run_script("scripts/quality/build_exact_artifacts.py", "--source-commit", COMMIT, "--output-dir", str(first))
            self.run_script("scripts/quality/build_exact_artifacts.py", "--source-commit", COMMIT, "--output-dir", str(second))
            for component in ("vps", "ubuntu-worker", "edge"):
                filename = f"sea-speed-{component}-{COMMIT}.tar.gz"
                self.assertEqual((first / filename).read_bytes(), (second / filename).read_bytes())
            manifest = json.loads((first / "exact-artifacts.json").read_text(encoding="utf-8"))
            vps = next(a for a in manifest["artifacts"] if a["component"] == "vps")
            edge = next(a for a in manifest["artifacts"] if a["component"] == "edge")
            ubuntu = manifest["release_artifacts"][0]
            vps_paths = {x["path"] for x in vps["files"]}
            edge_paths = {x["path"] for x in edge["files"]}
            ubuntu_paths = {x["path"] for x in ubuntu["files"]}
            self.assertIn("frontend/sea-speed/road/index.html", vps_paths)
            for marker in (
                "deploy/vps/sea-speed-auth-cutover.sh",
                "deploy/vps/install-auth-privilege-boundary.sh",
                "deploy/vps/sea-speed-auth-privileged-helper.py",
                "scripts/operations/nginx_cam1_direct_h264.py",
                "scripts/operations/nginx_sea_speed_auth.py",
            ):
                self.assertIn(marker, vps_paths)
            self.assertIn("worker/analytics_profiles.py", edge_paths)
            for marker in (
                "worker/analytics_profiles.py", "deploy/worker/ubuntu/road-worker.env.example",
                "deploy/worker/ubuntu/sea-speed-road-worker.service.template",
                "deploy/worker/ubuntu/configure-analytics-profiles.py", "deploy/worker/ubuntu/prepare-yolo-model.py",
            ):
                self.assertIn(marker, ubuntu_paths)
            for artifact in [*manifest["artifacts"], *manifest["release_artifacts"]]:
                self.assertFalse(any(x["path"].endswith((".pt", ".onnx", ".engine")) for x in artifact["files"]))
            self.run_script("scripts/quality/validate_exact_artifacts.py", "--manifest", str(first / "exact-artifacts.json"))

    def test_quality_evidence_still_binds_vps_and_edge_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            exact = Path(temp_dir) / "exact"
            evidence = Path(temp_dir) / "quality-evidence.json"
            self.run_script("scripts/quality/build_exact_artifacts.py", "--source-commit", COMMIT, "--output-dir", str(exact))
            self.run_script("scripts/quality/build_quality_evidence.py", "--source-commit", COMMIT, "--artifacts-manifest", str(exact / "exact-artifacts.json"), "--output", str(evidence))
            self.run_script("scripts/quality/validate_quality_evidence.py", "--evidence", str(evidence), "--artifacts-manifest", str(exact / "exact-artifacts.json"))
            data = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertEqual({a["component"] for a in data["artifacts"]}, {"vps", "edge"})


if __name__ == "__main__":
    unittest.main()
