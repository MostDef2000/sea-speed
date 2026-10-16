# Tasks: #398 wave 1 — overlay/live text-pin conversion

- Issue: #398
- Specification: specs/398-wave1/spec.md

## Delivery tasks

- T-001: Node-exec harness — tests/support/frontend_node.py: run_node (window shim, stubbed setInterval, embedded stderr), DOM stub with recording 2d-context + stub video, envelope builders with per-page defaults (water cam1/sea, road road1/road), render-call extraction; smoke-verify real JS bytes for all key scenarios (water interp/fallback/clears, road interp/fallback, DPR letterboxing)
- T-002: tests/test_water_overlay_sync.py — retire Python mirrors (L13–69) → 6 exec twins; keep marker pins + anti-form assertNotIns verbatim; document the retired mirror's conflation bug (near-fallback anchored on mediaMs vs real maxCapture − latencyMs)
- T-003: tests/test_water_live_sync_guard.py — 7 behavior text-pins → exec twins (probe sentinel ×3, resolvedTargetMs branches, water-only mapping, bounded near draw/clear, no-latest-draw, age-agnostic bracket, interp); forbidden regression forms + Hls/attachMedia pins verbatim
- T-004: tests/test_live_overlay_sync.py — export-presence exec-based; delegation spy-exec fixed (DOM stub before init; 25-render lag loop); include tags + anti-dup markers verbatim
- T-005: tests/test_road_overlay_sync.py — mirror retired → real road JS (4 structural + 4 exec twins; p95 stays); unreachable mixed-generation mirror case replaced by generation-bump-reset assertion
- T-006: tests/test_398_wave1_demo.py — two-direction regression demo (refactor tolerance, dead-marker intolerance) on tmp mutations of live-sync.js
- T-007: SDD trio (this set) + final evidence: full battery (baseline 1035 passed / 4 skipped on both 0b1c0b3 and 397ed06), focused runs, validate_sdd, validate_repo, allowed-paths check; single orchestrator-owned commit/push/PR/CI/merge

## Completion gate

- [x] T-001
- [x] T-002
- [x] T-003
- [x] T-004
- [x] T-005
- [x] T-006
- [x] T-007
- [ ] Exact changed-file scope verified (orchestrator acceptance)
- [ ] Required tests and evidence complete — full battery + validators on the final tree (orchestrator)

## Requirements traceability

- AC-001 | Task: T-001, T-002, T-003, T-004, T-005 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T-002, T-003, T-004, T-005 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-006 | Evidence: TEST-003 | Coverage: COVERED
- AC-004 | Task: T-001–T-006 | Evidence: TEST-004 | Coverage: COVERED
- AC-005 | Task: T-007 | Evidence: TEST-005 | Coverage: COVERED
- AC-006 | Task: T-001–T-007 | Evidence: TEST-004, TEST-005 | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified — orchestrator acceptance
- [ ] Required tests and evidence complete — orchestrator acceptance (battery/validators on final tree)
- [x] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main (567a885c)
- [x] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] No deploy required (tests-only; no production artifact change) — recorded
- [ ] Runtime acceptance = exact-head CI green (RF-001) — orchestrator-owned
- [ ] Independent peer review APPROVE — orchestrator-owned
- [ ] Site-mapping table verified against the actual diff — reviewer
- [ ] Two drift-invisibility instances documented (water conflation, road unreachable state) — recorded in plan.md Decisions
