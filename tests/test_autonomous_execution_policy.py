from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_PATH = ROOT / "scripts/release/evaluate_production_policy.py"
spec = importlib.util.spec_from_file_location("evaluate_production_policy", EVALUATOR_PATH)
assert spec and spec.loader
EVALUATOR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(EVALUATOR)

CHANGE_POLICY = json.loads(
    (ROOT / "data/contracts/change-control-policy-v1.json").read_text(encoding="utf-8")
)


class AutonomousExecutionPolicyTests(unittest.TestCase):
    def test_legacy_comment_trigger_workflows_are_absent(self):
        self.assertFalse((ROOT / ".github/workflows/deploy-runtime-request.yml").exists())
        self.assertFalse((ROOT / ".github/workflows/deploy-vps-request.yml").exists())

    def test_autonomous_router_uses_current_tip_quality_and_trusted_environment_state(self):
        source = (ROOT / ".github/workflows/deploy-runtime-autonomous.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_run:", source)
        self.assertIn('workflows: ["Quality integration gate"]', source)
        self.assertIn("github.event.workflow_run.event == 'push'", source)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", source)
        self.assertIn("Require quality commit is current main tip", source)
        self.assertIn("refs/remotes/origin/main", source)
        self.assertIn("Ignoring stale successful Quality run", source)
        self.assertIn("steps.freshness.outputs.fresh == 'true'", source)
        self.assertIn("environment: production", source)
        self.assertIn("vars.SEA_SPEED_PRODUCTION_DELEGATION_V1", source)
        self.assertIn("evaluate_production_policy.py", source)
        self.assertNotIn("issue_comment:", source)
        self.assertNotIn("PRODUCTION APPROVED", source)
        self.assertNotIn("Execution-Intent: EXECUTE", source)

    def test_protected_deploy_workflows_re_evaluate_policy(self):
        for name in ("deploy-vps.yml", "deploy-ubuntu-worker.yml"):
            source = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn("evaluate_production_policy.py", source)
            self.assertIn("--require-allow", source)
            self.assertIn("vars.SEA_SPEED_PRODUCTION_DELEGATION_V1", source)
            self.assertNotIn("verify_production_authorization.py", source)
            self.assertNotIn("PRODUCTION APPROVED", source)

    def test_repository_text_cannot_become_authority_input(self):
        evaluator = EVALUATOR_PATH.read_text(encoding="utf-8")
        self.assertIn("SEA_SPEED_PRODUCTION_DELEGATION_V1", evaluator)
        self.assertNotIn("/comments", evaluator)
        self.assertNotIn("PRODUCTION APPROVED", evaluator)
        self.assertNotIn("authorizedActors", evaluator)

    def test_runtime_contours_are_derived_from_exact_source_paths(self):
        vps, active_vps = EVALUATOR.derive_release_contract(["api/app/main.py"], CHANGE_POLICY)
        self.assertEqual(vps, {"productionImpact": "VPS", "vps": "REQUIRED", "ubuntuWorkerRelay": "NOT REQUIRED"})
        self.assertEqual(active_vps, {"VPS"})
        mixed, active_mixed = EVALUATOR.derive_release_contract(
            ["frontend/sea-speed/index.html", "worker/runtime.py"], CHANGE_POLICY
        )
        self.assertEqual(mixed["productionImpact"], "MIXED")
        self.assertEqual(active_mixed, {"VPS", "UBUNTU_WORKER"})

    def test_authentik_blueprint_routes_to_ubuntu_not_vps(self):
        contours, active = EVALUATOR.derive_release_contract(
            ["deploy/vps/authentik/blueprints/sea-speed-auth-v1.yaml"], CHANGE_POLICY
        )
        self.assertEqual(
            contours,
            {
                "productionImpact": "UBUNTU_WORKER",
                "vps": "NOT REQUIRED",
                "ubuntuWorkerRelay": "REQUIRED",
            },
        )
        self.assertEqual(active, {"UBUNTU_WORKER"})
        self.assertEqual(CHANGE_POLICY["rules"][0]["impact"], "UBUNTU_WORKER")
        self.assertIn("deploy/vps/authentik/blueprints/**", CHANGE_POLICY["rules"][0]["patterns"])

    def test_mutable_pr_runtime_metadata_must_match_derived_contours(self):
        derived = {"productionImpact": "VPS", "vps": "REQUIRED", "ubuntuWorkerRelay": "NOT REQUIRED"}
        valid = {
            "Production impact": "VPS",
            "VPS deployment": "REQUIRED",
            "Ubuntu worker/relay update": "NOT REQUIRED",
            "VPS execution capability": "CONNECTOR",
            "Ubuntu worker execution capability": "NOT APPLICABLE",
        }
        self.assertEqual(
            EVALUATOR.validate_pr_runtime_metadata(valid, derived, {"VPS"}),
            {"vps": "CONNECTOR", "ubuntuWorkerRelay": "NOT APPLICABLE"},
        )
        tampered = dict(valid)
        tampered["VPS deployment"] = "NOT REQUIRED"
        with self.assertRaises(EVALUATOR.PolicyError):
            EVALUATOR.validate_pr_runtime_metadata(tampered, derived, {"VPS"})


if __name__ == "__main__":
    unittest.main()
