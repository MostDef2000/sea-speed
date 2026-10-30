import json
import unittest
from pathlib import Path

from tests.support import markdown_docs


ROOT = Path(__file__).resolve().parents[1]


class DeliveryTodoContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_canonical_entrypoints_require_transient_todo_projection(self):
        # SS twins (issue #398 wave 6): every entrypoint must carry its
        # todo-projection vocabulary together with the transient-state
        # classification in ONE parsed section (the retired pin accepted the
        # marker anywhere in the file; PM_BOOTSTRAP states the projection in
        # its Required behavior bootstrap without the transient wording, so
        # its twin is section-scoped to Required behavior). The runtime and
        # the orchestrator agent must keep dedicated todo-projection
        # sections.
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
                text = self.read(relative)
                if relative == "docs/agents/PM_BOOTSTRAP.md":
                    section = markdown_docs.section_titled(text, "Required behavior")
                    self.assertIsNotNone(section)
                    self.assertIn(marker.lower(), (section[0] + section[1]).lower())
                else:
                    section = markdown_docs.section_containing(text, marker, "transient")
                    self.assertIsNotNone(section, relative)
        runtime = self.read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
        self.assertIsNotNone(markdown_docs.section_titled(runtime, "Structured todo projection"))
        agent = self.read(".opencode/agents/sea-speed-delivery-orchestrator.md")
        self.assertIsNotNone(markdown_docs.section_titled(agent, "Structured Todo Projection"))

    def test_todo_is_not_durable_authority(self):
        # SS twins (issue #398 wave 6): runtime, governance and the
        # orchestrator agent must classify todo as transient against the
        # durable checkpoint in ONE section each (the retired pin accepted
        # the three vocabulary words anywhere in the file). SP keep: the
        # DELIVERY_POLICY ban wording "Todo is never durable authority" IS
        # the policy — it stays verbatim, placement-pinned to the section
        # that carries the todo-projection rule.
        for relative in (
            "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
            "contracts/SEA_SPEED_GOVERNANCE.md",
            ".opencode/agents/sea-speed-delivery-orchestrator.md",
        ):
            section = markdown_docs.section_containing(
                self.read(relative), "todo", "transient", "checkpoint"
            )
            self.assertIsNotNone(section, relative)
        policy = self.read("contracts/SEA_SPEED_DELIVERY_POLICY.md")
        section = markdown_docs.section_containing(
            policy, "Todo is never durable authority", "transient"
        )
        self.assertIsNotNone(section)

    def test_status_contract_exposes_todo_summary(self):
        # SS twins (issue #398 wave 6): the runtime todo display block is the
        # EXACT five-line fenced set (three todo fields plus the two model
        # lines) inside the Structured todo projection section, and the
        # Required status block template carries the colon-variant fields as
        # exact list lines (the retired pins accepted the fragments anywhere
        # in the file). AGENTS must co-locate the three todo-summary
        # fragments in one section.
        runtime = self.read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
        section = markdown_docs.section_titled(runtime, "Structured todo projection")
        self.assertIsNotNone(section)
        display_blocks = [
            block
            for block in markdown_docs.fenced_blocks(section[1])
            if any("Todo / current" in line for line in block)
        ]
        self.assertEqual(len(display_blocks), 1)
        self.assertEqual(
            {line.strip() for line in display_blocks[0]},
            {
                "Todo / current",
                "Todo / completed since prior visible transition",
                "Todo / pending or waiting",
                "Model / orchestrator",
                "Model / active worker",
            },
        )
        status_section = markdown_docs.section_titled(runtime, "Required status block")
        self.assertIsNotNone(status_section)
        template_blocks = [
            block
            for block in markdown_docs.fenced_blocks(status_section[1])
            if any(line.strip() == "- Todo / current:" for line in block)
        ]
        self.assertEqual(len(template_blocks), 1)
        template_lines = {line.strip() for line in template_blocks[0]}
        for field in (
            "- Todo / current:",
            "- Todo / completed since prior visible transition:",
            "- Todo / pending or waiting:",
        ):
            self.assertIn(field, template_lines, field)

        agents = self.read("AGENTS.md")
        section = markdown_docs.section_containing(
            agents,
            "current item",
            "completed since the prior visible transition",
            "remaining/waiting items",
        )
        self.assertIsNotNone(section)

    def test_active_wait_and_resume_semantics_are_explicit(self):
        # SS placement twin (issue #398 wave 6): all five todo
        # wait/resume/authority literals live in the runtime Structured todo
        # projection section (the retired pin accepted them anywhere in the
        # file); drift into another section now fails.
        runtime = self.read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
        section = markdown_docs.section_titled(runtime, "Structured todo projection")
        self.assertIsNotNone(section)
        for literal in (
            "Under `ACTIVE` it is executable work",
            "Under `WAITING_EXTERNAL`",
            "MUST NOT imply background execution",
            "Resume Probe reconstructs",
            "checkpoint evidence wins",
        ):
            self.assertIn(literal, section[1], literal)

    def test_todo_status_includes_model_lines(self):
        # SS twins (issue #398 wave 6): both model lines must co-occur in ONE
        # section of every entrypoint (the retired pin accepted them
        # anywhere in the file), and the runtime Required status block
        # template carries them as exact list lines.
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
                section = markdown_docs.section_containing(text, *model_markers)
                self.assertIsNotNone(section, relative)
        runtime = self.read("contracts/runtime/SEA_SPEED_TASK_RUNTIME.md")
        status_section = markdown_docs.section_titled(runtime, "Required status block")
        self.assertIsNotNone(status_section)
        template_blocks = [
            block
            for block in markdown_docs.fenced_blocks(status_section[1])
            if any(line.strip() == "- Model / orchestrator:" for line in block)
        ]
        self.assertEqual(len(template_blocks), 1)
        template_lines = {line.strip() for line in template_blocks[0]}
        self.assertIn("- Model / orchestrator:", template_lines)
        self.assertIn("- Model / active worker:", template_lines)

    def test_agent_has_no_gh_repository_lifecycle_fallback(self):
        # SP keep (issue #398 wave 6): the Russian agent-file routing rules
        # are literal policy — the banned `gh` fallback phrasing must stay
        # absent and the Connector-only lifecycle requirement (with the
        # forbidden-verb wording) present verbatim. There is no structural
        # twin for a negative routing ban; the literals ARE the contract.
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
