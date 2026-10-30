from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Iterator

# PyYAML is a test-only dependency: the battery jobs install pyyaml==6.0.3
# (pr-validation.yml, quality-integration.yml) and run every test here; the
# stdlib-only property-fuzz-reliability job runs this module without it, so the
# two yaml-consuming tests skip LOUDLY there instead of breaking the import
# (issue #398 wave 2; CI failure 40443050987).
try:
    import yaml  # noqa: F401
    HAS_YAML = True
except ModuleNotFoundError:  # pragma: no cover - exercised by the stdlib-only CI job
    HAS_YAML = False


def _yaml_load(text: str) -> Any:
    """Parse YAML in tests that require the test-only parser (see HAS_YAML)."""
    import yaml

    return yaml.safe_load(text)

from tests.support import worker_source

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "0123456789abcdef0123456789abcdef01234567"


def walk_strings(node: Any) -> Iterator[str]:
    """Every string value reachable in a parsed YAML structure (issue #398)."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from walk_strings(key)
            yield from walk_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_strings(item)


class QualityArchitectureTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True,
        )

    @unittest.skipUnless(HAS_YAML, "PyYAML not installed (stdlib-only property-fuzz job); battery jobs run this test")
    def test_protected_workflow_admission_contracts_remain(self) -> None:
        # Structured workflow contracts (issue #398 wave 2): shapes are parsed
        # with yaml.safe_load instead of substring pins; the retirement bans
        # (STATIC_POLICY: textual absence is the contract) stay verbatim.
        deploy_text = (ROOT / ".github/workflows/deploy-vps.yml").read_text(encoding="utf-8")
        ubuntu_text = (ROOT / ".github/workflows/deploy-ubuntu-worker.yml").read_text(encoding="utf-8")
        autonomous_text = (ROOT / ".github/workflows/deploy-runtime-autonomous.yml").read_text(encoding="utf-8")
        deploy = _yaml_load(deploy_text)
        ubuntu = _yaml_load(ubuntu_text)
        autonomous = _yaml_load(autonomous_text)

        # The shared composite action is the structured carrier of the
        # exact-release verification chain: source protection, first-parent
        # main membership, aggregate quality status, then standing-delegation
        # policy evaluation with the require-allow switch the deploy
        # workflows bind.
        verify_action = _yaml_load(
            (ROOT / ".github/actions/verify-exact-release/action.yml").read_text(encoding="utf-8")
        )
        action_strings = "\n".join(walk_strings(verify_action["runs"]["steps"]))
        chain_positions = [
            action_strings.index("verify_source_protection.py"),
            action_strings.index("verify_quality_status.py"),
            action_strings.index("evaluate_production_policy.py"),
        ]
        self.assertEqual(chain_positions, sorted(chain_positions))
        self.assertIn("--require-allow", action_strings)
        self.assertIn("--first-parent", action_strings)
        self.assertIn('require-context "Repository validation"', action_strings)

        for workflow, text in ((deploy, deploy_text), (ubuntu, ubuntu_text)):
            job = workflow["jobs"]["deploy"]
            self.assertEqual(job["environment"], "production")
            verify_step = next(step for step in job["steps"] if step.get("id") == "verify")
            self.assertEqual(verify_step["uses"], "./.github/actions/verify-exact-release")
            self.assertEqual(verify_step["with"]["require_allow"], "true")
            job_strings = "\n".join(walk_strings(job))
            self.assertIn("production-policy-decision.json", job_strings)
            self.assertNotIn("verify_production_authorization.py", text)  # STATIC_POLICY: retired verifier never re-enters the pipeline

        ubuntu_strings = "\n".join(walk_strings(ubuntu["jobs"]["deploy"]))
        self.assertIn("deploy/worker/ubuntu/deploy-authorized.sh", ubuntu_strings)
        self.assertIn("ProxyJump sea-speed-vps-jump", ubuntu_strings)
        self.assertIn("User sea-speed-deploy", ubuntu_strings)
        self.assertIn("Operator actions expected: 0", ubuntu_strings)
        self.assertNotIn("ubuntu-worker-one-command.sh", ubuntu_text)  # STATIC_POLICY: retired one-command path stays retired

        # The autonomous router triggers only on the aggregate quality gate.
        autonomous_triggers = autonomous.get(True, autonomous.get("on", {}))
        self.assertEqual(autonomous_triggers["workflow_run"]["workflows"], ["Quality integration gate"])
        evaluate_strings = "\n".join(walk_strings(autonomous["jobs"]["evaluate"]))
        self.assertEqual(autonomous["jobs"]["evaluate"]["environment"], "production")
        self.assertIn("verify_source_protection.py", evaluate_strings)
        self.assertNotIn("issue_comment:", autonomous_text)  # STATIC_POLICY: comments are non-authoritative

        # The Road private M2M boundary travels with the VPS deploy step.
        deploy_job = deploy["jobs"]["deploy"]
        self.assertEqual(
            deploy_job["env"],
            {
                "SEA_SPEED_REQUIRE_AUTH_BOUNDARY": "1",
                "SEA_SPEED_AUTHENTIK_UPSTREAM": "http://10.123.239.102:19000",
                "SEA_SPEED_WORKER_PRIVATE_LISTEN": "10.123.239.29:18080",
                "SEA_SPEED_WORKER_PRIVATE_PEER": "10.123.239.102",
            },
        )
        self.assertTrue(
            any(
                step.get("name") == "Deploy exact commit and reconcile Road private M2M boundary"
                for step in deploy_job["steps"]
            ),
            "reconcile step missing from deploy-vps.yml",
        )
        self.assertIn("auth_v1_road_private_m2m", "\n".join(walk_strings(deploy_job)))

    @unittest.skipUnless(HAS_YAML, "PyYAML not installed (stdlib-only property-fuzz job); battery jobs run this test")
    def test_source_protection_contract_is_fail_closed(self) -> None:
        # AST conversion (issue #398 wave 2): the fail-closed comparisons and
        # the required-status-checks refusal are parsed from the verifier
        # instead of pinned as raw substrings, so harmless refactoring cannot
        # break them while any loosening of the guards still fails RED.
        source = (ROOT / "scripts/release/verify_source_protection.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertTrue(worker_source.contains_expr(tree, 'repository.get("visibility") != "public"'))
        self.assertTrue(worker_source.contains_expr(tree, 'branch.get("protected") is not True'))
        self.assertTrue(
            any("missing required status checks" in constant for constant in worker_source.string_constants(tree)),
            "required-status-checks refusal message missing from verify_source_protection.py",
        )
        # The deploy chain requires the two status contexts through the shared
        # action (structured), not by comment text in the workflow files.
        verify_action = _yaml_load(
            (ROOT / ".github/actions/verify-exact-release/action.yml").read_text(encoding="utf-8")
        )
        action_strings = "\n".join(walk_strings(verify_action["runs"]["steps"]))
        self.assertIn('--require-context "Repository validation"', action_strings)
        self.assertIn('--workflow-file quality-integration.yml', action_strings)

    def test_comment_authority_paths_are_retired_or_fail_closed_tombstones(self) -> None:
        self.assertFalse((ROOT / ".github/workflows/deploy-runtime-request.yml").exists())
        self.assertFalse((ROOT / ".github/workflows/deploy-vps-request.yml").exists())
        self.assertFalse((ROOT / "scripts/release/parse_runtime_execution_request.py").exists())
        self.assertFalse((ROOT / "scripts/release/parse_deployment_request.py").exists())
        # Executed tombstone (issue #398 wave 2): the retired verifier is run
        # for real — it must fail closed with exit code 2 and the retirement
        # error, not just contain the right text.
        result = subprocess.run(
            [sys.executable, "scripts/release/verify_production_authorization.py"],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("retired", (result.stderr + result.stdout).lower())
        verifier = (ROOT / "scripts/release/verify_production_authorization.py").read_text(encoding="utf-8")
        self.assertNotIn("PRODUCTION APPROVED", verifier)  # STATIC_POLICY: comment authority stays retired
        policy = json.loads((ROOT / "data/contracts/production-authorization-policy-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(policy["status"], "retired-compatibility-tombstone")
        self.assertEqual(policy["authorizedActors"], [])
        self.assertEqual(policy["authority"], "NONE")

    def test_vps_deploy_verifies_unprivileged_caddy_boundary_before_live_mutation(self) -> None:
        # STATIC_POLICY: the privileged nginx-helper pipeline markers are
        # retired from the pipeline — their textual absence is the retirement
        # contract and stays pinned verbatim. The fail-closed verifier markers
        # and their before-mutation ordering are asserted behaviorally by the
        # executed deploy.sh twins in tests/test_vps_deploy_transaction.py
        # (bind-absent failures before manifest, degraded-path recovery,
        # post-mutation rollback), so they are not re-pinned here
        # (issue #398 wave 2).
        source = (ROOT / "deploy/vps/deploy.sh").read_text(encoding="utf-8")
        self.assertNotIn("check_auth_privilege_boundary", source)
        self.assertNotIn("PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES", source)
        self.assertNotIn("SEA_SPEED_AUTH_PRIVILEGE_BOUNDARY=PASS", source)
        self.assertNotIn("SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS", source)
        self.assertNotIn('run_root bash "$cutover"', source)

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
        # STATIC_POLICY (issue #398 wave 8): byte-absence of the retired
        # Windows fallback markers IS the contract — parsed-structure absence
        # would let markers survive in comments; the tombstone check above
        # covers file absence.
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
                "deploy/vps/sea-speed-auth-privileged-helper.py", "deploy/vps/sea-speed-nginx-zerotier-wait.sh",
                "deploy/vps/sea-speed-nginx-zerotier.conf", "scripts/operations/nginx_cam1_direct_h264.py",
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
