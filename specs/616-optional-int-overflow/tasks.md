# Tasks — Issue #616 optional_int non-finite guard

- Issue: #616
- Specification: specs/616-optional-int-overflow/spec.md

## Delivery tasks

- T-1: api/app/objects_registry.py — optional_int finiteness guard
  (isinstance-float chained comparison → None before int(), comment
  referencing #616, module-import-free body) + OverflowError added to the
  except tuple; optional_float untouched. DONE.
- T-2: tests/test_616_optional_int_overflow.py — 8 tests / 2 classes (5
  exec-harness unit pins for optional_int + 3 real-handler ingestion pins
  for post_analytics_crossing with only the sinks stubbed), RED on base
  fa8148f9 verified (byte-identical test file on base api/ → FAILED
  errors=6 OverflowError), byte-unchanged through the fix. DONE.
- T-3: specs/616-optional-int-overflow/ trio (this spec/plan/tasks).
  DONE.

## Battery identity

Baseline at base fa8148f9 without the new file: 1398 passed / 2 skipped.
Delta: +8 tests in tests/test_616_optional_int_overflow.py — expected 1406
passed / 2 skipped. Observed: recorded in the completion gate below.

## Completion gate

- Focused `python3 -W error::ResourceWarning -m unittest tests.test_616_optional_int_overflow`: OBSERVED 8/8 tests OK with the fix.
- RED differential (byte-identical test file on base fa8148f9, api/ at base state): OBSERVED FAILED (errors=6) OverflowError — RED authenticity; fix restored byte-identical afterwards.
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`: OBSERVED 1406 tests OK (skipped=2).
- ruff `ruff check --config scripts/quality/ruff.toml api/app/objects_registry.py tests/test_616_optional_int_overflow.py`: OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py`: OBSERVED pass (EXIT=0) with this trio.

## Requirements traceability

- AC-001 | Task: T-1+T-2 | Evidence: exec-harness unit pin (inf/-inf/nan → None) + RED differential (FAILED errors=6 OverflowError on base fa8148f9) | Coverage: COVERED
- AC-002 | Task: T-1+T-2 | Evidence: 10**30 exact-precision pin at unit level and end-to-end through the ingestion harness (result exact, isinstance int) | Coverage: COVERED
- AC-003 | Task: T-1+T-2 | Evidence: finite/normal behavior pins (3.0→3, 12, "42", True→1, 0; "1e999" string → None via ValueError path; None/""/"abc" → None) | Coverage: COVERED
- AC-004 | Task: T-1 | Evidence: OverflowError in the optional_int except tuple — belt for non-float overflowers (e.g. Decimal('Infinity')), verified by code reading; float overflow cases pinned by the finiteness-guard tests | Coverage: COVERED
- AC-005 | Task: T-1+T-2 | Evidence: real post_analytics_crossing ingestion harness (only sinks stubbed) — non-finite track_id ingests ok with track_id None at both sinks (RED on base: OverflowError); valid/large/absent track_id contracts unchanged | Coverage: COVERED
- AC-006 | Task: T-1+T-2 | Evidence: exec-harness stub namespace (only typing.Any/Optional) pins the module-import-free body — any module-level reference raises NameError | Coverage: COVERED
- AC-007 | Task: T-1+T-2+T-3 | Evidence: full battery 1406 OK (skipped=2), ruff clean, validate_sdd green, RED differential errors=6 on base fa8148f9 (observed outputs in the completion gate) | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (api/app/objects_registry.py + tests/test_616_optional_int_overflow.py + this trio)
- [x] Required tests and evidence complete
- [ ] Required CI green — pending exact-head CI on the merge PR
- [ ] Exact-green-head merge complete — pending squash merge to main
- [ ] Deployment state resolved (lane-A VPS API contour)
- [ ] Runtime acceptance resolved (health/signature probes + unauthenticated 1e999 POST intercepted by auth boundary, post-deploy)
- [x] Deferred work recorded (none — no deferred work)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
