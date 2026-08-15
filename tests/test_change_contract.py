from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/ci/validate_change_contract.py"
POLICY_PATH = ROOT / "data/contracts/change-control-policy-v1.json"


def load_module():
    spec = importlib.util.spec_from_file_location("sea_speed_change_contract", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load change contract validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def body(
    files: list[str],
    *,
    impact: str = "CONTROL_PLANE",
    vps: str = "NOT REQUIRED",
    ubuntu: str = "NOT REQUIRED",
    worker: str = "NOT REQUIRED",
    authorization: str = "OUTCOME APPROVED",
    approval: str = "YES",
    boundary_change: str = "NO",
    production_envelope: str = "NOT REQUIRED",
) -> str:
    listed = "\n".join(f"  - `{path}`" for path in files)
    return f"""## Canonical task

- Issue: #172
- Specification: `specs/012-delivery-control-hardening/spec.md`
- Approved scope: Bounded delivery-control hardening.
- Source authorization: {authorization}
- Approval recorded after Implementation Scope Check: {approval}
- Material scope/protected-boundary change since authorization: {boundary_change}
- Acceptance criteria: Exact runtime contour and provenance gates are enforced.

## Change

- Intended behavior: Validate PR metadata against exact Git diff and runtime contours.
- Changed files:
{listed}
- Out of scope: Product runtime behavior and production deployment.

## Impact

- Production impact: {impact}
- Production-impact rationale: Exact contour classification.
- Security impact: Delivery admission only.
- API/event/state/storage schema impact: None.
- Detection/tracking/calibration/speed formula impact: None.
- Backward compatibility: Legacy persisted evidence remains readable.

## Delivery

- VPS deployment: {vps}
- Ubuntu worker/relay update: {ubuntu}
- Windows worker update: {worker}
- Production safety envelope: {production_envelope}
- Rollout order: Merge after required CI and authorization.
- Release manifest: Provenance v2 when deployable.
- Rollback target: Revert the source PR.

## Validation

- Local checks: Unit tests.
- PR checks: PR Validation and Quality integration gate.
- Runtime acceptance plan: Not applicable to this control-plane task.
- Telemetry/evidence plan: CI evidence.

## Completion

- [ ] Exact changed-file scope verified
"""


class ChangeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_module()
        cls.policy = cls.validator.load_policy(POLICY_PATH)

    def test_control_plane_contract(self) -> None:
        files = ["scripts/ci/validate_change_contract.py", ".github/workflows/pr-validation.yml"]
        self.assertEqual(self.validator.validate_contract(body(files), files, self.policy), "CONTROL_PLANE")

    def test_legacy_source_authorization_remains_readable(self) -> None:
        files = ["scripts/ci/validate_change_contract.py"]
        self.assertEqual(self.validator.validate_contract(body(files, authorization="LEGACY COMMIT APPROVED"), files, self.policy), "CONTROL_PLANE")

    def test_rejects_changed_file_mismatch(self) -> None:
        with self.assertRaisesRegex(self.validator.ContractError, "do not match"):
            self.validator.validate_contract(body(["AGENTS.md"]), ["AGENTS.md", "contracts/SEA_SPEED_GOVERNANCE.md"], self.policy)

    def test_vps_requires_vps_and_envelope(self) -> None:
        files = ["api/app/main.py"]
        self.assertEqual(
            self.validator.validate_contract(body(files, impact="VPS", vps="REQUIRED", production_envelope="REQUIRED"), files, self.policy),
            "VPS",
        )

    def test_ubuntu_deploy_is_not_control_plane(self) -> None:
        files = ["deploy/worker/ubuntu/update-exact.sh"]
        self.assertEqual(self.validator.derive_impact(files, self.policy), "UBUNTU_WORKER")
        with self.assertRaisesRegex(self.validator.ContractError, "Production safety envelope"):
            self.validator.validate_contract(body(files, impact="UBUNTU_WORKER", ubuntu="REQUIRED"), files, self.policy)
        self.assertEqual(
            self.validator.validate_contract(body(files, impact="UBUNTU_WORKER", ubuntu="REQUIRED", production_envelope="REQUIRED"), files, self.policy),
            "UBUNTU_WORKER",
        )

    def test_windows_specific_script_is_windows_only(self) -> None:
        files = ["worker/update_worker.ps1"]
        self.assertEqual(
            self.validator.validate_contract(body(files, impact="WINDOWS_WORKER", worker="REQUIRED", production_envelope="REQUIRED"), files, self.policy),
            "WINDOWS_WORKER",
        )

    def test_shared_worker_python_is_mixed_ubuntu_and_windows(self) -> None:
        files = ["worker/camera_worker.py"]
        self.assertEqual(self.validator.derive_impact(files, self.policy), "MIXED")
        self.assertEqual(
            self.validator.validate_contract(
                body(files, impact="MIXED", ubuntu="REQUIRED", worker="REQUIRED", production_envelope="REQUIRED"), files, self.policy
            ),
            "MIXED",
        )

    def test_vps_plus_ubuntu_is_mixed_with_exact_flags(self) -> None:
        files = ["api/app/main.py", "deploy/worker/ubuntu/update-exact.sh"]
        self.assertEqual(self.validator.derive_impact(files, self.policy), "MIXED")
        self.assertEqual(
            self.validator.validate_contract(
                body(files, impact="MIXED", vps="REQUIRED", ubuntu="REQUIRED", production_envelope="REQUIRED"), files, self.policy
            ),
            "MIXED",
        )
        with self.assertRaisesRegex(self.validator.ContractError, "exact derived contours"):
            self.validator.validate_contract(
                body(files, impact="MIXED", ubuntu="REQUIRED", worker="REQUIRED", production_envelope="REQUIRED"), files, self.policy
            )

    def test_all_three_runtime_contours_require_all_three_flags(self) -> None:
        files = ["api/app/main.py", "worker/camera_worker.py"]
        self.assertEqual(self.validator.derive_runtime_contours(files, self.policy), {"VPS", "UBUNTU_WORKER", "WINDOWS_WORKER"})
        self.assertEqual(
            self.validator.validate_contract(
                body(files, impact="MIXED", vps="REQUIRED", ubuntu="REQUIRED", worker="REQUIRED", production_envelope="REQUIRED"), files, self.policy
            ),
            "MIXED",
        )
        with self.assertRaisesRegex(self.validator.ContractError, "exact derived contours"):
            self.validator.validate_contract(
                body(files, impact="MIXED", vps="REQUIRED", worker="REQUIRED", production_envelope="REQUIRED"), files, self.policy
            )

    def test_control_plane_requires_no_production_envelope(self) -> None:
        files = ["contracts/SEA_SPEED_GOVERNANCE.md"]
        with self.assertRaisesRegex(self.validator.ContractError, "non-runtime impact"):
            self.validator.validate_contract(body(files, production_envelope="REQUIRED"), files, self.policy)

    def test_rejects_boundary_change_without_fresh_authorization(self) -> None:
        files = ["scripts/ci/validate_change_contract.py"]
        with self.assertRaisesRegex(self.validator.ContractError, "fresh authorization"):
            self.validator.validate_contract(body(files, boundary_change="YES"), files, self.policy)


if __name__ == "__main__":
    unittest.main()
