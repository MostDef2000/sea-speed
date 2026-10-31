# Issue #573 demo: ast.parse structural twins vs raw source-line pins.
#
# Direction A (stability): a harmless reformat of the pinned source (comment
# insertion + whitespace drift) keeps the parsed twin's verdict green, while a
# verbatim copy of the retired raw `assertIn` approach false-fails on the same
# reformat (demo-twin-копия — documented pattern, see specs/398-wave5/plan.md
# and the wave-8 demo row).
#
# Direction B (teeth): a semantic mutation (the pinned `diagnostics=None`
# default removed from the signature) turns the parsed twin RED — the twin
# tracks structure, not text, so a mutation that changes behavior cannot hide.
#
# The twin under test is the real helper from tests/test_water_recall_ubuntu_ipc.py
# (wave-8 import style: import the module under demonstration, no mocking).
# RED-sensitivity of the WIRED test methods themselves (not just these helpers)
# is proven separately by the mutation probes on tmp copies recorded in the
# delivery record (PR body / specs/573-residual-parsed-twins/tasks.md).
from __future__ import annotations

import ast
import unittest

from tests.test_water_recall_ubuntu_ipc import (
    _find_function_def,
    _parameter_facts,
    _parse_source,
)

_ORIGINAL = """\
def supervised_detect_vehicles(_model, frame, diagnostics=None):
    supervisor = BoundedYoloSupervisor(_model)
    return supervisor.detect(frame, diagnostics=diagnostics)
"""

# Semantically identical to _ORIGINAL: comments added, whitespace drifted.
_REFORMATTED = """\
# operator note: wrapper keeps the two-argument callers backward compatible
def supervised_detect_vehicles(_model, frame,     diagnostics=None):
    supervisor = BoundedYoloSupervisor(_model)
    # diagnostics flows to the bounded detector
    return supervisor.detect(frame, diagnostics=diagnostics)
"""

# Semantic mutation: the diagnostics sink is gone (signature + call changed).
_MUTATED = """\
def supervised_detect_vehicles(_model, frame):
    supervisor = BoundedYoloSupervisor(_model)
    return supervisor.detect(frame)
"""


def _parsed_twin_accepts(source: str) -> bool:
    """The parsed twin: supervised_detect_vehicles keeps its diagnostics=None default."""
    tree = _parse_source(source, "fixture.py")
    func = _find_function_def(tree, "supervised_detect_vehicles")
    facts = _parameter_facts(func)
    default = facts.get("diagnostics")
    return isinstance(default, ast.Constant) and default.value is None


def _retired_raw_pin(source: str) -> bool:
    """Verbatim copy of the retired raw approach (demo-twin-копия — задокументированный
    паттерн, дрейфа нет): exact source-line substring pin. It must never be
    re-adopted in the module."""
    return "def supervised_detect_vehicles(_model, frame, diagnostics=None):" in source


class Demo573Tests(unittest.TestCase):
    def test_ast_twin_is_refactor_blind_and_keeps_teeth(self) -> None:
        # Direction A: the harmless reformat is accepted by the parsed twin...
        self.assertTrue(_parsed_twin_accepts(_ORIGINAL))
        self.assertTrue(_parsed_twin_accepts(_REFORMATTED))
        # ...while the retired raw pin false-fails on the same reformat
        # (RED-sensitivity: under a raw-line implementation this assertion
        # fails, which is exactly the brittleness #573 removes).
        self.assertFalse(
            _retired_raw_pin(_REFORMATTED),
            "the retired raw pin must false-fail on the harmless reformat",
        )
        # Direction B: the semantic mutation is rejected by the parsed twin
        # (teeth: a structure-tracking twin cannot be satisfied by text alone).
        self.assertFalse(
            _parsed_twin_accepts(_MUTATED),
            "the parsed twin must reject the mutated signature",
        )


if __name__ == "__main__":
    unittest.main()
