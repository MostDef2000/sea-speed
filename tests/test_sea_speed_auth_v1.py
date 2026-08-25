from __future__ import annotations

import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts/operations/nginx_sea_speed_auth.py"
CAM_RENDERER = ROOT / "scripts/operations/nginx_cam1_direct_h264.py"
CUTOVER = ROOT / "deploy/vps/sea-speed-auth-cutover.sh"
VPS_DEPLOY = ROOT / "deploy/vps/deploy.sh"
WORKER_AUTH_ROOT = ROOT / "deploy/worker/ubuntu/authentik"
WORKER_STAGE = WORKER_AUTH_ROOT / "stage.sh"
COMPOSE = WORKER_AUTH_ROOT / "compose.yml"
ENV_EXAMPLE = WORKER_AUTH_ROOT / "env.example"
AUTH_DOC = WORKER_AUTH_ROOT / "README.md"
BLUEPRINT = ROOT / "deploy/vps/authentik/blueprints/sea-speed-auth-v1.yaml"
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
AUTHENTIK_UPSTREAM = "http://10.123.239.102:19000"


class SeaSpeedAuthV1Tests(unittest.TestCase):
    def _render(self, source: str = BASE) -> str:
        return nginxauth.render(
            source,
            worker_private_listen=PRIVATE_LISTEN,
            worker_private_peer=PRIVATE_PEER,
            authentik_upstream=AUTHENTIK_UPSTREAM,
        )

    def _verify(self, source: str) -> None:
        nginxauth.verify(
            source,
            worker_private_listen=PRIVATE_LISTEN,
            worker_private_peer=PRIVATE_PEER,
            authentik_upstream=AUTHENTIK_UPSTREAM,
        )

    def test_renderer_retires_cams_and_protects_every_sea_speed_location(self) -> None:
        rendered = self._render()
        self._verify(rendered)
        self.assertNotIn("/cams/hls/cam1/", rendered)
        self.assertNotIn('auth_basic "Sea Speed"', rendered)
        self.assertIn("location = /cams {", rendered)
        self.assertIn("location ^~ /cams/ {", rendered)
        self.assertEqual(rendered.count("auth_request /outpost.goauthentik.io/auth/nginx;"), 3)
        self.assertIn("proxy_pass http://10.123.239.102:19000/outpost.goauthentik.io;", rendered)
        self.assertNotIn("proxy_pass http://127.0.0.1:9000/outpost.goauthentik.io;", rendered)
        self.assertIn("location @goauthentik_proxy_signin", rendered)

    def test_renderer_canonicalizes_www_before_forward_auth(self) -> None:
        rendered = self._render()
        self.assertEqual(rendered.count("if ($host = www.mostdef.ru) {"), 1)
        self.assertEqual(rendered.count("return 308 https://mostdef.ru$request_uri;"), 1)
        sea_location = re.search(r"(?m)^[ \t]*location[ \t]+(?:\^~[ \t]+)?/sea-speed/[ \t]*\{", rendered)
        self.assertIsNotNone(sea_location)
        self.assertLess(rendered.index("if ($host = www.mostdef.ru) {"), sea_location.start())

    def test_renderer_keeps_only_root_outpost_without_recursive_auth(self) -> None:
        rendered = self._render()
        self.assertEqual(rendered.count("location ^~ /outpost.goauthentik.io {"), 1)
        self.assertNotIn("location ^~ /sea-speed/outpost.goauthentik.io", rendered)
        match = re.search(r"location \^~ /outpost\.goauthentik\.io \{(?P<body>.*?)\n\s*\}", rendered, re.S)
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("proxy_pass http://10.123.239.102:19000/outpost.goauthentik.io;", body)
        self.assertNotIn("auth_request ", body)
        self.assertNotIn("error_page 401", body)

    def test_renderer_verification_rejects_missing_www_canonicalization(self) -> None:
        rendered = self._render()
        start = rendered.index("if ($host = www.mostdef.ru) {")
        line_start = rendered.rfind("\n", 0, start) + 1
        return_end = rendered.index("return 308 https://mostdef.ru$request_uri;", start)
        close_start = rendered.index("}", return_end)
        close_end = rendered.index("\n", close_start) + 1
        broken = rendered[:line_start] + rendered[close_end:]
        with self.assertRaises(nginxauth.ConfigError):
            self._verify(broken)

    def test_renderer_is_idempotent_for_exact_private_authentik_origin(self) -> None:
        first = self._render()
        second = self._render(first)
        self.assertEqual(first, second)

    def test_renderer_rejects_unsafe_authentik_origins(self) -> None:
        for upstream in (
            "https://10.123.239.102:19000",
            "http://203.0.113.10:19000",
            "http://10.123.239.102:19000/path",
            "http://user:pass@10.123.239.102:19000",
            "http://10.123.239.102",
            "http://auth.internal:19000",
        ):
            with self.subTest(upstream=upstream):
                with self.assertRaises(nginxauth.ConfigError):
                    nginxauth.render(
                        BASE,
                        worker_private_listen=PRIVATE_LISTEN,
                        worker_private_peer=PRIVATE_PEER,
                        authentik_upstream=upstream,
                    )

    def test_renderer_verification_binds_exact_authentik_origin(self) -> None:
        rendered = self._render()
        with self.assertRaises(nginxauth.ConfigError):
            nginxauth.verify(
                rendered,
                worker_private_listen=PRIVATE_LISTEN,
                worker_private_peer=PRIVATE_PEER,
                authentik_upstream="http://10.123.239.103:19000",
            )

    def test_private_worker_ingress_is_exact_peer_and_exact_endpoints(self) -> None:
        rendered = self._render()
        self.assertIn("listen 10.123.239.1:18080;", rendered)
        self.assertIn("allow 10.123.239.102;", rendered)
        self.assertIn("deny all;", rendered)
        expected = (
            ("/api/cam1/state", "POST"),
            ("/api/cam1/events", "POST"),
            ("/api/cam1/passages", "POST"),
            ("/api/cam1/roi", "GET"),
            ("/api/cam1/speed-config", "GET"),
            ("/api/cam1/speed-lines", "GET"),
            ("/api/analytics/road1/state", "POST"),
            ("/api/analytics/road1/events", "POST"),
            ("/api/analytics/road1/roi", "GET"),
            ("/api/analytics/road1/speed-config", "GET"),
            ("/api/analytics/road1/speed-lines", "GET"),
            ("/api/cam1/crossing-line", "GET"),
            ("/api/cam1/crossings", "POST"),
            ("/api/analytics/road1/crossing-line", "GET"),
            ("/api/analytics/road1/crossings", "POST"),
            ("/api/analytics/road1/live", "POST"),
            ("/api/cam1/live", "POST"),
        )
        self.assertEqual(nginxauth.WORKER_PRIVATE_ENDPOINTS, expected)
        for path, method in expected:
            self.assertIn(f"location = {path} {{", rendered)
            self.assertIn(f"limit_except {method} {{ deny all; }}", rendered)
            self.assertIn(f"proxy_pass http://127.0.0.1:8000{path};", rendered)
        browser_control = (
            "/api/worker/control",
            "/api/worker/control/start",
            "/api/worker/control/stop",
            "/api/worker/control/road1",
            "/api/worker/control/road1/start",
            "/api/worker/control/road1/stop",
        )
        self.assertEqual(nginxauth.WORKER_BROWSER_CONTROL_PATHS, browser_control)
        for path in browser_control:
            self.assertNotIn(f"location = {path} {{", rendered)
        self.assertNotIn("location /api/ {", rendered)
        self.assertNotIn("location /api/analytics/", rendered)
        self.assertNotIn("/api/analytics/road1/objects", rendered)
        self.assertEqual(nginxauth.WORKER_BROWSER_CONTROL_PREFIX, "/api/worker/control")

    def test_private_worker_verifier_rejects_method_or_path_drift(self) -> None:
        rendered = self._render()
        broken_method = rendered.replace(
            "location = /api/analytics/road1/state {\n        limit_except POST { deny all; }",
            "location = /api/analytics/road1/state {\n        limit_except GET { deny all; }",
            1,
        )
        with self.assertRaises(nginxauth.ConfigError):
            self._verify(broken_method)
        broken_path = rendered.replace(
            "location = /api/analytics/road1/events {",
            "location = /api/analytics/road2/events {",
            1,
        )
        with self.assertRaises(nginxauth.ConfigError):
            self._verify(broken_path)

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
                        authentik_upstream=AUTHENTIK_UPSTREAM,
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
                authentik_upstream=AUTHENTIK_UPSTREAM,
            )

    def test_cli_render_and_verify_private_authentik_origin(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "site.conf"
            candidate = root / "candidate.conf"
            source.write_text(BASE, encoding="utf-8")
            rendered = subprocess.run(
                [
                    "python3", str(RENDERER), "render", "--config", str(source), "--output", str(candidate),
                    "--authentik-upstream", AUTHENTIK_UPSTREAM,
                    "--worker-private-listen", PRIVATE_LISTEN,
                    "--worker-private-peer", PRIVATE_PEER,
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn("SEA_SPEED_AUTH_RENDER=PASS", rendered.stdout)
            verified = subprocess.run(
                [
                    "python3", str(RENDERER), "verify", "--config", str(candidate),
                    "--authentik-upstream", AUTHENTIK_UPSTREAM,
                    "--worker-private-listen", PRIVATE_LISTEN,
                    "--worker-private-peer", PRIVATE_PEER,
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn("SEA_SPEED_AUTH_CONFIG=PASS", verified.stdout)

    def test_split_layout_materializes_direct_snippets_and_runs_full_render_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            snippets = root / "snippets"
            snippets.mkdir()
            api = snippets / "sea-speed-api.conf"
            page = snippets / "sea-speed-page.conf"
            unrelated = root / "letsencrypt-options.conf"
            api.write_text(
                '    location /sea-speed/api/ {\n        proxy_pass http://127.0.0.1:8000/api/;\n    }\n\n'
                '    location /sea-speed/media/ {\n        alias /opt/sea-speed-api/media/;\n    }\n',
                encoding="utf-8",
            )
            page.write_text(
                '    location ^~ /sea-speed/ {\n        auth_basic "Sea Speed";\n'
                '        auth_basic_user_file /etc/nginx/.htpasswd;\n        try_files $uri $uri/ =404;\n    }\n',
                encoding="utf-8",
            )
            source = f'\nserver {{\n    listen 443 ssl;\n    server_name mostdef.ru www.mostdef.ru;\n    include {unrelated};\n    include {api};\n    include {page};\n}}\n'
            nginxauth.verify_source_layout(source)
            materialized = nginxauth.materialize_sea_speed_includes(source, include_root=snippets)
            self.assertIn(f"include {unrelated};", materialized)
            self.assertNotIn(f"include {api};", materialized)
            self.assertNotIn(f"include {page};", materialized)
            self.assertIn(nginxauth.MATERIALIZED_INCLUDE_BEGIN, materialized)
            self.assertIn("location /sea-speed/api/", materialized)
            self.assertIn("location ^~ /sea-speed/", materialized)
            flattened = root / "flattened.conf"
            cam_stage = root / "cam.conf"
            candidate = root / "candidate.conf"
            flattened.write_text(materialized, encoding="utf-8")
            subprocess.run(["python3", str(CAM_RENDERER), "render", "--config", str(flattened), "--output", str(cam_stage)], check=True, text=True, capture_output=True)
            subprocess.run(
                ["python3", str(RENDERER), "render", "--config", str(cam_stage), "--output", str(candidate), "--authentik-upstream", AUTHENTIK_UPSTREAM, "--worker-private-listen", PRIVATE_LISTEN, "--worker-private-peer", PRIVATE_PEER],
                check=True,
                text=True,
                capture_output=True,
            )
            final = candidate.read_text(encoding="utf-8")
            self._verify(final)
            self.assertIn(f"include {unrelated};", final)
            self.assertNotIn(f"include {api};", final)
            self.assertNotIn(f"include {page};", final)
            self.assertIn("location ^~ /sea-speed/media/cam1/", final)

    def test_split_layout_materialization_fails_closed_for_unsafe_includes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            snippets = root / "snippets"
            snippets.mkdir()
            wildcard = f'\nserver {{\n    listen 443 ssl;\n    server_name mostdef.ru;\n    include {snippets}/sea-speed-*.conf;\n}}\n'
            with self.assertRaises(nginxauth.ConfigError):
                nginxauth.materialize_sea_speed_includes(wildcard, include_root=snippets)
            nested_path = snippets / "sea-speed-page.conf"
            nested_path.write_text("include /etc/nginx/snippets/other.conf;\nlocation /sea-speed/ { try_files $uri $uri/ =404; }\n", encoding="utf-8")
            nested = f'\nserver {{\n    listen 443 ssl;\n    server_name mostdef.ru;\n    include {nested_path};\n}}\n'
            with self.assertRaises(nginxauth.ConfigError):
                nginxauth.materialize_sea_speed_includes(nested, include_root=snippets)
            outside_root = root / "outside"
            outside_root.mkdir()
            outside = outside_root / "sea-speed-api.conf"
            outside.write_text("location /sea-speed/api/ { proxy_pass http://127.0.0.1:8000/api/; }\n", encoding="utf-8")
            outside_source = f'\nserver {{\n    listen 443 ssl;\n    server_name mostdef.ru;\n    include {outside};\n}}\n'
            with self.assertRaises(nginxauth.ConfigError):
                nginxauth.materialize_sea_speed_includes(outside_source, include_root=snippets)

    def test_source_layout_requires_exact_mostdef_tls_host(self) -> None:
        wrong_host = 'server {\n    listen 443 ssl;\n    server_name auth.mostdef.ru;\n    location /sea-speed/ { return 200; }\n}\n'
        with self.assertRaises(nginxauth.ConfigError):
            nginxauth.verify_source_layout(wrong_host)

    def test_worker_authentik_runtime_is_pinned_loopback_and_has_no_docker_socket(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")
        self.assertEqual(compose.count("ghcr.io/goauthentik/server:2026.5.6"), 2)
        self.assertIn("docker.io/library/postgres:16-alpine", compose)
        self.assertIn('"127.0.0.1:${AUTHENTIK_HTTP_PORT:-9000}:9000"', compose)
        self.assertNotIn("/var/run/docker.sock", compose)
        self.assertNotRegex(compose, r"(?m)^\s*-\s*[\"']?9000:9000")
        self.assertNotRegex(compose, r"(?m)^\s*-\s*[\"']?5432:5432")
        self.assertNotIn(":latest", compose)
        env_example = ENV_EXAMPLE.read_text(encoding="utf-8")
        for secret_key in ("PG_PASS=", "AUTHENTIK_SECRET_KEY=", "AUTHENTIK_BOOTSTRAP_PASSWORD=", "AUTHENTIK_EMAIL__PASSWORD="):
            self.assertIn(secret_key, env_example)
        self.assertNotRegex(env_example, r"(?m)^(PG_PASS|AUTHENTIK_SECRET_KEY)=\S+")

    def test_worker_stage_is_one_stage_private_and_does_not_mutate_sea_speed_worker(self) -> None:
        subprocess.run(["bash", "-n", str(WORKER_STAGE)], check=True)
        source = WORKER_STAGE.read_text(encoding="utf-8")
        for marker in (
            "sea-speed-worker", "DOCKER_PACKAGE_CONFLICT", "download.docker.com", "docker-ce",
            "docker-compose-plugin", "socat", "range=${vps_peer}/32", "TCP4:127.0.0.1:9000",
            "AUTHENTIK_PRIVATE_ORIGIN=http://%s:%s", "AUTHENTIK_WORKER_STAGE=PASS",
            "AUTHENTIK_POSTGRESQL_PUBLIC_PORT=NO", "AUTHENTIK_DOCKER_SOCKET_MOUNT=NO",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("SEA_SPEED_API_TOKEN", source)
        self.assertNotIn("systemctl restart sea-speed-worker", source)
        self.assertNotIn("systemctl stop sea-speed-worker", source)
        self.assertNotIn("systemctl restart mediamtx", source)
        self.assertNotIn("0.0.0.0:9000", source)

    def test_blueprint_is_invite_only_owner_totp_only_and_30_day_session(self) -> None:
        source = BLUEPRINT.read_text(encoding="utf-8")
        for group in ("Sea Speed Owner", "Sea Speed Admin", "Sea Speed Operator", "Sea Speed Viewer"):
            self.assertIn(f"name: {group}", source)
        self.assertIsNotNone(re.search(r"name: Sea Speed Owner.*?is_superuser: true", source, re.S))
        self.assertEqual(source.count("continue_flow_without_invitation: false"), 3)
        self.assertIn("length_min: 15", source)
        self.assertIn("check_have_i_been_pwned: true", source)
        self.assertIn("check_zxcvbn: true", source)
        self.assertIn("not_configured_action: deny", source)
        self.assertIn("- totp", source)
        self.assertIn('name="Sea Speed Owner"', source)
        self.assertEqual(source.count("session_duration: days=30"), 2)
        self.assertNotIn("session_duration: hours=12", source)
        self.assertEqual(source.count("remember_me_offset: seconds=0"), 2)
        self.assertEqual(source.count("remember_device: seconds=0"), 2)
        self.assertIn("slug: sea-speed-owner-totp-setup", source)
        self.assertIn("designation: stage_configuration", source)
        self.assertIn("authentication: require_authenticated", source)
        self.assertIn("model: authentik_stages_authenticator_totp.authenticatortotpstage", source)
        self.assertIn("configure_flow: !KeyOf owner-totp-setup-flow", source)
        self.assertIn("configuration_stages:", source)
        self.assertIn("- !KeyOf owner-totp-setup-stage", source)
        self.assertNotIn("authentik_stages_authenticator_sms", source)
        self.assertNotIn("authentik_stages_authenticator_webauthn", source)

    def test_cutover_is_sha_bound_fail_closed_remote_authentik_and_private_worker_scoped(self) -> None:
        subprocess.run(["bash", "-n", str(CUTOVER)], check=True)
        source = CUTOVER.read_text(encoding="utf-8")
        for marker in (
            "bootstrap-public --authentik-upstream URL",
            "prepare --authentik-upstream URL --worker-private-listen IP:PORT --worker-private-peer IP",
            "activate --authentik-upstream URL --worker-private-listen IP:PORT --worker-private-peer IP --expected-sha256 SHA256",
            "--authentik-upstream", "AUTHENTIK_PRIVATE_UPSTREAM", "non-loopback RFC1918 IPv4",
            "render_candidate", "source-check", "materialize", "nginx -t", "systemctl reload nginx.service",
            "certbot certonly", "--webroot-path", "# SEA-SPEED-AUTH-PUBLIC-V1", "proxy_http_version 1.1",
            "proxy_set_header Host \\$host;", "proxy_set_header X-Forwarded-Proto \\$scheme;",
            "proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;", "proxy_set_header Upgrade \\$http_upgrade;",
            "AUTHENTIK_PUBLIC_BOOTSTRAP=PASS", "SEA_SPEED_MAIN_BOUNDARY_CHANGED=NO", "AUTOMATIC_ROLLBACK=NO",
            "--require-protected-baseline", "verify_protected_baseline", "restore_protected_backup",
            "ROLLBACK_CAPABILITY=VERIFIED", "AUTOMATIC_ROLLBACK=PASS", "AUTOMATIC_ROLLBACK=AVAILABLE",
            "WORKER_RUNTIME_RECONFIGURATION_REQUIRED=YES", "WORKER_PRIVATE_ROAD_API_BASE=http://%s/api/analytics/road1",
            "/sea-speed/media/cam1/index.m3u8", "https://auth.mostdef.ru",
        ):
            self.assertIn(marker, source)
        self.assertIn('python3 "$auth_renderer" source-check --config "$resolved"', source)
        self.assertIn('python3 "$auth_renderer" materialize', source)
        self.assertIn('--config "$materialized"', source)
        self.assertNotIn('cam_renderer" render --config "$nginx_site"', source)
        self.assertIn("CANDIDATE_SHA256", source)
        self.assertIn("rendered candidate SHA256 changed since prepare", source)
        self.assertIn("/var/lib/sea-speed-auth-v1", source)
        self.assertNotIn("certbot --nginx", source)
        self.assertNotIn('local_authentik="http://127.0.0.1:9000', source)
        self.assertNotIn("systemctl restart sea-speed-worker", source)
        self.assertNotIn("systemctl restart mediamtx", source)
        self.assertNotIn("auth_basic_user_file", source)

    def test_vps_deploy_uses_origin_health_and_public_auth_smoke(self) -> None:
        subprocess.run(["bash", "-n", str(VPS_DEPLOY)], check=True)
        source = VPS_DEPLOY.read_text(encoding="utf-8")
        self.assertIn('ORIGIN_HEALTH_URL="${SEA_SPEED_ORIGIN_HEALTH_URL:-http://127.0.0.1:8010/api/health}"', source)
        self.assertIn('PUBLIC_HEALTH_URL="${SEA_SPEED_HEALTH_URL:-https://mostdef.ru/sea-speed/api/health}"', source)
        self.assertIn('curl --fail --silent --show-error --max-time 10 "$ORIGIN_HEALTH_URL"', source)
        self.assertIn('verify_public_url "Public private-health boundary" "$PUBLIC_HEALTH_URL"', source)
        self.assertIn("200|301|302|307|308|401|403", source)
        self.assertIn('"api_origin_health"', source)
        self.assertIn('"public_private_health_smoke"', source)
        self.assertIn('AUTH_BOUNDARY_REQUIRED="${SEA_SPEED_REQUIRE_AUTH_BOUNDARY:-0}"', source)
        self.assertIn('run_auth_boundary()', source)
        self.assertIn('deploy/vps/sea-speed-auth-cutover.sh', source)
        self.assertIn('--require-protected-baseline', source)
        self.assertIn('"auth_v1_road_private_m2m"', source)
        self.assertNotIn('curl --fail --silent --show-error --max-time 10 "$PUBLIC_HEALTH_URL"', source)

    def test_sdd_and_runtime_docs_record_issue_122_and_keep_production_separate(self) -> None:
        for path in (SPEC, PLAN, TASKS, QUICKSTART, AUTH_DOC, OPS_DOC):
            source = path.read_text(encoding="utf-8")
            self.assertIn("#115", source)
            self.assertIn("#122", source)
        for path in (SPEC, PLAN, TASKS, QUICKSTART, OPS_DOC):
            self.assertIn("#140", path.read_text(encoding="utf-8"))
        spec_source = SPEC.read_text(encoding="utf-8")
        self.assertIn("PRODUCTION APPROVED", spec_source)
        self.assertIn("/sea-speed/media/cam1/index.m3u8", spec_source)
        self.assertIn("worker-loopback-only", spec_source.lower())
        self.assertIn("worker machine-to-machine", spec_source.lower())
        self.assertIn("96 hours", spec_source)
        self.assertIn("12 hours", spec_source)
        auth_doc = AUTH_DOC.read_text(encoding="utf-8")
        self.assertIn("Ubuntu worker", auth_doc)
        self.assertIn("socat", auth_doc)
        self.assertIn("range=<vps-ip>/32", auth_doc)
        self.assertIn("superseded", auth_doc.lower())
        ops_doc = OPS_DOC.read_text(encoding="utf-8")
        self.assertIn("#146", ops_doc)
        self.assertIn("External host: https://mostdef.ru", ops_doc)
        self.assertIn("Launch URL: https://mostdef.ru/sea-speed/", ops_doc)
        self.assertNotIn("External host: https://mostdef.ru/sea-speed/", ops_doc)
        self.assertIn("stage.sh stage", ops_doc)
        self.assertIn("AUTHENTIK_PRIVATE_ORIGIN", ops_doc)
        self.assertIn("SEA_SPEED_API_URL", ops_doc)
        self.assertIn("SEA_SPEED_API_TOKEN", ops_doc)
        self.assertIn("fail-closed", ops_doc.lower())
        self.assertIn("sea-speed-auth-cutover.sh", ops_doc)
        self.assertIn("sea-speed-*.conf", ops_doc)
        self.assertIn("96 hours", ops_doc)
        self.assertIn("30 days", ops_doc)


if __name__ == "__main__":
    unittest.main()