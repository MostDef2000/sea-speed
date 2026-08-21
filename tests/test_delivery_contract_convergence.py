from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DeliveryContractConvergenceTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8-sig")

    def test_delivery_orchestrator_is_canonical_owner(self) -> None:
        contract = self.read("contracts/branches/project-manager.md")
        self.assertIn("Role: Sea Speed Delivery Orchestrator", contract)
        self.assertIn("compatibility path", contract.lower())
        self.assertNotIn("Role: Sea Speed Project Manager", contract)

    def test_core_and_domain_contracts_are_review_lenses(self) -> None:
        paths = [
            "contracts/branches/core-release.md", "contracts/branches/api.md", "contracts/branches/frontend.md",
            "contracts/branches/worker.md", "contracts/branches/deploy.md", "contracts/branches/diagnostics.md",
            "contracts/branches/review.md", "contracts/branches/governance.md",
        ]
        for path in paths:
            text = self.read(path)
            self.assertIn("Review Lens", text, path)
            self.assertIn("Delivery Orchestrator", text, path)

    def test_source_authorization_remains_outcome_approved(self) -> None:
        template = self.read(".github/pull_request_template.md")
        validator = self.read("scripts/ci/validate_change_contract.py")
        self.assertIn("Source authorization: OUTCOME APPROVED", template)
        self.assertNotIn("LEGACY COMMIT APPROVED", template)
        self.assertIn('SOURCE_AUTHORIZATIONS = {"OUTCOME APPROVED"}', validator)

    def test_active_docs_name_exactly_two_production_contours(self) -> None:
        for path in ("README.md", "AGENTS.md", "contracts/SEA_SPEED_DELIVERY_POLICY.md"):
            text = self.read(path)
            self.assertIn("VPS", text, path)
            self.assertIn("Ubuntu Worker/relay", text, path)
            self.assertRegex(text.lower(), r"windows worker.*retired|retired.*windows worker", path)
        self.assertIn("exactly two", self.read("README.md").lower())
        self.assertIn("exactly two", self.read("AGENTS.md").lower())

    def test_change_contract_template_has_no_windows_runtime_fields(self) -> None:
        template = self.read(".github/pull_request_template.md")
        self.assertNotIn("Windows worker update:", template)
        self.assertNotIn("Windows worker execution capability:", template)
        self.assertIn("VPS deployment:", template)
        self.assertIn("Ubuntu worker/relay update:", template)

    def test_autonomous_runtime_router_has_no_comment_authority(self) -> None:
        workflow = self.read(".github/workflows/deploy-runtime-autonomous.yml")
        self.assertNotIn("issue_comment:", workflow)
        self.assertNotIn("PRODUCTION APPROVED", workflow)
        self.assertNotIn("Execution-Intent: EXECUTE", workflow)
        self.assertIn("deploy-vps", workflow)
        self.assertIn("deploy-ubuntu-worker", workflow)
        self.assertIn("SEA_SPEED_PRODUCTION_DELEGATION_V1", workflow)
        self.assertIn("verify_source_protection.py", workflow)

    def test_public_protected_main_and_zero_touch_transport_converge_across_contracts(self) -> None:
        policy = self.read("contracts/SEA_SPEED_DELIVERY_POLICY.md")
        gate = self.read("contracts/runtime/RELEASE_READINESS_GATE.md")
        deploy = self.read("contracts/branches/deploy.md")
        architecture = self.read("docs/architecture/sea-speed-control-plane.md")
        operations = self.read("docs/operations/UBUNTU_ZERO_TOUCH_DEPLOYMENT.md")
        for source in (policy, gate, deploy, architecture, operations):
            self.assertIn("protected", source.lower())
            self.assertIn("sea-speed-deploy", source)
            self.assertIn("ProxyJump", source)
        self.assertIn("Operator actions expected: 0", policy)
        self.assertIn("verify_source_protection.py", gate)
        self.assertIn("forced command", operations)

    def test_actions_pin_risk_is_closed_but_retained(self) -> None:
        risks = json.loads(self.read("data/quality/accepted-risks-v1.json"))["risks"]
        target = next(item for item in risks if item["id"] == "RISK-ACTIONS-PIN-001")
        self.assertEqual(target["status"], "closed")
        self.assertTrue(target["resolution_evidence"])

    def test_historical_decisions_are_retained_and_dr006_exists(self) -> None:
        for number in (1, 2, 3, 4, 5, 6):
            matches = list((ROOT / "docs/decision_records").glob(f"DR-{number:03d}-*.md"))
            self.assertTrue(matches, number)

    def test_resumable_delivery_converges_across_active_entrypoints(self) -> None:
        canonical = self.read("contracts/DELIVERY_CANONICAL.md")
        self.assertIn("Resume Probe", canonical)
        self.assertIn("Delivery Checkpoint", canonical)
        self.assertIn("Next admissible action", canonical)
        self.assertIn("same exact admitted scope", canonical.lower())
        for path in (
            "AGENTS.md",
            "contracts/SEA_SPEED_GOVERNANCE.md",
            "contracts/SEA_SPEED_DELIVERY_POLICY.md",
            "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
            "contracts/runtime/RELEASE_READINESS_GATE.md",
            "contracts/branches/project-manager.md",
            "docs/agents/PM_BOOTSTRAP.md",
            "docs/architecture/sea-speed-control-plane.md",
        ):
            text = self.read(path)
            self.assertIn("DELIVERY_CANONICAL", text, path)

    def test_context_loss_does_not_reopen_source_admission(self) -> None:
        combined = "\n".join(
            self.read(path).lower()
            for path in (
                "AGENTS.md",
                "contracts/SEA_SPEED_GOVERNANCE.md",
                "contracts/SEA_SPEED_DELIVERY_POLICY.md",
                "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
                "contracts/branches/project-manager.md",
            )
        )
        for marker in ("context compaction", "session restart", "connector truncation"):
            self.assertIn(marker, combined)
        self.assertIn("discussion", combined)
        self.assertIn("outcome approved", combined)
        self.assertIn("cannot create", combined)

    def test_synchronous_wait_converges_across_active_entrypoints(self) -> None:
        canonical = self.read("contracts/DELIVERY_CANONICAL.md")
        self.assertIn("Delivery Checkpoint v2", canonical)
        self.assertIn("WAITING_EXTERNAL", canonical)
        self.assertIn("nonterminal", canonical.lower())
        self.assertIn("background", canonical.lower())
        self.assertIn("unchanged", canonical.lower())
        for path in (
            "AGENTS.md", "contracts/SEA_SPEED_GOVERNANCE.md", "contracts/SEA_SPEED_DELIVERY_POLICY.md",
            "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md", "contracts/runtime/RELEASE_READINESS_GATE.md",
            "contracts/branches/project-manager.md", "contracts/branches/task-intake.md",
            "docs/agents/PM_BOOTSTRAP.md",
            "docs/architecture/sea-speed-control-plane.md",
        ):
            text = self.read(path)
            self.assertIn("DELIVERY_CANONICAL", text, path)


if __name__ == "__main__":
    unittest.main()
