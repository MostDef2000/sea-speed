from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPERATOR_SOURCE = ROOT / "frontend/sea-speed/index.html"
ROOT_SOURCE = ROOT / "frontend/root/index.html"
OBJECTS_SOURCE = ROOT / "frontend/sea-speed/objects/index.html"
CAMERAS_SOURCE = ROOT / "frontend/sea-speed/cameras/index.html"


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = OPERATOR_SOURCE.read_text(encoding="utf-8-sig")
        cls.root_source = ROOT_SOURCE.read_text(encoding="utf-8-sig")
        cls.objects_source = OBJECTS_SOURCE.read_text(encoding="utf-8-sig")
        cls.cameras_source = CAMERAS_SOURCE.read_text(encoding="utf-8-sig")

    def test_operator_endpoints_are_explicit(self) -> None:
        expected = {
            "HLS_URL": "/sea-speed/media/cam1/index.m3u8",
            "STATE_URL": "/sea-speed/api/cam1/state",
            "EVENTS_URL": "/sea-speed/api/cam1/events?limit=3",
            "ROI_URL": "/sea-speed/api/cam1/roi",
            "SPEED_CONFIG_URL": "/sea-speed/api/cam1/speed-config",
            "SPEED_LINES_URL": "/sea-speed/api/cam1/speed-lines",
        }
        for name, value in expected.items():
            self.assertRegex(self.source, rf"const\s+{name}\s*=\s*[\"']{re.escape(value)}[\"']")
        self.assertNotIn("/cams/", self.source)

    def test_configuration_save_flows_use_json_post(self) -> None:
        for function_name in ("saveSpeedConfig", "saveSpeedLines", "saveRoi"):
            self.assertIn(f"async function {function_name}", self.source)
        self.assertIn('method:"POST"', self.source)
        self.assertIn('headers:{"Content-Type":"application/json"}', self.source)

    def test_runtime_ids_are_unique(self) -> None:
        ids = re.findall(r'\bid="([^"]+)"', self.source)
        self.assertEqual(len(ids), len(set(ids)))
        for element_id in (
            "video", "streamStatus", "workerStatus", "motionStatus", "aiStatus",
            "detectionsStatus", "tracksStatus", "overlayImg", "roiCanvas",
            "speedLinesCanvas", "stateJson", "debugLog", "eventsList",
        ):
            self.assertEqual(self.source.count(f'id="{element_id}"'), 1)

    def test_desktop_workspace_has_three_columns_and_named_areas(self) -> None:
        self.assertIn('data-layout="three-column-workspace"', self.source)
        self.assertIn('grid-template-columns:minmax(250px,286px) minmax(0,720px) minmax(300px,340px)', self.source)
        self.assertIn('grid-template-areas:"utilities camera right"', self.source)
        self.assertIn('data-layout="left-utilities"', self.source)
        self.assertIn('data-layout="primary-camera"', self.source)
        self.assertIn('data-layout="right-live-history"', self.source)

    def test_primary_camera_is_annotated_and_contains_no_video(self) -> None:
        match = re.search(r'<article\s+class="panel camera-panel"[^>]*>(?P<body>.*?)</article>', self.source, re.S)
        self.assertIsNotNone(match)
        body = match.group("body")
        for marker in ('id="overlayImg"', 'id="roiCanvas"', 'id="speedLinesCanvas"'):
            self.assertIn(marker, body)
        self.assertNotIn('id="video"', body)
        self.assertIn('width:min(100%,720px)', self.source)

    def test_clean_live_and_detection_history_share_right_rail(self) -> None:
        right = re.search(r'<aside\s+class="right-sidebar"[^>]*>(?P<body>.*?)</aside>', self.source, re.S)
        self.assertIsNotNone(right)
        body = right.group("body")
        self.assertIn('data-layout="clean-live"', body)
        self.assertIn('<video id="video" controls playsinline muted></video>', body)
        self.assertIn('data-layout="compact-detection-history"', body)
        self.assertIn('id="eventsList"', body)
        self.assertLess(body.index('data-layout="clean-live"'), body.index('data-layout="compact-detection-history"'))
        self.assertEqual(self.source.count('new Hls('), 1)

    def test_clean_live_has_controlled_retry_lifecycle(self) -> None:
        for marker in (
            'const STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000]',
            'streamDesired=false',
            'connectInFlight=false',
            'playInFlight=false',
            'reconnectAttempt=0',
            'reconnectTimer=null',
            'function scheduleStreamReconnect',
            'function attemptVideoPlay',
            'function destroyStreamMedia',
        ):
            self.assertIn(marker, self.source)
        self.assertIn('if(connectInFlight)return', self.source)
        self.assertEqual(self.source.count('new Hls('), 1)

    def test_hls_errors_use_network_and_media_recovery(self) -> None:
        for marker in (
            'Hls.ErrorTypes.NETWORK_ERROR',
            'instance.startLoad()',
            'Hls.ErrorTypes.MEDIA_ERROR',
            'instance.recoverMediaError()',
        ):
            self.assertIn(marker, self.source)

    def test_stream_status_tracks_actual_playback_and_stop_cancels_retry(self) -> None:
        self.assertIn('video.addEventListener("playing"', self.source)
        self.assertEqual(self.source.count('setStatus(streamStatus,"online","good")'), 1)
        self.assertNotIn(
            'MANIFEST_PARSED,()=>video.play().then(()=>setStatus(streamStatus,"online"',
            self.source,
        )
        start = self.source.index('function disconnectStream(')
        end = self.source.index('async function refreshState', start)
        disconnect_source = self.source[start:end]
        for marker in (
            'streamDesired=false',
            'clearReconnectTimer()',
            'destroyStreamMedia()',
            'setStatus(streamStatus,"idle","warn")',
        ):
            self.assertIn(marker, disconnect_source)
        self.assertIn('video.removeAttribute("src")', self.source)

    def test_stalled_stream_uses_progress_watchdog_before_reconnect(self) -> None:
        for marker in (
            'const STREAM_STALL_GRACE_MS=2500',
            'playbackWatchdogTimer=null',
            'function schedulePlaybackWatchdog',
            'video.currentTime)||0',
            'current>baseline+0.05',
            'video.addEventListener("timeupdate",notePlaybackProgress)',
            'schedulePlaybackWatchdog("waiting timeout")',
            'schedulePlaybackWatchdog("stalled timeout")',
            'schedulePlaybackWatchdog("video error timeout")',
        ):
            self.assertIn(marker, self.source)
        self.assertNotIn('scheduleStreamReconnect("stalled")', self.source)
        self.assertNotIn('scheduleStreamReconnect("video error")', self.source)

    def test_hls_builtin_recovery_gets_grace_period(self) -> None:
        for marker in (
            'const STREAM_RECOVERY_GRACE_MS=3500',
            'recoveryTimer=null',
            'function scheduleRecoveryCheck',
            'scheduleRecoveryCheck("network recovery timeout")',
            'scheduleRecoveryCheck("media recovery timeout")',
        ):
            self.assertIn(marker, self.source)
        self.assertNotIn('scheduleStreamReconnect("network error")', self.source)
        self.assertNotIn('scheduleStreamReconnect("media error")', self.source)

    def test_playback_progress_clears_stale_reconnect_status(self) -> None:
        self.assertIn('function markStreamOnline()', self.source)
        self.assertIn('function playbackIsAdvancing', self.source)
        self.assertIn('if(playbackIsAdvancing()){markStreamOnline();return}', self.source)
        mark_start = self.source.index('function markStreamOnline()')
        mark_end = self.source.index('function notePlaybackProgress()', mark_start)
        mark_source = self.source[mark_start:mark_end]
        for marker in (
            'clearStreamRecoveryTimers()',
            'reconnectAttempt=0',
            'connectInFlight=false',
            'setStatus(streamStatus,"online","good")',
        ):
            self.assertIn(marker, mark_source)

    def test_stop_cancels_watchdog_and_recovery_timers(self) -> None:
        start = self.source.index('function disconnectStream(')
        end = self.source.index('video.addEventListener("loadedmetadata"', start)
        disconnect_source = self.source[start:end]
        for marker in (
            'clearReconnectTimer()',
            'clearPlaybackWatchdog()',
            'clearRecoveryTimer()',
            'lastPlaybackTime=0',
            'lastPlaybackProgressAt=0',
        ):
            self.assertIn(marker, disconnect_source)

    def test_stream_autoconnects_and_recovers_video_events(self) -> None:
        for marker in (
            'video.addEventListener("stalled"',
            'video.addEventListener("ended"',
            'video.addEventListener("error"',
            'setTimeout(()=>connectStream({resetRetry:true,reason:"auto"}),0)',
        ):
            self.assertIn(marker, self.source)

    def test_detection_history_is_capped_and_does_not_use_bottom_panel(self) -> None:
        self.assertIn('events.slice(0,3)', self.source)
        self.assertIn('grid-template-rows:auto minmax(0,1fr)', self.source)
        self.assertIn('overflow-y:auto', self.source)
        self.assertNotIn('class="panel events-panel"', self.source)
        self.assertEqual(self.source.count('id="eventsList"'), 1)

    def test_all_left_utility_blocks_are_closed_disclosures(self) -> None:
        markers = (
            ('collapsible-overlay-controls', 'Overlay controls'),
            ('collapsible-calibration', 'Speed calibration'),
            ('collapsible-state', 'State JSON'),
            ('collapsible-log', 'Operator log'),
        )
        for layout, label in markers:
            match = re.search(
                rf'<details\s+class="[^"]+"\s+data-layout="{layout}"(?P<attrs>[^>]*)>.*?{re.escape(label)}.*?</details>',
                self.source,
                re.S,
            )
            self.assertIsNotNone(match)
            self.assertNotRegex(match.group("attrs"), r'\bopen\b')

    def test_mobile_order_prioritizes_camera_live_history_then_utilities(self) -> None:
        self.assertRegex(
            self.source,
            re.compile(r'@media\(max-width:760px\).*?grid-template-areas:"camera" "right" "utilities"', re.S),
        )
        for marker in (
            "viewport-fit=cover",
            "env(safe-area-inset-top)",
            "env(safe-area-inset-right)",
            "env(safe-area-inset-bottom)",
            "env(safe-area-inset-left)",
            "@media(max-width:430px)",
            "@media(max-width:390px)",
            "min-height:44px",
        ):
            self.assertIn(marker, self.source)

    def test_operator_links_to_objects_registry(self) -> None:
        self.assertRegex(
            self.source,
            r'<a\s+class="objects-link"\s+href="/sea-speed/objects/">Реестр объектов</a>',
        )

    def test_protected_headers_use_trusted_authentik_identity_and_logout(self) -> None:
        pages = (self.source, self.objects_source, self.cameras_source)
        for page in pages:
            self.assertEqual(page.count('id="sessionUser"'), 1)
            self.assertIn('class="project-home" href="/"', page)
            self.assertIn('class="project-lighthouse"', page)
            self.assertIn('aria-label="На главную mostdef.ru"', page)
            self.assertIn('href="/outpost.goauthentik.io/sign_out">Выйти</a>', page)
            self.assertRegex(
                page,
                r'const\s+SESSION_URL\s*=\s*["\']/sea-speed/api/session["\']',
            )
            self.assertNotIn('/outpost.goauthentik.io/auth/nginx', page)
            self.assertIn('credentials:"same-origin"', page)
            self.assertIn('textContent=', page)
            self.assertNotIn('localStorage', page)
            self.assertNotIn('sessionStorage', page)

    def test_common_protected_headers_are_mobile_responsive(self) -> None:
        for page in (self.source, self.objects_source, self.cameras_source):
            self.assertIn('@media(max-width:760px)', page)
            self.assertIn('.session-bar', page)
            self.assertIn('.project-home', page)

    def test_objects_page_api_and_operator_actions(self) -> None:
        self.assertRegex(
            self.objects_source,
            r'const\s+OBJECTS_URL\s*=\s*["\']/sea-speed/api/cam1/objects["\']',
        )
        for marker in (
            'method:"PATCH"',
            'method:"DELETE"',
            'credentials:"same-origin"',
            'const PAGE_SIZE=24',
            'id="objectsGrid"',
            'id="detailPhoto"',
            'id="editClassName"',
            'id="editSpeed"',
            'id="editStatus"',
            'id="editComment"',
            'id="editForm"',
            'id="deleteBtn"',
            'id="prevBtn"',
            'id="nextBtn"',
            'href="/sea-speed/"',
        ):
            self.assertIn(marker, self.objects_source)
        ids = re.findall(r'\bid="([^"]+)"', self.objects_source)
        self.assertEqual(len(ids), len(set(ids)))

    def test_objects_page_mobile_and_accessibility_baseline(self) -> None:
        self.assertIn('@media(max-width:760px)', self.objects_source)
        self.assertIn('min-height:44px', self.objects_source)
        self.assertIn('viewport-fit=cover', self.objects_source)

    def test_cameras_page_runtime_ids_are_unique(self) -> None:
        ids = re.findall(r'\bid="([^"]+)"', self.cameras_source)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.cameras_source.count('id="sessionUser"'), 1)
        self.assertIn('const CAMERAS_URL="/sea-speed/api/cameras"', self.cameras_source)
        self.assertIn('const PREVIEW_STOP_URL="/sea-speed/api/cameras/preview/stop"', self.cameras_source)

    def test_root_page_primary_action_opens_operator_frontend(self) -> None:
        self.assertRegex(self.root_source, r'<a\s+class="primary-link"\s+href="/sea-speed/">')
        self.assertIn("Открыть морской мониторинг", self.root_source)

    def test_root_page_has_no_public_cameras_surface(self) -> None:
        self.assertNotIn('href="/cams/"', self.root_source)
        self.assertNotIn("https://mostdef.ru/cams/", self.root_source)
        self.assertNotIn(">Камеры</a>", self.root_source)

    def test_root_page_uses_local_absolute_paths(self) -> None:
        self.assertNotIn("https://mostdef.ru/sea-speed/", self.root_source)
        self.assertNotIn("https://mostdef.ru/cams/", self.root_source)

    def test_root_page_is_explicitly_maritime_and_local(self) -> None:
        for phrase in ("морского транспорта", "Обнаружение судов", "акватории Владивостока", "Эгершельд"):
            self.assertIn(phrase, self.root_source)

    def test_root_page_contains_marine_scene_and_radar_animation(self) -> None:
        for class_name in ("marine-backdrop", "vladivostok-skyline", "lighthouse-scene", "lighthouse", "sea", "radar", "sweep", "vessel"):
            self.assertIn(f'class="{class_name}"', self.root_source)
        self.assertIn("@keyframes sweep", self.root_source)
        self.assertIn("prefers-reduced-motion", self.root_source)

    def test_root_page_has_no_external_visual_assets(self) -> None:
        self.assertNotRegex(self.root_source, r'<img\b')
        self.assertNotRegex(self.root_source, r'url\(["\']?https?://')


if __name__ == "__main__":
    unittest.main()