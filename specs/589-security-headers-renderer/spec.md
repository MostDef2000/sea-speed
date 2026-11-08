# Spec: #589 — Security-header set (XCTO, Referrer-Policy, CSP) emitted by the nginx edge-vhost renderer

- Issue: #589
- Specification: specs/589-security-headers-renderer/spec.md
- Authorization: wave-1 task C (owner instruction 2026-11-08: continue
  execution per the last approved plan; scope A of wave 1 — #591 + #587 +
  #589 + #576 closure); base ab901e06, head = the upcoming fix commit on
  branch main (fix uncommitted in the working tree at trio-writing time;
  committed together with this trio).

## Product outcome

The #581 live probe found the security-header families CSP/frame-ancestors,
X-Content-Type-Options and Referrer-Policy absent from every observable live
response, and the repo's nginx generator
(scripts/operations/nginx_sea_speed_auth.py) emits none of them — only HSTS
exists (edge/origin layer, preserved-not-generated per specs/520). After the
fix: the renderer emits a frozen three-header set — X-Content-Type-Options
"nosniff", Referrer-Policy "strict-origin-when-cross-origin", and
Content-Security-Policy "default-src 'self'; script-src 'self'
https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; connect-src
'self'; media-src 'self' blob:; img-src 'self' data:; frame-ancestors
'none'" — every line as nginx `add_header ... always;`, defined once as
module constants aggregated in a SECURITY_HEADERS tuple (single source of
truth for emission and verification). Emission is inheritance-aware: at
server level in the authentik-mode global marked block, plus explicit
repeats inside every protected /sea-speed* location and the fallback outage
location (any location-level add_header cancels server-level add_header
inheritance), and inside every protected location in basic-auth mode (no
server-level requirement there). verify() pins the set so a stripped or
hand-edited config fails closed with ConfigError, and an old pre-#589
rendered config fed to the new verify() is rejected — render()'s canonical
early-return then breaks and the full re-render path regenerates the config
with headers (fail-closed migration, intentional). Outpost/signin locations
(proxied Authentik content) deliberately get no headers. Production nginx
apply is a separate lane-B/C operation with its own gates (explicit issue
requirement) — this change ships the renderer only.

## User scenarios

- SC-1: an operator renders the edge vhost in authentik mode — the global
  marked block carries all three headers at server level, every protected
  /sea-speed* location repeats all three, and the fallback outage location
  repeats all three (locations carrying their own add_header — Set-Cookie in
  auth locations, Cache-Control/Retry-After in the fallback — would
  otherwise cancel server-level inheritance).
- SC-2: an operator renders the edge vhost in basic-auth mode — every
  protected /sea-speed* location repeats all three headers; no server-level
  emission is required or made in this mode.
- SC-3: a hand-edited or stripped config is verified — removing any of the
  three header lines from the server-level global block or from any
  protected location (either mode) makes verify() raise ConfigError instead
  of passing.
- SC-4: rendering is idempotent — render(render(x)) == render(x) in both
  modes with the headers present.
- SC-5: an old pre-#589 rendered config is fed to the new renderer —
  verify() rejects it (ConfigError, both modes), the canonical early-return
  breaks, and the full re-render path regenerates the config with the header
  set (fail-closed, intentional).

## Requirements

- R-1: scripts/operations/nginx_sea_speed_auth.py defines the header set
  once — module constants SECURITY_HEADER_XCTO / SECURITY_HEADER_REFERRER /
  SECURITY_HEADER_CSP (:80-89) aggregated in the SECURITY_HEADERS tuple —
  the single source of truth driving both emission and verification; static
  public header strings only, never any secret value.
- R-2: emission at exactly 4 sites: server-level top of the authentik-mode
  global marked block (_global_block :371), authentik protected /sea-speed*
  locations (_auth_location_snippet :312), basic-auth protected locations
  (_basic_auth_location_snippet :322), fallback outage location
  (_fallback_block :329); every emitted line ends with `always;`.
- R-3: verify() pins the set — authentik mode: the global-block body (the
  GLOBAL_BEGIN..GLOBAL_END slice, guarded by the existing count==1 checks —
  not the whole server text) must contain all three; every protected
  /sea-speed* location must contain all three in BOTH modes; the fallback
  outage location body must contain all three (authentik mode); basic-auth
  mode has NO server-level requirement.
- R-4: deliberate exclusions: outpost/signin locations (proxied Authentik
  content) get no security headers; the worker-private block is untouched;
  basic-auth mode gets no server-level emission.
- R-5: the golden constants in tests/test_sea_speed_edge_vhost_renderer.py
  are regenerated programmatically (+21 header lines: 4 sites × 3 in
  AUTHENTIK_GOLDEN, 3 × 3 in BASIC_AUTH_GOLDEN_FRONT, 0 in
  BASIC_AUTH_GOLDEN_WORKER); new-golden-minus-header-lines equals the old
  golden byte-for-byte.
- R-6: tests/test_589_security_headers_renderer.py (8 test methods) is the
  acceptance oracle, byte-unchanged through the fix (md5
  b78107038b57a65adfefb9446448a069), RED on base ab901e06 and GREEN with the
  fix; stdlib-only imports, so the run_tests import-hygiene scan needs no
  registration tuple.
- R-7: no existing renderer pin is weakened — outage headers, auth wiring,
  the secret-literal ban and all pre-existing golden/verify assertions stay
  intact (full battery green).

## Acceptance criteria

- AC-001: authentik-mode render emits all three headers at server level
  inside the global marked block (GLOBAL_BEGIN..GLOBAL_END body); on base
  ab901e06 the test fails (headers absent) — RED authenticity recorded.
- AC-002: authentik-mode render repeats all three headers in every protected
  /sea-speed* location (2 locations in the fixture).
- AC-003: authentik-mode render repeats all three headers in the fallback
  outage location.
- AC-004: basic-auth-mode render repeats all three headers in every protected
  /sea-speed* location (3 locations in the fixture).
- AC-005: verify() rejects (ConfigError) a config whose server-level global
  block had the header lines stripped; on base the pin does not exist and
  the stripped config verifies — RED authenticity recorded.
- AC-006: verify() rejects (ConfigError) a config with one header line
  removed from a protected /sea-speed* location, in both modes.
- AC-007: every emitted header line ends with `always;` and the CSP value
  contains no secret-shaped literals (the existing no-secret pin extended to
  the new header set).
- AC-008: render is idempotent with the headers present, in both modes
  (render(render(x)) == render(x)).
- AC-009: full battery green with the fix (1398 tests, skipped=2), ruff
  clean, validate_sdd green; no committed test regressed; the oracle file is
  byte-unchanged from its RED state.

## Runtime feedback

- RF-001: Operator actions expected: 0 — the renderer file rides the normal
  VPS release artifact, so the lane-A deploy delivers the updated renderer
  to the VPS, but it does NOT regenerate or apply the nginx vhost config:
  production nginx apply is a separate lane-B/C operation with its own gates
  (explicit issue requirement). Runtime acceptance for THIS issue = the
  deploy delivers the renderer (artifact/file updated on VPS) + CI battery
  green on the exact merged SHA; header visibility on live responses is
  deferred to the lane-B/C apply and explicitly out of scope here.
- RF-002: behavior note — renderer output changes, so an old pre-#589
  rendered config fails the new verify() pins (ConfigError, both modes —
  fail-closed by design) and render()'s canonical early-return breaks for
  it, forcing the full re-render path that regenerates the config with the
  header set; already-canonical post-fix configs keep the early-return; no
  production nginx config is touched by this change.

## NFR assessment

- NFR-001 | Area: security headers coverage | Target: the rendered edge
  vhost carries X-Content-Type-Options "nosniff", Referrer-Policy
  "strict-origin-when-cross-origin" and a CSP with frame-ancestors 'none'
  (jsdelivr only in script-src for hls.js), emitted with `always;` at every
  inheritance-relevant site | Validation:
  tests/test_589_security_headers_renderer.py (8 test methods; RED on base
  ab901e06 — 36 failures — and GREEN with the fix; stash differential
  verified) | Evidence: focused run + RED differential recorded in plan.md |
  Status: PASS
- NFR-002 | Area: compatibility | Target: zero behavior change for
  already-canonical post-fix configs except the intentional fail-closed
  migration of old configs; existing renderer pins (outage headers, auth
  wiring, secret-literal ban) intact | Validation: full battery 1398 OK
  (skipped=2) incl. tests/test_sea_speed_edge_vhost_renderer.py; ruff clean |
  Evidence: observed runs recorded in plan.md and tasks.md | Status: PASS
- NFR-003 | Area: performance | Target: negligible — three static string
  constants emitted at render time and substring checks in verify(); the
  headers are static nginx config lines, no per-request runtime cost |
  Validation: code review; no hot-loop additions | Evidence: diff inspection
  (+28/−3 renderer, +21 golden lines) | Status: PASS
