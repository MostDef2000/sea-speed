"""Issue #397 wave-8 integrity: worker_tracking split of the runtime worker.

Guards the invariants of the wave-8 move-only refactor (the tracking
cluster: 3 state literals + 8 defs moved verbatim from
hls_motion_yolo_worker_events.py into worker/worker_tracking.py):

(a) Import allowlist for worker_tracking (tracking analogue of the
    wave-2/3/4/6/7 module allowlists): top-level imports limited to stdlib
    time — the moved estimators timestamp samples with time.time()/monotonic
    — plus the repo-pure siblings worker_kernel (env_float, the DETECTION_*
    tunables) and worker_transport (fetch_speed_config,
    fetch_speed_lines_config, the calibration configs the estimators read).
    FORBIDDEN (derived from the moved bodies, none of them appear):
    cv2/numpy — the tracking math is pure Python over detection dicts and
    transport-provided configs; datetime — timestamps come from time, not
    datetime; threading/queue — the tracking cluster owns NO thread/queue
    lifecycle (unlike the wave-7 publisher); ultralytics/av/subprocess/
    socket — model/media/spawn/sockets stay in the worker shell; requests/
    json/pathlib/os — network and payload plumbing live in worker_transport/
    worker_kernel.
(b) Placement: the 8 tracking defs and 3 state literals are defined ONLY
    in worker/worker_tracking.py (no duplicate defs in the worker, live,
    transport or crossings modules), the worker re-exports exactly the 11
    moved names (3 state + 8 defs — the re-export preserves object identity
    for the per-track state dicts and the ns-injection/monkeypatch
    surface), and the wave-4/5 transport (15 names), wave-6 crossings
    (6 names) and wave-7 live (6 names) re-export blocks are untouched.
(c) Strict no-rebinding guard across the worker sources: for
    _speed_track/_track_states/_line_speed_state the ONLY Store access
    anywhere under worker/*.py is the defining literal in
    worker_tracking.py (every other access is an in-place mutation or a
    read of the same dicts — the same discipline as the wave-4/5/6/7 state
    contracts), and NO `global` statement anywhere names any of the 11
    moved names (3 state + 8 defs — defs are never rebound, and a `global`
    on the state names would license forking the shared dicts).
(d) Identity + re-export regression: a pristine subprocess import pins
    worker.<name> IS worker_tracking.<name> for all 11 moved names and
    "_speed_track"/"_track_states"/"_line_speed_state" in vars(worker) —
    the staying call sites (build_event's convert_px_s_to_kmh, the
    supervision main loop's update_speed_estimate/
    update_speed_lines_estimate/prune_track_states/water_event_candidates/
    track_event_posted/mark_track_event_posted) resolve the moved names
    through the worker's flat re-export, so losing the re-export would
    turn every speed estimate and track event into a NameError at runtime;
    the vars() membership pins (wave-6/7 globals-guard pattern) make
    exactly that failure loud in CI.
(e) Compatibility gate: MODULE_SOURCES is the seven-file union (worker +
    media + render + transport + crossings + live + tracking),
    worker_tracking present, union-compatible with every required env name
    still resolved across the union.
(f) draw_speed_lines_overlay placement: the overlay renderer STAYS in the
    worker (render surface, no production callers — it reads only
    fetch_speed_lines_config + cv2 and none of the moved names), so its
    def must exist in the worker file and must NOT have moved into
    worker_tracking.py.
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
TRACKING = ROOT / "worker" / "worker_tracking.py"
TRANSPORT = ROOT / "worker" / "worker_transport.py"
CROSSINGS = ROOT / "worker" / "worker_crossings.py"
LIVE = ROOT / "worker" / "worker_live.py"

# Exact moved-name sets for wave 8 (keep in sync with the
# `from worker_tracking import (...)` block — the tests below enforce BOTH
# directions of that sync; like wave 7 the state names ARE re-exported:
# the re-export preserves object identity and the monkeypatch surface).
TRACKING_MOVED_DEFS = (
    "convert_px_s_to_kmh",
    "detection_center_px",
    "mark_track_event_posted",
    "prune_track_states",
    "track_event_posted",
    "update_speed_estimate",
    "update_speed_lines_estimate",
    "water_event_candidates",
)
TRACKING_STATE_NAMES = (
    "_line_speed_state",
    "_speed_track",
    "_track_states",
)
# The full re-export set: 8 defs + 3 state names.
TRACKING_MOVED_NAMES = tuple(sorted(TRACKING_MOVED_DEFS + TRACKING_STATE_NAMES))
WORKER_TRANSPORT_REEXPORT_COUNT = 15  # wave-4 (9) + wave-5 (6); exact set pinned by tests/test_worker_transport_module.py
WORKER_CROSSINGS_REEXPORT_COUNT = 6  # wave-6; exact set pinned by tests/test_worker_crossings_module.py
WORKER_LIVE_REEXPORT_COUNT = 6  # wave-7; exact set pinned by tests/test_worker_live_module.py

# Top-level import allowlist for worker_tracking: stdlib time + the
# repo-pure siblings only. NOT included: cv2/numpy (the tracking math is
# pure Python), datetime (timestamps come from time), threading/queue (the
# tracking cluster owns no thread/queue lifecycle — that is the wave-7
# publisher), ultralytics/av (model/media), subprocess/socket (spawn/raw
# sockets), requests/json/pathlib/os (network and payload plumbing live in
# worker_transport/worker_kernel).
TRACKING_IMPORT_ALLOWLIST = frozenset({"time", "worker_kernel", "worker_transport"})

FORBIDDEN_TRACKING_IMPORTS = frozenset(
    {
        "cv2",
        "numpy",
        "datetime",
        "threading",
        "queue",
        "ultralytics",
        "av",
        "subprocess",
        "socket",
        "requests",
        "json",
        "pathlib",
        "os",
    }
)


def _top_level_import_names(source: str) -> set[str]:
    tree = ast.parse(source, filename="worker_tracking.py")
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class WorkerTrackingImportAllowlistTests(unittest.TestCase):
    def test_tracking_module_top_level_imports_within_allowlist(self) -> None:
        imported = _top_level_import_names(TRACKING.read_text(encoding="utf-8-sig"))
        self.assertEqual(
            sorted(imported - TRACKING_IMPORT_ALLOWLIST),
            [],
            "worker_tracking gained a top-level import outside the tracking allowlist",
        )
        # Double-armed: the two repo-pure siblings are REQUIRED — the moved
        # bodies resolve the env tunables from worker_kernel and the
        # calibration configs from worker_transport; stdlib time is required
        # for the sample timestamps.
        self.assertIn("worker_kernel", imported, "the tracking layer must reuse the kernel env reader")
        self.assertIn("worker_transport", imported, "the estimators must reuse the transport config fetchers")
        self.assertIn("time", imported, "the estimators must reuse stdlib time for sample timestamps")

    def test_tracking_module_has_no_offline_layer_imports(self) -> None:
        # The tracking cluster is pure-Python math over detection dicts and
        # transport-provided configs: cv2/numpy (render/detection arrays),
        # datetime (time formatting), threading/queue (no thread/queue
        # lifecycle here — that is the wave-7 publisher), ultralytics/av
        # (model/media), subprocess/socket (spawn/raw sockets) and requests/
        # json/pathlib/os at module level fail CI.
        tree = ast.parse(TRACKING.read_text(encoding="utf-8-sig"), filename=str(TRACKING))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(
                        alias.name.split(".")[0],
                        FORBIDDEN_TRACKING_IMPORTS,
                        f"worker_tracking must not import {alias.name} at module level",
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(
                    node.module.split(".")[0],
                    FORBIDDEN_TRACKING_IMPORTS,
                    f"worker_tracking must not import from {node.module} at module level",
                )


class WorkerTrackingPlacementTests(unittest.TestCase):
    def test_tracking_names_defined_only_in_tracking_module(self) -> None:
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

        tracking_defs = top_defs(TRACKING)
        tracking_assigns = top_assigns(TRACKING)
        worker_defs = top_defs(WORKER)
        transport_defs = top_defs(TRANSPORT)
        crossings_defs = top_defs(CROSSINGS)
        live_defs = top_defs(LIVE)
        self.assertEqual(
            sorted(set(TRACKING_MOVED_DEFS) - tracking_defs),
            [],
            "every tracking function must be DEFINED in worker_tracking.py",
        )
        self.assertEqual(
            sorted(set(TRACKING_STATE_NAMES) - tracking_assigns),
            [],
            "every per-track state literal must be DEFINED in worker_tracking.py",
        )
        self.assertEqual(
            sorted(set(TRACKING_MOVED_DEFS) & worker_defs),
            [],
            "moved tracking defs must not keep duplicate definitions in the worker",
        )
        self.assertEqual(
            sorted(set(TRACKING_MOVED_DEFS) & transport_defs),
            [],
            "moved tracking defs must not be defined in worker_transport.py",
        )
        self.assertEqual(
            sorted(set(TRACKING_MOVED_DEFS) & crossings_defs),
            [],
            "moved tracking defs must not be defined in worker_crossings.py",
        )
        self.assertEqual(
            sorted(set(TRACKING_MOVED_DEFS) & live_defs),
            [],
            "moved tracking defs must not be defined in worker_live.py",
        )

    def test_draw_speed_lines_overlay_stays_in_worker(self) -> None:
        # (f) the overlay renderer is a render surface with no production
        # callers (it reads only fetch_speed_lines_config + cv2 and none of
        # the moved names), so it STAYS in the worker: its def must exist in
        # the worker file and must NOT have moved into worker_tracking.py.
        def top_defs(path: Path) -> set[str]:
            return {
                node.name
                for node in ast.parse(path.read_text(encoding="utf-8-sig")).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }

        self.assertIn("draw_speed_lines_overlay", top_defs(WORKER), "the overlay renderer must stay in the worker")
        self.assertNotIn(
            "draw_speed_lines_overlay",
            top_defs(TRACKING),
            "the overlay renderer must not move into worker_tracking.py",
        )

    def test_worker_reexports_exact_tracking_name_set(self) -> None:
        # (b) exact-list check, both directions: the worker re-exports the 11
        # moved names via ONE flat sibling ImportFrom (defs + state names —
        # identity + monkeypatch surface).
        tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
        imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_tracking"
        ]
        self.assertEqual(
            len(imports),
            1,
            "worker must import the moved tracking names from worker_tracking exactly once",
        )
        aliases = [alias.name for alias in imports[0].names]
        self.assertEqual(sorted(aliases), sorted(TRACKING_MOVED_NAMES))
        # The wave-4/5 transport re-export block stays untouched: exactly one
        # ImportFrom from worker_transport with its full 15-name alias set.
        transport_imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_transport"
        ]
        self.assertEqual(len(transport_imports), 1)
        self.assertEqual(len(transport_imports[0].names), WORKER_TRANSPORT_REEXPORT_COUNT)
        # The wave-6 crossings re-export block stays untouched too: exactly
        # one ImportFrom from worker_crossings with its 6 def names.
        crossings_imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_crossings"
        ]
        self.assertEqual(len(crossings_imports), 1)
        self.assertEqual(len(crossings_imports[0].names), WORKER_CROSSINGS_REEXPORT_COUNT)
        # And the wave-7 live re-export block: exactly one ImportFrom from
        # worker_live with its 6 names.
        live_imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_live"
        ]
        self.assertEqual(len(live_imports), 1)
        self.assertEqual(len(live_imports[0].names), WORKER_LIVE_REEXPORT_COUNT)


class WorkerTrackingNoRebindingTests(unittest.TestCase):
    def test_no_rebinding_of_state_names_anywhere(self) -> None:
        # (c) AST guard across ALL worker/*.py sources (cheap: the worker dir
        # is eight harness files): the ONLY Store access to a per-track state
        # name is its defining literal at module level of worker_tracking.py.
        # Any other assignment would fork the state dicts seen by the
        # estimators and the staying callers (the same discipline as the
        # wave-4/5/6/7 state contracts). All three names are strictly
        # non-rebinding: the moved bodies mutate them in place
        # (dict[key] = ..., .clear(), .update()) and never rebind the name.
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
                and node.targets[0].id in TRACKING_STATE_NAMES
            }
            if path == TRACKING:
                self.assertEqual(
                    len(defining_literals),
                    len(TRACKING_STATE_NAMES),
                    "every per-track state literal must be defined in worker_tracking.py",
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
                        if name.id not in TRACKING_STATE_NAMES:
                            continue
                        self.assertEqual(
                            (path.name, name.lineno),
                            ("worker_tracking.py", defining_literals.get(name.id)),
                            f"{path.name}:{node.lineno} rebinds {name.id} "
                            "(only the defining literal in worker_tracking.py may assign it)",
                        )

    def test_no_global_statement_names_tracking_state_or_defs(self) -> None:
        # (c) no `global` statement anywhere under worker/*.py may name the
        # per-track state names or the moved defs: a `global` on the state
        # dicts would license rebinding (forking the shared objects), and
        # the tracking defs are never rebound. (The worker's pre-existing
        # `global _roi_processing_points` names a render-surface state that
        # stayed in the worker and is out of scope here.)
        sources = sorted((ROOT / "worker").glob("*.py"))
        protected = TRACKING_STATE_NAMES + TRACKING_MOVED_DEFS
        for path in sources:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Global):
                    offending = [name for name in node.names if name in protected]
                    self.assertEqual(
                        offending,
                        [],
                        f"{path.name}:{node.lineno} declares global {offending} "
                        "(tracking state/defs are never rebound via global statements)",
                    )


class WorkerTrackingIdentityTests(unittest.TestCase):
    def _import_worker_pair(self):
        # mock heavy deps so import succeeds without cv2/numpy/ultralytics/av
        for name in ["cv2", "numpy", "ultralytics", "av", "requests"]:
            if name not in sys.modules:
                sys.modules[name] = mock.MagicMock()
        sys.path.insert(0, str(ROOT / "worker"))
        try:
            import hls_motion_yolo_worker_events as worker

            import worker_tracking
        finally:
            if sys.path[0] == str(ROOT / "worker"):
                sys.path.remove(str(ROOT / "worker"))
        return worker, worker_tracking

    def test_tracking_names_reexport_pristine_import_identity(self) -> None:
        # (d) Import-time re-export identity, proven in an ISOLATED subprocess
        # (mirrors the crossings/live tests' pristine probe): the worker's
        # re-export must bind the SAME objects worker_tracking defines — the
        # 8 defs and the 3 per-track state dicts (the SAME dicts mutated by
        # the estimators and read by the staying callers).
        probe = (
            "import sys\n"
            "from unittest import mock\n"
            "for name in ['cv2', 'numpy', 'ultralytics', 'av', 'requests']:\n"
            "    sys.modules.setdefault(name, mock.MagicMock())\n"
            "import hls_motion_yolo_worker_events as worker\n"
            "import worker_tracking\n"
            "names = (\n"
            + "".join(f'    "{name}",\n' for name in TRACKING_MOVED_NAMES)
            + ")\n"
            "for name in names:\n"
            "    assert getattr(worker, name) is getattr(worker_tracking, name), name\n"
            'assert "_speed_track" in vars(worker), "globals()-guard regression"\n'
            'assert "_track_states" in vars(worker), "globals()-guard regression"\n'
            'assert "_line_speed_state" in vars(worker), "globals()-guard regression"\n'
            "print('TRACKING-REEXPORT-IDENTITY-OK')\n"
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
            f"pristine tracking re-export identity failed:\n{result.stdout[-800:]}\n{result.stderr[-800:]}",
        )
        self.assertIn("TRACKING-REEXPORT-IDENTITY-OK", result.stdout)

    def test_tracking_names_identity_and_reexport_in_process(self) -> None:
        # (d) Same identity pin in-process, plus the re-export regression:
        # the staying call sites (build_event's convert_px_s_to_kmh and the
        # supervision main loop's estimators/bookkeeping) resolve the moved
        # names through the worker's flat re-export —
        # "_speed_track"/"_track_states"/"_line_speed_state" in vars(worker)
        # is the wave-6/7 globals-guard pattern applied to the per-track
        # state.
        worker, worker_tracking = self._import_worker_pair()
        for name in TRACKING_MOVED_NAMES:
            self.assertIs(
                getattr(worker, name),
                getattr(worker_tracking, name),
                f"{name} must be the same object in worker and worker_tracking",
            )
        self.assertIn(
            "_speed_track",
            vars(worker),
            "re-export regression: the worker namespace must expose _speed_track",
        )
        self.assertIn(
            "_track_states",
            vars(worker),
            "re-export regression: the worker namespace must expose _track_states",
        )
        self.assertIn(
            "_line_speed_state",
            vars(worker),
            "re-export regression: the worker namespace must expose _line_speed_state",
        )
        worker_tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
        call_sites = [
            node
            for node in ast.walk(worker_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"update_speed_estimate", "update_speed_lines_estimate", "convert_px_s_to_kmh"}
        ]
        self.assertTrue(
            call_sites,
            "worker must keep its tracking call sites (the flat re-export feeds them)",
        )


class CompatibilityGateModuleSourcesTests(unittest.TestCase):
    def test_gate_scans_module_sources(self) -> None:
        # (e) wave-8 contract: the gate's MODULE_SOURCES union is the
        # seven-file set (worker + media + render + transport + crossings +
        # live + tracking) with worker_tracking.py present, and stays
        # compatible with every required env name resolved across it.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ubuntu_worker_compatibility",
            ROOT / "scripts" / "worker" / "check_ubuntu_compatibility.py",
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(len(module.MODULE_SOURCES), 7)
        self.assertIn(ROOT / "worker" / "worker_tracking.py", module.MODULE_SOURCES)
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
