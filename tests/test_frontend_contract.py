from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend/sea-speed/index.html"


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8-sig")

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


if __name__ == "__main__":
    unittest.main()
