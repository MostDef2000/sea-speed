# Spec: #587 — Residual non-finite input paths (NaN/±Infinity) must be rejected at the API boundary

- Issue: #587
- Specification: specs/587-nonfinite-residual-paths/spec.md
- Authorization: wave-1 task B (owner instruction 2026-11-08: continue
  execution per the last approved plan; scope A of wave 1 — #591 + #587 +
  #589 + #576 closure); base ef01fa80, head 35cabf92 (branch main).

## Product outcome

The #577 fix hardened scalar numeric inputs (distance_m guard,
optional_float/optional_int), but residual non-finite input paths survived:
json.loads accepts bare NaN/Infinity tokens, and 1e999 literals / numeric
strings parse to non-finite floats. Today three handlers crash with an
unhandled 500 on int(nan) (post_analytics_roi, post_analytics_speed_lines,
post_analytics_crossing_line reference dimensions), two free-form JSON paths
(cam1 passage measurement_meta, analytics event metadata) persist bare NaN
tokens — invalid strict JSON — into sqlite, and speed_min/speed_max query
params on the object-list endpoints silently return empty result sets (NaN
comparisons are always false). After the fix: every external non-finite
input is rejected with HTTP 400 at the boundary before any persist/mirror/
media write; the two free-form JSON payloads are scanned recursively
(including nested dicts/lists, with the offending dotted path in the error);
the reference-dimension guards fall through to existing defaults for falsy
values and keep the existing failure mode for non-floatable ones; and for
speed_min=-1e999 the status 400 is preserved while the detail message is
updated to the finite-number form (the finite guard precedes the `< 0`
guard).

## User scenarios

- SC-1: an authorized actor POSTs a cam1 passage whose measurement_meta
  contains a NaN/Infinity token anywhere (top level or nested) — the API
  responds 400 naming the offending path and nothing is persisted, mirrored,
  or written to media.
- SC-2: an authorized actor POSTs an analytics event whose metadata contains
  a non-finite value anywhere — 400, no event row, no media write.
- SC-3: an operator requests object lists with speed_min/speed_max set to a
  non-finite value (NaN, ±Infinity, 1e999, numeric strings) — 400 instead of
  a silently empty result set.
- SC-4: an actor POSTs ROI / speed-lines / crossing-line config with a
  reference dimension that is floatable-but-non-finite (e.g. "1e999",
  Infinity) — 400 before int() conversion (today: unhandled 500); a falsy
  value still falls through to the existing defaults and a non-floatable
  value keeps its existing downstream failure mode.
- SC-5: legitimate payloads (finite floats, ints, numeric strings, nulls,
  bools, nested structures) behave exactly as before — the scan passes them
  untouched.

## Requirements

- R-1: api/app/store.py provides find_nonfinite_json_value(value,
  path="metadata") -> Optional[str]: recursive scan of parsed JSON — float
  → chained-comparison finite check; dict → recurse values with dotted
  path; list → recurse with index path; ints/strings/None/bools pass —
  returning the offending path or None. store.py stays fastapi-free: the
  helper returns the path, the handler raises HTTPException(400).
- R-2: post_cam1_passage scans the parsed measurement_meta payload after
  the isinstance-dict check and BEFORE snapshot.read() and any persist/
  mirror/media write; non-finite → 400.
- R-3: post_analytics_event scans the parsed metadata payload after the
  json.loads except-block, before any normalization/media/persist write;
  non-finite → 400.
- R-4: get_cam1_objects and get_objects place inline finite guards for
  speed_min/speed_max BEFORE the existing < 0 guards (existing
  speed_min=-1e999 → 400 behavior preserved).
- R-5: post_analytics_roi, post_analytics_speed_lines and
  post_analytics_crossing_line guard the 4 reference-dimension keys
  (reference_width/referenceWidth/reference_height/referenceHeight):
  falsy → fall through to existing defaults; non-floatable → keep the
  existing downstream failure mode; floatable-but-non-finite → 400 before
  int() conversion.
- R-6: handlers AST/exec'd by fixed-stub test harnesses
  (test_numeric_input_validation.py, test_api_contract.py,
  test_sea_speed_rbac.py — the last stubs `store` with ONLY
  JSON_READ_ERRORS) use inline chained-comparison checks only (no
  `import math`, no helper calls); the store helper appears only in
  post_cam1_passage (never AST-exec'd) and post_analytics_event (harnesses
  pass the real store module).
- R-7: tests/test_587_nonfinite_residual_paths.py (8 test methods / 39 subtests: 38 RED on base + 1 stability pin)
  is the acceptance oracle, byte-unchanged through the fix, RED on base
  ef01fa80 and GREEN with the fix; the import-hygiene registration in
  tests/test_run_tests_script.py gains exactly 3 guarded-optional-import
  tuples (fastapi ×2, httpx ×1) — registration, not a weakening.

## Acceptance criteria

- AC-001: POST cam1 passage with a non-finite value anywhere in measurement_meta returns 400 (offending dotted path) and performs no snapshot read, persist, mirror or media write; on base ef01fa80 the request 500s or persists a bare NaN token — RED differential verified.
- AC-002: POST analytics event with a non-finite value anywhere in metadata returns 400 with no event persisted and no media write; RED on base verified.
- AC-003: GET cam1 objects with speed_min or speed_max non-finite (NaN, ±Infinity, 1e999, numeric strings) returns 400 instead of a silently empty result set.
- AC-004: GET objects with non-finite speed_min/speed_max returns 400 under the same guard ordering as AC-003.
- AC-005: POST analytics ROI with a floatable-but-non-finite reference dimension returns 400 before int() conversion (base: unhandled 500); falsy values fall through to existing defaults; non-floatable values keep the existing downstream failure mode.
- AC-006: POST analytics speed-lines behaves per AC-005 for all four reference-dimension keys.
- AC-007: POST analytics crossing-line behaves per AC-005 for all four reference-dimension keys.
- AC-008: no-state-change property — every 400 rejection above leaves sqlite rows, mirror state and media files byte-identical (rejection strictly precedes all writes).
- AC-009: speed_min=-1e999 stability pin — status 400 preserved on both object-list endpoints; the detail message is updated to the finite-number form (the finite guard precedes the < 0 guard).
- AC-010: full battery green with the fix (1390 tests, skipped=2), ruff clean, validate_sdd green; no committed test regressed; the new test file is byte-unchanged from its RED state.

## Runtime feedback

- RF-001: Operator actions expected: 0 — api/** rides the normal VPS release
  contour. Runtime acceptance = exact-head CI green on the merge PR, then
  the lane-A deploy probe: replay the issue's non-finite payloads against
  prod (measurement_meta NaN, speed_min=1e999, reference_width="1e999") and
  observe 400 with no row/mirror/media delta (today: 500, silent empty set,
  or NaN persisted).
- RF-002: behavior-tightening change — previously-500 paths become clean
  400s, previously-silent-empty speed filters become 400, and bare NaN
  tokens no longer reach sqlite; no schema change, no stored-data migration;
  existing finite-input behavior unchanged.

## NFR assessment

- NFR-001 | Area: input validation / API robustness | Target: no external non-finite input (NaN/±Infinity incl. 1e999 literals and numeric strings) reaches int() conversion, sqlite persistence, mirror or media writes — all such inputs are rejected 400 at the boundary | Validation: tests/test_587_nonfinite_residual_paths.py (8 test methods / 39 subtests: 38 RED on base ef01fa80 + 1 stability pin green on base; GREEN with fix; stash differential verified) | Evidence: focused run + base-stash differential recorded in plan.md | Status: PASS
- NFR-002 | Area: compatibility | Target: zero change for finite inputs; existing speed_min=-1e999 → 400 preserved; AST/exec harness namespaces (test_numeric_input_validation.py, test_api_contract.py, test_sea_speed_rbac.py) unbroken | Validation: full battery 1390 OK (skipped=2) incl. the three harness suites; ruff clean | Evidence: observed runs recorded in plan.md and tasks.md | Status: PASS
- NFR-003 | Area: performance | Target: negligible — one recursive scan over small JSON payloads at the boundary, O(payload size), before any I/O | Validation: code review; scan runs once per affected request; no hot-loop additions | Evidence: diff inspection (+98 lines across api/app/{store,main,analytics}.py) | Status: PASS
