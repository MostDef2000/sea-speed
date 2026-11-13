# Plan: water page absolute local script paths (nested /sea-speed/water/ URL)

- Specification: specs/665-water-page-absolute-assets/spec.md

## Architecture
Pure frontend-path fix plus test-harness adaptation. The water operator page is served at two URLs (/sea-speed/ and the /sea-speed/water/ alias); relative script srcs resolve against the page URL, so only same-origin absolute paths survive both. Three src values in frontend/sea-speed/index.html change from ./<name>.js to /sea-speed/<name>.js; nothing else in the file changes. The executed-script harness (tests/support/frontend_html.py external_local_scripts) learns that same-origin absolute /sea-speed/... srcs are local files resolved to frontend/sea-speed/<name>.js, keeping the wave demos' tmp-copy mutation sensitivity through a next-to-the-source-first probe.

## Decisions
- Same-origin absolute srcs (not `<base>` or server-side rewrites): the page already references /sea-speed/overlay-canvas.js absolutely (#631) and the road page references live-sync.js/overlay-canvas.js absolutely — the rewrite makes every local src uniform and is exactly what the RED oracle pins.
- The harness change is additive, not a behavior rewrite: relative ./x.js resolution keeps its exact existing path (source-dir-first, then the page's real frontend directory); only the previously blanket-skipped absolute branch is narrowed — /sea-speed/... becomes local, every other absolute src stays skipped, https:// CDN sources stay skipped.
- /sea-speed/overlay-canvas.js stays excluded from the executed set: the shim's recording SeaSpeedOverlayCanvas stub populates the __record.overlayInits/workerActive evidence the executed page twins assert (test_frontend_contract water/road worker twins); executing the real overlay-canvas.js would silently replace the stub and empty those records.
- Absolute-src resolution probes a same-named file next to the source FIRST, then frontend/sea-speed/<name>.js: test_398_wave4_demo writes a mutated main.js next to its tmp HTML copy and its Direction B (dead-marker intolerance) depends on that copy winning.
- Accepted side effect, verified assertion-neutral: /sea-speed/live-sync.js joins the road page's executed set (the road page already references it absolutely). live-sync.js at module level only installs the waterMainVideo getStartDate probe and publishes window.SeaSpeedLiveSync — no timers, no fetch — and no structural assertNotIn pin matches its body (checked across all harness consumers).

## Affected contours
- VPS (release tree): frontend/sea-speed/index.html (already shipped by deploy/vps/deploy.sh — allowlist untouched, no new files)
- tests/support/frontend_html.py (harness), tests/test_live_overlay_sync.py (stale pin)
- specs/665-water-page-absolute-assets/ (spec, plan, tasks)
- Explicitly unchanged: deploy/** (allowlist untouched), frontend/sea-speed/road/**, frontend/sea-speed/objects/**, frontend/sea-speed/cameras/**, worker/**, .github/**

## Validation
- `python3 -m unittest tests.test_665_water_page_assets -v` → Ran 4 tests, OK (RED on base b9168c8: Ran 4 tests, FAILED failures=7).
- `python3 -m unittest tests.test_live_overlay_sync tests.test_398_wave4_demo tests.test_626_csp_no_inline_scripts tests.test_water_live_sync_guard -v` → Ran 18 tests, OK.
- `python3 -m unittest tests.test_frontend_contract -v` → Ran 38 tests, OK.
- Focused blast-radius run of the remaining harness consumers (test_398_wave2_demo, test_line_crossing, test_roi_normalization, test_analytics_profiles, test_auth_session_frontend_contract, test_auth_logout_contract, test_water_passage, test_api_contract) → Ran 127 tests, OK.
- `git diff --stat` → only frontend/sea-speed/index.html, tests/test_live_overlay_sync.py, tests/support/frontend_html.py plus this trio.
- `python3 scripts/ci/validate_sdd.py` green with the new trio.

## Runtime feedback
- Issue #665: at /sea-speed/water/ the browser requested /sea-speed/water/main.js (and siblings) and got 404s — the page rendered without its scripts.
- The absolute pattern is already production-proven on this page: /sea-speed/overlay-canvas.js (#631) resolves identically at both URLs.

## Risk profile
- Risk profile: NOT REQUIRED

This PR ships a three-line src rewrite in an already-shipped file plus test-only changes: the deploy allowlist is untouched (no new files), the executed script set and order are unchanged, and the harness consumers gate the merge — no risk-profile rows are required (same disposition as the 656/633 frontend changes).

## Test design
- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_665_water_page_assets.py 4/4 OK (src presence, no relative srcs, exact absolute paths, preserved execution order); RED authenticity observed on base b9168c8 (Ran 4 tests, FAILED failures=7)
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: tests.test_live_overlay_sync + tests.test_398_wave4_demo + tests.test_626_csp_no_inline_scripts + tests.test_water_live_sync_guard → Ran 18 tests, OK (wave-4 Direction B proves the mutated tmp main.js still wins resolution)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: tests.test_frontend_contract → Ran 38 tests, OK (recorded-evidence contract unchanged: overlayInits/workerActive stub records intact)
- TEST-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: full battery run by the delivery orchestrator before merge (unittest discover output in the PR delivery record)

## Correct-course check
- Trigger: NONE
- Issue impact: requirements stable — the fix is the mechanical rewrite the issue describes
- Specification impact: none — the spec matches the locked design (absolute srcs, additive harness adaptation)
- Plan impact: none — the harness change stayed additive as planned
- Tasks impact: none — delivery tasks executed as written
- Authorization impact: NONE
- Follow-up: sibling-page relative-src exposure (road/objects/cameras) recorded report-only in the delivery record; no change required for their canonical URLs

## Deployment transaction audit
- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged, no changes applied | Retry: N/A | Rollback: N/A | Evidence: SDD validators green on the #665 PR
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: Server assets unchanged, relative-src page still served | Retry: N/A | Rollback: N/A | Evidence: deploy workflow ancestry and trusted-CI gates on the merged main SHA
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: Absolute-src index.html served via Caddy, previous assets intact | Retry: Re-deploy previous SHA | Rollback: Revert to the previous main SHA | Evidence: Lane-A deploy workflow run artifacts
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: Acceptance probe fails, scripts 404 at /sea-speed/water/ | Retry: Re-run probes | Rollback: Revert to previous SHA | Evidence: /sea-speed/water/ probe — page HTML lists /sea-speed/*.js srcs, zero script 404s
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Merge commit recorded in git | Retry: Re-merge | Rollback: Revert merge commit | Evidence: Merge commit SHA on main
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: JOURNAL entry pending | Retry: Re-record | Rollback: N/A | Evidence: JOURNAL.md entry
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Probe logs missing | Retry: Re-run probes | Rollback: N/A | Evidence: Probe output captured in the PR delivery record
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: Previous SHA restored on server | Retry: Re-attempt rollback | Rollback: N/A | Evidence: Rollback commit SHA
