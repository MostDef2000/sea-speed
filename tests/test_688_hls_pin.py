"""Issue #688 — hls.js pin refresh 1.5.7 → 1.7.4 across the operator pages.

The frontend contract tests pin the URL and SRI per page; this file adds the
cross-page guarantees of the refresh itself: the three shipped tags are the
same bytes (up to leading indentation), the exact 1.7.4 URL + sha384 SRI are
literal constants here, no stale 1.5.7 reference survives in the three pages,
and the pinned SRI is a well-formed sha384 digest.

Real browser playback of the 1.7.4 artifact is RUNTIME-MANUAL pending deploy —
these tests assert the shipped markup only.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAGE_FILES = (
    ROOT / "frontend" / "sea-speed" / "index.html",
    ROOT / "frontend" / "sea-speed" / "road" / "index.html",
    ROOT / "frontend" / "sea-speed" / "cameras" / "index.html",
)

# Exact literals for the refreshed pin (issue #688), verified by the
# orchestrator against the CDN bytes and the npm-published dist.integrity.
HLS_PINNED_SRC = "https://cdn.jsdelivr.net/npm/hls.js@1.7.4/dist/hls.min.js"
HLS_SRI_INTEGRITY = "sha384-p9vgU/7IYJWd3I4STrtqxqR/2cAQlhIX7D/HrTnIMEjjcUox165b7se7sxmm3zDg"
EXPECTED_TAG = (
    f'<script src="{HLS_PINNED_SRC}" integrity="{HLS_SRI_INTEGRITY}" '
    'crossorigin="anonymous"></script>'
)

CDN_TAG_RE = re.compile(r"<script\b[^>]*hls\.js[^>]*>.*?</script>", re.DOTALL)
SHA384_RE = re.compile(r"^sha384-[A-Za-z0-9+/]+={0,2}$")


def page_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def hls_tags(text: str) -> list[str]:
    """Raw hls.js <script>...</script> tags in document order (comments included:
    a commented tag would still be a stale 1.5.7 reference worth failing on)."""
    return CDN_TAG_RE.findall(text)


class Hls688PinRefreshTests(unittest.TestCase):
    def test_the_three_hls_tags_are_byte_identical_after_indentation(self) -> None:
        """AC: normalized tag extraction yields three identical hls.js tags."""
        stripped_sets = []
        for path in PAGE_FILES:
            with self.subTest(page=path.name):
                tags = hls_tags(page_text(path))
                self.assertEqual(
                    len(tags), 1,
                    f"{path}: expected exactly one hls.js script tag, got {len(tags)}",
                )
                stripped_sets.append(tags[0].strip())
        self.assertEqual(
            len(set(stripped_sets)), 1,
            "the water/road/cameras hls.js tags differ beyond leading whitespace: "
            f"{stripped_sets}",
        )

    def test_each_tag_is_the_exact_1_7_4_literal(self) -> None:
        """Pin the exact URL + SRI + crossorigin as literals (no @latest)."""
        for path in PAGE_FILES:
            with self.subTest(page=path.name):
                tags = hls_tags(page_text(path))
                self.assertEqual(len(tags), 1, f"{path}: expected one hls.js tag")
                self.assertEqual(
                    tags[0].strip(), EXPECTED_TAG,
                    f"{path}: hls.js tag must be exactly the #688 1.7.4 pin",
                )

    def test_no_stale_1_5_7_reference_remains_in_the_three_pages(self) -> None:
        """Completion gate: no `hls.js@1.5.7` remains in the three pages."""
        for path in PAGE_FILES:
            with self.subTest(page=path.name):
                self.assertNotIn(
                    "hls.js@1.5.7", page_text(path),
                    f"{path}: stale hls.js@1.5.7 reference must be gone",
                )

    def test_pinned_sri_is_a_well_formed_sha384_digest(self) -> None:
        self.assertRegex(HLS_SRI_INTEGRITY, SHA384_RE)
        # A sha384 digest is 48 bytes → 64 base64 chars (padded to a multiple
        # of 4; 64 is already one, so no '=' padding here).
        self.assertEqual(len(HLS_SRI_INTEGRITY.removeprefix("sha384-")), 64)


if __name__ == "__main__":
    unittest.main()
