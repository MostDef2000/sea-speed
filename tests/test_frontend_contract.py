from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPERATOR_SOURCE = ROOT / "frontend/sea-speed/index.html"
ROOT_SOURCE = ROOT / "frontend/root/index.html"


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = OPERATOR_SOURCE.read_text(encoding="utf-8-sig")
        cls.root_source = ROOT_SOURCE.read_text(encoding="utf-8-sig")

    def test_operator_endpoints_are_explicit(self) -> None:
        expected = {
            "STATE_URL": "/sea-speed/api/cam1/state",
            "EVENTS_URL": "/sea-speed/api/cam1/events?limit=3",
            "ROI_URL": "/sea-speed/api/cam1/roi",
            "SPEED_CONFIG_URL": "/sea-speed/api/cam1/speed-config",
            "SPEED_LINES_URL": "/sea-speed/api/cam1/speed-lines",
        }
        for name, value in expected.items():
            self.assertRegex(self.source, rf"const\s+{name}\s*=\s*[\"']{re.escape(value)}[\"']")

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

    def test_root_page_primary_action_opens_operator_frontend(self) -> None:
        self.assertRegex(self.root_source, r'<a\s+class="primary-link"\s+href="/sea-speed/">')
        self.assertIn("Открыть морской мониторинг", self.root_source)

    def test_root_page_cameras_link_is_secondary_and_in_footer(self) -> None:
        self.assertRegex(self.root_source, r'<footer>\s*<a\s+class="secondary-link"\s+href="/cams/">Камеры</a>\s*</footer>')
        self.assertEqual(self.root_source.count('href="/cams/"'), 1)

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
