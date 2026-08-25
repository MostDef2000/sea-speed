import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GitHubActionsConnectorContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_opencode_uses_official_secret_free_remote_connector(self):
        config = json.loads(self.read("opencode.json"))
        github = config["mcp"]["github"]
        self.assertEqual(github["type"], "remote")
        self.assertEqual(github["url"], "https://api.githubcopilot.com/mcp/")
        self.assertTrue(github["enabled"])
        self.assertFalse(github["oauth"])
        self.assertEqual(
            github["headers"]["Authorization"],
            "Bearer {env:GH_TOKEN}",
        )
        self.assertEqual(
            github["headers"]["X-MCP-Toolsets"].split(","),
            ["context", "repos", "issues", "pull_requests", "actions"],
        )
        serialized = json.dumps(config)
        self.assertNotIn("@modelcontextprotocol/server-github", serialized)
        self.assertNotRegex(serialized, r"(?:ghp|github_pat)_[A-Za-z0-9_]{20,}")

    def test_canonical_contracts_require_exact_actions_preflight(self):
        paths = (
            "AGENTS.md",
            "contracts/SEA_SPEED_GOVERNANCE.md",
            "contracts/SEA_SPEED_DELIVERY_POLICY.md",
            "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
            "contracts/runtime/RELEASE_READINESS_GATE.md",
            "contracts/branches/project-manager.md",
            "docs/agents/PM_BOOTSTRAP.md",
            ".opencode/agents/sea-speed-delivery-orchestrator.md",
        )
        for relative in paths:
            with self.subTest(path=relative):
                text = self.read(relative)
                for tool in (
                    "actions_list",
                    "actions_get",
                    "get_job_logs",
                    "actions_run_trigger",
                ):
                    self.assertIn(tool, text)

    def test_trigger_methods_are_bounded_and_destructive_methods_denied(self):
        paths = (
            "AGENTS.md",
            "contracts/SEA_SPEED_GOVERNANCE.md",
            "contracts/SEA_SPEED_DELIVERY_POLICY.md",
            "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
            "contracts/runtime/RELEASE_READINESS_GATE.md",
            "contracts/branches/project-manager.md",
            "docs/agents/PM_BOOTSTRAP.md",
            ".opencode/agents/sea-speed-delivery-orchestrator.md",
        )
        for relative in paths:
            with self.subTest(path=relative):
                text = self.read(relative)
                for method in (
                    "run_workflow",
                    "rerun_workflow_run",
                    "rerun_failed_jobs",
                    "cancel_workflow_run",
                    "delete_workflow_run_logs",
                ):
                    self.assertIn(method, text)
                lowered = text.lower()
                self.assertIn("destructive", lowered)
                self.assertIn("authoriz", lowered)
                denial = ("forbidden", "запрещены", "fail closed",
                          "scope", "authoriz", "approval")
                for line in text.splitlines():
                    if "cancel_workflow_run" in line or "delete_workflow_run_logs" in line:
                        with self.subTest(path=relative, line=line.strip()[:80]):
                            lowered_line = line.lower()
                            self.assertIn("destructive", lowered_line)
                            self.assertTrue(
                                any(phrase in lowered_line for phrase in denial),
                                f"destructive method without denial context: {line.strip()}",
                            )

    def test_repository_validation_tracks_config_without_relaxing_opencode(self):
        module_path = ROOT / "scripts" / "ci" / "validate_repo.py"
        spec = importlib.util.spec_from_file_location(
            "validate_repo_actions_contract", module_path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn("opencode.json", module.ALLOWED_TOP_LEVEL)
        self.assertIn("opencode.json", module.REQUIRED_FILES)
        self.assertEqual(
            module.ALLOWED_EXACT_PATHS,
            {".opencode/agents/sea-speed-delivery-orchestrator.md"},
        )


if __name__ == "__main__":
    unittest.main()
