# Tasks: Unify Water/Road live-overlay contour rendering (#375)

- Specification: specs/375-water-road-overlay-unify/spec.md
- Issue: #375

## Delivery tasks

- T1: Create shared `frontend/sea-speed/overlay-canvas.js` module (R1, R2, R3)
- T2: Refactor Water `index.html` to use shared module (R1, R4)
- T3: Refactor Road `road/index.html` to use shared module (R1, R4, R5)
- T4: Extend `tests/test_frontend_contract.py` and live-overlay sync tests (AC-002, AC-004)
- T5: Run `scripts/ci/*`, `scripts/quality/*`, `python3 -m unittest discover -s tests` (all)
- T6: Open PR with Change Contract (VPS REQUIRED / Ubuntu NOT) (EVIDENCE)

## Requirements traceability

- AC-001 | Task: T2, T3 | Evidence: overlay-canvas.js drawLive + both pages init | Coverage: COVERED
- AC-002 | Task: T1, T4 | Evidence: test_live_overlay_unified_module asserts (r.height-ch)/2 and no /h | Coverage: COVERED
- AC-003 | Task: T1, T4 | Evidence: test_live_overlay_unified_module asserts raw == null fallback draws latest | Coverage: COVERED
- AC-004 | Task: T2, T3, T4 | Evidence: test_live_overlay_sync asserts no duplicate inline sync math; road unchanged | Coverage: COVERED

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

## Completion gate

- [ ] `overlay-canvas.js` exists, exports `SeaSpeedOverlayCanvas.init`, centers vertically with `/2`, draws latest envelope when no HLS wall-clock.
- [ ] Water + Road pages call `init` and wire `setWorkerActive`; inline IIFEs removed.
- [ ] Contract + sync tests assert centering fix, module load, no duplicate globals; full suite green.
- [ ] PR green; exact-green-head merge; #375 closed; #373 noted as predecessor.
- [ ] Operator confirms Water + Road contours visible with labels (RUNTIME-MANUAL).
