"""Issue #397 wave-9 integrity: worker_roi split of the runtime worker.

Guards the invariants of the wave-9 move-only refactor (the ROI/analytics
cluster: 2 state literals + 9 defs moved verbatim from
hls_motion_yolo_worker_events.py into worker/worker_roi.py):

(a) Import allowlist for worker_roi (ROI analogue of the wave-2/3/4/6/7/8
    module allowlists): top-level imports limited to stdlib json/time —
    json serializes the water-recall diagnostic payload, time.monotonic
    gates its emission interval — plus cv2/numpy ALLOWED here (this module
    OWNS the polygon math and frame masking, unlike the pure-Python wave-8
    tracking sibling) and the repo-pure siblings worker_kernel (bbox_center,
    the env_* readers, water_recall_diagnostics_enabled) and
    worker_transport (fetch_remote_roi). FORBIDDEN: requests (the road-ROI
    fetch lives in worker_transport), ultralytics/av/subprocess/socket —
    model/media/spawn/sockets stay in the worker shell, threading/queue —
    the ROI cluster owns NO thread/queue lifecycle, datetime — monotonic
    gating comes from time, os/pathlib — plumbing lives in the siblings.
(b) Placement: the 9 ROI defs and 2 state literals are defined ONLY in
    worker/worker_roi.py (no duplicate defs/assigns in the worker or any
    sibling module), the worker re-exports exactly the 11 moved names
    (2 state + 9 defs — the re-export preserves object identity for the
    shared state and the monkeypatch surface), the wave-4/5 transport
    (15 names), wave-6 crossings (6), wave-7 live (6) and wave-8 tracking
    (11) re-export blocks are untouched, and worker_roi.py is present in
    the compatibility gate's MODULE_SOURCES union.
(c) Strict no-rebinding guard across the worker sources: for
    _WATER_RECALL_DIAGNOSTIC_STATE the ONLY Store access anywhere under
    worker/*.py is its defining literal in worker_roi.py (the emission
    gate mutates the dict IN PLACE — dict item assignment — and never
    rebinds the name; the same discipline as the wave-4/5/6/7/8 state
    contracts), and NO `global` statement anywhere names any of the 9
    moved defs or _WATER_RECALL_DIAGNOSTIC_STATE. (_roi_processing_points
    is deliberately absent from this guard: it REBINDS via `global` +
    assignment and is pinned by the rebinder-coupling test (d).)
(d) Rebinder coupling for _roi_processing_points (the wave-7 idiom): the
    state moved WITH its sole rebinder — exactly ONE `global` statement
    across the repo worker sources names it, ONLY inside
    prepare_roi_processing_frame; the sole non-literal Assign sits in the
    SAME def; rebinder and defining literal are both top-level in the
    SAME module (worker_roi.py — the couple is never split); PLUS the
    no-Load guard: NO Load-context Name read of _roi_processing_points
    exists outside worker_roi.py (the worker's re-export copy is a frozen
    import-time snapshot, so a worker-namespace reader would silently
    observe a stale value instead of the live points list).
(e) Identity + re-export regression: a pristine subprocess import pins
    worker.<name> IS worker_roi.<name> for all 11 moved names and
    "_roi_processing_points"/"_WATER_RECALL_DIAGNOSTIC_STATE" in
    vars(worker) — the staying call sites (select_profile_detections'
    filter_detections_by_roi and the supervision main loop's
    prepare_roi_processing_frame/filter_detections_by_roi/
    maybe_emit_water_recall_diagnostics) resolve the moved names through
    the worker's flat re-export, so losing the re-export would turn ROI
    masking and the water-recall diagnostics into NameErrors at runtime;
    the vars() membership pins (wave-6/7 globals-guard pattern) make
    exactly that failure loud in CI.
(f) Compatibility gate size: MODULE_SOURCES is the eight-file union
    (worker + media + render + transport + crossings + live + tracking +
    roi) — the wave-8 seven-file set plus worker_roi.py.
(g) STAYS placement pins: select_profile_detections and
    draw_speed_lines_overlay STAY in the worker (the profile selector
    calls the staying detect_vehicles/filter_detections_by_motion
    alongside the moved filter_detections_by_roi — moving it would create
    an import cycle; the overlay renderer is a render surface with no
    production callers), so both defs must exist in the worker file and
    must NOT have moved into worker_roi.py.
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
ROI = ROOT / "worker" / "worker_roi.py"
KERNEL = ROOT / "worker" / "worker_kernel.py"
MEDIA = ROOT / "worker" / "worker_media.py"
RENDER = ROOT / "worker" / "worker_render.py"
TRANSPORT = ROOT / "worker" / "worker_transport.py"
CROSSINGS = ROOT / "worker" / "worker_crossings.py"
LIVE = ROOT / "worker" / "worker_live.py"
TRACKING = ROOT / "worker" / "worker_tracking.py"

# Exact moved-name sets for wave 9 (keep in sync with the
# `from worker_roi import (...)` block — the tests below enforce BOTH
# directions of that sync; like waves 7/8 the state names ARE re-exported:
# the re-export preserves object identity and the monkeypatch surface).
ROI_MOVED_DEFS = (
    "detection_inside_road_roi",
    "draw_roi_polygon",
    "filter_detections_by_roi",
    "mask_frame_to_roi",
    "maybe_emit_water_recall_diagnostics",
    "parse_road_roi_polygon",
    "prepare_roi_processing_frame",
    "road_roi_enabled",
    "roi_processing_signature",
)
# _WATER_RECALL_DIAGNOSTIC_STATE is strictly non-rebinding (the emission
# gate mutates the dict in place); _roi_processing_points is the coupled
# rebinder pinned by the rebinder-coupling test.
ROI_NON_REBINDING_STATE_NAMES = (
    "_WATER_RECALL_DIAGNOSTIC_STATE",
)
ROI_REBINDING_STATE_NAMES = (
    "_roi_processing_points",
)
# The full re-export set: 9 defs + 2 state names.
ROI_MOVED_NAMES = tuple(
    sorted(ROI_MOVED_DEFS + ROI_NON_REBINDING_STATE_NAMES + ROI_REBINDING_STATE_NAMES)
)
WORKER_TRANSPORT_REEXPORT_COUNT = 15  # wave-4 (9) + wave-5 (6); exact set pinned by tests/test_worker_transport_module.py
WORKER_CROSSINGS_REEXPORT_COUNT = 6  # wave-6; exact set pinned by tests/test_worker_crossings_module.py
WORKER_LIVE_REEXPORT_COUNT = 6  # wave-7; exact set pinned by tests/test_worker_live_module.py
WORKER_TRACKING_REEXPORT_COUNT = 11  # wave-8 (3 state + 8 defs); exact set pinned by tests/test_worker_tracking_module.py

# Top-level import allowlist for worker_roi: stdlib json/time + the cv2/
# numpy frame-math stack + the repo-pure siblings. NOT included: requests
# (the road-ROI fetch lives in worker_transport), ultralytics/av (model/
# media), subprocess/socket (spawn/raw sockets), threading/queue (the ROI
# cluster owns no thread/queue lifecycle), datetime (monotonic gating comes
# from time), os/pathlib (plumbing lives in the siblings).
ROI_IMPORT_ALLOWLIST = frozenset(
    {
        "cv2",
        "json",
        "numpy",
        "time",
        "worker_kernel",
        "worker_transport",
    }
)

FORBIDDEN_ROI_IMPORTS = frozenset(
    {
        "av",
        "datetime",
        "os",
        "pathlib",
        "queue",
        "requests",
        "socket",
        "subprocess",
        "threading",
        "ultralytics",
    }
)


def _top_level_import_names(source: str) -> set[str]:
    tree = ast.parse(source, filename="worker_roi.py")
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class WorkerRoiImportAllowlistTests(unittest.TestCase):
    def test_roi_module_top_level_imports_within_allowlist(self) -> None:
        imported = _top_level_import_names(ROI.read_text(encoding="utf-8-sig"))
        self.assertEqual(
            sorted(imported - ROI_IMPORT_ALLOWLIST),
            [],
            "worker_roi gained a top-level import outside the ROI allowlist",
        )
        # Double-armed: every allowed family is REQUIRED — the moved bodies
        # serialize the diagnostic payload (json), gate it by monotonic time
        # (time), own the polygon math and frame masking (cv2/numpy), read
        # the env tunables from worker_kernel and the road ROI from
        # worker_transport.
        for required in ("cv2", "json", "numpy", "time", "worker_kernel", "worker_transport"):
            self.assertIn(
                required,
                imported,
                f"the ROI layer must import {required} at module level",
            )

    def test_roi_module_has_no_offline_layer_imports(self) -> None:
        # The ROI cluster fetches its polygon through worker_transport and
        # owns no lifecycle of its own: requests (network), ultralytics/av
        # (model/media), subprocess/socket (spawn/raw sockets), threading/
        # queue (no thread/queue lifecycle here), datetime (time formatting)
        # and os/pathlib (plumbing) at module level fail CI.
        tree = ast.parse(ROI.read_text(encoding="utf-8-sig"), filename=str(ROI))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(
                        alias.name.split(".")[0],
                        FORBIDDEN_ROI_IMPORTS,
                        f"worker_roi must not import {alias.name} at module level",
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(
                    node.module.split(".")[0],
                    FORBIDDEN_ROI_IMPORTS,
                    f"worker_roi must not import from {node.module} at module level",
                )


class WorkerRoiPlacementTests(unittest.TestCase):
    def test_roi_names_defined_only_in_roi_module(self) -> None:
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

        roi_defs = top_defs(ROI)
        roi_assigns = top_assigns(ROI)
        self.assertEqual(
            sorted(set(ROI_MOVED_DEFS) - roi_defs),
            [],
            "every ROI/analytics function must be DEFINED in worker_roi.py",
        )
        self.assertEqual(
            sorted(set(ROI_NON_REBINDING_STATE_NAMES + ROI_REBINDING_STATE_NAMES) - roi_assigns),
            [],
            "every moved state literal must be DEFINED in worker_roi.py",
        )
        others = {
            "the worker": WORKER,
            "worker_kernel": KERNEL,
            "worker_media": MEDIA,
            "worker_render": RENDER,
            "worker_transport": TRANSPORT,
            "worker_crossings": CROSSINGS,
            "worker_live": LIVE,
            "worker_tracking": TRACKING,
        }
        for other_name, other_path in others.items():
            self.assertEqual(
                sorted(set(ROI_MOVED_DEFS) & top_defs(other_path)),
                [],
                f"moved ROI defs must not keep duplicate definitions in {other_name}",
            )
            self.assertEqual(
                sorted(set(ROI_NON_REBINDING_STATE_NAMES + ROI_REBINDING_STATE_NAMES) & top_assigns(other_path)),
                [],
                f"moved ROI state literals must not keep duplicate assignments in {other_name}",
            )

    def test_worker_reexports_exact_roi_name_set(self) -> None:
        # (b) exact-list check, both directions: the worker re-exports the 11
        # moved names via ONE flat sibling ImportFrom (defs + state names —
        # identity + monkeypatch surface).
        tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
        imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_roi"
        ]
        self.assertEqual(
            len(imports),
            1,
            "worker must import the moved ROI names from worker_roi exactly once",
        )
        aliases = [alias.name for alias in imports[0].names]
        self.assertEqual(sorted(aliases), sorted(ROI_MOVED_NAMES))
        # The prior sibling re-export blocks stay untouched: exactly one
        # ImportFrom each with their full alias sets (the per-module exact
        # sets are pinned by their own module tests).
        transport_imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_transport"
        ]
        self.assertEqual(len(transport_imports), 1)
        self.assertEqual(len(transport_imports[0].names), WORKER_TRANSPORT_REEXPORT_COUNT)
        crossings_imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_crossings"
        ]
        self.assertEqual(len(crossings_imports), 1)
        self.assertEqual(len(crossings_imports[0].names), WORKER_CROSSINGS_REEXPORT_COUNT)
        live_imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_live"
        ]
        self.assertEqual(len(live_imports), 1)
        self.assertEqual(len(live_imports[0].names), WORKER_LIVE_REEXPORT_COUNT)
        tracking_imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_tracking"
        ]
        self.assertEqual(len(tracking_imports), 1)
        self.assertEqual(len(tracking_imports[0].names), WORKER_TRACKING_REEXPORT_COUNT)

    def test_select_profile_detections_and_overlay_stay_in_worker(self) -> None:
        # (g) the profile selector calls the staying detect_vehicles/
        # filter_detections_by_motion alongside the moved
        # filter_detections_by_roi (moving it would create an import cycle),
        # and the overlay renderer is a render surface with no production
        # callers — both STAY in the worker: their defs must exist in the
        # worker file and must NOT have moved into worker_roi.py.
        def top_defs(path: Path) -> set[str]:
            return {
                node.name
                for node in ast.parse(path.read_text(encoding="utf-8-sig")).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }

        for staying in ("select_profile_detections", "draw_speed_lines_overlay"):
            self.assertIn(staying, top_defs(WORKER), f"{staying} must stay in the worker")
            self.assertNotIn(
                staying,
                top_defs(ROI),
                f"{staying} must not move into worker_roi.py",
            )


class WorkerRoiNoRebindingTests(unittest.TestCase):
    def test_no_rebinding_of_diagnostic_state_anywhere(self) -> None:
        # (c) AST guard across ALL worker/*.py sources (cheap: the worker dir
        # is nine harness files): the ONLY Store access to
        # _WATER_RECALL_DIAGNOSTIC_STATE is its defining literal at module
        # level of worker_roi.py. Any other assignment would fork the state
        # dict seen by maybe_emit_water_recall_diagnostics and any staying
        # reader (the same discipline as the wave-4/5/6/7/8 state
        # contracts). The name is strictly non-rebinding: the moved body
        # mutates it in place (dict item assignment) and never rebinds it.
        # (_roi_processing_points is deliberately absent here: it REBINDS
        # via `global` + assignment and moved WITH its sole rebinder —
        # pinned by WorkerRoiRebinderCouplingTests.)
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
                and node.targets[0].id in ROI_NON_REBINDING_STATE_NAMES
            }
            if path == ROI:
                self.assertEqual(
                    len(defining_literals),
                    len(ROI_NON_REBINDING_STATE_NAMES),
                    "the diagnostic state literal must be defined in worker_roi.py",
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
                        if name.id not in ROI_NON_REBINDING_STATE_NAMES:
                            continue
                        self.assertEqual(
                            (path.name, name.lineno),
                            ("worker_roi.py", defining_literals.get(name.id)),
                            f"{path.name}:{node.lineno} rebinds {name.id} "
                            "(only the defining literal in worker_roi.py may assign it)",
                        )

    def test_no_global_statement_names_roi_defs_or_diagnostic_state(self) -> None:
        # (c) no `global` statement anywhere under worker/*.py may name the
        # moved ROI defs or the diagnostic state: a `global` on the state
        # dict would license rebinding (forking the shared object), and the
        # ROI defs are never rebound. (_roi_processing_points is
        # deliberately absent here — its single `global` inside
        # prepare_roi_processing_frame is pinned by the rebinder-coupling
        # test.)
        sources = sorted((ROOT / "worker").glob("*.py"))
        protected = ROI_MOVED_DEFS + ROI_NON_REBINDING_STATE_NAMES
        for path in sources:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Global):
                    offending = [name for name in node.names if name in protected]
                    self.assertEqual(
                        offending,
                        [],
                        f"{path.name}:{node.lineno} declares global {offending} "
                        "(ROI defs/diagnostic state are never rebound via global statements)",
                    )


class WorkerRoiRebinderCouplingTests(unittest.TestCase):
    def test_roi_processing_points_moves_with_its_sole_rebinder(self) -> None:
        # (d) _roi_processing_points REBINDS (prepare_roi_processing_frame
        # refreshes the last processed ROI point list on every frame), so it
        # moved WITH its sole rebinder under the same module top level. Pin
        # the coupling:
        #   - exactly ONE Assign beyond the defining literal in the whole
        #     worker source set (all worker/*.py);
        #   - that assign's enclosing FunctionDef is prepare_roi_processing_frame;
        #   - the ONLY ast.Global naming it sits in that same def;
        #   - prepare_roi_processing_frame and the defining literal are both
        #     top-level in worker_roi.py (global + rebinder in the SAME
        #     module — the couple is never split);
        #   - NO Load-context Name read of _roi_processing_points exists
        #     outside worker_roi.py (no worker-namespace reader: the
        #     re-export copy is a frozen import-time snapshot, so a reader
        #     would silently observe a stale points list — e.g. the None
        #     taken before the first processed frame — instead of the live
        #     value).
        sources = sorted((ROOT / "worker").glob("*.py"))
        assigns: list[tuple[Path, ast.Assign, str | None]] = []
        globals_stmts: list[tuple[Path, ast.Global, str | None]] = []
        worker_ns_reads: list[tuple[Path, ast.Name]] = []

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
                    and node.targets[0].id == "_roi_processing_points"
                ):
                    assigns.append((path, node, enclosing_function(node, tree)))
                elif isinstance(node, ast.Global) and "_roi_processing_points" in node.names:
                    globals_stmts.append((path, node, enclosing_function(node, tree)))
                elif (
                    isinstance(node, ast.Name)
                    and isinstance(node.ctx, ast.Load)
                    and node.id == "_roi_processing_points"
                    and path != ROI
                ):
                    worker_ns_reads.append((path, node))

        self.assertEqual(
            len(assigns),
            2,
            f"_roi_processing_points must have exactly the defining literal + one rebinder, got {assigns}",
        )
        defining = [(p, n, fn) for p, n, fn in assigns if fn is None]
        rebinding = [(p, n, fn) for p, n, fn in assigns if fn is not None]
        self.assertEqual(len(defining), 1, "the defining literal must be top-level (module scope)")
        self.assertEqual(defining[0][0], ROI, "the defining literal must live in worker_roi.py")
        self.assertEqual(len(rebinding), 1, "exactly one rebinding assign may exist")
        self.assertEqual(
            rebinding[0][2], "prepare_roi_processing_frame", "the sole rebinder must be prepare_roi_processing_frame"
        )
        self.assertEqual(rebinding[0][0], ROI, "the rebinding assign must live in worker_roi.py")
        self.assertEqual(
            len(globals_stmts),
            1,
            "the ONLY ast.Global naming _roi_processing_points must be unique across the worker sources",
        )
        self.assertEqual(
            globals_stmts[0][2],
            "prepare_roi_processing_frame",
            "the ast.Global must sit inside prepare_roi_processing_frame",
        )
        self.assertEqual(globals_stmts[0][0], ROI, "the ast.Global must live in worker_roi.py")
        # Both halves of the couple are top-level in the SAME module.
        roi_tree = ast.parse(ROI.read_text(encoding="utf-8-sig"), filename=str(ROI))
        top_level_names = {
            node.name for node in roi_tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("prepare_roi_processing_frame", top_level_names)
        top_assign_names = {
            node.targets[0].id
            for node in roi_tree.body
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        }
        self.assertIn("_roi_processing_points", top_assign_names)
        # No-Load guard: the rebinding name is scoped to worker_roi's
        # namespace — any Load-context read outside worker_roi.py would
        # silently observe the stale frozen snapshot (the worker-ns
        # re-export copy never rebinds), so no reader may exist. An ops
        # probe reading worker._roi_processing_points fails CI here.
        self.assertEqual(
            [(path.name, node.lineno) for path, node in worker_ns_reads],
            [],
            "Load-context reads of _roi_processing_points outside worker_roi.py "
            "(the rebinding name has no worker-namespace reader: a reader would "
            "silently see the stale frozen snapshot)",
        )


class WorkerRoiIdentityTests(unittest.TestCase):
    def _import_worker_pair(self):
        # mock heavy deps so import succeeds without cv2/numpy/ultralytics/av
        for name in ["cv2", "numpy", "ultralytics", "av", "requests"]:
            if name not in sys.modules:
                sys.modules[name] = mock.MagicMock()
        sys.path.insert(0, str(ROOT / "worker"))
        try:
            import hls_motion_yolo_worker_events as worker

            import worker_roi
        finally:
            if sys.path[0] == str(ROOT / "worker"):
                sys.path.remove(str(ROOT / "worker"))
        return worker, worker_roi

    def test_roi_names_reexport_pristine_import_identity(self) -> None:
        # (e) Import-time re-export identity, proven in an ISOLATED subprocess
        # (mirrors the tracking test's pristine probe): the worker's
        # re-export must bind the SAME objects worker_roi defines — the
        # 9 defs, the shared diagnostic state dict (the SAME dict mutated in
        # place by maybe_emit_water_recall_diagnostics) and the rebinding
        # _roi_processing_points snapshot.
        probe = (
            "import sys\n"
            "from unittest import mock\n"
            "for name in ['cv2', 'numpy', 'ultralytics', 'av', 'requests']:\n"
            "    sys.modules.setdefault(name, mock.MagicMock())\n"
            "import hls_motion_yolo_worker_events as worker\n"
            "import worker_roi\n"
            "names = (\n"
            + "".join(f'    "{name}",\n' for name in ROI_MOVED_NAMES)
            + ")\n"
            "for name in names:\n"
            "    assert getattr(worker, name) is getattr(worker_roi, name), name\n"
            'assert "_roi_processing_points" in vars(worker), "globals()-guard regression"\n'
            'assert "_WATER_RECALL_DIAGNOSTIC_STATE" in vars(worker), "globals()-guard regression"\n'
            "print('ROI-REEXPORT-IDENTITY-OK')\n"
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
            f"pristine ROI re-export identity failed:\n{result.stdout[-800:]}\n{result.stderr[-800:]}",
        )
        self.assertIn("ROI-REEXPORT-IDENTITY-OK", result.stdout)

    def test_roi_names_identity_and_reexport_in_process(self) -> None:
        # (e) Same identity pin in-process, plus the re-export regression:
        # the staying call sites (select_profile_detections'
        # filter_detections_by_roi and the supervision main loop's
        # prepare_roi_processing_frame/filter_detections_by_roi/
        # maybe_emit_water_recall_diagnostics) resolve the moved names
        # through the worker's flat re-export —
        # "_roi_processing_points"/"_WATER_RECALL_DIAGNOSTIC_STATE" in
        # vars(worker) is the wave-6/7 globals-guard pattern applied to the
        # ROI state.
        worker, worker_roi = self._import_worker_pair()
        for name in ROI_MOVED_NAMES:
            self.assertIs(
                getattr(worker, name),
                getattr(worker_roi, name),
                f"{name} must be the same object in worker and worker_roi",
            )
        self.assertIn(
            "_roi_processing_points",
            vars(worker),
            "re-export regression: the worker namespace must expose _roi_processing_points",
        )
        self.assertIn(
            "_WATER_RECALL_DIAGNOSTIC_STATE",
            vars(worker),
            "re-export regression: the worker namespace must expose _WATER_RECALL_DIAGNOSTIC_STATE",
        )
        worker_tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
        call_sites = [
            node
            for node in ast.walk(worker_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id
            in {"prepare_roi_processing_frame", "filter_detections_by_roi", "maybe_emit_water_recall_diagnostics"}
        ]
        self.assertTrue(
            call_sites,
            "worker must keep its ROI call sites (the flat re-export feeds them)",
        )


class CompatibilityGateModuleSourcesTests(unittest.TestCase):
    def test_gate_scans_module_sources(self) -> None:
        # (b)+(f) wave-9 contract: the gate's MODULE_SOURCES union is the
        # eight-file set (worker + media + render + transport + crossings +
        # live + tracking + roi) with worker_roi.py present, and stays
        # compatible with every required env name resolved across it.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ubuntu_worker_compatibility",
            ROOT / "scripts" / "worker" / "check_ubuntu_compatibility.py",
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # wave-9 contract transfer: the gate grew by worker_roi.py (8 files).
        self.assertEqual(len(module.MODULE_SOURCES), 8)
        self.assertIn(ROOT / "worker" / "worker_roi.py", module.MODULE_SOURCES)
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
