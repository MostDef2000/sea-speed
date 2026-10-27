from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.support import frontend_html

FRONTENDS = (
    ROOT / "frontend/sea-speed/index.html",
    ROOT / "frontend/sea-speed/cameras/index.html",
    ROOT / "frontend/sea-speed/objects/index.html",
    ROOT / "frontend/sea-speed/road/index.html",
)


class AuthSessionFrontendContractTests(unittest.TestCase):
    def test_all_protected_frontends_use_same_origin_session_api(self) -> None:
        for path in FRONTENDS:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8-sig")
                self.assertIn('/sea-speed/api/session', text)
                self.assertNotIn('/outpost.goauthentik.io/auth/nginx', text)
                self.assertNotIn('headers.get("X-authentik-username")', text)
                self.assertIn('username', text)
                self.assertIn('credentials:"same-origin"', text)

    def test_logout_and_lighthouse_contract_is_preserved(self) -> None:
        for path in FRONTENDS:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8-sig")
                self.assertIn('href="/outpost.goauthentik.io/sign_out"', text)
                self.assertIn('class="project-home" href="/"', text)
                self.assertNotIn("localStorage", text)
                self.assertNotIn("sessionStorage", text)

    def test_operator_keeps_protected_camera_media_path(self) -> None:
        text = (ROOT / "frontend/sea-speed/index.html").read_text(encoding="utf-8-sig")
        self.assertIn('/sea-speed/media/cam1/index.m3u8', text)
        self.assertNotIn('/cams/hls/cam1/index.m3u8', text)

    def test_road_session_watchdog_matches_protected_operator_semantics(self) -> None:
        # Behavioral conversion (issue #398 wave 2): the page's real inline
        # scripts execute in node under the frontend_html shim — the 15 s
        # watchdog wiring, the same-origin session fetch, the identity
        # population and the identity-loss redirect are asserted on the
        # executed page, not on its formatting (reformatting or renaming
        # internals keeps this green; breaking the wiring fails it even when
        # the historical marker text survives).
        evidence = frontend_html.run_inline_scripts()
        self.assertIn(
            frontend_html.WATCHDOG_MS,
            [interval["ms"] for interval in evidence["intervals"]],
            "15 s session watchdog interval missing",
        )
        self.assertTrue(evidence["sessionFetches"], "session endpoint never fetched")
        self.assertEqual(evidence["sessionFetches"][0].get("credentials"), "same-origin")
        self.assertEqual(evidence["sessionUser"], "operator")
        self.assertEqual(evidence["redirects"], [frontend_html.REDIRECT_PATH])


if __name__ == "__main__":
    unittest.main()
