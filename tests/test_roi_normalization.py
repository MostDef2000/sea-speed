from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_MAIN = ROOT / "api/app/main.py"
DEPLOY_SH = ROOT / "deploy/vps/deploy.sh"
WATER_PAGE = ROOT / "frontend/sea-speed/index.html"
ROAD_PAGE = ROOT / "frontend/sea-speed/road/index.html"

from tests.support import frontend_html  # noqa: E402  (ROOT import path)

spec = importlib.util.spec_from_file_location("roi_api", API_MAIN)
assert spec and spec.loader

# Road-page ROI twin: the save button handler must POST the normalized
# schema (polygon_norm + pinned 1920x1080 reference), and the boot
# loadRoiConfig must normalize a legacy polygon through the executed
# sourceDims() (1920x1080 video stub).
ROAD_ROI_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
  assert(
    persistedRoiPoints.length === 3 && Math.abs(persistedRoiPoints[0].x_norm - 352 / 1920) < 1e-9,
    "legacy road ROI must normalize against the executed sourceDims reference: " +
      JSON.stringify(persistedRoiPoints)
  );
  roiPoints = [
    { x_norm: 0.25, y_norm: 0.25 },
    { x_norm: 0.75, y_norm: 0.25 },
    { x_norm: 0.5, y_norm: 0.75 },
  ];
  await __record.elements.roiSaveBtn.onclick();
  await new Promise((r) => setImmediate(r));
  const roiPosts = __record.fetch.filter(
    (c) => c.url === "/sea-speed/api/analytics/road1/roi" && (c.options.method || "GET") === "POST"
  );
  assert(roiPosts.length >= 1, "the ROI save control did not POST the ROI endpoint");
  const posts = roiPosts.map((c) => JSON.parse(c.options.body));
  assert(
    posts.every((body) => Array.isArray(body.polygon_norm) && body.polygon_norm.length === 3),
    "road ROI save payload must carry polygon_norm"
  );
  assert(
    posts.every((body) => body.reference_width === 1920 && body.reference_height === 1080),
    "road ROI save payload must pin the 1920x1080 reference"
  );
  console.log("###" + JSON.stringify({ posts }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


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

    def test_water_page_saves_and_loads_normalized_roi(self):
        # Executed twin (issue #398 wave 4): the water operator page's real
        # ROI wiring runs in node — the boot loadRoi consumes a LEGACY
        # absolute polygon response and normalizes it against the inferred
        # 704x576 reference, and saveRoi() POSTs the normalized schema with
        # the 1920x1080 reference pinned. The POST body is parsed from the
        # recorded fetch, so reformatting the page keeps this green and
        # rewiring the payload fails it.
        legacy_response = {
            "match": "/api/cam1/roi",
            "json": {
                "polygon": [{"x": 352, "y": 288}, {"x": 700, "y": 570}, {"x": 100, "y": 100}],
                "enabled": True,
            },
        }
        scenario = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  const round = (v) => Math.round(v * 1e6) / 1e6;
  await new Promise((r) => setImmediate(r));
  assert(roiPoints.length === 3, "boot loadRoi did not populate roiPoints from the legacy polygon");
  const legacy = roiPoints.map((p) => ({ x_norm: round(p.x_norm), y_norm: round(p.y_norm) }));
  assert(
    legacy[0].x_norm === 0.5 && legacy[0].y_norm === 0.5,
    "legacy 704x576 polygon must normalize against the inferred 704x576 reference: " + JSON.stringify(legacy)
  );
  roiPoints = [
    { x_norm: 0.25, y_norm: 0.25 },
    { x_norm: 0.75, y_norm: 0.25 },
    { x_norm: 0.5, y_norm: 0.75 },
  ];
  await saveRoi();
  await new Promise((r) => setImmediate(r));
  const roiPosts = __record.fetch.filter(
    (c) => c.url === "/sea-speed/api/cam1/roi" && (c.options.method || "GET") === "POST"
  );
  assert(roiPosts.length >= 1, "saveRoi did not POST the ROI endpoint");
  const posts = roiPosts.map((c) => JSON.parse(c.options.body));
  assert(
    posts.every((body) => Array.isArray(body.polygon_norm) && body.polygon_norm.length === 3),
    "saveRoi payload must carry polygon_norm"
  );
  assert(
    posts.every((body) => body.reference_width === 1920 && body.reference_height === 1080),
    "saveRoi payload must pin the 1920x1080 reference"
  );
  console.log("###" + JSON.stringify({ legacy, posts }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
        evidence = frontend_html.run_inline_scripts(
            source=WATER_PAGE, scenario=scenario, responses=[legacy_response]
        )
        self.assertEqual(evidence["legacy"][0], {"x_norm": 0.5, "y_norm": 0.5})
        self.assertTrue(evidence["posts"])
        for body in evidence["posts"]:
            self.assertEqual(len(body["polygon_norm"]), 3)
            self.assertEqual(body["reference_width"], 1920)
            self.assertEqual(body["reference_height"], 1080)
            self.assertTrue(body["enabled"])

    def test_road_page_saves_and_loads_normalized_roi(self):
        # Executed twin: the road operator page's ROI save control POSTs the
        # normalized schema, and the boot loadRoiConfig normalizes a legacy
        # polygon through the executed sourceDims() (1920x1080 video stub).
        legacy_response = {
            "match": "/api/analytics/road1/roi",
            "json": {
                "polygon": [{"x": 352, "y": 288}, {"x": 700, "y": 570}, {"x": 100, "y": 100}],
                "enabled": True,
            },
        }
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE,
            scenario=ROAD_ROI_SCENARIO,
            responses=[legacy_response],
        )
        self.assertTrue(evidence["posts"])
        for body in evidence["posts"]:
            self.assertEqual(len(body["polygon_norm"]), 3)
            self.assertEqual(body["reference_width"], 1920)
            self.assertEqual(body["reference_height"], 1080)

    def test_deploy_migration_normalizes_legacy_roi_state(self):
        # Read-back twin: the REAL migrate_legacy_roi_to_normalized function
        # is extracted from deploy/vps/deploy.sh (with its one-line log
        # helper) and executed against a fixture data tree — legacy
        # ROI/crossing JSON files must come out normalized against the
        # inferred 704x576 reference, already-normalized files stay
        # untouched, and the absolute polygon is re-denormalized to the
        # 1920x1080 compat shape.
        text = DEPLOY_SH.read_text(encoding="utf-8")
        log_start = text.index("log() {")
        log_end = text.index("\n", log_start) + 1
        fn_start = text.index("migrate_legacy_roi_to_normalized() {")
        fn_end = text.index("\n}", fn_start) + 2
        script = (
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            + text[log_start:log_end]
            + "\n"
            + text[fn_start:fn_end]
            + "\nmigrate_legacy_roi_to_normalized\n"
        )
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            migration = tmp / "migrate.sh"
            migration.write_text(script, encoding="utf-8")
            # data_dir derives from API_TARGET as dirname(dirname(API_TARGET))/data
            api_app = tmp / "srv" / "api" / "app"
            api_app.mkdir(parents=True)
            (api_app / "main.py").write_text("# API_TARGET placeholder\n", encoding="utf-8")
            data = tmp / "srv" / "api" / "data"
            data.mkdir()
            legacy_roi = {
                "polygon": [{"x": 352, "y": 288}, {"x": 700, "y": 570}, {"x": 100, "y": 100}],
                "enabled": True,
            }
            (data / "cam1_roi.json").write_text(json.dumps(legacy_roi), encoding="utf-8")
            already_norm = {
                "polygon_norm": [{"x_norm": 0.5, "y_norm": 0.5}],
                "reference_width": 1920,
                "enabled": True,
            }
            (data / "road1_roi.json").write_text(json.dumps(already_norm), encoding="utf-8")
            crossing = {"line": [{"x": 100, "y": 50}, {"x": 600, "y": 500}], "enabled": True}
            (data / "cam1_crossing_line.json").write_text(json.dumps(crossing), encoding="utf-8")
            env = dict(os.environ)
            env["API_TARGET"] = str(api_app / "main.py")
            proc = subprocess.run(
                ["bash", str(migration)],
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("ROI_MIGRATED total=2", proc.stdout)
            migrated = json.loads((data / "cam1_roi.json").read_text())
            self.assertIn("polygon_norm", migrated)
            self.assertEqual(migrated["reference_width"], 704)
            self.assertEqual(migrated["reference_height"], 576)
            self.assertAlmostEqual(migrated["polygon_norm"][0]["x_norm"], 0.5)
            self.assertAlmostEqual(migrated["polygon_norm"][0]["y_norm"], 0.5)
            # compat: the absolute polygon is re-denormalized to 1920x1080
            self.assertEqual(migrated["polygon"][0], {"x": 960, "y": 540})
            # already-normalized state must not be rewritten
            self.assertEqual(json.loads((data / "road1_roi.json").read_text()), already_norm)
            migrated_crossing = json.loads((data / "cam1_crossing_line.json").read_text())
            self.assertIn("line_norm", migrated_crossing)
            self.assertAlmostEqual(migrated_crossing["line_norm"][0]["x_norm"], 100 / 704)
            self.assertAlmostEqual(migrated_crossing["line_norm"][1]["x_norm"], 600 / 704)


if __name__ == "__main__":
    unittest.main()
