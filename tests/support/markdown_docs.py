"""Minimal markdown structure scanning for governance-doc contract tests.

Issue #398 wave 6: replaces raw substring-in-file pins on governance docs
with section-scoped structural assertions. Stdlib-only line scanner — no new
dependencies. Fence-aware: ATX headings inside ```/~~~ fenced blocks never
split sections, so embedded templates/JSON stay inside their section.
"""

from __future__ import annotations

import re

PREAMBLE = "(preamble)"

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^(```|~~~)")


def sections(text: str) -> list[tuple[str, str]]:
    """Split a markdown document into (heading, body) pairs at ATX headings.

    The document preamble is returned with heading ``(preamble)``. Fenced
    code blocks stay inside their enclosing section, so embedded templates
    and JSON examples keep their placement.
    """
    result: list[tuple[str, str]] = []
    heading = PREAMBLE
    body: list[str] = []
    fence = ""
    for line in text.splitlines():
        if fence:
            if line.lstrip().startswith(fence):
                fence = ""
            body.append(line)
            continue
        fence_match = _FENCE_RE.match(line.lstrip())
        if fence_match:
            fence = fence_match.group(1)
            body.append(line)
            continue
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            if body or heading != PREAMBLE:
                result.append((heading, "\n".join(body)))
            heading = heading_match.group(2)
            body = []
            continue
        body.append(line)
    if body or heading != PREAMBLE:
        result.append((heading, "\n".join(body)))
    return result


def section_containing(text: str, *markers: str) -> tuple[str, str] | None:
    """First (heading, body) whose heading+body contains every marker, else None.

    Markers match case-insensitively and must co-occur within ONE section
    (heading or body), so a marker that drifts into an unrelated section
    fails the placement contract instead of passing file-wide.
    """
    needles = [marker.lower() for marker in markers]
    for heading, body in sections(text):
        haystack = f"{heading}\n{body}".lower()
        if all(marker in haystack for marker in needles):
            return heading, body
    return None


def section_titled(text: str, *title_fragments: str) -> tuple[str, str] | None:
    """First section whose heading contains every title fragment, else None.

    Title fragments match case-insensitively against the heading line only,
    pinning content to the RIGHT section rather than anywhere in the file.
    """
    needles = [fragment.lower() for fragment in title_fragments]
    for heading, body in sections(text):
        lowered = heading.lower()
        if all(fragment in lowered for fragment in needles):
            return heading, body
    return None


def fenced_blocks(body: str) -> list[list[str]]:
    """Return the line lists of every fenced code block in a section body."""
    blocks: list[list[str]] = []
    current: list[str] = []
    fence = ""
    for line in body.splitlines():
        if fence:
            if line.lstrip().startswith(fence):
                blocks.append(current)
                current = []
                fence = ""
            else:
                current.append(line)
            continue
        fence_match = _FENCE_RE.match(line.lstrip())
        if fence_match:
            fence = fence_match.group(1)
    return blocks
