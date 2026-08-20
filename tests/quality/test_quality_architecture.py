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
        return subprocess.run(
            [sys.executable, *args], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True,
        )

    def test_protected_workflow_admission_contracts_remain(self) -> None:
        deploy = (ROOT / ".github/workflows/deploy-vps.yml").read_text(encoding="utf-8")
        ubuntu = (ROOT / ".github/workflows/deploy-ubuntu-worker.yml").read_text(encoding="utf-8")
        autonomous = (ROOT / ".github/workflows/deploy-runtime-autonomous.yml").read_text(encoding="utf-8")
        for source in (deploy, ubuntu):
            self.assertIn("environment: production", source)
            self.assertIn("verify_source_protection.py", source)
            self.assertIn("verify_quality_status.py", source)
            self.assertIn("evaluate_production_policy.py", source)
            self.assertIn("--require-allow", source)
            self.assertIn("--first-parent", source)
            self.assertIn("production-policy-decision.json", source)
            self.assertNotIn("verify_production_authorization.py", source)
            self.assertLess(source.index("verify_source_protection.py"), source.index("evaluate_production_policy.py"))
        self.assertIn("deploy/worker/ubuntu/deploy-authorized.sh", ubuntu)
        self.assertIn("ProxyJump sea-speed-vps-jump", ubuntu)
        self.assertIn("User sea-speed-deploy", ubuntu)
        self.assertIn("Operator actions expected: 0", ubuntu)
        self.assertNotIn("ubuntu-worker-one-command.sh", ubuntu)
        self.assertIn("workflow_run:", autonomous)
        self.assertIn('workflows: ["Quality integration gate"]', autonomous)
        self.assertIn("verify_source_protection.py", autonomous)
        self.assertNotIn("issue_comment:", autonomous)
        for marker in (
            'SEA_SPEED_REQUIRE_AUTH_BOUNDARY: "1"',
            'SEA_SPEED_AUTHENTIK_UPSTREAM: "http://10.123.239.102:19000"',
            'SEA_SPEED_WORKER_PRIVATE_LISTEN: "10.123.239.101:18080"',
            'SEA_SPEED_WORKER_PRIVATE_PEER: "10.123.239.102"',
            "Deploy exact commit and reconcile Road private M2M boundary",
            "auth_v1_road_private_m2m",
        ):
            self.assertIn(marker, deploy)

    def test_source_protection_contract_is_fail_closed(self) -> None:
        source = (ROOT / "scripts/release/verify_source_protection.py").read_text(encoding="utf-8")
        self.assertIn('repository.get("visibility") != "public"', source)
        self.assertIn('branch.get("protected") is not True', source)
        self.assertIn("missing required status checks", source)
        self.assertIn("Repository validation", (ROOT / ".github/workflows/deploy-vps.yml").read_text(encoding="utf-8"))
        self.assertIn("quality-integration", (ROOT / ".github/workflows/deploy-vps.yml").read_text(encoding="utf-8"))

    def test_comment_authority_paths_are_retired_or_fail_closed_tombstones(self) -> None:
        self.assertFalse((ROOT / ".github/workflows/deploy-runtime-request.yml").exists())
        self.assertFalse((ROOT / ".github/workflows/deploy-vps-request.yml").exists())
        self.assertFalse((ROOT / "scripts/release/parse_runtime_execution_request.py").exists())
        self.assertFalse((ROOT / "scripts/release/parse_deployment_request.py").exists())
        verifier = (ROOT / "scripts/release/verify_production_authorization.py").read_text(encoding="utf-8")
        self.assertIn("Retired compatibility tombstone", verifier)
        self.assertIn("return 2", verifier)
        self.assertNotIn("PRODUCTION APPROVED", verifier)
        policy = json.loads((ROOT / "data/contracts/production-authorization-policy-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(policy["status"], "retired-compatibility-tombstone")
        self.assertEqual(policy["authorizedActors"], [])
        self.assertEqual(policy["authority"], "NONE")

    def test_vps_deploy_uses_restricted_privilege_boundary_before_live_mutation(self) -> None:
        source = (ROOT / "deploy/vps/deploy.sh").read_text(encoding="utf-8")
        self.assertIn("check_auth_privilege_boundary", source)
        self.assertIn("PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES", source)
        self.assertIn("SEA_SPEED_AUTH_PRIVILEGE_BOUNDARY=PASS", source)
        self.assertIn("SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS", source)
        self.assertNotIn('run_root bash "$cutover"', source)
        self.assertLess(source.index("check_auth_privilege_boundary"), source.index("bootstrap_current_release"))

    def test_ubuntu_zero_touch_gate_is_bounded(self) -> None:
        gate = (ROOT / "scripts/operations/sea_speed_ubuntu_zero_touch_gate.sh").read_text(encoding="utf-8")
        bootstrap = (ROOT / "scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh").read_text(encoding="utf-8")
        self.assertIn("SSH_ORIGINAL_COMMAND", gate)
        self.assertIn("build_exact_artifacts.py", gate)
        self.assertIn("deploy/worker/ubuntu/deploy-authorized.sh", gate)
        self.assertNotIn("eval ", gate)
        self.assertIn('restrict,command="%s"', bootstrap)
        self.assertNotIn("NOPASSWD: ALL", bootstrap)

    def test_windows_package_workflow_is_retired(self) -> None:
        self.assertFalse((ROOT / ".github/workflows/package-worker.yml").exists())
        autonomous = (ROOT / ".github/workflows/deploy-runtime-autonomous.yml").read_text(encoding="utf-8")
        self.assertNotIn("windows_worker_required", autonomous)
        self.assertNotIn("windows-worker-fallback", autonomous)

    def test_exact_artifacts_are_deterministic_and_bind_active_profiles(self) -> None:
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
                "deploy/vps/sea-speed-auth-cutover.sh", "deploy/vps/install-auth-privilege-boundary.sh",
                "deploy/vps/sea-speed-auth-privileged-helper.py", "scripts/operations/nginx_cam1_direct_h264.py",
                "scripts/operations/nginx_sea_speed_auth.py",
            ):
                self.assertIn(marker, vps_paths)
            self.assertIn("worker/analytics_profiles.py", edge_paths)
            self.assertFalse(any(Path(path).suffix.lower() in {".cmd", ".ps1"} for path in edge_paths))
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
            self.run_script(
                "scripts/quality/build_quality_evidence.py", "--source-commit", COMMIT,
                "--artifacts-manifest", str(exact / "exact-artifacts.json"), "--output", str(evidence),
            )
            self.run_script(
                "scripts/quality/validate_quality_evidence.py", "--evidence", str(evidence),
                "--artifacts-manifest", str(exact / "exact-artifacts.json"),
            )
            data = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertEqual({a["component"] for a in data["artifacts"]}, {"vps", "edge"})


if __name__ == "__main__":
    unittest.main()
