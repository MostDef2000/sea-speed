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
            "EVENTS_URL": "/sea-speed/api/cam1/events?limit=4",
            "ROI_URL": "/sea-speed/api/cam1/roi",
            "SPEED_CONFIG_URL": "/sea-speed/api/cam1/speed-config",
            "SPEED_LINES_URL": "/sea-speed/api/cam1/speed-lines",
        }
        for name, value in expected.items():
            self.assertRegex(
                self.source,
                rf"const\s+{name}\s*=\s*[\"']{re.escape(value)}[\"']",
            )

    def test_configuration_save_flows_use_json_post(self) -> None:
        for function_name in ("saveSpeedConfig", "saveSpeedLines", "saveRoi"):
            self.assertIn(f"async function {function_name}", self.source)
        self.assertGreaterEqual(self.source.count('method: "POST"'), 3)
        self.assertGreaterEqual(self.source.count('"Content-Type": "application/json"'), 3)

    def test_runtime_status_fields_are_rendered(self) -> None:
        for element_id in (
            "streamStatus",
            "workerStatus",
            "motionStatus",
            "aiStatus",
            "detectionsStatus",
            "tracksStatus",
            "stateJson",
            "eventsList",
        ):
            self.assertEqual(self.source.count(f'id="{element_id}"'), 1)

    def test_operator_uses_primary_annotated_camera_stage(self) -> None:
        self.assertIn('data-layout="primary-camera"', self.source)
        self.assertRegex(
            self.source,
            re.compile(
                r'<div\s+class="camera-stage"[^>]*>.*?'
                r'<div\s+class="roi-editor-wrap"\s+id="roiEditorWrap">.*?'
                r'<img\s+id="overlayImg".*?'
                r'<canvas\s+id="roiCanvas"></canvas>.*?'
                r'<canvas\s+id="speedLinesCanvas"></canvas>',
                re.S,
            ),
        )
        stage = self.source.split('<div class="camera-stage" id="cameraStage">', 1)[1].split('</div>\n\n        <div class="camera-meta">', 1)[0]
        self.assertNotIn('id="video"', stage)
        self.assertIn("Разметка ROI и линий скорости отображается непосредственно на основном кадре", self.source)

    def test_operator_has_single_clean_live_preview_in_right_sidebar(self) -> None:
        self.assertEqual(self.source.count('id="video"'), 1)
        match = re.search(
            r'<section\s+class="panel control-card live-preview-card"[^>]*>'
            r'(?P<body>.*?)</section>',
            self.source,
            re.S,
        )
        self.assertIsNotNone(match)
        live_card = match.group("body")
        for marker in (
            'data-layout="clean-live"',
            'id="connectBtn"',
            'id="disconnectBtn"',
            '<video id="video" controls playsinline muted></video>',
            'HLS без AI overlay',
        ):
            if marker.startswith('data-layout'):
                self.assertIn(marker, match.group(0))
            else:
                self.assertIn(marker, live_card)
        self.assertEqual(self.source.count('new Hls('), 1)

    def test_operator_overlay_controls_are_collapsed_by_default(self) -> None:
        match = re.search(
            r'<details\s+class="panel overlay-controls-card"\s+'
            r'data-layout="collapsible-overlay-controls"(?P<attrs>[^>]*)>.*?'
            r'<summary>.*?Overlay controls.*?</summary>.*?'
            r'id="roiEditBtn".*?id="speedLineABtn".*?</details>',
            self.source,
            re.S,
        )
        self.assertIsNotNone(match)
        self.assertNotIn(" open", match.group("attrs"))

    def test_operator_desktop_overlay_is_reduced_and_mobile_restores_width(self) -> None:
        self.assertIn("grid-template-columns: minmax(0, 820px) minmax(320px, 380px)", self.source)
        self.assertIn("width: min(100%, 720px);", self.source)
        self.assertRegex(
            self.source,
            re.compile(
                r'@media \(max-width: 900px\).*?'
                r'\.camera-stage\s*\{\s*width: 100%;',
                re.S,
            ),
        )

    def test_operator_status_is_compact_and_controls_are_right_sidebar(self) -> None:
        self.assertIn('class="status-strip"', self.source)
        self.assertIn('data-layout="compact-status"', self.source)
        self.assertIn('class="control-sidebar" data-layout="right-controls"', self.source)
        self.assertLess(
            self.source.index('data-layout="compact-status"'),
            self.source.index('<main class="operator-shell">'),
        )
        self.assertRegex(
            self.source,
            re.compile(
                r'<aside\s+class="control-sidebar"[^>]*>.*?'
                r'data-layout="clean-live".*?'
                r'data-layout="collapsible-overlay-controls".*?'
                r'id="roiEditBtn".*?id="speedLineABtn".*?'
                r'class="panel control-card speed-calibration-card".*?'
                r'<details\s+class="panel diagnostics-card state-card">',
                re.S,
            ),
        )

    def test_operator_mobile_layout_targets_ios_pro_widths(self) -> None:
        for marker in (
            "viewport-fit=cover",
            "env(safe-area-inset-top)",
            "env(safe-area-inset-right)",
            "env(safe-area-inset-bottom)",
            "env(safe-area-inset-left)",
            "@media (max-width: 430px)",
            "@media (max-width: 390px)",
            "min-height: 44px",
            "-webkit-overflow-scrolling: touch",
        ):
            self.assertIn(marker, self.source)

    def test_operator_state_and_log_are_compact_disclosures(self) -> None:
        self.assertRegex(
            self.source,
            re.compile(
                r'<details\s+class="panel diagnostics-card state-card">.*?'
                r'<pre\s+id="stateJson">\{\}</pre>.*?</details>',
                re.S,
            ),
        )
        self.assertRegex(
            self.source,
            re.compile(
                r'<details\s+class="panel diagnostics-card debug-card">.*?'
                r'<div\s+id="debugLog"\s+class="debug"></div>.*?</details>',
                re.S,
            ),
        )

    def test_root_page_primary_action_opens_operator_frontend(self) -> None:
        self.assertRegex(
            self.root_source,
            r'<a\s+class="primary-link"\s+href="/sea-speed/">',
        )
        self.assertIn("Открыть морской мониторинг", self.root_source)

    def test_root_page_cameras_link_is_secondary_and_in_footer(self) -> None:
        self.assertRegex(
            self.root_source,
            r'<footer>\s*<a\s+class="secondary-link"\s+href="/cams/">Камеры</a>\s*</footer>',
        )
        self.assertEqual(self.root_source.count('href="/cams/"'), 1)

    def test_root_page_uses_local_absolute_paths(self) -> None:
        self.assertNotIn("https://mostdef.ru/sea-speed/", self.root_source)
        self.assertNotIn("https://mostdef.ru/cams/", self.root_source)

    def test_root_page_is_explicitly_maritime_and_local(self) -> None:
        for phrase in (
            "морского транспорта",
            "Обнаружение судов",
            "акватории Владивостока",
            "Эгершельд",
        ):
            self.assertIn(phrase, self.root_source)

    def test_root_page_contains_marine_scene_and_radar_animation(self) -> None:
        for class_name in (
            "marine-backdrop",
            "vladivostok-skyline",
            "lighthouse-scene",
            "lighthouse",
            "sea",
            "radar",
            "sweep",
            "vessel",
        ):
            self.assertIn(f'class="{class_name}"', self.root_source)
        self.assertIn("@keyframes sweep", self.root_source)
        self.assertIn("prefers-reduced-motion", self.root_source)

    def test_root_page_has_no_external_visual_assets(self) -> None:
        self.assertNotRegex(self.root_source, r'<img\b')
        self.assertNotRegex(self.root_source, r'url\(["\']?https?://')


if __name__ == "__main__":
    unittest.main()
