# Spec: #616 — optional_int must reject non-finite floats (1e999 → OverflowError 500 on crossing ingestion)

- Issue: #616
- Specification: specs/616-optional-int-overflow/spec.md
- Authorization: commit approved (wave-2 admission, 2026-11-08); base
  fa8148f9, head 5b53c44 (branch fix/616-optional-int-overflow).

## Product outcome

The #577 fix hardened scalar numeric inputs (distance_m guard,
optional_float/optional_int), but optional_int kept a residual non-finite
path: it caught only (TypeError, ValueError), so a JSON number like 1e999
parses to float inf and int(inf) raises OverflowError — unhandled, an HTTP
500 on the crossing ingestion path (post_analytics_crossing track_id,
parsed at api/app/analytics.py:454; the route POST /api/cam1/crossings
wraps the handler in no try/except, and unlike the passage/event metadata
paths it has no #587 non-finite boundary scan). After the fix: optional_int
drops non-finite floats exactly like non-numeric input (None, mirroring the
#577-hardened optional_float), exact integers never round-trip through
float() so large values (e.g. 10**30) keep full precision, and
OverflowError joins the except tuple as a belt for non-float overflowers
(e.g. Decimal('Infinity')); the crossing ingestion path ingests a
non-finite track_id with track_id None — the same treatment an absent or
non-numeric track_id already gets — instead of surfacing an unhandled 500.

## User scenarios

- SC-1: an authorized actor POSTs a crossing whose track_id is a non-finite
  number (1e999 / -1e999 JSON literals, ±Infinity, NaN) — the crossing is
  ingested normally with track_id None at both sinks (registry mirror and
  crossing record), exactly the treatment an absent or non-numeric track_id
  already gets, instead of an unhandled OverflowError 500.
- SC-2: an actor POSTs a crossing with an exact large integer track_id
  (e.g. 10**30) — full precision preserved end-to-end (no float()
  round-trip anywhere in the path).
- SC-3: legitimate payloads behave exactly as before — finite floats
  truncate (3.0 → 3), ints and numeric strings pass, bools map to 1/0,
  None/""/non-numeric strings → None, the string "1e999" still returns None
  via the existing ValueError path, and an absent track_id still ingests
  with None.

## Requirements

- R-1: api/app/objects_registry.py optional_int drops non-finite floats
  exactly like non-numeric input: an isinstance(value, float)
  chained-comparison finiteness guard (not (float("-inf") < value <
  float("inf"))) placed before int() returns None for non-finite floats,
  with a comment referencing #616; no float() round-trip is introduced
  (exact ints keep full precision).
- R-2: OverflowError joins the optional_int except tuple
  (TypeError, ValueError, OverflowError) → None — a belt for non-float
  overflowers (e.g. Decimal('Infinity')) that the isinstance-float guard
  cannot see.
- R-3: optional_float is untouched; finite/normal inputs keep their exact
  existing behavior; the crossing ingestion handler
  post_analytics_crossing needs no change — it inherits the hardened
  optional_int.
- R-4: the optional_int body stays module-import-free — the chained
  comparison is math.isfinite(value) without the import; the AST/exec test
  harnesses exec this function verbatim against stub namespaces.
- R-5: tests/test_616_optional_int_overflow.py (8 tests: 5 exec-harness
  unit pins + 3 real-handler ingestion pins with only the sinks stubbed) is
  the acceptance oracle, byte-unchanged through the fix, RED on base
  fa8148f9 (FAILED, errors=6, OverflowError) and GREEN with the fix; no
  TestClient/third-party import is introduced, so the import-hygiene
  registry in tests/test_run_tests_script.py needs no change.

## Acceptance criteria

- AC-001: optional_int returns None for non-finite floats (inf, -inf, nan, including the 1e999 / -1e999 JSON overflow literals) — dropped exactly like non-numeric input; on base fa8148f9 int(inf)/int(-inf) raised OverflowError — RED differential verified.
- AC-002: exact large integers keep full precision — optional_int(10**30) returns 10**30 unchanged and still an int (the fix does not round-trip integers through float()).
- AC-003: finite/normal inputs behave identically to base — finite float 3.0 → 3, ints and numeric strings pass, True → 1, 0 → 0, None/""/"abc" → None, and the string "1e999" still returns None via the existing ValueError path.
- AC-004: OverflowError is caught by the optional_int except tuple — non-float overflowers (e.g. Decimal('Infinity')) return None instead of raising (belt behind the isinstance-float finiteness guard).
- AC-005: the crossing ingestion path (real post_analytics_crossing, only the sinks stubbed) ingests a non-finite track_id without OverflowError — the crossing record reaches both sinks with track_id None; valid, exact-large (10**30) and absent track_id ingestion contracts are unchanged.
- AC-006: the optional_int body remains module-import-free — the exec-harness stub namespace (only typing.Any/Optional) pins that any module-level reference would raise NameError.
- AC-007: full battery green with the fix (1406 tests, skipped=2; baseline at fa8148f9 without the new file 1398 — delta +8), ruff clean, and the new test file is RED on base fa8148f9 (FAILED, errors=6) / GREEN with the fix, byte-unchanged.

## Runtime feedback

- RF-001: Operator actions expected: 0 — api/** rides the normal VPS release
  contour. Runtime acceptance = exact-head CI green on the merge PR, then
  the lane-A deploy probe: external read-only probes confirm GET /,
  /sea-speed/ and /sea-speed/api/health signatures, and an unauthenticated
  1e999 crossing POST is intercepted by the auth boundary (wave-1 #587
  precedent, issuecomment-6724516508).
- RF-002: behavior-tightening change — the previously-500 crossing ingestion
  path now degrades a non-finite track_id to None (strictly fewer server
  errors); no schema change, no stored-data migration; existing
  finite-input behavior unchanged.

## NFR assessment

- NFR-001 | Area: input validation / API robustness | Target: no non-finite float (NaN/±Infinity incl. 1e999 literals) reaches int() conversion in optional_int — such inputs return None exactly like non-numeric input, so no OverflowError 500 can occur on the crossing ingestion path | Validation: tests/test_616_optional_int_overflow.py (8 tests: 5 exec-harness unit pins + 3 real-handler ingestion pins; RED on base fa8148f9 errors=6, GREEN 8/8 with fix) | Evidence: focused run + base differential recorded in plan.md | Status: PASS
- NFR-002 | Area: compatibility / precision | Target: zero change for finite inputs; exact integers never round-trip through float() (10**30 keeps full precision); optional_float untouched; AST/exec harness namespaces (test_numeric_input_validation.py idiom) unbroken | Validation: full battery 1406 OK (skipped=2) incl. test_numeric_input_validation.py; ruff clean | Evidence: observed runs recorded in plan.md and tasks.md | Status: PASS
- NFR-003 | Area: performance | Target: negligible — one isinstance check plus chained comparison per optional_int call, O(1), before int() | Validation: code review; no hot-loop additions | Evidence: diff inspection (+11/-1 lines in api/app/objects_registry.py) | Status: PASS
