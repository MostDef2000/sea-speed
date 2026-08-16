from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "0123456789abcdef0123456789abcdef01234567"
WORKFLOW_POLICY = ROOT / "scripts/quality/validate_workflow_policy.py"


def load_workflow_policy():
    spec = importlib.util.spec_from_file_location("sea_speed_workflow_policy", WORKFLOW_POLICY)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load workflow policy validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QualityArchitectureTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True,
        )

    def test_contracts_properties_fuzz_and_workflow_policy(self) -> None:
        for command in (
            ("scripts/quality/validate_quality_contracts.py",),
            ("scripts/quality/validate_workflow_policy.py",),
            ("scripts/quality/test_properties.py",),
            ("scripts/quality/test_fuzz_recovery.py",),
        ):
            result = self.run_script(*command)
            self.assertIn("passed" if "test_" in command[0] else "valid", result.stdout.lower())

    def test_workflow_policy_rejects_mutable_and_dangerous_workflows(self) -> None:
        policy = load_workflow_policy()
        valid = """name: test
on: workflow_dispatch
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
"""
        policy.validate_workflow_source(valid, "valid.yml")
        invalid_sources = {
            "mutable action": valid.replace("11d5960a326750d5838078e36cf38b85af677262", "v4"),
            "write-all": valid.replace("permissions:\n  contents: read", "permissions: write-all"),
            "dangerous trigger": valid.replace("on: workflow_dispatch", "on:\n  pull_request_target:"),
            "download pipe": valid + "      - run: curl https://example.invalid/tool | bash\n",
            "missing permissions": valid.replace("permissions:\n  contents: read\n", ""),
        }
        for name, source in invalid_sources.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    policy.validate_workflow_source(source, f"{name}.yml")

    def test_quality_workflow_wires_sdd_into_aggregate_dependency(self) -> None:
        quality = (ROOT / ".github/workflows/quality-integration.yml").read_text(encoding="utf-8")
        self.assertIn("validate_sdd.py --event", quality)
        static = quality[quality.index("  static-contract-security:"):quality.index("  property-fuzz-reliability:")]
        self.assertIn("validate_sdd.py", static)
        aggregate = quality[quality.index("  quality-integration:"):]
        self.assertIn("static-contract-security", aggregate)

    def test_deploy_workflow_has_all_admission_guards_before_ssh(self) -> None:
        deploy = (ROOT / ".github/workflows/deploy-vps.yml").read_text(encoding="utf-8")
        configure = deploy.index("Configure SSH")
        for marker in (
            "workflow_dispatch:", "workflow_call:", "refs/heads/main", "--first-parent",
            "verify_quality_status.py", "verify_production_authorization.py", "Build release provenance v2",
        ):
            self.assertLess(deploy.index(marker), configure, marker)
        self.assertIn("environment: production", deploy)
        self.assertNotIn("${INPUT_COMMIT,,}", deploy)

    def test_deploy_first_parent_guard_is_pipefail_safe(self) -> None:
        deploy = (ROOT / ".github/workflows/deploy-vps.yml").read_text(encoding="utf-8")
        self.assertNotIn('git rev-list --first-parent origin/main | grep -Fxq "$DEPLOY_SHA"', deploy)
        self.assertIn("FIRST_PARENT_MATCH=0", deploy)
        self.assertIn("done < <(git rev-list --first-parent origin/main)", deploy)
        self.assertIn('[[ "$FIRST_PARENT_MATCH" == "1" ]] || {', deploy)

    def test_issue_request_delegates_to_reusable_deploy_without_runtime_mutation(self) -> None:
        request = (ROOT / ".github/workflows/deploy-vps-request.yml").read_text(encoding="utf-8")
        self.assertIn("issue_comment:", request)
        self.assertIn("types: [created]", request)
        self.assertIn("!github.event.issue.pull_request", request)
        self.assertIn("startsWith(github.event.comment.body, 'DEPLOY VPS ')", request)
        self.assertIn("scripts/release/parse_deployment_request.py", request)
        self.assertIn("uses: ./.github/workflows/deploy-vps.yml", request)
        self.assertIn("secrets: inherit", request)
        self.assertNotIn("environment: production", request)
        self.assertNotIn("VPS_SSH_PRIVATE_KEY", request)
        self.assertNotIn("ssh -i", request)

    def test_exact_artifacts_are_deterministic_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first"
            second = Path(temp_dir) / "second"
            self.run_script("scripts/quality/build_exact_artifacts.py", "--source-commit", COMMIT, "--output-dir", str(first))
            self.run_script("scripts/quality/build_exact_artifacts.py", "--source-commit", COMMIT, "--output-dir", str(second))
            for component in ("vps", "ubuntu-worker", "edge"):
                filename = f"sea-speed-{component}-{COMMIT}.tar.gz"
                self.assertEqual((first / filename).read_bytes(), (second / filename).read_bytes())
            self.assertEqual((first / "exact-artifacts.json").read_bytes(), (second / "exact-artifacts.json").read_bytes())
            manifest = json.loads((first / "exact-artifacts.json").read_text(encoding="utf-8"))
            self.assertEqual(
                {artifact["component"] for artifact in manifest["artifacts"]},
                {"vps", "edge"},
            )
            self.assertEqual(
                {artifact["component"] for artifact in manifest["release_artifacts"]},
                {"ubuntu-worker"},
            )
            vps = next(artifact for artifact in manifest["artifacts"] if artifact["component"] == "vps")
            vps_paths = {entry["path"] for entry in vps["files"]}
            self.assertIn("frontend/sea-speed/cameras/index.html", vps_paths)
            ubuntu = manifest["release_artifacts"][0]
            ubuntu_paths = {entry["path"] for entry in ubuntu["files"]}
            self.assertIn("deploy/worker/ubuntu/worker-control-agent.py", ubuntu_paths)
            self.assertIn("deploy/worker/ubuntu/update-exact.sh", ubuntu_paths)
            self.assertIn("worker/hls_motion_yolo_worker_events.py", ubuntu_paths)
            self.run_script("scripts/quality/validate_exact_artifacts.py", "--manifest", str(first / "exact-artifacts.json"))

    def test_quality_evidence_binds_legacy_artifacts_while_manifest_binds_ubuntu_release(self) -> None:
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
            manifest = json.loads((exact / "exact-artifacts.json").read_text(encoding="utf-8"))
            self.assertEqual(data["source_commit"], COMMIT)
            self.assertEqual(
                {artifact["component"] for artifact in data["artifacts"]},
                {"vps", "edge"},
            )
            self.assertEqual(manifest["release_artifacts"][0]["component"], "ubuntu-worker")
            self.assertRegex(manifest["release_artifacts"][0]["sha256"], r"^[0-9a-f]{64}$")
            self.assertFalse(data["deployment"]["automatic_from_main"])
            self.assertEqual(data["contracts"]["target_media_mode"], "edge_v2")


if __name__ == "__main__":
    unittest.main()
