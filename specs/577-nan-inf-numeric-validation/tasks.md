# Tasks — Issue #577 NaN/Infinity numeric input validation

- Issue: #577
- Specification: specs/577-nan-inf-numeric-validation/spec.md

## Delivery tasks

- T-1: api/app/objects_registry.py — `optional_float` returns `None` when the
  converted result is non-finite (dependency-free chained comparison with
  `math.isfinite` semantics), so event ingest everywhere inherits the guard
  through its callers. DONE (focused green).
- T-2: api/app/analytics.py — `_clean_norm_points` drops any point with a
  non-finite x_norm/y_norm via the same `continue` the malformed-conversion
  path uses, instead of the corrupting max/min clamp. DONE (focused green).
- T-3: api/app/main.py — `post_analytics_speed_config` raises 400
  `kmh_per_px_s must be a finite number` between the existing conversion and
  `< 0` checks. DONE (focused green).
- T-4: api/app/main.py — `post_analytics_speed_lines` raises 400
  `distance_m must be a finite number` between the existing conversion and
  `<= 0` checks. DONE (focused green).
- T-5: api/app/objects_registry.py — `patch_object_record` raises 400
  `speed_kmh must be a finite number` between the existing conversion and
  `< 0` checks. DONE (focused green).
- T-6: tests/test_numeric_input_validation.py — new file, 13 methods /
  34 subtests in the suite's AST-extract/exec harness idiom (no TestClient —
  issue #582): non-finite rejection at all five sites (float and numeric-string
  forms) plus unchanged-behavior pins (finite values including negative finite
  at ingest, null, empty, malformed strings, ROI clamping, existing 400
  details). DONE (focused green: 13 passed / 34 subtests).
- T-7: specs/577-nan-inf-numeric-validation/ trio (this spec/plan/tasks).
  DONE.

## Battery identity

Baseline on base 79ffab2: 1234 passed / 2 skipped / 312 subtests
(orchestrator-provided). Delta: +13 test methods / +34 subtests in
tests/test_numeric_input_validation.py — expected 1247 passed / 2 skipped /
346 subtests. Observed: recorded in the completion gate below.

## Completion gate

- Focused `python3 -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/577/pytest-tmp tests/test_numeric_input_validation.py -q`: OBSERVED 13 passed / 34 subtests passed.
- Full battery `python3 -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/577/pytest-tmp tests/ -q`: OBSERVED 1247 passed / 2 skipped / 346 subtests — identity 1234 + 13 methods, 312 + 34 subtests, as accounted above.
- ruff `ruff check --config scripts/quality/ruff.toml .`: OBSERVED clean (All checks passed!).
- `python3 scripts/ci/validate_sdd.py`: OBSERVED "Sea Speed SDD validation passed".
- `python3 scripts/quality/validate_workflow_policy.py`: OBSERVED "Workflow policy valid: protected public main -> exact quality -> standing policy -> restricted VPS/Ubuntu zero-touch execution".

## Requirements traceability

- AC-001 | Task: T-1+T-6 | Evidence: focused pytest run — OptionalFloatFiniteTests (NaN/+inf/-inf in float and string forms → None; finite/null/empty/malformed pins unchanged) | Coverage: COVERED
- AC-002 | Task: T-2+T-6 | Evidence: focused pytest run — CleanNormPointsFiniteTests (non-finite points dropped; valid clamping and malformed-drop pins unchanged; mixed-input survival) | Coverage: COVERED
- AC-003 | Task: T-3+T-6 | Evidence: focused pytest run — SpeedConfigEndpointFiniteTests (handler-level 400 on NaN/±inf kmh_per_px_s with no write; finite/range pins unchanged) | Coverage: COVERED
- AC-004 | Task: T-4+T-6 | Evidence: focused pytest run — SpeedLinesEndpointFiniteTests (handler-level 400 on NaN/±inf distance_m; valid enabled config still writes; NaN line point cannot complete an enabled config) | Coverage: COVERED
- AC-005 | Task: T-5+T-6 | Evidence: focused pytest run — PatchObjectSpeedFiniteTests (real sqlite registry in a temp dir; NaN/±inf → 400; finite/null/`>= 0`/malformed pins unchanged) | Coverage: COVERED
- AC-006 | Task: T-6+T-7 | Evidence: base-stash differential run (28 failures/subfailures on base 79ffab2, recorded in plan.md) + full battery 1247/2/346, ruff clean, validate_sdd passed (observed outputs in the completion gate) | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (3 api/app files + 1 test file + this trio)
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (rides the normal VPS release contour)
- [ ] Runtime acceptance resolved (post-deploy probe: valid ingest/calibration/object edits unchanged; NaN/Infinity payloads 400)
- [x] Deferred work recorded (none — no deferred work)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
