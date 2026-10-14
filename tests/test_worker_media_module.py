"""Issue #397 wave-2 integrity: worker_media split of the runtime worker.

Guards the invariants of the wave-2 move-only refactor:

(a) The worker re-exports the FULL moved-name set from worker/worker_media.py
    at module level (exact-list check, fails on drift in either direction), so
    main() global-name resolution, the supervision seam
    (``worker.start_media_reader``) and the test monkeypatch surface survive.
(b) Placement separation: the media/reader layer is defined ONLY in
    worker/worker_media.py (no duplicate defs left in the worker, nothing
    media-shaped in the stdlib kernel).
(c) Import allowlist for worker_media (the media analogue of the wave-1
    stdlib-only probe): top-level imports are limited to the media stack
    (cv2/numpy/subprocess/os/time/pathlib/datetime/urllib.parse/typing) plus
    the repo-pure siblings worker_kernel and analytics_profiles. A future
    ultralytics/requests/av TOP-LEVEL import in the media module fails CI
    instead of bloating the layer. (``av`` stays a lazy import inside
    RtspFrameReader so the no-PyAV fallback path keeps its runtime error.)
(d) Compatibility-gate extension (RISK-002): the checker must scan BOTH
    worker sources — a required env-name call site satisfied from either file
    passes, a call site removed from BOTH fails, and a missing worker source
    file fails closed instead of silently narrowing the scan.
"""

from __future__ import annotations

import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker" / "hls_motion_yolo_worker_events.py"
KERNEL = ROOT / "worker" / "worker_kernel.py"
MEDIA = ROOT / "worker" / "worker_media.py"
CHECKER = ROOT / "scripts" / "worker" / "check_ubuntu_compatibility.py"

# Exact moved-name set for wave 2 (keep in sync with the
# `from worker_media import (...)` block — the test below enforces BOTH
# directions of that sync).
MOVED_MEDIA_NAMES = (
    "FFmpegFrameReader",
    "RtspFrameReader",
    "_frame_time_seconds",
    "_resolve_frame_size",
    "read_exact",
    "start_ffmpeg",
    "start_media_reader",
)

# Media-layer runtime helpers that stay in the worker (not in the kernel,
# not in the media module): the remaining this-wave placement contract.
# Wave 3 transferred draw_overlay/write_passage_snapshot/crop_sharpness to
# the worker_render guard (contract transfer, not a pin fix).
STAYING_IN_WORKER = (
    "detect_vehicles",
    "draw_roi_polygon",
    "draw_speed_lines_overlay",
    "fetch_remote_roi",
    "main",
)

# Top-level import allowlist for worker_media: the media stack + repo-pure
# siblings. NOT included: av (must stay lazy inside RtspFrameReader — the
# no-PyAV RuntimeError fallback), ultralytics, requests, fastapi and anything
# else that would bloat the media layer.
MEDIA_IMPORT_ALLOWLIST = frozenset(
    {
        "analytics_profiles",
        "cv2",
        "datetime",
        "numpy",
        "os",
        "pathlib",
        "subprocess",
        "time",
        "typing",
        "urllib.parse",
        "worker_kernel",
    }
)


def _top_level_import_names(source: str) -> set[str]:
    tree = ast.parse(source, filename="worker_media.py")
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class WorkerMediaImportAllowlistTests(unittest.TestCase):
    def test_media_module_top_level_imports_within_allowlist(self) -> None:
        # (c) media-layer bloat gate: any NEW top-level dependency (av,
        # ultralytics, requests, ...) must fail here, not silently enter the
        # media module.
        imported = _top_level_import_names(MEDIA.read_text(encoding="utf-8-sig"))
        self.assertEqual(
            sorted(imported - MEDIA_IMPORT_ALLOWLIST),
            [],
            "worker_media gained a top-level import outside the media allowlist",
        )
        self.assertIn("subprocess", imported, "media layer owns the ffmpeg process spawn")
        self.assertIn("numpy", imported, "media layer owns raw frame conversion")

    def test_av_import_stays_lazy_inside_rtsp_reader(self) -> None:
        # The PyAV fallback contract: `import av` must remain INSIDE
        # RtspFrameReader.__init__ (module-level hoist would break the
        # no-PyAV RuntimeError path and is caught by the allowlist test
        # above; this pins the lazy import still exists in the body).
        tree = ast.parse(MEDIA.read_text(encoding="utf-8-sig"), filename=str(MEDIA))
        rtsp = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "RtspFrameReader"
        )
        init = next(node for node in rtsp.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
        lazy_imports = [
            node
            for node in ast.walk(init)
            if isinstance(node, ast.Import) and any(alias.name == "av" for alias in node.names)
        ]
        self.assertEqual(len(lazy_imports), 1, "RtspFrameReader must lazily import av exactly once")


class WorkerMediaReExportSurfaceTests(unittest.TestCase):
    def _worker_media_aliases(self) -> list[str]:
        tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
        imports = [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "worker_media"
        ]
        self.assertEqual(
            len(imports),
            1,
            "worker must import the moved names from worker_media exactly once",
        )
        return [alias.name for alias in imports[0].names]

    def test_worker_reexports_exact_moved_media_name_set(self) -> None:
        # (a) exact-list check, both directions.
        self.assertEqual(sorted(self._worker_media_aliases()), sorted(MOVED_MEDIA_NAMES))

    def test_moved_names_defined_only_in_media_and_staying_in_worker(self) -> None:
        def top_defs(path: Path) -> set[str]:
            return {
                node.name
                for node in ast.parse(path.read_text(encoding="utf-8-sig")).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }

        media_defs, worker_defs, kernel_defs = top_defs(MEDIA), top_defs(WORKER), top_defs(KERNEL)
        self.assertEqual(
            sorted(set(MOVED_MEDIA_NAMES) - media_defs),
            [],
            "every media function/class must be DEFINED in worker_media.py",
        )
        self.assertEqual(
            sorted(set(MOVED_MEDIA_NAMES) & worker_defs),
            [],
            "moved media defs must not keep duplicate definitions in the worker",
        )
        self.assertEqual(
            sorted(set(MOVED_MEDIA_NAMES) & kernel_defs),
            [],
            "media defs must not leak into the stdlib-only kernel",
        )
        self.assertEqual(
            sorted(set(STAYING_IN_WORKER) - worker_defs),
            [],
            "remaining heavy-dependency helpers must stay in the worker",
        )
        self.assertEqual(
            sorted(set(STAYING_IN_WORKER) & (media_defs | kernel_defs)),
            [],
            "worker-resident helpers must not move into media/kernel this wave",
        )


def _load_checker():
    spec = importlib.util.spec_from_file_location("ubuntu_worker_compatibility", CHECKER)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load compatibility checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompatibilityGateMultiFileTests(unittest.TestCase):
    """RISK-002 negative tests: the extended gate must not go falsely green."""

    def test_single_worker_scan_is_no_longer_sufficient(self) -> None:
        # HLS_URL call sites now live ONLY in worker_media.py — scanning the
        # worker file alone must MISS them. This proves the extension does
        # real cross-file work instead of duplicating the old single-file scan.
        module = _load_checker()
        single = module.inspect_worker(WORKER)
        self.assertIn("HLS_URL", single["missing_required_environment_names"])
        self.assertFalse(single["compatible"], single)

    def test_union_across_both_files_satisfies_contract(self) -> None:
        module = _load_checker()
        findings = module.inspect_worker([WORKER, MEDIA])
        self.assertTrue(findings["compatible"], findings)
        self.assertEqual(findings["missing_required_environment_names"], [])
        self.assertTrue(findings["uses_subprocess"])
        self.assertTrue(findings["subprocess_uses_argument_list"])

    def test_gate_fails_when_required_env_call_site_removed_from_both_files(self) -> None:
        module = _load_checker()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worker_copy = tmp_path / "worker.py"
            media_copy = tmp_path / "worker_media.py"
            worker_source = WORKER.read_text(encoding="utf-8-sig")
            # Remove the HLS_URL call site from BOTH sources (it only exists
            # in worker_media today, but the contract is: removing it from
            # every file must fail the gate, from whichever file it lived in).
            worker_source = worker_source.replace('env_str("HLS_URL"', 'env_str("HLS_URL_GONE"')
            media_source = MEDIA.read_text(encoding="utf-8-sig").replace(
                'env_str("HLS_URL"', 'env_str("HLS_URL_GONE"'
            )
            worker_copy.write_text(worker_source, encoding="utf-8")
            media_copy.write_text(media_source, encoding="utf-8")
            findings = module.inspect_worker([worker_copy, media_copy])
        self.assertIn("HLS_URL", findings["missing_required_environment_names"])
        self.assertFalse(findings["compatible"], findings)

    def test_gate_fails_closed_when_worker_media_file_is_missing(self) -> None:
        module = _load_checker()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worker_copy = tmp_path / "worker.py"
            worker_copy.write_text(WORKER.read_text(encoding="utf-8-sig"), encoding="utf-8")
            with self.assertRaises(SystemExit):
                module.inspect_worker([worker_copy, tmp_path / "worker_media.py"])


if __name__ == "__main__":
    unittest.main()
