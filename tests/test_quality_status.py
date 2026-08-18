from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/quality/verify_quality_status.py"
WORKFLOW_PATH = ROOT / ".github/workflows/main-quality-status.yml"
spec = importlib.util.spec_from_file_location("verify_quality_status", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SHA = "a" * 40


class QualityStatusTests(unittest.TestCase):
    def test_accepts_exact_successful_main_push_run(self) -> None:
        payload = {"workflow_runs": [{"id": 1, "run_number": 9, "head_sha": SHA, "head_branch": "main", "event": "push", "status": "completed", "conclusion": "success"}]}
        with patch.object(module, "github_json", return_value=payload):
            run = module.verify("MostDef2000/sea-speed", SHA, "token")
        self.assertEqual(run["id"], 1)

    def test_pr_run_is_not_production_quality_proof(self) -> None:
        payload = {"workflow_runs": [{"id": 2, "run_number": 10, "head_sha": SHA, "head_branch": "feature", "event": "pull_request", "status": "completed", "conclusion": "success"}]}
        with patch.object(module, "github_json", return_value=payload):
            with self.assertRaisesRegex(ValueError, "push run on main"):
                module.verify("MostDef2000/sea-speed", SHA, "token")

    def test_uppercase_sha_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "lowercase"):
            module.verify("MostDef2000/sea-speed", SHA.upper(), "token")


class MainQualityStatusPublisherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_uses_completed_quality_workflow_run_only(self) -> None:
        self.assertIn("workflow_run:", self.source)
        self.assertIn("Quality integration gate", self.source)
        self.assertIn("- completed", self.source)
        self.assertNotIn("pull_request_target:", self.source)

    def test_publishes_only_main_push_runs(self) -> None:
        self.assertIn("github.event.workflow_run.event == 'push'", self.source)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", self.source)
        self.assertIn("github.event.workflow_run.head_sha", self.source)
        self.assertIn("^[0-9a-f]{40}$", self.source)

    def test_permission_boundary_is_statuses_write_only(self) -> None:
        permissions = self.source.split("permissions:", 1)[1].split("jobs:", 1)[0]
        self.assertIn("statuses: write", permissions)
        for forbidden in ("contents: write", "issues: write", "pull-requests: write", "actions: write", "deployments: write", "id-token: write"):
            self.assertNotIn(forbidden, permissions)
        self.assertNotIn("actions/checkout", self.source)
        self.assertIsNone(re.search(r"(?m)^\s*-?\s*uses:\s*", self.source))

    def test_fixed_context_and_run_identity_are_published(self) -> None:
        self.assertIn('"context": "sea-speed/quality-push-main"', self.source)
        self.assertIn("workflow_run.id", self.source)
        self.assertIn("workflow_run.run_number", self.source)
        self.assertIn("workflow_run.html_url", self.source)
        self.assertIn("workflow_run.conclusion", self.source)
        self.assertIn('/statuses/${HEAD_SHA}', self.source)

    def test_conclusion_mapping_is_fail_closed(self) -> None:
        self.assertIn('if [[ "$RUN_CONCLUSION" == "success" ]]', self.source)
        self.assertIn('STATE="success"', self.source)
        self.assertIn('STATE="failure"', self.source)


if __name__ == "__main__":
    unittest.main()
