"""Issue #397 wave-7 integrity: worker_live split of the runtime worker.

Guards the invariants of the wave-7 move-only refactor (the live-publisher
family: 3 state literals + 3 defs moved verbatim from
hls_motion_yolo_worker_events.py into worker/worker_live.py):

(a) Import allowlist for worker_live (live analogue of the wave-2/3/4/6
    module allowlists): top-level imports limited to queue and threading —
    this module OWNS the publish-thread lifecycle (the bounded queue, its
    lock and the daemon thread are created, started and drained here and
    nowhere else) — plus the repo-pure siblings worker_kernel (env_str) and
    worker_transport (_post_live_envelope_sync, the loop's network body
    from wave 5). NO offline-layer imports (cv2/numpy/datetime/
    ultralytics/av/subprocess/socket) and NO requests/json/pathlib/os —
    network I/O stays in worker_transport; the publisher only hands
    envelopes to the queue.
(b) Placement separation: the 3 publisher defs and 3 state literals are
    defined ONLY in worker/worker_live.py (no duplicate defs in the
    worker, transport or crossings modules), the worker re-exports exactly
    the 6 moved names (unlike wave 6 the state names ARE re-exported: the
    re-export preserves object identity for the queue/lock/thread and the
    ns-injection/monkeypatch surface), and the wave-4/5 transport (15
    names) and wave-6 crossings (6 names) re-export blocks are untouched.
(c) Strict no-rebinding guard across the worker sources: for
    _LIVE_PUBLISH_QUEUE/_LIVE_PUBLISH_LOCK the ONLY Store access anywhere
    under worker/*.py is the defining literal in worker_live.py (every
    other access is a method call on the same Queue/Lock objects — the
    same discipline as the wave-4/5/6 state contracts), and NO `global`
    statement anywhere names _LIVE_PUBLISH_QUEUE/_LIVE_PUBLISH_LOCK/
    _live_publisher_loop/post_live_envelope.
(d) Rebinder coupling for _LIVE_PUBLISH_THREAD: the state literal moved
    WITH its sole rebinder — exactly ONE Assign beyond the defining
    literal exists in the whole worker source set, it sits inside
    _ensure_live_publisher, the ONLY `global` statement naming it sits in
    that same def, and both the def and the literal are top-level in
    worker_live.py (global + rebinder in the SAME module). The pair must
    never be split (a rebinding name cannot move away from its rebinder).
    Coupled no-Load guard: NO Load-context Name read of
    _LIVE_PUBLISH_THREAD exists outside worker_live.py across the worker
    sources — the rebinding name has no worker-namespace reader (the
    worker-ns re-export copy is a frozen import-time snapshot, so a
    reader would silently observe the stale snapshot; an ops probe
    reading worker._LIVE_PUBLISH_THREAD must fail CI instead).
(e) Identity + re-export regression: a pristine subprocess import pins
    worker.<name> IS worker_live.<name> for all 6 moved names and
    "_LIVE_PUBLISH_QUEUE"/"_LIVE_PUBLISH_THREAD" in vars(worker) — the
    staying post_live_envelope(env_live) call sites in the supervision
    main loop resolve the moved def through the worker's flat re-export,
    so losing the re-export would turn every road/water live publish into
    a NameError at runtime; the vars() membership pins (wave-6
    globals-guard pattern) make exactly that failure loud in CI.
(f) Compatibility gate: MODULE_SOURCES is the eight-file union (worker +
    media + render + transport + crossings + live + tracking + roi), worker_live
    present, union-compatible with every required env name still resolved
    across the union.
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
LIVE = ROOT / "worker" / "worker_live.py"
TRANSPORT = ROOT / "worker" / "worker_transport.py"
CROSSINGS = ROOT / "worker" / "worker_crossings.py"

# Exact moved-name sets for wave 7 (keep in sync with the
# `from worker_live import (...)` block — the tests below enforce BOTH
# directions of that sync; unlike wave 6 the state names ARE re-exported:
# the re-export preserves object identity and the monkeypatch surface).
LIVE_MOVED_DEFS = (
    "_ensure_live_publisher",
    "_live_publisher_loop",
    "post_live_envelope",
)
LIVE_STATE_NAMES = (
    "_LIVE_PUBLISH_LOCK",
    "_LIVE_PUBLISH_QUEUE",
    "_LIVE_PUBLISH_THREAD",
)
# The full re-export set: 3 defs + 3 state names.
LIVE_MOVED_NAMES = tuple(sorted(LIVE_MOVED_DEFS + LIVE_STATE_NAMES))
# The strictly non-rebinding state names (pin (c)); _LIVE_PUBLISH_THREAD is
# covered separately by the rebinder-coupling pin (d).
NON_REBINDING_STATE_NAMES = (
    "_LIVE_PUBLISH_LOCK",
    "_LIVE_PUBLISH_QUEUE",
)
WORKER_TRANSPORT_REEXPORT_COUNT = 15  # wave-4 (9) + wave-5 (6); exact set pinned by tests/test_worker_transport_module.py
WORKER_CROSSINGS_REEXPORT_COUNT = 6  # wave-6; exact set pinned by tests/test_worker_crossings_module.py

# Top-level import allowlist for worker_live: stdlib queue/threading + the
# repo-pure siblings only. NOT included: cv2/numpy/datetime (render/
# detection/time formatting), ultralytics/av (model/media), subprocess/
# socket (spawn/raw sockets), requests/json/pathlib/os (network and payload
# plumbing live in worker_transport/worker_kernel).
LIVE_IMPORT_ALLOWLIST = frozenset({"queue", "threading", "worker_kernel", "worker_transport"})

FORBIDDEN_LIVE_IMPORTS = frozenset(
    {
        "cv2",
        "numpy",
        "datetime",
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
    tree = ast.parse(source, filename="worker_live.py")
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class WorkerLiveImportAllowlistTests(unittest.TestCase):
    def test_live_module_top_level_imports_within_allowlist(self) -> None:
        imported = _top_level_import_names(LIVE.read_text(encoding="utf-8-sig"))
        self.assertEqual(
            sorted(imported - LIVE_IMPORT_ALLOWLIST),
            [],
            "worker_live gained a top-level import outside the live allowlist",
        )
        # Double-armed: the two repo-pure siblings are REQUIRED — the moved
        # bodies resolve the env readers from worker_kernel and the loop's
        # network body from worker_transport.
        self.assertIn("worker_kernel", imported, "the live layer must reuse the kernel env reader")
        self.assertIn("worker_transport", imported, "the publisher loop must reuse the transport sync poster")

    def test_live_module_has_no_offline_layer_imports(self) -> None:
        # The live module is a thread/queue shim over the transport: cv2/
        # numpy (render/detection), datetime (time formatting), ultralytics/
        # av (model/media), subprocess/socket (spawn/raw sockets) and
        # requests/json/pathlib/os at module level fail CI.
        tree = ast.parse(LIVE.read_text(encoding="utf-8-sig"), filename=str(LIVE))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(
                        alias.name.split(".")[0],
                        FORBIDDEN_LIVE_IMPORTS,
                        f"worker_live must not import {alias.name} at module level",
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(
                    node.module.split(".")[0],
                    FORBIDDEN_LIVE_IMPORTS,
                    f"worker_live must not import from {node.module} at module level",
                )


class WorkerLivePlacementTests(unittest.TestCase):
    def test_live_names_defined_only_in_live_module(self) -> None:
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

        live_defs = top_defs(LIVE)
        live_assigns = top_assigns(LIVE)
        worker_defs = top_defs(WORKER)
        transport_defs = top_defs(TRANSPORT)
        crossings_defs = top_defs(CROSSINGS)
        self.assertEqual(
            sorted(set(LIVE_MOVED_DEFS) - live_defs),
            [],
            "every live-publisher function must be DEFINED in worker_live.py",
        )
        self.assertEqual(
            sorted(set(LIVE_STATE_NAMES) - live_assigns),
            [],
            "every publish-thread state literal must be DEFINED in worker_live.py",
        )
        self.assertEqual(
            sorted(set(LIVE_MOVED_DEFS) & worker_defs),
            [],
            "moved live-publisher defs must not keep duplicate definitions in the worker",
        )
        self.assertEqual(
            sorted(set(LIVE_MOVED_DEFS) & transport_defs),
            [],
            "moved live-publisher defs must not be defined in worker_transport.py",
        )
        self.assertEqual(
            sorted(set(LIVE_MOVED_DEFS) & crossings_defs),
            [],
            "moved live-publisher defs must not be defined in worker_crossings.py",
        )
        # The loop's network body is transport-OWNED (wave 5): worker_live
        # IMPORTS _post_live_envelope_sync, it never redefines it.
        self.assertNotIn("_post_live_envelope_sync", live_defs, "the sync poster stays owned by worker_transport")
        self.assertIn("_post_live_envelope_sync", transport_defs)

    def test_worker_reexports_exact_live_name_set(self) -> None:
        # (b) exact-list check, both directions: the worker re-exports the 6
        # moved names via ONE flat sibling ImportFrom (defs + state names —
        # identity + monkeypatch surface).
        tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
        imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_live"
        ]
        self.assertEqual(
            len(imports),
            1,
            "worker must import the moved live-publisher names from worker_live exactly once",
        )
        aliases = [alias.name for alias in imports[0].names]
        self.assertEqual(sorted(aliases), sorted(LIVE_MOVED_NAMES))
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


class WorkerLiveNoRebindingTests(unittest.TestCase):
    def test_no_rebinding_of_state_names_anywhere(self) -> None:
        # (c) AST guard across ALL worker/*.py sources (cheap: the worker dir
        # is eight files): the ONLY Store access to a non-rebinding state
        # name is its defining literal at module level of worker_live.py. Any
        # other assignment would fork the publish queue/lock seen by the
        # publisher loop and the staying callers (the same discipline as the
        # wave-4/5 cache contract and the wave-6 state contract).
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
            if path == LIVE:
                self.assertEqual(
                    len(defining_literals),
                    len(NON_REBINDING_STATE_NAMES),
                    "every non-rebinding state literal must be defined in worker_live.py",
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
                            ("worker_live.py", defining_literals.get(name.id)),
                            f"{path.name}:{node.lineno} rebinds {name.id} "
                            "(only the defining literal in worker_live.py may assign it)",
                        )

    def test_no_global_statement_names_live_state_or_defs(self) -> None:
        # (c) no `global` statement anywhere under worker/*.py may name the
        # non-rebinding state names or the moved defs: a `global` on the
        # queue/lock would license rebinding (forking the shared objects),
        # and the publisher defs are never rebound. (_LIVE_PUBLISH_THREAD is
        # deliberately absent here — its single `global` inside
        # _ensure_live_publisher is pinned by the rebinder-coupling test.)
        sources = sorted((ROOT / "worker").glob("*.py"))
        protected = NON_REBINDING_STATE_NAMES + LIVE_MOVED_DEFS
        for path in sources:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Global):
                    offending = [name for name in node.names if name in protected]
                    self.assertEqual(
                        offending,
                        [],
                        f"{path.name}:{node.lineno} declares global {offending} "
                        "(live state/defs are never rebound via global statements)",
                    )


class WorkerLiveRebinderCouplingTests(unittest.TestCase):
    def test_live_publish_thread_moves_with_its_sole_rebinder(self) -> None:
        # (d) _LIVE_PUBLISH_THREAD REBINDS (the daemon thread is (re)created
        # on the next publish), so it moved WITH its sole rebinder under the
        # same module top level. Pin the coupling:
        #   - exactly ONE Assign beyond the defining literal in the whole
        #     worker source set (all worker/*.py);
        #   - that assign's enclosing FunctionDef is _ensure_live_publisher;
        #   - the ONLY ast.Global naming it sits in that same def;
        #   - _ensure_live_publisher and the defining literal are both
        #     top-level in worker_live.py (global + rebinder in the SAME
        #     module — the pair is never split);
        #   - NO Load-context Name read of _LIVE_PUBLISH_THREAD exists
        #     outside worker_live.py (no worker-namespace reader: the
        #     re-export copy is a frozen import-time snapshot, so a reader
        #     would silently see the stale snapshot — e.g. the None taken
        #     before the first publish — instead of the live thread).
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
                    and node.targets[0].id == "_LIVE_PUBLISH_THREAD"
                ):
                    assigns.append((path, node, enclosing_function(node, tree)))
                elif isinstance(node, ast.Global) and "_LIVE_PUBLISH_THREAD" in node.names:
                    globals_stmts.append((path, node, enclosing_function(node, tree)))
                elif (
                    isinstance(node, ast.Name)
                    and isinstance(node.ctx, ast.Load)
                    and node.id == "_LIVE_PUBLISH_THREAD"
                    and path != LIVE
                ):
                    worker_ns_reads.append((path, node))

        self.assertEqual(
            len(assigns),
            2,
            f"_LIVE_PUBLISH_THREAD must have exactly the defining literal + one rebinder, got {assigns}",
        )
        defining = [(p, n, fn) for p, n, fn in assigns if fn is None]
        rebinding = [(p, n, fn) for p, n, fn in assigns if fn is not None]
        self.assertEqual(len(defining), 1, "the defining literal must be top-level (module scope)")
        self.assertEqual(defining[0][0], LIVE, "the defining literal must live in worker_live.py")
        self.assertEqual(len(rebinding), 1, "exactly one rebinding assign may exist")
        self.assertEqual(rebinding[0][2], "_ensure_live_publisher", "the sole rebinder must be _ensure_live_publisher")
        self.assertEqual(rebinding[0][0], LIVE, "the rebinding assign must live in worker_live.py")
        self.assertEqual(
            len(globals_stmts),
            1,
            "the ONLY ast.Global naming _LIVE_PUBLISH_THREAD must be unique across the worker sources",
        )
        self.assertEqual(globals_stmts[0][2], "_ensure_live_publisher", "the ast.Global must sit inside _ensure_live_publisher")
        self.assertEqual(globals_stmts[0][0], LIVE, "the ast.Global must live in worker_live.py")
        # Both halves of the couple are top-level in the SAME module.
        live_tree = ast.parse(LIVE.read_text(encoding="utf-8-sig"), filename=str(LIVE))
        top_level_names = {
            node.name for node in live_tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("_ensure_live_publisher", top_level_names)
        top_assign_names = {
            node.targets[0].id
            for node in live_tree.body
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        }
        self.assertIn("_LIVE_PUBLISH_THREAD", top_assign_names)
        # No-Load guard: the rebinding name is scoped to worker_live's
        # namespace — any Load-context read outside worker_live.py would
        # silently observe the stale frozen snapshot (the worker-ns
        # re-export copy never rebinds), so no reader may exist. An ops
        # probe reading worker._LIVE_PUBLISH_THREAD fails CI here.
        self.assertEqual(
            [(path.name, node.lineno) for path, node in worker_ns_reads],
            [],
            "Load-context reads of _LIVE_PUBLISH_THREAD outside worker_live.py "
            "(the rebinding name has no worker-namespace reader: a reader would "
            "silently see the stale frozen snapshot)",
        )


class WorkerLiveIdentityTests(unittest.TestCase):
    def _import_worker_pair(self):
        # mock heavy deps so import succeeds without cv2/numpy/ultralytics/av
        for name in ["cv2", "numpy", "ultralytics", "av", "requests"]:
            if name not in sys.modules:
                sys.modules[name] = mock.MagicMock()
        sys.path.insert(0, str(ROOT / "worker"))
        try:
            import hls_motion_yolo_worker_events as worker

            import worker_live
        finally:
            if sys.path[0] == str(ROOT / "worker"):
                sys.path.remove(str(ROOT / "worker"))
        return worker, worker_live

    def test_live_names_reexport_pristine_import_identity(self) -> None:
        # (e) Import-time re-export identity, proven in an ISOLATED subprocess
        # (mirrors the crossings test's pristine probe): the worker's re-export
        # must bind the SAME objects worker_live defines — the 3 defs and the
        # 3 publish-thread state objects (ONE queue/lock/thread shared by the
        # worker call sites and the publisher loop).
        probe = (
            "import sys\n"
            "from unittest import mock\n"
            "for name in ['cv2', 'numpy', 'ultralytics', 'av', 'requests']:\n"
            "    sys.modules.setdefault(name, mock.MagicMock())\n"
            "import hls_motion_yolo_worker_events as worker\n"
            "import worker_live\n"
            "names = (\n"
            + "".join(f'    "{name}",\n' for name in LIVE_MOVED_NAMES)
            + ")\n"
            "for name in names:\n"
            "    assert getattr(worker, name) is getattr(worker_live, name), name\n"
            'assert "_LIVE_PUBLISH_QUEUE" in vars(worker), "globals()-guard regression"\n'
            'assert "_LIVE_PUBLISH_THREAD" in vars(worker), "globals()-guard regression"\n'
            "print('LIVE-REEXPORT-IDENTITY-OK')\n"
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
            f"pristine live re-export identity failed:\n{result.stdout[-800:]}\n{result.stderr[-800:]}",
        )
        self.assertIn("LIVE-REEXPORT-IDENTITY-OK", result.stdout)

    def test_live_names_identity_and_reexport_in_process(self) -> None:
        # (e) Same identity pin in-process, plus the re-export regression:
        # the staying post_live_envelope(env_live) call sites in main()
        # resolve the moved def through the worker's flat re-export —
        # "_LIVE_PUBLISH_QUEUE"/"_LIVE_PUBLISH_THREAD" in vars(worker) is the
        # wave-6 globals-guard pattern applied to the publish-thread state.
        worker, worker_live = self._import_worker_pair()
        for name in LIVE_MOVED_NAMES:
            self.assertIs(
                getattr(worker, name),
                getattr(worker_live, name),
                f"{name} must be the same object in worker and worker_live",
            )
        self.assertIn(
            "_LIVE_PUBLISH_QUEUE",
            vars(worker),
            "re-export regression: the worker namespace must expose _LIVE_PUBLISH_QUEUE",
        )
        self.assertIn(
            "_LIVE_PUBLISH_THREAD",
            vars(worker),
            "re-export regression: the worker namespace must expose _LIVE_PUBLISH_THREAD",
        )
        worker_tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
        call_sites = [
            node
            for node in ast.walk(worker_tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "post_live_envelope"
        ]
        self.assertTrue(
            call_sites,
            "worker must keep its post_live_envelope call sites (the flat re-export feeds them)",
        )


class CompatibilityGateModuleSourcesTests(unittest.TestCase):
    def test_gate_scans_module_sources(self) -> None:
        # (f) wave-7 contract, extended by waves 8-9: the gate's MODULE_SOURCES
        # union is the eight-file set (worker + media + render + transport +
        # crossings + live + tracking + roi) with worker_live.py present, and
        # stays compatible with every required env name resolved across it.
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
        self.assertIn(ROOT / "worker" / "worker_live.py", module.MODULE_SOURCES)
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
