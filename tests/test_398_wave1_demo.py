"""Issue #398 wave 1 — regression demo for the converted overlay/live pins.

Two directions from the #398 wave-1 plan, demonstrated against mutated
copies of the real ``frontend/sea-speed/live-sync.js`` written to a
temporary directory (the live ``frontend/**`` sources are never touched):

1. Refactor tolerance: a behaviorally identical live-sync module with
   renamed internals and reformatted export map passes every converted
   exec check (export presence, shared-math behavior, road render
   interpolation through the real overlay) — exactly the edits a safe
   refactor makes. The retired source-text presence pin
   (``assertIn("ssMedian", ...)`` &c., formerly
   ``test_module_exists_and_exports_shared_helpers``) false-FAILS on the
   same variant: the marker text is gone while the behavior is intact.
2. Dead-marker intolerance: a variant that keeps every historical marker
   string but breaks ``bracketForMedia`` (unconditional ``return null``)
   passes the retired presence pins — the markers are still in the text —
   while the converted exec checks FAIL it at both the math level and the
   rendered road page level.

Direction contrasts (observed against the pre-conversion test file at
397ed06, re-asserted here on the fixtures):
the retired ``test_module_exists_and_exports_shared_helpers`` pinned the
five markers ``ssMedian / ssClampLag / ssBracketForMedia /
ssClosestEarlierEnvelope / window.SeaSpeedLiveSync`` with ``assertIn``;
the retired ``test_pages_delegate_instead_of_duplicating_sync_math`` and
``test_road_uses_closest_earlier_fallback`` pinned overlay call-shape
text (``SeaSpeedLiveSync.bracketForMedia(mediaMs, {``,
``closestEarlierEnvelope(mediaMs)``, ``LIVE_NEAR_MAX_AGE_MS``). All of
those pins are satisfied by text alone; the converted checks require the
behavior to execute.
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from tests.support import frontend_node
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import frontend_node

# The exact markers the retired presence pin asserted on live-sync.js text.
RETIRED_PRESENCE_MARKERS = (
    "ssMedian",
    "ssClampLag",
    "ssBracketForMedia",
    "ssClosestEarlierEnvelope",
    "window.SeaSpeedLiveSync",
)

# Converted exec probes, kept byte-equivalent to the assertions the
# converted test files make against the real module.
EXPORT_PRESENCE_BODY = """
for (const name of ['median', 'clampLag', 'bracketForMedia', 'closestEarlierEnvelope']) {
  if (typeof S[name] !== 'function') throw new Error('missing export: ' + name);
}
if (window.SeaSpeedLiveSync !== S) throw new Error('export identity broken');
console.log('###OK');
"""

SHARED_MATH_BODY = """
const buf = [
  { generation: 1, capture_time_unix_ms: 1000, camera_id: 'road1', domain: 'road' },
  { generation: 1, capture_time_unix_ms: 1100, camera_id: 'road1', domain: 'road' },
  { generation: 1, capture_time_unix_ms: 1200, camera_id: 'road1', domain: 'road' }
];
const cap = function (e) { return e.capture_time_unix_ms; };
const opts = { liveBuffer: buf, getCaptureMs: cap, lagCompensationMs: 0, maxGapMs: 500 };
const br = S.bracketForMedia(1050, opts);
if (!br || br.lo !== buf[0] || br.hi !== buf[1]) throw new Error('bracket failed');
if (Math.abs(br.t - 0.5) > 1e-9) throw new Error('interpolation t wrong: ' + br.t);
if (S.bracketForMedia(1300, opts) !== null) throw new Error('beyond buffer must be null');
const gen2 = { generation: 2, capture_time_unix_ms: 1250, camera_id: 'road1', domain: 'road' };
if (S.bracketForMedia(1220, { ...opts, liveBuffer: [buf[0], gen2] }) !== null) {
  throw new Error('mixed generation must be null');
}
if (S.closestEarlierEnvelope(1150, opts) !== buf[1]) throw new Error('closest earlier failed');
if (S.clampLag(-5) !== 0 || S.clampLag(6000) !== 1200 || S.clampLag(700) !== 700) {
  throw new Error('clampLag wrong');
}
if (S.median([3, 1, 2]) !== 2 || S.median([1, 2, 3, 4]) !== 2.5) {
  throw new Error('median wrong');
}
console.log('###OK');
"""


def _write_variant(source: str, tmp: str, name: str) -> Path:
    path = Path(tmp) / name
    path.write_text(source, encoding="utf-8")
    return path


def _reformatted_variant() -> str:
    """Behaviorally identical live-sync module with renamed internals and a
    reformatted export map — the kind of edit a safe refactor makes."""
    live = frontend_node.LIVE_SYNC_JS.read_text(encoding="utf-8")
    renames = {
        "ssMedian": "ssComputeMedian",
        "ssClampLag": "ssLimitLag",
        "ssBracketForMedia": "ssFindMediaBracket",
        "ssClosestEarlierEnvelope": "ssLatestAtOrBefore",
        "ssFiniteCaptureValues": "ssFiniteCaptures",
        "ssIsWaterBuffer": "ssLooksLikeWaterBuffer",
        "ssWaterPlaybackLatencyMs": "ssWaterLatencyMs",
        "ssWaterTargetCaptureMs": "ssWaterCaptureTargetMs",
        "ssResolvedTargetMs": "ssResolveTargetMs",
        "ssInstallWaterMediaTimeProbe": "ssInstallMediaTimeProbe",
    }
    for old, new in renames.items():
        live = re.sub(r"\b%s\b" % re.escape(old), new, live)
    header = (
        "// Refactor rehearsal: internals renamed, export map reformatted;\n"
        "// exported contract (window.SeaSpeedLiveSync keys) unchanged.\n"
    )
    return header + live.replace(
        "window.SeaSpeedLiveSync = {\n",
        "window.SeaSpeedLiveSync = {\n  // same public keys, reformatted layout\n",
    )


def _dead_marker_variant() -> str:
    """Keeps every historical marker string but breaks the bracket math:
    ssBracketForMedia returns null unconditionally while the rest of the
    module (and all its text) stays intact."""
    live = frontend_node.LIVE_SYNC_JS.read_text(encoding="utf-8")
    needle = "function ssBracketForMedia(mediaMs, opts) {\n"
    assert needle in live, "live-sync.js ssBracketForMedia signature drifted"
    return live.replace(needle, needle + "  return null; // demo mutation\n", 1)


def _assert_export_presence(source: Path) -> None:
    out = frontend_node.run_live_sync(EXPORT_PRESENCE_BODY, source=source)
    assert out == "###OK", out


def _assert_shared_math(source: Path) -> None:
    out = frontend_node.run_live_sync(SHARED_MATH_BODY, source=source)
    assert out == "###OK", out


def _assert_road_interpolates_x108(source: Path) -> None:
    """The converted road check twin: real overlay + this live-sync source
    must draw the interpolated box at 108 px (envelopes -300/-100 at x1
    0.1/0.2, media time at the bracket midpoint)."""
    calls = frontend_node.overlay_render_calls(
        {"isWater": False},
        [
            frontend_node.envelope(-300, page="road", x1_norm=0.1),
            frontend_node.envelope(-100, page="road", x1_norm=0.2),
        ],
        raw_offset_ms=-200.0,
        live_source=source,
    )
    assert len(calls["strokeRect"]) == 1, calls
    assert abs(calls["strokeRect"][0][0] - 108.0) < 1e-6, calls


class RefactorToleranceTests(unittest.TestCase):
    def test_renamed_reformatted_live_sync_passes_converted_checks(self) -> None:
        # Direction (a): renames + reformat keep every converted exec check
        # green because the exported contract and behavior are unchanged.
        with tempfile.TemporaryDirectory() as tmp:
            variant = _write_variant(_reformatted_variant(), tmp, "live-sync.refactor.js")
            self.assertEqual(frontend_node.run_live_sync(EXPORT_PRESENCE_BODY, source=variant), "###OK")
            self.assertEqual(frontend_node.run_live_sync(SHARED_MATH_BODY, source=variant), "###OK")
            _assert_road_interpolates_x108(variant)
            # The retired presence pin would false-FAIL here: its markers are
            # gone from a perfectly healthy module.
            variant_text = variant.read_text(encoding="utf-8")
            for marker in RETIRED_PRESENCE_MARKERS[:4]:
                self.assertNotIn(marker, variant_text)


class DeadMarkerIntoleranceTests(unittest.TestCase):
    def test_dead_marker_fails_converted_checks_that_retired_pins_pass(self) -> None:
        # Direction (b): the mutation keeps every historical marker string,
        # so the retired presence pin would still pass — asserted here by
        # the same assertIn the old test ran...
        dead_text = _dead_marker_variant()
        for marker in RETIRED_PRESENCE_MARKERS:
            self.assertIn(marker, dead_text)
        # ...while the converted exec checks reject it: the shared-math
        # probe (bracket must bracket) and the rendered road page both fail.
        with tempfile.TemporaryDirectory() as tmp:
            dead = _write_variant(dead_text, tmp, "live-sync.dead-marker.js")
            with self.assertRaises(AssertionError):
                _assert_shared_math(dead)
            with self.assertRaises(AssertionError):
                _assert_road_interpolates_x108(dead)
            # The intact surface around the dead function is genuinely
            # intact: export presence still passes (the old pin's whole
            # view of the world), only the behavior probe catches it.
            _assert_export_presence(dead)


if __name__ == "__main__":
    unittest.main()
