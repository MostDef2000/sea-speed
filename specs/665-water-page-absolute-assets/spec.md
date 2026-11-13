# Spec: water page absolute local script paths (nested /sea-speed/water/ URL)

- Issue: #665

## Product outcome
The water operator page (frontend/sea-speed/index.html) is served both at /sea-speed/ and at the nested /sea-speed/water/ alias. Its three local `<script src>` values are relative (`./crossing-line.js`, `./main.js`, `./live-sync.js`), so at /sea-speed/water/ the browser resolves them against the page URL and requests /sea-speed/water/main.js etc., which 404 — the page boots without its scripts. The fix rewrites exactly those three srcs to same-origin absolute paths under /sea-speed/ (the pattern /sea-speed/overlay-canvas.js already uses since #631), preserving tag order and every other byte. The pinned hls.js CDN artifact (issue #575) keeps its Subresource Integrity attribute. No new files ship: deploy/vps/deploy.sh already copies index.html, so the deploy allowlist is untouched.

## User scenarios
- An authenticated viewer opens https://mostdef.ru/sea-speed/water/ and the water operator page boots fully: crossing-line editor, HLS stream wiring, live overlay sync and session watchdog all load, because every local script resolves by its absolute /sea-speed/ path regardless of the page URL.
- The page at its canonical /sea-speed/ URL behaves exactly as before — same scripts, same execution order, no extra requests.

## Requirements
1. frontend/sea-speed/index.html references its three local scripts by the exact absolute paths /sea-speed/crossing-line.js, /sea-speed/main.js, /sea-speed/live-sync.js; tag order and every other byte of the file are unchanged.
2. The pinned hls.js CDN tag (https://cdn.jsdelivr.net/npm/hls.js@1.5.7/dist/hls.min.js with integrity + crossorigin) and the already-absolute /sea-speed/overlay-canvas.js tag stay untouched.
3. tests/support/frontend_html.py treats same-origin absolute /sea-speed/... srcs as local files resolved to frontend/sea-speed/<name>.js, additively: the relative ./x.js resolution path (source-dir-first, tmp-copy mutation sensitivity for the wave demos) is preserved exactly, true external/CDN sources stay skipped, and the stubbed overlay module (/sea-speed/overlay-canvas.js) stays excluded from the executed set so the recorded-evidence contract (overlayInits/workerActive stub records) is unchanged.
4. tests/test_live_overlay_sync.py pins the water page's live-sync include by its new absolute path; the road page's pin (already absolute) is unchanged; each assertion keeps its intent (the module is included by that page).
5. No deploy-script changes: no new files are shipped, so the deploy.sh allowlist is untouched; deployment contour is VPS only (release tree), Ubuntu worker not required.

## Acceptance criteria
- AC-001: The raw-text scan (tests/test_665_water_page_assets.py, 4 tests) proves no `<script src>` is relative, the three local scripts carry their exact absolute paths, and the full ordered src list is [crossing-line.js, CDN hls.js, overlay-canvas.js, main.js, live-sync.js].
- AC-002: The executed harness twins stay green — tests.test_live_overlay_sync, tests.test_398_wave4_demo (the mutated temporary main.js written next to the tmp HTML copy is still the file executed: mutation sensitivity survives), tests.test_626_csp_no_inline_scripts, tests.test_water_live_sync_guard.
- AC-003: tests.test_frontend_contract (the largest harness consumer) stays green — the water page's executed script set and recorded evidence are unchanged from base.
- AC-004: The full unittest battery is green (run by the delivery orchestrator before merge).

## Runtime feedback
- Issue #665: served at the nested /sea-speed/water/ URL, the page requested /sea-speed/water/main.js (and siblings) and got 404s — the operator page rendered without its wiring.
- The absolute pattern is already production-proven on this page: /sea-speed/overlay-canvas.js (issue #631) resolves identically at both URLs.

## NFR assessment
- NFR-001 | Area: Security | Target: CSP contract intact — no inline scripts, no new endpoints, the CDN hls.js artifact unchanged with SRI | Validation: tests.test_626_csp_no_inline_scripts + tests.test_frontend_contract HlsScriptPinTests | Evidence: both green after the rewrite; only src attribute values changed | Status: PASS
- NFR-002 | Area: Reliability | Target: The water page boots fully at both /sea-speed/ and /sea-speed/water/ | Validation: executed harness twins (test_frontend_contract water scenarios) | Evidence: executed script set unchanged (crossing-line, main, live-sync in the same order); absolute srcs are page-URL-independent | Status: PASS
- NFR-003 | Area: Performance | Target: No runtime change — same files, same execution order, no extra requests | Validation: tests.test_665_water_page_assets order pin + executed twins | Evidence: EXPECTED_SCRIPT_ORDER unchanged; the same three local files execute | Status: PASS
- NFR-004 | Area: Compatibility | Target: Deploy allowlist untouched, no new files, road/objects/cameras pages untouched | Validation: git diff --stat + tests.test_626_csp_no_inline_scripts deploy pin | Evidence: diff limited to index.html, two test files and this trio; deploy.sh already copies index.html | Status: PASS
- NFR-005 | Area: Maintainability | Target: Harness exclusion rationale documented; stale pin updated with intent preserved | Validation: tests.test_live_overlay_sync | Evidence: frontend_html.py documents the stubbed-module exclusion; the include pin still asserts each page includes the module | Status: PASS
