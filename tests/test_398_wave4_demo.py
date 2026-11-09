"""Issue #398 wave 4 demo: executed frontend twins vs raw source-text pins.

Target check: the converted water-page HLS wiring contract (the page's real
inline scripts execute under the tests/support/frontend_html.py shim; the
check asserts exactly one HLS instance attached to waterMainVideo only,
published as both ``window.hls`` and ``window.waterHls``, and that the
MEDIA_ATTACHED handler loads the protected ``/sea-speed/media/cam1`` path).

Two-direction proof, mirroring the wave-1/2/3 demos:

- Direction A (refactor tolerance): a tmp copy of the real operator page whose
  wiring lines are rewritten behavior-preservingly (spaces around operators on
  the attach/publish/fallback-gate lines, ``connectStream`` renamed to
  ``openMediaStream``, ``notePlaybackProgress`` renamed to
  ``noteMediaProgress``) still satisfies the EXECUTED check, while the retired
  raw-text pins (``instance.attachMedia(waterMainVideo)``,
  ``window.hls=instance;window.waterHls=instance``,
  ``waterMainVideo.addEventListener("timeupdate",notePlaybackProgress)``,
  ``if(s.last_overlay_url&&!playbackIsAdvancing(STREAM_RECOVERY_GRACE_MS))``)
  would all fail on it.
- Direction B (dead-marker intolerance): a tmp copy that keeps every retired
  marker verbatim but breaks the wiring (a stray second ``attachMedia`` binds
  the HLS player to the overlay image too) passes the retired text pins and
  FAILS the executed check.

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

WATER_PAGE = ROOT / "frontend/sea-speed/index.html"
# Issue #626: the page wiring the demos mutate (the HLS wiring) moved out of
# the HTML into the shipped external script, so the mutation surface is the
# .js bytes written next to the tmp HTML copy (the harness resolves relative
# src= targets source-dir-first).
WATER_MAIN_JS = ROOT / "frontend/sea-speed/main.js"

RETIRED_TEXT_PINS = (
    "instance.attachMedia(waterMainVideo)",
    "window.hls=instance;window.waterHls=instance",
    'waterMainVideo.addEventListener("timeupdate",notePlaybackProgress)',
    "if(s.last_overlay_url&&!playbackIsAdvancing(STREAM_RECOVERY_GRACE_MS))",
)

# The compact executed twin the demo proves: the same wiring contract the
# converted suite pins (one instance, main-video attach, dual publication,
# protected loadSource), driven against a page copy.
EXECUTED_HLS_SCENARIO = (
    ";(async () => {\n"
    + """
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  const settle = () => new Promise((r) => setImmediate(r));
  await settle();
  __record.timeouts.splice(0).forEach(([fn]) => fn());
  await settle();
  const instances = __record.hlsInstances;
  assert(instances.length === 1, "one HLS instance expected, got " + instances.length);
  const inst = instances[0];
  assert(
    inst.attached.length === 1 && inst.attached[0].id === "waterMainVideo",
    "HLS must attach to waterMainVideo only: " + JSON.stringify(inst.attached.map((e) => e && e.id))
  );
  assert(window.hls === inst && window.waterHls === inst, "the instance must be published as window.hls and window.waterHls");
  for (const handler of inst.handlers.hlsMediaAttached || []) await handler();
  assert(
    JSON.stringify(inst.sources) === JSON.stringify(["/sea-speed/media/cam1/index.m3u8"]),
    "MEDIA_ATTACHED must loadSource the protected water HLS path; got " + JSON.stringify(inst.sources)
  );
  console.log("###" + JSON.stringify({ sources: inst.sources }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)


def _refactored_page(html: str, main_js: str) -> tuple[str, str]:
    """Rewrite the wiring idioms; identical boot/connect/fallback behavior.

    Applies to the page HTML and the shipped main.js wiring (issue #626
    moved the water page's wiring out of the HTML into external/main.js).
    """
    main_js = main_js.replace(
        "instance.attachMedia(waterMainVideo)",
        "instance.attachMedia( waterMainVideo )",
    )
    main_js = main_js.replace(
        "window.hls=instance;window.waterHls=instance",
        "window.hls = instance; window.waterHls = instance",
    )
    main_js = main_js.replace(
        "if(s.last_overlay_url&&!playbackIsAdvancing(STREAM_RECOVERY_GRACE_MS))",
        "if (s.last_overlay_url && !playbackIsAdvancing(STREAM_RECOVERY_GRACE_MS))",
    )
    main_js = main_js.replace("connectStream", "openMediaStream")
    main_js = main_js.replace("notePlaybackProgress", "noteMediaProgress")
    return html, main_js


def _marker_only_broken_page(html: str, main_js: str) -> tuple[str, str]:
    """Keep ALL retired marker text verbatim but break the player binding.

    A stray second attach right after the (verbatim) main-video attach binds
    the HLS player to the overlay image as well. The retired text pins pass —
    every marker survives byte-for-byte — while the executed check fails
    because the player is attached to two elements. The stray attach installs
    into the shipped main.js bytes (issue #626).
    """
    anchor = "instance.attachMedia(waterMainVideo)"
    replacement = (
        anchor
        + ';instance.attachMedia(document.getElementById("overlayImg"))'
        + "/* demo interceptor: stray second attach while keeping every marker */"
    )
    assert anchor in main_js, "water attach anchor changed; demo needs an update"
    return html, main_js.replace(anchor, replacement, 1)


def _run_executed_hls_check(page_text: str, main_js_text: str, tmp: Path) -> tuple[bool, str]:
    """Run the converted behavioral check against a page copy in tmp.

    Issue #626: the copy's wiring ships as main.js next to it (the harness
    resolves relative src= targets source-dir-first); each call writes both
    files so a direction never inherits the previous direction's .js.
    """
    copy = tmp / "index.html"
    copy.write_text(page_text, encoding="utf-8")
    (tmp / "main.js").write_text(main_js_text, encoding="utf-8")
    try:
        frontend_html.run_inline_scripts(source=copy, scenario=EXECUTED_HLS_SCENARIO)
    except AssertionError as exc:
        return False, str(exc)[-400:]
    return True, ""


def _run_retired_text_pins(page_text: str, main_js_text: str) -> tuple[bool, list[str]]:
    """Run the RETIRED raw-text pins against a page copy (demo only).

    Issue #626: the pinned code moved into the shipped external main.js, so
    the scan surface is the page HTML plus the .js bytes being executed.
    """
    failed = [
        marker
        for marker in RETIRED_TEXT_PINS
        if marker not in page_text + main_js_text
    ]
    return (not failed), failed


class Test398Wave4Demo(unittest.TestCase):
    def test_refactor_tolerance_and_dead_marker_intolerance(self) -> None:
        real_page = WATER_PAGE.read_text(encoding="utf-8-sig")
        real_js = WATER_MAIN_JS.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            # Direction A: behavior-preserving refactor.
            refactored_html, refactored_js = _refactored_page(real_page, real_js)
            refactored_ok, refactored_error = _run_executed_hls_check(refactored_html, refactored_js, tmp)
            retired_ok, retired_failed = _run_retired_text_pins(refactored_html, refactored_js)
            self.assertTrue(
                refactored_ok,
                f"executed check must tolerate a pure refactor: {refactored_error}",
            )
            self.assertFalse(
                retired_ok,
                f"retired text pins would fail the refactor (expected): {retired_failed}",
            )
            # Direction B: markers kept, wiring broken.
            broken_html, broken_js = _marker_only_broken_page(real_page, real_js)
            broken_ok, broken_error = _run_executed_hls_check(broken_html, broken_js, tmp)
            broken_retired_ok, _ = _run_retired_text_pins(broken_html, broken_js)
            self.assertFalse(
                broken_ok,
                "executed check must fail a page whose player binding is broken "
                f"despite intact marker text: {broken_error}",
            )
            self.assertTrue(
                broken_retired_ok,
                "retired text pins pass the marker-only page (the false-green "
                "the conversion removes)",
            )
            # Sanity: the real page satisfies the executed check (tmp copy —
            # no repo mutation).
            real_ok, real_error = _run_executed_hls_check(real_page, real_js, tmp)
            self.assertTrue(real_ok, f"real page must satisfy the executed check: {real_error}")


if __name__ == "__main__":
    unittest.main()
