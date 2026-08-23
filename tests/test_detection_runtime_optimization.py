from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))


class DetectionPerformanceTests(unittest.TestCase):
    def test_tracker_window_and_p95(self):
        from detection_performance import PerformanceTracker

        tr = PerformanceTracker(window_sec=5.0)
        # simulate 10 frames in quick succession
        for i in range(10):
            tr.record_frame(ingest_mono=float(i) * 0.1, inference_ms=50.0 + i, frame_age_ms=10.0)
        self.assertGreater(tr.effective_fps(), 5.0)
        self.assertGreater(tr.p95_inference_ms(), 50)
        self.assertAlmostEqual(tr.avg_frame_age_ms(), 10.0)
        snap = tr.snapshot()
        self.assertIn("effective_fps", snap)
        self.assertIn("p95_inference_ms", snap)
        self.assertIn("dropped", snap)

    def test_parity_tolerance(self):
        from detection_performance import PerformanceTracker

        self.assertTrue(PerformanceTracker.check_parity_within_tolerance([10, 10, 20, 20], [11, 10, 20, 21], tol=1))
        self.assertFalse(PerformanceTracker.check_parity_within_tolerance([10, 10, 20, 20], [12, 10, 20, 20], tol=1))

    def test_dropped_count(self):
        from detection_performance import PerformanceTracker

        tr = PerformanceTracker()
        tr.record_dropped(3)
        self.assertEqual(tr.snapshot()["dropped"], 3)


class ProfileFpsHdTests(unittest.TestCase):
    def test_profiles_are_10fps_hd(self):
        import analytics_profiles as profiles

        w = profiles.get_profile("water-v1")
        r = profiles.get_profile("road-v1")
        self.assertEqual(w.sample_fps, 10.0)
        self.assertEqual(r.sample_fps, 10.0)
        self.assertEqual(w.frame_width, 1920)
        self.assertEqual(r.frame_height, 1080)

    def test_defaults_propagate(self):
        import analytics_profiles as profiles

        d = profiles.profile_defaults("water-v1")
        self.assertEqual(d["SAMPLE_FPS"], 10.0)
        self.assertEqual(d["FRAME_WIDTH"], 1920)


class MotionGateTests(unittest.TestCase):
    def _load_worker_with_mocks(self):
        # mock heavy deps so import succeeds without cv2/numpy/ultralytics/av
        for name in ["cv2", "numpy", "ultralytics", "av", "requests"]:
            if name not in sys.modules:
                sys.modules[name] = mock.MagicMock()
        # ensure submodule ultralytics.YOLO mock
        if "ultralytics" in sys.modules:
            sys.modules["ultralytics"].YOLO = mock.MagicMock()
        sys.path.insert(0, str(WORKER))
        import hls_motion_yolo_worker_events as worker
        return worker

    def test_always_on_flag(self):
        worker = self._load_worker_with_mocks()

        with mock.patch.dict(os.environ, {"MOTION_GATE_MODE": "always_on"}):
            self.assertTrue(worker.is_motion_gate_always_on())
        with mock.patch.dict(os.environ, {"MOTION_GATE_MODE": "gated"}):
            self.assertFalse(worker.is_motion_gate_always_on())
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(worker.is_motion_gate_always_on())

    def test_yolo_half_and_classes_flags(self):
        worker = self._load_worker_with_mocks()

        with mock.patch.dict(os.environ, {"YOLO_HALF": "1"}):
            self.assertTrue(worker.is_yolo_half_enabled())
        with mock.patch.dict(os.environ, {"YOLO_HALF": "0"}):
            self.assertFalse(worker.is_yolo_half_enabled())
        with mock.patch.dict(os.environ, {"YOLO_CLASSES_FILTER": "1"}):
            self.assertTrue(worker.is_yolo_classes_filter_enabled())
        with mock.patch.dict(os.environ, {"YOLO_CLASSES": "car,person"}):
            self.assertTrue(worker.is_yolo_classes_filter_enabled())


class ConfigGenerationTests(unittest.TestCase):
    def test_no_704_fallback_in_config(self):
        text = (ROOT / "deploy/worker/ubuntu/configure-analytics-profiles.py").read_text()
        # The fixed generator must resolve HD and not default to 704 for road
        self.assertIn('"1920"', text)
        self.assertIn('"1080"', text)
        # ensure fallback logic forces HD
        self.assertIn("LATEST_FRAME_BOUNDED", text)
        self.assertIn("YOLO_HALF", text)
        self.assertIn("MOTION_GATE_MODE", text)

    def test_road_env_example_is_hd_10fps(self):
        text = (ROOT / "deploy/worker/ubuntu/road-worker.env.example").read_text()
        self.assertIn("FRAME_WIDTH=1920", text)
        self.assertIn("FRAME_HEIGHT=1080", text)
        self.assertIn("SAMPLE_FPS=10", text)
        self.assertIn("YOLO_HALF=1", text)
        self.assertIn("MOTION_GATE_MODE=gated", text)


class BoundedQueueAndPublishingTests(unittest.TestCase):
    def _load_entry_with_mocks(self):
        for name in ["numpy", "cv2", "ultralytics", "av", "requests"]:
            if name not in sys.modules:
                sys.modules[name] = mock.MagicMock()
        sys.path.insert(0, str(WORKER))
        import ubuntu_worker_entrypoint as entry
        return entry

    def test_latest_frame_bounded_enabled(self):
        entry = self._load_entry_with_mocks()

        with mock.patch.dict(os.environ, {"LATEST_FRAME_BOUNDED": "1"}):
            self.assertTrue(entry.latest_frame_bounded_enabled())
        with mock.patch.dict(os.environ, {"LATEST_FRAME_BOUNDED": "0"}):
            self.assertFalse(entry.latest_frame_bounded_enabled())

    def test_publish_queue_coalescing(self):
        # just ensure post_state/post_event do not block without ffmpeg/model
        entry = self._load_entry_with_mocks()

        # mock original to avoid HTTP
        with mock.patch.dict(os.environ, {"SEA_SPEED_SOURCE_COMMIT": "a" * 40}), mock.patch.object(
            entry, "_ORIGINAL_POST_STATE", return_value=True
        ), mock.patch.object(entry, "_ORIGINAL_POST_EVENT", return_value=True):
            entry._publish_queue.queue.clear()
            ok = entry.post_state({"a": 1}, Path("/tmp/test.jpg"))
            self.assertTrue(ok)
            ok2 = entry.post_event({"b": 2}, Path("/tmp/test2.jpg"))
            self.assertTrue(ok2)
            # queue should have 2 items
            self.assertGreaterEqual(entry._publish_queue.qsize(), 1)
            # cleanup queue for other tests
            try:
                while not entry._publish_queue.empty():
                    entry._publish_queue.get_nowait()
                    entry._publish_queue.task_done()
            except Exception:
                pass


class ObservedRunnerTelemetryTests(unittest.TestCase):
    def test_observed_parses_telemetry(self):
        text = (ROOT / "deploy/worker/ubuntu/observed-worker-runner.py").read_text()
        self.assertIn("last_inference_ms", text)
        self.assertIn("inference_ms=", text)
        self.assertIn("dropped_frames", text)


if __name__ == "__main__":
    unittest.main()
