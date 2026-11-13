# Tasks: water page absolute local script paths (nested /sea-speed/water/ URL)

- Specification: specs/665-water-page-absolute-assets/spec.md

## Delivery tasks
- [x] Rewrite the three local script srcs in frontend/sea-speed/index.html to the absolute paths /sea-speed/crossing-line.js, /sea-speed/main.js, /sea-speed/live-sync.js, preserving tag order and every other byte (CDN hls.js and /sea-speed/overlay-canvas.js tags untouched)
- [x] Adapt tests/support/frontend_html.py external_local_scripts additively: same-origin absolute /sea-speed/... srcs resolve as local files (same-named file next to the source first, then frontend/sea-speed/<name>.js); relative ./x.js resolution, CDN skipping and the stubbed-overlay-module exclusion preserved
- [x] Update the stale water live-sync include pin in tests/test_live_overlay_sync.py to the absolute path (road pin already absolute, unchanged; assertion intent preserved)
- [x] Write the SDD trio specs/665-water-page-absolute-assets/{spec,plan,tasks}.md and pass scripts/ci/validate_sdd.py
- [ ] Peer verification of the combined diff (independent second worker)
- [ ] CI green on the #665 PR
- [ ] Merge the #665 PR to main
- [ ] Lane-A deploy on merged main SHA (VPS release tree; deploy.sh allowlist untouched — no new files shipped)
- [ ] Post-deploy acceptance: /sea-speed/water/ serves the page and every script request resolves (zero script 404s in the probe network log)

## Completion gate
- Peer verification of the #665 diff complete
- CI green on the #665 PR
- PR merged to main
- Lane-A deploy completed and post-deploy acceptance recorded

## Requirements traceability
- AC-001 | Task: index.html src rewrite | Evidence: tests/test_665_water_page_assets.py 4/4 OK (exact absolute paths, preserved order); RED on base b9168c8 observed | Coverage: COVERED
- AC-002 | Task: harness adaptation + stale pin update | Evidence: tests.test_live_overlay_sync + tests.test_398_wave4_demo + tests.test_626_csp_no_inline_scripts + tests.test_water_live_sync_guard → Ran 18 tests, OK | Coverage: COVERED
- AC-003 | Task: harness-consumer regression | Evidence: tests.test_frontend_contract → Ran 38 tests, OK | Coverage: COVERED
- AC-004 | Task: full battery | Evidence: orchestrator-run unittest discover output in the PR delivery record | Coverage: COVERED

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
