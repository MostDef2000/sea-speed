from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DeliveryQualityLayerTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8-sig")

    def test_templates_keep_quality_artifacts_in_existing_sdd(self) -> None:
        spec = self.read(".specify/templates/overrides/spec-template.md")
        plan = self.read(".specify/templates/overrides/plan-template.md")
        tasks = self.read(".specify/templates/overrides/tasks-template.md")
        self.assertIn("## NFR assessment", spec)
        for marker in ("## Risk profile", "## Test design", "## Correct-course check"):
            self.assertIn(marker, plan)
        for marker in ("## Requirements traceability", "## Definition of Done"):
            self.assertIn(marker, tasks)
        self.assertNotIn("Separate merge approval", tasks)

    def test_pr_contract_has_risk_derivation_and_quality_waiver_fields(self) -> None:
        template = self.read(".github/pull_request_template.md")
        for marker in (
            "Risk profile: REQUIRED / NOT REQUIRED",
            "Quality verdict: PASS / CONCERNS / FAIL / WAIVED",
            "Destructive/data migration impact: YES/NO",
            "Other high-risk trigger: YES/NO",
            "Waiver review/expiry date",
            "Waiver compensating controls",
            "Waiver follow-up/remediation target",
        ):
            self.assertIn(marker, template)

    def test_hard_gates_are_not_waivable(self) -> None:
        governance = self.read("contracts/SEA_SPEED_GOVERNANCE.md")
        policy = self.read("contracts/SEA_SPEED_DELIVERY_POLICY.md")
        readiness = self.read("contracts/runtime/RELEASE_READINESS_GATE.md")
        for text in (governance, policy, readiness):
            self.assertIn("waiver", text.lower())
            self.assertIn("hard gate", text.lower())
        self.assertIn("OUTCOME APPROVED", governance)
        self.assertIn("PRODUCTION APPROVED", governance)

    def test_active_delivery_role_and_three_contours_remain(self) -> None:
        contract = self.read("contracts/branches/project-manager.md")
        policy = self.read("contracts/SEA_SPEED_DELIVERY_POLICY.md")
        self.assertIn("Role: Sea Speed Delivery Orchestrator", contract)
        for marker in ("VPS", "Ubuntu Worker/relay", "Windows AI Worker"):
            self.assertIn(marker, policy)

    def test_quality_validator_vocabulary_is_canonical(self) -> None:
        sdd = self.read("scripts/ci/validate_sdd.py")
        change = self.read("scripts/ci/validate_change_contract.py")
        for marker in ("TECH", "SEC", "PERF", "DATA", "BUS", "OPS", "runtime-manual", "P0", "P3"):
            self.assertIn(marker, sdd)
        for marker in ("PASS", "CONCERNS", "FAIL", "WAIVED", "Other high-risk trigger", "Destructive/data migration impact"):
            self.assertIn(marker, change)

    def test_stage_c_sdd_is_quality_enabled(self) -> None:
        spec = self.read("specs/014-bmad-derived-quality-layer/spec.md")
        plan = self.read("specs/014-bmad-derived-quality-layer/plan.md")
        tasks = self.read("specs/014-bmad-derived-quality-layer/tasks.md")
        self.assertIn("- Issue: #176", spec)
        self.assertIn("## NFR assessment", spec)
        self.assertIn("- Risk profile: NOT REQUIRED", plan)
        self.assertIn("## Test design", plan)
        self.assertIn("## Correct-course check", plan)
        self.assertIn("## Requirements traceability", tasks)
        self.assertIn("## Definition of Done", tasks)


if __name__ == "__main__":
    unittest.main()
