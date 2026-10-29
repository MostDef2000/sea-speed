"""Issue #398 wave 5 demo: parsed-structure twins vs raw source-text pins.

Target check: the converted Main Quality status publisher contract
(.github/workflows/main-quality-status.yml — the workflow_run trigger watches
exactly the Quality integration gate workflow on completed, the job gates on
push+main, permissions are exactly statuses:write with no uses: steps, the
run identity is wired from the workflow_run event, the status context is the
fixed sea-speed/quality-push-main, and the conclusion mapping is fail-closed).

Two-direction proof, mirroring the wave-1/2/3/4 demos:

- Direction A (refactor tolerance): a tmp copy of the real workflow rewritten
  behavior-preservingly (quoted trigger key, flow-style lists, \\x20-escaped
  watched-workflow name, double-quoted expression literals, hex-escaped env
  expression dots, equivalent regex character-class order, bash single-quote
  literals, brace-less shell variable, python payload context variable) still
  satisfies every parsed twin, while ALL retired raw-text pins fail on it.
- Direction B (dead-marker intolerance): a tmp copy that keeps every retired
  marker verbatim but inverts the conclusion mapping (success and failure
  states swapped) passes the retired text pins and FAILS the parsed twins.

Both directions run against tmp copies only; .github/ is never modified.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_quality_status import assert_main_quality_status_publisher_contract

WORKFLOW = ROOT / ".github/workflows/main-quality-status.yml"

# The retired raw-text pins of the five converted MainQualityStatusPublisher
# tests (issue #398 wave 5), restated here for the two-direction proof.
RETIRED_TEXT_PINS = (
    "workflow_run:",  # trigger key (raw block style)
    "Quality integration gate",  # watched workflow name (raw spelling)
    "- completed",  # trigger type (block list item)
    "github.event.workflow_run.event == 'push'",  # job if condition (single-quoted)
    "github.event.workflow_run.head_branch == 'main'",  # job if condition (single-quoted)
    "github.event.workflow_run.head_sha",  # head-sha env expression (dotted)
    "^[0-9a-f]{40}$",  # SHA validation regex (class order)
    "statuses: write",  # permission (block style)
    '"context": "sea-speed/quality-push-main"',  # payload context (inline literal)
    "workflow_run.id",  # run identity env expression
    "workflow_run.run_number",  # run identity env expression
    "workflow_run.html_url",  # run identity env expression
    "workflow_run.conclusion",  # run identity env expression
    "/statuses/${HEAD_SHA}",  # statuses URL (braced shell variable)
    'if [[ "$RUN_CONCLUSION" == "success" ]]',  # conclusion branch (double-quoted)
    'STATE="success"',  # success state (double-quoted)
    'STATE="failure"',  # failure state (double-quoted)
)


def _replace_exact(source: str, old: str, new: str) -> str:
    assert old in source, f"demo anchor drifted: {old[:70]!r}"
    return source.replace(old, new, 1)


def _refactored_workflow(source: str) -> str:
    """Rewrite every retired marker's spelling; identical parsed semantics.

    Each rewrite is behavior-preserving: quoted YAML keys, flow-style lists,
    ``\\x20``/``\\x2e`` hex escapes inside double-quoted scalars (PyYAML
    decodes them to the identical strings), double-quoted GitHub expression
    literals ('x' and "x" are the same expression string), an equivalent
    regex character-class order, bash single-quote literals inside [[ ]],
    a brace-less shell variable, and a python payload context variable.
    """
    # Trigger: quoted key, flow lists, escaped watched-workflow name.
    source = _replace_exact(
        source,
        "on:\n  workflow_run:\n    workflows:\n      - Quality integration gate\n    types:\n      - completed\n",
        'on:\n  "workflow_run":\n    workflows: ["Quality\\x20integration\\x20gate"]\n    types: [completed]\n',
    )
    # Permissions: flow mapping with a quoted key (identical parsed map).
    source = _replace_exact(
        source,
        "permissions:\n  statuses: write\n",
        'permissions: {"statuses": write}\n',
    )
    # Job if: double-quoted expression string literals (identical semantics).
    source = _replace_exact(
        source,
        "    if: github.event.workflow_run.event == 'push' && github.event.workflow_run.head_branch == 'main'\n",
        '    if: "github.event.workflow_run.event == \\"push\\" && github.event.workflow_run.head_branch == \\"main\\""\n',
    )
    # Run-identity env wiring: hex-escaped dots inside double-quoted scalars
    # (PyYAML decodes each to the exact original expression string).
    for field in ("head_sha", "id", "run_number", "html_url", "conclusion"):
        env_key = {
            "head_sha": "HEAD_SHA",
            "id": "RUN_ID",
            "run_number": "RUN_NUMBER",
            "html_url": "RUN_URL",
            "conclusion": "RUN_CONCLUSION",
        }[field]
        source = _replace_exact(
            source,
            f"          {env_key}: ${{{{ github.event.workflow_run.{field} }}}}\n",
            f'          {env_key}: "${{{{ github\\x2eevent\\x2eworkflow_run\\x2e{field} }}}}"\n',
        )
    # Publish run text: equivalent regex class order, bash single-quote
    # literals, brace-less variable, python payload context variable.
    source = _replace_exact(
        source,
        'if [[ ! "$HEAD_SHA" =~ ^[0-9a-f]{40}$ ]]; then',
        'if [[ ! "$HEAD_SHA" =~ ^[a-f0-9]{40}$ ]]; then',
    )
    source = _replace_exact(
        source,
        'if [[ "$RUN_CONCLUSION" == "success" ]]; then',
        "if [[ \"$RUN_CONCLUSION\" == 'success' ]]; then",
    )
    source = _replace_exact(source, 'STATE="success"', "STATE='success'")
    source = _replace_exact(source, 'STATE="failure"', "STATE='failure'")
    source = _replace_exact(source, "/statuses/${HEAD_SHA}", "/statuses/$HEAD_SHA")
    source = _replace_exact(
        source,
        "          import json\n          import os\n\n          print(json.dumps({",
        '          import json\n          import os\n\n          CONTEXT = "sea-speed/quality-push-main"\n\n          print(json.dumps({',
    )
    source = _replace_exact(
        source,
        '              "context": "sea-speed/quality-push-main",',
        '              "context": CONTEXT,',
    )
    return source


def _marker_only_broken_workflow(source: str) -> str:
    """Keep ALL retired marker text verbatim but invert the conclusion mapping.

    The success branch yields the failure state and vice versa. Every retired
    text pin survives byte-for-byte (the comparison line and both STATE
    assignments are still present), while the parsed fail-closed mapping twin
    fails because the success state no longer follows the success comparison.
    """
    healthy = (
        'if [[ "$RUN_CONCLUSION" == "success" ]]; then\n'
        '            STATE="success"\n'
        "          else\n"
        '            STATE="failure"\n'
    )
    broken = (
        'if [[ "$RUN_CONCLUSION" == "success" ]]; then\n'
        '            STATE="failure"\n'
        "          else\n"
        '            STATE="success"\n'
    )
    assert healthy in source, "conclusion-mapping anchor changed; demo needs an update"
    return source.replace(healthy, broken, 1)


def _run_parsed_twins(workflow_text: str) -> tuple[bool, str]:
    """Run the converted parsed twins against a workflow copy."""
    try:
        assert_main_quality_status_publisher_contract(yaml.safe_load(workflow_text))
    except AssertionError as exc:
        return False, str(exc)[:400]
    return True, ""


def _run_retired_text_pins(workflow_text: str) -> tuple[bool, list[str]]:
    """Run the RETIRED raw-text pins against a workflow copy (demo only)."""
    failed = [marker for marker in RETIRED_TEXT_PINS if marker not in workflow_text]
    return (not failed), failed


class Test398Wave5Demo(unittest.TestCase):
    def test_refactor_tolerance_and_dead_marker_intolerance(self) -> None:
        real_workflow = WORKFLOW.read_text(encoding="utf-8")
        # Sanity: the real workflow satisfies the parsed twins.
        real_ok, real_error = _run_parsed_twins(real_workflow)
        self.assertTrue(real_ok, f"real workflow must satisfy the parsed twins: {real_error}")
        # Direction A: behavior-preserving refactor.
        refactored = _refactored_workflow(real_workflow)
        refactored_ok, refactored_error = _run_parsed_twins(refactored)
        retired_ok, retired_failed = _run_retired_text_pins(refactored)
        self.assertTrue(
            refactored_ok,
            f"parsed twins must tolerate a pure refactor: {refactored_error}",
        )
        self.assertFalse(
            retired_ok,
            f"retired text pins would fail the refactor (expected): {retired_failed}",
        )
        # Every retired pin individually fails the refactor — the raw pins
        # are pure spelling anchors, the parsed twins carry the whole contract.
        self.assertEqual(retired_failed, list(RETIRED_TEXT_PINS))
        # Direction B: markers kept, mapping broken.
        broken = _marker_only_broken_workflow(real_workflow)
        broken_ok, broken_error = _run_parsed_twins(broken)
        broken_retired_ok, _ = _run_retired_text_pins(broken)
        self.assertFalse(
            broken_ok,
            "parsed twins must fail a workflow whose conclusion mapping is "
            f"inverted despite intact marker text: {broken_error}",
        )
        self.assertTrue(
            broken_retired_ok,
            "retired text pins pass the marker-only workflow (the false-green "
            "the conversion removes)",
        )


if __name__ == "__main__":
    unittest.main()
