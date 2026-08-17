from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPERATOR_SOURCE = ROOT / "frontend/sea-speed/index.html"
OBJECTS_SOURCE = ROOT / "frontend/sea-speed/objects/index.html"
CAMERAS_SOURCE = ROOT / "frontend/sea-speed/cameras/index.html"
ROAD_SOURCE = ROOT / "frontend/sea-speed/road/index.html"
ROOT_SOURCE = ROOT / "frontend/root/index.html"


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = OPERATOR_SOURCE.read_text(encoding="utf-8-sig")
        cls.objects = OBJECTS_SOURCE.read_text(encoding="utf-8-sig")
        cls.cameras = CAMERAS_SOURCE.read_text(encoding="utf-8-sig")
        cls.road = ROAD_SOURCE.read_text(encoding="utf-8-sig")
        cls.root = ROOT_SOURCE.read_text(encoding="utf-8-sig")

    def test_existing_operator_endpoints_and_single_stream_control_remain(self) -> None:
        expected = {
            "HLS_URL": "/sea-speed/media/cam1/index.m3u8", "STATE_URL": "/sea-speed/api/cam1/state",
            "ROI_URL": "/sea-speed/api/cam1/roi", "WORKER_CONTROL_URL": "/sea-speed/api/worker/control",
        }
        for name, value in expected.items():
            self.assertRegex(self.source, rf"const\s+{name}\s*=\s*[\"']{re.escape(value)}[\"']")
        self.assertEqual(self.source.count('id="streamControlBtn"'), 1)
        self.assertEqual(self.source.count('id="workerControlBtn"'), 1)
        self.assertIn('streamControlBtn.onclick=()=>streamDesired?disconnectStream(true):connectStream', self.source)
        self.assertNotIn('id="connectBtn"', self.source)
        self.assertNotIn('id="disconnectBtn"', self.source)

    def test_navigation_is_synchronized_across_four_authenticated_pages(self) -> None:
        for page in (self.source, self.objects, self.cameras, self.road):
            self.assertIn('/sea-speed/objects/', page)
            self.assertIn('/sea-speed/cameras/', page)
            self.assertEqual(page.count('id="sessionUser"'), 1)
            self.assertIn('href="/outpost.goauthentik.io/sign_out">Выйти</a>', page)
            self.assertRegex(page, r'SESSION_URL\s*=\s*["\']/sea-speed/api/session["\']')
            self.assertNotIn("localStorage", page)
            self.assertNotIn("sessionStorage", page)
        for page in (self.source, self.objects, self.cameras):
            self.assertIn('/sea-speed/road/', page)

    def test_water_and_road_navigation_toggle_is_reciprocal_and_highlighted(self) -> None:
        water_to_road = '<a class="objects-link road-link active" href="/sea-speed/road/">Дорога</a>'
        road_to_water = '<a class="objects-link road-link active" href="/sea-speed/">Вода</a>'
        self.assertIn(water_to_road, self.source)
        self.assertIn(road_to_water, self.road)
        self.assertEqual(self.source.count(water_to_road), 1)
        self.assertEqual(self.road.count(road_to_water), 1)
        self.assertIn('.objects-link.active{', self.source)
        self.assertIn('.objects-link.active{', self.road)

    def test_road_page_uses_logical_road1_and_generic_analytics_api(self) -> None:
        for marker in (
            'const CAMERA_ID="road1"', 'const BASE="/sea-speed/api/analytics/road1"',
            'const STATE_URL=BASE+"/state"', 'const EVENTS_URL=BASE+"/events?limit=3"',
            'const ROI_URL=BASE+"/roi"', 'const SPEED_CONFIG_URL=BASE+"/speed-config"',
            'const SPEED_LINES_URL=BASE+"/speed-lines"',
            'const PREVIEW_START_URL="/sea-speed/api/cameras/road1/preview/start"',
            'const PREVIEW_STOP_URL="/sea-speed/api/cameras/preview/stop"',
            'const WORKER_CONTROL_URL="/sea-speed/api/worker/control/road1"',
        ):
            self.assertIn(marker, self.road)
        self.assertNotRegex(self.road, r'rtsp://[^\s"\']+:[^\s"\']+@')

    def test_road_page_matches_operator_layout_and_controls(self) -> None:
        for marker in (
            'data-layout="compact-status"', 'data-layout="three-column-workspace"',
            'data-layout="primary-camera"', 'data-layout="clean-live"',
            'Overlay controls', 'Speed calibration', 'State JSON', 'Operator log',
            'DETECTION HISTORY', 'id="overlayImg"', 'id="roiCanvas"', 'id="speedLinesCanvas"',
            'id="stateJson"', 'id="debugLog"', 'id="eventsList"',
        ):
            self.assertIn(marker, self.road)
        self.assertEqual(self.road.count('id="streamControlBtn"'), 1)
        self.assertEqual(self.road.count('id="workerControlBtn"'), 1)
        self.assertEqual(self.road.count('id="video"'), 1)
        self.assertNotIn('id="previewStart"', self.road)
        self.assertNotIn('id="previewStop"', self.road)
        ids = re.findall(r'\bid="([^"]+)"', self.road)
        self.assertEqual(len(ids), len(set(ids)))

    def test_road_stream_is_auto_connected_contextual_and_resilient(self) -> None:
        for marker in (
            'const STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000]',
            'Hls.ErrorTypes.MEDIA_ERROR', 'function schedulePlaybackWatchdog',
            'function disconnectStream(', 'setTimeout(()=>connectStream(false),0)',
            'streamControlBtn.onclick=()=>streamDesired?disconnectStream(true):connectStream(true)',
            'livePreviewFrame.classList.remove("has-video")',
        ):
            self.assertIn(marker, self.road)
        self.assertIn('Road AI worker stopped; live preview unchanged', self.road)

    def test_road_worker_control_is_road_scoped_and_contextual(self) -> None:
        self.assertIn('WORKER_START_URL=WORKER_CONTROL_URL+"/start"', self.road)
        self.assertIn('WORKER_STOP_URL=WORKER_CONTROL_URL+"/stop"', self.road)
        self.assertIn('d.target!=="road1"', self.road)
        self.assertIn('Остановить только Road AI worker; live preview продолжит работать', self.road)
        self.assertNotIn('/sea-speed/api/worker/control/start"', self.road)
        self.assertNotIn('/sea-speed/api/worker/control/stop"', self.road)

    def test_objects_registry_is_cross_camera_and_filterable(self) -> None:
        self.assertIn('const OBJECTS_URL="/sea-speed/api/objects"', self.objects)
        self.assertIn('name="camera_id"', self.objects)
        self.assertIn('name="domain"', self.objects)
        self.assertIn('value="cam1"', self.objects)
        self.assertIn('value="road1"', self.objects)
        for marker in ('method:"PATCH"', 'method:"DELETE"', 'credentials:"same-origin"', 'id="objectsGrid"'):
            self.assertIn(marker, self.objects)

    def test_existing_operator_workspace_and_hls_recovery_markers_remain(self) -> None:
        for marker in (
            'data-layout="three-column-workspace"', 'data-layout="primary-camera"', 'data-layout="clean-live"',
            'const STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000]', 'Hls.ErrorTypes.NETWORK_ERROR',
            'Hls.ErrorTypes.MEDIA_ERROR', 'function schedulePlaybackWatchdog', 'function disconnectStream(',
        ):
            self.assertIn(marker, self.source)

    def test_all_pages_keep_mobile_baseline(self) -> None:
        for page in (self.source, self.objects, self.cameras, self.road):
            self.assertIn('@media(max-width:760px)', page)
            self.assertIn('viewport-fit=cover', page)
        self.assertIn('href="/sea-speed/"', self.root)


if __name__ == "__main__":
    unittest.main()