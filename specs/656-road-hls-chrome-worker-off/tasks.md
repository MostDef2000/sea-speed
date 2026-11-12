# Tasks: road/water/cameras hls.js first + worker off

- Spec: specs/656-road-hls-chrome-worker-off/spec.md

## Delivery tasks
- [x] Swap attachHls branch order in road/main.js (hls.js first, native as no-MSE fallback)
- [x] Add enableWorker:false to road/main.js, main.js and cameras/cameras.js Hls configs
- [x] Add executed twins: Chrome-lie reconnect, no-MSE fallback, water worker-off, source scan
- [x] Prove the new twins RED on the base JS (fail without the fix)
- [x] CI green on PR #657
- [x] Merge PR #657 to main (133a4a7)
- [x] Lane-A deploy on merged main SHA (deploy run #53)
- [x] Post-deploy Playwright acceptance on prod — cameras PASS; road/water FAIL: startup watchdog doom-loop (third blocker, issue #656 comment 6815532835)
- [x] Diagnose startup doom-loop with control-group proof (cameras plays both streams; regular HLS, ~5–8s to first frame)
- [x] Add 6 watchdog twins (ROAD/WATER_STARTUP_GRACE, _STARTUP_TIMEOUT, _POST_START_STALL) + VIRTUAL_CLOCK shim; proven RED on base 133a4a7
- [x] Implement ~15s startup grace in road/main.js and main.js; strict post-start stall detection preserved
- [ ] Peer verification of the combined diff (independent second worker)
- [ ] CI green on the watchdog PR
- [ ] Merge watchdog PR to main
- [ ] Lane-A deploy on merged main SHA
- [ ] Post-deploy Playwright re-acceptance on prod: road, water AND cameras (readyState 4, currentTime advancing, segments 200, zero 404, console clean)

## Completion gate
- Peer verification of the watchdog diff complete
- CI green on the watchdog PR
- PR merged to main
- Lane-A deploy successful on merged main SHA
- Post-deploy Playwright acceptance passes on production for all three pages

## Requirements traceability
- AC-001 | Task: Chrome-lie reconnect twin | Evidence: ROAD_CHROME_LIE_SCENARIO in tests/test_frontend_contract.py | Coverage: COVERED
- AC-002 | Task: no-MSE fallback twin | Evidence: ROAD_NO_MSE_SCENARIO in tests/test_frontend_contract.py | Coverage: COVERED
- AC-003 | Task: source scan of all three operator configs | Evidence: test_every_operator_hls_config_disables_the_worker in tests/test_frontend_contract.py | Coverage: COVERED
- AC-004 | Task: post-deploy Playwright acceptance on prod | Evidence: acceptance screenshot plus console and network logs | Coverage: RUNTIME-MANUAL | Reason: production-only visual acceptance
- AC-005 | Task: startup-grace + startup-timeout twins | Evidence: ROAD/WATER_STARTUP_GRACE_SCENARIO, ROAD/WATER_STARTUP_TIMEOUT in tests/test_frontend_contract.py | Coverage: COVERED
- AC-006 | Task: post-start strict stall regression guards | Evidence: ROAD/WATER_POST_START_STALL in tests/test_frontend_contract.py | Coverage: COVERED

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
