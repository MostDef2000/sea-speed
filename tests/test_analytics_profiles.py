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


class AnalyticsProfilesTests(unittest.TestCase):
    def test_profile_defaults_are_exact(self) -> None:
        water = profiles.get_profile("water-v1")
        road = profiles.get_profile("road-v1")
        for profile, camera, domain in ((water, "cam1", "water"), (road, "road1", "road")):
            self.assertEqual(profile.default_camera_id, camera)
            self.assertEqual(profile.domain, domain)
            self.assertEqual(profile.model_name, "models/yolo26x.pt")
            self.assertEqual(profile.image_size, 960)
            self.assertEqual(profile.confidence, 0.15)
            self.assertEqual(profile.tracker, "bytetrack.yaml")
            self.assertEqual(profile.sample_fps, 5.0)
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

    def test_frontends_have_synchronized_road_navigation_and_no_private_source(self) -> None:
        paths = [
            ROOT / "frontend/sea-speed/index.html",
            ROOT / "frontend/sea-speed/objects/index.html",
            ROOT / "frontend/sea-speed/cameras/index.html",
            ROOT / "frontend/sea-speed/road/index.html",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn('/sea-speed/road/', text, path)
            self.assertNotRegex(text, r'rtsp://[^\s"\']+:[^\s"\']+@')
        road = paths[-1].read_text(encoding="utf-8")
        self.assertIn('CAMERA_ID="road1"', road)
        self.assertIn('/sea-speed/api/analytics/road1', road)
        self.assertIn('/sea-speed/api/cameras/road1/preview/start', road)
        self.assertNotIn('/api/worker/control', road)
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
        configure = files[1].read_text(encoding="utf-8")
        self.assertIn('camera_id") == "road1"', configure)
        self.assertIn('"/preview_road1"', configure)
        self.assertIn('worker.env must be mode 600', configure)

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
