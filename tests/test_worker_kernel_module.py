"""Issue #397 wave-1 integrity: worker_kernel split of the runtime worker.

Guards the two invariants of the wave-1 move-only refactor:

(a) worker/worker_kernel.py is STDLIB-ONLY — importable in an isolated
    subprocess (``python3 -I``: no user site, no PYTHONPATH) with only the
    worker/ directory on sys.path, i.e. with NO cv2/numpy/requests/ultralytics.
(b) hls_motion_yolo_worker_events.py re-exports the FULL moved-name set at
    module level (exact-list check, fails on drift in either direction), so
    main() global-name resolution and the test monkeypatch surface survive
    the decomposition.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker" / "hls_motion_yolo_worker_events.py"
KERNEL = ROOT / "worker" / "worker_kernel.py"

# Exact moved-name set for wave 1 (keep in sync with the
# `from worker_kernel import (...)` block — the test below enforces BOTH
# directions of that sync).
MOVED_NAMES = (
    "bbox_center",
    "crossed_line",
    "env_float",
    "env_int",
    "env_str",
    "format_detection_label",
    "get_crossing_line_url",
    "get_roi_url",
    "get_speed_config_url",
    "get_speed_lines_url",
    "is_motion_gate_always_on",
    "is_yolo_classes_filter_enabled",
    "is_yolo_half_enabled",
    "media_basic_auth_for_input",
    "now_iso",
    "overlay_label_opacity",
    "roi_basic_auth",
    "safe_media_input_label",
    "side_of_line",
    "sign_with_deadzone",
    "water_recall_diagnostics_enabled",
    "_media_input_scheme",
    "_maybe_scale_legacy_absolute",
    "_scale_norm_points",
)

# Names the kernel must NOT gain: heavy-dependency runtime helpers stay in the
# worker or the media module (wave 2 moved start_ffmpeg/start_media_reader/
# _resolve_frame_size to worker_media.py; wave 3 moved draw_overlay/
# write_passage_snapshot/crop_sharpness to worker_render.py — their placement
# is guarded by the wave-2/3 module tests).
STAYING_NAMES = (
    "detect_vehicles",
    "main",
    "build_event",
    "fetch_remote_roi",
)


class WorkerKernelStdlibOnlyTests(unittest.TestCase):
    def test_kernel_imports_in_isolated_subprocess(self) -> None:
        # (a) stdlib-only proof: -I ignores PYTHONPATH/user-site; the only
        # path added is worker/, so any third-party import would fail.
        probe = "import sys; sys.path.insert(0, sys.argv[1]); import worker_kernel; print('ok')"
        result = subprocess.run(
            [sys.executable, "-I", "-c", probe, str(ROOT / "worker")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"worker_kernel must import without third-party deps; stderr: {result.stderr}",
        )
        self.assertIn("ok", result.stdout)


class WorkerReExportSurfaceTests(unittest.TestCase):
    def _worker_reexport_aliases(self) -> list[str]:
        tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
        imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_kernel"
        ]
        self.assertEqual(
            len(imports),
            1,
            "worker must import the moved names from worker_kernel exactly once",
        )
        return [alias.name for alias in imports[0].names]

    def test_worker_reexports_exact_moved_name_set(self) -> None:
        # (b) exact-list check: any drift (missing re-export breaks main()'s
        # global-name resolution and the monkeypatch surface; extra re-export
        # means a function moved without updating the contract) fails here.
        self.assertEqual(sorted(self._worker_reexport_aliases()), sorted(MOVED_NAMES))

    def test_moved_names_stay_absent_from_worker_and_staying_from_kernel(self) -> None:
        kernel_defs = {
            node.name
            for node in ast.parse(KERNEL.read_text(encoding="utf-8-sig")).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        worker_defs = {
            node.name
            for node in ast.parse(WORKER.read_text(encoding="utf-8-sig")).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertEqual(
            sorted(set(MOVED_NAMES) - kernel_defs),
            [],
            "every moved function must be DEFINED in worker_kernel.py",
        )
        self.assertEqual(
            sorted(set(MOVED_NAMES) & worker_defs),
            [],
            "moved functions must not keep duplicate definitions in the worker",
        )
        self.assertEqual(
            sorted(set(STAYING_NAMES) & kernel_defs),
            [],
            "heavy-dependency runtime helpers must stay in the worker this wave",
        )
        self.assertEqual(
            sorted(set(STAYING_NAMES) - worker_defs),
            [],
            "staying functions must remain defined in the worker",
        )


if __name__ == "__main__":
    unittest.main()
