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

    def test_new_authorization_model_excludes_legacy(self) -> None:
        template = self.read(".github/pull_request_template.md")
        validator = self.read("scripts/ci/validate_change_contract.py")
        self.assertIn("Source authorization: OUTCOME APPROVED", template)
        self.assertNotIn("LEGACY COMMIT APPROVED", template)
        self.assertIn('SOURCE_AUTHORIZATIONS = {"OUTCOME APPROVED"}', validator)

    def test_active_docs_name_three_runtime_contours(self) -> None:
        for path in ("README.md", "AGENTS.md", "contracts/SEA_SPEED_DELIVERY_POLICY.md"):
            text = self.read(path)
            for marker in ("VPS", "Ubuntu Worker/relay", "Windows AI Worker"):
                self.assertIn(marker, text, path)

    def test_actions_pin_risk_is_closed_but_retained(self) -> None:
        risks = json.loads(self.read("data/quality/accepted-risks-v1.json"))["risks"]
        target = next(item for item in risks if item["id"] == "RISK-ACTIONS-PIN-001")
        self.assertEqual(target["status"], "closed")
        self.assertTrue(target["resolution_evidence"])

    def test_historical_decisions_are_retained_and_dr004_exists(self) -> None:
        for number in (1, 2, 3, 4):
            matches = list((ROOT / "docs/decision_records").glob(f"DR-{number:03d}-*.md"))
            self.assertTrue(matches, number)


if __name__ == "__main__":
    unittest.main()
