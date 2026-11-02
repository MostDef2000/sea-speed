# Tasks — Issue #582 wave 1: real FastAPI HTTP integration tests

- Issue: #582
- Spec: specs/582-http-integration-wave1/spec.md
- Plan: specs/582-http-integration-wave1/plan.md
- Base: dc1e9f7 (branch fix/582-api-http-integration-wave1)

## Delivery tasks

- [x] T-1 RECON: config.py path derivation + env-override precedent,
      identity.py auth/role semantics, route inventory, dual-idiom imports,
      module-tail side effects, guarded-optional idiom and scan semantics
      (recorded in the session progress log; facts cited in plan.md).
- [x] T-2 `tests/test_api_http_integration.py` — 15 tests / 6 subtests over
      the real app via TestClient against a disposable temp data root
      (AC-001).
- [x] T-3 `api/app/config.py` — `SEA_SPEED_BASE_DIR` /
      `SEA_SPEED_DEPLOYED_COMMIT_FILE` env overrides, previous hardcoded
      values as defaults, +12/−2 (AC-003).
- [x] T-4 guarded-optional pin update in `tests/test_run_tests_script.py`
      (RED captured before the fix; expectation = actual scanned set)
      (AC-005).
- [x] T-5 one-process battery containment: sys.modules snapshot + eviction
      of non-preexisting fastapi names in the class cleanup; roi harness
      untouched (AC-004; CC-1).
- [x] T-6 validation runs (see Battery identity).
- [x] T-7 this SDD trio.
- [x] T-8 independent peer review of the full wave diff: verdict PASS with
      no blockers; F-1 (docstring runner-pins claim false) and F-2
      (containment boundary undocumented) fixed and re-verified; F-3
      (reviewer sandbox could not run tests) closed by orchestrator-run
      batteries (see plan.md CC-3).
- [ ] T-9 commit, PR, exact-head CI, merge per the admitted scope.

## Battery identity

- Baseline dc1e9f7 (wave admission base): 1274 passed / 2 skipped /
  357 subtests.
- Wave tree on dc1e9f7: canonical gate `python3 scripts/run_tests.py` →
  `PASS: 2/2 CI battery commands green (Python 3.14.4 cpython, deps:
  pyyaml==6.0.3)`; with fastapi present `pytest tests/ -q` →
  `1289 passed, 2 skipped, 363 subtests passed` (delta: +15 tests,
  +6 subtests — exactly the new module).
- Rebase onto main 349b39c (#590 merged, no file overlap): canonical gate
  PASS 2/2; with fastapi present `1293 passed, 2 skipped, 363 subtests`
  (1278 main baseline + exactly the new module). CI (no fastapi) expects
  1278 passed / 17 skipped / 357 subtests.
- Focused: new module 15 passed + 6 subtests with fastapi; 15 skipped
  without; `tests/test_run_tests_script.py` 27 passed + 11 subtests.

## Completion gate

- [x] AC-001 — new module green with fastapi present (focused + full
  battery evidence above).
- [x] AC-002 — canonical gate PASS 2/2 on the final tree; skip path
  observed (15 skipped without fastapi).
- [x] AC-003 — config diff is the two env overrides; canonical battery
  (env unset) green proves unset equivalence.
- [x] AC-004 — combined run and full battery with fastapi present green
  after the containment (CC-1).
- [x] AC-005 — pin matches scanner output (83/84/86 + live_envelope 61).
- [x] AC-006 — both battery modes green, observed on the final tree.
- [x] Peer review verdict recorded (T-8): PASS, no blockers, F-1/F-2 fixed.
- [ ] PR merged with exact-head green CI (T-9).

## Requirements traceability

- AC-001 | Task: T-2 | Evidence: focused run — new module 15 passed + 6 subtests with fastapi present (orchestrator-observed); full-battery delta is exactly the new module | Coverage: COVERED
- AC-002 | Task: T-2+T-4 | Evidence: canonical gate `python3 scripts/run_tests.py` PASS 2/2 without fastapi; skip path observed (15 skipped without fastapi) | Coverage: COVERED
- AC-003 | Task: T-3 | Evidence: config diff is the two env overrides; canonical battery (env unset) green on the final tree proves unset equivalence | Coverage: COVERED
- AC-004 | Task: T-5 | Evidence: combined run and full battery with fastapi present green after the containment (CC-1) | Coverage: COVERED
- AC-005 | Task: T-4 | Evidence: `tests/test_run_tests_script.py` 27 passed + 11 subtests; pin = scanner output (83/84/86 + live_envelope 61); RED captured before the fix | Coverage: COVERED
- AC-006 | Task: T-6 | Evidence: both battery modes green on the final tree — canonical PASS 2/2; fastapi present 1293 passed / 2 skipped / 363 subtests / 0 failed (see Battery identity) | Coverage: COVERED

Requirement-to-AC mapping: R-1 (config env overrides) → AC-003; R-2 (new
test module) → AC-001, AC-004; R-3 (pin update) → AC-005; R-4 (SDD trio)
→ this directory.

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (1 api/app file + 1 new test module + 1 pin file + this trio)
- [x] Required tests and evidence complete (Battery identity above)
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (rides the autonomous post-merge VPS contour; observed, not dispatched, by this wave)
- [ ] Runtime acceptance resolved (none required — no runtime contour mutated by this wave; autonomous pipeline evidence observed post-merge)
- [x] Deferred work recorded (activating the HTTP tests in CI is a later #582 wave; out of scope here)
- [x] Risks resolved or explicitly accepted (plan.md Risk profile)
- [x] Waivers resolved or current (no waivers)

Evidence notes:

- Full battery green in both modes (canonical no-fastapi gate; full pytest
  with fastapi present) with the delta accounted (+15 tests / +6 subtests).
- No assertion weakened, skipped or mocked to obtain green; the containment
  is real cleanup; the pin matches scanner output.
- No secrets, no local runtime state, no generated output committed; fixture
  constants are gitleaks-safe low-entropy values per repo precedent.
- Peer review completed and findings addressed or explicitly dispositioned
  (T-8: PASS, no blockers; F-1/F-2 fixed and re-verified, F-3 closed by
  orchestrator-run batteries).
- PR merged with exact-head required CI; issue #582 checkpoint updated with
  the wave-1 evidence cursor.
