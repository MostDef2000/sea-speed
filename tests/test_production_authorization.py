from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/release/verify_production_authorization.py"
spec = importlib.util.spec_from_file_location("verify_production_authorization", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

ISSUE_BODY = """# Task\n\n## Outcome Contract\n- Product outcome: harden delivery\n- Protected: runtime behavior\n\n## Scope\nBounded.\n"""


def pr_body(*, rollback: str = "previous exact main release", legacy_windows: bool = False) -> str:
    windows = "- Windows worker update: NOT REQUIRED\n" if legacy_windows else ""
    return f"""## Canonical task\n\n- Issue: #172\n\n## Change\n\n- Changed files:\n  - `deploy/vps/deploy.sh`\n  - `scripts/release/build_release_manifest.py`\n- Out of scope: runtime behavior\n\n## Impact\n\n- Production impact: VPS\n- Production-impact rationale: VPS exact deployment target\n- Security impact: deployment admission only\n\n## Delivery\n\n- VPS deployment: REQUIRED\n- Ubuntu worker/relay update: NOT REQUIRED\n{windows}- Rollback target: {rollback}\n"""


class ProductionAuthorizationTests(unittest.TestCase):
    def test_fingerprint_changes_when_rollback_boundary_changes(self) -> None:
        first = module.canonical_json_sha256(module.authorization_payload(172, 173, "a" * 40, ISSUE_BODY, pr_body()))
        second = module.canonical_json_sha256(module.authorization_payload(172, 173, "a" * 40, ISSUE_BODY, pr_body(rollback="different exact release")))
        self.assertNotEqual(first, second)

    def test_new_authorization_payload_has_only_active_runtime_contours(self) -> None:
        payload = module.authorization_payload(172, 173, "a" * 40, ISSUE_BODY, pr_body())
        self.assertEqual(
            payload["runtimeContours"],
            {"productionImpact": "VPS", "vps": "REQUIRED", "ubuntuWorkerRelay": "NOT REQUIRED"},
        )

    def test_historical_windows_payload_shape_remains_reproducible(self) -> None:
        payload = module.authorization_payload(172, 173, "a" * 40, ISSUE_BODY, pr_body(legacy_windows=True))
        self.assertEqual(
            payload["runtimeContours"],
            {
                "productionImpact": "VPS",
                "vps": "REQUIRED",
                "ubuntuWorkerRelay": "NOT REQUIRED",
                "windowsWorker": "NOT REQUIRED",
            },
        )
        historical = module.canonical_json_sha256(payload)
        modern = module.canonical_json_sha256(module.authorization_payload(172, 173, "a" * 40, ISSUE_BODY, pr_body()))
        self.assertNotEqual(historical, modern)
        self.assertEqual(
            historical,
            module.canonical_json_sha256(module.authorization_payload(172, 173, "a" * 40, ISSUE_BODY, pr_body(legacy_windows=True))),
        )

    def test_approved_files_are_from_change_contract_not_merge_message(self) -> None:
        self.assertEqual(
            module.declared_changed_files(pr_body()),
            ["deploy/vps/deploy.sh", "scripts/release/build_release_manifest.py"],
        )

    def test_missing_outcome_contract_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Outcome Contract"):
            module.outcome_contract("# no contract\n")


if __name__ == "__main__":
    unittest.main()
