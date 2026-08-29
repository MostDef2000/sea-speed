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

    def test_water_and_road_navigation_is_reciprocal_without_false_water_active_state(self) -> None:
        water_to_road = '<a class="objects-link road-link" href="/sea-speed/road/">Дорога</a>'
        road_to_water = '<a class="objects-link road-link active" href="/sea-speed/">Вода</a>'
        self.assertIn(water_to_road, self.source)
        self.assertNotIn('<a class="objects-link road-link active" href="/sea-speed/road/">Дорога</a>', self.source)
        self.assertIn(road_to_water, self.road)
        self.assertEqual(self.source.count(water_to_road), 1)
        self.assertEqual(self.road.count(road_to_water), 1)
        self.assertIn('.objects-link.active{', self.road)

    def test_water_operator_matches_069_dashboard_layout(self) -> None:
        for marker in (
            'data-layout="single-row-header"', 'data-layout="water-operator-workspace"',
            'data-layout="primary-camera"', 'data-layout="right-information-rail"',
            'data-layout="crossing-stats"', 'data-layout="recent-passages"',
            'data-layout="under-camera-controls"', 'data-layout="collapsible-state"',
            'data-layout="collapsible-log"', 'id="waterMainVideo"', 'id="liveOverlayCanvas"',
            'id="roiCanvas"', 'id="speedLinesCanvas"', 'id="stateJson"', 'id="debugLog"',
        ):
            self.assertIn(marker, self.source)
        self.assertNotRegex(
            self.source,
            r'<(?:section|article|div)\b[^>]*data-layout="clean-live"',
        )
        self.assertNotIn('Чистый поток', self.source)
        self.assertNotIn('id="cxSummary"', self.source)
        self.assertEqual(self.source.count('id="waterMainVideo"'), 1)
        self.assertEqual(self.source.count('id="video"'), 0)
        self.assertNotIn('class="stream-probe"', self.source)
        ids = re.findall(r'\bid="([^"]+)"', self.source)
        self.assertEqual(len(ids), len(set(ids)))

    def test_water_header_begins_with_clickable_lighthouse_and_compact_status(self) -> None:
        header_start = self.source.index('<header class="operator-header" data-layout="single-row-header">')
        header_end = self.source.index('</header>', header_start)
        header = self.source[header_start:header_end]
        self.assertLess(header.index('class="project-home"'), header.index('class="brand-inline"'))
        self.assertLess(header.index('class="brand-inline"'), header.index('class="header-links"'))
        self.assertIn('data-layout="compact-status"', header)
        self.assertIn('class="session-bar"', header)
        self.assertIn('.operator-header{display:flex;align-items:center;', self.source)

    def test_water_crossings_and_recent_passages_use_existing_sources(self) -> None:
        self.assertIn('const CROSSING_SUMMARY_URL="/sea-speed/api/analytics/cam1/crossings/summary"', self.source)
        self.assertIn('href="/sea-speed/objects/?scope=water&view=crossings">История</a>', self.source)
        self.assertIn('id="cxStatsIn"', self.source)
        self.assertIn('id="cxStatsOut"', self.source)
        self.assertIn('id="cxStatsTotal"', self.source)
        self.assertIn('id="cxStatsRows"', self.source)
        self.assertIn('Последнее пересечение:', self.source)
        self.assertIn('const PASSAGES_URL="/sea-speed/api/cam1/passages?limit=3"', self.source)
        self.assertIn('passages.slice(0,3)', self.source)
        self.assertIn('ev.status||ev.speed_status||"tracking"', self.source)
        self.assertIn('href="/sea-speed/objects/?scope=water">Все проходы</a>', self.source)

    def test_water_controls_stay_under_camera_and_mobile_order_is_explicit(self) -> None:
        for marker in (
            'id="roiEditBtn"', 'id="roiUndoBtn"', 'id="roiClearBtn"', 'id="roiSaveBtn"',
            'id="speedLineABtn"', 'id="speedLineBBtn"', 'id="speedLinesSaveBtn"',
            'id="cxEditBtn"', 'id="cxUndoBtn"', 'id="cxSaveBtn"', 'id="cxOffBtn"',
            'id="speedFactorInput"', 'id="speedSaveBtn"',
        ):
            self.assertEqual(self.source.count(marker), 1)
        self.assertIn('grid-template-areas:"camera right" "controls right"', self.source)
        self.assertIn('grid-template-areas:"camera" "right" "controls"', self.source)
        self.assertIn('@media(max-width:430px)', self.source)

    def test_water_uses_one_hls_player_bound_to_main_video(self) -> None:
        self.assertEqual(self.source.count('new Hls('), 1)
        self.assertIn('instance.attachMedia(waterMainVideo)', self.source)
        self.assertIn('window.hls=instance;window.waterHls=instance', self.source)
        self.assertNotIn('waterHls=new Hls(', self.source)
        self.assertNotIn('instance.attachMedia(video)', self.source)
        self.assertNotIn('video.currentTime', self.source)
        self.assertNotIn('video.addEventListener(', self.source)
        self.assertIn('waterMainVideo.addEventListener("timeupdate",notePlaybackProgress)', self.source)
        self.assertIn('waterMainVideo.addEventListener("waiting",()=>schedulePlaybackWatchdog("waiting timeout"))', self.source)
        self.assertIn('waterMainVideo.addEventListener("stalled",()=>schedulePlaybackWatchdog("stalled timeout"))', self.source)

    def test_water_worker_lifecycle_only_controls_ai_overlay(self) -> None:
        self.assertIn('AI worker stopped; live HLS unchanged', self.source)
        self.assertIn('if(!workerServiceActive)window.clearWaterLiveOverlay?.()', self.source)
        self.assertIn('window.clearWaterLiveOverlay=()=>{', self.source)
        self.assertIn('if(workerServiceActive===false){clearLive();return}', self.source)
        self.assertNotRegex(self.source, r'toggleWorker\([^)]*\).*connectStream')
        self.assertNotRegex(self.source, r'toggleWorker\([^)]*\).*disconnectStream')

    def test_water_overlay_snapshot_is_bounded_fallback_only(self) -> None:
        self.assertIn('lastFallbackOverlayUrl=""', self.source)
        self.assertIn('if(s.last_overlay_url&&!playbackIsAdvancing(STREAM_RECOVERY_GRACE_MS))', self.source)
        self.assertIn('if(fallbackUrl&&fallbackUrl!==lastFallbackOverlayUrl)', self.source)
        self.assertNotIn('if(s.last_overlay_url)overlayImg.src=', self.source)

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

    def test_objects_registry_is_domain_scoped_from_water_and_road(self) -> None:
        self.assertIn('href="/sea-speed/objects/">Реестр объектов</a>', self.source)
        self.assertIn('href="/sea-speed/objects/">Реестр объектов</a>', self.road)
        self.assertIn('const OBJECTS_URL="/sea-speed/api/objects"', self.objects)
        self.assertIn('water:{camera_id:"cam1",domain:"water"', self.objects)
        self.assertIn('road:{camera_id:"road1",domain:"road"', self.objects)
        self.assertIn('const requestedScope=new URLSearchParams(window.location.search).get("scope")', self.objects)
        self.assertIn('const referrerPath=', self.objects)
        self.assertIn('referrerPath.startsWith("/sea-speed/road/")?"road":"water"', self.objects)
        self.assertIn('function applyRegistryScope()', self.objects)
        self.assertIn('history.replaceState(null,"",url)', self.objects)
        self.assertIn('camera_id:registryScope.camera_id,domain:registryScope.domain', self.objects)
        self.assertIn('if(key==="camera_id"||key==="domain")continue', self.objects)
        self.assertIn('filters.reset();applyRegistryScope();offset=0;loadObjects()', self.objects)
        self.assertRegex(self.objects, r'name="camera_id"[^>]*disabled')
        self.assertRegex(self.objects, r'<select id="domainInput" name="domain">')
        self.assertIn('function setRegistryScope(', self.objects)
        self.assertIn('domainInput.addEventListener("change",()=>setRegistryScope(domainInput.value))', self.objects)
        self.assertIn('registryScopeKey=key;registryScope=REGISTRY_SCOPES[key];offset=0;applyRegistryScope();loadObjects()', self.objects)
        for marker in ('method:"PATCH"', 'method:"DELETE"', 'credentials:"same-origin"', 'id="objectsGrid"'):
            self.assertIn(marker, self.objects)

    def test_water_hls_recovery_and_live_sync_markers_remain(self) -> None:
        for marker in (
            'const STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000]', 'Hls.ErrorTypes.NETWORK_ERROR',
            'Hls.ErrorTypes.MEDIA_ERROR', 'function schedulePlaybackWatchdog', 'function disconnectStream(',
            'SeaSpeedLiveSync.bracketForMedia(mediaMs,{',
            'SeaSpeedLiveSync.closestEarlierEnvelope(compMs,{',
            'SeaSpeedLiveSync.clampLag(SeaSpeedLiveSync.median(lagSamples))',
            '<script src="./live-sync.js"></script>',
        ):
            self.assertIn(marker, self.source)

    def test_all_pages_keep_mobile_baseline(self) -> None:
        for page in (self.objects, self.cameras, self.road):
            self.assertIn('@media(max-width:760px)', page)
            self.assertIn('viewport-fit=cover', page)
        self.assertIn('@media(max-width:700px)', self.source)
        self.assertIn('@media(max-width:430px)', self.source)
        self.assertIn('viewport-fit=cover', self.source)
        self.assertIn('href="/sea-speed/"', self.root)


if __name__ == "__main__":
    unittest.main()
