"""Single-writer guard for the crossing-line toggle handler (issue #694).

Issue #694: the road page's crossing-line toggle button (``#cxOffBtn``)
had two independent ``onclick`` implementations — the canonical one in
``frontend/sea-speed/road/main.js`` (error display + ``drawCrossing()``)
and a simplified duplicate in ``frontend/sea-speed/road/config.js``.
main.js assigns the handler while its script executes directly, but
config.js defers its init to ``DOMContentLoaded``, so config.js ran later
and its simplified handler silently overwrote main.js's — the same class
of bug as #680 (a later writer clobbering an earlier one).

This is a static guard, not a behavior test: exactly one ``*.js`` file in
the whole ``frontend/sea-speed`` tree may assign ``cxOffBtn.onclick``, and
it must be ``frontend/sea-speed/road/main.js``. The guard also pins that
``road/config.js`` keeps its boot-status write (``cxStatus.textContent
= ...``) — the fix removes only the duplicate toggle block. Full
click-integration browser coverage arrives with issue #684.

On base 282fe49 both ``road/main.js`` and ``road/config.js`` assign the
handler, so the single-writer assertions FAIL (RED); after the fix removes
the config.js toggle block they pass unchanged (GREEN). The scan is a
raw-text regex scan (stdlib only), mirroring the test_626 oracle
conventions (``utf-8-sig`` reads, sorted ``rglob`` for determinism).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FRONTEND_DIR = ROOT / "frontend" / "sea-speed"
CONFIG_JS = FRONTEND_DIR / "road" / "config.js"

CANONICAL_TOGGLE_WRITER = "frontend/sea-speed/road/main.js"

TOGGLE_ASSIGNMENT_RE = re.compile(r"cxOffBtn\.onclick\s*=")
BOOT_STATUS_RE = re.compile(r"cxStatus\.textContent\s*=")


class SeaSpeedSingleToggleWriterTests(unittest.TestCase):
    """Exactly one file assigns cxOffBtn.onclick, and it is road/main.js."""

    def test_exactly_one_file_assigns_toggle_handler(self) -> None:
        writers = []
        for path in sorted(FRONTEND_DIR.rglob("*.js")):
            text = path.read_text(encoding="utf-8-sig")
            if TOGGLE_ASSIGNMENT_RE.search(text):
                writers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            writers,
            [CANONICAL_TOGGLE_WRITER],
            "issue #694: cxOffBtn.onclick must have exactly one writer "
            f"({CANONICAL_TOGGLE_WRITER}); files assigning it: "
            f"{writers or 'none'}",
        )

    def test_config_js_does_not_assign_toggle_handler(self) -> None:
        text = CONFIG_JS.read_text(encoding="utf-8-sig")
        match = TOGGLE_ASSIGNMENT_RE.search(text)
        self.assertIsNone(
            match,
            "issue #694: frontend/sea-speed/road/config.js still assigns "
            "cxOffBtn.onclick; remove the duplicate simplified toggle block "
            "(road/main.js owns the canonical handler)",
        )

    def test_config_js_keeps_boot_status_write(self) -> None:
        text = CONFIG_JS.read_text(encoding="utf-8-sig")
        match = BOOT_STATUS_RE.search(text)
        self.assertIsNotNone(
            match,
            "issue #694 guard: frontend/sea-speed/road/config.js must keep its "
            "boot-status write (cxStatus.textContent = ...); the fix removes "
            "only the duplicate toggle block",
        )


if __name__ == "__main__":
    unittest.main()
