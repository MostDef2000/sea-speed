"""Drift guard: the protected configure step derives its analytics profile
defaults from the canonical worker/analytics_profiles.py module.

Regression contract for #395: non-secret profile values (model, tracker, image
size, confidence, sample-fps default) exist in exactly one place. The configure
script is loaded through the module-wide SEA_SPEED_395_CONFIGURE_PATH override
so this battery can also be run RED against a base-script materialization.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

import analytics_profiles as profiles

CONFIGURE = Path(
    os.environ.get("SEA_SPEED_395_CONFIGURE_PATH", str(ROOT / "deploy/worker/ubuntu/configure-analytics-profiles.py"))
)
configure_spec = importlib.util.spec_from_file_location("configure_analytics_profiles_drift", CONFIGURE)
assert configure_spec and configure_spec.loader
configure = importlib.util.module_from_spec(configure_spec)
configure_spec.loader.exec_module(configure)


def expected_env_defaults(profile: profiles.AnalyticsProfile) -> dict[str, str]:
    """Independently re-derive the env-file mapping from canonical fields."""
    fps = str(int(profile.sample_fps)) if float(profile.sample_fps).is_integer() else str(profile.sample_fps)
    return {
        "ANALYTICS_PROFILE": profile.name,
        "CAMERA_ID": profile.default_camera_id,
        "MODEL_NAME": profile.model_name,
        "YOLO_TRACKER": profile.tracker,
        "YOLO_IMAGE_SIZE": str(profile.image_size),
        "YOLO_CONFIDENCE": f"{profile.confidence:.2f}",
        "SAMPLE_FPS": fps,
    }


class ConfigureDerivesFromCanonicalProfilesTests(unittest.TestCase):
    def test_water_and_road_defaults_equal_canonical_profile_fields(self) -> None:
        derived = configure.derived_profile_defaults()
        self.assertEqual(set(derived), set(profiles.PROFILES))
        for profile_name in ("water-v1", "road-v1"):
            with self.subTest(profile=profile_name):
                profile = profiles.get_profile(profile_name)
                self.assertEqual(derived[profile_name], expected_env_defaults(profile))

    def test_confidence_literals_unchanged_and_two_decimal_serialized(self) -> None:
        self.assertEqual(profiles.get_profile("water-v1").confidence, 0.10)
        self.assertEqual(profiles.get_profile("road-v1").confidence, 0.15)
        derived = configure.derived_profile_defaults()
        self.assertEqual(derived["water-v1"]["YOLO_CONFIDENCE"], "0.10")
        self.assertEqual(derived["road-v1"]["YOLO_CONFIDENCE"], "0.15")
        self.assertEqual(derived["water-v1"]["YOLO_IMAGE_SIZE"], "960")
        self.assertEqual(derived["water-v1"]["SAMPLE_FPS"], "10")
        self.assertEqual(derived["road-v1"]["SAMPLE_FPS"], "10")
        self.assertEqual(derived["water-v1"]["MODEL_NAME"], "models/yolo26x.pt")
        self.assertEqual(derived["road-v1"]["YOLO_TRACKER"], "bytetrack.yaml")

    def test_configure_script_derives_and_fails_closed_without_hardcoded_values(self) -> None:
        source = CONFIGURE.read_text(encoding="utf-8")
        self.assertIn("import analytics_profiles", source)
        self.assertIn("SystemExit", source)
        self.assertIn("ERROR", source)
        for value in ("models/yolo26x.pt", "bytetrack.yaml", "0.10", "0.15", "960"):
            self.assertNotIn(f'"{value}"', source)

    def test_existing_env_value_overrides_derived_default(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            install_root = root / "install"
            config_root = install_root / "shared/config"
            config_root.mkdir(parents=True)
            worker_env = config_root / "worker.env"
            worker_env.write_text(
                "SEA_SPEED_API_URL=http://10.123.239.101:18080/api/cam1/state\n"
                "SEA_SPEED_API_TOKEN=[redacted:generic-assignment]\n"
                "SAMPLE_FPS=7.5\n",
                encoding="utf-8",
            )
            os.chmod(worker_env, 0o600)
            road_env = config_root / "road-worker.env"
            road_env.write_text("SAMPLE_FPS=12.5\n", encoding="utf-8")
            os.chmod(road_env, 0o600)
            catalog = root / "camera-preview-catalog.json"
            catalog.write_text(
                json.dumps(
                    {
                        "schema": "sea_speed_camera_preview_catalog_v1",
                        "cameras": [
                            {
                                "camera_id": "road1",
                                "source": "rtsp://10.123.239.102:8555/preview_road1",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(CONFIGURE),
                    "--install-root",
                    str(install_root),
                    "--preview-catalog",
                    str(catalog),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            water_values = configure.read_env(worker_env)
            road_values = configure.read_env(road_env)
            self.assertEqual(water_values["SAMPLE_FPS"], "7.5")
            self.assertEqual(road_values["SAMPLE_FPS"], "12.5")
            self.assertEqual(water_values["YOLO_CONFIDENCE"], "0.10")
            self.assertEqual(road_values["YOLO_CONFIDENCE"], "0.15")
            self.assertEqual(stat.S_IMODE(road_env.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
