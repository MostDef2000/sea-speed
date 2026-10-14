"""Issue #397 wave-6 integrity: worker_crossings split of the runtime worker.

Guards the invariants of the wave-6 move-only refactor (the crossing-domain
cluster: 5 state literals + 6 defs moved verbatim from
hls_motion_yolo_worker_events.py into worker/worker_crossings.py):

(a) Import allowlist for worker_crossings (crossing analogue of the wave-2/3/4
    module allowlists): top-level imports limited to time, datetime and the
    repo-pure siblings worker_kernel (env_float, side_of_line,
    sign_with_deadzone) and worker_transport (the two shared crossing objects
    + fetch_crossing_line_config). NO offline-layer imports (cv2/numpy/
    ultralytics/av/subprocess/socket/threading/queue) and NO requests/json/
    pathlib/os — the crossing layer is offline except through the transport
    fetcher.
(b) Placement separation: the 6 crossing defs and 5 state literals are
    defined ONLY in worker/worker_crossings.py (no duplicate defs in the
    worker), the worker re-exports exactly the 6 def names (state names have
    no staying reader and are NOT re-exported), and the wave-4/5 transport
    re-export block is untouched (15 names).
(c) Strict no-rebinding guard across the worker sources: for
    _crossing_counts/_crossings_by_class/_crossing_track_sides/VLZ_TIMEZONE
    the ONLY Store access anywhere under worker/*.py is the defining literal
    in worker_crossings.py (every other access is an in-place mutation or a
    read — the same discipline as the wave-4/5 cache contract).
(d) Rebinder coupling for _crossing_vlz_date: the state literal moved WITH
    its sole rebinder — exactly ONE Assign beyond the defining literal exists
    in the whole worker source set, it sits inside maybe_reset_daily_crossings,
    the ONLY `global` statement naming it sits in that same def, and both the
    def and the literal are top-level in worker_crossings.py. The pair must
    never be split (a rebinding name cannot move away from its rebinder).
(e) Identity + globals()-guard regression: a pristine subprocess import pins
    worker.<def> IS worker_crossings.<def> for all 6 moved defs and
    "crossing_overlay_summary" in vars(worker) — the globals()-guard call
    site in build_road_live_envelope (worker) depends on that membership, so
    losing the re-export would silently drop crossings from the road live
    envelope instead of failing loudly.
(f) Compatibility gate: MODULE_SOURCES is the six-file union (worker +
    media + render + transport + crossings + live), union-compatible with
    every required env name still resolved across the union (wave-7
    transfer: the gate grows by worker_live.py, this file's pin tracks the
    count).
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker" / "hls_motion_yolo_worker_events.py"
CROSSINGS = ROOT / "worker" / "worker_crossings.py"
TRANSPORT = ROOT / "worker" / "worker_transport.py"

# Exact moved-name sets for wave 6 (keep in sync with the
# `from worker_crossings import (...)` block — the tests below enforce BOTH
# directions of that sync for the defs; the state literals are deliberately
# NOT re-exported: the worker has zero staying readers of them).
CROSSINGS_MOVED_DEFS = (
    "vlz_date",
    "reset_crossing_counts",
    "maybe_reset_daily_crossings",
    "prune_crossing_tracks",
    "update_crossing_counts",
    "crossing_overlay_summary",
)
CROSSINGS_STATE_NAMES = (
    "_crossing_track_sides",
    "_crossing_counts",
    "_crossings_by_class",
    "VLZ_TIMEZONE",
    "_crossing_vlz_date",
)
# The strictly non-rebinding state names (pin (c)); _crossing_vlz_date is
# covered separately by the rebinder-coupling pin (d).
NON_REBINDING_STATE_NAMES = (
    "_crossing_track_sides",
    "_crossing_counts",
    "_crossings_by_class",
    "VLZ_TIMEZONE",
)
WORKER_TRANSPORT_REEXPORT_COUNT = 15  # wave-4 (9) + wave-5 (6); exact set pinned by tests/test_worker_transport_module.py

# Top-level import allowlist for worker_crossings: stdlib time/datetime +
# repo-pure siblings only. NOT included: cv2/numpy (render/detection),
# ultralytics/av (model/media), subprocess/socket (spawn/raw sockets),
# threading/queue (live-publisher loop), requests/json/pathlib/os (network
# and payload plumbing live in worker_transport/worker_kernel).
CROSSINGS_IMPORT_ALLOWLIST = frozenset({"time", "datetime", "worker_kernel", "worker_transport"})

FORBIDDEN_CROSSINGS_IMPORTS = frozenset(
    {
        "cv2",
        "numpy",
        "ultralytics",
        "av",
        "subprocess",
        "socket",
        "threading",
        "queue",
        "requests",
        "json",
        "pathlib",
        "os",
    }
)


def _top_level_import_names(source: str) -> set[str]:
    tree = ast.parse(source, filename="worker_crossings.py")
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class WorkerCrossingsImportAllowlistTests(unittest.TestCase):
    def test_crossings_module_top_level_imports_within_allowlist(self) -> None:
        imported = _top_level_import_names(CROSSINGS.read_text(encoding="utf-8-sig"))
        self.assertEqual(
            sorted(imported - CROSSINGS_IMPORT_ALLOWLIST),
            [],
            "worker_crossings gained a top-level import outside the crossings allowlist",
        )
        # Double-armed: the two repo-pure siblings are REQUIRED — the moved
        # bodies resolve env/deadzone helpers from worker_kernel and the
        # shared crossing objects/fetcher from worker_transport.
        self.assertIn("worker_kernel", imported, "crossing layer must reuse the kernel helpers")
        self.assertIn("worker_transport", imported, "crossing layer must reuse the transport objects/fetcher")

    def test_crossings_module_has_no_offline_layer_imports(self) -> None:
        # The crossing layer is offline: analytics domain logic over the
        # transport fetcher only. cv2/numpy (render/detection), ultralytics/av
        # (model/media), subprocess/socket (spawn/raw sockets), threading/queue
        # (live-publisher loop) and requests/json/pathlib/os at module level
        # fail CI.
        tree = ast.parse(CROSSINGS.read_text(encoding="utf-8-sig"), filename=str(CROSSINGS))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(
                        alias.name.split(".")[0],
                        FORBIDDEN_CROSSINGS_IMPORTS,
                        f"worker_crossings must not import {alias.name} at module level",
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(
                    node.module.split(".")[0],
                    FORBIDDEN_CROSSINGS_IMPORTS,
                    f"worker_crossings must not import from {node.module} at module level",
                )


class WorkerCrossingsPlacementTests(unittest.TestCase):
    def test_crossing_names_defined_only_in_crossings_module(self) -> None:
        def top_defs(path: Path) -> set[str]:
            return {
                node.name
                for node in ast.parse(path.read_text(encoding="utf-8-sig")).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }

        def top_assigns(path: Path) -> set[str]:
            return {
                node.targets[0].id
                for node in ast.parse(path.read_text(encoding="utf-8-sig")).body
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            }

        crossings_defs = top_defs(CROSSINGS)
        crossings_assigns = top_assigns(CROSSINGS)
        worker_defs = top_defs(WORKER)
        transport_defs = top_defs(TRANSPORT)
        self.assertEqual(
            sorted(set(CROSSINGS_MOVED_DEFS) - crossings_defs),
            [],
            "every crossing function must be DEFINED in worker_crossings.py",
        )
        self.assertEqual(
            sorted(set(CROSSINGS_STATE_NAMES) - crossings_assigns),
            [],
            "every crossing state literal must be DEFINED in worker_crossings.py",
        )
        self.assertEqual(
            sorted(set(CROSSINGS_MOVED_DEFS) & worker_defs),
            [],
            "moved crossing defs must not keep duplicate definitions in the worker",
        )
        self.assertEqual(
            sorted(set(CROSSINGS_MOVED_DEFS) & transport_defs),
            [],
            "moved crossing defs must not be defined in worker_transport.py",
        )
        # The 15 transport re-exported names are UNCHANGED by wave 6: none of
        # them may be (re)defined in worker_crossings.py — the crossings
        # module imports the shared objects, it never redefines them (the
        # exact 15-name set itself stays pinned by tests/test_worker_transport_module.py).
        transport_assigns = top_assigns(TRANSPORT)
        moved_transport_names = transport_defs | transport_assigns
        self.assertGreaterEqual(len(moved_transport_names), WORKER_TRANSPORT_REEXPORT_COUNT)
        self.assertEqual(
            sorted(set(CROSSINGS_MOVED_DEFS) & moved_transport_names),
            [],
            "crossing defs are distinct from the transport-owned moved names",
        )

    def test_worker_reexports_exact_crossings_def_set(self) -> None:
        # (b) exact-list check, both directions: the worker re-exports the 6
        # moved defs via ONE flat sibling ImportFrom; state names are NOT
        # re-exported (no staying reader).
        tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
        imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_crossings"
        ]
        self.assertEqual(
            len(imports),
            1,
            "worker must import the moved crossing names from worker_crossings exactly once",
        )
        aliases = [alias.name for alias in imports[0].names]
        self.assertEqual(sorted(aliases), sorted(CROSSINGS_MOVED_DEFS))
        self.assertEqual(
            sorted(set(CROSSINGS_STATE_NAMES) & set(aliases)),
            [],
            "crossing state names must not be re-exported (no staying reader)",
        )
        # The wave-4/5 transport re-export block stays untouched: exactly one
        # ImportFrom from worker_transport with its full alias set.
        transport_imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_transport"
        ]
        self.assertEqual(len(transport_imports), 1)
        self.assertEqual(len(transport_imports[0].names), WORKER_TRANSPORT_REEXPORT_COUNT)


class WorkerCrossingsNoRebindingTests(unittest.TestCase):
    def test_no_rebinding_of_state_names_anywhere(self) -> None:
        # (c) AST guard across ALL worker/*.py sources (cheap: the worker dir
        # is six files): the ONLY Store access to a non-rebinding state name
        # is its defining literal at module level of worker_crossings.py. Any
        # other assignment would fork mover/staying views of the counters.
        sources = sorted((ROOT / "worker").glob("*.py"))
        self.assertTrue(sources)
        for path in sources:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            defining_literals = {
                node.targets[0].id: node.lineno
                for node in tree.body
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in NON_REBINDING_STATE_NAMES
            }
            if path == CROSSINGS:
                self.assertEqual(
                    len(defining_literals),
                    len(NON_REBINDING_STATE_NAMES),
                    "every non-rebinding state literal must be defined in worker_crossings.py",
                )
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.For)):
                    targets = [node.target]
                elif isinstance(node, ast.With):
                    targets = [item.optional_vars for item in node.items if item.optional_vars is not None]
                elif isinstance(node, ast.NamedExpr):
                    targets = [node.target]
                else:
                    continue
                for target in targets:
                    if isinstance(target, (ast.Tuple, ast.List)):
                        names = [e for e in target.elts if isinstance(e, ast.Name)]
                    else:
                        names = [target] if isinstance(target, ast.Name) else []
                    for name in names:
                        if name.id not in NON_REBINDING_STATE_NAMES:
                            continue
                        self.assertEqual(
                            (path.name, name.lineno),
                            ("worker_crossings.py", defining_literals.get(name.id)),
                            f"{path.name}:{node.lineno} rebinds {name.id} "
                            "(only the defining literal in worker_crossings.py may assign it)",
                        )


class WorkerCrossingsRebinderCouplingTests(unittest.TestCase):
    def test_crossing_vlz_date_moves_with_its_sole_rebinder(self) -> None:
        # (d) _crossing_vlz_date REBINDS (daily reset), so it moved WITH its
        # sole rebinder under the same module top level. Pin the coupling:
        #   - exactly ONE Assign beyond the defining literal in the whole
        #     worker source set (all worker/*.py);
        #   - that assign's enclosing FunctionDef is maybe_reset_daily_crossings;
        #   - the ONLY ast.Global naming it sits in that same def;
        #   - maybe_reset_daily_crossings and the defining literal are both
        #     top-level in worker_crossings.py.
        sources = sorted((ROOT / "worker").glob("*.py"))
        assigns: list[tuple[Path, ast.Assign, str | None]] = []
        globals_stmts: list[tuple[Path, ast.Global, str | None]] = []

        def enclosing_function(node: ast.AST, tree: ast.Module) -> str | None:
            for top in tree.body:
                if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                    child is node for child in ast.walk(top)
                ):
                    return top.name
            return None

        for path in sources:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == "_crossing_vlz_date"
                ):
                    assigns.append((path, node, enclosing_function(node, tree)))
                elif isinstance(node, ast.Global) and "_crossing_vlz_date" in node.names:
                    globals_stmts.append((path, node, enclosing_function(node, tree)))

        self.assertEqual(
            len(assigns),
            2,
            f"_crossing_vlz_date must have exactly the defining literal + one rebinder, got {assigns}",
        )
        defining = [(p, n, fn) for p, n, fn in assigns if fn is None]
        rebinding = [(p, n, fn) for p, n, fn in assigns if fn is not None]
        self.assertEqual(len(defining), 1, "the defining literal must be top-level (module scope)")
        self.assertEqual(defining[0][0], CROSSINGS, "the defining literal must live in worker_crossings.py")
        self.assertEqual(len(rebinding), 1, "exactly one rebinding assign may exist")
        self.assertEqual(rebinding[0][2], "maybe_reset_daily_crossings", "the sole rebinder must be maybe_reset_daily_crossings")
        self.assertEqual(rebinding[0][0], CROSSINGS, "the rebinding assign must live in worker_crossings.py")
        self.assertEqual(
            len(globals_stmts),
            1,
            "the ONLY ast.Global naming _crossing_vlz_date must be unique across the worker sources",
        )
        self.assertEqual(globals_stmts[0][2], "maybe_reset_daily_crossings", "the ast.Global must sit inside maybe_reset_daily_crossings")
        self.assertEqual(globals_stmts[0][0], CROSSINGS, "the ast.Global must live in worker_crossings.py")
        # Both halves of the couple are top-level in the SAME module.
        crossings_tree = ast.parse(CROSSINGS.read_text(encoding="utf-8-sig"), filename=str(CROSSINGS))
        top_level_names = {
            node.name for node in crossings_tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("maybe_reset_daily_crossings", top_level_names)
        top_assign_names = {
            node.targets[0].id
            for node in crossings_tree.body
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        }
        self.assertIn("_crossing_vlz_date", top_assign_names)


class WorkerCrossingsIdentityTests(unittest.TestCase):
    def _import_worker_pair(self):
        # mock heavy deps so import succeeds without cv2/numpy/ultralytics/av
        for name in ["cv2", "numpy", "ultralytics", "av", "requests"]:
            if name not in sys.modules:
                sys.modules[name] = mock.MagicMock()
        sys.path.insert(0, str(ROOT / "worker"))
        try:
            import hls_motion_yolo_worker_events as worker

            import worker_crossings
        finally:
            if sys.path[0] == str(ROOT / "worker"):
                sys.path.remove(str(ROOT / "worker"))
        return worker, worker_crossings

    def test_crossing_defs_reexport_pristine_import_identity(self) -> None:
        # (e) Import-time re-export identity, proven in an ISOLATED subprocess
        # (mirrors the transport test's pristine probe): the worker's re-export
        # must bind the SAME function objects worker_crossings defines.
        probe = (
            "import sys\n"
            "from unittest import mock\n"
            "for name in ['cv2', 'numpy', 'ultralytics', 'av', 'requests']:\n"
            "    sys.modules.setdefault(name, mock.MagicMock())\n"
            "import hls_motion_yolo_worker_events as worker\n"
            "import worker_crossings\n"
            "names = (\n"
            + "".join(f'    "{name}",\n' for name in CROSSINGS_MOVED_DEFS)
            + ")\n"
            "for name in names:\n"
            "    assert getattr(worker, name) is getattr(worker_crossings, name), name\n"
            'assert "crossing_overlay_summary" in vars(worker), "globals()-guard regression"\n'
            "print('CROSSINGS-REEXPORT-IDENTITY-OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join([str(ROOT / "worker"), str(ROOT)]),
            },
            timeout=120,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"pristine crossings re-export identity failed:\n{result.stdout[-800:]}\n{result.stderr[-800:]}",
        )
        self.assertIn("CROSSINGS-REEXPORT-IDENTITY-OK", result.stdout)

    def test_crossing_defs_identity_and_globals_guard_in_process(self) -> None:
        # (e) Same identity pin in-process, plus the globals()-guard
        # regression: build_road_live_envelope keeps its
        # `"crossing_overlay_summary" in globals()` membership test — the
        # re-export must exist in the worker namespace or crossings would be
        # silently dropped from the road live envelope.
        worker, worker_crossings = self._import_worker_pair()
        for name in CROSSINGS_MOVED_DEFS:
            self.assertIs(
                getattr(worker, name),
                getattr(worker_crossings, name),
                f"{name} must be the same object in worker and worker_crossings",
            )
        self.assertIn(
            "crossing_overlay_summary",
            vars(worker),
            "globals()-guard regression: the re-export must expose crossing_overlay_summary",
        )
        worker_tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
        envelope = [
            node
            for node in worker_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "build_road_live_envelope"
        ]
        self.assertEqual(len(envelope), 1)
        guard_constants = [
            node.value
            for node in ast.walk(envelope[0])
            if isinstance(node, ast.Constant) and node.value == "crossing_overlay_summary"
        ]
        self.assertTrue(
            guard_constants,
            "build_road_live_envelope must keep the crossing_overlay_summary globals() membership guard",
        )


class CompatibilityGateFiveFileTests(unittest.TestCase):
    def test_gate_scans_five_worker_sources(self) -> None:
        # (f) wave-6 contract, extended by wave 7: the gate's MODULE_SOURCES
        # union is the six-file set (worker + media + render + transport +
        # crossings + live) and stays compatible with every required env
        # name resolved across it.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ubuntu_worker_compatibility",
            ROOT / "scripts" / "worker" / "check_ubuntu_compatibility.py",
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(len(module.MODULE_SOURCES), 6)
        self.assertTrue(all(path.is_file() for path in module.MODULE_SOURCES))
        findings = module.inspect_worker(list(module.MODULE_SOURCES))
        self.assertTrue(findings["compatible"], findings)
        self.assertEqual(findings["missing_required_environment_names"], [])
        self.assertEqual(
            sorted(findings["required_environment_names_present"]),
            sorted(module.REQUIRED_ENV_NAMES),
        )


if __name__ == "__main__":
    unittest.main()
