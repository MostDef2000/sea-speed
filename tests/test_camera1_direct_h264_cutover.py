from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts/operations/nginx_cam1_direct_h264.py"
DEPLOY = ROOT / "deploy/vps/camera1-direct-h264-cutover.sh"
DOC = ROOT / "docs/operations/CAMERA1_DIRECT_H264_CUTOVER.md"

spec = importlib.util.spec_from_file_location("nginx_cam1_direct_h264", RENDERER)
assert spec and spec.loader
nginxcut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nginxcut)

BASE = r'''
server {
    listen 443 ssl;
    server_name mostdef.ru www.mostdef.ru;

    location /cams/hls/ {
        auth_basic "Sea Speed";
        auth_basic_user_file /etc/nginx/.htpasswd;
        proxy_pass http://127.0.0.1:8888/;
        proxy_buffering off;
    }

    location /sea-speed/ {
        try_files $uri $uri/ =404;
    }
}
'''


class Camera1DirectH264CutoverTests(unittest.TestCase):
    def test_renderer_creates_exact_cam1_precedence_and_preserves_generic_route(self) -> None:
        rendered = nginxcut.render(BASE)
        nginxcut.verify(rendered)
        self.assertIn("location ^~ /cams/hls/cam1/ {", rendered)
        self.assertIn("proxy_pass http://127.0.0.1:18889/cam1/;", rendered)
        self.assertIn("proxy_cache off;", rendered)
        self.assertIn('add_header Cache-Control "no-store, no-cache, must-revalidate" always;', rendered)
        self.assertIn('auth_basic "Sea Speed";', rendered)
        self.assertIn("auth_basic_user_file /etc/nginx/.htpasswd;", rendered)
        self.assertIn("location /cams/hls/ {", rendered)
        self.assertIn("proxy_pass http://127.0.0.1:8888/;", rendered)

    def test_renderer_is_idempotent(self) -> None:
        first = nginxcut.render(BASE)
        second = nginxcut.render(first)
        self.assertEqual(first, second)

    def test_renderer_replaces_unmanaged_exact_cam1_location(self) -> None:
        source = BASE.replace(
            "    location /cams/hls/ {",
            "    location ^~ /cams/hls/cam1/ { proxy_pass http://127.0.0.1:9999/; }\n\n    location /cams/hls/ {",
            1,
        )
        rendered = nginxcut.render(source)
        nginxcut.verify(rendered)
        self.assertNotIn("127.0.0.1:9999", rendered)
        self.assertEqual(rendered.count("location ^~ /cams/hls/cam1/ {"), 1)

    def test_renderer_requires_single_target_server_and_generic_location(self) -> None:
        with self.assertRaises(nginxcut.ConfigError):
            nginxcut.render(BASE.replace("mostdef.ru", "example.invalid"))
        duplicate = BASE + BASE
        with self.assertRaises(nginxcut.ConfigError):
            nginxcut.render(duplicate)

    def test_cli_render_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "site.conf"
            candidate = root / "candidate.conf"
            source.write_text(BASE, encoding="utf-8")
            rendered = subprocess.run(
                ["python3", str(RENDERER), "render", "--config", str(source), "--output", str(candidate)],
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn("CAM1_DIRECT_H264_RENDER=PASS", rendered.stdout)
            verified = subprocess.run(
                ["python3", str(RENDERER), "verify", "--config", str(candidate)],
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn("CAM1_DIRECT_H264_CONFIG=PASS", verified.stdout)

    def test_deploy_contract_is_narrow_and_no_automatic_rollback(self) -> None:
        subprocess.run(["bash", "-n", str(DEPLOY)], check=True)
        source = DEPLOY.read_text(encoding="utf-8")
        self.assertIn("127.0.0.1:18889/cam1/index.m3u8", source)
        self.assertIn("MEDIAMTX_BROWSER_PATH=BYPASSED", source)
        self.assertIn("PLAYLIST_CACHE=DISABLED", source)
        self.assertIn("AI_CHANGED=NO", source)
        self.assertIn("AUTOMATIC_ROLLBACK=NO", source)
        self.assertNotIn("systemctl restart sea-speed-worker", source)
        self.assertNotIn("systemctl start sea-speed-worker", source)
        self.assertNotIn("systemctl restart mediamtx", source)
        self.assertNotIn("systemctl stop mediamtx", source)

    def test_documentation_keeps_product_acceptance_simple(self) -> None:
        source = DOC.read_text(encoding="utf-8")
        self.assertIn("/cams/hls/cam1/index.m3u8", source)
        self.assertIn("VPS MediaMTX", source)
        self.assertIn("H264 1280x720 at 15 fps", source)
        self.assertIn("LIVE CAMERA", source)
        self.assertIn("Automatic rollback is not performed", source)


if __name__ == "__main__":
    unittest.main()
