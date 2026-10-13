"""Issue #398 Wave A — regression demo for the converted worker pins.

Three directions from the #398 Slice 0 plan:

1. Equivalent-but-reformatted worker code passes the converted checks
   (behavioral exec + structural AST), and the ``SEA_SPEED_WORKER_SOURCE``
   override retargets the shared harness at a rewritten layout — exactly the
   situation the #397 decomposition creates.
2. The converted mechanism rejects a dead-code fixture that the retired
   source-text pin would have false-passed.
3. A multi-file (``os.pathsep``-joined) ``SEA_SPEED_WORKER_SOURCE`` resolves
   and executes functions spread across sources.

Direction 2 contrast (observed in a one-off probe, not re-asserted here):
on the dead-code fixture below the retired pin
``self.assertIn('publishable = track_id is not None and '
'best.get("object_type") != "person"', source)`` evaluates True — the gate
text lives inside a dead function — so the old test would have passed. The
converted ``WorkerEventGateTests.test_gate_requires_track_and_blocks_person``
(test_road_event_hygiene.py:57, pins formerly L51-64) requires the gate to
be assigned exactly once inside ``main()``, so the same fixture fails it.
"""

from __future__ import annotations

import ast
import os
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

try:
    from tests.support import worker_source
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import worker_source

# Behavioral stub namespace shared by the exec-based checks: the extracted
# worker functions resolve these names at call time, mirroring the converted
# worker-contract harness.
STUB_NAMESPACE = {
    "time": time,
    "uuid": uuid,
    "now_iso": lambda: "2026-10-13T00:00:00+00:00",
    "env_str": lambda name, default="": {"MODEL_NAME": "yolo11s.pt"}.get(name, default),
    "fetch_speed_config": lambda: {"enabled": True, "kmh_per_px_s": 0.036},
}

# Tiny live worker bodies used to build multi-file fixtures (kept in sync
# with worker/hls_motion_yolo_worker_events.py L1163-1187).
SIDE_OF_LINE_SRC = '''\
def side_of_line(point, line):
    if not line or len(line) != 2:
        return None
    x, y = point
    x1, y1 = line[0]
    x2, y2 = line[1]
    return (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
'''

CROSSED_LINE_SRC = '''\
def crossed_line(prev_side, current_side):
    ps = sign_with_deadzone(prev_side)
    cs = sign_with_deadzone(current_side)
    if ps == 0 or cs == 0:
        return False
    return ps != cs
'''

SIGN_WITH_DEADZONE_SRC = '''\
def sign_with_deadzone(value, deadzone=1.0):
    if value is None:
        return 0
    if value > deadzone:
        return 1
    if value < -deadzone:
        return -1
    return 0
'''

# Direction 2 fixtures: identical module except for where the historical
# gate text lives.
DEAD_CODE_FIXTURE = '''\
def dead_legacy_gate(best, track_id):
    publishable = track_id is not None and best.get("object_type") != "person"
    return publishable


def main():
    pass
'''

GATE_ONCE_FIXTURE = '''\
def main():
    for best in detections:
        if best:
            publishable = track_id is not None and best.get("object_type") != "person"
            if publishable:
                post(best)
'''

GATE_TWICE_FIXTURE = '''\
def main():
    publishable = track_id is not None
    if best:
        publishable = track_id is not None and best.get("object_type") != "person"
        if publishable:
            post(best)
'''


def _main_of(source: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("fixture has no main()")


class ReformattedEquivalentTests(unittest.TestCase):
    def test_unparsed_equivalent_passes_converted_checks_and_retargets_env(self) -> None:
        # Direction (a): build a behaviorally equivalent but differently
        # formatted module from the live worker (ast.unparse drops comments
        # and normalizes spacing/quoting), retarget the harness at it via
        # SEA_SPEED_WORKER_SOURCE, and show the converted checks still hold.
        live = worker_source.function_nodes({"build_event", "convert_px_s_to_kmh"})
        variant_source = (
            "# Issue #397 rehearsal: reformatted equivalent module\n\n"
            + ast.unparse(live["build_event"])
            + "\n\n\n"
            + ast.unparse(live["convert_px_s_to_kmh"])
            + "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            variant_path = Path(tmp) / "worker_split_part1.py"
            variant_path.write_text(variant_source, encoding="utf-8")
            with mock.patch.dict(os.environ, {"SEA_SPEED_WORKER_SOURCE": str(variant_path)}):
                # The env override resolves and parses the rewritten layout.
                variant_trees = worker_source.module_trees()
                self.assertEqual(len(variant_trees), 1)
                namespace = worker_source.load_functions(
                    {"build_event", "convert_px_s_to_kmh"}, dict(STUB_NAMESPACE)
                )
                variant_main_tree = ast.parse(variant_source)
                variant_build_event = next(
                    node
                    for node in variant_main_tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "build_event"
                )

        # Behavioral: the reformatted build_event still converts px/s speed
        # through the px factor and keeps the no-profile defaults.
        event = namespace["build_event"](
            {
                "track_id": 7,
                "class_name": "car",
                "confidence": 0.9,
                "bbox_xyxy": [0, 0, 10, 10],
            },
            42.0,
            {
                "speed_px_s": 1000.0,
                "center_x": 1.0,
                "center_y": 2.0,
                "dx_px": 3.0,
                "dy_px": 4.0,
                "dt_sec": 0.5,
                "distance_px": 6.0,
            },
        )
        self.assertEqual(event["speed_kmh"], 36.0)
        self.assertEqual(event["speed_source"], "px_factor")
        self.assertEqual(event["model_name"], "yolo11s.pt")
        self.assertEqual(event["motion_area"], 42)
        event_id = event["event_id"]
        self.assertIn("-", event_id)
        self.assertEqual(len(event_id.rsplit("-", 1)[1]), 8)

        # Structural: the converted invariants hold on BOTH the live module
        # and the reformatted equivalent (formatting-independent checks do
        # not false-fail the #397 decomposition).
        for build_event_node in (
            worker_source.function_node("build_event"),
            variant_build_event,
        ):
            self.assertTrue(
                worker_source.contains_stmt(
                    build_event_node,
                    'event_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"',
                ),
                "event_id identity must stay composed from time + uuid",
            )
            self.assertTrue(
                worker_source.contains_expr(build_event_node, 'env_str("MODEL_NAME", "yolo11s.pt")'),
                "model_name default must stay env-driven with the yolo11s fallback",
            )


class DeadCodeVerdictTests(unittest.TestCase):
    def _require_gate_once(self, main_node: ast.FunctionDef) -> None:
        matches = worker_source.find_assignments(main_node, "publishable")
        self.assertEqual(
            len(matches),
            1,
            "publishable gate must be assigned exactly once inside main()",
        )

    def test_converted_mechanism_rejects_dead_code_that_text_pin_false_passes(self) -> None:
        # Direction (b): the dead-code fixture keeps the historical gate
        # text in a dead function and a main() without the gate. The retired
        # source-text pin would PASS on it (the text exists); the converted
        # main()-scoped check FAILS it.
        with self.assertRaises(AssertionError):
            self._require_gate_once(_main_of(DEAD_CODE_FIXTURE))
        # The gate existing exactly once inside main() is accepted...
        self._require_gate_once(_main_of(GATE_ONCE_FIXTURE))
        # ...and a duplicated gate is still rejected (the old text pin could
        # not see duplication at all).
        with self.assertRaises(AssertionError):
            self._require_gate_once(_main_of(GATE_TWICE_FIXTURE))


class MultiSourceResolutionTests(unittest.TestCase):
    def test_pathsep_joined_sources_resolve_and_execute_across_files(self) -> None:
        # Direction (c): a #397-style multi-file worker resolves through the
        # os.pathsep-joined override and execs into one shared namespace.
        with tempfile.TemporaryDirectory() as tmp:
            part_a = Path(tmp) / "worker_part_a.py"
            part_b = Path(tmp) / "worker_part_b.py"
            part_a.write_text(SIDE_OF_LINE_SRC + "\n\n" + CROSSED_LINE_SRC, encoding="utf-8")
            part_b.write_text(SIGN_WITH_DEADZONE_SRC, encoding="utf-8")
            override = os.pathsep.join((str(part_a), str(part_b)))
            with mock.patch.dict(os.environ, {"SEA_SPEED_WORKER_SOURCE": override}):
                self.assertEqual(len(worker_source.module_trees()), 2)
                namespace = worker_source.load_functions(
                    {"crossed_line", "side_of_line", "sign_with_deadzone"},
                    {},
                )
        # Behavioral: functions split across files still cooperate.
        self.assertTrue(namespace["crossed_line"](5.0, -5.0))
        self.assertFalse(namespace["crossed_line"](5.0, 5.0))
        self.assertFalse(namespace["crossed_line"](0.5, -0.5))  # deadzone


if __name__ == "__main__":
    unittest.main()
