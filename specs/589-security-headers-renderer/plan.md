# Plan — Issue #589 security-header set from the nginx edge-vhost renderer

- Issue: #589
- Specification: specs/589-security-headers-renderer/spec.md

## Architecture

Single-source constants + inheritance-aware emission + verify pins, all
inside scripts/operations/nginx_sea_speed_auth.py. The three header lines
are module constants (SECURITY_HEADER_XCTO / SECURITY_HEADER_REFERRER /
SECURITY_HEADER_CSP, :80-89) aggregated in the SECURITY_HEADERS tuple — the
same tuple drives emission and verification, so the set cannot drift between
the two. Emission at 4 sites: server-level top of the authentik-mode global
marked block (_global_block :371), inside every authentik protected
/sea-speed* location (_auth_location_snippet :312), inside every basic-auth
protected location (_basic_auth_location_snippet :322), and inside the
fallback outage location (_fallback_block :329). verify() pins: the
global-block body — the GLOBAL_BEGIN..GLOBAL_END slice taken after the
existing count==1 guards, deliberately not the whole server text, so a
header line smuggled outside the marked block cannot satisfy the pin
(:478-480); the per-location required-marker list extended with
SECURITY_HEADERS for both modes (:513); the fallback location body pinned in
authentik mode (:496-497).

nginx inheritance rationale: any location-level add_header cancels
server-level add_header inheritance for that location. The protected
locations carry their own add_header (Set-Cookie in auth locations,
Cache-Control/Retry-After in the fallback), so server-level lines alone
would never reach them — hence the explicit repeats. Server-level lines do
reach locations without their own add_header (e.g. the /cams deny
locations), which get the set without duplication.

## Decisions

- **Inheritance-aware repeats (server-level AND location-level)**: nginx
  add_header inheritance is cancelled per-location by any location-level
  add_header; emitting only at server level would silently produce no
  security headers on exactly the locations that matter (auth + fallback).
  Repeats make each protected location self-contained.
- **No CSP on Authentik outpost/signin locations**: those locations proxy
  Authentik's own content (outpost start, signin redirect); a CSP authored
  for the Sea Speed app could break Authentik's pages, and the header set
  targets Sea Speed responses. Documented exclusion — the oracle
  deliberately does not test those locations.
- **Basic-auth mode: no server-level emission**: in basic-auth mode the
  renderer's codified footprint is the location-level marked blocks only (no
  renderer-owned server-level marked block exists to emit into or pin), so
  the set is repeated inside every protected location and no server-level
  requirement is enforced. Consequence tracked as follow-up #618.
- **Fail-closed old-config migration**: an old pre-#589 rendered config fed
  to the new verify() raises ConfigError (peer-verified both modes), which
  breaks render()'s canonical early-return (it returns the text unchanged
  only when verify() passes) and forces the full re-render path — the config
  converges to the header-bearing form instead of a headerless config staying
  "canonical". Intentional.

## Affected contours

- CONTROL_PLANE (per change-control-policy-v1: scripts/operations/**):
  scripts/operations/nginx_sea_speed_auth.py (+28/−3) — an operator tool
  delivered through the repository; no runtime deployment occurs.
- No runtime contour: tests/test_sea_speed_edge_vhost_renderer.py (+21
  golden lines), tests/test_589_security_headers_renderer.py (new, 8
  methods), this SDD trio classify NONE. Nothing else — no api/, worker/,
  frontend/, deploy/, .github/ changes and no production nginx config
  change (the lane-B/C apply is a separate gated operation per the issue).

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the new location-level add_header lines in basic-auth mode cancel server-level add_header inheritance for the protected /sea-speed* locations — the operator's server-level HSTS no longer reaches them; filed as follow-up #618 (outside this fix's frozen design), mitigated by browser HSTS stickiness and by basic-auth not being the current production mode | Validation: follow-up #618 tracks the fix; the frozen design is pinned byte-exactly by the oracle | Residual risk: accepted for this scope, owned by #618 | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-002 | Category: TECH | Probability: 1 | Impact: 1 | Score: 1 | Mitigation: verify() pins are substring checks, so a header line pasted into a comment or another directive's argument could theoretically false-pass; unreachable through the renderer (it emits whole marked lines at fixed positions) and the marked-block slice bounds (count==1 guards + GLOBAL_BEGIN..GLOBAL_END slice) keep the server-level pin scoped | Validation: tests/test_589_security_headers_renderer.py (strip-based negative tests remove whole lines, not substrings) | Residual risk: theoretical, hand-crafted configs only | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: this change ships the renderer only — it does not regenerate or apply the nginx vhost config and no runtime deployment occurs (CONTROL_PLANE contour), so no production nginx mutation happens in this scope; production apply is a separate lane-B/C operation with its own gates (explicit issue requirement); old configs are only re-rendered if/when the renderer is actually run on them, and then fail closed into a full re-render | Validation: full battery + ruff + validate_sdd green before merge; no deploy step exists in this scope | Residual risk: none from this change; the lane-B/C apply carries its own gates | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: tests/test_589_security_headers_renderer.py::test_authentik_render_emits_security_headers_server_level — global-block body contains all three header lines
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: same file::test_authentik_render_repeats_headers_in_every_sea_speed_location — 2 protected locations × 3 headers
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: same file::test_authentik_render_repeats_headers_in_fallback_location
- TEST-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: same file::test_basic_auth_render_repeats_headers_in_every_sea_speed_location — 3 protected locations × 3 headers
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: same file::test_verify_rejects_missing_server_level_headers — header lines stripped from the global block → ConfigError
- TEST-006 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: same file::test_verify_rejects_missing_location_repeat — one header line removed from one protected location → ConfigError, both modes
- TEST-007 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: same file::test_headers_carry_always_flag_and_no_secret_literals — every emitted line ends with `always;`; CSP value free of secret-shaped literals
- TEST-008 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: same file::test_render_idempotent_with_headers_both_modes — render(render(x)) == render(x), both modes
- TEST-009 | Covers: AC-009 | Level: integration | Priority: P1 | Evidence: RED differential (36 failures on base ab901e06 with scripts/ stashed; 8/8 OK with the fix) + full battery 1398 OK (skipped=2) + ruff clean (observed, see Validation)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: #618 (basic-auth mode HSTS inheritance loss on /sea-speed* paths — outside this fix's frozen design; recorded in RISK-001 and the Definition of Done)

## Deployment transaction audit

NOT REQUIRED for this change: CONTROL_PLANE contour (scripts/operations/**
per change-control-policy-v1), no deploy/** or scripts/release/** files
changed, and the PR declares VPS deployment NOT REQUIRED — no runtime
deployment transaction occurs. The renderer reaches operators through the
repository; production nginx apply remains a separate lane-B/C operation
with its own gates (explicit issue requirement) and carries its own
transaction audit at that time.

## Validation

- Focused run `python3 -W error::ResourceWarning -m unittest
  tests.test_589_security_headers_renderer`: OBSERVED 8/8 methods OK with
  the fix.
- RED differential: scripts/ fix stashed on base ab901e06 → OBSERVED 36
  failures (headers absent / header pins not yet enforced); fix restored
  byte-identical afterwards → 8/8 OK (orchestrator-observed via stash;
  independently reproduced on a scratch base copy: FAILED (failures=36)).
- Golden integrity: new golden constants minus the 21 header lines equal the
  base goldens byte-for-byte (AUTHENTIK_GOLDEN, BASIC_AUTH_GOLDEN_FRONT,
  BASIC_AUTH_GOLDEN_WORKER — the last byte-identical, 0 header lines).
- Fail-closed migration: old (base) rendered config + new verify() →
  ConfigError in both modes; new.render(old_cfg) differs from old_cfg (full
  re-render path) in both modes.
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p 'test_*.py'`: OBSERVED 1398 tests OK (skipped=2); baseline at
  ab901e06 without the new file 1390 OK (skipped=2) — delta +8 methods as
  accounted.
- ruff `ruff check --config scripts/quality/ruff.toml` on the renderer and
  both test files: OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py` with this trio: pending final green
  run recorded in the delivery report.

## Runtime feedback

- RF-001: Operator actions expected: 0 — CONTROL_PLANE contour, no runtime
  deployment occurs; runtime acceptance for this issue = exact-head CI green
  on the merge PR. Header visibility on live responses is deferred to the
  separate lane-B/C production nginx apply (explicit issue requirement) and
  is out of scope here.
- RF-002: no production nginx config is touched by this change; old
  pre-#589 rendered configs fail the new verify() pins and re-render fully
  (fail-closed, intentional) whenever the updated renderer is next run on
  them.
