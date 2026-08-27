import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeliveryTodoContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_canonical_entrypoints_require_transient_todo_projection(self):
        required = {
            "AGENTS.md": "structured todo",
            "contracts/SEA_SPEED_GOVERNANCE.md": "todo projection",
            "contracts/SEA_SPEED_DELIVERY_POLICY.md": "todo projection",
            "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md": "Structured todo projection",
            "contracts/branches/project-manager.md": "todo projection",
            "docs/agents/PM_BOOTSTRAP.md": "todo projection",
            ".opencode/agents/sea-speed-delivery-orchestrator.md": "Structured Todo Projection",
        }
        for relative, marker in required.items():
            with self.subTest(path=relative):
                self.assertIn(marker.lower(), self.read(relative).lower())

    def test_todo_is_not_durable_authority(self):
        runtime = self.read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
        governance = self.read("contracts/SEA_SPEED_GOVERNANCE.md")
        agent = self.read(
            ".opencode/agents/sea-speed-delivery-orchestrator.md"
        )
        for text in (runtime, governance, agent):
            lowered = text.lower()
            self.assertIn("todo", lowered)
            self.assertIn("transient", lowered)
            self.assertIn("checkpoint", lowered)
        self.assertIn("Todo is never durable authority", self.read(
            "contracts/SEA_SPEED_DELIVERY_POLICY.md"
        ))

    def test_status_contract_exposes_todo_summary(self):
        runtime = self.read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
        for field in (
            "Todo / current:",
            "Todo / completed since prior visible transition:",
            "Todo / pending or waiting:",
        ):
            self.assertIn(field, runtime)

        agents = self.read("AGENTS.md")
        self.assertIn("current item", agents)
        self.assertIn("completed since the prior visible transition", agents)
        self.assertIn("remaining/waiting items", agents)

    def test_active_wait_and_resume_semantics_are_explicit(self):
        runtime = self.read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
        self.assertIn("Under `ACTIVE` it is executable work", runtime)
        self.assertIn("Under `WAITING_EXTERNAL`", runtime)
        self.assertIn("MUST NOT imply background execution", runtime)
        self.assertIn("Resume Probe reconstructs", runtime)
        self.assertIn("checkpoint evidence wins", runtime)

    def test_todo_status_includes_model_lines(self):
        model_markers = ("Model / orchestrator", "Model / active worker")
        entrypoints = (
            "AGENTS.md",
            "contracts/SEA_SPEED_GOVERNANCE.md",
            "contracts/SEA_SPEED_DELIVERY_POLICY.md",
            "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
            "contracts/branches/project-manager.md",
            "docs/agents/PM_BOOTSTRAP.md",
            ".opencode/agents/sea-speed-delivery-orchestrator.md",
        )
        for relative in entrypoints:
            with self.subTest(path=relative):
                text = self.read(relative)
                for marker in model_markers:
                    self.assertIn(marker, text)
        runtime = self.read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
        self.assertIn("Model / orchestrator:", runtime)
        self.assertIn("Model / active worker:", runtime)

    def test_agent_has_no_gh_repository_lifecycle_fallback(self):
        agent = self.read(
            ".opencode/agents/sea-speed-delivery-orchestrator.md"
        )
        self.assertNotIn("Connector или `gh` fallback", agent)
        self.assertIn(
            "PR/Issue/API lifecycle выполняй только через Connector",
            agent,
        )
        self.assertIn("`gh`", agent)
        self.assertIn("запрещены", agent)

    def test_repository_validation_admits_only_canonical_opencode_paths(self):
        import importlib.util

        module_path = ROOT / "scripts" / "ci" / "validate_repo.py"
        module_spec = importlib.util.spec_from_file_location(
            "validate_repo_under_test", module_path
        )
        assert module_spec is not None
        loader = module_spec.loader
        assert loader is not None
        module = importlib.util.module_from_spec(module_spec)
        loader.exec_module(module)
        canonical = {
            ".opencode/agents/sea-speed-delivery-orchestrator.md",
            ".opencode/project-profile.json",
            ".opencode/delivery-pipeline.json",
        }
        self.assertEqual(module.ALLOWED_EXACT_PATHS, canonical)
        module.validate_paths([Path(path) for path in canonical])
        for rejected in (
            ".opencode/agents/other-agent.md",
            ".opencode/settings.json",
            ".opencode/node_modules/pkg/index.js",
        ):
            with self.subTest(path=rejected):
                with self.assertRaises(SystemExit):
                    module.validate_paths([Path(rejected)])

    def test_reusable_profile_preserves_primary_and_bounded_workers(self):
        profile = json.loads(self.read(
            ".opencode/project-profile.json"
        ))
        self.assertEqual(profile, {
            "version": 1,
            "stack": "auto",
            "delivery": True,
            "sdd": True,
            "github": True,
            "githubOwner": "MostDef2000",
        })
        self.assertEqual(
            json.loads(self.read("opencode.json"))["default_agent"],
            "sea-speed-delivery-orchestrator",
        )
        entrypoints = (
            self.read("AGENTS.md"),
            self.read(".opencode/agents/sea-speed-delivery-orchestrator.md"),
        )
        roles = (
            "profile-worker-explore",
            "profile-worker-architect",
            "profile-worker-code",
            "profile-worker-test",
            "profile-worker-review",
            "profile-worker-ui",
        )
        for text in entrypoints:
            with self.subTest(entrypoint=text[:20]):
                for role in roles:
                    self.assertIn(role, text)
                self.assertIn("primary orchestrator", text)
                self.assertIn("authority boundary", text)
                self.assertIn("SOURCE_AUTHORIZATION_ADMISSION=OPEN", text)
                self.assertNotIn("free-openrouter/", text)
                self.assertNotIn("free-sprutdock/", text)

    def test_delivery_pipeline_matches_local_quality_domains(self):
        manifest = json.loads(self.read(
            ".opencode/delivery-pipeline.json"
        ))
        self.assertEqual(manifest["version"], 1)
        self.assertEqual(
            [gate["id"] for gate in manifest["gates"]],
            [
                "repository",
                "contracts",
                "sdd",
                "quality-contracts",
                "workflow-policy",
                "unittest",
                "property",
                "fuzz-recovery",
                "quality-architecture",
            ],
        )
        for gate in manifest["gates"]:
            self.assertEqual(gate["cwd"], ".")
            self.assertEqual(gate["argv"][0], "python3")
            self.assertGreater(gate["timeoutSeconds"], 0)


if __name__ == "__main__":
    unittest.main()
