"""Issue #398 wave 2 demo: behavioral frontend checks vs raw source-text pins.

Target check: the converted road session-watchdog contract in
tests/test_auth_session_frontend_contract.py (executed via
tests/support/frontend_html.py against the page's real inline scripts).

Two-direction proof, mirroring the wave-1 demo:

- Direction A (refactor tolerance): a tmp copy of the real road page whose
  watchdog is reformatted (``const SESSION_WATCHDOG_MS = 15000;`` with
  spaces) and whose internals are renamed (``loadSessionIdentity`` ->
  ``refreshTrustedIdentity``) still satisfies the EXECUTED check, while the
  retired raw-text pins (``const SESSION_WATCHDOG_MS=15000``,
  ``setInterval(loadSessionIdentity,SESSION_WATCHDOG_MS)``) would fail on it.
- Direction B (dead-marker intolerance): a tmp copy that keeps every
  historical marker text verbatim but breaks the wiring (the watchdog
  interval re-registered at 60000 ms) passes the retired text pins and FAILS
  the executed check.

Both directions run against tmp copies only; frontend/ is never modified.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.support import frontend_html

ROAD_PAGE = ROOT / "frontend/sea-speed/road/index.html"


def _refactored_page(html: str) -> str:
    """Reformat the watchdog const and rename the page internals.

    Pure formatting/renaming refactor: same behavior (15 s interval on the
    identity loader, same redirect), different bytes.
    """
    html = html.replace("const SESSION_WATCHDOG_MS=15000;", "const SESSION_WATCHDOG_MS = 15000;")
    html = html.replace("loadSessionIdentity", "refreshTrustedIdentity")
    return html


def _marker_only_broken_page(html: str) -> str:
    """Keep ALL historical marker text verbatim but break the wiring.

    An interceptor installed right after the (verbatim) watchdog const silently
    re-cadences every SESSION_WATCHDOG_MS interval to 60000 ms. The retired
    text pins pass — every marker survives byte-for-byte — while the executed
    check fails because the effective cadence is no longer 15000 ms.
    """
    return html.replace(
        "const SESSION_WATCHDOG_MS=15000;",
        "const SESSION_WATCHDOG_MS=15000;"
        "const __retiredPinsSetInterval=setInterval;"
        "setInterval=(fn,ms)=>__retiredPinsSetInterval(fn,ms===SESSION_WATCHDOG_MS?60000:ms);",
        1,
    )


def _run_converted_check(source: Path) -> tuple[bool, str]:
    """Run the converted behavioral check against a page copy."""
    try:
        frontend_html.run_inline_scripts(source=source)
    except AssertionError as error:
        return False, str(error)
    return True, ""


def _run_retired_text_pins(source: Path) -> tuple[bool, list[str]]:
    """Run the RETIRED raw-text pins against a page copy (for the demo only)."""
    text = source.read_text(encoding="utf-8-sig")
    failed = [
        marker
        for marker in (
            "const SESSION_WATCHDOG_MS=15000",
            "function redirectForReauthentication()",
            "setInterval(loadSessionIdentity,SESSION_WATCHDOG_MS)",
            'credentials:"same-origin"',
        )
        if marker not in text
    ]
    return (not failed), failed


class Test398Wave2Demo(unittest.TestCase):
    def test_refactor_tolerance_and_dead_marker_intolerance(self) -> None:
        real_html = ROAD_PAGE.read_text(encoding="utf-8-sig")
        with tempfile.TemporaryDirectory() as raw:
            # Direction A: behavior-preserving refactor.
            refactored = Path(raw) / "refactored.html"
            refactored.write_text(_refactored_page(real_html), encoding="utf-8")
            converted_ok, converted_error = _run_converted_check(refactored)
            retired_ok, retired_failed = _run_retired_text_pins(refactored)
            self.assertTrue(
                converted_ok,
                f"converted check must tolerate a pure refactor: {converted_error[:400]}",
            )
            self.assertFalse(
                retired_ok,
                f"retired text pins would fail the refactor (expected): {retired_failed}",
            )
            # Direction B: markers kept, wiring broken.
            broken = Path(raw) / "broken.html"
            broken.write_text(_marker_only_broken_page(real_html), encoding="utf-8")
            broken_converted_ok, broken_error = _run_converted_check(broken)
            broken_retired_ok, _ = _run_retired_text_pins(broken)
            self.assertFalse(
                broken_converted_ok,
                "converted check must fail a page whose watchdog interval is "
                f"broken despite intact marker text: {broken_error[:200]}",
            )
            self.assertTrue(
                broken_retired_ok,
                "retired text pins pass the marker-only page (the false-green "
                "the conversion removes)",
            )
            # Sanity: the real page satisfies the converted check.
            real_ok, real_error = _run_converted_check(ROAD_PAGE)
            self.assertTrue(real_ok, f"real page must satisfy the converted check: {real_error[:400]}")


if __name__ == "__main__":
    unittest.main()
