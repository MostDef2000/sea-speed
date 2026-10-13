from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "worker/ubuntu_worker_entrypoint.py"
UNIT = ROOT / "deploy/worker/ubuntu/sea-speed-worker.service.template"

try:
    from tests.support import worker_source
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import worker_source


def _entrypoint_tree() -> ast.Module:
    return ast.parse(ENTRYPOINT.read_text(encoding="utf-8"), filename=str(ENTRYPOINT))


def _rebinds_worker_attribute(tree: ast.Module, attribute: str) -> bool:
    """True when the entrypoint rebinds worker.<attribute> from a module-level name.

    AST equivalent of the `worker.<attribute> = <name>` supervision-seam text
    pin: the assignment target must be the worker module attribute and the
    value must be a plain name defined at the entrypoint's module level.
    """
    module_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "worker"
                and target.attr == attribute
            ):
                continue
            if isinstance(node.value, ast.Name) and node.value.id in module_names:
                return True
    return False


class WorkerRtspRuntimeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ENTRYPOINT.read_text(encoding="utf-8")
        self.unit = UNIT.read_text(encoding="utf-8")

    def test_ubuntu_production_rtsp_uses_ffmpeg_tcp_entrypoint(self) -> None:
        self.assertIn('"-rtsp_transport"', self.source)
        self.assertIn('"tcp"', self.source)
        # 398-wave-a: converted from source-text pin (was L21) — the
        # supervision seam is structural: the entrypoint must rebind
        # worker.start_media_reader from one of its own module-level names.
        self.assertTrue(
            _rebinds_worker_attribute(_entrypoint_tree(), "start_media_reader"),
            "entrypoint must rebind worker.start_media_reader from a module-level name",
        )
        self.assertIn('ubuntu_worker_entrypoint.py', self.unit)
        self.assertNotIn('import av', self.source)

    def test_rtsp_reads_are_bounded_and_restart_ffmpeg(self) -> None:
        self.assertIn('RTSP_FRAME_TIMEOUT_SEC', self.source)
        self.assertIn('RTSP_READER_MAX_RESTARTS', self.source)
        self.assertIn('RTSP_READER_RESTART_BACKOFF_SEC', self.source)
        self.assertIn('select.select(', self.source)
        self.assertIn('os.read(', self.source)
        self.assertIn('self._restart(', self.source)
        self.assertIn('exhausted restart budget', self.source)

    def test_media_secrets_are_not_written_to_worker_logs(self) -> None:
        self.assertIn('worker.safe_media_input_label(input_url)', self.source)
        self.assertNotIn('print(input_url)', self.source)
        # FFmpeg stderr is captured in-process and every drained line passes
        # mandatory redaction before it can reach the journal: ffmpeg error
        # text can embed the credential-bearing RTSP URL.
        self.assertIn('stderr=subprocess.PIPE', self.source)
        self.assertIn('def _redact_media_secrets', self.source)
        self.assertIn('tail.append(_redact_media_secrets(', self.source)
        self.assertIn('rtsp://[REDACTED]', self.source)
        self.assertNotIn('stderr=subprocess.DEVNULL', self.source)

    def test_non_rtsp_inputs_keep_existing_worker_reader(self) -> None:
        self.assertIn('_ORIGINAL_START_MEDIA_READER', self.source)
        self.assertIn('return _ORIGINAL_START_MEDIA_READER(av_module=av_module)', self.source)
        # 398-wave-a: converted from source-text pin (was L49-50) — the worker
        # module must keep exposing the start_media_reader seam: structurally
        # defined with an optional av_module parameter (AST, always-on), and
        # importable as a callable module attribute when cv2 is available
        # (behavioral, skips in envs without cv2).
        reader_node = worker_source.function_node("start_media_reader")
        parameter_names = [arg.arg for arg in reader_node.args.args]
        self.assertIn("av_module", parameter_names, "start_media_reader must keep the av_module seam parameter")
        # Pair every parameter with its own default from the right (same
        # reversed-zip pattern as crossing_summary in test_line_crossing.py):
        # av_module's ALIGNED default must be None, regardless of how many
        # other optional parameters precede it.
        aligned = [
            (arg, default)
            for arg, default in zip(
                reversed(reader_node.args.args),
                reversed([*reader_node.args.defaults]),
            )
        ]
        av_defaults = [
            default for parameter, default in aligned if parameter.arg == "av_module"
        ]
        self.assertEqual(
            len(av_defaults),
            1,
            "av_module must stay optional (exactly one aligned None default)",
        )
        self.assertTrue(
            isinstance(av_defaults[0], ast.Constant) and av_defaults[0].value is None,
            "av_module default must stay None",
        )
        try:
            import sys

            sys.path.insert(0, str(ROOT / "worker"))
            import hls_motion_yolo_worker_events as worker_module  # type: ignore

            self.assertTrue(callable(worker_module.start_media_reader), "worker module must expose the start_media_reader seam")
        except ModuleNotFoundError:
            self.skipTest("cv2 not available in local env")

    def test_calibration_rendering_remains_out_of_main_overlay_path(self) -> None:
        # 398-wave-a: converted from source-text pin (was L52-59) — inside the
        # live main() flow: ROI/speed-line calibration rendering must stay out
        # of the main overlay path, while the ROI final guard and the
        # per-detection speed estimate stay wired in.
        main_node = worker_source.function_node("main")
        self.assertEqual(
            worker_source.calls_named(main_node, "draw_roi_polygon"),
            [],
            "draw_roi_polygon(overlay) must stay out of main()",
        )
        self.assertEqual(
            worker_source.calls_named(main_node, "draw_speed_lines_overlay"),
            [],
            "draw_speed_lines_overlay(overlay) must stay out of main()",
        )
        self.assertTrue(
            worker_source.contains_expr(main_node, "filter_detections_by_roi(detections)"),
            "main() must keep the final ROI guard",
        )
        self.assertTrue(
            worker_source.contains_expr(main_node, "update_speed_lines_estimate(det)"),
            "main() must keep the per-detection speed estimate",
        )


if __name__ == "__main__":
    unittest.main()
