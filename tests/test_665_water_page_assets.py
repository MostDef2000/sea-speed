"""Issue #665: the water page breaks when served at the nested URL
/sea-speed/water/ because its local <script src> values are relative.

The water operator page (frontend/sea-speed/index.html) is served both at
/sea-speed/ and at the nested /sea-speed/water/ alias. A relative src such as
"./main.js" resolves against the page's own URL, so at /sea-speed/water/ the
browser requests /sea-speed/water/main.js and 404s — the page loads without
its scripts. Every local script must therefore be referenced by a
same-origin absolute path under /sea-speed/, and the only allowed exception
is the pinned hls.js CDN artifact (issue #575), which must keep its
Subresource Integrity attribute.

Desired behavior pinned here:

* AC-1: no <script src> value is relative — every src is either a
  same-origin absolute path (starts with "/sea-speed/") or the pinned CDN
  hls.js (https://cdn.jsdelivr.net/...) carrying an integrity attribute,
* AC-2: the three local scripts are referenced by their exact absolute
  paths: /sea-speed/crossing-line.js, /sea-speed/main.js,
  /sea-speed/live-sync.js,
* AC-3: script execution order is preserved — the full ordered src list is
  [crossing-line.js, CDN hls.js, overlay-canvas.js, main.js, live-sync.js].

On base b9168c8 the three local scripts are referenced as "./crossing-line.js",
"./main.js" and "./live-sync.js", so this oracle FAILS (RED); after the
mechanical rewrite to absolute paths it passes unchanged (GREEN). The scan is
a raw-text regex scan (stdlib only), mirroring
tests/test_626_csp_no_inline_scripts.py.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATER_HTML = ROOT / "frontend" / "sea-speed" / "index.html"

SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*>", re.IGNORECASE)
SRC_ATTR_RE = re.compile(r'\bsrc\s*=\s*"([^"]*)"', re.IGNORECASE)

# Pinned hls.js CDN artifact (issue #575): the production-proven 1.5.7
# release, loaded with Subresource Integrity (same pin as
# tests/test_frontend_contract.py).
HLS_PINNED_SRC = "https://cdn.jsdelivr.net/npm/hls.js@1.5.7/dist/hls.min.js"

LOCAL_SCRIPTS = (
    "/sea-speed/crossing-line.js",
    "/sea-speed/main.js",
    "/sea-speed/live-sync.js",
)

EXPECTED_SCRIPT_ORDER = (
    "/sea-speed/crossing-line.js",
    HLS_PINNED_SRC,
    "/sea-speed/overlay-canvas.js",
    "/sea-speed/main.js",
    "/sea-speed/live-sync.js",
)


def script_srcs(html: str) -> list[tuple[str, str]]:
    """(tag, src) for every <script src=...> tag, in document order."""
    pairs = []
    for tag in SCRIPT_TAG_RE.findall(html):
        match = SRC_ATTR_RE.search(tag)
        if match:
            pairs.append((tag, match.group(1)))
    return pairs


class WaterPageAbsoluteAssetTests(unittest.TestCase):
    """The water page references every script by an absolute path (issue #665)."""

    def setUp(self) -> None:
        self.html = WATER_HTML.read_text(encoding="utf-8-sig")
        self.srcs = script_srcs(self.html)

    def test_page_carries_script_tags(self) -> None:
        self.assertTrue(self.srcs, "index.html: no <script src> tags found at all")

    def test_no_relative_script_srcs(self) -> None:
        # AC-1: every src is a same-origin absolute /sea-speed/ path or the
        # pinned CDN hls.js with an integrity attribute — nothing relative.
        for tag, src in self.srcs:
            with self.subTest(src=src):
                if src.startswith("/sea-speed/"):
                    continue
                if src.startswith("https://cdn.jsdelivr.net/"):
                    self.assertIn(
                        "integrity=",
                        tag,
                        f"CDN script {src} must carry a Subresource Integrity attribute",
                    )
                    continue
                self.fail(
                    f"relative or foreign script src {src!r}: at the nested "
                    "/sea-speed/water/ URL it resolves against the page URL and 404s; "
                    "use a same-origin absolute /sea-speed/ path"
                )

    def test_local_scripts_use_exact_absolute_paths(self) -> None:
        # AC-2: the three local scripts are referenced by exact absolute paths.
        src_list = [src for _, src in self.srcs]
        for expected in LOCAL_SCRIPTS:
            with self.subTest(script=expected):
                self.assertIn(
                    expected,
                    src_list,
                    f"local script must be referenced by the exact absolute path {expected}",
                )

    def test_script_execution_order_preserved(self) -> None:
        # AC-3: the full ordered src list is unchanged by the rewrite.
        src_list = [src for _, src in self.srcs]
        self.assertEqual(
            src_list,
            list(EXPECTED_SCRIPT_ORDER),
            "script execution order changed: the water page depends on "
            "crossing-line.js before hls.js, hls.js before overlay-canvas.js, "
            "and main.js/live-sync.js last",
        )


if __name__ == "__main__":
    unittest.main()
