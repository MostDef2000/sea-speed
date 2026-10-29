from __future__ import annotations

import ast
import importlib.util
import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class DeliveryContractConvergenceTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8-sig")

    def _constant_string_set(self, path: str, name: str) -> set[str]:
        """Parse a module-level `NAME = {...}` literal into a set of strings."""
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                continue
            elements = node.value.elts if isinstance(node.value, (ast.Set, ast.List, ast.Tuple)) else []
            values = {
                element.value
                for element in elements
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            }
            self.assertEqual(len(values), len(elements), f"{name} must be a flat string literal set")
            return values
        self.fail(f"{path} does not define module constant {name}")

    def _load_validator(self):
        """Import the real validate_change_contract module (import-safe)."""
        path = ROOT / "scripts/ci/validate_change_contract.py"
        spec = importlib.util.spec_from_file_location("validate_change_contract", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

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

    def test_source_authorization_uses_unified_phrase_exclusively(self) -> None:
        template = self.read(".github/pull_request_template.md")
        # Template presentation keeps (markdown prose, no AST): the unified
        # phrase is the only one presented and no legacy phrase appears.
        self.assertIn("Source authorization: commit approved", template)
        self.assertNotIn("Source authorization: OUTCOME APPROVED", template)
        self.assertNotIn("LEGACY COMMIT APPROVED", template)
        # AST twin (issue #398 wave 5): the admission set is read from the
        # validator's PARSED module constant instead of a byte-exact source
        # line, so refactors of the literal cannot silently widen the set.
        self.assertEqual(
            self._constant_string_set("scripts/ci/validate_change_contract.py", "SOURCE_AUTHORIZATIONS"),
            {"commit approved"},
        )
        # Parsed schema twin (issue #398 wave 5): the receipt enum is read via
        # json.loads instead of a byte-exact JSON fragment.
        schema = json.loads(self.read("schemas/delivery-checkpoint-v2.schema.json"))
        self.assertEqual(schema["properties"]["authorization_receipt"]["enum"], ["commit approved"])
        # The retired raw validator pins — the byte-exact constant line and
        # the absence ban on the quoted legacy literal — are superseded by the
        # EXECUTED twin in
        # test_validate_authorization_rejects_retired_phrase_and_accepts_unified.

    def test_validate_authorization_rejects_retired_phrase_and_accepts_unified(self) -> None:
        # EXECUTED twin (issue #398 wave 5): the real validate_authorization
        # runs against both phrases — the unified phrase is accepted and
        # returned as the receipt; the retired legacy phrase fails closed for
        # new admissions, with the unified phrase named in the error.
        validator = self._load_validator()
        fields = {
            "Approval recorded after Implementation Scope Check": "YES",
            "Material scope/protected-boundary change since authorization": "NO",
        }
        self.assertEqual(
            validator.validate_authorization({**fields, "Source authorization": "commit approved"}),
            "commit approved",
        )
        with self.assertRaises(validator.ContractError) as rejected:
            validator.validate_authorization({**fields, "Source authorization": "OUTCOME APPROVED"})
        message = str(rejected.exception)
        self.assertIn("commit approved", message)
        self.assertIn("OUTCOME APPROVED", message)

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

    def test_autonomous_runtime_router_routes_only_allowed_contours(self) -> None:
        # Parsed-structure twin (issue #398 wave 5): the router's downstream
        # routing table is asserted on the parsed jobs — each contour job
        # needs the policy evaluation, is gated on the allowed decision AND
        # its own contour requirement, and delegates to the local reusable
        # deploy workflow with inherited secrets.
        # The retired raw text pins of the former
        # test_autonomous_runtime_router_has_no_comment_authority (trigger
        # ban, comment-authority bans, delegation env, source-protection
        # step) are superseded by the strictly stronger parsed twins in
        # test_autonomous_execution_policy.py
        # ::test_autonomous_router_uses_current_tip_quality_trusted_environment_and_source_protection.
        workflow = yaml.safe_load(self.read(".github/workflows/deploy-runtime-autonomous.yml"))
        jobs = workflow["jobs"]
        self.assertEqual(sorted(jobs), ["deploy-ubuntu-worker", "deploy-vps", "evaluate"])
        for job_name, contour_output, workflow_file in (
            ("deploy-vps", "vps_required", "deploy-vps.yml"),
            ("deploy-ubuntu-worker", "ubuntu_worker_required", "deploy-ubuntu-worker.yml"),
        ):
            job = jobs[job_name]
            needs = job["needs"]
            self.assertEqual(needs if isinstance(needs, list) else [needs], ["evaluate"], job_name)
            self.assertEqual(job["uses"], f"./.github/workflows/{workflow_file}", job_name)
            self.assertEqual(job["secrets"], "inherit", job_name)
            for condition in (
                "needs.evaluate.outputs.allowed == 'true'",
                f"needs.evaluate.outputs.{contour_output} == 'true'",
            ):
                self.assertIn(condition, job["if"], job_name)

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
        paths = (
            "AGENTS.md",
            "contracts/SEA_SPEED_GOVERNANCE.md",
            "contracts/SEA_SPEED_DELIVERY_POLICY.md",
            "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
            "contracts/runtime/RELEASE_READINESS_GATE.md",
            "contracts/branches/project-manager.md",
            "docs/agents/PM_BOOTSTRAP.md",
            "docs/architecture/sea-speed-control-plane.md",
        )
        for path in paths:
            text = self.read(path)
            self.assertIn("Resume Probe", text, path)
            self.assertIn("Delivery Checkpoint", text, path)
            self.assertIn("Next admissible action", text, path)
            self.assertIn("same exact admitted scope", text.lower(), path)

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
        self.assertIn("commit approved", combined)
        self.assertIn("outcome approved", combined)
        self.assertIn("cannot create", combined)

    def test_synchronous_wait_converges_across_active_entrypoints(self) -> None:
        paths = (
            "AGENTS.md", "contracts/SEA_SPEED_GOVERNANCE.md", "contracts/SEA_SPEED_DELIVERY_POLICY.md",
            "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md", "contracts/runtime/RELEASE_READINESS_GATE.md",
            "contracts/branches/project-manager.md", "contracts/branches/task-intake.md",
            "docs/agents/PM_BOOTSTRAP.md",
            "docs/architecture/sea-speed-control-plane.md",
        )
        for path in paths:
            text = self.read(path)
            lowered = text.lower()
            self.assertIn("Delivery Checkpoint v2", text, path)
            self.assertIn("WAITING_EXTERNAL", text, path)
            self.assertIn("nonterminal", lowered, path)
            self.assertIn("background", lowered, path)
            self.assertIn("unchanged", lowered, path)

    def test_pending_ci_foreground_observation_converges_across_canonical_contracts(self) -> None:
        paths = (
            "AGENTS.md",
            "contracts/SEA_SPEED_GOVERNANCE.md",
            "contracts/SEA_SPEED_DELIVERY_POLICY.md",
            "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
            "contracts/runtime/RELEASE_READINESS_GATE.md",
            "contracts/branches/project-manager.md",
        )
        combined = "\n".join(self.read(path) for path in paths)
        lowered = combined.lower()
        for path in paths:
            text = self.read(path)
            self.assertIn("queued", text, path)
            self.assertIn("in_progress", text, path)
            self.assertIn("ACTIVE", text, path)
            self.assertIn("WAITING_EXTERNAL", text, path)
            self.assertIn("foreground", text.lower(), path)
            self.assertIn("Connector/provider capability outage", text, path)
        for marker in (
            "at least 30 seconds",
            "no observation count or deadline",
            "no checkpoint-generation churn",
            "failure immediately narrows to failed job/log remediation",
        ):
            self.assertIn(marker, lowered)


if __name__ == "__main__":
    unittest.main()
