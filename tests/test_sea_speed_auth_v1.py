from __future__ import annotations

import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts/operations/nginx_sea_speed_auth.py"
CUTOVER = ROOT / "deploy/vps/sea-speed-auth-cutover.sh"
VPS_DEPLOY = ROOT / "deploy/vps/deploy.sh"
COMPOSE = ROOT / "deploy/vps/authentik/compose.yml"
ENV_EXAMPLE = ROOT / "deploy/vps/authentik/env.example"
BLUEPRINT = ROOT / "deploy/vps/authentik/blueprints/sea-speed-auth-v1.yaml"
AUTH_DOC = ROOT / "deploy/vps/authentik/README.md"
OPS_DOC = ROOT / "docs/operations/SEA_SPEED_AUTH_V1.md"
SPEC = ROOT / "specs/004-sea-speed-auth-v1/spec.md"
PLAN = ROOT / "specs/004-sea-speed-auth-v1/plan.md"
TASKS = ROOT / "specs/004-sea-speed-auth-v1/tasks.md"
QUICKSTART = ROOT / "specs/004-sea-speed-auth-v1/quickstart.md"

spec = importlib.util.spec_from_file_location("nginx_sea_speed_auth", RENDERER)
assert spec and spec.loader
nginxauth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nginxauth)

BASE = r'''
server {
    listen 80;
    server_name mostdef.ru www.mostdef.ru;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl;
    server_name mostdef.ru www.mostdef.ru;

    location / {
        try_files $uri $uri/ =404;
    }

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
    }

    location /sea-speed/ {
        auth_basic "Sea Speed";
        auth_basic_user_file /etc/nginx/.htpasswd;
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


class SeaSpeedAuthV1Tests(unittest.TestCase):
    def test_renderer_retires_cams_and_protects_every_sea_speed_location(self) -> None:
        rendered = nginxauth.render(
            BASE,
            worker_private_listen=PRIVATE_LISTEN,
            worker_private_peer=PRIVATE_PEER,
        )
        nginxauth.verify(
            rendered,
            worker_private_listen=PRIVATE_LISTEN,
            worker_private_peer=PRIVATE_PEER,
        )
        self.assertNotIn("/cams/hls/cam1/", rendered)
        self.assertNotIn("auth_basic \"Sea Speed\"", rendered)
        self.assertIn("location = /cams {", rendered)
        self.assertIn("location ^~ /cams/ {", rendered)
        self.assertEqual(
            rendered.count("auth_request /outpost.goauthentik.io/auth/nginx;"),
            3,
        )
        self.assertIn(
            "proxy_pass http://127.0.0.1:9000/outpost.goauthentik.io;",
            rendered,
        )
        self.assertIn("location @goauthentik_proxy_signin", rendered)

    def test_renderer_is_idempotent(self) -> None:
        first = nginxauth.render(
            BASE,
            worker_private_listen=PRIVATE_LISTEN,
            worker_private_peer=PRIVATE_PEER,
        )
        second = nginxauth.render(
            first,
            worker_private_listen=PRIVATE_LISTEN,
            worker_private_peer=PRIVATE_PEER,
        )
        self.assertEqual(first, second)

    def test_private_worker_ingress_is_exact_peer_and_exact_endpoints(self) -> None:
        rendered = nginxauth.render(
            BASE,
            worker_private_listen=PRIVATE_LISTEN,
            worker_private_peer=PRIVATE_PEER,
        )
        self.assertIn("listen 10.123.239.1:18080;", rendered)
        self.assertIn("allow 10.123.239.102;", rendered)
        self.assertIn("deny all;", rendered)
        for path, method in (
            ("/api/cam1/state", "POST"),
            ("/api/cam1/events", "POST"),
            ("/api/cam1/roi", "GET"),
            ("/api/cam1/speed-config", "GET"),
            ("/api/cam1/speed-lines", "GET"),
        ):
            self.assertIn(f"location = {path} {{", rendered)
            self.assertIn(f"limit_except {method} {{ deny all; }}", rendered)
            self.assertIn(f"proxy_pass http://127.0.0.1:8000{path};", rendered)
        self.assertNotIn("location /api/ {", rendered)

    def test_renderer_rejects_public_or_network_wide_worker_addresses(self) -> None:
        for listen, peer in (
            ("203.0.113.10:18080", PRIVATE_PEER),
            (PRIVATE_LISTEN, "203.0.113.11"),
            ("127.0.0.1:18080", PRIVATE_PEER),
            (PRIVATE_LISTEN, "10.123.239.0/24"),
        ):
            with self.subTest(listen=listen, peer=peer):
                with self.assertRaises(nginxauth.ConfigError):
                    nginxauth.render(
                        BASE,
                        worker_private_listen=listen,
                        worker_private_peer=peer,
                    )

    def test_renderer_rejects_non_loopback_api_upstream(self) -> None:
        unsafe = BASE.replace(
            "proxy_pass http://127.0.0.1:8000/api/;",
            "proxy_pass http://10.0.0.9:8000/api/;",
            1,
        )
        with self.assertRaises(nginxauth.ConfigError):
            nginxauth.render(
                unsafe,
                worker_private_listen=PRIVATE_LISTEN,
                worker_private_peer=PRIVATE_PEER,
            )

    def test_cli_render_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "site.conf"
            candidate = root / "candidate.conf"
            source.write_text(BASE, encoding="utf-8")
            rendered = subprocess.run(
                [
                    "python3",
                    str(RENDERER),
                    "render",
                    "--config",
                    str(source),
                    "--output",
                    str(candidate),
                    "--worker-private-listen",
                    PRIVATE_LISTEN,
                    "--worker-private-peer",
                    PRIVATE_PEER,
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn("SEA_SPEED_AUTH_RENDER=PASS", rendered.stdout)
            verified = subprocess.run(
                [
                    "python3",
                    str(RENDERER),
                    "verify",
                    "--config",
                    str(candidate),
                    "--worker-private-listen",
                    PRIVATE_LISTEN,
                    "--worker-private-peer",
                    PRIVATE_PEER,
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn("SEA_SPEED_AUTH_CONFIG=PASS", verified.stdout)

    def test_authentik_runtime_is_pinned_private_and_has_no_docker_socket(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")
        self.assertEqual(compose.count("ghcr.io/goauthentik/server:2026.5.6"), 2)
        self.assertIn('"127.0.0.1:${AUTHENTIK_HTTP_PORT:-9000}:9000"', compose)
        self.assertNotIn("/var/run/docker.sock", compose)
        self.assertNotRegex(compose, r"(?m)^\s*-\s*[\"']?9000:9000")
        self.assertNotIn(":latest", compose)
        env_example = ENV_EXAMPLE.read_text(encoding="utf-8")
        for secret_key in (
            "PG_PASS=",
            "AUTHENTIK_SECRET_KEY=",
            "AUTHENTIK_BOOTSTRAP_PASSWORD=",
            "AUTHENTIK_EMAIL__PASSWORD=",
        ):
            self.assertIn(secret_key, env_example)
        self.assertNotRegex(env_example, r"(?m)^(PG_PASS|AUTHENTIK_SECRET_KEY)=\S+")

    def test_blueprint_is_invite_only_and_owner_totp_only(self) -> None:
        source = BLUEPRINT.read_text(encoding="utf-8")
        self.assertIn('blueprints.goauthentik.io/instantiate: "true"', source)
        for group in (
            "Sea Speed Owner",
            "Sea Speed Admin",
            "Sea Speed Operator",
            "Sea Speed Viewer",
        ):
            self.assertIn(f"name: {group}", source)
        owner_block = re.search(
            r"name: Sea Speed Owner.*?is_superuser: true",
            source,
            re.S,
        )
        self.assertIsNotNone(owner_block)
        self.assertEqual(source.count("continue_flow_without_invitation: false"), 3)
        self.assertIn("length_min: 15", source)
        self.assertIn("check_have_i_been_pwned: true", source)
        self.assertIn("check_zxcvbn: true", source)
        self.assertIn("not_configured_action: deny", source)
        self.assertIn("- totp", source)
        self.assertIn('name="Sea Speed Owner"', source)
        self.assertIn("session_duration: hours=12", source)
        self.assertNotIn("authentik_stages_authenticator_sms", source)
        self.assertNotIn("authentik_stages_authenticator_webauthn", source)

    def test_cutover_is_sha_bound_fail_closed_and_private_worker_scoped(self) -> None:
        subprocess.run(["bash", "-n", str(CUTOVER)], check=True)
        source = CUTOVER.read_text(encoding="utf-8")
        for marker in (
            "prepare --worker-private-listen IP:PORT --worker-private-peer IP",
            "activate --worker-private-listen IP:PORT --worker-private-peer IP --expected-sha256 SHA256",
            "--expected-sha256",
            "render_candidate",
            "nginx -t",
            "systemctl reload nginx.service",
            "AUTOMATIC_ROLLBACK=NO",
            "WORKER_RUNTIME_RECONFIGURATION_REQUIRED=YES",
            "/sea-speed/media/cam1/index.m3u8",
            "https://auth.mostdef.ru",
        ):
            self.assertIn(marker, source)
        self.assertIn("CANDIDATE_SHA256", source)
        self.assertIn("rendered candidate SHA256 changed since prepare", source)
        self.assertIn("/var/lib/sea-speed-auth-v1", source)
        self.assertNotIn("systemctl restart sea-speed-worker", source)
        self.assertNotIn("systemctl restart mediamtx", source)
        self.assertNotIn("auth_basic_user_file", source)

    def test_vps_deploy_uses_origin_health_and_public_auth_smoke(self) -> None:
        subprocess.run(["bash", "-n", str(VPS_DEPLOY)], check=True)
        source = VPS_DEPLOY.read_text(encoding="utf-8")
        self.assertIn(
            'ORIGIN_HEALTH_URL="${SEA_SPEED_ORIGIN_HEALTH_URL:-http://127.0.0.1:8000/api/health}"',
            source,
        )
        self.assertIn(
            'PUBLIC_HEALTH_URL="${SEA_SPEED_HEALTH_URL:-https://mostdef.ru/sea-speed/api/health}"',
            source,
        )
        self.assertIn('curl --fail --silent --show-error --max-time 10 "$ORIGIN_HEALTH_URL"', source)
        self.assertIn('verify_public_url "Public private-health boundary" "$PUBLIC_HEALTH_URL"', source)
        self.assertIn("200|301|302|307|308|401|403", source)
        self.assertIn('"api_origin_health"', source)
        self.assertIn('"public_private_health_smoke"', source)
        self.assertNotIn('curl --fail --silent --show-error --max-time 10 "$PUBLIC_HEALTH_URL"', source)

    def test_sdd_and_runtime_docs_keep_production_separate(self) -> None:
        for path in (SPEC, PLAN, TASKS, QUICKSTART, AUTH_DOC, OPS_DOC):
            source = path.read_text(encoding="utf-8")
            self.assertIn("#115", source)
        spec_source = SPEC.read_text(encoding="utf-8")
        self.assertIn("PRODUCTION APPROVED", spec_source)
        self.assertIn("/sea-speed/media/cam1/index.m3u8", spec_source)
        self.assertIn("/cams", spec_source)
        self.assertIn("worker machine-to-machine", spec_source.lower())
        auth_doc = AUTH_DOC.read_text(encoding="utf-8")
        self.assertIn("Forward auth (single application)", auth_doc)
        self.assertIn("authentik Embedded Outpost", auth_doc)
        self.assertIn("fixed_data", auth_doc)
        self.assertIn("single_use: true", auth_doc)
        ops_doc = OPS_DOC.read_text(encoding="utf-8")
        self.assertIn("SEA_SPEED_API_URL", ops_doc)
        self.assertIn("SEA_SPEED_API_TOKEN", ops_doc)
        self.assertIn("fail-closed", ops_doc.lower())
        self.assertIn("sea-speed-auth-cutover.sh", ops_doc)


if __name__ == "__main__":
    unittest.main()
