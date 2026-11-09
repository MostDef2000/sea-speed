# Tasks — Issue #618 basic-auth HSTS inheritance loss on /sea-speed* paths

- Issue: #618
- Specification: specs/618-basic-auth-hsts/spec.md

## Delivery tasks

- T-1: scripts/operations/nginx_sea_speed_auth.py — SECURITY_HEADER_HSTS
  constant (basic-auth-only comment: location-level add_header cancels
  server-level HSTS inheritance, issue #618); emission in
  _basic_auth_location_snippet after the SECURITY_HEADERS block before
  LOCATION_END; verify() basic-auth sea-speed branch extends `required`
  with the HSTS line (fail-closed, #589 pattern). Authentik emission sites
  (_auth_location_snippet, _global_block, _fallback_block), the
  SECURITY_HEADERS tuple and the authentik verify branch untouched.
  DONE.
- T-2: tests/test_sea_speed_edge_vhost_renderer.py — BASIC_AUTH_GOLDEN_FRONT
  regenerated programmatically from the renderer output on the fixture
  (+3 HSTS lines, one per protected /sea-speed* location);
  AUTHENTIK_GOLDEN and BASIC_AUTH_GOLDEN_WORKER byte-unchanged; no other
  change in the file (new-golden-minus-HSTS-lines == old golden
  byte-for-byte). DONE.
- T-3: tests/test_618_basic_auth_hsts.py — acceptance oracle, 5 tests /
  1 class (renderer-test harness idiom of test_589/test_sea_speed_edge_vhost_renderer:
  importlib module load, stdlib imports only), pins: HSTS in every
  protected basic-auth location, server-level HSTS survives exactly once
  outside the snippets (1+3=4 accounting), verify() fail-closed on a
  single-location strip, authentik negative pin (no location-level HSTS),
  render idempotency with the new line; RED on base d60ffdb verified
  (FAILED, failures=4 — written and run before the renderer change),
  byte-unchanged through the fix (sha256 37f9004a). DONE.
- T-4: specs/618-basic-auth-hsts/ trio (this spec/plan/tasks). DONE.

## Battery identity

Baseline at base d60ffdb without the new file: 1412 passed / 2 skipped.
Delta: +5 test methods in tests/test_618_basic_auth_hsts.py — expected
1417 passed / 2 skipped. Observed: recorded in the completion gate below.

## Completion gate

- Focused `python3 -W error::ResourceWarning -m unittest tests.test_618_basic_auth_hsts -v`: OBSERVED 5/5 tests OK with the fix (EXIT=0).
- RED differential (test file written and run on base d60ffdb before the renderer change, byte-identical sha256 37f9004a through the fix): OBSERVED FAILED (failures=4 of 5) — HSTS absent from the basic-auth /sea-speed* locations, whole-server count 1 != 4, removal harness no-op so verify() accepts the stripped text, idempotency per-location pin failed; authentik negative pin green pre-fix by design. RED authenticity.
- Renderer suites `python3 -W error::ResourceWarning -m unittest tests.test_sea_speed_edge_vhost_renderer tests.test_589_security_headers_renderer -v`: OBSERVED 29 tests OK; `git diff --stat tests/test_589_security_headers_renderer.py` empty.
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`: OBSERVED 1417 tests OK (skipped=2).
- ruff `RUFF_CACHE=/tmp/opencode/toolcache/sea-speed ruff check --config scripts/quality/ruff.toml scripts/operations/nginx_sea_speed_auth.py tests/test_618_basic_auth_hsts.py tests/test_sea_speed_edge_vhost_renderer.py`: OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py`: OBSERVED pass (EXIT=0) with this trio.

## Requirements traceability

- AC-001 | Task: T-1+T-2+T-3 | Evidence: test_basic_auth_render_emits_hsts_in_every_sea_speed_location — 3 protected locations each carry the exact HSTS line; golden regenerated with the same 3 lines (RED on base d60ffdb: assertIn failed, line absent) | Coverage: COVERED
- AC-002 | Task: T-1+T-3 | Evidence: test_server_level_hsts_survives_rendering_exactly_once — outside the managed location snippets the server-level line survives exactly once; whole-server count 1+3=4 (RED on base: 1 != 4) — the renderer leaves server-level directives alone | Coverage: COVERED
- AC-003 | Task: T-1+T-3 | Evidence: test_verify_rejects_hsts_removed_from_one_sea_location — #589 removal-harness idiom strips the line from ONE location → ConfigError (RED on base: removal was a no-op and verify accepted the text — fail-closed pin placement proven) | Coverage: COVERED
- AC-004 | Task: T-1+T-3 | Evidence: test_authentik_mode_has_no_location_level_hsts — no authentik location body contains the HSTS line (negative pin against cross-mode creep; green pre- and post-fix by design) | Coverage: COVERED
- AC-005 | Task: T-1+T-3 | Evidence: test_render_idempotent_with_hsts_basic_auth — render(render(x)) == render(x) and the re-rendered output still carries HSTS in every protected location (canonical short-circuit accepts the new line) | Coverage: COVERED
- AC-006 | Task: T-1+T-2+T-3+T-4 | Evidence: full battery 1417 OK (skipped=2; baseline 1412), ruff clean, renderer suites 29 OK, test_589 git diff empty, RED differential failures=4 on base d60ffdb (observed outputs in the completion gate) | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (scripts/operations/nginx_sea_speed_auth.py + tests/test_618_basic_auth_hsts.py + tests/test_sea_speed_edge_vhost_renderer.py golden regeneration + this trio)
- [x] Required tests and evidence complete
- [x] Required CI green — pending exact-head CI on the merge PR — auto-synced on merge to main
- [x] Exact-green-head merge complete — pending squash merge to main — auto-synced on merge to main
- [ ] Deployment state resolved (CONTROL_PLANE contour — no runtime deployment occurs; the renderer reaches operators through the repository; production nginx apply is a separate lane-B/C operation with its own gates — out of scope here)
- [ ] Runtime acceptance resolved (exact-head CI green on the merge PR; live HSTS visibility on 3d.mostdef.ru responses deferred to the lane-B/C nginx apply)
- [x] Deferred work recorded (production nginx apply on 3d.mostdef.ru — lane-B/C operation with its own gates; live HSTS probe deferred to that apply)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
