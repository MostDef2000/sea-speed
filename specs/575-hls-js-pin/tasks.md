# Tasks — Issue #575 hls.js production pin with SRI

- Issue: #575
- Specification: specs/575-hls-js-pin/spec.md

## Delivery tasks

- T-1: frontend/sea-speed/index.html — replace the `hls.js@latest` script tag
  with the pinned `https://cdn.jsdelivr.net/npm/hls.js@1.5.7/dist/hls.min.js`
  plus `integrity="sha384-1B+J55elPxu+trIhW7QThjZg3evX8C5P6zjB82Xnn46RKPAXpL+vkanRSjCidsJv"`
  and `crossorigin="anonymous"`. DONE (focused green).
- T-2: frontend/sea-speed/cameras/index.html — same replacement as T-1.
  DONE (focused green).
- T-3: frontend/sea-speed/road/index.html — keep the pinned URL, add the same
  `integrity` and `crossorigin` attributes. DONE (focused green).
- T-4: tests/test_frontend_contract.py — `script_tags()` structured extraction
  helper + `HlsScriptPinTests` (2 methods, 3 subtests each): per page the
  single hls.js tag's src/integrity/crossorigin equal the pinned values
  exactly; plus the no-`@latest` guard across all three pages. Style matches
  the file's SS extraction twins (regex attribute maps over comment-stripped
  source). DONE (focused green: 25 passed + 6 subtests).
- T-5: specs/575-hls-js-pin/ trio (this spec/plan/tasks). DONE.

## Battery identity

Baseline on base 871cc50: 1232 passed / 2 skipped / 306 subtests
(orchestrator-provided). Delta: +2 test methods (3 subtests each) in
tests/test_frontend_contract.py — expected 1234 passed / 2 skipped /
312 subtests. Observed: recorded in the completion gate below.

## Completion gate

- Focused `python3 -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/534/pytest-tmp tests/test_frontend_contract.py -q`: OBSERVED 25 passed, 6 subtests passed (base 23 passed / 0 subtests).
- Full battery `python3 -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/534/pytest-tmp tests/ -q`: OBSERVED 1234 passed / 2 skipped / 312 subtests — identity 1232 + 2 methods, 306 + 6 subtests, as accounted above.
- ruff `ruff check --config scripts/quality/ruff.toml .`: OBSERVED clean (All checks passed).
- `python3 scripts/ci/validate_sdd.py`: OBSERVED "Sea Speed SDD validation passed".

## Requirements traceability

- AC-001 | Task: T-1+T-2+T-3 | Evidence: focused pytest run 25 passed + 6 subtests (per-page src/integrity/crossorigin pins) | Coverage: COVERED
- AC-002 | Task: T-4 | Evidence: focused pytest run — no-@latest guard over water/cameras/road | Coverage: COVERED
- AC-003 | Task: T-4+T-5 | Evidence: full battery 1234/2/312, ruff clean, validate_sdd passed (observed outputs in the completion gate) | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (3 frontend pages + 1 test file + this trio)
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (rides the normal VPS release contour)
- [ ] Runtime acceptance resolved (post-deploy probe: three pages load, HLS playback starts)
- [x] Deferred work recorded (none — no deferred work)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
