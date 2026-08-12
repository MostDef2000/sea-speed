from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "api/app/main.py").read_text(encoding="utf-8-sig")
OPERATOR = (ROOT / "frontend/sea-speed/index.html").read_text(encoding="utf-8-sig")
CAMERAS = (ROOT / "frontend/sea-speed/cameras/index.html").read_text(encoding="utf-8-sig")
RELAY = (ROOT / "deploy/worker/ubuntu/camera-preview-relay.sh").read_text(encoding="utf-8-sig")
DEPLOY = (ROOT / "deploy/vps/deploy.sh").read_text(encoding="utf-8-sig")
SPEC = (ROOT / "specs/002-camera-preview-gallery/spec.md").read_text(encoding="utf-8-sig")
PLAN = (ROOT / "specs/002-camera-preview-gallery/plan.md").read_text(encoding="utf-8-sig")
TASKS = (ROOT / "specs/002-camera-preview-gallery/tasks.md").read_text(encoding="utf-8-sig")
QUICKSTART = (ROOT / "specs/002-camera-preview-gallery/quickstart.md").read_text(encoding="utf-8-sig")


class CameraPreviewGalleryTests(unittest.TestCase):
    def test_python_and_shell_sources_are_structurally_valid(self) -> None:
        ast.parse(API)
        self.assertTrue(RELAY.startswith("#!/usr/bin/env bash\nset -Eeuo pipefail"))
        self.assertTrue(DEPLOY.startswith("#!/usr/bin/env bash\nset -Eeuo pipefail"))

    def test_operator_preserves_objects_link_and_adds_cameras_link(self) -> None:
        self.assertRegex(
            OPERATOR,
            r'<a\s+class="objects-link"\s+href="/sea-speed/objects/">Реестр объектов</a>',
        )
        self.assertRegex(
            OPERATOR,
            r'<a\s+class="objects-link cameras-link"\s+href="/sea-speed/cameras/">Камеры</a>',
        )
        for marker in (
            'const HLS_URL = "/cams/hls/cam1/index.m3u8";',
            'const STATE_URL = "/sea-speed/api/cam1/state";',
            'data-layout="primary-camera"',
            'data-layout="clean-live"',
            'id="roiCanvas"',
            'id="speedLinesCanvas"',
        ):
            self.assertIn(marker, OPERATOR)

    def test_gallery_uses_runtime_catalog_and_has_no_native_rtsp_source(self) -> None:
        for marker in (
            'const CAMERAS_URL="/sea-speed/api/cameras"',
            'const PREVIEW_STATUS_URL="/sea-speed/api/cameras/preview"',
            'const PREVIEW_STOP_URL="/sea-speed/api/cameras/preview/stop"',
            '/sea-speed/api/cameras/${encodeURIComponent(cameraId)}/preview/start',
            'method:"POST"',
            'credentials:"same-origin"',
            'id="cameraGrid"',
        ):
            self.assertIn(marker, CAMERAS)
        self.assertNotIn("rtsp://", CAMERAS)
        self.assertNotRegex(CAMERAS, r"192\.168\.88\.\d+")

    def test_gallery_does_not_autostart_preview(self) -> None:
        self.assertIn("loadCatalog();", CAMERAS)
        self.assertNotIn("startPreview(cameras[0]", CAMERAS)
        self.assertNotIn("autoplayPreview", CAMERAS)
        self.assertIn('if(active?.hls_url)attachActivePlayer()', CAMERAS)

    def test_gallery_batch_preview_is_sequential_and_operator_controllable(self) -> None:
        for marker in (
            'id="previewAllButton"',
            'id="stopAllButton"',
            'id="batchProgress"',
            'async function runPreviewAll()',
            'for(let index=0;index<cameras.length;index++)',
            'await startPreview(camera.camera_id,{batchToken:token})',
            'await waitForVideoFrame(activeVideo)',
            'await waitForStableVideoFrame(activeVideo)',
            'await stopPreview({preserveFrame:true})',
            'async function stopAllPreviews()',
            'batchGeneration++',
        ):
            self.assertIn(marker, CAMERAS)
        self.assertNotIn("Promise.all(cameras", CAMERAS)
        self.assertNotIn("max_active: 33", CAMERAS)

    def test_gallery_batch_snapshot_waits_for_actual_playback_progress(self) -> None:
        for marker in (
            'const BATCH_STABLE_ADVANCE_SEC=3;',
            'const BATCH_STABLE_TIMEOUT_MS=12000;',
            'function waitForStableVideoFrame(video,{minAdvanceSec=BATCH_STABLE_ADVANCE_SEC,timeoutMs=BATCH_STABLE_TIMEOUT_MS}={})',
            'video.currentTime-baseline>=minAdvanceSec',
            'requestAnimationFrame(check)',
            'const stable=await waitForStableVideoFrame(activeVideo);',
            'cameraErrors.set(camera.camera_id,"Видео не успело стабилизироваться")',
        ):
            self.assertIn(marker, CAMERAS)
        self.assertNotIn('const BATCH_FRAME_DWELL_MS=1200;', CAMERAS)
        self.assertNotIn('await delay(BATCH_FRAME_DWELL_MS);', CAMERAS)

    def test_gallery_retains_last_frame_only_in_page_memory(self) -> None:
        for marker in (
            '<canvas data-snapshot',
            'const snapshotIds=new Set()',
            'function captureActiveFrame()',
            'context.drawImage(activeVideo,0,0,width,height)',
            'snapshotIds.add(active.camera_id)',
            'destroyPlayer({capture=true}={})',
            'async function stopPreview({preserveFrame=true}={})',
        ):
            self.assertIn(marker, CAMERAS)
        for forbidden in (
            "localStorage",
            "sessionStorage",
            "indexedDB",
            "caches.open",
            "CacheStorage",
        ):
            self.assertNotIn(forbidden, CAMERAS)
        self.assertNotIn("snapshot_url", CAMERAS)

    def test_gallery_failed_batch_camera_does_not_abort_remaining_catalog(self) -> None:
        self.assertIn('cameraErrors.set(cameraId,error.message)', CAMERAS)
        self.assertIn('if(!started||!activeVideo)continue;', CAMERAS)
        self.assertIn('cameraErrors.set(camera.camera_id,"Видео не успело показать кадр")', CAMERAS)
        self.assertIn('cameraErrors.set(camera.camera_id,"Видео не успело стабилизироваться")', CAMERAS)

    def test_api_exposes_catalog_only_start_stop_status_contract(self) -> None:
        for marker in (
            '@app.get("/api/cameras")',
            '@app.get("/api/cameras/preview")',
            '@app.post("/api/cameras/{camera_id}/preview/start")',
            '@app.post("/api/cameras/preview/stop")',
            'camera = next((entry for entry in cameras if entry["camera_id"] == camera_id), None)',
            '"preview_policy": {"max_active": 1, "ttl_sec": CAMERA_PREVIEW_TTL_SEC}',
        ):
            self.assertIn(marker, API)
        self.assertNotIn('payload.get("source")', API)
        self.assertNotIn('payload.get("rtsp_url")', API)

    def test_api_never_returns_private_source_field(self) -> None:
        public_state_start = API.index("def camera_preview_public_state")
        public_state_end = API.index("def camera_preview_pid_matches", public_state_start)
        public_state = API[public_state_start:public_state_end]
        self.assertNotIn('"source"', public_state)
        get_start = API.index("def get_cameras")
        get_end = API.index('@app.get("/api/cameras/preview")', get_start)
        public_catalog = API[get_start:get_end]
        self.assertNotIn('camera["source"]', public_catalog)

    def test_api_relay_source_is_private_credential_free_and_identity_bound(self) -> None:
        start = API.index("def validate_camera_preview_source")
        end = API.index("def load_camera_preview_catalog", start)
        source = API[start:end]
        for marker in (
            'parsed.scheme.lower() != "rtsp"',
            'CAMERA_PREVIEW_RFC1918',
            'parsed.username is not None or parsed.password is not None',
            'parsed.query or parsed.fragment',
            'f"/preview_{camera_id}"',
        ):
            self.assertIn(marker, source)

    def test_api_preview_is_one_process_bounded_h264_hls(self) -> None:
        for marker in (
            'CAMERA_PREVIEW_TTL_SEC = max(',
            'min(int(os.environ.get("SEA_SPEED_CAMERA_PREVIEW_TTL_SEC", "120")), 600)',
            'terminate_camera_preview_locked()',
            'subprocess.Popen(',
            'stdout=subprocess.DEVNULL',
            'stderr=subprocess.DEVNULL',
            '"scale=640:-2,fps=8"',
            '"-an"',
            '"libx264"',
            '"baseline"',
            '"-hls_segment_type"',
            '"fmp4"',
            'str(CAMERA_PREVIEW_TTL_SEC)',
        ):
            self.assertIn(marker, API)
        self.assertNotIn("shell=True", API)
        self.assertIn('hls_url = f"/sea-speed/media/camera-preview/{session_id}/index.m3u8"', API)
        self.assertIn('output_dir.mkdir(mode=0o755, parents=False, exist_ok=False)', API)
        self.assertNotIn('output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)', API)

    def test_api_pid_cleanup_is_bound_to_exact_managed_output(self) -> None:
        start = API.index("def camera_preview_pid_matches")
        end = API.index("def cleanup_camera_preview_media", start)
        source = API[start:end]
        self.assertIn('Path(CAMERA_PREVIEW_FFMPEG_BIN).name in cmdline', source)
        self.assertIn('expected_playlist in cmdline', source)
        self.assertIn("CAMERA_PREVIEW_SESSION_RE.fullmatch", API)

    def test_ubuntu_preview_relay_is_separate_source_on_demand_and_private(self) -> None:
        for marker in (
            'service_name="sea-speed-camera-preview-relay.service"',
            'cam1_service="sea-speed-stream.service"',
            'sourceOnDemand: yes',
            'sourceOnDemandCloseAfter: 2s',
            'rtspTransports: [tcp]',
            r'path: \"~^preview_[a-z0-9._-]+$\"',
            'CAM1_RELAY_CHANGED=NO',
            'AI_WORKER_CHANGED=NO',
            'SECRETS_DISPLAYED=NO',
        ):
            self.assertIn(marker, RELAY)
        self.assertNotIn('systemctl restart "$cam1_service"', RELAY)
        self.assertNotIn('systemctl restart "$ai_service"', RELAY)
        self.assertIn('chmod 0750 "$state_root" "$active_root"', RELAY)

    def test_ubuntu_inventory_is_protected_and_catalog_is_sanitized(self) -> None:
        for marker in (
            'inventory mode must be 600',
            'inventory must be root-owned',
            'sea_speed_camera_preview_inventory_v1',
            'sea_speed_camera_preview_catalog_v1',
            'if parsed.username is None:',
            'source": f"rtsp://{relay_host}:{relay_port}/{path_name}"',
        ):
            self.assertIn(marker, RELAY)
        self.assertNotRegex(RELAY, r"192\.168\.88\.\d+")

    def test_vps_deploy_installs_rolls_back_and_smokes_cameras_page(self) -> None:
        for marker in (
            'CAMERAS_FRONTEND_TARGET="${SEA_SPEED_CAMERAS_FRONTEND_TARGET:-/var/www/mostdef.ru/sea-speed/cameras/index.html}"',
            'CAMERAS_FRONTEND_URL="${SEA_SPEED_CAMERAS_FRONTEND_URL:-https://mostdef.ru/sea-speed/cameras/}"',
            'frontend/sea-speed/cameras/index.html',
            'frontend/sea-speed/cameras/.absent',
            'ensure_current_release_has_cameras_frontend',
            'verify_url "Cameras frontend" "$CAMERAS_FRONTEND_URL"',
            '"cameras_frontend_release_state"',
        ):
            self.assertIn(marker, DEPLOY)

    def test_sdd_links_extension_issue_and_preserves_camera1_and_storage_boundary(self) -> None:
        for doc in (SPEC, PLAN, TASKS, QUICKSTART):
            self.assertIn("#109", doc)
        self.assertIn("/cams/hls/cam1/index.m3u8", SPEC)
        self.assertIn("Camera 1", PLAN)
        self.assertIn("one active", SPEC.lower())
        self.assertIn("localStorage", SPEC)
        self.assertIn("sequential", PLAN.lower())


if __name__ == "__main__":
    unittest.main()
