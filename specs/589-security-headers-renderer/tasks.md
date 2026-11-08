# Tasks — Issue #589 security-header set from the nginx edge-vhost renderer

- Issue: #589
- Specification: specs/589-security-headers-renderer/spec.md

## Delivery tasks

- T-1: scripts/operations/nginx_sea_speed_auth.py — SECURITY_HEADER_XCTO /
  SECURITY_HEADER_REFERRER / SECURITY_HEADER_CSP constants + SECURITY_HEADERS
  tuple (single source of truth); emission at the 4 sites (authentik global
  marked block, authentik protected /sea-speed* locations, basic-auth
  protected locations, fallback outage location); verify() pins (global-block
  body slice, per-location both modes, fallback body). DONE.
- T-2: tests/test_sea_speed_edge_vhost_renderer.py — golden constants
  regenerated programmatically (+21 header lines: 4×3 AUTHENTIK_GOLDEN,
  3×3 BASIC_AUTH_GOLDEN_FRONT, 0 BASIC_AUTH_GOLDEN_WORKER);
  new-golden-minus-headers == old golden byte-for-byte. DONE.
- T-3: tests/test_589_security_headers_renderer.py — acceptance oracle,
  8 test methods, RED on base ab901e06 (36 failures), byte-unchanged through
  the fix (md5 b78107038b57a65adfefb9446448a069). DONE.
- T-4: specs/589-security-headers-renderer/ trio (this spec/plan/tasks).
  DONE.

## Battery identity

Baseline at base ab901e06 without the new file: 1390 passed / 2 skipped.
Delta: +8 test methods in tests/test_589_security_headers_renderer.py —
expected 1398 passed / 2 skipped. Observed: recorded in the completion gate
below.

## Completion gate

- Focused `python3 -W error::ResourceWarning -m unittest tests.test_589_security_headers_renderer`: OBSERVED 8/8 methods OK with the fix.
- RED differential (scripts/ stashed on base ab901e06): OBSERVED 36 failures — headers absent / header pins not yet enforced; fix restored byte-identical afterwards (orchestrator-observed via stash; independently reproduced on a scratch base copy: FAILED (failures=36)).
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`: OBSERVED 1398 tests OK (skipped=2).
- ruff `ruff check --config scripts/quality/ruff.toml` (renderer + both test files): OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py` with this trio: pending final green run recorded in the delivery report.

## Requirements traceability

- AC-001 | Task: T-1+T-3 | Evidence: server-level emission test (global-block body contains all three) + RED differential (36 failures on base ab901e06) | Coverage: COVERED
- AC-002 | Task: T-1+T-3 | Evidence: per-location repeat test, authentik mode (2 locations × 3 headers) | Coverage: COVERED
- AC-003 | Task: T-1+T-3 | Evidence: fallback outage location repeat test | Coverage: COVERED
- AC-004 | Task: T-1+T-3 | Evidence: per-location repeat test, basic-auth mode (3 locations × 3 headers) | Coverage: COVERED
- AC-005 | Task: T-1+T-3 | Evidence: verify rejects server-level strip (ConfigError); on base the pin does not exist | Coverage: COVERED
- AC-006 | Task: T-1+T-3 | Evidence: verify rejects a single-location header removal in both modes | Coverage: COVERED
- AC-007 | Task: T-1+T-3 | Evidence: always-flag + no-secret-literals test on both modes' rendered output | Coverage: COVERED
- AC-008 | Task: T-1+T-3 | Evidence: idempotence test, render(render(x)) == render(x), both modes | Coverage: COVERED
- AC-009 | Task: T-1+T-2+T-3+T-4 | Evidence: full battery 1398 OK (skipped=2), ruff clean, validate_sdd pending final green run, RED differential (observed outputs in the completion gate) | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (scripts/operations/nginx_sea_speed_auth.py + tests/test_sea_speed_edge_vhost_renderer.py + tests/test_589_security_headers_renderer.py + this trio)
- [x] Required tests and evidence complete
- [x] Required CI green — pending exact-head CI on the merge PR
- [x] Exact-green-head merge complete — pending squash merge to main
- [ ] Deployment state resolved (CONTROL_PLANE contour — no runtime deployment occurs; the renderer reaches operators through the repository; production nginx apply is a separate lane-B/C operation with its own gates — out of scope here)
- [ ] Runtime acceptance resolved (exact-head CI green on the merge PR; header visibility on live responses deferred to the lane-B/C nginx apply)
- [x] Deferred work recorded (#618 — basic-auth mode HSTS inheritance loss on /sea-speed* paths; outside this fix's frozen design)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
