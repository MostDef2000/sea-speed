from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/quality/verify_quality_status.py"
WORKFLOW_PATH = ROOT / ".github/workflows/main-quality-status.yml"
spec = importlib.util.spec_from_file_location("verify_quality_status", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SHA = "a" * 40


def load_workflow(path: Path) -> dict:
    """yaml.safe_load of a workflow file."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def trigger_of(data: dict) -> dict:
    """Trigger map of a workflow (YAML 1.1 parses a bare `on:` as True)."""
    return data.get(True, data.get("on", {}))


def steps_of(data: dict) -> list[tuple[str, dict]]:
    """(job_name, step) pairs across all jobs of a workflow."""
    pairs: list[tuple[str, dict]] = []
    for job_name, job in (data.get("jobs") or {}).items():
        for step in (job or {}).get("steps") or []:
            pairs.append((str(job_name), step))
    return pairs


def run_text(step: dict) -> str:
    return str(step.get("run") or "")


def publish_step_of(data: dict) -> dict:
    """The status-publish step, located semantically by its statuses API call."""
    matches = [step for _, step in steps_of(data) if "/statuses/" in run_text(step)]
    assert len(matches) == 1, f"expected exactly one statuses-publish step, got {len(matches)}"
    return matches[0]


def assert_completed_quality_workflow_run_trigger(data: dict) -> None:
    """Parsed twin of the retired raw trigger pins (issue #398 wave 5).

    Retired raw pins: assertIn("workflow_run:"), assertIn("Quality
    integration gate"), assertIn("- completed") and
    assertNotIn("pull_request_target:") against the file text. The parsed
    twin pins the ENTIRE trigger map — workflow_run is the only trigger,
    watching exactly the Quality integration gate workflow with exactly the
    completed type — so any added trigger, watched workflow or type fails,
    regardless of formatting.
    """
    trigger = trigger_of(data)
    assert list(trigger) == ["workflow_run"], (
        f"workflow_run must be the only trigger, got {list(trigger)}"
    )
    wiring = trigger["workflow_run"]
    assert wiring.get("workflows") == ["Quality integration gate"], (
        f"trigger must watch exactly the Quality integration gate workflow, got {wiring.get('workflows')}"
    )
    assert wiring.get("types") == ["completed"], (
        f"trigger must fire on completed only, got {wiring.get('types')}"
    )


def assert_publishes_only_main_push_runs(data: dict) -> None:
    """Parsed twin of the retired main-push gating pins (issue #398 wave 5).

    Retired raw pins: the two single-quoted if conditions, the head_sha
    expression and the exact 40-hex regex, all against the file text. The
    parsed twin pins the job if-condition logic (quote-style normalized —
    GitHub expressions treat 'x' and "x" identically), the HEAD_SHA env
    wiring to the workflow_run head sha, and an exact 40-char lowercase-hex
    SHA validation in the publish step (character-class order normalized).
    """
    job = data["jobs"]["publish-main-quality-status"]
    condition = str(job.get("if") or "").replace('"', "'")
    assert "github.event.workflow_run.event == 'push'" in condition, (
        f"job if must gate on push runs, got: {job.get('if')}"
    )
    assert "github.event.workflow_run.head_branch == 'main'" in condition, (
        f"job if must gate on main, got: {job.get('if')}"
    )
    step = publish_step_of(data)
    env = step.get("env") or {}
    assert env.get("HEAD_SHA") == "${{ github.event.workflow_run.head_sha }}", (
        f"HEAD_SHA must be wired to the workflow_run head sha, got: {env.get('HEAD_SHA')}"
    )
    assert re.search(r"\^\[(?:0-9a-f|a-f0-9)\]\{40\}\$", run_text(step)), (
        "publish step must validate an exact 40-char lowercase hex SHA"
    )


def assert_permission_boundary_is_statuses_write_only(data: dict) -> None:
    """Parsed twin of the retired permission-boundary pins (issue #398 wave 5).

    Retired raw pins: a text-sliced permissions block containing
    "statuses: write", six forbidden "*: write" substrings, no
    "actions/checkout" and no uses: line anywhere. The parsed twin pins the
    WHOLE permission map by strict equality (any added permission fails) and
    walks the parsed jobs/steps for any uses: reference.
    """
    assert data.get("permissions") == {"statuses": "write"}, (
        f"permissions must be exactly statuses:write, got {data.get('permissions')}"
    )
    for job_name, job in (data.get("jobs") or {}).items():
        assert "uses" not in (job or {}), f"job {job_name} must not call a reusable workflow or action"
        for step in (job or {}).get("steps") or []:
            assert "uses" not in step, f"job {job_name} must not use an action: {step.get('name')}"


def assert_fixed_context_and_run_identity_are_published(data: dict) -> None:
    """Parsed twin of the retired run-identity pins (issue #398 wave 5).

    Retired raw pins: the JSON context literal, the four workflow_run
    identity expressions and the /statuses/${HEAD_SHA} path, all against the
    file text. The parsed twin pins the env wiring of the four run-identity
    fields by exact value, and the publish run text: the fixed check context
    value, the statuses API path for the validated head SHA (brace-style
    normalized) and the run identity embedded in the description.
    """
    step = publish_step_of(data)
    env = step.get("env") or {}
    assert env.get("RUN_ID") == "${{ github.event.workflow_run.id }}", (
        f"RUN_ID must be wired to the workflow_run id, got: {env.get('RUN_ID')}"
    )
    assert env.get("RUN_NUMBER") == "${{ github.event.workflow_run.run_number }}", (
        f"RUN_NUMBER must be wired to the workflow_run run_number, got: {env.get('RUN_NUMBER')}"
    )
    assert env.get("RUN_URL") == "${{ github.event.workflow_run.html_url }}", (
        f"RUN_URL must be wired to the workflow_run html_url, got: {env.get('RUN_URL')}"
    )
    assert env.get("RUN_CONCLUSION") == "${{ github.event.workflow_run.conclusion }}", (
        f"RUN_CONCLUSION must be wired to the workflow_run conclusion, got: {env.get('RUN_CONCLUSION')}"
    )
    run = run_text(step).replace("${HEAD_SHA}", "$HEAD_SHA")
    assert "sea-speed/quality-push-main" in run, "publish step must use the fixed check context value"
    assert '"context"' in run, "publish step must publish the context field"
    assert "/statuses/$HEAD_SHA" in run, "publish step must post the status for the validated head SHA"
    for identity in ("RUN_NUMBER", "RUN_ID", "RUN_CONCLUSION"):
        assert identity in run, f"publish description must embed the run identity: {identity}"


def assert_conclusion_mapping_is_fail_closed(data: dict) -> None:
    """Parsed twin of the retired conclusion-mapping pins (issue #398 wave 5).

    Retired raw pins: the success-comparison if and the two STATE
    assignments, as independent substrings. The parsed twin pins the mapping
    STRUCTURE on the publish run text (quote-style normalized — bash [[ ]]
    treats 'x' and "x" identically for literal comparison): the success
    comparison must precede the success state, which must precede the
    failure state, so an inverted or partial mapping fails.
    """
    run = run_text(publish_step_of(data)).replace("'", '"')
    mapping_if = run.find('if [[ "$RUN_CONCLUSION" == "success" ]]; then')
    assert mapping_if != -1, "publish step must compare RUN_CONCLUSION to success"
    success = run.find('STATE="success"')
    failure = run.find('STATE="failure"')
    assert success != -1 and failure != -1, "publish step must map both success and failure states"
    assert mapping_if < success < failure, (
        "success state must be the mapped branch of the success comparison, failure the fallback"
    )


def assert_main_quality_status_publisher_contract(data: dict) -> None:
    """The full converted publisher contract (all five parsed twins)."""
    assert_completed_quality_workflow_run_trigger(data)
    assert_publishes_only_main_push_runs(data)
    assert_permission_boundary_is_statuses_write_only(data)
    assert_fixed_context_and_run_identity_are_published(data)
    assert_conclusion_mapping_is_fail_closed(data)


class QualityStatusTests(unittest.TestCase):
    def test_accepts_exact_successful_main_push_run(self) -> None:
        payload = {"workflow_runs": [{"id": 1, "run_number": 9, "head_sha": SHA, "head_branch": "main", "event": "push", "status": "completed", "conclusion": "success"}]}
        with patch.object(module, "github_json", return_value=payload):
            run = module.verify("MostDef2000/sea-speed", SHA, "token")
        self.assertEqual(run["id"], 1)

    def test_pr_run_is_not_production_quality_proof(self) -> None:
        payload = {"workflow_runs": [{"id": 2, "run_number": 10, "head_sha": SHA, "head_branch": "feature", "event": "pull_request", "status": "completed", "conclusion": "success"}]}
        with patch.object(module, "github_json", return_value=payload):
            with self.assertRaisesRegex(ValueError, "push run on main"):
                module.verify("MostDef2000/sea-speed", SHA, "token")

    def test_uppercase_sha_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "lowercase"):
            module.verify("MostDef2000/sea-speed", SHA.upper(), "token")


class MainQualityStatusPublisherTests(unittest.TestCase):
    """Parsed-structure twins for the Main Quality status publisher workflow.

    Issue #398 wave 5: the five tests retired their raw source-text pins on
    .github/workflows/main-quality-status.yml; each now executes the
    module-level parsed twin of the same name, and the twins are reused by
    tests/test_398_wave5_demo.py against tmp workflow copies. The three
    executed verify_quality_status module tests above are untouched.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = load_workflow(WORKFLOW_PATH)

    def test_uses_completed_quality_workflow_run_only(self) -> None:
        assert_completed_quality_workflow_run_trigger(self.workflow)

    def test_publishes_only_main_push_runs(self) -> None:
        assert_publishes_only_main_push_runs(self.workflow)

    def test_permission_boundary_is_statuses_write_only(self) -> None:
        assert_permission_boundary_is_statuses_write_only(self.workflow)

    def test_fixed_context_and_run_identity_are_published(self) -> None:
        assert_fixed_context_and_run_identity_are_published(self.workflow)

    def test_conclusion_mapping_is_fail_closed(self) -> None:
        assert_conclusion_mapping_is_fail_closed(self.workflow)


if __name__ == "__main__":
    unittest.main()
