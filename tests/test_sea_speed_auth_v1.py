from __future__ import annotations

import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.support import markdown_docs

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
        # Issue #573: yaml.safe_load parsed twin — the compose pins are
        # structural security properties of the parsed services tree, blind to
        # comments/reordering where the raw substring/regex pins false-failed.
        compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
        services = compose["services"]
        images = {name: service.get("image") for name, service in services.items()}
        self.assertEqual(
            list(images.values()).count("ghcr.io/goauthentik/server:2026.5.6"),
            2,
        )
        self.assertIn("docker.io/library/postgres:16-alpine", images.values())
        # Same-or-stronger upgrade vs the retired raw `:latest` byte-ban: every
        # service image must carry an explicit non-latest tag — an image with
        # NO tag defaults to latest at pull time, which the raw ban missed.
        # The tag check bans the "latest" SUBSTRING so an env-default like
        # ${AUTHENTIK_TAG:-latest} cannot smuggle latest through the parsed
        # walk (peer review finding, #573).
        for name, image in images.items():
            self.assertIsInstance(image, str, f"service {name} must pin an image")
            leaf = image.rsplit("/", 1)[-1]
            tag = leaf.rsplit(":", 1)[-1] if ":" in leaf else None
            self.assertIsNotNone(
                tag, f"service {name} image {image!r} has no explicit tag (defaults to latest)"
            )
            self.assertNotIn(
                "latest",
                tag.lower(),
                f"service {name} image tag {tag!r} must not resolve to :latest",
            )
        # Every published port must bind 127.0.0.1 explicitly (parsed superset
        # of the retired `9000:9000`/`5432:5432` unbound-publish regex bans).
        published = []
        for name, service in services.items():
            for entry in service.get("ports") or []:
                self.assertIsInstance(entry, str, f"service {name} port entry must be a string mapping")
                # container port from the right (host port may embed colons via
                # ${VAR:-default}), host ip from the left.
                remainder, _, container_port = entry.rpartition(":")
                host_ip = None
                host_port = None
                if remainder:
                    if ":" in remainder:
                        host_ip, _, host_port = remainder.partition(":")
                    else:
                        host_port = remainder
                published.append((name, host_ip, host_port, container_port))
        for name, host_ip, host_port, container_port in published:
            self.assertEqual(
                host_ip,
                "127.0.0.1",
                f"service {name} publishes {host_port}:{container_port} without a loopback bind",
            )
        # The authentik HTTP endpoint stays env-tunable on the host side and
        # loopback-bound to container port 9000.
        self.assertIn(
            ("server", "127.0.0.1", "${AUTHENTIK_HTTP_PORT:-9000}", "9000"),
            published,
        )
        # No service may mount the docker socket (source or target side —
        # parsed walk, superset of the retired substring ban).
        for name, service in services.items():
            for volume in service.get("volumes") or []:
                self.assertIsInstance(volume, str)
                self.assertFalse(
                    any("/var/run/docker.sock" in part for part in volume.split(":")),
                    f"service {name} must not mount /var/run/docker.sock",
                )
        # Retained raw catch-all bans (issue #573 peer review): the parsed walks
        # above attribute violations per service, but the socket path or a
        # :latest reference could also appear OUTSIDE service volumes/images
        # (build args, environment, top-level keys) — the byte-level bans stay
        # as the global net. Together with the parsed twins this is strictly
        # stronger than either alone.
        compose_text = COMPOSE.read_text(encoding="utf-8")
        self.assertNotIn("/var/run/docker.sock", compose_text)
        self.assertNotIn(":latest", compose_text)
        # STATIC_POLICY (issue #573): the env.example secret-key pins stay raw —
        # presence of the keys with EMPTY values IS the dotenv security
        # contract (byte-level), parsed-absence N/A for prose/dotenv.
        env_example = ENV_EXAMPLE.read_text(encoding="utf-8")
        for secret_key in ("PG_PASS=", "AUTHENTIK_SECRET_KEY=", "AUTHENTIK_BOOTSTRAP_PASSWORD=", "AUTHENTIK_EMAIL__PASSWORD="):
            self.assertIn(secret_key, env_example)
        self.assertNotRegex(env_example, r"(?m)^(PG_PASS|AUTHENTIK_SECRET_KEY)=\S+")

    def test_worker_stage_is_one_stage_private_and_does_not_mutate_sea_speed_worker(self) -> None:
        subprocess.run(["bash", "-n", str(WORKER_STAGE)], check=True)
        # STATIC_POLICY (issue #573): stage.sh byte-identity IS the contract — shell deploy script, any change must fail review; parsed-absence N/A for shell.
        source = WORKER_STAGE.read_text(encoding="utf-8")
        for marker in (
            "sea-speed-worker", "DOCKER_PACKAGE_CONFLICT", "download.docker.com", "docker-ce",
            "docker-compose-plugin", "socat", "range=${vps_peer}/32", "TCP4:127.0.0.1:9000",
            "AUTHENTIK_PRIVATE_ORIGIN=http://%s:%s", "AUTHENTIK_WORKER_STAGE=PASS",
            "AUTHENTIK_POSTGRESQL_PUBLIC_PORT=NO", "AUTHENTIK_DOCKER_SOCKET_MOUNT=NO",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("SEA_SPEED_API_TOKEN", source)
        self.assertNotIn("SEA_SPEED_WORKER_CONTROL_TOKEN", source)
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
        # The privileged cutover flow is retired from the VPS deploy pipeline;
        # the flag remains pinned against the cutover script above.
        self.assertNotIn('--require-protected-baseline', source)
        self.assertIn('"auth_v1_road_private_m2m"', source)
        self.assertNotIn('curl --fail --silent --show-error --max-time 10 "$PUBLIC_HEALTH_URL"', source)

    def test_sdd_and_runtime_docs_record_issue_122_and_keep_production_separate(self) -> None:
        # SDD feature docs (spec/plan/tasks/quickstart) keep their raw pins:
        # wave-4 precedent — prose SDD docs are historical records, their
        # textual presence IS the record (NO-CHANGE). The runtime docs
        # (worker-auth README, ops runbook) get structural twins below.
        for path in (SPEC, PLAN, TASKS, QUICKSTART):
            source = path.read_text(encoding="utf-8")
            self.assertIn("#115", source)
            self.assertIn("#122", source)
        for path in (SPEC, PLAN, TASKS, QUICKSTART):
            self.assertIn("#140", path.read_text(encoding="utf-8"))
        spec_source = SPEC.read_text(encoding="utf-8")
        self.assertIn("PRODUCTION APPROVED", spec_source)
        self.assertIn("/sea-speed/media/cam1/index.m3u8", spec_source)
        self.assertIn("worker-loopback-only", spec_source.lower())
        self.assertIn("worker machine-to-machine", spec_source.lower())
        self.assertIn("96 hours", spec_source)
        self.assertIn("12 hours", spec_source)
        # SS twins (issue #398 wave 6) — worker-auth README: the doc's first
        # section (its preamble) must bind the issue chain to the canonical
        # Ubuntu-worker placement claim — both bound to sections()[0] (peer
        # review F5: section_containing alone would match any section); the
        # Topology-section content (socat source-restriction with the exact
        # /32 range option; the superseded-placement deprecation with its
        # must-not-stage ban) is enforced as one-section co-location — the
        # first matching section is the doc's Topology section.
        auth_doc = AUTH_DOC.read_text(encoding="utf-8")
        auth_preamble = markdown_docs.sections(auth_doc)[0]
        self.assertIn("#115", auth_preamble[1])
        self.assertIn("#122", auth_preamble[1])
        self.assertIn("Ubuntu worker", auth_preamble[1])
        self.assertIn("canonical production runtime placement", auth_preamble[1])
        self.assertIsNotNone(
            markdown_docs.section_containing(auth_doc, "socat", "range=<vps-ip>/32")
        )
        self.assertIsNotNone(
            markdown_docs.section_containing(auth_doc, "superseded", "must not be used for production")
        )
        # SS twins (issue #398 wave 6) — ops runbook: the doc's first section
        # (its preamble) carries the full issue chain (#115/#122/#140/#146),
        # bound to sections()[0] (peer review F5); the Issue #146 section
        # pins External host and Launch URL as EXACT single-line fenced
        # values; the staged-invocation tokens co-locate in one section (the
        # exact staged command fenced block on the real doc — the twin pins
        # token co-location, not the exact command text); the private origin
        # is exposed as
        # non-secret; the ingestion token secrecy rule co-locates with the
        # token; the cutover script and snippet materialization rules live
        # in the split-layout section; session/token timing pairs both
        # timers as separate; the fail-closed dependency test phase requires
        # the never-anonymous outcome.
        ops_doc = OPS_DOC.read_text(encoding="utf-8")
        ops_preamble = markdown_docs.sections(ops_doc)[0]
        for issue in ("#115", "#122", "#140", "#146"):
            self.assertIn(issue, ops_preamble[1], issue)
        section_146 = markdown_docs.section_titled(ops_doc, "#146")
        self.assertIsNotNone(section_146)
        ext_blocks = [
            block
            for block in markdown_docs.fenced_blocks(section_146[1])
            if any("External host:" in line for line in block)
        ]
        self.assertEqual(len(ext_blocks), 1)
        self.assertEqual(
            [line.strip() for line in ext_blocks[0]], ["External host: https://mostdef.ru"]
        )
        launch_blocks = [
            block
            for block in markdown_docs.fenced_blocks(section_146[1])
            if any("Launch URL:" in line for line in block)
        ]
        self.assertEqual(len(launch_blocks), 1)
        self.assertEqual(
            [line.strip() for line in launch_blocks[0]], ["Launch URL: https://mostdef.ru/sea-speed/"]
        )
        # SP keep (issue #398 wave 6): the path-bearing External host is the
        # exact misconfiguration the doc bans — negative contract, the ban
        # must fail if the literal value appears anywhere in the runbook.
        self.assertNotIn("External host: https://mostdef.ru/sea-speed/", ops_doc)
        self.assertIsNotNone(
            markdown_docs.section_containing(
                ops_doc, "stage.sh stage", "--bind-ip", "--vps-peer", "--env-file"
            )
        )
        self.assertIsNotNone(
            markdown_docs.section_containing(ops_doc, "AUTHENTIK_PRIVATE_ORIGIN", "non-secret")
        )
        self.assertIsNotNone(
            markdown_docs.section_containing(ops_doc, "SEA_SPEED_API_TOKEN", "must not appear in chat")
        )
        m2m_blocks = [
            block
            for _, body in markdown_docs.sections(ops_doc)
            for block in markdown_docs.fenced_blocks(body)
            if any(line.strip().startswith("SEA_SPEED_API_URL=") for line in block)
        ]
        self.assertEqual(len(m2m_blocks), 1)
        self.assertEqual(
            [line.strip() for line in m2m_blocks[0]],
            [
                "SEA_SPEED_API_URL=http://<vps-private-ip>:<port>/api/cam1/state",
                "SEA_SPEED_EVENT_API_URL=http://<vps-private-ip>:<port>/api/cam1/events",
                "SEA_SPEED_ROI_URL=http://<vps-private-ip>:<port>/api/cam1/roi",
                "SEA_SPEED_SPEED_CONFIG_URL=http://<vps-private-ip>:<port>/api/cam1/speed-config",
                "SEA_SPEED_SPEED_LINES_URL=http://<vps-private-ip>:<port>/api/cam1/speed-lines",
            ],
        )
        phase_e = markdown_docs.section_titled(ops_doc, "fail-closed")
        self.assertIsNotNone(phase_e)
        self.assertIn("never anonymous", phase_e[1].lower())
        self.assertIsNotNone(
            markdown_docs.section_containing(ops_doc, "sea-speed-auth-cutover.sh", "prepare")
        )
        self.assertIsNotNone(
            markdown_docs.section_containing(ops_doc, "sea-speed-*.conf", "materializ")
        )
        self.assertIsNotNone(
            markdown_docs.section_containing(ops_doc, "96 hours", "30 days", "separate timers")
        )


if __name__ == "__main__":
    unittest.main()