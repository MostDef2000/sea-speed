from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_MAIN = ROOT / "api/app/main.py"
spec = importlib.util.spec_from_file_location("roi_api", API_MAIN)
assert spec and spec.loader

class RoiNormalizationTests(unittest.TestCase):
    def _import_app(self):
        # load API helpers via isolated spec without polluting real api.app.main
        mods = ["fastapi", "fastapi.staticfiles", "fastapi.responses", "PIL", "PIL.Image"]
        patch_dict = {m: mock.MagicMock() for m in mods if m not in sys.modules}
        with mock.patch.dict(sys.modules, patch_dict):
            with mock.patch.object(Path, "mkdir", lambda *a, **k: None):
                import sqlite3 as _sq
                with mock.patch.object(_sq, "connect", lambda *a, **k: mock.MagicMock()):
                    spec = importlib.util.spec_from_file_location("roi_api_test", API_MAIN)
                    assert spec and spec.loader
                    mod = importlib.util.module_from_spec(spec)
                    # need to inject required parent packages for relative imports inside main? main uses absolute imports only
                    spec.loader.exec_module(mod)
                    return mod
        # fallback (should not happen)
        sys.path.insert(0, str(ROOT / "api"))
        import api.app.main as app  # type: ignore
        return app

    def test_legacy_704_normalized_to_1920_roundtrip(self):
        app = self._import_app()
        legacy = [{"x": 352, "y": 288}, {"x": 700, "y": 570}, {"x": 100, "y": 100}]
        norm, rw, rh = app._normalize_legacy_polygon(legacy, {})
        self.assertEqual(rw, 704)
        self.assertAlmostEqual(norm[0]["x_norm"], 0.5)
        # denormalize to 1920 should be same relative lane
        abs1920 = app._denormalize_to_absolute(norm, 1920, 1080)
        self.assertEqual(abs1920[0]["x"], 960)
        self.assertEqual(abs1920[0]["y"], 540)

    def test_normalized_write_read_worker_scaling(self):
        app = self._import_app()
        # worker scaling helper is in worker module; test via api denormalize
        norm = [{"x_norm": 0.25, "y_norm": 0.75}]
        abs_pt = app._denormalize_to_absolute(norm, 1920, 1080)
        self.assertEqual(abs_pt[0]["x"], 480)
        self.assertEqual(abs_pt[0]["y"], 810)
        # back to norm via worker helper
        for _m in ["cv2", "numpy", "ultralytics", "av", "requests"]:
            if _m not in sys.modules:
                sys.modules[_m] = mock.MagicMock()
        sys.path.insert(0, str(ROOT / "worker"))
        import hls_motion_yolo_worker_events as worker
        scaled = worker._scale_norm_points(norm, 1920, 1080)
        self.assertEqual(scaled, [(480, 810)])
        # legacy absolute scale fallback
        legacy_abs = [(352, 288)]
        scaled_legacy = worker._maybe_scale_legacy_absolute(legacy_abs, 1920, 1080)
        self.assertEqual(scaled_legacy, [(960, 540)])

    def test_api_accepts_both_schemas(self):
        app = self._import_app()
        # legacy POST should be normalized internally
        legacy_payload = {"polygon": [{"x": 352, "y": 288}, {"x": 700, "y": 10}, {"x": 10, "y": 10}], "enabled": True}
        # simulate POST logic: if norm not present, legacy path
        legacy = app.clean_points_list(legacy_payload["polygon"], max_points=1000)
        norm, rw, rh = app._normalize_legacy_polygon(legacy, legacy_payload)
        self.assertEqual(rw, 704)
        self.assertEqual(len(norm), 3)
        # normalized payload
        norm_payload = {"polygon_norm": [{"x_norm": 0.5, "y_norm": 0.5}, {"x_norm": 0.9, "y_norm": 0.1}, {"x_norm": 0.1, "y_norm": 0.1}], "reference_width": 1920}
        cleaned = app._clean_norm_points(norm_payload["polygon_norm"], max_points=1000)
        self.assertEqual(len(cleaned), 3)
        self.assertAlmostEqual(cleaned[0]["x_norm"], 0.5)

    def test_frontend_files_use_normalized_and_1920(self):
        for p in [ROOT/"frontend/sea-speed/index.html", ROOT/"frontend/sea-speed/road/index.html"]:
            t = p.read_text()
            self.assertIn("1920/1080", t)
            self.assertIn("x_norm", t)
            self.assertIn("polygon_norm", t)

    def test_deploy_migration_present(self):
        t = (ROOT/"deploy/vps/deploy.sh").read_text()
        self.assertIn("migrate_legacy_roi_to_normalized", t)
        self.assertIn("polygon_norm", t)

if __name__ == "__main__":
    unittest.main()
