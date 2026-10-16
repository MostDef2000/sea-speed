# Plan: #398 wave 1 — overlay/live text-pin conversion (node exec)

- Issue: #398
- Specification: specs/398-wave1/spec.md

## Architecture

Convert the overlay/live cluster to execution-based checks by executing the real frontend JS in node from Python tests, replacing the Python mirror implementations and their text-marker tethers. Harness: tests/support/frontend_node.py (new) — `run_node` (subprocess with embedded stderr), window shim (`global.window = global` so overlay-canvas.js's bare `SeaSpeedLiveSync` reference resolves), stubbed `setInterval` (node would hang on the real one), recording 2d-context DOM stub (`__makeOverlayDom`), stub video with no-op `requestVideoFrameCallback`, envelope builders with per-page defaults (water: cam1/sea; road: road1/road), and render-call extraction helpers. Assertions are made on the recording stub's calls (stroke coordinates, clear operations, letterboxing) — real bytes, no DOM, no network.

## Decisions

- D-1: water mirror RETIRES. The old Python mirror was subtly wrong: `render_fallback_on_bracket_failure` anchored the bounded near-window on its target argument (the Water target `maxCapture − latencyMs`), while the REAL overlay anchors the near-window on `mediaMs = raw − lagCompensationMs` (overlay-canvas.js:259-270) — the mirror could pass while the JS drifted. Exec twins pin the real semantics.
- D-2: road mirror RETIRES. Its `test_no_interpolate_across_generation` exercised an UNREACHABLE state: `overlay-canvas.js:179-185` resets `liveBuffer` on any generation bump, so a mixed-generation buffer cannot arise through the public flow. Replaced by `test_generation_bump_resets_and_draws_new_generation` (reset + verbatim new-gen draw).
- D-3: live_overlay delegation checks become spy-exec (spy installed before `init`/`startLoop`; `__makeOverlayDom` before init — the overlay requires `document`; lag math requires ≥20 samples → 25-render loop). Anti-duplication pins stay verbatim.
- D-4: STATIC_POLICY pins are never converted: forbidden `localStorage`/`sessionStorage`, `rtsp://user:pass@` regex, anti-copy/anti-dup markers, forbidden regression forms (guard L54–61), include tags, `new Hls(`==1, `attachMedia(waterMainVideo)`, `drawLive(liveBuffer[...])` absence.
- D-5: in-repo conversion models only — the node harness pattern from tests/test_live_overlay_sync.py (wave A); no new frameworks.
- D-6: SP/wiring markers on page HTML (include tags) retained as text pins — the include tag IS the contract (deployed page references exactly this script).

## Site-mapping table (old → replacement)

| Old site (base 397ed06) | Class | Replacement |
|---|---|---|
| test_water_overlay_sync: mirrors `water_target_capture_ms`, `bracket_for_target`, `closest_earlier_envelope`, `render_fallback_on_bracket_failure` (L13–69) | RB mirror | 6 exec twins via harness (target+bracket math exec; clock-offset invariance; fail-closed ×3; near-pref draw; beyond-2s clear; future-only clear) — no page-config-acceptance or byte-identity test |
| test_water_overlay_sync: verbatim marker block (live-sync pins `function ssWaterPlaybackLatencyMs()`, `function ssWaterTargetCaptureMs(opts)`, `return Math.max(...captures) - latencyMs;`, `latest.camera_id === "cam1"`, `ssInstallWaterMediaTimeProbe();` + overlay pins) — present verbatim at test_water_overlay_sync.py:170-185 | SP | verbatim retention (`test_frontend_source_contains_relative_sync_markers`) |
| test_live_overlay_sync: marker pins (`ssMedian`, `ssClampLag`, `ssBracketForMedia`, `ssClosestEarlierEnvelope`, `window.SeaSpeedLiveSync`) in `test_module_exists_and_exports_shared_helpers` | SS | retired-with-executed-twin (level: exec): export presence asserted on the live module object — no verbatim retention |
| test_water_live_sync_guard: 7 text-pin tests (JS control-flow proxies) | RB | 8 exec twins (probe sentinel ×3, resolvedTargetMs branches, seekable-latency fallback, water-only mapping, bounded near draw/clear, no-latest-draw, age-agnostic bracket, interp) |
| test_water_live_sync_guard: forbidden regression forms L54–61 + Hls/attachMedia pins | SP | verbatim retention |
| test_live_overlay_sync: export-presence via text | SS | exec-based export check (module loads, API surface asserted on live object) |
| test_live_overlay_sync: overlay call-shape pins (`SeaSpeedLiveSync.bracketForMedia(mediaMs, {`, `closestEarlierEnvelope(mediaMs)`, `LIVE_NEAR_MAX_AGE_MS`) | RB | spy-exec delegation (call observed on real module with ≥20 lag samples) |
| test_live_overlay_sync: include tags + anti-dup markers | SP | verbatim retention |
| test_road_overlay_sync: `interpolate_boxes` ×2, `bracket_for_media` ×5, content-box ±1px mirrors | RB/SS | 8 exec twins vs real road JS (4 math via `S.bracketForMedia`, 4 rendered via the real road overlay on the harness DOM); p95 test stays |
| test_water_overlay_sync: `render_fallback_on_bracket_failure` conflation | (drift instance) | documented here; reachable-state twins pin real semantics |

## Affected contours

- None of deploy/** — tests-only; no UBUNTU_WORKER/DEPLOY contour files touched. Union-scan owner rule: no fixed-subset scan is retired (the converted files were not union-scan members); tests/support/ additions do not affect MODULE_SOURCES gate.

## Validation

- Focused: the 4 converted files + demo green (exact tails in tests_run evidence).
- Full battery vs baseline 1035 passed / 4 skipped (both 0b1c0b3 and 397ed06 baselines), per-file delta table in the PR evidence.
- validate_sdd + validate_repo green; allowed-paths-only check.

## Runtime feedback

- CI exact-head on the merge PR is the runtime surface (RF-001 in spec); no deploy, no on-box effect.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: node availability is a proven CI capability (wave-A node harness already green in CI since #474); no new CI capability introduced | Validation: CI exact-head run on the merge PR; local node v22.22.1 verified in three worker sessions | Residual risk: a CI runner without node would fail loudly at wave-A tests before this wave matters | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: harness ordering pitfalls are pinned by the suites themselves: DOM stub installed before `init()` (overlay-canvas.js:24 requires document), spies installed before first render, lag math exercised with 25 renders (≥20-sample threshold at overlay-canvas.js:223), `setInterval` stubbed to avoid hang | Validation: the two root causes found and fixed this wave (stderr-embedded assertions); focused runs green | Residual risk: future JS init-shape changes could break the stub — fails loudly, not silently | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: DATA | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: accidental SP-pin loss is impossible to miss: the mapping table enumerates every retained pin, the battery count delta must be non-negative per file, and peer review re-enumerates the pins verbatim | Validation: reviewer enumeration; battery delta accounting | Residual risk: a future PR could delete a pin — the same review gate applies then | Owner: delivery orchestrator | Status: MITIGATED
- RISK-004 | Category: PERF | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: node spawns are bounded (per-test scenario, demo ~6 spawns ≈1.5s); battery timing compared to baseline in final evidence | Validation: full battery run | Residual risk: runner variance — bounded by spawn count, no retries needed | Owner: delivery orchestrator | Status: MITIGATED
- RISK-005 | Category: DATA | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: demo mutations operate on tmp copies of live-sync.js (repo files untouched); cleanup in finally | Validation: demo test isolation assertions; git status clean after suite | Residual risk: none identified | Owner: delivery orchestrator | Status: MITIGATED
- RISK-006 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: retired mirror semantics (water conflation, road unreachable-state) are recorded in this trio so the historical intent is recoverable; exec twins are stricter than the mirrors | Validation: demo dead-marker direction proves the converted checks cannot be fooled by dead text | Residual risk: none — old false-coverage removed, not added | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001, R-1 | Level: unit | Priority: P0 | Evidence: converted water/guard/road suites execute real JS bytes via frontend_node.py (focused runs green); site-mapping table enumerates old→new
- TEST-002 | Covers: AC-002, R-2 | Level: unit | Priority: P0 | Evidence: SP pins verbatim in converted files (reviewer enumeration against the mapping table)
- TEST-003 | Covers: AC-003, R-3 | Level: integration | Priority: P1 | Evidence: tests/test_398_wave1_demo.py — both directions (refactor tolerance, dead-marker intolerance), 2 passed
- TEST-004 | Covers: AC-004, R-4, R-5 | Level: integration | Priority: P0 | Evidence: full battery green with accounted deltas; deterministic repeats across sessions
- TEST-005 | Covers: AC-005, AC-006 | Level: integration | Priority: P1 | Evidence: validate_sdd green; validate_repo green; allowed-paths check

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: none — no production learning, no pivot, no material scope change.
