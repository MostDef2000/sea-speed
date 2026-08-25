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


if __name__ == "__main__":
    unittest.main()
