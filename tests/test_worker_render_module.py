"""Issue #397 wave-3 integrity: worker_render split of the runtime worker.

Guards the invariants of the wave-3 move-only refactor:

(a) The worker re-exports the FULL moved-name set from worker/worker_render.py
    at module level (exact-list check, fails on drift in either direction), so
    main() global-name resolution and the monkeypatch surface survive.
(b) Placement separation: the cv2 render/snapshot layer is defined ONLY in
    worker/worker_render.py (no duplicate defs in the worker/kernel/media).
(c) Import allowlist for worker_render (render analogue of the wave-2 media
    allowlist): top-level imports limited to cv2/numpy/os/time/datetime/
    pathlib/typing plus the repo-pure siblings worker_kernel and
    analytics_profiles. NO network imports (requests/ultralytics/av) — the
    render layer is offline by contract. cv2 is imported DELIBERATELY at
    module level (this is the render module — no lazy-cv2 pin needed).
(d) The wave-3 STAYS are recorded: draw_roi_polygon and draw_speed_lines_
    overlay remain in the worker (each calls a staying requests-entangled
    worker function — parse_road_roi_polygon/fetch_speed_lines_config — and
    move-only forbids body edits that would be needed to break the cycle);
    crossing_overlay_summary stays (crossing-domain state reader of
    _crossing_counts/_crossings_by_class/_crossing_line_cache, no cv2, and
    dynamically referenced via the `globals()` guard in
    build_road_live_envelope — moving it would change that call site's
    semantics space rather than preserve it). Wave 6 transferred
    crossing_overlay_summary to the worker_crossings guard (contract
    transfer) — its `globals()`-guard call site in build_road_live_envelope
    still resolves through the worker re-export (pinned by
    tests/test_worker_crossings_module.py).
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker" / "hls_motion_yolo_worker_events.py"
KERNEL = ROOT / "worker" / "worker_kernel.py"
MEDIA = ROOT / "worker" / "worker_media.py"
RENDER = ROOT / "worker" / "worker_render.py"

# Exact moved-name set for wave 3 (keep in sync with the
# `from worker_render import (...)` block — the test below enforces BOTH
# directions of that sync).
MOVED_RENDER_NAMES = (
    "crop_sharpness",
    "draw_overlay",
    "write_passage_snapshot",
)

# Render-domain helpers that STAY in the worker this wave (recorded STAYS):
# each calls a staying requests-entangled worker function, or reads
# crossing-domain mutable state — outside the render module's import
# allowlist by construction.
# Render-domain helpers that STAY in the worker this wave (recorded STAYS):
# each calls a staying requests-entangled worker function, or reads
# crossing-domain mutable state — outside the render module's import
# allowlist by construction. Wave 4 transferred fetch_remote_roi/post_state/
# post_event/post_passage to the worker_transport guard (contract transfer).
# Wave 6 transferred crossing_overlay_summary to the worker_crossings guard
# (contract transfer).
STAYING_IN_WORKER = (
    "draw_roi_polygon",
    "draw_speed_lines_overlay",
    "detect_vehicles",
    "main",
)

# Top-level import allowlist for worker_render: the render stack + repo-pure
# siblings. NOT included: requests, ultralytics, av, subprocess (offline
# render layer — spawning and network stay in media/worker).
RENDER_IMPORT_ALLOWLIST = frozenset(
    {
        "analytics_profiles",
        "cv2",
        "datetime",
        "numpy",
        "os",
        "pathlib",
        "time",
        "typing",
        "worker_kernel",
    }
)

FORBIDDEN_RENDER_IMPORTS = frozenset({"requests", "ultralytics", "av", "subprocess", "socket"})


def _top_level_import_names(source: str) -> set[str]:
    tree = ast.parse(source, filename="worker_render.py")
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class WorkerRenderImportAllowlistTests(unittest.TestCase):
    def test_render_module_top_level_imports_within_allowlist(self) -> None:
        imported = _top_level_import_names(RENDER.read_text(encoding="utf-8-sig"))
        self.assertEqual(
            sorted(imported - RENDER_IMPORT_ALLOWLIST),
            [],
            "worker_render gained a top-level import outside the render allowlist",
        )
        self.assertIn("cv2", imported, "render layer owns the cv2 drawing/writing surface")

    def test_render_module_has_no_network_imports(self) -> None:
        # The render layer is OFFLINE: drawing and snapshot writing only.
        # Any network import (requests/ultralytics/av) or process spawn
        # (subprocess) at module level must fail CI.
        tree = ast.parse(RENDER.read_text(encoding="utf-8-sig"), filename=str(RENDER))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(
                        alias.name.split(".")[0],
                        FORBIDDEN_RENDER_IMPORTS,
                        f"worker_render must not import {alias.name} at module level",
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(
                    node.module.split(".")[0],
                    FORBIDDEN_RENDER_IMPORTS,
                    f"worker_render must not import from {node.module} at module level",
                )


class WorkerRenderReExportSurfaceTests(unittest.TestCase):
    def _worker_render_aliases(self) -> list[str]:
        tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
        imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_render"
        ]
        self.assertEqual(
            len(imports),
            1,
            "worker must import the moved names from worker_render exactly once",
        )
        return [alias.name for alias in imports[0].names]

    def test_worker_reexports_exact_moved_render_name_set(self) -> None:
        # (a) exact-list check, both directions.
        self.assertEqual(sorted(self._worker_render_aliases()), sorted(MOVED_RENDER_NAMES))

    def test_moved_names_defined_only_in_render_and_staying_in_worker(self) -> None:
        def top_defs(path: Path) -> set[str]:
            return {
                node.name
                for node in ast.parse(path.read_text(encoding="utf-8-sig")).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }

        render_defs = top_defs(RENDER)
        worker_defs = top_defs(WORKER)
        kernel_defs = top_defs(KERNEL)
        media_defs = top_defs(MEDIA)
        self.assertEqual(
            sorted(set(MOVED_RENDER_NAMES) - render_defs),
            [],
            "every render function must be DEFINED in worker_render.py",
        )
        for other_name, other_defs in (
            ("worker", worker_defs),
            ("worker_kernel", kernel_defs),
            ("worker_media", media_defs),
        ):
            self.assertEqual(
                sorted(set(MOVED_RENDER_NAMES) & other_defs),
                [],
                f"moved render defs must not keep duplicate definitions in {other_name}",
            )
        self.assertEqual(
            sorted(set(STAYING_IN_WORKER) - worker_defs),
            [],
            "network-entangled/domain-state render helpers must stay in the worker",
        )
        self.assertEqual(
            sorted(set(STAYING_IN_WORKER) & (render_defs | kernel_defs | media_defs)),
            [],
            "worker-resident render-adjacent helpers must not move this wave",
        )


class CompatibilityGateThreeFileTests(unittest.TestCase):
    def test_gate_scans_all_worker_sources(self) -> None:
        # Wave-3 contract, extended by the wave-4 transport module: the gate
        # must scan at least the three-file wave-3 union (worker + media +
        # render) and stay compatible. The exact four-file count is pinned by
        # tests/test_worker_transport_module.py (wave-4 contract transfer).
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ubuntu_worker_compatibility",
            ROOT / "scripts" / "worker" / "check_ubuntu_compatibility.py",
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertGreaterEqual(len(module.MODULE_SOURCES), 3)
        self.assertTrue(all(path.is_file() for path in module.MODULE_SOURCES))
        findings = module.inspect_worker(list(module.MODULE_SOURCES))
        self.assertTrue(findings["compatible"], findings)
        self.assertEqual(findings["missing_required_environment_names"], [])


if __name__ == "__main__":
    unittest.main()
