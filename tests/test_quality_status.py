from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/quality/verify_quality_status.py"
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


if __name__ == "__main__":
    unittest.main()
