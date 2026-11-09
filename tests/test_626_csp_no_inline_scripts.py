"""CSP-readiness guard oracle for the sea-speed frontend (issue #626).

Issue #626: the sea-speed frontend pages carry inline ``<script>`` blocks and
one HTML-attribute event handler (``onclick="location.reload()"`` on the
unavailable page's retry button). An enforcing Content-Security-Policy for
mostdef.ru ``/sea-speed*`` without ``unsafe-inline`` in ``script-src`` would
block every one of them, so before the edge CSP can flip from
Report-Only to enforcing, the pages must load their scripts from external
files only.

Desired behavior pinned here (R-6 of specs/626-csp-external-scripts/spec.md):

* every ``<script>`` tag in the four front pages (``index.html``,
  ``cameras/index.html``, ``road/index.html``, ``unavailable.html``) carries
  a ``src=`` attribute — no inline script blocks,
* no HTML-attribute event handler (``on[a-z]+=``) appears anywhere in those
  files (JS-assigned ``.onclick = ...`` handlers are CSP-legal and stay),
* the six external scripts extracted by #626 exist and are non-empty,
* ``deploy/vps/deploy.sh`` copies every one of them to the VPS (a merged
  frontend referencing files the deploy does not copy would 404 in
  production).

On base 8f409d2 the inline blocks and the onclick attribute are present and
the external files do not exist, so this oracle FAILS (RED); after the
mechanical extraction it passes unchanged (GREEN). The scan is a raw-text
regex scan (stdlib only): ``<script\\b[^>]*>`` for the src check and
``\\son[a-z]+\\s*=`` for attribute handlers — precise enough for these
pages, which contain no legitimate ``on*``-shaped attribute text.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HTML_PAGES = (
    ROOT / "frontend" / "sea-speed" / "index.html",
    ROOT / "frontend" / "sea-speed" / "cameras" / "index.html",
    ROOT / "frontend" / "sea-speed" / "road" / "index.html",
    ROOT / "frontend" / "sea-speed" / "unavailable.html",
)

NEW_EXTERNAL_SCRIPTS = (
    "frontend/sea-speed/crossing-line.js",
    "frontend/sea-speed/main.js",
    "frontend/sea-speed/cameras/cameras.js",
    "frontend/sea-speed/road/config.js",
    "frontend/sea-speed/road/main.js",
    "frontend/sea-speed/unavailable.js",
)

DEPLOY_SCRIPT = ROOT / "deploy" / "vps" / "deploy.sh"

SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*>", re.IGNORECASE)
ON_ATTRIBUTE_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)


class SeaSpeedCspNoInlineScriptsTests(unittest.TestCase):
    """The four sea-speed pages carry zero inline scripts and zero on*= handlers."""

    def test_every_script_tag_carries_src(self) -> None:
        for page in HTML_PAGES:
            with self.subTest(page=str(page.relative_to(ROOT))):
                html = page.read_text(encoding="utf-8-sig")
                tags = SCRIPT_TAG_RE.findall(html)
                self.assertTrue(tags, f"{page.name}: no <script> tags found at all")
                for tag in tags:
                    self.assertIn(
                        "src=",
                        tag,
                        f"{page.name}: inline <script> block without src= (CSP would block it): {tag}",
                    )

    def test_no_on_attribute_event_handlers(self) -> None:
        for page in HTML_PAGES:
            with self.subTest(page=str(page.relative_to(ROOT))):
                html = page.read_text(encoding="utf-8-sig")
                match = ON_ATTRIBUTE_RE.search(html)
                self.assertTrue(
                    match is None,
                    f"{page.name}: HTML-attribute event handler "
                    f"{match.group(0) if match else ''!r} is blocked by an enforcing "
                    "CSP; move it into an external script",
                )

    def test_external_script_files_exist_and_are_non_empty(self) -> None:
        for relative in NEW_EXTERNAL_SCRIPTS:
            with self.subTest(script=relative):
                path = ROOT / relative
                self.assertTrue(path.is_file(), f"missing external script: {relative}")
                self.assertGreater(
                    path.stat().st_size,
                    0,
                    f"external script is empty: {relative}",
                )

    def test_deploy_script_copies_every_external_script(self) -> None:
        deploy_text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        for relative in NEW_EXTERNAL_SCRIPTS:
            with self.subTest(script=relative):
                self.assertIn(
                    relative,
                    deploy_text,
                    f"deploy/vps/deploy.sh does not reference {relative}; "
                    "the merged frontend would 404 for it in production",
                )


if __name__ == "__main__":
    unittest.main()
