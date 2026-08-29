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
        self.assertNotRegex(self.source, r'<(?:section|article|div)\b[^>]*data-layout="clean-live"')
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
            'const SPEED_LINES_URL=BASE+"/speed-lines"', 'const CROSSING_LINE_URL=BASE+"/crossing-line"',
            'const PREVIEW_START_URL="/sea-speed/api/cameras/road1/preview/start"',
            'const PREVIEW_STOP_URL="/sea-speed/api/cameras/preview/stop"',
            'const WORKER_CONTROL_URL="/sea-speed/api/worker/control/road1"',
        ):
            self.assertIn(marker, self.road)
        self.assertNotRegex(self.road, r'rtsp://[^\s"\']+:[^\s"\']+@')

    def test_road_page_matches_water_parity_layout_and_controls(self) -> None:
        for marker in (
            'data-layout="single-row-header"', 'data-layout="compact-status"',
            'data-layout="road-operator-workspace"', 'data-layout="primary-camera"',
            'data-layout="right-information-rail"', 'data-layout="crossing-stats"',
            'data-layout="recent-events"', 'data-layout="under-camera-controls"',
            'data-layout="collapsible-state"', 'data-layout="collapsible-log"',
            'id="roadMainVideo"', 'id="overlayImg"', 'id="liveOverlayCanvas"',
            'id="roiCanvas"', 'id="speedLinesCanvas"', 'id="crossingCanvas"',
            'id="stateJson"', 'id="debugLog"', 'id="eventsList"',
        ):
            self.assertIn(marker, self.road)
        for marker in (
            'id="roiEditBtn"', 'id="roiUndoBtn"', 'id="roiClearBtn"', 'id="roiSaveBtn"',
            'id="speedLineABtn"', 'id="speedLineBBtn"', 'id="speedLinesSaveBtn"',
            'id="cxEditBtn"', 'id="cxUndoBtn"', 'id="cxSaveBtn"', 'id="cxOffBtn"',
            'id="speedFactorInput"', 'id="speedSaveBtn"',
        ):
            self.assertEqual(self.road.count(marker), 1)
        self.assertNotIn('data-layout="clean-live"', self.road)
        self.assertNotIn('Чистый поток', self.road)
        self.assertNotIn('cleanPreviewVideo', self.road)
        self.assertEqual(self.road.count('id="roadMainVideo"'), 1)
        self.assertEqual(self.road.count('id="video"'), 0)
        self.assertIn('grid-template-areas:"camera right" "controls right"', self.road)
        self.assertIn('grid-template-areas:"camera" "right" "controls"', self.road)
        ids = re.findall(r'\bid="([^"]+)"', self.road)
        self.assertEqual(len(ids), len(set(ids)))

    def test_road_header_begins_with_lighthouse_and_compact_status(self) -> None:
        header_start = self.road.index('<header class="operator-header" data-layout="single-row-header">')
        header_end = self.road.index('</header>', header_start)
        header = self.road[header_start:header_end]
        self.assertLess(header.index('class="project-home"'), header.index('class="brand-inline"'))
        self.assertLess(header.index('class="brand-inline"'), header.index('class="header-links"'))
        self.assertIn('data-layout="compact-status"', header)
        self.assertIn('class="session-bar"', header)
        self.assertIn('.operator-header{display:flex;align-items:center;', self.road)

    def test_road_uses_one_hls_player_bound_to_main_video(self) -> None:
        self.assertEqual(self.road.count('new Hls('), 1)
        self.assertIn('instance.attachMedia(roadMainVideo)', self.road)
        self.assertNotIn('cleanHls', self.road)
        self.assertNotIn('attachMedia(video)', self.road)
        self.assertIn('roadMainVideo.addEventListener("timeupdate",notePlaybackProgress)', self.road)
        self.assertIn('roadMainVideo.addEventListener("waiting",()=>schedulePlaybackWatchdog("waiting timeout"))', self.road)
        self.assertIn('roadMainVideo.addEventListener("stalled",()=>schedulePlaybackWatchdog("stalled timeout"))', self.road)
        self.assertIn('streamControlBtn.onclick=()=>streamDesired?disconnectStream(true):connectStream(true)', self.road)
        self.assertIn('const STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000]', self.road)
        self.assertIn('Hls.ErrorTypes.MEDIA_ERROR', self.road)
        self.assertIn('Hls.ErrorTypes.NETWORK_ERROR', self.road)

    def test_road_worker_control_is_road_scoped_and_media_independent(self) -> None:
        self.assertIn('WORKER_START_URL=WORKER_CONTROL_URL+"/start"', self.road)
        self.assertIn('WORKER_STOP_URL=WORKER_CONTROL_URL+"/stop"', self.road)
        self.assertIn('d.target!=="road1"', self.road)
        self.assertIn('Остановить только Road AI worker; live HLS продолжит работать', self.road)
        self.assertIn('Road AI worker stopped; live HLS unchanged', self.road)
        self.assertIn('window.clearRoadLiveOverlay=()=>{', self.road)
        self.assertIn('if(workerServiceActive===false){clearLive();return}', self.road)
        self.assertNotIn('/sea-speed/api/worker/control/start"', self.road)
        self.assertNotIn('/sea-speed/api/worker/control/stop"', self.road)
        self.assertNotRegex(self.road, r'toggleWorker\([^)]*\).*connectStream')
        self.assertNotRegex(self.road, r'toggleWorker\([^)]*\).*disconnectStream')

    def test_road_overlay_snapshot_is_bounded_fallback_only(self) -> None:
        self.assertIn('lastFallbackOverlayUrl=""', self.road)
        self.assertIn('if(d.last_overlay_url&&!playbackIsAdvancing(STREAM_RECOVERY_GRACE_MS))', self.road)
        self.assertIn('if(url!==lastFallbackOverlayUrl)', self.road)
        self.assertNotIn('if(d.last_overlay_url)overlayImg.src=', self.road)

    def test_road_crossings_and_recent_events_are_independent_cards(self) -> None:
        self.assertIn('href="/sea-speed/objects/?scope=road&view=crossings">История</a>', self.road)
        self.assertIn('id="cxStatsIn"', self.road)
        self.assertIn('id="cxStatsOut"', self.road)
        self.assertIn('id="cxStatsTotal"', self.road)
        self.assertIn('id="cxStatsRows"', self.road)
        self.assertIn('Последнее пересечение:', self.road)
        self.assertIn('(data.events||[]).slice(0,3)', self.road)
        self.assertIn('href="/sea-speed/objects/?scope=road">Все события</a>', self.road)

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

    def test_road_live_sync_markers_remain(self) -> None:
        for marker in (
            'SeaSpeedLiveSync.bracketForMedia(mediaMs,{',
            'SeaSpeedLiveSync.closestEarlierEnvelope(compMs,{',
            'SeaSpeedLiveSync.clampLag(SeaSpeedLiveSync.median(lagSamples))',
            '<script src="/sea-speed/live-sync.js"></script>',
        ):
            self.assertIn(marker, self.road)

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
