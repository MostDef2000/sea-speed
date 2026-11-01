# Tasks — Issue #590 X-Authentik-Groups pipe/comma separator fix

- Issue: #590
- Specification: specs/590-authentik-groups-pipe-separator/spec.md

## Delivery tasks

- T-1: api/app/identity.py — `resolve_role()` splits `X-Authentik-Groups` on
  both `|` and `,` (`.replace("|", ",").split(",")`), docstring and constants
  comment updated to document both separators and why. DONE (focused green).
- T-2: tests/test_sea_speed_rbac.py — 4 new cases in `ResolverSemanticsTests`
  (production pipe format → admin, highest-wins across pipe, mixed
  separators, fail-closed with unknown pipe tokens); RED observed on the
  unfixed resolver for the two pipe-only-reachable cases. DONE (focused
  green).
- T-3: specs/590-authentik-groups-pipe-separator/ trio (this spec/plan/tasks).
  DONE.

## Battery identity

Baseline on base dc1e9f7: 1274 passed / 2 skipped / 357 subtests
(orchestrator-provided). Delta: +4 test methods / +0 subtests in
tests/test_sea_speed_rbac.py — expected 1278 passed / 2 skipped / 357
subtests. Observed: recorded in the completion gate below.

## Completion gate

- Focused `PYTHONPATH=/tmp/opencode/582/pylibs:. python3 -m pytest -p
  no:cacheprovider --basetemp=/tmp/opencode/590/pytest-tmp
  tests/test_sea_speed_rbac.py tests/test_auth_session_identity.py -q`:
  OBSERVED 44 passed / 130 subtests passed.
- Full battery `PYTHONPATH=/tmp/opencode/582/pylibs:. python3 -m pytest -p
  no:cacheprovider --basetemp=/tmp/opencode/590/pytest-tmp tests/ -q`:
  OBSERVED 1278 passed / 2 skipped / 357 subtests — identity 1274 + 4
  methods, 357 + 0 subtests, as accounted above.
- Canonical runner `PYTHONPATH=/tmp/opencode/582/pylibs:. python3
  scripts/run_tests.py --skip-install`: OBSERVED PASS 2/2 CI battery commands
  green, EXIT=0.
- RED differential: the two pipe-only-reachable tests observed failing on the
  unfixed resolver at dc1e9f7 (implementer run + independent peer
  reproduction in a separate scratch worktree).
- `python3 scripts/ci/validate_sdd.py`: OBSERVED "Sea Speed SDD validation
  passed".
- `python3 scripts/ci/validate_change_contract.py` (PR body simulated):
  OBSERVED contract valid, derived impact VPS.

## Requirements traceability

- AC-001 | Task: T-1+T-2 | Evidence: focused pytest run — test_pipe_separated_groups_production_format resolves admin on the production pipe format; observed failing on base dc1e9f7 | Coverage: COVERED
- AC-002 | Task: T-1+T-2 | Evidence: focused pytest run — test_pipe_split_highest_wins resolves operator across pipe; observed failing on base dc1e9f7 | Coverage: COVERED
- AC-003 | Task: T-1+T-2 | Evidence: focused pytest run — test_mixed_separators_split resolves admin across mixed `|`/`,` | Coverage: COVERED
- AC-004 | Task: T-1+T-2 | Evidence: focused pytest run — test_pipe_unknown_tokens_fail_closed grants nothing for unknown pipe tokens; absent/blank → viewer pins pre-existing and untouched | Coverage: COVERED
- AC-005 | Task: T-2+T-3 | Evidence: full battery 1278/2/357 (delta exactly +4 methods, all pre-existing tests untouched), peer fuzz 20,027 cases (0 mismatches), ruff clean, validate_sdd passed (observed outputs in the completion gate) | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (1 api/app file + 1 test file + this trio)
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (rides the normal VPS release contour)
- [ ] Runtime acceptance resolved (post-deploy probe: owner-triggered mutations return 200)
- [x] Deferred work recorded (doc drift in specs/530-roles spec.md:124/plan.md:223 — follow-up, outside this scope)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
