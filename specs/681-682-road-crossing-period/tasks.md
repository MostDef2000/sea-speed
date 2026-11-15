# Tasks: road crossing period filter drives the panel and the last-crossing time becomes truthful

- Spec: specs/681-682-road-crossing-period/spec.md

## Delivery tasks
- [x] Issue #681: bind `cxShowBtn.onclick` to `loadCrossingStats()` in `frontend/sea-speed/road/main.js` — read `#cxFrom`/`#cxTo`, reject `from > to` client-side (error row + `#cxMode` «период задан неверно», no request), otherwise fetch `/sea-speed/api/analytics/road1/crossings/summary?date_from=..&date_to=..`, render `totals`/`by_class` into the KPIs and table, set `#cxMode` to the applied range, switch `crossingStatsMode` to `"period"`
- [x] Period-view protection: `renderCrossingStats` early-returns unless `crossingStatsMode === "live"` (the 3-second state refresh no longer overwrites the panel); stale-response guard `crossingStatsRequestSeq` discards out-of-order responses
- [x] `#cxLiveBtn` («Текущее») returns to live mode: `crossingStatsMode="live"`, `#cxMode` «текущее состояние», refresh `#cxLast`, `refresh()` restores the state counts; both date inputs default to `vlzToday()` (UTC+10) at boot
- [x] Issue #682 (API): additive `last_crossing_at` in `api/app/analytics.py` crossings summary — the maximum parsed `created_at` among window-filtered records with a valid direction, `null` when none, naive timestamps as UTC, timezone-qualified ISO-8601
- [x] Issue #682 (frontend): delete the browser-clock line; `renderCrossingLast` renders the summary value in Asia/Vladivostok (ru-RU date+time) or «Нет данных» when null/invalid; live mode fetches the VLZ-today summary on boot and every 15 s solely for `#cxLast`, isolated from state/events rendering
- [x] Tests: new `tests/test_681_682_road_crossing_period.py` (`RoadCrossingPeriodTests`, 9 tests); `tests/test_line_crossing.py` extended with `SummaryLastCrossingAtTests` (5 tests)
- [x] RED proof: 13 failed / 1 passed (the 1 = documented non-RED invariant `test_date_inputs_default_to_same_non_empty_date`: date inputs non-empty and equal)
- [x] GREEN: 59 passed across `tests/test_681_682_road_crossing_period.py` + `tests/test_line_crossing.py`
- [x] Full battery green: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` (documented runner) — Ran 1420, OK (skipped=2); no existing test weakened, skipped or mocked; existing road twin `tests/test_frontend_contract.py` (18 road tests) green
- [x] Validators and lint: validate_repo (953 tracked files), validate_contracts, validate_quality_contracts, validate_workflow_policy, validate_token_preflight — all PASS; ruff PASS
- [x] Write the SDD trio `specs/681-682-road-crossing-period/{spec,plan,tasks}.md` and pass `python3 scripts/ci/validate_sdd.py`
- [ ] CI green on the 681/682 PR
- [ ] Merge the 681/682 PR to main
- [ ] VPS redeploy (lane-A) on the merged main SHA so the period filter and the truthful last-crossing time ship to production (orchestrator-owned authorized chain)

## Completion gate
- CI green on the 681/682 PR
- PR merged to main
- VPS redeploy executed in the authorized chain; the road page period filter issues the summary request and renders period numbers that survive the 3-second state refresh, `#cxLast` shows the true last crossing in Vladivostok time, and live mode keeps the spec-044 `state.crossings` behaviour

## Requirements traceability
- AC-001 | Task: bind cxShowBtn.onclick to loadCrossingStats issuing exactly one summary request with both selected dates | Evidence: tests/test_681_682_road_crossing_period.py::RoadCrossingPeriodTests.test_period_query_issues_one_summary_request_with_both_dates; RED before implementation (the handler called refresh(), never the summary endpoint), GREEN after | Coverage: COVERED
- AC-002 | Task: render the period response into KPIs and table and protect it from the 3-second state refresh and stale responses | Evidence: tests/test_681_682_road_crossing_period.py — test_period_response_renders_into_kpis_and_table + test_state_refresh_does_not_overwrite_period_numbers (crossingStatsMode guard; crossingStatsRequestSeq stale-response discipline pinned at source level) | Coverage: COVERED
- AC-003 | Task: client-side range validation and summary-failure handling | Evidence: tests/test_681_682_road_crossing_period.py — test_invalid_range_renders_error_and_issues_no_request (error row, zero requests) + test_summary_failure_renders_error_and_keeps_previous_numbers (error row, previous numbers kept) | Coverage: COVERED
- AC-004 | Task: truthful last-crossing time — additive API field, VLZ rendering, browser clock removed | Evidence: tests/test_681_682_road_crossing_period.py — test_cx_last_shows_summary_last_crossing_at_not_browser_clock + test_empty_summary_renders_no_data; API side tests/test_line_crossing.py::SummaryLastCrossingAtTests (max counted instant in the VLZ window; null when none; timezone-qualified; rolling-hours mode; naive timestamps as UTC) | Coverage: COVERED
- AC-005 | Task: return-to-live control and regression safety | Evidence: tests/test_681_682_road_crossing_period.py — test_live_button_returns_to_live_mode_and_restores_state_counts; tests/test_frontend_contract.py (18 road tests) green; full battery Ran 1420 OK (skipped=2) | Coverage: COVERED

## Definition of Done
- Issue/spec/plan/tasks current
- Exact changed-file scope verified
- Required tests and evidence complete
- Required CI green
- Exact-green-head merge complete
- Deployment state resolved
- Runtime acceptance resolved
- Deferred work recorded
- Risks resolved or explicitly accepted
- Waivers resolved or current
