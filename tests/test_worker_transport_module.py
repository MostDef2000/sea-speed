"""Issue #397 wave-4 integrity: worker_transport split of the runtime worker.

Guards the invariants of the wave-4 move-only refactor:

(a) The worker re-exports the FULL moved-name set from
    worker/worker_transport.py at module level (exact-list check, fails on
    drift in either direction) — defs AND the three TTL caches, so main()
    global-name resolution, the ns-injection surface and cache object
    identity survive.
(b) Placement separation: the requests transport/posting layer is defined
    ONLY in worker/worker_transport.py (no duplicate defs in the worker/
    kernel/media/render modules).
(c) Import allowlist for worker_transport (transport analogue of the wave-2/3
    module allowlists): top-level imports limited to requests (REQUIRED —
    this module owns the network surface), json/time/pathlib, and the
    repo-pure siblings worker_kernel (env readers, API URL builders, ROI
    geometry scaling) and worker_media (_resolve_frame_size, the frame-size
    resolver the fetchers scale fetched geometry against). NO cv2/numpy/
    ultralytics/av and NO subprocess/socket.
(d) Cache object identity: worker.<cache> IS worker_transport.<cache> for
    every moved cache. The re-export via ImportFrom preserves the OBJECT, and
    every access anywhere is an in-place mutation (item assignment /
    dict.update / .get), so staying readers (crossing_overlay_summary reads
    _crossing_line_cache) observe mover mutations and vice versa.
(e) No rebinding of the moved caches anywhere (AST guard): the only Store
    access to a moved cache name is its defining literal in
    worker_transport.py. A rebinding (``_roi_cache = {...}`` or
    ``monkeypatch.setattr``-style rebinding at runtime) would fork mover and
    worker state — forbidden by the wave-4 contract; runtime tests must stub
    requests, not the cache objects.

Wave 5 extends the moved sets verbatim with the crossing/speed-config
posting surface (fetch_speed_config, post_crossing, flush_crossing_posts,
_post_live_envelope_sync) plus the two state objects that move under the
same identity contract (_speed_config_cache, _crossing_pending_posts —
staying mutators update_crossing_counts/reset_crossing_counts act through
the re-exported SAME list object).
"""

from __future__ import annotations

import ast
import os
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker" / "hls_motion_yolo_worker_events.py"
KERNEL = ROOT / "worker" / "worker_kernel.py"
MEDIA = ROOT / "worker" / "worker_media.py"
RENDER = ROOT / "worker" / "worker_render.py"
TRANSPORT = ROOT / "worker" / "worker_transport.py"
CROSSINGS = ROOT / "worker" / "worker_crossings.py"

# Exact moved-name set (keep in sync with the
# `from worker_transport import (...)` block — the tests below enforce BOTH
# directions of that sync). Wave 5 transferred the crossing/speed-config
# posting surface into this guard (contract transfer, work-order-sanctioned).
MOVED_TRANSPORT_DEFS = (
    "fetch_remote_roi",
    "post_state",
    "post_event",
    "post_passage",
    "fetch_speed_lines_config",
    "fetch_crossing_line_config",
    "fetch_speed_config",
    "post_crossing",
    "flush_crossing_posts",
    "_post_live_envelope_sync",
)
MOVED_TRANSPORT_CACHES = (
    "_roi_cache",
    "_speed_lines_cache",
    "_crossing_line_cache",
    "_speed_config_cache",
    "_crossing_pending_posts",
)
MOVED_TRANSPORT_NAMES = MOVED_TRANSPORT_DEFS + MOVED_TRANSPORT_CACHES

# Requests-adjacent runtime helpers that STAY in the worker
# (recorded STAYS): each is entangled with staying domain state, staying
# callers, or the live-publisher loop — outside the transport cut. Wave 5
# transferred fetch_speed_config/post_crossing/flush_crossing_posts/
# _post_live_envelope_sync to the moved set above (contract transfer).
# Wave 6 transferred update_crossing_counts/reset_crossing_counts/
# crossing_overlay_summary to the worker_crossings guard (contract transfer).
# Wave 7 transferred the whole live-publisher family (incl.
# _ensure_live_publisher) to the worker_live guard (contract transfer).
STAYING_IN_WORKER = (
    "road_roi_enabled",
    "detect_vehicles",
    "main",
)

# Top-level import allowlist for worker_transport: the network stack +
# stdlib payload/json/time/path needs + repo-pure siblings. NOT included:
# cv2/numpy (offline layers), ultralytics/av (model/media), subprocess/socket.
TRANSPORT_IMPORT_ALLOWLIST = frozenset(
    {
        "json",
        "pathlib",
        "requests",
        "time",
        "worker_kernel",
        "worker_media",
    }
)

FORBIDDEN_TRANSPORT_IMPORTS = frozenset({"cv2", "numpy", "ultralytics", "av", "subprocess", "socket"})


def _top_level_import_names(source: str) -> set[str]:
    tree = ast.parse(source, filename="worker_transport.py")
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class WorkerTransportImportAllowlistTests(unittest.TestCase):
    def test_transport_module_top_level_imports_within_allowlist(self) -> None:
        imported = _top_level_import_names(TRANSPORT.read_text(encoding="utf-8-sig"))
        self.assertEqual(
            sorted(imported - TRANSPORT_IMPORT_ALLOWLIST),
            [],
            "worker_transport gained a top-level import outside the transport allowlist",
        )
        # Double-armed: requests is REQUIRED at module level — this module
        # owns the network surface (post_*/fetch_* call requests directly).
        self.assertIn(
            "requests",
            imported,
            "transport layer must own the requests import (network surface)",
        )

    def test_transport_module_has_no_offline_layer_imports(self) -> None:
        # The transport layer is requests + stdlib payload plumbing only.
        # cv2/numpy (render/detection), ultralytics/av (model/media) and
        # subprocess/socket (spawn/raw sockets) at module level fail CI.
        tree = ast.parse(TRANSPORT.read_text(encoding="utf-8-sig"), filename=str(TRANSPORT))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(
                        alias.name.split(".")[0],
                        FORBIDDEN_TRANSPORT_IMPORTS,
                        f"worker_transport must not import {alias.name} at module level",
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(
                    node.module.split(".")[0],
                    FORBIDDEN_TRANSPORT_IMPORTS,
                    f"worker_transport must not import from {node.module} at module level",
                )


class WorkerTransportReExportSurfaceTests(unittest.TestCase):
    def _worker_transport_aliases(self) -> list[str]:
        tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
        imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_transport"
        ]
        self.assertEqual(
            len(imports),
            1,
            "worker must import the moved names from worker_transport exactly once",
        )
        return [alias.name for alias in imports[0].names]

    def test_worker_reexports_exact_moved_transport_name_set(self) -> None:
        # (a) exact-list check, both directions: defs AND moved caches.
        self.assertEqual(sorted(self._worker_transport_aliases()), sorted(MOVED_TRANSPORT_NAMES))

    def test_moved_names_defined_only_in_transport_and_staying_in_worker(self) -> None:
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

        transport_defs = top_defs(TRANSPORT)
        transport_assigns = top_assigns(TRANSPORT)
        worker_defs = top_defs(WORKER)
        worker_assigns = top_assigns(WORKER)
        kernel_defs = top_defs(KERNEL)
        media_defs = top_defs(MEDIA)
        render_defs = top_defs(RENDER)
        self.assertEqual(
            sorted(set(MOVED_TRANSPORT_DEFS) - transport_defs),
            [],
            "every transport function must be DEFINED in worker_transport.py",
        )
        self.assertEqual(
            sorted(set(MOVED_TRANSPORT_CACHES) - transport_assigns),
            [],
            "every moved TTL cache must be DEFINED in worker_transport.py",
        )
        for other_name, other_defs in (
            ("worker", worker_defs | worker_assigns),
            ("worker_kernel", kernel_defs),
            ("worker_media", media_defs),
            ("worker_render", render_defs),
        ):
            self.assertEqual(
                sorted(set(MOVED_TRANSPORT_NAMES) & other_defs),
                [],
                f"moved transport names must not keep duplicate definitions in {other_name}",
            )
        self.assertEqual(
            sorted(set(STAYING_IN_WORKER) - worker_defs),
            [],
            "requests-adjacent/domain-state helpers must stay in the worker",
        )
        self.assertEqual(
            sorted(set(STAYING_IN_WORKER) & (transport_defs | kernel_defs | media_defs | render_defs)),
            [],
            "worker-resident transport-adjacent helpers must not move this wave",
        )


class WorkerTransportCacheIdentityTests(unittest.TestCase):
    def _import_worker_pair(self):
        # mock heavy deps so import succeeds without cv2/numpy/ultralytics/av
        import sys

        for name in ["cv2", "numpy", "ultralytics", "av", "requests"]:
            if name not in sys.modules:
                sys.modules[name] = mock.MagicMock()
        sys.path.insert(0, str(ROOT / "worker"))
        try:
            import hls_motion_yolo_worker_events as worker

            import worker_transport
        finally:
            if sys.path[0] == str(ROOT / "worker"):
                sys.path.remove(str(ROOT / "worker"))
        return worker, worker_transport

    def test_moved_caches_are_the_same_objects(self) -> None:
        # (d) Object IDENTITY, not equality: the worker's re-export and the
        # transport module must expose ONE dict object per moved cache, so
        # in-place mutations from either side are visible everywhere.
        worker, worker_transport = self._import_worker_pair()
        for cache in MOVED_TRANSPORT_CACHES:
            self.assertIs(
                getattr(worker, cache),
                getattr(worker_transport, cache),
                f"{cache} must be the same object in worker and worker_transport",
            )

    def test_moved_fetchers_reexport_pristine_import_identity(self) -> None:
        # Import-time re-export identity, proven in an ISOLATED subprocess:
        # in a shared test process the integration layer deliberately rebinds
        # worker.post_state/post_event (ubuntu_worker_entrypoint.py:748-749 and
        # hls_motion_yolo_runtime.py:111 — the pre-existing composition seam),
        # so runtime function identity is NOT an invariant; the pristine
        # import-time binding to the defining module's objects IS.
        import subprocess
        import sys

        probe = (
            "import sys\n"
            "from unittest import mock\n"
            "for name in ['cv2', 'numpy', 'ultralytics', 'av', 'requests']:\n"
            "    sys.modules.setdefault(name, mock.MagicMock())\n"
            "import hls_motion_yolo_worker_events as worker\n"
            "import worker_transport\n"
            "names = (\n"
            + "".join(f'    "{name}",\n' for name in MOVED_TRANSPORT_DEFS)
            + ")\n"
            "for name in names:\n"
            "    assert getattr(worker, name) is getattr(worker_transport, name), name\n"
            "print('REEXPORT-IDENTITY-OK')\n"
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
            f"pristine re-export identity failed:\n{result.stdout[-800:]}\n{result.stderr[-800:]}",
        )
        self.assertIn("REEXPORT-IDENTITY-OK", result.stdout)


class WorkerTransportNoCacheRebindingTests(unittest.TestCase):
    def test_no_rebinding_of_moved_caches_anywhere(self) -> None:
        # (e) AST guard for the cache-identity contract: the ONLY Store access
        # to a moved cache name in worker+transport+crossings is its defining
        # literal at module level of worker_transport.py. Any other assignment
        # (rebinding) would fork the mover/worker views of the cache and break
        # coherence. Wave 6: the crossings module now hosts the former staying
        # mutators (.append/.clear on _crossing_pending_posts), so the scan
        # includes worker_crossings.py — it is a file where moved-cache names
        # appear (in-place use) and a future rebinding there must fail CI.
        for path in (WORKER, TRANSPORT, CROSSINGS):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            defining_literals = {
                node.targets[0].id: node.lineno
                for node in tree.body
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in MOVED_TRANSPORT_CACHES
            }
            if path == WORKER:
                self.assertEqual(defining_literals, {}, "moved caches must be defined only in worker_transport")
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
                        if name.id not in MOVED_TRANSPORT_CACHES:
                            continue
                        self.assertEqual(
                            (path.name, name.lineno),
                            ("worker_transport.py", defining_literals.get(name.id)),
                            f"{path.name}:{node.lineno} rebinds {name.id} "
                            "(only the defining literal in worker_transport.py may assign it)",
                        )


class CompatibilityGateModuleSourcesTests(unittest.TestCase):
    def test_gate_scans_module_sources(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ubuntu_worker_compatibility",
            ROOT / "scripts" / "worker" / "check_ubuntu_compatibility.py",
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(
            len(module.MODULE_SOURCES),
            6,
            "wave-7: the live module joins the gate's worker-source union",
        )
        self.assertTrue(all(path.is_file() for path in module.MODULE_SOURCES))
        findings = module.inspect_worker(list(module.MODULE_SOURCES))
        self.assertTrue(findings["compatible"], findings)
        self.assertEqual(findings["missing_required_environment_names"], [])
        # The six-file union must still surface every required env read,
        # including the SEA_SPEED_API_URL/SEA_SPEED_API_TOKEN reads that
        # moved into worker_transport with the post_* functions.
        self.assertEqual(
            sorted(findings["required_environment_names_present"]),
            sorted(module.REQUIRED_ENV_NAMES),
        )


if __name__ == "__main__":
    unittest.main()
