# Tasks — Issue #587 residual non-finite input paths

- Issue: #587
- Specification: specs/587-nonfinite-residual-paths/spec.md

## Delivery tasks

- T-1: api/app/store.py — find_nonfinite_json_value recursive scanner
  (fastapi-free, returns the offending dotted path; handler raises 400).
  DONE.
- T-2: api/app/main.py — post_cam1_passage + post_analytics_event payload
  scans (400 before any read/normalization/persist/mirror/media write);
  get_cam1_objects + get_objects speed_min/speed_max finite guards before
  the < 0 guards; post_analytics_roi + post_analytics_speed_lines
  reference-dimension guards. DONE.
- T-3: api/app/analytics.py — post_analytics_crossing_line
  reference-dimension guard. DONE.
- T-4: tests/test_587_nonfinite_residual_paths.py — 8 test methods / 39
  subtests (38 RED on base + 1 stability pin), RED on base ef01fa80 verified
  (stash differential), byte-unchanged through the fix;
  tests/test_run_tests_script.py hygiene registration +3 tuples.
  DONE.
- T-5: specs/587-nonfinite-residual-paths/ trio (this spec/plan/tasks).
  DONE.

## Battery identity

Baseline at base ef01fa80 without the new file: 1382 passed / 2 skipped.
Delta: +8 test methods in tests/test_587_nonfinite_residual_paths.py —
expected 1390 passed / 2 skipped. Observed: recorded in the completion gate
below.

## Completion gate

- Focused `python3 -W error::ResourceWarning -m unittest tests.test_587_nonfinite_residual_paths`: OBSERVED 8/8 methods OK (39 subtests) with the fix.
- RED differential (api/ stashed on base ef01fa80): OBSERVED 38 subtest failures — RED authenticity; fix restored byte-identical afterwards.
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`: OBSERVED 1390 tests OK (skipped=2).
- ruff `ruff check --config scripts/quality/ruff.toml api/`: OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py --event /tmp/opencode/zerotouch-gate/cleanup/event-587.json`: OBSERVED pass with this trio (final green run recorded in the delivery report).

## Requirements traceability

- AC-001 | Task: T-1+T-2+T-4 | Evidence: cam1 passage measurement_meta scan test + RED differential (38 subtest failures on base ef01fa80) | Coverage: COVERED
- AC-002 | Task: T-1+T-2+T-4 | Evidence: analytics event metadata scan test + RED differential | Coverage: COVERED
- AC-003 | Task: T-2+T-4 | Evidence: get_cam1_objects speed-filter guard test (400 instead of silently empty set) | Coverage: COVERED
- AC-004 | Task: T-2+T-4 | Evidence: query-param guard test on /api/cam1/objects; get_objects coverage verified by code reading (delegation) | Coverage: COVERED
- AC-005 | Task: T-2+T-4 | Evidence: roi reference-dimension guard test (400 / defaults / existing failure mode) | Coverage: COVERED
- AC-006 | Task: T-2+T-4 | Evidence: speed-lines reference-dimension guard test | Coverage: COVERED
- AC-007 | Task: T-3+T-4 | Evidence: crossing-line reference-dimension guard test | Coverage: COVERED
- AC-008 | Task: T-2+T-3+T-4 | Evidence: no-state-change assertions on every rejected request (sqlite/mirror/media untouched) | Coverage: COVERED
- AC-009 | Task: T-2+T-4 | Evidence: speed_min=-1e999 → 400 stability pin on both object-list endpoints | Coverage: COVERED
- AC-010 | Task: T-1+T-2+T-3+T-4+T-5 | Evidence: full battery 1390 OK (skipped=2), ruff clean, validate_sdd green, RED differential (observed outputs in the completion gate) | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (api/app/{store,main,analytics}.py + tests/test_587_nonfinite_residual_paths.py + tests/test_run_tests_script.py + this trio)
- [x] Required tests and evidence complete
- [x] Required CI green — pending exact-head CI on the merge PR — auto-synced on merge to main (f7bba87c)
- [x] Exact-green-head merge complete — pending squash merge to main — auto-synced on merge to main (f7bba87c)
- [ ] Deployment state resolved (lane-A VPS API contour)
- [ ] Runtime acceptance resolved (non-finite replay probe post-deploy)
- [x] Deferred work recorded (none — no deferred work)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
