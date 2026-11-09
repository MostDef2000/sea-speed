# Plan — Issue #618 basic-auth HSTS inheritance loss on /sea-speed* paths

- Issue: #618
- Specification: specs/618-basic-auth-hsts/spec.md

## Architecture

Single emission site + single verify pin in
`scripts/operations/nginx_sea_speed_auth.py`. The 3d.mostdef.ru vhost
carries `add_header Strict-Transport-Security "max-age=31536000" always;`
at server level (BASIC_AUTH_SOURCE fixture line 5), but nginx cancels the
entire inherited add_header set for any location that emits its own
add_header — and `_basic_auth_location_snippet` (:316-324) already emits
the #589 location-level set (XCTO, Referrer-Policy, CSP from the
SECURITY_HEADERS tuple). The fix appends one new module constant
``SECURITY_HEADER_HSTS`` (defined next to SECURITY_HEADERS with the
basic-auth-only rationale) to the basic-auth location-repeat set:
``lines.append(inner + SECURITY_HEADER_HSTS)`` after the SECURITY_HEADERS
extend, before LOCATION_END. The fail-closed contract pin extends
``required`` with the same line in the verify() basic-auth sea-speed
branch (the authentik branch and the common ``required += SECURITY_HEADERS``
line are untouched), mirroring the #589 per-location removal pattern: a
stripped line in any one location fails verification. SECURITY_HEADERS
itself is NOT extended — that would change authentik-mode output (global
block, fallback outage location, authentik locations), which is out of
#618 scope; the authentik server-level HSTS story is different and its
emission sites are untouched.

## Decisions

- **Basic-auth-only constant, not a SECURITY_HEADERS member**: the
  authentik-mode vhost's server-level HSTS story is different (issue text)
  and its rendered output is pinned byte-for-byte by AUTHENTIK_GOLDEN;
  extending the shared tuple would change the authentik global block,
  fallback location and authentik locations — out of #618 scope. A separate
  constant keeps the authentik emission sites byte-identical.
- **Emit after the #589 header block, inside the snippet**: the HSTS line
  lands in the same location-level add_header set (after XCTO /
  Referrer-Policy / CSP, before LOCATION_END), so the protected locations
  carry the complete header set and the server-level line keeps covering
  only the paths without location-level add_header.
- **Fail-closed verify pin mirrors #589**: ``required += (SECURITY_HEADER_HSTS,)``
  in the basic-auth branch makes a stripped line a ConfigError per
  location (the #589 removal-harness precedent), so a future edit that
  drops the re-emitted line cannot pass verification.
- **Golden regeneration is the only test-file change**: the golden is
  regenerated programmatically from the renderer on the existing
  BASIC_AUTH_SOURCE fixture; new-golden-minus-HSTS-lines == old golden
  byte-for-byte (verified: the diff is exactly 3 inserted lines, one per
  protected location). AUTHENTIK_GOLDEN and BASIC_AUTH_GOLDEN_WORKER are
  byte-unchanged.
- **RED-first test authorship**: tests/test_618_basic_auth_hsts.py was
  written and run against the base renderer BEFORE the fix (sha256
  37f9004a…, byte-identical through the fix) — RED authenticity is the
  natural run order, no revert dance needed.

## Affected contours

- Control plane: scripts/operations/nginx_sea_speed_auth.py (+14 lines:
  constant + rationale comment, emission line + comment, verify
  required-line + comment), tests/test_618_basic_auth_hsts.py (new, 5 tests),
  tests/test_sea_speed_edge_vhost_renderer.py (golden regeneration only,
  +3 lines), this SDD trio. Nothing else — no api/, worker/, frontend/,
  deploy/, .github/, no other scripts/ or tests/, no other specs/.
- CONTROL_PLANE contour: the renderer reaches operators through the
  repository; production nginx apply (re-render + reload on the VPS) is a
  separate lane-B/C operation with its own gates — no VPS/worker deploy in
  this change.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the emission is a single constant line appended to one snippet builder; the golden is regenerated programmatically from the actual renderer output and new-golden-minus-HSTS-lines equals the old golden byte-for-byte (git diff shows exactly 3 inserted lines); idempotency pin render(render(x)) == render(x) guards the canonical short-circuit in render() | Validation: tests/test_618_basic_auth_hsts.py + tests/test_sea_speed_edge_vhost_renderer.py + tests/test_589_security_headers_renderer.py + full battery | Residual risk: a future emission-site change could re-drop the line — the verify() pin fails closed on it | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: SEC | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the fix strictly adds a security header to protected responses (strictly more transport security, no weakening); the negative pin holds authentik mode free of location-level HSTS so the fix cannot creep across modes; the frozen #589 oracle (presence-only assertions) stays byte-identical and green | Validation: test_authentik_mode_has_no_location_level_hsts + renderer suites + git diff --stat on the frozen file (empty) | Residual risk: live 3d.mostdef.ru responses keep dropping HSTS until the production nginx apply (lane-B/C, out of scope) — recorded in RF-001 | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: CONTROL_PLANE contour — the renderer reaches operators through the repository; no deploy/** or scripts/release/** files change and no runtime deployment occurs; production nginx apply remains a separate lane-B/C operation with its own gates and transaction audit | Validation: validate_sdd green; exact-head CI on the merge PR | Residual risk: standard repository-contour risk only | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_618_basic_auth_hsts.py test_basic_auth_render_emits_hsts_in_every_sea_speed_location — 3 protected locations each carry the exact HSTS line (RED on base d60ffdb: line absent)
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: same file test_server_level_hsts_survives_rendering_exactly_once — outside the managed location snippets the server-level line survives exactly once; whole-server count 1+3=4 (RED on base: 1 != 4)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: same file test_verify_rejects_hsts_removed_from_one_sea_location — #589 removal-harness idiom strips the line from ONE location → ConfigError (RED on base: removal is a no-op, verify accepts the text)
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: same file test_authentik_mode_has_no_location_level_hsts — no authentik location body contains the HSTS line (negative pin, green pre- and post-fix by design)
- TEST-005 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: same file test_render_idempotent_with_hsts_basic_auth — render(render(x)) == render(x) and the re-rendered locations still carry HSTS (RED on base: per-location pin fails)
- TEST-006 | Covers: AC-006 | Level: integration | Priority: P1 | Evidence: RED differential (test file byte-identical, sha256 37f9004a, run on base d60ffdb before the renderer change → FAILED failures=4; with the fix → 5/5 OK) + full battery 1417 OK (skipped=2; baseline 1412) + ruff clean + renderer suites 29 OK + test_589 git diff empty (observed, see Validation)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

NOT REQUIRED for this change: CONTROL_PLANE contour (scripts/operations/**
per change-control-policy-v1), no deploy/** or scripts/release/** files
changed, and no VPS/worker deployment is declared — no runtime deployment
transaction occurs. The renderer reaches operators through the repository;
the production nginx apply on 3d.mostdef.ru (re-render + reload, where live
HSTS visibility is probed) remains a separate lane-B/C operation with its
own gates and carries its own transaction audit at that time (#589
precedent).

## Validation

- Focused run `python3 -W error::ResourceWarning -m unittest tests.test_618_basic_auth_hsts -v`: OBSERVED 5/5 tests OK with the fix (EXIT=0).
- RED differential: the test file was written and run BEFORE the renderer change on base d60ffdb → OBSERVED FAILED (failures=4 of 5) — HSTS absent from the basic-auth locations (assertIn fails), whole-server HSTS count 1 != 4, the removal harness cannot strip a line that is not there so verify() accepts the stripped text (assertNotEqual fails), and the idempotency per-location pin fails; the authentik negative pin passes pre-fix by design. Test file byte-identical through the fix (sha256 37f9004ae638cd90309b1ffb5a71a8203d2de24b5392ab0ccebf78531464d5a7 before and after).
- Renderer suites `python3 -W error::ResourceWarning -m unittest tests.test_sea_speed_edge_vhost_renderer tests.test_589_security_headers_renderer -v`: OBSERVED 29 tests OK; `git diff --stat tests/test_589_security_headers_renderer.py` empty (frozen oracle untouched).
- Golden regeneration: BASIC_AUTH_GOLDEN_FRONT regenerated programmatically from the renderer output on the fixture; git diff = exactly 3 inserted HSTS lines (one per protected location); AUTHENTIK_GOLDEN and BASIC_AUTH_GOLDEN_WORKER byte-unchanged.
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`: OBSERVED 1417 tests OK (skipped=2); baseline at d60ffdb without the new file 1412 OK (skipped=2) — delta +5 tests as accounted.
- ruff `RUFF_CACHE=/tmp/opencode/toolcache/sea-speed ruff check --config scripts/quality/ruff.toml scripts/operations/nginx_sea_speed_auth.py tests/test_618_basic_auth_hsts.py tests/test_sea_speed_edge_vhost_renderer.py`: OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py` with this trio: OBSERVED pass (EXIT=0).

## Runtime feedback

- RF-001: Operator actions expected: 0 — CONTROL_PLANE contour; the renderer
  reaches operators through the repository. Runtime acceptance = exact-head
  CI green on the merge PR; live HSTS visibility on 3d.mostdef.ru responses
  is probed at the separate lane-B/C production nginx apply.
- RF-002: strictly additive basic-auth-mode header emission; authentik-mode
  output byte-identical; no server-level directive touched; no data
  migration or runtime deploy involved.
