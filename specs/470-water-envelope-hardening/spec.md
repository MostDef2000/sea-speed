# 470 — Water live envelope validator hardening

- Issue: #470

## Product outcome

Water live envelope payloads that are not JSON-serializable currently escape the
`_validate_water_live_envelope` size check as an uncaught TypeError, surfacing as HTTP 500.
Road already guards the same check and returns 400. Outcome: both live domains return a
symmetric, client-actionable 400 "invalid json" for malformed payloads; previously-valid
payloads are unaffected.

## User scenarios

- Scenario 1: a monitoring client posts a water live envelope containing a non-serializable
  value (e.g. a set) — the API responds 400 "invalid json" instead of 500, matching the road
  contract; no state mutation occurs (validation precedes deepcopy/lock/seq/append).
- Scenario 2: a client posts a valid water live envelope — behavior is unchanged.

## Requirements

- R1: `_validate_water_live_envelope` guards its json.dumps size check with try/except and
  raises HTTPException 400 "invalid json" on TypeError/ValueError — textually identical to
  the road guard block.
- R2: the 400 path performs no state mutation (no deque append, no seq increment, no lock).
- R3: previously-serializable payloads behave byte-identically to the pre-fix code.
- R4: unit tests cover both validators with a non-serializable payload (RED-first: the water
  case fails against the base, passes after the fix).

## Acceptance criteria

- AC-001: water guard block textually identical to road guard block (same exception scope,
  status 400, "invalid json" wording, ensure_ascii=False).
- AC-002: non-serializable envelope payload returns 400 "invalid json" for both validators.
- AC-003: RED-first evidence recorded — water test errors against base (TypeError → 500),
  passes after fix.
- AC-004: no state mutation on the 400 path (guard precedes deepcopy/lock/seq/append).
- AC-005: full battery green with delta exactly +2 tests (910 OK skipped=4).

## Runtime feedback

Runtime acceptance via the deploy gate: health gate + authenticated route probe after the
wave deploy; the fix is only behavior-visible for malformed payloads (500 → 400).

## NFR assessment

- NFR-001 | Area: Reliability | Target: malformed water live payloads return 400 not 500 | Validation: unit tests both validators (RED-first) | Evidence: tests/test_live_envelope_validators.py 2/2 OK | Status: PASS
- NFR-002 | Area: Compatibility | Target: zero behavior change for valid payloads | Validation: full suite battery 910 OK (skipped=4) | Evidence: battery run at commit head | Status: PASS
- NFR-003 | Area: Maintainability | Target: road/water guard blocks textually identical | Validation: code review line compare | Evidence: peer review APPROVE | Status: PASS
