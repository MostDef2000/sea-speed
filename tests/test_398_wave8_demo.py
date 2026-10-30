"""Issue #398 wave 8 demo: parsed step-lookup extraction vs regex/line-scan slicing.

Target helpers: tests/test_deploy_freshness.py `_extract_freshness_run_block`
(issue #398 wave 8) — the freshness step's `run:` script is looked up in the
PARSED workflow YAML (`yaml.safe_load`) instead of sliced out of the raw text
by a line-scan between text anchors.

Two-direction proof, mirroring the wave-1..7 demos:

- Direction A (refactor tolerance): a reformatted-but-equivalent workflow
  variant — a YAML comment inserted in the old helper's sweep region, the
  whole steps list reindented, an unrelated step reordered before the
  freshness step — yields the IDENTICAL extracted run text (assertEqual of
  the two extractions, and equality with the expected script bytes).
- Direction B (old-approach brittleness): a verbatim copy of the RETIRED
  line-scan helper (demo-twin-копия — задокументированный паттерн, дрейфа
  нет; documented like the wave-5 demo row in specs/398-wave5/plan.md) does
  NOT survive the same harmless reformat: it returns different bytes than
  the parsed extraction (its `^      - name:` terminator no longer matches
  the reindented following step, so it sweeps to EOF and swallows the
  comment into the "script"). The old approach false-failed on harmless
  refactors; the parsed lookup is stable. Direction B constrains only the
  legacy copy; the demo's RED-sensitivity against a module revert lives in
  Direction A (the reformatted-equality assertion fails under the retired
  implementation).

Both directions run against in-memory strings only; no repo file is modified.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_deploy_freshness import _extract_freshness_run_block

EXPECTED_FRESHNESS_SCRIPT = (
    "set -euo pipefail\n"
    'echo "fresh=true" >> "$GITHUB_OUTPUT"\n'
)

ORIGINAL_WORKFLOW = """\
name: Freshness demo
on:
  workflow_run:
    workflows: [Quality integration gate]
jobs:
  evaluate:
    steps:
      - name: Require quality commit is current main tip
        id: freshness
        run: |
          set -euo pipefail
          echo "fresh=true" >> "$GITHUB_OUTPUT"
"""

# Semantically identical to ORIGINAL_WORKFLOW: an unrelated step reordered
# before the freshness step, the whole steps list reindented two columns
# deeper, and a YAML comment inserted in the region the retired line-scan
# helper sweeps (at step-key indentation, so the parser drops it instead of
# folding it into the block scalar).
REFORMATTED_WORKFLOW = """\
name: Freshness demo
on:
  workflow_run:
    workflows: [Quality integration gate]
jobs:
  evaluate:
    steps:
        # wave-8 demo: an unrelated step reordered before the freshness step
        - name: Set up Python
          uses: actions/setup-python@v5
        - name: Require quality commit is current main tip
          id: freshness
          run: |
            set -euo pipefail
            echo "fresh=true" >> "$GITHUB_OUTPUT"
          # wave-8 demo comment: a YAML comment is not script content
        - name: Summarize policy decision
          run: |
            echo "summarizing"
"""


def _legacy_line_scan_extract_freshness_run_block(source: str) -> str:
    """Verbatim copy of the RETIRED pre-wave-8 `_extract_freshness_run_block`.

    demo-twin-копия — задокументированный паттерн, дрейфа нет: this is the
    exact line-scan implementation retired by issue #398 wave 8, inlined for
    the brittleness proof only (documented like the wave-5 demo row in
    specs/398-wave5/plan.md). It must never be re-adopted in the module.
    """
    lines = source.splitlines()
    anchor = next((i for i, line in enumerate(lines) if line.strip() == "id: freshness"), None)
    if anchor is None:
        raise AssertionError("workflow YAML has no freshness step anchor 'id: freshness'")
    run_index = None
    for index in range(anchor, min(anchor + 8, len(lines))):
        if re.match(r"^\s*run:\s*\|\s*$", lines[index]):
            run_index = index
            break
    if run_index is None:
        raise AssertionError("freshness step has no 'run: |' block after 'id: freshness'")
    block: list[str] = []
    for line in lines[run_index + 1:]:
        if re.match(r"^      - name:", line):
            break
        block.append(line)
    while block and not block[-1].strip():
        block.pop()
    if not block:
        raise AssertionError("freshness run block is empty")
    indent = min(len(line) - len(line.lstrip(" ")) for line in block if line.strip())
    return "\n".join(line[indent:] if line.strip() else "" for line in block) + "\n"


class Test398Wave8Demo(unittest.TestCase):
    def test_refactor_tolerance_and_legacy_line_scan_brittleness(self) -> None:
        # Sanity: the module's parsed extraction returns the expected script
        # bytes for the original workflow (exercises the new code path for
        # real — no mocking; if the module were still line-scan-based, the
        # Direction-A equality below would fail on the reformatted variant).
        original_run = _extract_freshness_run_block(ORIGINAL_WORKFLOW)
        self.assertEqual(original_run, EXPECTED_FRESHNESS_SCRIPT)
        # Direction A (refactor tolerance): comment insertion, reindentation
        # and step reordering leave the parsed extraction byte-identical.
        reformatted_run = _extract_freshness_run_block(REFORMATTED_WORKFLOW)
        self.assertEqual(reformatted_run, original_run)
        self.assertEqual(reformatted_run, EXPECTED_FRESHNESS_SCRIPT)
        # Direction B (old-approach brittleness): the retired line-scan copy
        # extracted the original correctly...
        self.assertEqual(_legacy_line_scan_extract_freshness_run_block(ORIGINAL_WORKFLOW), EXPECTED_FRESHNESS_SCRIPT)
        # ...but does NOT survive the harmless reformat: it either raises or
        # returns different bytes than the parsed extraction (observed here:
        # different bytes — it sweeps past the reindented following step and
        # swallows the YAML comment into the extracted "script").
        try:
            legacy_reformatted = _legacy_line_scan_extract_freshness_run_block(REFORMATTED_WORKFLOW)
        except AssertionError:
            legacy_reformatted = None
        self.assertTrue(
            legacy_reformatted is None or legacy_reformatted != reformatted_run,
            "retired line-scan extraction unexpectedly survived the reformat",
        )


if __name__ == "__main__":
    unittest.main()
