"""RED acceptance oracle for MostDef2000/sea-speed#589 (wave-1 task C, phase 1).

Issue #589: the nginx vhost renderer (``scripts/operations/nginx_sea_speed_auth.py``)
must emit a security-header set on the Sea Speed edge vhost. This file pins the
DESIRED behavior. On the current base (ab901e06) every test here FAILS for the
documented current-vs-desired reason (the renderer does not emit the headers
yet); once the fix lands the tests pass unchanged. No test is weakened, skipped,
or xfailed, and no code under test is mocked.

The frozen design (what the fix WILL do):

Three headers, emitted with nginx ``add_header ... always;``:

1. ``add_header X-Content-Type-Options "nosniff" always;``
2. ``add_header Referrer-Policy "strict-origin-when-cross-origin" always;``
3. ``add_header Content-Security-Policy "default-src 'self'; script-src 'self'
   https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; connect-src
   'self'; media-src 'self' blob:; img-src 'self' data:; frame-ancestors
   'none'" always;``

Emission sites (authentik mode): server-level via the global marked block
(GLOBAL_BEGIN..GLOBAL_END body — the server-level position inside ``server{}``),
PLUS repeats inside every protected ``/sea-speed*`` location and inside the
fallback outage location (nginx ``add_header`` inheritance is broken by any
location-level ``add_header``, so the server-level headers do not reach those
locations on their own). Basic-auth mode: repeats inside every protected
``/sea-speed*`` location; NO server-level requirement. Outpost/signin locations
(proxied Authentik content) deliberately get NO CSP and are not tested here.

The renderer module is loaded the same way as
``tests/test_sea_speed_edge_vhost_renderer.py`` (``importlib`` from the file
path), so no ``api`` modules are imported and no ``sys.modules`` eviction is
needed. Every import is stdlib, so the ``run_tests`` import-hygiene scan needs
no registration tuple.
"""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts/operations/nginx_sea_speed_auth.py"

spec = importlib.util.spec_from_file_location("nginx_sea_speed_auth_589", RENDERER)
assert spec and spec.loader
nginxauth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nginxauth)

# The three frozen security-header lines (exact, unindented). The renderer
# emits them with server/location indentation; the substring checks below are
# indentation-agnostic, and the removal helpers match any leading whitespace.
HEADER_NOSNIFF = 'add_header X-Content-Type-Options "nosniff" always;'
HEADER_REFERRER = 'add_header Referrer-Policy "strict-origin-when-cross-origin" always;'
HEADER_CSP = (
    "add_header Content-Security-Policy "
    "\"default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
    "media-src 'self' blob:; img-src 'self' data:; frame-ancestors 'none'\" "
    "always;"
)
HEADER_LINES = (HEADER_NOSNIFF, HEADER_REFERRER, HEADER_CSP)

# Fixture sources and parameters mirror tests/test_sea_speed_edge_vhost_renderer.py
# (the same vhost contours the existing golden tests render).
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

BASIC_AUTH_HOST = "3d.mostdef.ru"
BASIC_AUTH_LISTEN = "10.123.239.101:18080"
BASIC_AUTH_PEER = "10.123.239.102"
AUTHENTIK_UPSTREAM = "http://10.123.239.102:19000"


class SeaSpeedSecurityHeadersRendererTests(unittest.TestCase):
    """RED pins: the renderer must emit the #589 security-header set."""

    # -- render/verify helpers (mirror the existing renderer test) ----------

    def _render_authentik(self, source: str = AUTHENTIK_SOURCE, **kwargs) -> str:
        return nginxauth.render(source, authentik_upstream=AUTHENTIK_UPSTREAM, **kwargs)

    def _render_basic_auth(self, source: str = BASIC_AUTH_SOURCE, **kwargs) -> str:
        return nginxauth.render(
            source,
            host=BASIC_AUTH_HOST,
            worker_private_listen=BASIC_AUTH_LISTEN,
            worker_private_peer=BASIC_AUTH_PEER,
            mode=nginxauth.MODE_BASIC_AUTH,
            **kwargs,
        )

    def _verify_authentik(self, text: str, **kwargs) -> None:
        nginxauth.verify(text, authentik_upstream=AUTHENTIK_UPSTREAM, **kwargs)

    def _verify_basic_auth(self, text: str, **kwargs) -> None:
        nginxauth.verify(
            text,
            host=BASIC_AUTH_HOST,
            worker_private_listen=BASIC_AUTH_LISTEN,
            worker_private_peer=BASIC_AUTH_PEER,
            mode=nginxauth.MODE_BASIC_AUTH,
            **kwargs,
        )

    # -- structural helpers --------------------------------------------------

    @staticmethod
    def _server_text(rendered: str, host: str) -> str:
        server_start, _open, server_close = nginxauth._server_for_host(rendered, host)
        return rendered[server_start : server_close + 1]

    @staticmethod
    def _sea_location_bodies(server_text: str) -> list[str]:
        bodies = []
        for spec_text, _start, open_index, close_index in nginxauth._location_blocks(server_text):
            uri = nginxauth._location_uri(spec_text)
            if uri == nginxauth.SEA_SPEED_PREFIX or uri.startswith(nginxauth.SEA_SPEED_PREFIX + "/"):
                bodies.append(server_text[open_index + 1 : close_index])
        return bodies

    @staticmethod
    def _fallback_location_body(server_text: str) -> str | None:
        for spec_text, _start, open_index, close_index in nginxauth._location_blocks(server_text):
            if nginxauth._location_uri(spec_text) == nginxauth.FALLBACK_URI:
                return server_text[open_index + 1 : close_index]
        return None

    @staticmethod
    def _global_block_body(rendered: str) -> str:
        begin = rendered.index(nginxauth.GLOBAL_BEGIN)
        end = rendered.index(nginxauth.GLOBAL_END)
        return rendered[begin:end]

    @staticmethod
    def _header_line_pattern(line: str) -> re.Pattern:
        # Match the emitted header line with any leading/trailing indentation.
        return re.compile(r"^[ \t]*" + re.escape(line) + r"[ \t]*\r?\n", re.MULTILINE)

    def _remove_header_lines(self, text: str, lines: tuple[str, ...]) -> str:
        for line in lines:
            text = self._header_line_pattern(line).sub("", text)
        return text

    def _remove_header_from_one_sea_location(self, rendered: str, host: str, line: str) -> str:
        server_start, _open, server_close = nginxauth._server_for_host(rendered, host)
        server_text = rendered[server_start : server_close + 1]
        for spec_text, _start, open_index, close_index in nginxauth._location_blocks(server_text):
            uri = nginxauth._location_uri(spec_text)
            if uri == nginxauth.SEA_SPEED_PREFIX or uri.startswith(nginxauth.SEA_SPEED_PREFIX + "/"):
                body_start = server_start + open_index + 1
                body_end = server_start + close_index
                body = rendered[body_start:body_end]
                new_body, count = self._header_line_pattern(line).subn("", body, count=1)
                if count:
                    return rendered[:body_start] + new_body + rendered[body_end:]
        return rendered

    # -- tests ---------------------------------------------------------------

    def test_authentik_render_emits_security_headers_server_level(self) -> None:
        rendered = self._render_authentik()
        global_body = self._global_block_body(rendered)
        for line in HEADER_LINES:
            with self.subTest(header=line):
                self.assertIn(line, global_body)

    def test_authentik_render_repeats_headers_in_every_sea_speed_location(self) -> None:
        rendered = self._render_authentik()
        server_text = self._server_text(rendered, "mostdef.ru")
        bodies = self._sea_location_bodies(server_text)
        self.assertEqual(len(bodies), 2)
        for body in bodies:
            for line in HEADER_LINES:
                with self.subTest(header=line):
                    self.assertIn(line, body)

    def test_authentik_render_repeats_headers_in_fallback_location(self) -> None:
        rendered = self._render_authentik()
        server_text = self._server_text(rendered, "mostdef.ru")
        fallback_body = self._fallback_location_body(server_text)
        self.assertIsNotNone(fallback_body)
        for line in HEADER_LINES:
            with self.subTest(header=line):
                self.assertIn(line, fallback_body)

    def test_basic_auth_render_repeats_headers_in_every_sea_speed_location(self) -> None:
        rendered = self._render_basic_auth()
        server_text = self._server_text(rendered, BASIC_AUTH_HOST)
        bodies = self._sea_location_bodies(server_text)
        self.assertEqual(len(bodies), 3)
        for body in bodies:
            for line in HEADER_LINES:
                with self.subTest(header=line):
                    self.assertIn(line, body)

    def test_verify_rejects_missing_server_level_headers(self) -> None:
        rendered = self._render_authentik()
        begin = rendered.index(nginxauth.GLOBAL_BEGIN)
        end = rendered.index(nginxauth.GLOBAL_END)
        block = self._remove_header_lines(rendered[begin:end], HEADER_LINES)
        broken = rendered[:begin] + block + rendered[end:]
        with self.assertRaises(nginxauth.ConfigError):
            self._verify_authentik(broken)

    def test_verify_rejects_missing_location_repeat(self) -> None:
        for mode, render_fn, verify_fn, host in (
            ("authentik", self._render_authentik, self._verify_authentik, "mostdef.ru"),
            ("basic-auth", self._render_basic_auth, self._verify_basic_auth, BASIC_AUTH_HOST),
        ):
            with self.subTest(mode=mode):
                rendered = render_fn()
                broken = self._remove_header_from_one_sea_location(rendered, host, HEADER_NOSNIFF)
                self.assertNotEqual(
                    broken, rendered, "removal must change the text (header was present)"
                )
                with self.assertRaises(nginxauth.ConfigError):
                    verify_fn(broken)

    def test_headers_carry_always_flag_and_no_secret_literals(self) -> None:
        for mode, render_fn in (
            ("authentik", self._render_authentik),
            ("basic-auth", self._render_basic_auth),
        ):
            with self.subTest(mode=mode):
                rendered = render_fn()
                for line in HEADER_LINES:
                    with self.subTest(header=line):
                        pattern = re.compile(r"^[ \t]*" + re.escape(line) + r"[ \t]*$", re.MULTILINE)
                        match = pattern.search(rendered)
                        self.assertIsNotNone(match, f"emitted header line not found: {line}")
                        self.assertTrue(
                            match.group(0).strip().endswith("always;"),
                            f"emitted header line must end with 'always;': {match.group(0)!r}",
                        )
        csp_value = HEADER_CSP.split('"', 1)[1].rsplit('"', 1)[0]
        for secret in ("password", "token", "key"):
            self.assertNotIn(secret, csp_value.lower())

    def test_render_idempotent_with_headers_both_modes(self) -> None:
        for mode, render_fn in (
            ("authentik", self._render_authentik),
            ("basic-auth", self._render_basic_auth),
        ):
            with self.subTest(mode=mode):
                first = render_fn()
                for line in HEADER_LINES:
                    with self.subTest(header=line):
                        self.assertIn(line, first)
                second = render_fn(first)
                self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
