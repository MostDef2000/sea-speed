from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/ci/validate_sdd.py"
spec = importlib.util.spec_from_file_location("validate_sdd", MODULE_PATH)
assert spec and spec.loader
sdd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdd)


class ValidateSddTests(unittest.TestCase):
    def make_repo(self, *, quality=True, risk="NOT REQUIRED") -> Path:
        temp = Path(tempfile.mkdtemp(prefix="sea-speed-sdd-test-"))
        for path in sdd.BASELINE_FILES:
            target = temp / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("baseline\n", encoding="utf-8")
        self.add_feature(temp, "001-example", 1, quality=quality, risk=risk)
        return temp

    def add_feature(self, root: Path, name: str, issue: int, *, quality=True, risk="NOT REQUIRED") -> None:
        feature = root / "specs" / name
        feature.mkdir(parents=True)
        quality_spec = "" if not quality else "\n## NFR assessment\n- NFR-001 | Area: RELIABILITY | Target: validator rejects invalid records | Validation: unit test | Evidence: tests/test_validate_sdd.py | Status: PASS\n"
        (feature / "spec.md").write_text(
            f"# Feature Specification: {name}\n\n- Issue: #{issue}\n\n## Product outcome\nOutcome\n\n## User scenarios\nScenario\n\n"
            "## Requirements\n- FR-001: Requirement\n\n## Acceptance criteria\n- AC-001: Criteria one\n- AC-002: Criteria two\n"
            f"{quality_spec}\n## Runtime feedback\nFeedback\n",
            encoding="utf-8",
        )
        risk_row = "" if risk == "NOT REQUIRED" else "- RISK-001 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: preserve hard gates | Validation: unit test | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED\n"
        quality_plan = "" if not quality else (
            f"\n## Risk profile\n- Risk profile: {risk}\n{risk_row}\n"
            "## Test design\n- TEST-001 | Covers: AC-001, AC-002 | Level: unit | Priority: P1 | Evidence: tests/test_validate_sdd.py\n\n"
            "## Correct-course check\n- Trigger: NONE\n- Issue impact: NONE\n- Specification impact: NONE\n- Plan impact: NONE\n- Tasks impact: NONE\n- Authorization impact: NONE\n- Follow-up: NONE\n"
        )
        (feature / "plan.md").write_text(
            f"# Implementation Plan\n\nSpecification: specs/{name}/spec.md\n\n## Architecture\nA\n\n## Decisions\nD\n\n"
            "## Affected contours\nNone\n\n## Validation\nV\n"
            f"{quality_plan}\n## Runtime feedback\nFeedback\n",
            encoding="utf-8",
        )
        quality_tasks = "" if not quality else (
            "\n## Requirements traceability\n"
            "- AC-001 | Task: T001 | Evidence: TEST-001 | Coverage: COVERED\n"
            "- AC-002 | Task: T001 | Evidence: TEST-001 | Coverage: COVERED\n\n"
            "## Definition of Done\n"
            "- [ ] Issue/spec/plan/tasks current\n"
            "- [ ] Exact changed-file scope verified\n"
            "- [ ] Required tests and evidence complete\n"
            "- [ ] Required CI green\n"
            "- [ ] Exact-green-head merge complete\n"
            "- [ ] Deployment state resolved\n"
            "- [ ] Runtime acceptance resolved\n"
            "- [ ] Deferred work recorded\n"
            "- [ ] Risks resolved or explicitly accepted\n"
            "- [ ] Waivers resolved or current\n"
        )
        (feature / "tasks.md").write_text(
            f"# Tasks\n\nSpecification: specs/{name}/spec.md\n\n## Delivery tasks\n- [x] T001\n{quality_tasks}\n## Completion gate\n- [x] Done\n",
            encoding="utf-8",
        )

    def test_valid_repository_and_significant_pr_link(self) -> None:
        root = self.make_repo()
        sdd.validate_repository(root)
        sdd.validate_pr_link("- Specification: `specs/001-example/spec.md`\n- Risk profile: NOT REQUIRED\n", ["frontend/sea-speed/index.html"], root)

    def test_historical_repository_does_not_require_quality_layer_until_linked(self) -> None:
        root = self.make_repo(quality=False)
        sdd.validate_repository(root)
        with self.assertRaisesRegex(sdd.SddError, "NFR assessment"):
            sdd.validate_pr_link("- Specification: `specs/001-example/spec.md`\n- Risk profile: NOT REQUIRED\n", ["api/app/main.py"], root)

    def test_significant_pr_without_spec_fails(self) -> None:
        root = self.make_repo()
        with self.assertRaises(sdd.SddError):
            sdd.validate_pr_link("", ["api/app/main.py"], root)

    def test_spec_only_change_does_not_require_pr_link(self) -> None:
        root = self.make_repo(quality=False)
        sdd.validate_pr_link("", ["specs/001-example/spec.md"], root)

    def test_required_risk_profile_needs_complete_risk_row(self) -> None:
        root = self.make_repo(risk="REQUIRED")
        sdd.validate_pr_link("- Specification: `specs/001-example/spec.md`\n- Risk profile: REQUIRED\n", ["contracts/example.md"], root)
        plan = root / "specs/001-example/plan.md"
        plan.write_text(plan.read_text().replace("- RISK-001 |", "- BROKEN-001 |"), encoding="utf-8")
        with self.assertRaisesRegex(sdd.SddError, "requires at least one complete risk row"):
            sdd.validate_pr_link("- Specification: `specs/001-example/spec.md`\n- Risk profile: REQUIRED\n", ["contracts/example.md"], root)

    def test_nfr_unknown_target_cannot_pass(self) -> None:
        root = self.make_repo()
        spec_path = root / "specs/001-example/spec.md"
        spec_path.write_text(spec_path.read_text().replace("Target: validator rejects invalid records", "Target: UNKNOWN"), encoding="utf-8")
        with self.assertRaisesRegex(sdd.SddError, "cannot be PASS"):
            sdd.validate_pr_link("- Specification: `specs/001-example/spec.md`\n- Risk profile: NOT REQUIRED\n", ["api/app/main.py"], root)

    def test_traceability_requires_every_acceptance_criterion(self) -> None:
        root = self.make_repo()
        tasks = root / "specs/001-example/tasks.md"
        tasks.write_text(tasks.read_text().replace("- AC-002 | Task: T001 | Evidence: TEST-001 | Coverage: COVERED\n", ""), encoding="utf-8")
        with self.assertRaisesRegex(sdd.SddError, "traceability mismatch"):
            sdd.validate_pr_link("- Specification: `specs/001-example/spec.md`\n- Risk profile: NOT REQUIRED\n", ["api/app/main.py"], root)

    def test_missing_tasks_fails_repository_validation(self) -> None:
        root = self.make_repo()
        (root / "specs/001-example/tasks.md").unlink()
        with self.assertRaises(sdd.SddError):
            sdd.validate_repository(root)

    def test_historical_002_collision_is_grandfathered(self) -> None:
        root = self.make_repo()
        self.add_feature(root, "002-camera-preview-gallery", 2)
        self.add_feature(root, "002-sdd-adoption", 3)
        sdd.validate_repository(root)

    def test_new_duplicate_numeric_prefix_fails(self) -> None:
        root = self.make_repo()
        self.add_feature(root, "013-first", 13)
        self.add_feature(root, "013-second", 14)
        with self.assertRaisesRegex(sdd.SddError, "duplicate SDD numeric prefix 013"):
            sdd.validate_repository(root)


if __name__ == "__main__":
    unittest.main()
