from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts/operations/nginx_sea_speed_auth.py"

spec = importlib.util.spec_from_file_location("nginx_sea_speed_auth", RENDERER)
assert spec and spec.loader
nginxauth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nginxauth)

# Gitleaks-safe low-entropy fixture values, following the repo precedent
# (tests/test_393_control_token_separation.py INGESTION_TOKEN,
# tests/test_auth_session_identity.py STRICT_EDGE_FIXTURE). The renderer
# must never contain, emit or read any secret value: these constants exist
# only to prove their absence from renderer source and rendered output.
EDGE_AUTH_FIXTURE_SECRET = "[redacted:generic-assignment]"
DEFAULT_EDGE_AUTH_INCLUDE = "/etc/nginx/snippets/sea-speed-edge-auth.conf"
CUSTOM_EDGE_AUTH_INCLUDE = "/etc/nginx/secrets/sea-speed-edge-auth-520.conf"

BASIC_AUTH_HOST = "3d.mostdef.ru"
# Recorded live worker-private vhost facts (issue #520 KB inventory):
# listen 10.123.239.101:18080 on the VPS, exact peer allow 10.123.239.102,
# loopback sea-speed API origin 127.0.0.1:8000.
BASIC_AUTH_LISTEN = "10.123.239.101:18080"
BASIC_AUTH_PEER = "10.123.239.102"
BASIC_AUTH_API_ORIGIN = "http://127.0.0.1:8000"
AUTHENTIK_UPSTREAM = "http://10.123.239.102:19000"

AUTHENTIK_SOURCE = '''server {
    listen 443 ssl;
    server_name mostdef.ru www.mostdef.ru;

    location /sea-speed/ {
        auth_basic "Sea Speed";
        auth_basic_user_file /etc/nginx/.htpasswd;
        try_files $uri $uri/ =404;
    }

    location /sea-speed/api/ {
        proxy_pass http://127.0.0.1:8000/api/;
    }
}
'''

BASIC_AUTH_SOURCE = '''server {
    listen 443 ssl;
    server_name 3d.mostdef.ru;

    add_header Strict-Transport-Security "max-age=31536000" always;

    location /sea-speed/ {
        auth_basic "Valery Manager";
        auth_basic_user_file /etc/nginx/.htpasswd_3d;
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

AUTHENTIK_GOLDEN = '''server {
    listen 443 ssl;
    server_name mostdef.ru www.mostdef.ru;
# SEA-SPEED-AUTH-V1-BEGIN
if ($host = www.mostdef.ru) {
    return 308 https://mostdef.ru$request_uri;
}
location = /cams {
    return 404;
}
location ^~ /cams/ {
    return 404;
}
location ^~ /outpost.goauthentik.io {
    proxy_pass http://10.123.239.102:19000/outpost.goauthentik.io;
    proxy_set_header Host $host;
    proxy_set_header X-Original-URL $scheme://$http_host$request_uri;
    add_header Set-Cookie $auth_cookie;
    auth_request_set $auth_cookie $upstream_http_set_cookie;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
}
location @goauthentik_proxy_signin {
    internal;
    add_header Set-Cookie $auth_cookie;
    return 302 /outpost.goauthentik.io/start?rd=$scheme://$http_host$request_uri;
}
# SEA-SPEED-AUTH-V1-END
# SEA-SPEED-FALLBACK-V1-BEGIN
location = /sea-speed-unavailable.html {
    internal;
    root /var/www/mostdef.ru;
    add_header Cache-Control "no-store" always;
    add_header Retry-After "30" always;
}
# SEA-SPEED-FALLBACK-V1-END

    location /sea-speed/ {
    # SEA-SPEED-AUTH-V1-LOCATION-BEGIN
    include /etc/nginx/snippets/sea-speed-edge-auth.conf;
    auth_request /outpost.goauthentik.io/auth/nginx;
    error_page 401 = @goauthentik_proxy_signin;
    error_page 500 =503 /sea-speed-unavailable.html;
    auth_request_set $auth_cookie $upstream_http_set_cookie;
    add_header Set-Cookie $auth_cookie;
    auth_request_set $authentik_username $upstream_http_x_authentik_username;
    auth_request_set $authentik_groups $upstream_http_x_authentik_groups;
    auth_request_set $authentik_entitlements $upstream_http_x_authentik_entitlements;
    auth_request_set $authentik_email $upstream_http_x_authentik_email;
    auth_request_set $authentik_name $upstream_http_x_authentik_name;
    auth_request_set $authentik_uid $upstream_http_x_authentik_uid;
    proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;
    proxy_set_header X-authentik-username $authentik_username;
    proxy_set_header X-authentik-groups $authentik_groups;
    proxy_set_header X-authentik-entitlements $authentik_entitlements;
    proxy_set_header X-authentik-email $authentik_email;
    proxy_set_header X-authentik-name $authentik_name;
    proxy_set_header X-authentik-uid $authentik_uid;
    # SEA-SPEED-AUTH-V1-LOCATION-END
        try_files $uri $uri/ =404;
    }

    location /sea-speed/api/ {
    # SEA-SPEED-AUTH-V1-LOCATION-BEGIN
    include /etc/nginx/snippets/sea-speed-edge-auth.conf;
    auth_request /outpost.goauthentik.io/auth/nginx;
    error_page 401 = @goauthentik_proxy_signin;
    error_page 500 =503 /sea-speed-unavailable.html;
    auth_request_set $auth_cookie $upstream_http_set_cookie;
    add_header Set-Cookie $auth_cookie;
    auth_request_set $authentik_username $upstream_http_x_authentik_username;
    auth_request_set $authentik_groups $upstream_http_x_authentik_groups;
    auth_request_set $authentik_entitlements $upstream_http_x_authentik_entitlements;
    auth_request_set $authentik_email $upstream_http_x_authentik_email;
    auth_request_set $authentik_name $upstream_http_x_authentik_name;
    auth_request_set $authentik_uid $upstream_http_x_authentik_uid;
    proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;
    proxy_set_header X-authentik-username $authentik_username;
    proxy_set_header X-authentik-groups $authentik_groups;
    proxy_set_header X-authentik-entitlements $authentik_entitlements;
    proxy_set_header X-authentik-email $authentik_email;
    proxy_set_header X-authentik-name $authentik_name;
    proxy_set_header X-authentik-uid $authentik_uid;
    # SEA-SPEED-AUTH-V1-LOCATION-END
        proxy_pass http://127.0.0.1:8000/api/;
    }
}
'''

BASIC_AUTH_GOLDEN_FRONT = '''server {
    listen 443 ssl;
    server_name 3d.mostdef.ru;

    add_header Strict-Transport-Security "max-age=31536000" always;

    location /sea-speed/ {
    # SEA-SPEED-AUTH-V1-LOCATION-BEGIN
    auth_basic "Valery Manager";
    auth_basic_user_file /etc/nginx/.htpasswd_3d;
    include /etc/nginx/snippets/sea-speed-edge-auth.conf;
    proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;
    proxy_set_header X-authentik-username "";
    proxy_set_header X-authentik-groups "";
    proxy_set_header X-authentik-entitlements "";
    proxy_set_header X-authentik-email "";
    proxy_set_header X-authentik-name "";
    proxy_set_header X-authentik-uid "";
    # SEA-SPEED-AUTH-V1-LOCATION-END
        try_files $uri $uri/ =404;
    }

    location /sea-speed/api/ {
    # SEA-SPEED-AUTH-V1-LOCATION-BEGIN
    auth_basic "Valery Manager";
    auth_basic_user_file /etc/nginx/.htpasswd_3d;
    include /etc/nginx/snippets/sea-speed-edge-auth.conf;
    proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;
    proxy_set_header X-authentik-username "";
    proxy_set_header X-authentik-groups "";
    proxy_set_header X-authentik-entitlements "";
    proxy_set_header X-authentik-email "";
    proxy_set_header X-authentik-name "";
    proxy_set_header X-authentik-uid "";
    # SEA-SPEED-AUTH-V1-LOCATION-END
        proxy_pass http://127.0.0.1:8000/api/;
    }

    location /sea-speed/media/ {
    # SEA-SPEED-AUTH-V1-LOCATION-BEGIN
    auth_basic "Valery Manager";
    auth_basic_user_file /etc/nginx/.htpasswd_3d;
    include /etc/nginx/snippets/sea-speed-edge-auth.conf;
    proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;
    proxy_set_header X-authentik-username "";
    proxy_set_header X-authentik-groups "";
    proxy_set_header X-authentik-entitlements "";
    proxy_set_header X-authentik-email "";
    proxy_set_header X-authentik-name "";
    proxy_set_header X-authentik-uid "";
    # SEA-SPEED-AUTH-V1-LOCATION-END
        alias /opt/sea-speed-api/media/;
    }
}
'''

BASIC_AUTH_GOLDEN_WORKER = '''# SEA-SPEED-WORKER-PRIVATE-V1-BEGIN
server {
    listen 10.123.239.101:18080;
    server_name sea-speed-worker-private;
    allow 10.123.239.102;
    deny all;
    client_max_body_size 25m;
    location = /api/cam1/state {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8000/api/cam1/state;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/cam1/events {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8000/api/cam1/events;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/cam1/passages {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8000/api/cam1/passages;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/cam1/roi {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8000/api/cam1/roi;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/cam1/speed-config {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8000/api/cam1/speed-config;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/cam1/speed-lines {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8000/api/cam1/speed-lines;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/analytics/road1/state {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8000/api/analytics/road1/state;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/analytics/road1/events {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8000/api/analytics/road1/events;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/analytics/road1/roi {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8000/api/analytics/road1/roi;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/analytics/road1/speed-config {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8000/api/analytics/road1/speed-config;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/analytics/road1/speed-lines {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8000/api/analytics/road1/speed-lines;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/cam1/crossing-line {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8000/api/cam1/crossing-line;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/cam1/crossings {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8000/api/cam1/crossings;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/analytics/road1/crossing-line {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.1:8000/api/analytics/road1/crossing-line;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/analytics/road1/crossings {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8000/api/analytics/road1/crossings;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/analytics/road1/live {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8000/api/analytics/road1/live;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location = /api/cam1/live {
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8000/api/cam1/live;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location / { return 404; }
}
# SEA-SPEED-WORKER-PRIVATE-V1-END

'''

BASIC_AUTH_GOLDEN = BASIC_AUTH_GOLDEN_FRONT + BASIC_AUTH_GOLDEN_WORKER


class SeaSpeedEdgeVhostRendererTests(unittest.TestCase):
    def _render_basic_auth(self, source: str = BASIC_AUTH_SOURCE, **kwargs) -> str:
        return nginxauth.render(
            source,
            host=BASIC_AUTH_HOST,
            worker_private_listen=BASIC_AUTH_LISTEN,
            worker_private_peer=BASIC_AUTH_PEER,
            mode=nginxauth.MODE_BASIC_AUTH,
            **kwargs,
        )

    def _verify_basic_auth(self, text: str, **kwargs) -> None:
        nginxauth.verify(
            text,
            host=BASIC_AUTH_HOST,
            worker_private_listen=BASIC_AUTH_LISTEN,
            worker_private_peer=BASIC_AUTH_PEER,
            mode=nginxauth.MODE_BASIC_AUTH,
            **kwargs,
        )

    def _render_authentik(self, source: str = AUTHENTIK_SOURCE, **kwargs) -> str:
        return nginxauth.render(source, authentik_upstream=AUTHENTIK_UPSTREAM, **kwargs)

    def _verify_authentik(self, text: str, **kwargs) -> None:
        nginxauth.verify(text, authentik_upstream=AUTHENTIK_UPSTREAM, **kwargs)

    def test_basic_auth_golden_byte_config(self) -> None:
        self.assertEqual(self._render_basic_auth(), BASIC_AUTH_GOLDEN)

    def test_authentik_golden_byte_config(self) -> None:
        self.assertEqual(self._render_authentik(), AUTHENTIK_GOLDEN)

    def test_edge_injection_present_in_every_sea_speed_location_in_both_modes(self) -> None:
        for golden, sea_locations in (
            (AUTHENTIK_GOLDEN, 2),
            (BASIC_AUTH_GOLDEN, 3),
        ):
            with self.subTest(mode="golden"):
                self.assertEqual(golden.count(f"include {DEFAULT_EDGE_AUTH_INCLUDE};"), sea_locations)
                self.assertEqual(golden.count("proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;"), sea_locations)
        server, _ = BASIC_AUTH_GOLDEN.split(nginxauth.WORKER_BEGIN, 1)
        for location_body in self._sea_location_bodies(server):
            self.assertIn(f"include {DEFAULT_EDGE_AUTH_INCLUDE};", location_body)
            self.assertIn("proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;", location_body)

    def test_basic_auth_mode_strips_client_authentik_headers_in_every_location(self) -> None:
        server, _ = BASIC_AUTH_GOLDEN.split(nginxauth.WORKER_BEGIN, 1)
        stripped = tuple(f'proxy_set_header X-authentik-{field} "";' for field in nginxauth.AUTHENTIK_IDENTITY_FIELDS)
        for location_body in self._sea_location_bodies(server):
            for line in stripped:
                self.assertIn(line, location_body)
        self.assertNotIn("$authentik_username", BASIC_AUTH_GOLDEN)
        self.assertNotIn("auth_request ", BASIC_AUTH_GOLDEN)
        self.assertNotIn(nginxauth.GLOBAL_BEGIN, BASIC_AUTH_GOLDEN)
        self.assertNotIn(nginxauth.FALLBACK_BEGIN, BASIC_AUTH_GOLDEN)

    def test_authentik_mode_keeps_auth_request_and_avoids_duplicate_blank_strips(self) -> None:
        self.assertIn("auth_request /outpost.goauthentik.io/auth/nginx;", AUTHENTIK_GOLDEN)
        self.assertIn("proxy_set_header X-authentik-username $authentik_username;", AUTHENTIK_GOLDEN)
        self.assertNotIn('proxy_set_header X-authentik-username "";', AUTHENTIK_GOLDEN)

    def test_render_is_idempotent_for_both_modes(self) -> None:
        first = self._render_basic_auth()
        self.assertEqual(first, self._render_basic_auth(first))
        authentik_first = self._render_authentik()
        self.assertEqual(authentik_first, self._render_authentik(authentik_first))

    def test_verify_fail_matrix_missing_edge_injection_both_modes(self) -> None:
        broken = BASIC_AUTH_GOLDEN.replace("proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;\n", "")
        with self.assertRaises(nginxauth.ConfigError):
            self._verify_basic_auth(broken)
        authentik_broken = AUTHENTIK_GOLDEN.replace("proxy_set_header X-Sea-Speed-Edge-Auth $edge_auth;\n", "")
        with self.assertRaises(nginxauth.ConfigError):
            self._verify_authentik(authentik_broken)

    def test_verify_fail_matrix_missing_edge_include_both_modes(self) -> None:
        broken = BASIC_AUTH_GOLDEN.replace(f"include {DEFAULT_EDGE_AUTH_INCLUDE};\n", "")
        with self.assertRaises(nginxauth.ConfigError):
            self._verify_basic_auth(broken)
        authentik_broken = AUTHENTIK_GOLDEN.replace(f"include {DEFAULT_EDGE_AUTH_INCLUDE};\n", "")
        with self.assertRaises(nginxauth.ConfigError):
            self._verify_authentik(authentik_broken)

    def test_verify_fail_matrix_missing_strip_in_basic_auth_mode(self) -> None:
        broken = BASIC_AUTH_GOLDEN.replace('proxy_set_header X-authentik-entitlements "";\n', "")
        with self.assertRaises(nginxauth.ConfigError):
            self._verify_basic_auth(broken)

    def test_verify_fail_matrix_missing_basic_auth_pair(self) -> None:
        broken = BASIC_AUTH_GOLDEN.replace("auth_basic_user_file /etc/nginx/.htpasswd_3d;\n", "")
        with self.assertRaises(nginxauth.ConfigError):
            self._verify_basic_auth(broken)
        realm_drift = BASIC_AUTH_GOLDEN.replace('auth_basic "Valery Manager";', 'auth_basic "Sea Speed";', 1)
        with self.assertRaises(nginxauth.ConfigError):
            self._verify_basic_auth(realm_drift)

    def test_verify_fail_matrix_auth_request_forbidden_in_basic_auth_mode(self) -> None:
        broken = BASIC_AUTH_GOLDEN.replace(
            'auth_basic "Valery Manager";',
            'auth_basic "Valery Manager";\n    auth_request /outpost.goauthentik.io/auth/nginx;',
            1,
        )
        with self.assertRaises(nginxauth.ConfigError):
            self._verify_basic_auth(broken)

    def test_verify_rejects_mode_mixing(self) -> None:
        with self.assertRaises(nginxauth.ConfigError):
            nginxauth.verify(BASIC_AUTH_GOLDEN, host=BASIC_AUTH_HOST, mode=nginxauth.MODE_AUTHENTIK)
        with self.assertRaises(nginxauth.ConfigError):
            self._verify_basic_auth(AUTHENTIK_GOLDEN)

    def test_edge_auth_include_path_is_a_parameter(self) -> None:
        rendered = self._render_basic_auth(edge_auth_include=CUSTOM_EDGE_AUTH_INCLUDE)
        self.assertIn(f"include {CUSTOM_EDGE_AUTH_INCLUDE};", rendered)
        self.assertNotIn(f"include {DEFAULT_EDGE_AUTH_INCLUDE};", rendered)
        self._verify_basic_auth(rendered, edge_auth_include=CUSTOM_EDGE_AUTH_INCLUDE)
        with self.assertRaises(nginxauth.ConfigError):
            self._verify_basic_auth(rendered)
        with self.assertRaises(nginxauth.ConfigError):
            self._render_basic_auth(edge_auth_include="relative-edge-auth.conf")
        with self.assertRaises(nginxauth.ConfigError):
            self._render_basic_auth(edge_auth_include="/etc/nginx/snippets/edge auth.conf")

    def test_worker_private_block_matches_recorded_live_facts(self) -> None:
        self.assertIn(f"listen {BASIC_AUTH_LISTEN};", BASIC_AUTH_GOLDEN)
        self.assertIn(f"allow {BASIC_AUTH_PEER};", BASIC_AUTH_GOLDEN)
        self.assertIn("deny all;", BASIC_AUTH_GOLDEN)
        self.assertIn("proxy_set_header Authorization $http_authorization;", BASIC_AUTH_GOLDEN)
        self.assertIn(f"proxy_pass {BASIC_AUTH_API_ORIGIN}/api/cam1/state;", BASIC_AUTH_GOLDEN)
        self.assertNotIn("location /api/ {", BASIC_AUTH_GOLDEN)
        for path in nginxauth.WORKER_BROWSER_CONTROL_PATHS:
            self.assertNotIn(f"location = {path} {{", BASIC_AUTH_GOLDEN)

    def test_basic_auth_render_leaves_server_level_directives_and_other_servers_untouched(self) -> None:
        source = (
            "server {\n"
            "    listen 443 ssl;\n"
            "    server_name mostdef.ru;\n"
            "# SEA-SPEED-AUTH-V1-BEGIN\n"
            "if ($host = www.mostdef.ru) {\n"
            "    return 308 https://mostdef.ru$request_uri;\n"
            "}\n"
            "# SEA-SPEED-AUTH-V1-END\n"
            "    location /sea-speed/ {\n"
            "        try_files $uri $uri/ =404;\n"
            "    }\n"
            "}\n"
            + BASIC_AUTH_SOURCE
        )
        rendered = self._render_basic_auth(source)
        self.assertIn(nginxauth.GLOBAL_BEGIN, rendered)
        self.assertIn("return 308 https://mostdef.ru$request_uri;", rendered)
        self.assertIn('auth_basic "Valery Manager";', rendered)
        self.assertIn('add_header Strict-Transport-Security "max-age=31536000" always;', rendered)
        self.assertEqual(rendered.count(nginxauth.GLOBAL_BEGIN), 1)

    def test_rendered_output_never_contains_secret_literals(self) -> None:
        renderer_source = RENDERER.read_text(encoding="utf-8")
        for text in (renderer_source, AUTHENTIK_GOLDEN, BASIC_AUTH_GOLDEN):
            self.assertNotIn(EDGE_AUTH_FIXTURE_SECRET, text)
            self.assertNotIn("set $edge_auth", text)
            self.assertNotRegex(text, r"(?m)^\s*set\s+\$")
        for text in (AUTHENTIK_GOLDEN, BASIC_AUTH_GOLDEN):
            self.assertIn(f"include {DEFAULT_EDGE_AUTH_INCLUDE};", text)

    def test_materialize_never_expands_or_reads_the_edge_secret_include(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            snippets = root / "snippets"
            snippets.mkdir()
            edge_snippet = snippets / "sea-speed-edge-auth.conf"
            edge_snippet.write_text(f'set $edge_auth "{EDGE_AUTH_FIXTURE_SECRET}";\n', encoding="utf-8")
            materialized = nginxauth.materialize_sea_speed_includes(
                BASIC_AUTH_GOLDEN, host=BASIC_AUTH_HOST, include_root=snippets
            )
            self.assertEqual(materialized, BASIC_AUTH_GOLDEN)
            self.assertNotIn(EDGE_AUTH_FIXTURE_SECRET, materialized)
            self.assertIn(f"include {DEFAULT_EDGE_AUTH_INCLUDE};", materialized)

    def test_cli_render_and_verify_both_modes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name, source, host, extra in (
                ("authentik", AUTHENTIK_SOURCE, "mostdef.ru", ["--authentik-upstream", AUTHENTIK_UPSTREAM]),
                (
                    "basic-auth",
                    BASIC_AUTH_SOURCE,
                    BASIC_AUTH_HOST,
                    ["--worker-private-listen", BASIC_AUTH_LISTEN, "--worker-private-peer", BASIC_AUTH_PEER],
                ),
            ):
                with self.subTest(mode=name):
                    conf = root / f"{name}-site.conf"
                    candidate = root / f"{name}-candidate.conf"
                    conf.write_text(source, encoding="utf-8")
                    rendered = subprocess.run(
                        [
                            "python3", str(RENDERER), "render",
                            "--config", str(conf), "--output", str(candidate),
                            "--host", host, "--mode", name,
                            "--edge-auth-include", DEFAULT_EDGE_AUTH_INCLUDE, *extra,
                        ],
                        check=True, text=True, capture_output=True,
                    )
                    self.assertIn("SEA_SPEED_AUTH_RENDER=PASS", rendered.stdout)
                    verified = subprocess.run(
                        [
                            "python3", str(RENDERER), "verify",
                            "--config", str(candidate),
                            "--host", host, "--mode", name,
                            "--edge-auth-include", DEFAULT_EDGE_AUTH_INCLUDE, *extra,
                        ],
                        check=True, text=True, capture_output=True,
                    )
                    self.assertIn("SEA_SPEED_AUTH_CONFIG=PASS", verified.stdout)
                    self.assertIn(f"include {DEFAULT_EDGE_AUTH_INCLUDE};", candidate.read_text(encoding="utf-8"))

    @staticmethod
    def _sea_location_bodies(server_text: str) -> list[str]:
        bodies = []
        for spec_text, _start, open_index, close_index in nginxauth._location_blocks(server_text):
            uri = nginxauth._location_uri(spec_text)
            if uri == nginxauth.SEA_SPEED_PREFIX or uri.startswith(nginxauth.SEA_SPEED_PREFIX + "/"):
                bodies.append(server_text[open_index + 1 : close_index])
        return bodies


if __name__ == "__main__":
    unittest.main()
