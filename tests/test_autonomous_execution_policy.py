from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AutonomousExecutionPolicyTests(unittest.TestCase):
    def test_legacy_comment_trigger_workflows_are_absent(self):
        self.assertFalse((ROOT / ".github/workflows/deploy-runtime-request.yml").exists())
        self.assertFalse((ROOT / ".github/workflows/deploy-vps-request.yml").exists())

    def test_autonomous_router_uses_quality_workflow_run_and_trusted_environment_state(self):
        source = (ROOT / ".github/workflows/deploy-runtime-autonomous.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_run:", source)
        self.assertIn('workflows: ["Quality integration gate"]', source)
        self.assertIn("github.event.workflow_run.event == 'push'", source)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", source)
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
        evaluator = (ROOT / "scripts/release/evaluate_production_policy.py").read_text(encoding="utf-8")
        self.assertIn("SEA_SPEED_PRODUCTION_DELEGATION_V1", evaluator)
        self.assertNotIn("/comments", evaluator)
        self.assertNotIn("PRODUCTION APPROVED", evaluator)
        self.assertNotIn("authorizedActors", evaluator)


if __name__ == "__main__":
    unittest.main()
