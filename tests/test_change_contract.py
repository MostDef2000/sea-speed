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
    worker: str = "NOT REQUIRED",
    approval: str = "YES",
) -> str:
    listed = "\n".join(f"  - `{path}`" for path in files)
    return f"""## Canonical task

- Issue: #76
- Approved scope: Enforce the executable Change Contract.
- Approval recorded after Implementation Scope Check: {approval}
- Acceptance criteria: CI rejects incorrect scope and production impact.

## Change

- Intended behavior: Validate PR metadata against the exact Git diff.
- Changed files:
{listed}
- Out of scope: Product runtime behavior and production deployment.

## Impact

- Production impact: {impact}
- Production-impact rationale: Repository control-plane validation only.
- Security impact: Reduces unauthorized scope and deployment ambiguity.
- API/event/state/storage schema impact: None.
- Detection/tracking/calibration/speed formula impact: None.
- Backward compatibility: Preserved.

## Delivery

- VPS deployment: {vps}
- Windows worker update: {worker}
- Rollout order: Merge after CI and separate approval.
- Release manifest: Not applicable.
- Rollback target: Revert the PR.

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
    def setUpClass(cls) -> None:
        cls.validator = load_module()
        cls.policy = cls.validator.load_policy(POLICY_PATH)

    def test_valid_control_plane_contract(self) -> None:
        files = ["scripts/ci/validate_change_contract.py", ".github/workflows/pr-validation.yml"]
        self.assertEqual(self.validator.validate_contract(body(files), files, self.policy), "CONTROL_PLANE")

    def test_rejects_missing_approval(self) -> None:
        files = ["scripts/ci/validate_change_contract.py"]
        with self.assertRaisesRegex(self.validator.ContractError, "approval"):
            self.validator.validate_contract(body(files, approval="NO"), files, self.policy)

    def test_rejects_changed_file_mismatch(self) -> None:
        with self.assertRaisesRegex(self.validator.ContractError, "do not match"):
            self.validator.validate_contract(
                body(["AGENTS.md"]),
                ["AGENTS.md", "contracts/SEA_SPEED_GOVERNANCE.md"],
                self.policy,
            )

    def test_rejects_runtime_impact_mismatch(self) -> None:
        files = ["api/app/main.py"]
        with self.assertRaisesRegex(self.validator.ContractError, "derived VPS"):
            self.validator.validate_contract(body(files, impact="NONE"), files, self.policy)

    def test_requires_runtime_deployment_for_vps_change(self) -> None:
        files = ["api/app/main.py"]
        with self.assertRaisesRegex(self.validator.ContractError, "deployment declaration"):
            self.validator.validate_contract(body(files, impact="VPS"), files, self.policy)
        self.assertEqual(
            self.validator.validate_contract(body(files, impact="VPS", vps="REQUIRED"), files, self.policy),
            "VPS",
        )


if __name__ == "__main__":
    unittest.main()
