from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DeliveryQualityLayerTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8-sig")

    def _parsed_strings(self, path: str) -> tuple[dict[str, tuple[str, ...]], set[str]]:
        """Parse a module: named string-collection constants + every string literal.

        The constants map holds every module-level ``NAME = {...}/[...]/(...)``
        assignment whose elements are plain string literals; the literal set
        holds every string constant anywhere in the AST (comments never parse,
        so literal membership is comment-blind).
        """
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        constants: dict[str, tuple[str, ...]] = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, (ast.Set, ast.List, ast.Tuple)):
                continue
            values = tuple(
                element.value
                for element in node.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            )
            if values:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = values
        literals = {
            node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        return constants, literals

    def _local_string_tuple(self, path: str, name: str) -> tuple[str, ...]:
        """Parse a (function-local) `name = (...)` flat string tuple."""
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, (ast.Set, ast.List, ast.Tuple)):
                continue
            if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                continue
            values = tuple(
                element.value
                for element in node.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            )
            self.assertEqual(len(values), len(node.value.elts), f"{name} must be a flat string tuple")
            return values
        self.fail(f"{path} does not define string tuple {name}")

    def _template_field_values(self, template: str, field: str) -> set[str]:
        """The value alternatives a `- Field: a / b` template line presents."""
        for line in template.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"- {field}:"):
                return {part.strip() for part in stripped.split(":", 1)[1].split("/")}
        self.fail(f"template field line missing: {field}")

    def test_templates_keep_quality_artifacts_in_existing_sdd(self) -> None:
        spec = self.read(".specify/templates/overrides/spec-template.md")
        plan = self.read(".specify/templates/overrides/plan-template.md")
        tasks = self.read(".specify/templates/overrides/tasks-template.md")
        # Convergence twin (issue #398 wave 5): the quality sections the
        # templates keep are read from the validator's PARSED marker constants
        # (QUALITY_SPEC_MARKERS / QUALITY_PLAN_MARKERS / QUALITY_TASK_MARKERS),
        # replacing the retired raw marker pins — a validator-enforced
        # artifact missing from a template now fails even if this pin list
        # was never updated.
        sdd_constants, _ = self._parsed_strings("scripts/ci/validate_sdd.py")
        for marker in sdd_constants["QUALITY_SPEC_MARKERS"]:
            self.assertIn(marker, spec)
        for marker in sdd_constants["QUALITY_PLAN_MARKERS"]:
            self.assertIn(marker, plan)
        for marker in sdd_constants["QUALITY_TASK_MARKERS"]:
            self.assertIn(marker, tasks)
        self.assertNotIn("Separate merge approval", tasks)  # SP keep: retired concept ban

    def test_pr_contract_has_risk_derivation_and_quality_waiver_fields(self) -> None:
        template = self.read(".github/pull_request_template.md")
        # Convergence twin (issue #398 wave 5): the value alternatives the
        # template presents for the risk-profile and quality-verdict fields
        # must equal the validator's PARSED allowed sets (RISK_PROFILE_VALUES,
        # QUALITY_VERDICTS), replacing the retired raw line pins — template
        # presentation and validator enforcement cannot drift apart. The
        # waiver fields are checked against the validator's PARSED waiver
        # field tuple (all five, not just the three the raw pin listed).
        change_constants, change_literals = self._parsed_strings("scripts/ci/validate_change_contract.py")
        self.assertEqual(
            self._template_field_values(template, "Risk profile"),
            set(change_constants["RISK_PROFILE_VALUES"]),
        )
        self.assertEqual(
            self._template_field_values(template, "Quality verdict"),
            set(change_constants["QUALITY_VERDICTS"]),
        )
        for field in self._local_string_tuple("scripts/ci/validate_change_contract.py", "waiver_fields"):
            self.assertIn(f"- {field}:", template)
        for field in ("Destructive/data migration impact", "Other high-risk trigger"):
            self.assertEqual(self._template_field_values(template, field), {"YES", "NO"})
            self.assertIn(field, change_literals)  # the validator enforces the field

    def test_hard_gates_are_not_waivable(self) -> None:
        governance = self.read("contracts/SEA_SPEED_GOVERNANCE.md")
        policy = self.read("contracts/SEA_SPEED_DELIVERY_POLICY.md")
        readiness = self.read("contracts/runtime/RELEASE_READINESS_GATE.md")
        for text in (governance, policy, readiness):
            self.assertIn("waiver", text.lower())
            self.assertIn("hard gate", text.lower())
        self.assertIn("commit approved", governance)
        self.assertIn("OUTCOME APPROVED", governance)
        self.assertIn("PRODUCTION APPROVED", governance)

    def test_active_delivery_role_and_three_contours_remain(self) -> None:
        contract = self.read("contracts/branches/project-manager.md")
        policy = self.read("contracts/SEA_SPEED_DELIVERY_POLICY.md")
        self.assertIn("Role: Sea Speed Delivery Orchestrator", contract)
        for marker in ("VPS", "Ubuntu Worker/relay", "Windows AI Worker"):
            self.assertIn(marker, policy)

    def test_quality_validator_vocabulary_is_canonical(self) -> None:
        # AST twins (issue #398 wave 5): the canonical vocabulary is read from
        # the validators' PARSED module constants — each retired vocabulary
        # item must be a member of the set the validator enforces, not merely
        # a substring of the file (comments no longer count). The two Change
        # Contract field names must appear among the validator's parsed string
        # literals (executable positions: require_value calls and field lists).
        sdd_constants, _ = self._parsed_strings("scripts/ci/validate_sdd.py")
        change_constants, change_literals = self._parsed_strings("scripts/ci/validate_change_contract.py")
        for category in ("TECH", "SEC", "PERF", "DATA", "BUS", "OPS"):
            self.assertIn(category, sdd_constants["RISK_CATEGORIES"])
        self.assertIn("runtime-manual", sdd_constants["TEST_LEVELS"])
        for priority in ("P0", "P3"):
            self.assertIn(priority, sdd_constants["TEST_PRIORITIES"])
        for verdict in ("PASS", "CONCERNS", "FAIL", "WAIVED"):
            self.assertIn(verdict, change_constants["QUALITY_VERDICTS"])
        for field in ("Other high-risk trigger", "Destructive/data migration impact"):
            self.assertIn(field, change_literals)

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
