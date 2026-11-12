# Tasks: road/water/cameras hls.js first + worker off

- Spec: specs/656-road-hls-chrome-worker-off/spec.md

## Delivery tasks
- [x] Swap attachHls branch order in road/main.js (hls.js first, native as no-MSE fallback)
- [x] Add enableWorker:false to road/main.js, main.js and cameras/cameras.js Hls configs
- [x] Add executed twins: Chrome-lie reconnect, no-MSE fallback, water worker-off, source scan
- [x] Prove the new twins RED on the base JS (fail without the fix)
- [ ] CI green on PR #657
- [ ] Merge PR to main
- [ ] Lane-A deploy on merged main SHA
- [ ] Post-deploy Playwright acceptance on prod (readyState 4, segments 200, zero 404, console clean)

## Completion gate
- CI green on PR #657
- PR merged to main
- Lane-A deploy successful on merged main SHA
- Post-deploy Playwright acceptance passes on production

## Requirements traceability
- AC-001 | Task: Chrome-lie reconnect twin | Evidence: ROAD_CHROME_LIE_SCENARIO in tests/test_frontend_contract.py | Coverage: COVERED
- AC-002 | Task: no-MSE fallback twin | Evidence: ROAD_NO_MSE_SCENARIO in tests/test_frontend_contract.py | Coverage: COVERED
- AC-003 | Task: source scan of all three operator configs | Evidence: test_every_operator_hls_config_disables_the_worker in tests/test_frontend_contract.py | Coverage: COVERED
- AC-004 | Task: post-deploy Playwright acceptance on prod | Evidence: acceptance screenshot plus console and network logs | Coverage: RUNTIME-MANUAL | Reason: production-only visual acceptance

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
