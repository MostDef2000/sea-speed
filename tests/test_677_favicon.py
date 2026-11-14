"""Issue #677: no Sea Speed page carries a favicon.

None of the six Sea Speed HTML pages (water, road, cameras, objects,
unavailable, public landing) declares a favicon, so browsers fall back to
requesting /favicon.ico and render the default glyph. The fix is one inline
SVG data-URI favicon <link> pasted verbatim into each page's <head> — inline
data-URI rather than a favicon file precisely so that deploy/vps/deploy.sh
needs no change (no new static asset to copy).

Desired behavior pinned here:

* AC-001: each of the six pages contains a <link> whose rel is "icon",
  whose type is "image/svg+xml" and whose href starts with
  "data:image/svg+xml," — and the six hrefs are byte-identical to each
  other (one icon, everywhere),
* AC-002: the data-URI percent-decodes to a string that parses as XML
  (xml.dom.minidom.parseString) and is at most 600 bytes,
* the decoded SVG keeps the brand colours #041725 (background) and
  #81d5e0 (wave stroke), guarding against a silently swapped icon.

On base cefd446 none of the six pages contains any <link> tag at all, so
this oracle FAILS (RED); after inserting the favicon <link> into each
<head> it passes unchanged (GREEN). The scan is a comment-stripped
raw-text regex scan (stdlib only), mirroring tests/test_665_water_page_assets.py and
tests/test_626_csp_no_inline_scripts.py.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote
from xml.dom.minidom import parseString

ROOT = Path(__file__).resolve().parents[1]

HTML_PAGES = (
    ROOT / "frontend" / "sea-speed" / "index.html",
    ROOT / "frontend" / "sea-speed" / "road" / "index.html",
    ROOT / "frontend" / "sea-speed" / "cameras" / "index.html",
    ROOT / "frontend" / "sea-speed" / "objects" / "index.html",
    ROOT / "frontend" / "sea-speed" / "unavailable.html",
    ROOT / "frontend" / "root" / "index.html",
)

LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
ATTR_RE = {
    name: re.compile(rf'\b{name}\s*=\s*"([^"]*)"', re.IGNORECASE)
    for name in ("rel", "type", "href")
}

MAX_DECODED_BYTES = 600
BRAND_COLOURS = ("#041725", "#81d5e0")


def favicon_links(html: str) -> list[str]:
    """Every <link> tag whose rel attribute is exactly "icon".

    Scans comment-stripped text so a favicon link commented out of a
    page is not counted.
    """
    icons = []
    for tag in LINK_TAG_RE.findall(HTML_COMMENT_RE.sub("", html)):
        rel = ATTR_RE["rel"].search(tag)
        if rel and rel.group(1).strip().lower() == "icon":
            icons.append(tag)
    return icons


class FaviconDataUriTests(unittest.TestCase):
    """All six Sea Speed pages carry the same inline SVG data-URI favicon."""

    def setUp(self) -> None:
        # Comment-stripped text: every scan and the placement assertions
        # below must ignore favicon links that live inside HTML comments.
        self.pages = {
            page: HTML_COMMENT_RE.sub("", page.read_text(encoding="utf-8-sig"))
            for page in HTML_PAGES
        }
        self.icons = {page: favicon_links(html) for page, html in self.pages.items()}
        self.hrefs = {
            page: [ATTR_RE["href"].search(tag).group(1) for tag in icons]
            for page, icons in self.icons.items()
        }

    def test_every_page_carries_exactly_one_svg_data_uri_favicon(self) -> None:
        # AC-001: one favicon <link> per page, rel="icon",
        # type="image/svg+xml", href starting with the svg data-URI scheme,
        # placed inside <head>.
        for page in HTML_PAGES:
            with self.subTest(page=str(page.relative_to(ROOT))):
                icons = self.icons[page]
                self.assertEqual(
                    len(icons),
                    1,
                    f"{page.name}: expected exactly one rel=icon <link>, found {len(icons)}",
                )
                tag = icons[0]
                self.assertEqual(
                    ATTR_RE["type"].search(tag).group(1).strip().lower(),
                    "image/svg+xml",
                    f"{page.name}: favicon link must declare type image/svg+xml: {tag}",
                )
                href = self.hrefs[page][0]
                self.assertTrue(
                    href.startswith("data:image/svg+xml,"),
                    f"{page.name}: favicon href must be an inline svg data-URI, got {href[:40]!r}…",
                )
                text = self.pages[page]
                head_open = re.search(r"<head\b", text, re.IGNORECASE)
                head_close = re.search(r"</head\s*>", text, re.IGNORECASE)
                self.assertIsNotNone(
                    head_open,
                    f"{page.name}: no <head> element found",
                )
                self.assertIsNotNone(
                    head_close,
                    f"{page.name}: no </head> element found",
                )
                tag_at = text.find(tag)
                self.assertGreater(
                    tag_at,
                    head_open.start(),
                    f"{page.name}: favicon <link> must sit inside <head>",
                )
                self.assertLess(
                    tag_at,
                    head_close.start(),
                    f"{page.name}: favicon <link> must sit inside <head>",
                )

    def test_all_six_hrefs_are_byte_identical(self) -> None:
        # AC-001: one icon everywhere — the six hrefs must be byte-identical.
        flat = [href for hrefs in self.hrefs.values() for href in hrefs]
        self.assertEqual(len(flat), len(HTML_PAGES), "expected one favicon href per page")
        self.assertEqual(
            len(set(flat)),
            1,
            "favicon hrefs differ between pages; every page must carry the "
            "byte-identical data-URI from shared/sea-speed-favicon/favicon-datauri.txt",
        )

    def test_data_uri_decodes_to_valid_compact_svg(self) -> None:
        # AC-002: the data-URI percent-decodes to XML-parseable SVG ≤ 600 bytes.
        href = self.hrefs[HTML_PAGES[0]][0]
        decoded = unquote(href.removeprefix("data:image/svg+xml,"))
        decoded_bytes = decoded.encode("utf-8")
        self.assertLessEqual(
            len(decoded_bytes),
            MAX_DECODED_BYTES,
            f"decoded favicon SVG is {len(decoded_bytes)} bytes, cap is {MAX_DECODED_BYTES}",
        )
        document = parseString(decoded)  # raises on malformed XML
        self.assertEqual(
            document.documentElement.tagName,
            "svg",
            "decoded favicon payload must be an <svg> document",
        )

    def test_decoded_svg_keeps_brand_colours(self) -> None:
        # Guard against a silently swapped icon: the brand background and
        # wave-stroke colours must survive in the decoded SVG.
        href = self.hrefs[HTML_PAGES[0]][0]
        decoded = unquote(href.removeprefix("data:image/svg+xml,"))
        for colour in BRAND_COLOURS:
            self.assertIn(
                colour,
                decoded,
                f"decoded favicon SVG lost brand colour {colour}",
            )


if __name__ == "__main__":
    unittest.main()
