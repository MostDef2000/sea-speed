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
    def make_repo(self) -> Path:
        temp = Path(tempfile.mkdtemp(prefix="sea-speed-sdd-test-"))
        for path in sdd.BASELINE_FILES:
            target = temp / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("baseline\n", encoding="utf-8")

        feature = temp / "specs/001-example"
        feature.mkdir(parents=True)
        (feature / "spec.md").write_text(
            "# Feature Specification: Example\n\n"
            "- Issue: #1\n\n"
            "## Product outcome\nOutcome\n\n"
            "## User scenarios\nScenario\n\n"
            "## Requirements\nRequirement\n\n"
            "## Acceptance criteria\nCriteria\n\n"
            "## Runtime feedback\nPending\n",
            encoding="utf-8",
        )
        (feature / "plan.md").write_text(
            "# Implementation Plan: Example\n\n"
            "Specification: specs/001-example/spec.md\n\n"
            "## Architecture\nA\n\n## Decisions\nD\n\n## Affected contours\nNone\n\n"
            "## Validation\nV\n\n## Runtime feedback\nPending\n",
            encoding="utf-8",
        )
        (feature / "tasks.md").write_text(
            "# Tasks: Example\n\nSpecification: specs/001-example/spec.md\n\n"
            "## Delivery tasks\n- [ ] T001\n\n## Completion gate\n- [ ] Done\n",
            encoding="utf-8",
        )
        return temp

    def test_valid_repository_and_significant_pr_link(self) -> None:
        root = self.make_repo()
        sdd.validate_repository(root)
        sdd.validate_pr_link(
            "- Specification: `specs/001-example/spec.md`\n",
            ["frontend/sea-speed/index.html"],
            root,
        )

    def test_significant_pr_without_spec_fails(self) -> None:
        root = self.make_repo()
        with self.assertRaises(sdd.SddError):
            sdd.validate_pr_link("", ["api/app/main.py"], root)

    def test_spec_only_change_does_not_require_pr_link(self) -> None:
        root = self.make_repo()
        sdd.validate_pr_link("", ["specs/001-example/spec.md"], root)

    def test_missing_tasks_fails_repository_validation(self) -> None:
        root = self.make_repo()
        (root / "specs/001-example/tasks.md").unlink()
        with self.assertRaises(sdd.SddError):
            sdd.validate_repository(root)


if __name__ == "__main__":
    unittest.main()
