from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "worker/ubuntu_worker_entrypoint.py"
UNIT = ROOT / "deploy/worker/ubuntu/sea-speed-worker.service.template"
CORE_WORKER = ROOT / "worker/hls_motion_yolo_worker_events.py"


class WorkerRtspRuntimeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ENTRYPOINT.read_text(encoding="utf-8")
        self.unit = UNIT.read_text(encoding="utf-8")

    def test_ubuntu_production_rtsp_uses_ffmpeg_tcp_entrypoint(self) -> None:
        self.assertIn('"-rtsp_transport"', self.source)
        self.assertIn('"tcp"', self.source)
        self.assertIn('worker.start_media_reader = start_media_reader', self.source)
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
        self.assertNotIn('stderr=subprocess.PIPE', self.source)
        self.assertIn('stderr=subprocess.DEVNULL', self.source)

    def test_non_rtsp_inputs_keep_existing_worker_reader(self) -> None:
        self.assertIn('_ORIGINAL_START_MEDIA_READER', self.source)
        self.assertIn('return _ORIGINAL_START_MEDIA_READER(av_module=av_module)', self.source)
        core = CORE_WORKER.read_text(encoding="utf-8-sig")
        self.assertIn('def start_media_reader(av_module=None):', core)

    def test_calibration_rendering_remains_out_of_main_overlay_path(self) -> None:
        core = CORE_WORKER.read_text(encoding="utf-8-sig")
        start = core.index('def main():')
        main_source = core[start:]
        self.assertNotIn('draw_roi_polygon(overlay)', main_source)
        self.assertNotIn('draw_speed_lines_overlay(overlay)', main_source)
        self.assertIn('filter_detections_by_roi(detections)', main_source)
        self.assertIn('update_speed_lines_estimate(det)', main_source)


if __name__ == "__main__":
    unittest.main()
