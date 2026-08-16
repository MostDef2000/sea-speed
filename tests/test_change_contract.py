from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/ci/validate_change_contract.py"
POLICY_PATH = ROOT / "data/contracts/change-control-policy-v1.json"


def load_module():
    spec = importlib.util.spec_from_file_location("sea_speed_change_contract", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def body(
    files: list[str], *, impact="CONTROL_PLANE", vps="NOT REQUIRED", ubuntu="NOT REQUIRED",
    worker="NOT REQUIRED", authorization="OUTCOME APPROVED", approval="YES", boundary_change="NO",
    production_envelope="NOT REQUIRED", security="NONE", schema="NONE", destructive="NO",
    other_high_risk="NO", risk_profile=None, quality_verdict="PASS", quality_finding="NONE",
    waiver_reason="NOT REQUIRED", waiver_approved_by="NOT REQUIRED", waiver_date="NOT REQUIRED",
    waiver_controls="NOT REQUIRED", waiver_followup="NOT REQUIRED", vps_cap=None, ubuntu_cap=None,
    windows_cap=None, operator_actions=None,
) -> str:
    listed = "\n".join(f"  - `{path}`" for path in files)
    if risk_profile is None:
        risk_profile = "REQUIRED" if impact == "MIXED" or security != "NONE" or schema != "NONE" or destructive == "YES" or other_high_risk == "YES" else "NOT REQUIRED"
    if vps_cap is None:
        vps_cap = "CONNECTOR" if vps == "REQUIRED" else "NOT APPLICABLE"
    if ubuntu_cap is None:
        ubuntu_cap = "ONE_COMMAND_FALLBACK" if ubuntu == "REQUIRED" else "NOT APPLICABLE"
    if windows_cap is None:
        windows_cap = "ONE_COMMAND_FALLBACK" if worker == "REQUIRED" else "NOT APPLICABLE"
    if operator_actions is None:
        operator_actions = sum(cap == "ONE_COMMAND_FALLBACK" for cap in (vps_cap, ubuntu_cap, windows_cap))
    return f"""## Canonical task

- Issue: #176
- Specification: `specs/014-bmad-derived-quality-layer/spec.md`
- Approved scope: Bounded delivery quality layer.
- Source authorization: {authorization}
- Approval recorded after Implementation Scope Check: {approval}
- Material scope/protected-boundary change since authorization: {boundary_change}
- Acceptance criteria: Exact quality and delivery gates.
- Risk profile: {risk_profile}
- Quality verdict: {quality_verdict}
- Quality finding: {quality_finding}
- Waiver reason: {waiver_reason}
- Waiver approved by: {waiver_approved_by}
- Waiver review/expiry date: {waiver_date}
- Waiver compensating controls: {waiver_controls}
- Waiver follow-up/remediation target: {waiver_followup}

## Change

- Intended behavior: Validate exact diff and delivery quality layer.
- Changed files:
{listed}
- Out of scope: Production mutation.

## Impact

- Production impact: {impact}
- Production-impact rationale: Exact contour classification.
- Security impact: {security}
- API/event/state/storage schema impact: {schema}
- Detection/tracking/calibration/speed formula impact: NONE
- Destructive/data migration impact: {destructive}
- Other high-risk trigger: {other_high_risk}
- Backward compatibility: Historical evidence remains readable.

## Delivery

- VPS deployment: {vps}
- Ubuntu worker/relay update: {ubuntu}
- Windows worker update: {worker}
- Production safety envelope: {production_envelope}
- VPS execution capability: {vps_cap}
- Ubuntu worker execution capability: {ubuntu_cap}
- Windows worker execution capability: {windows_cap}
- Operator actions expected: {operator_actions}
- Rollout order: Merge after required CI.
- Release manifest: Not required for control-plane work.
- Rollback target: Revert source PR.

## Validation

- Local checks: Unit tests.
- PR checks: PR Validation and Quality integration gate.
- Runtime acceptance plan: Not applicable.
- Telemetry/evidence plan: CI evidence.

## Completion

- [ ] Exact changed-file scope verified
"""


class ChangeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_module()
        cls.policy = cls.validator.load_policy(POLICY_PATH)

    def test_control_plane_contract(self):
        files = ["scripts/ci/validate_change_contract.py"]
        self.assertEqual(self.validator.validate_contract(body(files), files, self.policy), "CONTROL_PLANE")

    def test_legacy_source_authorization_is_rejected_for_new_pr(self):
        files = ["scripts/ci/validate_change_contract.py"]
        with self.assertRaisesRegex(self.validator.ContractError, "OUTCOME APPROVED"):
            self.validator.validate_contract(body(files, authorization="LEGACY COMMIT APPROVED"), files, self.policy)

    def test_rejects_changed_file_mismatch(self):
        with self.assertRaisesRegex(self.validator.ContractError, "do not match"):
            self.validator.validate_contract(body(["AGENTS.md"]), ["AGENTS.md", "contracts/SEA_SPEED_GOVERNANCE.md"], self.policy)

    def test_vps_requires_vps_envelope_and_connector_capability(self):
        files = ["api/app/main.py"]
        self.assertEqual(
            self.validator.validate_contract(body(files, impact="VPS", vps="REQUIRED", production_envelope="REQUIRED"), files, self.policy),
            "VPS",
        )

    def test_ubuntu_deploy_is_not_control_plane_and_declares_one_command_fallback(self):
        files = ["deploy/worker/ubuntu/update-exact.sh"]
        self.assertEqual(self.validator.derive_impact(files, self.policy), "UBUNTU_WORKER")
        self.assertEqual(
            self.validator.validate_contract(body(files, impact="UBUNTU_WORKER", ubuntu="REQUIRED", production_envelope="REQUIRED"), files, self.policy),
            "UBUNTU_WORKER",
        )

    def test_required_contour_cannot_have_missing_execution_capability(self):
        files = ["deploy/worker/ubuntu/update-exact.sh"]
        with self.assertRaisesRegex(self.validator.ContractError, "cannot declare execution capability MISSING"):
            self.validator.validate_contract(
                body(files, impact="UBUNTU_WORKER", ubuntu="REQUIRED", production_envelope="REQUIRED", ubuntu_cap="MISSING", operator_actions=0),
                files,
                self.policy,
            )

    def test_operator_action_budget_matches_fallback_contours(self):
        files = ["deploy/worker/ubuntu/update-exact.sh"]
        with self.assertRaisesRegex(self.validator.ContractError, "Operator actions expected"):
            self.validator.validate_contract(
                body(files, impact="UBUNTU_WORKER", ubuntu="REQUIRED", production_envelope="REQUIRED", operator_actions=0),
                files,
                self.policy,
            )

    def test_non_applicable_contour_must_be_not_applicable(self):
        files = ["api/app/main.py"]
        with self.assertRaisesRegex(self.validator.ContractError, "non-applicable runtime contour"):
            self.validator.validate_contract(
                body(files, impact="VPS", vps="REQUIRED", production_envelope="REQUIRED", ubuntu_cap="CONNECTOR", operator_actions=0),
                files,
                self.policy,
            )

    def test_windows_specific_script_is_windows_only(self):
        files = ["worker/update_worker.ps1"]
        self.assertEqual(
            self.validator.validate_contract(body(files, impact="WINDOWS_WORKER", worker="REQUIRED", production_envelope="REQUIRED"), files, self.policy),
            "WINDOWS_WORKER",
        )

    def test_shared_worker_python_is_mixed_and_requires_risk_profile(self):
        files = ["worker/camera_worker.py"]
        self.assertEqual(
            self.validator.validate_contract(body(files, impact="MIXED", ubuntu="REQUIRED", worker="REQUIRED", production_envelope="REQUIRED"), files, self.policy),
            "MIXED",
        )
        with self.assertRaisesRegex(self.validator.ContractError, "Risk profile must be REQUIRED"):
            self.validator.validate_contract(body(files, impact="MIXED", ubuntu="REQUIRED", worker="REQUIRED", production_envelope="REQUIRED", risk_profile="NOT REQUIRED"), files, self.policy)

    def test_security_schema_destructive_and_other_triggers_require_risk(self):
        files = ["scripts/ci/validate_change_contract.py"]
        for kwargs in ({"security":"authentication boundary"}, {"schema":"event schema v2"}, {"destructive":"YES"}, {"other_high_risk":"YES"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(self.validator.ContractError, "Risk profile must be REQUIRED"):
                    self.validator.validate_contract(body(files, risk_profile="NOT REQUIRED", **kwargs), files, self.policy)

    def test_quality_fail_blocks(self):
        files = ["scripts/ci/validate_change_contract.py"]
        with self.assertRaisesRegex(self.validator.ContractError, "FAIL blocks"):
            self.validator.validate_contract(body(files, quality_verdict="FAIL", quality_finding="NFR target missed"), files, self.policy)

    def test_waiver_requires_complete_record(self):
        files = ["scripts/ci/validate_change_contract.py"]
        with self.assertRaisesRegex(self.validator.ContractError, "requires Waiver reason"):
            self.validator.validate_contract(body(files, quality_verdict="WAIVED", quality_finding="Known temporary concern"), files, self.policy)
        accepted = body(files, quality_verdict="WAIVED", quality_finding="Known temporary concern", waiver_reason="Bounded temporary exception", waiver_approved_by="project owner", waiver_date="2026-10-01", waiver_controls="aggregate CI and runtime gate", waiver_followup="Issue #999")
        self.assertEqual(self.validator.validate_contract(accepted, files, self.policy), "CONTROL_PLANE")

    def test_rejects_boundary_change(self):
        files = ["scripts/ci/validate_change_contract.py"]
        with self.assertRaisesRegex(self.validator.ContractError, "fresh authorization"):
            self.validator.validate_contract(body(files, boundary_change="YES"), files, self.policy)


if __name__ == "__main__":
    unittest.main()
