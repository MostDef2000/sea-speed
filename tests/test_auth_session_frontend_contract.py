from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTENDS = (
    ROOT / "frontend/sea-speed/index.html",
    ROOT / "frontend/sea-speed/cameras/index.html",
    ROOT / "frontend/sea-speed/objects/index.html",
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


if __name__ == "__main__":
    unittest.main()
