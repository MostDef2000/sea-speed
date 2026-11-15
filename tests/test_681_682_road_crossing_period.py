"""Executed road crossing-period twins for issues #681 and #682 (RED).

These tests pin the agreed design for the road operator page's crossing-period
block (frontend/sea-speed/road/main.js + index.html) and the additive
``last_crossing_at`` field on the crossings summary endpoint. They are written
BEFORE any implementation and MUST be RED on the current tree:

- the API summary (``get_analytics_crossings_summary``) returns no
  ``last_crossing_at`` key;
- the road page HTML has no ``cxLiveBtn`` / ``cxMode`` elements;
- ``cxShowBtn.onclick`` is the 3-second state ``refresh`` (no period mode, no
  summary fetch, no ``crossingStatsMode``), and the date inputs default to UTC
  today (``new Date().toISOString().slice(0,10)``), not VLZ today.

So every scenario below fails on the current tree (a missing summary request,
a missing error row, a missing ``cxLiveBtn`` handler, or a ``cxLast`` that is
the browser clock instead of the summary's ``last_crossing_at``). They turn
GREEN only when the agreed design is implemented.

The scenarios execute the road page's real scripts under the html shim
(tests/support/frontend_html.py), exactly like
tests/test_frontend_contract.py::RoadStreamContractTests: the page boots
against programmable API responses and the scenario drives the recorded
handlers (the ``cxShowBtn`` / ``cxLiveBtn`` click handlers and the 3000 ms
state-refresh interval) the way an operator would. The state crossings
(2 in / 1 out) are the LIVE-mode counts (spec 044 R4/AC-004); the summary
totals (7 in / 3 out) are deliberately distinct so the period-render
assertions prove the numbers came from the summary, not the state.

AC-681-f limitation: the harness has no boot-time clock control, so the date
input defaults (set at boot from the real clock) cannot be pinned to a fixed
VLZ date. That test asserts the deterministic fallback (both inputs non-empty
and equal) and documents the limitation; it is a GREEN-preserving invariant,
not a RED driver.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.support import frontend_html  # noqa: E402

ROAD_PAGE = ROOT / "frontend/sea-speed/road/index.html"

# Boot responses. The state crossings (2 in / 1 out) are the LIVE-mode counts
# (spec 044 R4/AC-004); the summary totals (7 in / 3 out) are deliberately
# distinct so the period-render assertions prove the numbers came from the
# summary, not the state.
ROAD_STATE_STATS_RESPONSE = {
    "match": "/analytics/road1/state",
    "json": {
        "crossings": {
            "left_to_right": 2,
            "right_to_left": 1,
            "by_class": {"car": {"left_to_right": 2, "right_to_left": 1}},
        },
        "frame_width": 1920,
        "frame_height": 1080,
    },
}
ROAD_EVENTS_RESPONSE = {
    "match": "/analytics/road1/events",
    "json": {"events": []},
}
ROAD_SUMMARY_RESPONSE = {
    "match": "/crossings/summary",
    "json": {
        "totals": {"left_to_right": 7, "right_to_left": 3},
        "by_class": {
            "car": {"left_to_right": 5, "right_to_left": 2},
            "truck": {"left_to_right": 2, "right_to_left": 1},
        },
        "last_crossing_at": "2026-11-05T08:30:00+10:00",
    },
}
ROAD_BOOT_RESPONSES = [ROAD_STATE_STATS_RESPONSE, ROAD_EVENTS_RESPONSE, ROAD_SUMMARY_RESPONSE]

SCENARIO_PREAMBLE = """
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  const settle = () => new Promise((r) => setImmediate(r));
  await settle();
  await settle();
"""

# AC-681-a: clicking cxShowBtn with a valid range issues exactly one summary
# request carrying both date params.
PERIOD_REQUEST_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  __record.elements.cxFrom.value = "2026-11-01";
  __record.elements.cxTo.value = "2026-11-05";
  const before = __record.fetch.length;
  await __record.elements.cxShowBtn.onclick();
  await settle();
  const summaryFetches = __record.fetch.slice(before).filter((c) => c.url.includes("crossings/summary"));
  assert(summaryFetches.length === 1, "clicking cxShowBtn must issue exactly one summary request; got " + summaryFetches.length);
  const url = summaryFetches[0].url;
  assert(url.includes("date_from=2026-11-01"), "the summary request must carry date_from=2026-11-01: " + url);
  assert(url.includes("date_to=2026-11-05"), "the summary request must carry date_to=2026-11-05: " + url);
  console.log("###" + JSON.stringify({ url }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# AC-681-b: the period response's totals/by_class render into the KPIs and the
# table (distinct from the state counts).
PERIOD_RENDER_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  __record.elements.cxFrom.value = "2026-11-01";
  __record.elements.cxTo.value = "2026-11-05";
  await __record.elements.cxShowBtn.onclick();
  await settle();
  assert(String(__record.elements.cxStatsIn.textContent) === "7", "the IN kpi must render the summary total (7), not the state count: " + __record.elements.cxStatsIn.textContent);
  assert(String(__record.elements.cxStatsOut.textContent) === "3", "the OUT kpi must render the summary total (3): " + __record.elements.cxStatsOut.textContent);
  assert(String(__record.elements.cxStatsTotal.textContent) === "10", "the total kpi must sum the summary directions (10): " + __record.elements.cxStatsTotal.textContent);
  const rows = __record.elements.cxStatsRows.innerHTML;
  assert(rows.includes("car") && rows.includes("truck"), "the summary rows must break down by class (car + truck): " + rows);
  console.log("###" + JSON.stringify({ in: __record.elements.cxStatsIn.textContent, out: __record.elements.cxStatsOut.textContent, total: __record.elements.cxStatsTotal.textContent }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# AC-681-c: after a period query, a subsequent state render (the 3000 ms
# refresh path) must NOT overwrite the period numbers.
PERIOD_STICKY_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  __record.elements.cxFrom.value = "2026-11-01";
  __record.elements.cxTo.value = "2026-11-05";
  await __record.elements.cxShowBtn.onclick();
  await settle();
  assert(String(__record.elements.cxStatsIn.textContent) === "7", "the period query must render the summary numbers first: in=" + __record.elements.cxStatsIn.textContent);
  const refresh = __record.intervals.find(([, ms]) => ms === 3000);
  assert(refresh, "the 3000 ms state refresh interval is missing");
  await refresh[0]();
  await settle();
  assert(String(__record.elements.cxStatsIn.textContent) === "7", "a subsequent state render must not overwrite the period IN number: " + __record.elements.cxStatsIn.textContent);
  assert(String(__record.elements.cxStatsOut.textContent) === "3", "a subsequent state render must not overwrite the period OUT number: " + __record.elements.cxStatsOut.textContent);
  console.log("###" + JSON.stringify({ in: __record.elements.cxStatsIn.textContent, out: __record.elements.cxStatsOut.textContent }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# AC-681-d: from > to renders an error row and issues NO summary request.
INVALID_RANGE_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  __record.elements.cxFrom.value = "2026-11-05";
  __record.elements.cxTo.value = "2026-11-01";
  const before = __record.fetch.length;
  await __record.elements.cxShowBtn.onclick();
  await settle();
  const summaryFetches = __record.fetch.slice(before).filter((c) => c.url.includes("crossings/summary"));
  assert(summaryFetches.length === 0, "an invalid range (from > to) must issue NO summary request; got " + summaryFetches.length);
  const rows = __record.elements.cxStatsRows.innerHTML.toLowerCase();
  assert(rows.includes("ошибка") || rows.includes("error"), "an invalid range must render an error row in cxStatsRows: " + __record.elements.cxStatsRows.innerHTML);
  console.log("###" + JSON.stringify({ summaryFetches: summaryFetches.length }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# AC-681-e: a summary HTTP failure renders an error row and leaves the
# previous numbers intact.
SUMMARY_FAILURE_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  __record.elements.cxFrom.value = "2026-11-01";
  __record.elements.cxTo.value = "2026-11-05";
  await __record.elements.cxShowBtn.onclick();
  await settle();
  const goodIn = String(__record.elements.cxStatsIn.textContent);
  const goodOut = String(__record.elements.cxStatsOut.textContent);
  assert(goodIn === "7" && goodOut === "3", "the successful period query must render the summary numbers: in=" + goodIn + " out=" + goodOut);
  __responses.length = 0;
  __setResponse("/analytics/road1/state", { crossings: { left_to_right: 2, right_to_left: 1, by_class: { car: { left_to_right: 2, right_to_left: 1 } } }, frame_width: 1920, frame_height: 1080 });
  __setResponse("/analytics/road1/events", { events: [] });
  __setResponse("/crossings/summary", { totals: {}, by_class: {} }, false, 503);
  await __record.elements.cxShowBtn.onclick();
  await settle();
  const rows = __record.elements.cxStatsRows.innerHTML.toLowerCase();
  assert(rows.includes("ошибка") || rows.includes("error"), "a summary HTTP failure must render an error row: " + __record.elements.cxStatsRows.innerHTML);
  assert(String(__record.elements.cxStatsIn.textContent) === goodIn, "a summary failure must leave the previous IN number intact: " + __record.elements.cxStatsIn.textContent);
  assert(String(__record.elements.cxStatsOut.textContent) === goodOut, "a summary failure must leave the previous OUT number intact: " + __record.elements.cxStatsOut.textContent);
  console.log("###" + JSON.stringify({ in: __record.elements.cxStatsIn.textContent, out: __record.elements.cxStatsOut.textContent }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# AC-682-a: cxLast shows the summary's last_crossing_at (formatted
# date+time), NOT the browser clock.
LAST_CROSSING_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  __record.elements.cxFrom.value = "2026-11-01";
  __record.elements.cxTo.value = "2026-11-05";
  await __record.elements.cxShowBtn.onclick();
  await settle();
  const last = String(__record.elements.cxLast.textContent);
  assert(last.includes("2026"), "cxLast must show the summary's last_crossing_at (with the year 2026), not the browser clock: " + last);
  assert(last.includes("08:30") || last.includes("8:30"), "cxLast must show the summary's last_crossing_at time (08:30): " + last);
  assert(last !== new Date().toLocaleTimeString(), "cxLast must not be the browser clock: " + last);
  console.log("###" + JSON.stringify({ last }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# AC-682-b: an empty summary (last_crossing_at: null) renders "Нет данных".
EMPTY_SUMMARY_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  __responses.length = 0;
  __setResponse("/analytics/road1/state", { crossings: { left_to_right: 2, right_to_left: 1, by_class: { car: { left_to_right: 2, right_to_left: 1 } } }, frame_width: 1920, frame_height: 1080 });
  __setResponse("/analytics/road1/events", { events: [] });
  __setResponse("/crossings/summary", { totals: { left_to_right: 0, right_to_left: 0 }, by_class: {}, last_crossing_at: null });
  __record.elements.cxFrom.value = "2026-11-01";
  __record.elements.cxTo.value = "2026-11-05";
  await __record.elements.cxShowBtn.onclick();
  await settle();
  const last = String(__record.elements.cxLast.textContent);
  assert(last.includes("Нет данных"), "an empty summary (last_crossing_at: null) must render 'Нет данных' in cxLast: " + last);
  console.log("###" + JSON.stringify({ last }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# AC-682-c: clicking cxLiveBtn returns to live mode and the next state render
# restores the state counts.
LIVE_RETURN_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  __record.elements.cxFrom.value = "2026-11-01";
  __record.elements.cxTo.value = "2026-11-05";
  await __record.elements.cxShowBtn.onclick();
  await settle();
  assert(String(__record.elements.cxStatsIn.textContent) === "7", "the period query must render the summary numbers first: " + __record.elements.cxStatsIn.textContent);
  assert(typeof __record.elements.cxLiveBtn.onclick === "function", "cxLiveBtn must have a click handler");
  await __record.elements.cxLiveBtn.onclick();
  await settle();
  const refresh = __record.intervals.find(([, ms]) => ms === 3000);
  assert(refresh, "the 3000 ms state refresh interval is missing");
  await refresh[0]();
  await settle();
  assert(String(__record.elements.cxStatsIn.textContent) === "2", "after returning to live mode, the state render must restore the state IN count (2): " + __record.elements.cxStatsIn.textContent);
  assert(String(__record.elements.cxStatsOut.textContent) === "1", "after returning to live mode, the state render must restore the state OUT count (1): " + __record.elements.cxStatsOut.textContent);
  console.log("###" + JSON.stringify({ in: __record.elements.cxStatsIn.textContent, out: __record.elements.cxStatsOut.textContent }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# AC-681-f: the date inputs default to VLZ today (UTC+10). The harness has no
# boot-time clock control, so the defaults (set at boot from the real clock)
# cannot be pinned to a fixed VLZ date. This asserts the deterministic
# fallback: both inputs are non-empty and equal. (Limitation documented in the
# module docstring; this is a GREEN-preserving invariant, not a RED driver.)
DATE_DEFAULTS_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  const from = String(__record.elements.cxFrom.value);
  const to = String(__record.elements.cxTo.value);
  assert(from.length > 0, "cxFrom must default to a non-empty date: " + JSON.stringify(from));
  assert(to.length > 0, "cxTo must default to a non-empty date: " + JSON.stringify(to));
  assert(from === to, "cxFrom and cxTo must default to the same date: from=" + from + " to=" + to);
  console.log("###" + JSON.stringify({ from, to }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)


class RoadCrossingPeriodTests(unittest.TestCase):
    """Executed road crossing-period twins (issues #681/#682)."""

    def test_period_query_issues_one_summary_request_with_both_dates(self) -> None:
        # AC-681-a
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=PERIOD_REQUEST_SCENARIO, responses=ROAD_BOOT_RESPONSES
        )
        self.assertIn("crossings/summary", evidence["url"])

    def test_period_response_renders_into_kpis_and_table(self) -> None:
        # AC-681-b
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=PERIOD_RENDER_SCENARIO, responses=ROAD_BOOT_RESPONSES
        )
        self.assertEqual(evidence["in"], "7")
        self.assertEqual(evidence["out"], "3")
        self.assertEqual(evidence["total"], "10")

    def test_state_refresh_does_not_overwrite_period_numbers(self) -> None:
        # AC-681-c
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=PERIOD_STICKY_SCENARIO, responses=ROAD_BOOT_RESPONSES
        )
        self.assertEqual(evidence["in"], "7")
        self.assertEqual(evidence["out"], "3")

    def test_invalid_range_renders_error_and_issues_no_request(self) -> None:
        # AC-681-d
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=INVALID_RANGE_SCENARIO, responses=ROAD_BOOT_RESPONSES
        )
        self.assertEqual(evidence["summaryFetches"], 0)

    def test_summary_failure_renders_error_and_keeps_previous_numbers(self) -> None:
        # AC-681-e
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=SUMMARY_FAILURE_SCENARIO, responses=ROAD_BOOT_RESPONSES
        )
        self.assertEqual(evidence["in"], "7")
        self.assertEqual(evidence["out"], "3")

    def test_cx_last_shows_summary_last_crossing_at_not_browser_clock(self) -> None:
        # AC-682-a
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=LAST_CROSSING_SCENARIO, responses=ROAD_BOOT_RESPONSES
        )
        self.assertIn("2026", evidence["last"])

    def test_empty_summary_renders_no_data(self) -> None:
        # AC-682-b
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=EMPTY_SUMMARY_SCENARIO, responses=ROAD_BOOT_RESPONSES
        )
        self.assertIn("Нет данных", evidence["last"])

    def test_live_button_returns_to_live_mode_and_restores_state_counts(self) -> None:
        # AC-682-c
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=LIVE_RETURN_SCENARIO, responses=ROAD_BOOT_RESPONSES
        )
        self.assertEqual(str(evidence["in"]), "2")
        self.assertEqual(str(evidence["out"]), "1")

    def test_date_inputs_default_to_same_non_empty_date(self) -> None:
        # AC-681-f (fallback; see module docstring for the clock limitation)
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=DATE_DEFAULTS_SCENARIO, responses=ROAD_BOOT_RESPONSES
        )
        self.assertTrue(evidence["from"])
        self.assertEqual(evidence["from"], evidence["to"])


if __name__ == "__main__":
    unittest.main()
