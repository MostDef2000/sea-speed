from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts/operations/nginx_cam1_direct_h264.py"
AUTH_RENDERER = ROOT / "scripts/operations/nginx_sea_speed_auth.py"
DEPLOY = ROOT / "deploy/vps/camera1-direct-h264-cutover.sh"
DOC = ROOT / "docs/operations/CAMERA1_DIRECT_H264_CUTOVER.md"

cam_spec = importlib.util.spec_from_file_location("nginx_cam1_direct_h264", RENDERER)
assert cam_spec and cam_spec.loader
nginxcut = importlib.util.module_from_spec(cam_spec)
cam_spec.loader.exec_module(nginxcut)

auth_spec = importlib.util.spec_from_file_location("nginx_sea_speed_auth", AUTH_RENDERER)
assert auth_spec and auth_spec.loader
nginxauth = importlib.util.module_from_spec(auth_spec)
auth_spec.loader.exec_module(nginxauth)

BASE = r'''
server {
    listen 443 ssl;
    server_name mostdef.ru www.mostdef.ru;

    # SEA-SPEED-CAM1-DIRECT-H264-BEGIN
    location ^~ /cams/hls/cam1/ {
        auth_basic "Sea Speed";
        auth_basic_user_file /etc/nginx/.htpasswd;
        proxy_pass http://127.0.0.1:18889/cam1/;
    }
    # SEA-SPEED-CAM1-DIRECT-H264-END

    location /cams/hls/ {
        auth_basic "Sea Speed";
        auth_basic_user_file /etc/nginx/.htpasswd;
        proxy_pass http://127.0.0.1:8888/;
        proxy_buffering off;
    }

    location /sea-speed/ {
        try_files $uri $uri/ =404;
    }

    location /sea-speed/api/ {
        proxy_pass http://127.0.0.1:8000/api/;
    }

    location /sea-speed/media/ {
        alias /opt/sea-speed-api/media/;
    }
}
'''

PRIVATE_LISTEN = "10.123.239.1:18080"
PRIVATE_PEER = "10.123.239.102"


class Camera1DirectH264CutoverTests(unittest.TestCase):
    def test_renderer_moves_cam1_under_sea_speed_and_preserves_h264_upstream(self) -> None:
        rendered = nginxcut.render(BASE)
        nginxcut.verify(rendered)
        self.assertIn("location ^~ /sea-speed/media/cam1/ {", rendered)
        self.assertIn("proxy_pass http://127.0.0.1:18889/cam1/;", rendered)
        self.assertIn("proxy_cache off;", rendered)
        self.assertIn('add_header Cache-Control "no-store, no-cache, must-revalidate" always;', rendered)
        self.assertNotIn("location ^~ /cams/hls/cam1/ {", rendered)
        self.assertIn("location /cams/hls/ {", rendered)
        managed = rendered.split(nginxcut.BEGIN, 1)[1].split(nginxcut.END, 1)[0]
        self.assertNotIn("auth_basic", managed)
        self.assertNotIn("127.0.0.1:8888", managed)

    def test_renderer_is_idempotent(self) -> None:
        first = nginxcut.render(BASE)
        second = nginxcut.render(first)
        self.assertEqual(first, second)

    def test_renderer_requires_single_sea_speed_parent_location(self) -> None:
        with self.assertRaises(nginxcut.ConfigError):
            nginxcut.render(BASE.replace("location /sea-speed/ {", "location /operator/ {", 1))
        duplicate = BASE.replace(
            "    location /sea-speed/ {",
            "    location /sea-speed/ { try_files $uri =404; }\n\n    location /sea-speed/ {",
            1,
        )
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
            self.assertIn("CAM1_PROTECTED_H264_RENDER=PASS", rendered.stdout)
            verified = subprocess.run(
                ["python3", str(RENDERER), "verify", "--config", str(candidate)],
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn("CAM1_PROTECTED_H264_CONFIG=PASS", verified.stdout)

    def test_combined_auth_render_protects_new_cam1_and_retires_all_cams(self) -> None:
        media_candidate = nginxcut.render(BASE)
        final = nginxauth.render(
            media_candidate,
            worker_private_listen=PRIVATE_LISTEN,
            worker_private_peer=PRIVATE_PEER,
        )
        nginxcut.verify(final)
        nginxauth.verify(
            final,
            worker_private_listen=PRIVATE_LISTEN,
            worker_private_peer=PRIVATE_PEER,
        )
        managed = final.split(nginxcut.BEGIN, 1)[1].split(nginxcut.END, 1)[0]
        self.assertIn("auth_request /outpost.goauthentik.io/auth/nginx;", managed)
        self.assertIn("/sea-speed/media/cam1/", managed)
        self.assertNotIn("/cams/hls/cam1/", final)
        self.assertIn("location ^~ /cams/ {", final)

    def test_standalone_deploy_is_read_only_and_activation_is_retired(self) -> None:
        subprocess.run(["bash", "-n", str(DEPLOY)], check=True)
        source = DEPLOY.read_text(encoding="utf-8")
        self.assertIn("STANDALONE_ACTIVATION=RETIRED", source)
        self.assertIn("sea-speed-auth-cutover.sh", source)
        self.assertIn("PRODUCTION_MUTATION=NO", source)
        self.assertNotIn("systemctl reload nginx.service", source)
        self.assertNotIn("mv -f", source)
        self.assertNotIn("/cams/hls/cam1/index.m3u8", source)
        self.assertIn("/sea-speed/media/cam1/index.m3u8", source)

    def test_documentation_records_issue_115_security_migration(self) -> None:
        source = DOC.read_text(encoding="utf-8")
        self.assertIn("Issue #115", source)
        self.assertIn("/sea-speed/media/cam1/index.m3u8", source)
        self.assertIn("127.0.0.1:18889/cam1/", source)
        self.assertIn("sea-speed-auth-cutover.sh", source)
        self.assertIn("standalone", source.lower())
        self.assertNotIn("public Camera 1 identity remains", source)


if __name__ == "__main__":
    unittest.main()
