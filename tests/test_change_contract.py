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


def body(files: list[str], *, impact="CONTROL_PLANE", vps="NOT REQUIRED", ubuntu="NOT REQUIRED", worker="NOT REQUIRED", authorization="OUTCOME APPROVED", approval="YES", boundary_change="NO", production_envelope="NOT REQUIRED") -> str:
    listed = "\n".join(f"  - `{path}`" for path in files)
    return f"""## Canonical task

- Issue: #174
- Specification: `specs/013-delivery-orchestrator-convergence/spec.md`
- Approved scope: Bounded convergence.
- Source authorization: {authorization}
- Approval recorded after Implementation Scope Check: {approval}
- Material scope/protected-boundary change since authorization: {boundary_change}
- Acceptance criteria: Exact governance and contour gates.

## Change

- Intended behavior: Validate exact diff and current authorization model.
- Changed files:
{listed}
- Out of scope: Production mutation.

## Impact

- Production impact: {impact}
- Production-impact rationale: Exact contour classification.
- Security impact: Control-plane only.
- API/event/state/storage schema impact: None.
- Detection/tracking/calibration/speed formula impact: None.
- Backward compatibility: Historical evidence remains readable.

## Delivery

- VPS deployment: {vps}
- Ubuntu worker/relay update: {ubuntu}
- Windows worker update: {worker}
- Production safety envelope: {production_envelope}
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

    def test_vps_requires_vps_and_envelope(self):
        files = ["api/app/main.py"]
        self.assertEqual(self.validator.validate_contract(body(files, impact="VPS", vps="REQUIRED", production_envelope="REQUIRED"), files, self.policy), "VPS")

    def test_ubuntu_deploy_is_not_control_plane(self):
        files = ["deploy/worker/ubuntu/update-exact.sh"]
        self.assertEqual(self.validator.derive_impact(files, self.policy), "UBUNTU_WORKER")
        self.assertEqual(self.validator.validate_contract(body(files, impact="UBUNTU_WORKER", ubuntu="REQUIRED", production_envelope="REQUIRED"), files, self.policy), "UBUNTU_WORKER")

    def test_windows_specific_script_is_windows_only(self):
        files = ["worker/update_worker.ps1"]
        self.assertEqual(self.validator.validate_contract(body(files, impact="WINDOWS_WORKER", worker="REQUIRED", production_envelope="REQUIRED"), files, self.policy), "WINDOWS_WORKER")

    def test_shared_worker_python_is_mixed(self):
        files = ["worker/camera_worker.py"]
        self.assertEqual(self.validator.validate_contract(body(files, impact="MIXED", ubuntu="REQUIRED", worker="REQUIRED", production_envelope="REQUIRED"), files, self.policy), "MIXED")

    def test_all_three_runtime_contours(self):
        files = ["api/app/main.py", "worker/camera_worker.py"]
        self.assertEqual(self.validator.derive_runtime_contours(files, self.policy), {"VPS", "UBUNTU_WORKER", "WINDOWS_WORKER"})
        self.assertEqual(self.validator.validate_contract(body(files, impact="MIXED", vps="REQUIRED", ubuntu="REQUIRED", worker="REQUIRED", production_envelope="REQUIRED"), files, self.policy), "MIXED")

    def test_rejects_boundary_change(self):
        files = ["scripts/ci/validate_change_contract.py"]
        with self.assertRaisesRegex(self.validator.ContractError, "fresh authorization"):
            self.validator.validate_contract(body(files, boundary_change="YES"), files, self.policy)


if __name__ == "__main__":
    unittest.main()
