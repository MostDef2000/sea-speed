from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/release/verify_source_protection.py"
spec = importlib.util.spec_from_file_location("verify_source_protection", MODULE_PATH)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


class ProductionSourceProtectionTests(unittest.TestCase):
    def repository(self, *, public: bool = True):
        return {"private": not public, "visibility": "public" if public else "private"}

    def branch(self, *, protected: bool = True, contexts=()):
        return {
            "name": "main",
            "protected": protected,
            "protection": {"required_status_checks": {"contexts": list(contexts), "checks": []}},
        }

    def test_public_protected_main_with_required_checks_passes(self):
        MODULE.validate_source_state(
            self.repository(),
            self.branch(contexts=("PR Validation / Repository validation", "Quality integration gate / quality-integration")),
            required_contexts=("Repository validation", "quality-integration"),
        )

    def test_private_protected_repository_is_admitted(self):
        # Issue #668: the trust model admits a PRIVATE repository when main
        # is protected with the required status checks — no error is raised.
        MODULE.validate_source_state(
            self.repository(public=False),
            self.branch(contexts=("PR Validation / Repository validation", "Quality integration gate / quality-integration")),
            required_contexts=("Repository validation", "quality-integration"),
        )

    def test_private_repository_without_protection_is_denied(self):
        # Issue #668: admitting private repositories does not relax the
        # protection requirement — an unprotected main still fails closed.
        with self.assertRaisesRegex(MODULE.SourceProtectionError, "protection is not active"):
            MODULE.validate_source_state(self.repository(public=False), self.branch(protected=False))

    def test_private_repository_missing_required_check_is_denied(self):
        # Issue #668: a private repository with protection but a missing
        # required status check still fails closed.
        with self.assertRaisesRegex(MODULE.SourceProtectionError, "missing required status checks"):
            MODULE.validate_source_state(
                self.repository(public=False),
                self.branch(contexts=("Repository validation",)),
                required_contexts=("Repository validation", "quality-integration"),
            )

    def test_unprotected_main_is_denied(self):
        with self.assertRaisesRegex(MODULE.SourceProtectionError, "protection is not active"):
            MODULE.validate_source_state(self.repository(), self.branch(protected=False))

    def test_missing_required_check_is_denied(self):
        with self.assertRaisesRegex(MODULE.SourceProtectionError, "missing required status checks"):
            MODULE.validate_source_state(
                self.repository(),
                self.branch(contexts=("Repository validation",)),
                required_contexts=("Repository validation", "quality-integration"),
            )

    def test_context_normalization_accepts_full_workflow_job_name(self):
        observed = MODULE.normalized_contexts(
            self.branch(contexts=("Quality integration gate / quality-integration",))
        )
        self.assertIn("Quality integration gate / quality-integration", observed)
        self.assertIn("quality-integration", observed)


if __name__ == "__main__":
    unittest.main()
