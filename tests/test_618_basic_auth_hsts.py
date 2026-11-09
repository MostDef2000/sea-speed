"""RED regression tests for MostDef2000/sea-speed#618 (wave-2 task C).

Issue #618: in basic-auth mode the location-level security headers inside
every protected ``/sea-speed*`` location (emitted by
``_basic_auth_location_snippet`` — XCTO, Referrer-Policy, CSP from the
#589 ``SECURITY_HEADERS`` tuple) cancel nginx's ``add_header`` inheritance
of the server-level ``add_header Strict-Transport-Security
"max-age=31536000" always;`` on the 3d.mostdef.ru vhost (nginx semantics:
any location-level ``add_header`` replaces the entire inherited set), so
responses from those paths drop HSTS.

Desired behavior pinned here: the basic-auth location snippet re-emits the
exact HSTS line inside every protected ``/sea-speed*`` location (after the
#589 header block), the server-level HSTS line of the source vhost survives
rendering exactly once outside the location snippets (the renderer never
rewrites server-level directives), ``verify()`` fails closed when the line
is stripped from any one location, and authentik-mode output is untouched
(NO location-level HSTS — its server-level HSTS story is different and out
of #618 scope).

This file pins the DESIRED behavior. On base d60ffdb the emission/idempotency
pins FAIL for the documented current-vs-desired reason (the basic-auth
locations carry no HSTS line, so the removal harness cannot even strip one
and verify() accepts the stripped text); once the fix lands the tests pass
unchanged. No test is weakened, skipped, or xfailed, and no code under test
is mocked.

The renderer module is loaded the same way as
``tests/test_589_security_headers_renderer.py`` (``importlib`` from the file
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

spec = importlib.util.spec_from_file_location("nginx_sea_speed_auth_618", RENDERER)
assert spec and spec.loader
nginxauth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nginxauth)

# The exact HSTS line carried at server level by the 3d.mostdef.ru vhost
# (BASIC_AUTH_SOURCE fixture below) and re-emitted per location by the fix.
HSTS_LINE = 'add_header Strict-Transport-Security "max-age=31536000" always;'

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


class SeaSpeedBasicAuthHstsRendererTests(unittest.TestCase):
    """RED pins: basic-auth /sea-speed* locations must re-emit HSTS (#618)."""

    # -- render/verify helpers (mirror the existing renderer tests) ----------

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

    def _verify_basic_auth(self, text: str, **kwargs) -> None:
        nginxauth.verify(
            text,
            host=BASIC_AUTH_HOST,
            worker_private_listen=BASIC_AUTH_LISTEN,
            worker_private_peer=BASIC_AUTH_PEER,
            mode=nginxauth.MODE_BASIC_AUTH,
            **kwargs,
        )

    # -- structural helpers (mirror the #589 removal-harness idiom) ----------

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
    def _header_line_pattern(line: str) -> re.Pattern:
        # Match the emitted header line with any leading/trailing indentation.
        return re.compile(r"^[ \t]*" + re.escape(line) + r"[ \t]*\r?\n", re.MULTILINE)

    def _remove_hsts_from_one_sea_location(self, rendered: str, host: str) -> str:
        server_start, _open, server_close = nginxauth._server_for_host(rendered, host)
        server_text = rendered[server_start : server_close + 1]
        for spec_text, _start, open_index, close_index in nginxauth._location_blocks(server_text):
            uri = nginxauth._location_uri(spec_text)
            if uri == nginxauth.SEA_SPEED_PREFIX or uri.startswith(nginxauth.SEA_SPEED_PREFIX + "/"):
                body_start = server_start + open_index + 1
                body_end = server_start + close_index
                body = rendered[body_start:body_end]
                new_body, count = self._header_line_pattern(HSTS_LINE).subn("", body, count=1)
                if count:
                    return rendered[:body_start] + new_body + rendered[body_end:]
        return rendered

    # -- tests ---------------------------------------------------------------

    def test_basic_auth_render_emits_hsts_in_every_sea_speed_location(self) -> None:
        rendered = self._render_basic_auth()
        server_text = self._server_text(rendered, BASIC_AUTH_HOST)
        bodies = self._sea_location_bodies(server_text)
        self.assertEqual(len(bodies), 3)
        for body in bodies:
            self.assertIn(HSTS_LINE, body)

    def test_server_level_hsts_survives_rendering_exactly_once(self) -> None:
        rendered = self._render_basic_auth()
        server_text = self._server_text(rendered, BASIC_AUTH_HOST)
        # Outside the renderer-managed location snippets the server-level
        # HSTS line of the source vhost must survive exactly once: the
        # renderer leaves server-level directives alone (not stripped, not
        # duplicated).
        spans = nginxauth._marker_spans(server_text, nginxauth.LOCATION_BEGIN, nginxauth.LOCATION_END)
        outside = []
        index = 0
        for start, finish in spans:
            outside.append(server_text[index:start])
            index = finish
        outside.append(server_text[index:])
        self.assertEqual("".join(outside).count(HSTS_LINE), 1)
        # Whole-server accounting: 1 server-level + 3 location repeats.
        self.assertEqual(server_text.count(HSTS_LINE), 4)

    def test_verify_rejects_hsts_removed_from_one_sea_location(self) -> None:
        rendered = self._render_basic_auth()
        broken = self._remove_hsts_from_one_sea_location(rendered, BASIC_AUTH_HOST)
        self.assertNotEqual(
            broken, rendered, "removal must change the text (HSTS was present)"
        )
        with self.assertRaises(nginxauth.ConfigError):
            self._verify_basic_auth(broken)

    def test_authentik_mode_has_no_location_level_hsts(self) -> None:
        # The negative pin: the fix must not creep into authentik mode — its
        # server-level HSTS story is different and no authentik emission site
        # may grow a location-level HSTS line.
        rendered = self._render_authentik()
        server_text = self._server_text(rendered, "mostdef.ru")
        location_bodies = [
            server_text[open_index + 1 : close_index]
            for _spec_text, _start, open_index, close_index in nginxauth._location_blocks(server_text)
        ]
        self.assertTrue(location_bodies)
        for body in location_bodies:
            self.assertNotIn(HSTS_LINE, body)

    def test_render_idempotent_with_hsts_basic_auth(self) -> None:
        first = self._render_basic_auth()
        second = self._render_basic_auth(first)
        self.assertEqual(first, second)
        server_text = self._server_text(second, BASIC_AUTH_HOST)
        for body in self._sea_location_bodies(server_text):
            self.assertIn(HSTS_LINE, body)


if __name__ == "__main__":
    unittest.main()
