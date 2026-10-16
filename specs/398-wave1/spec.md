# Spec: #398 wave 1 — overlay/live text-pin conversion (node-exec)

- Issue: #398
- Specification: specs/398-wave1/spec.md
- Authorization: six-field Scope for #398 approved by the owner (OUTCOME APPROVED, 2026-10-16); this wave = overlay/live cluster of that scope.

## Product outcome

The overlay/live regression cluster stops verifying frontend behavior by reading JS source files as raw text and starts verifying it by executing the real JS bytes in node. The Python "mirror" reimplementations of water and road overlay math retire; every former text-pin that proxied behavior becomes an execution assertion against `frontend/sea-speed/live-sync.js` / `overlay-canvas.js`; STATIC_POLICY pins (forbidden patterns, anti-duplication, include tags) stay verbatim. Two drift-invisibility instances found by the conversion are documented (water mirror conflation bug; road mirror testing an unreachable mixed-generation state).

## User scenarios

- A developer renames a local variable or reformats an overlay JS function: CI stays green for identifiers that are not SP-pinned (old text-pins would have failed — false failure eliminated). Exception by D-4 design: the retained verbatim water marker block still text-pins three function names (`ssWaterPlaybackLatencyMs`, `ssWaterTargetCaptureMs`, `ssInstallWaterMediaTimeProbe`), and renaming those deliberately fails CI — those SP-pinned names remain text-locked.
- A developer deletes the delegated math from live-sync.js while leaving the marker text in a dead branch: the converted check fails (old text-pin would have passed — false pass eliminated).
- A future wave touches frontend bytes without changing behavior: the converted suites keep passing, so review attention goes to real diffs.

## Scope

- tests/test_water_overlay_sync.py, tests/test_water_live_sync_guard.py, tests/test_live_overlay_sync.py, tests/test_road_overlay_sync.py — rewritten per the #398 inventory (RB→exec, SS→exec/parse, SP verbatim).
- tests/support/frontend_node.py (new, additive) — node-exec harness: run_node with window shim, DOM stub, envelope builders, page configs.
- tests/test_398_wave1_demo.py (new) — two-direction regression demonstration.
- specs/398-wave1/** — this trio.
- NO production surface: frontend/**, api/**, worker/**, deploy/**, scripts/**, .github/** untouched.

## Requirements

- R-1 (AC-001): water/road Python mirrors retire; every behavioral assertion they carried is replaced by an execution twin against the real JS bytes via tests/support/frontend_node.py; no assertion is lost without an executed twin or verbatim STATIC_POLICY retention (mapping table in plan.md Decisions).
- R-2 (AC-002): STATIC_POLICY pins stay verbatim — forbidden `localStorage`/`sessionStorage`, `rtsp://user:pass@` regex, anti-copy/anti-duplication markers, forbidden regression forms (guard L54–61), include tags, `new Hls(`==1, `attachMedia(waterMainVideo)`, `drawLive(liveBuffer[...])` absence.
- R-3 (AC-003): tests/test_398_wave1_demo.py proves both directions: (a) refactor tolerance — equivalent JS refactoring no longer fails the converted checks; (b) dead-marker intolerance — marker text present without behavior FAILS the converted check where the old text-pin passed.
- R-4 (AC-004): road overlay suite verifies the real road JS flow; the unreachable mixed-generation mirror case is replaced by the real semantics (generation bump resets liveBuffer, then draws the new generation verbatim).
- R-5 (AC-005): the suite is deterministic in CI — no network, tmp-isolated node mutations, no dependence on runner-state beyond node + repo bytes.
- R-6 (AC-006): full battery green with per-file deltas accounted (never weaker); validate_repo, validate_sdd green; changed files limited to the allowed set.

## Acceptance criteria

- AC-001: focused run of the 4 converted files + demo is green; water and road mirrors no longer exist in the test files.
- AC-002: the SP pin set enumerated in plan.md's mapping table is present verbatim in the converted files (reviewer-checked).
- AC-003: `tests/test_398_wave1_demo.py` passes with both explicit directions (refactor-tolerant AND dead-marker-intolerant).
- AC-004: full battery `pytest tests/ -q` green; count delta vs baseline 1035 passed / 4 skipped justified site-by-site in the final evidence.
- AC-005: `python3 scripts/ci/validate_sdd.py` green for this trio; `validate_repo.py` green.
- AC-006: `git status`/diff shows only the allowed paths.

## Runtime feedback

- RF-001: Operator actions expected: 0 — tests-only change; no deploy is required and no production artifact changes. Runtime acceptance = exact-head CI green on the merge PR (the node-exec suites run in CI as part of the battery).
- RF-002: CI precedent: the node harness model already runs in CI (tests/test_live_overlay_sync.py node tests since #398 wave A) — no new CI capability is introduced by this wave.

## NFR assessment

- NFR-001 | Area: reliability | Target: converted suites are deterministic (no network, no real browser, deterministic DOM stub; node subprocess per scenario with embedded stderr in failures) | Validation: focused runs repeated across sessions; demo isolates mutations in tmp with cleanup | Evidence: focused tails final tree (water 7, guard 8 incl. seekable fallback twin, live 5, road 9, demo 2 passed); full battery 1038 passed / 4 skipped | Status: PASS
- NFR-002 | Area: coverage | Target: zero coverage loss — every removed text assertion maps to an executed twin or a retained verbatim SP pin; two former false-coverage instances (water mirror conflation, road unreachable state) replaced by reachable-state assertions | Validation: site-mapping table in plan.md; peer review enumeration | Evidence: tests_run evidence + review | Status: PASS
- NFR-003 | Area: performance | Target: battery wall time does not materially regress (node spawns ~1.5s for the demo; per-test spawn overhead bounded) | Validation: full battery timing comparison vs baseline | Evidence: tests_run tails | Status: PASS
- NFR-004 | Area: maintainability | Target: ONE harness module (tests/support/frontend_node.py) instead of per-test JS plumbing; house conversion models only (node harness from wave A, bash extraction, AST helpers) | Validation: reviewer check that no new framework/pattern was invented | Evidence: diff review | Status: PASS
