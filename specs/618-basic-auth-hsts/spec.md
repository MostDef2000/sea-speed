# Spec: #618 — basic-auth /sea-speed* locations must re-emit HSTS (location-level add_header cancels server-level inheritance)

- Issue: #618
- Specification: specs/618-basic-auth-hsts/spec.md
- Authorization: commit approved (wave-2 task C admission, 2026-11-09); base
  d60ffdbc58570eb3c96a2b28472f886b21657342 (includes merged #616/#617),
  branch fix/618-basic-auth-hsts.

## Product outcome

The 3d.mostdef.ru vhost carries `add_header Strict-Transport-Security
"max-age=31536000" always;` at server level, but nginx cancels the entire
inherited `add_header` set for any location that emits its own `add_header`
— and every protected `/sea-speed*` location in basic-auth mode emits the
#589 location-level security-header set (XCTO, Referrer-Policy, CSP) via
``_basic_auth_location_snippet`` (scripts/operations/nginx_sea_speed_auth.py).
Responses from those paths therefore drop HSTS. After the fix: the
basic-auth location snippet re-emits the exact HSTS line after the #589
header block (new module constant ``SECURITY_HEADER_HSTS``), and
``verify()`` fails closed when the line is stripped from any one protected
location. Authentik mode is byte-unchanged (its server-level HSTS story is
different — out of #618 scope), and the server-level HSTS line of the
source vhost is untouched (the renderer never rewrites server-level
directives).

## User scenarios

- SC-1: a browser opens any protected `/sea-speed*` path on 3d.mostdef.ru
  in basic-auth mode — the response carries
  `Strict-Transport-Security: max-age=31536000` (the location-level #589
  header set no longer cancels it), so HSTS enforcement holds on the edge
  vhost.
- SC-2: an operator re-renders or hand-edits the basic-auth vhost and
  strips the HSTS line from one `/sea-speed*` location — `verify()`
  rejects the config (fail-closed) instead of silently deploying the
  inheritance loss.
- SC-3: an operator renders the authentik-mode vhost — output is
  byte-identical to the pre-#618 renderer (no location-level HSTS creep;
  the authentik server-level HSTS story is out of scope).

## Requirements

- R-1: scripts/operations/nginx_sea_speed_auth.py adds module constant
  ``SECURITY_HEADER_HSTS = 'add_header Strict-Transport-Security
  "max-age=31536000" always;'`` next to ``SECURITY_HEADERS`` with a comment
  explaining why it is basic-auth-only (location-level add_header cancels
  server-level inheritance; extending SECURITY_HEADERS itself would change
  authentik-mode output — global block, fallback, authentik locations —
  out of #618 scope).
- R-2: ``_basic_auth_location_snippet`` emits the HSTS line inside the
  location, after the ``SECURITY_HEADERS`` block and before
  LOCATION_END — the only emission-site change. ``_auth_location_snippet``,
  ``_global_block``, ``_fallback_block`` and the server-level HSTS line of
  the source vhost are untouched (the renderer never rewrites server-level
  directives — existing pin
  test_basic_auth_render_leaves_server_level_directives_and_other_servers_untouched
  stays green).
- R-3: ``verify()`` basic-auth sea-speed branch extends ``required`` with
  the HSTS line (fail-closed, mirroring the #589 per-location pattern); the
  authentik branch is unchanged.
- R-4: tests/test_sea_speed_edge_vhost_renderer.py — BASIC_AUTH_GOLDEN_FRONT
  regenerated programmatically from the renderer (+3 HSTS lines, one per
  protected `/sea-speed*` location); AUTHENTIK_GOLDEN,
  BASIC_AUTH_GOLDEN_WORKER and every other test in the file byte-unchanged
  (the file's only diff is the golden regeneration).
- R-5: tests/test_618_basic_auth_hsts.py (5 tests) is the acceptance
  oracle, byte-unchanged through the fix, RED on base d60ffdb (FAILED,
  failures=4 — HSTS absent from the basic-auth locations, the removal
  harness cannot strip a line that is not there so verify() accepts the
  text, whole-server HSTS count 1 != 4, and the post-re-render location pin)
  and GREEN with the fix; renderer-test harness only (importlib module
  load, stdlib imports — no api/FastAPI import, so the import-hygiene
  registry in tests/test_run_tests_script.py needs no change).
- R-6: tests/test_589_security_headers_renderer.py is a FROZEN oracle —
  byte-identical and green through this fix (its assertions are
  presence-only, so the added HSTS line does not affect it).

## Acceptance criteria

- AC-001: rendered basic-auth output carries the exact HSTS line
  (`add_header Strict-Transport-Security "max-age=31536000" always;`) in
  EVERY protected `/sea-speed*` location body — 3 locations in the
  BASIC_AUTH_SOURCE fixture (/sea-speed/, /sea-speed/api/,
  /sea-speed/media/); on base d60ffdb the locations carry no HSTS line
  (RED differential verified).
- AC-002: the server-level HSTS line of the source vhost survives rendering
  exactly once in the server text outside the renderer-managed location
  snippets (not stripped, not duplicated); whole-server accounting is
  1 server-level + 3 location repeats = 4 occurrences.
- AC-003: verify() fail-closed — removing the HSTS line from ONE sea-speed
  location yields ConfigError (per-location walk, #589 removal-harness
  idiom); on base the removal is a no-op and verify accepts the text.
- AC-004: authentik-mode rendered output contains NO location-level HSTS
  line in any location body (negative pin — the fix must not creep into
  authentik mode).
- AC-005: render idempotency holds with the new line —
  render(render(x)) == render(x) for basic-auth mode, and the re-rendered
  output still carries HSTS in every protected location.
- AC-006: full battery green with the fix (1417 tests, skipped=2; baseline
  at d60ffdb without the new file 1412 — delta +5), ruff clean on the
  changed files, the frozen #589 oracle byte-identical (git diff empty) and
  green, and the new test file RED on base d60ffdb (FAILED, failures=4) /
  GREEN with the fix, byte-unchanged.

## Runtime feedback

- RF-001: Operator actions expected: 0 — CONTROL_PLANE contour: the renderer
  reaches operators through the repository; production nginx apply on
  3d.mostdef.ru (re-render + reload) remains a separate lane-B/C operation
  with its own gates, where live HSTS visibility on /sea-speed* responses is
  probed. Runtime acceptance for this change = exact-head CI green on the
  merge PR.
- RF-002: strictly additive header emission in basic-auth mode only —
  authentik-mode output is byte-identical (AUTHENTIK_GOLDEN unchanged); the
  previously dropped HSTS header reappears on protected /sea-speed*
  responses (strictly more browser-enforced transport security); no
  server-level directive of the source vhost is touched.

## NFR assessment

- NFR-001 | Area: security headers / transport security | Target: every protected /sea-speed* location in basic-auth mode re-emits `add_header Strict-Transport-Security "max-age=31536000" always;` so nginx location-level add_header no longer cancels server-level HSTS on those responses; verify() fails closed on a stripped line in any one location | Validation: tests/test_618_basic_auth_hsts.py (5 tests; RED on base d60ffdb failures=4, GREEN 5/5 with fix) + regenerated BASIC_AUTH_GOLDEN_FRONT | Evidence: focused run + base differential recorded in plan.md | Status: PASS
- NFR-002 | Area: compatibility | Target: zero change for authentik mode — AUTHENTIK_GOLDEN byte-unchanged, no location-level HSTS in any authentik location, frozen #589 oracle byte-identical and green; server-level HSTS line of the source vhost survives exactly once; SECURITY_HEADERS tuple not extended | Validation: renderer suites (29 tests OK) + full battery 1417 OK (skipped=2) + ruff clean | Evidence: observed runs recorded in plan.md and tasks.md | Status: PASS
- NFR-003 | Area: performance | Target: negligible — one constant string appended per basic-auth location snippet at render time and one extra containment check per sea-speed location in verify(); no hot-loop or parsing changes | Validation: code review; diff inspection (+4 renderer lines incl. comments) | Evidence: diff inspection in plan.md | Status: PASS
