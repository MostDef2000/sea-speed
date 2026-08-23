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

CONFIGURE = ROOT / "deploy/worker/ubuntu/configure-analytics-profiles.py"
configure_spec = importlib.util.spec_from_file_location("configure_analytics_profiles", CONFIGURE)
assert configure_spec and configure_spec.loader
configure = importlib.util.module_from_spec(configure_spec)
configure_spec.loader.exec_module(configure)


class AnalyticsProfilesTests(unittest.TestCase):
    def test_profile_defaults_are_exact(self) -> None:
        water = profiles.get_profile("water-v1")
        road = profiles.get_profile("road-v1")
        self.assertEqual(profiles.DEFAULT_PROFILE, "water-v1")
        self.assertEqual(profiles.get_profile(), water)
        for profile, camera, domain in ((water, "cam1", "water"), (road, "road1", "road")):
            self.assertEqual(profile.default_camera_id, camera)
            self.assertEqual(profile.domain, domain)
            self.assertEqual(profile.model_name, "models/yolo26x.pt")
            self.assertEqual(profile.image_size, 960)
            self.assertEqual(profile.confidence, 0.15)
            self.assertEqual(profile.tracker, "bytetrack.yaml")
            self.assertEqual(profile.sample_fps, 10.0)
        self.assertEqual(set(profiles.PROFILES), {"water-v1", "road-v1"})

    def test_water_normalizes_boat_and_rejects_road_classes(self) -> None:
        self.assertEqual(
            profiles.normalize_model_class("boat", "water-v1"),
            {
                "analytics_profile": "water-v1",
                "domain": "water",
                "object_type": "vessel",
                "model_class": "boat",
                "class_name": "vessel",
            },
        )
        for raw in ("car", "truck", "bus", "motorcycle", "bicycle"):
            self.assertIsNone(profiles.normalize_model_class(raw, "water-v1"), raw)

    def test_road_accepts_only_road_baseline_classes(self) -> None:
        for raw in ("car", "truck", "bus", "motorcycle", "bicycle"):
            semantic = profiles.normalize_model_class(raw, "road-v1")
            self.assertIsNotNone(semantic)
            self.assertEqual(semantic["analytics_profile"], "road-v1")
            self.assertEqual(semantic["domain"], "road")
            self.assertEqual(semantic["object_type"], raw)
            self.assertEqual(semantic["model_class"], raw)
            self.assertEqual(semantic["class_name"], raw)
        self.assertIsNone(profiles.normalize_model_class("boat", "road-v1"))

    def test_unknown_profile_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            profiles.get_profile("unknown")

    def test_worker_and_ai_child_share_profile_boundary(self) -> None:
        worker = (ROOT / "worker/hls_motion_yolo_worker_events.py").read_text(encoding="utf-8")
        entry = (ROOT / "worker/ubuntu_worker_entrypoint.py").read_text(encoding="utf-8")
        child = (ROOT / "worker/ubuntu_ai_inference_worker.py").read_text(encoding="utf-8")
        for text in (worker, child):
            self.assertIn("normalize_model_class", text)
            self.assertIn("analytics_profile", text)
        self.assertIn("object_type", worker)
        self.assertIn("model_class", worker)
        self.assertIn("**semantic", child)
        self.assertIn('"--analytics-profile"', entry)
        self.assertIn('profile = get_profile', entry)
        self.assertNotIn('MODEL_NAME", "yolo11s.pt"', entry)

    def test_worker_separates_water_continuous_detection_from_road_motion_policy(self) -> None:
        worker = (ROOT / "worker/hls_motion_yolo_worker_events.py").read_text(encoding="utf-8")
        self.assertIn("def select_profile_detections(", worker)
        self.assertIn('profile.domain == "water"', worker)
        self.assertIn("filter_detections_by_motion(raw_detections, motion_boxes)", worker)
        self.assertIn("def water_event_candidates(", worker)
        self.assertIn('det.get("class_name") != "vessel"', worker)
        self.assertIn('profile.domain == "water":\n                for vessel in water_event_candidates', worker)

    def test_api_is_additive_and_camera_isolated(self) -> None:
        source = (ROOT / "api/app/main.py").read_text(encoding="utf-8")
        for route in (
            '/api/analytics/{camera_id}/state',
            '/api/analytics/{camera_id}/events',
            '/api/analytics/{camera_id}/roi',
            '/api/analytics/{camera_id}/speed-config',
            '/api/analytics/{camera_id}/speed-lines',
            '/api/analytics/{camera_id}/objects',
            '/api/objects',
            '/api/cam1/state',
            '/api/cam1/events',
            '/api/cam1/objects',
        ):
            self.assertIn(route, source)
        self.assertIn('"road1": {"analytics_profile": "road-v1", "domain": "road"}', source)
        self.assertIn('DATA_DIR / f"{camera_id}_{kind}.json"', source)
        self.assertIn("ALTER TABLE objects ADD COLUMN", source)
        for field in ("analytics_profile", "domain", "object_type", "model_class"):
            self.assertIn(field, source)

    def test_frontends_have_synchronized_road_navigation_and_bounded_road_control(self) -> None:
        paths = [
            ROOT / "frontend/sea-speed/index.html",
            ROOT / "frontend/sea-speed/objects/index.html",
            ROOT / "frontend/sea-speed/cameras/index.html",
            ROOT / "frontend/sea-speed/road/index.html",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r'rtsp://[^\s"\']+:[^\s"\']+@')
        for path in paths[:-1]:
            self.assertIn('/sea-speed/road/', path.read_text(encoding="utf-8"), path)
        road = paths[-1].read_text(encoding="utf-8")
        self.assertIn('class="objects-link road-link active" href="/sea-speed/">Вода</a>', road)
        self.assertNotIn('class="objects-link road-link active" href="/sea-speed/road/">Дорога</a>', road)
        self.assertIn('CAMERA_ID="road1"', road)
        self.assertIn('/sea-speed/api/analytics/road1', road)
        self.assertIn('/sea-speed/api/cameras/road1/preview/start', road)
        self.assertIn('const WORKER_CONTROL_URL="/sea-speed/api/worker/control/road1"', road)
        self.assertEqual(road.count('/sea-speed/api/worker/control/road1'), 1)
        self.assertNotIn('/v1/road1/', road)
        self.assertNotIn('10.123.239.101', road)
        self.assertNotIn('SEA_SPEED_API_TOKEN', road)
        objects = paths[1].read_text(encoding="utf-8")
        self.assertIn('const OBJECTS_URL="/sea-speed/api/objects"', objects)
        self.assertIn('name="camera_id"', objects)
        self.assertIn('name="domain"', objects)

    def test_runtime_assets_do_not_embed_protected_road_source(self) -> None:
        files = [
            ROOT / "deploy/worker/ubuntu/road-worker.env.example",
            ROOT / "deploy/worker/ubuntu/configure-analytics-profiles.py",
            ROOT / "deploy/worker/ubuntu/sea-speed-road-worker.service.template",
        ]
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"rtsp://[^\s\"']+:[^\s\"']+@")
        configure_source = files[1].read_text(encoding="utf-8")
        road_example = files[0].read_text(encoding="utf-8")
        self.assertIn('camera_id") == "road1"', configure_source)
        self.assertIn('"/preview_road1"', configure_source)
        self.assertIn('worker.env must be mode 600', configure_source)
        self.assertNotIn("https://mostdef.ru/sea-speed/api/analytics/road1", road_example)
        self.assertIn("private Worker->VPS M2M endpoint", road_example)

    def test_road_worker_api_urls_derive_only_from_exact_private_cam1_m2m_endpoint(self) -> None:
        state_url, event_url = configure.road_worker_api_urls(
            {"SEA_SPEED_API_URL": "http://10.123.239.101:18080/api/cam1/state"}
        )
        self.assertEqual(state_url, "http://10.123.239.101:18080/api/analytics/road1/state")
        self.assertEqual(event_url, "http://10.123.239.101:18080/api/analytics/road1/events")
        for invalid in (
            "https://mostdef.ru/sea-speed/api/cam1/state",
            "http://user:pass@10.123.239.101:18080/api/cam1/state",
            "http://203.0.113.10:18080/api/cam1/state",
            "http://127.0.0.1:18080/api/cam1/state",
            "http://10.123.239.101/api/cam1/state",
            "http://10.123.239.101:18080/api/cam1/events",
            "http://10.123.239.101:18080/api/cam1/state?redirect=1",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(SystemExit):
                    configure.road_worker_api_urls({"SEA_SPEED_API_URL": invalid})

    def test_configure_profiles_writes_private_road_m2m_urls_and_mode_600(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            install_root = root / "install"
            config_root = install_root / "shared/config"
            config_root.mkdir(parents=True)
            worker_env = config_root / "worker.env"
            worker_env.write_text(
                "SEA_SPEED_API_URL=http://10.123.239.101:18080/api/cam1/state\n"
                "SEA_SPEED_API_TOKEN=test-token\n"
                "FRAME_WIDTH=704\n"
                "FRAME_HEIGHT=576\n",
                encoding="utf-8",
            )
            os.chmod(worker_env, 0o600)
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
            result = subprocess.run(
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
            self.assertIn("ROAD_API=protected_private_worker_ingress", result.stdout)
            road_env = config_root / "road-worker.env"
            values = configure.read_env(road_env)
            self.assertEqual(values["SEA_SPEED_API_URL"], "http://10.123.239.101:18080/api/analytics/road1/state")
            self.assertEqual(values["SEA_SPEED_EVENT_API_URL"], "http://10.123.239.101:18080/api/analytics/road1/events")
            self.assertEqual(values["HLS_URL"], "rtsp://10.123.239.102:8555/preview_road1")
            self.assertEqual(stat.S_IMODE(road_env.stat().st_mode), 0o600)
            self.assertNotIn("mostdef.ru", road_env.read_text(encoding="utf-8"))

    def test_model_preparation_is_digest_bound_cuda_fail_closed(self) -> None:
        source = (ROOT / "deploy/worker/ubuntu/prepare-yolo-model.py").read_text(encoding="utf-8")
        self.assertIn("expected-sha256", source)
        self.assertIn("torch.cuda.is_available()", source)
        self.assertIn("YOLO26x CUDA load/self-test failed", source)
        self.assertIn("imgsz=960", source)
        self.assertIn("conf=0.15", source)
        self.assertNotIn("download", source.lower())
        self.assertNotIn("yolo11", source.lower())

    def test_exact_artifacts_include_profiles_and_road_but_not_model_binaries(self) -> None:
        build = (ROOT / "scripts/quality/build_exact_artifacts.py").read_text(encoding="utf-8")
        validate = (ROOT / "scripts/quality/validate_exact_artifacts.py").read_text(encoding="utf-8")
        for marker in (
            "frontend/sea-speed/road/index.html",
            "worker/analytics_profiles.py",
            "deploy/worker/ubuntu/sea-speed-road-worker.service.template",
            "deploy/worker/ubuntu/configure-analytics-profiles.py",
            "deploy/worker/ubuntu/prepare-yolo-model.py",
        ):
            self.assertIn(marker, build)
            self.assertIn(marker, validate)
        for suffix in ('".pt"', '".onnx"', '".engine"'):
            self.assertIn(suffix, build)
            self.assertIn(suffix, validate)

    def test_vps_deployer_tracks_road_frontend_transactionally(self) -> None:
        source = (ROOT / "deploy/vps/deploy.sh").read_text(encoding="utf-8")
        for marker in (
            "ROAD_FRONTEND_TARGET",
            "ROAD_FRONTEND_URL",
            "ensure_current_release_has_road_frontend",
            "road_frontend_release_state",
            'verify_public_url "Road frontend"',
        ):
            self.assertIn(marker, source)

    def test_ubuntu_service_is_isolated_but_shares_runtime_and_models(self) -> None:
        unit = (ROOT / "deploy/worker/ubuntu/sea-speed-road-worker.service.template").read_text(encoding="utf-8")
        install = (ROOT / "deploy/worker/ubuntu/install-systemd.sh").read_text(encoding="utf-8")
        self.assertIn("Environment=ANALYTICS_PROFILE=road-v1", unit)
        self.assertIn("Environment=CAMERA_ID=road1", unit)
        self.assertIn("road-worker-heartbeat.json", unit)
        self.assertIn("__RUNTIME_ID__/venv/bin/python", unit)
        self.assertIn('ln -sfn "$install_root/shared/models" "$road_runtime_root/models"', install)
        self.assertIn('road-worker.env', install)


if __name__ == "__main__":
    unittest.main()
