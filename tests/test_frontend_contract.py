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
            "workerStatus",
            "motionStatus",
            "aiStatus",
            "detectionsStatus",
            "tracksStatus",
            "stateJson",
            "eventsList",
        ):
            self.assertIn(f'id="{element_id}"', self.source)

    def test_root_page_primary_action_opens_operator_frontend(self) -> None:
        self.assertRegex(
            self.root_source,
            r'<a\s+class="primary-link"\s+href="/sea-speed/">',
        )
        self.assertIn("Открыть Sea Speed", self.root_source)

    def test_root_page_cameras_link_is_secondary_and_in_footer(self) -> None:
        self.assertRegex(
            self.root_source,
            r'<footer>\s*<a\s+class="secondary-link"\s+href="/cams/">Камеры</a>\s*</footer>',
        )
        self.assertEqual(self.root_source.count('href="/cams/"'), 1)

    def test_root_page_uses_local_absolute_paths(self) -> None:
        self.assertNotIn("https://mostdef.ru/sea-speed/", self.root_source)
        self.assertNotIn("https://mostdef.ru/cams/", self.root_source)


if __name__ == "__main__":
    unittest.main()
