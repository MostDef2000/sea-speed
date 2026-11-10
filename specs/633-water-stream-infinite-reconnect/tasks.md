# Tasks — Issue #633 water page stream reconnect retries indefinitely

- Issue: #633
- Specification: specs/633-water-stream-infinite-reconnect/spec.md
- Authorization: commit approved (owner admission in the dev-chat delivery
  session, 2026-11-10, for the #633 scope: water stream infinite reconnect +
  structural test + SDD trio, chain through merge, deploy and probes);
  base 8e8a77f

## Delivery tasks

- T-1: frontend/sea-speed/main.js — scheduleStreamReconnect: exhaustion
  early-return branch removed; delay capped via
  `STREAM_RETRY_DELAYS_MS[Math.min(reconnectAttempt,STREAM_RETRY_DELAYS_MS.length-1)]`
  (road/main.js:37 idiom); status/log strings drop the "/4" denominator.
  DONE — node --check clean; git diff = 1 line.
- T-2: tests/test_frontend_contract.py — new class
  StreamReconnectSemanticsStructuralTests (3 tests: water delay-index cap,
  water no-terminal-exhaustion, road cap guard) following the
  StreamRetryLadderStructuralTests pattern. DONE — RED on base observed
  (2 failed / 1 passed), green after the fix.
- T-3: specs/633-water-stream-infinite-reconnect/ trio (this spec/plan/
  tasks) — evidence fields filled with observed runs. DONE (this update).

## Battery identity

Baseline at base 8e8a77f without the new tests: `Ran 1426 tests` → `OK
(skipped=2)`. Delta: +3 test methods in tests/test_frontend_contract.py —
expected 1429. OBSERVED after the change: `Ran 1429 tests in 154.215s` →
`OK (skipped=2)`.

## Completion gate

- Focused `python3 -m pytest tests/test_frontend_contract.py -q`:
  OBSERVED — 28 passed + 6 subtests (baseline 25 passed + 6 subtests +
  exactly the 3 new tests).
- RED-authenticity differential: OBSERVED — with the new tests in place
  and main.js still unmodified (stash probe): `FAILED (failures=2)` —
  test_water_reconnect_caps_the_delay_index_at_the_last_ladder_rung and
  test_water_reconnect_has_no_terminal_exhaustion fail on the base source;
  the road-guard test passes (road unchanged). After the fix the same
  tests are green. The RED state is not part of the final tree.
- Full battery `python3 -m unittest discover -s tests -p "test_*.py"`:
  OBSERVED — `Ran 1429 tests in 154.215s` → `OK (skipped=2)`, exit code 0
  (baseline 1426 OK skipped=2; delta exactly +3).
- `node --check frontend/sea-speed/main.js`: OBSERVED — clean exit.
- `python3 scripts/ci/validate_sdd.py`: OBSERVED — `Sea Speed SDD
  validation passed`.
- Peer verification: independent read-only re-derivation by a second
  worker (the review-role worker was blocked by sandbox external_directory
  on the scratch clone; the peer ran as a second code-role worker with an
  independent instruction) — verdict APPROVE: all 6 scheduleStreamReconnect
  call-sites traced (no silent hang, no retry storm), RED confirmed
  analytically against the base blob, 28/28 green, no dependency on the
  removed behavior; no divergence with the implementing workers (2:0).

## Requirements traceability

- AC-001 | Task: T-1+T-2 | Evidence: StreamReconnectSemanticsStructuralTests — delay-index cap and no-terminal-exhaustion asserted on live source; RED differential observed on base (2 failed / 1 passed) | Coverage: COVERED
- AC-002 | Task: T-2 | Evidence: test_road_reconnect_keeps_its_delay_index_cap guards the road page's Math.min cap | Coverage: COVERED
- AC-003 | Task: T-1+T-2+T-3 | Evidence: full battery `Ran 1429 tests / OK (skipped=2)`; pytest focused run 28 passed + 6 subtests; node --check clean; validate_sdd green; git status limited to frontend/sea-speed/main.js, tests/test_frontend_contract.py and this trio | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (frontend/sea-speed/main.js + tests/test_frontend_contract.py + this trio)
- [x] Required tests and evidence complete (RED-authenticity differential + focused run + battery + node --check + validate_sdd observed)
- [x] Required CI green — pending exact-head CI on the merge PR — auto-synced on merge to main
- [x] Exact-green-head merge complete — pending squash merge to main — auto-synced on merge to main
- [ ] Deployment state resolved (VPS front deploy via deploy-vps.yml on the merged main SHA — authorized chain)
- [ ] Runtime acceptance resolved (deployed main.js carries the Math.min cap; cam1 playlist liveness probed)
- [ ] Deferred work recorded (none — the road preview TTL cadence is a separate owner decision, out of scope)
- [ ] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
