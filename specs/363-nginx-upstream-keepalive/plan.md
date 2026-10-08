# Plan: NGINX upstream keepalive for Camera 1 HLS

- Issue: #363
- Specification: specs/363-nginx-upstream-keepalive/spec.md

## Implementation approach

1. `scripts/operations/nginx_cam1_direct_h264.py` — replace the direct
   upstream constant with `CAM1_BACKEND = "127.0.0.1:18889"`,
   `HLS_UPSTREAM = "sea_speed_cam1_hls"` and
   `PROXY_PASS = f"http://{HLS_UPSTREAM}/cam1/"`; add `_remove_upstream()`
   (removes any previously emitted `upstream <name>` block plus its
   trailing blank line, reusing the file's existing `_blocks()` scanner);
   in `render()`, after the marked-section/legacy-location cleanup, emit
   the upstream block immediately before the managed server block at the
   server line's indent (so it lands inside the enclosing `http{}` in
   real configs), then re-locate the server block and insert the managed
   location with `proxy_pass http://sea_speed_cam1_hls/cam1/;`,
   `proxy_http_version 1.1;` and `proxy_set_header Connection "";`.
2. `verify()` hardening — before the existing checks, require exactly one
   `upstream` block named `sea_speed_cam1_hls` in the full text and
   require `server 127.0.0.1:18889;` plus `keepalive 8;` inside its body;
   inside the managed block require
   `proxy_pass http://sea_speed_cam1_hls/cam1/;`,
   `proxy_http_version 1.1;` and `proxy_set_header Connection "";` (the
   latter two via the existing required-directive loop, which keeps the
   `proxy_cache off;` / `proxy_buffering off;` / `Cache-Control` checks).
3. Test pins — `tests/test_camera1_direct_h264_cutover.py` swaps the
   direct `proxy_pass` pin for the named-upstream pin and adds assertions
   for the upstream block, `server 127.0.0.1:18889;`, `keepalive 8;`,
   `proxy_http_version 1.1;` and `proxy_set_header Connection "";`;
   `tests/test_sea_speed_auth_v1.py` is audited and deliberately left
   unchanged (its ~:50 line is the legacy input fixture).

## Architecture

The renderer stays a pure text transformer plus a deterministic verifier
with no I/O in the library path. The upstream block is emitted
immediately before the managed `server` block: in a real nginx tree the
server block lives inside `http{}`, so the upstream lands at http level
where NGINX requires it; in test fixtures without an `http{}` wrapper it
simply precedes the server. `verify()` locates the upstream block by
name over the whole text (it lives outside the server block) and keeps
all managed-block checks scoped to the server text and the BEGIN/END
region, exactly like the pre-existing checks.

## Decisions

- D-1: Named upstream (`sea_speed_cam1_hls`) with
  `proxy_pass http://sea_speed_cam1_hls/cam1/;` — the `/cam1/` URI
  suffix is preserved so the path rewrite to MediaMTX is byte-identical
  to the previous behavior.
- D-2: `keepalive 8` per the approved work order — bounds the per-worker
  idle connection pool while comfortably covering the hls.js request
  rate for one camera.
- D-3: `proxy_http_version 1.1` + `proxy_set_header Connection "";` are
  mandatory companions of `keepalive` in NGINX (the default HTTP/1.0 +
  `Connection: close` behavior would defeat the pool); both are already
  partially present, the header is added.
- D-4: Upstream removal on every re-render (mirroring the existing
  `_strip_marked_section`/`_remove_location` idempotency idiom) instead
  of marker-wrapping the upstream block — keeps the managed surface to
  the location block and makes re-render over an older render safe.
- D-5: `verify()` checks the upstream block on the whole text rather
  than the server text because the block intentionally lives outside the
  server block; uniqueness (exactly one match) guards duplicates.
- D-6: `tests/test_sea_speed_auth_v1.py` gets no edit: its ~:50
  `proxy_pass http://127.0.0.1:18889/cam1/;` sits inside the legacy
  `SEA-SPEED-CAM1-DIRECT-H264-*` input fixture that the renderer
  consumes; the full-suite run proves no rendered-output pin in that
  file depends on the old direct proxy_pass.

## Affected contours

- VPS nginx config rendering only: `scripts/operations/nginx_cam1_direct_h264.py`,
  `tests/test_camera1_direct_h264_cutover.py`, this SDD trio, and the
  durable progress file outside the repo tree.
- No change to `api/`, `deploy/`, `.github/`, frontend, worker, or the
  auth renderer (`nginx_sea_speed_auth.py`); the docs page
  `docs/operations/CAMERA1_DIRECT_H264_CUTOVER.md` is untouched (its
  content pin still passes; see Correct-course).
- Production effect after the next deploy: NGINX reuses up to 8 idle
  keepalive connections per worker to 127.0.0.1:18889 instead of opening
  one connection per proxied request.

## Validation

- Full suite on head: `python3 -m pytest tests/ -q` → 777 passed,
  4 skipped, 119 subtests passed (baseline counts preserved).
- Renderer CLI: `render` → `CAM1_PROTECTED_H264_RENDER=PASS`; `verify` →
  `CAM1_PROTECTED_H264_CONFIG=PASS`.
- Negative verification: verify() raises ConfigError for missing upstream
  block, missing `keepalive 8;`, missing `Connection ""` header and
  legacy direct `proxy_pass` — NEGATIVE-VERIFY=PASS.
- ruff (`scripts/quality/ruff.toml`) on the changed Python files: All
  checks passed!
- `bash -n`: no shell files changed in this task — not applicable.
- `python3 scripts/ci/validate_sdd.py`: green (see tasks.md).

## Runtime feedback

- RF-001: Operator actions expected: 0 — the next VPS deploy renders the
  config through this script; `nginx -t` in the deploy path gates reload.
- RF-002: Failure evidence: `ConfigError` messages from `verify()`
  (missing upstream block / directive / header), and the
  `CAM1_PROTECTED_H264_*` CLI PASS markers; a failing verify aborts
  render() before any output is written.

## Risk profile

- Risk profile: NOT REQUIRED
- Risk-profile rationale: derived NOT REQUIRED by the PR Change Contract
  (CONTROL_PLANE impact, security NONE, schema NONE, no destructive
  migration); the formal risk register is therefore omitted per policy,
  and the renderer-side mitigations below stay in force regardless.
- Informative risk analysis (prose, no formal register): (1) a malformed
  or duplicated upstream block could break the Camera 1 path or the whole
  nginx reload — mitigated by emitting the upstream block only from the
  managed renderer immediately before the managed server block (http-level
  in real trees), stripping any previously emitted same-name block before
  re-inserting (renders can never accumulate duplicates), and verify()
  failing loudly on missing/duplicated upstream or missing
  keepalive/Connection directives at the end of every render(); the
  deploy-side nginx -t gate is unchanged. (2) per-request proxying
  regression (keepalive not engaged) — mitigated by the updated output
  pin asserting the upstream name, `server 127.0.0.1:18889;`,
  `keepalive 8;`, pooled proxy_pass with the /cam1/ URI, HTTP/1.1 and
  `Connection ""`, plus the auth-render pipeline test proving the block
  survives the auth renderer. (3) hand-edited production config outside
  the managed markers — outside renderer scope, unchanged from before;
  the deploy-side nginx -t gate backstops. (4) keepalive pool silently
  not engaging or the /cam1/ URI rewrite suffix lost — mitigated by the
  documented NGINX keepalive prerequisites (proxy_http_version 1.1 +
  proxy_set_header Connection "") rendered alongside the upstream, and by
  pipeline tests re-running the combined auth render and the split-layout
  include pipeline (cache no-store headers and legacy-marker migration
  semantics untouched). Negative coverage observed:
  NEGATIVE-VERIFY=PASS (four loud-fail cases), 9 additional peer negative
  probes all raising precise ConfigError, test_renderer_is_idempotent,
  CLI render+verify PASS, full suite 777 passed / 4 skipped.

## Test design

- TEST-001 | Covers: upstream emission and keepalive engagement | Level: unit | Priority: P0 | Evidence: test_renderer_moves_cam1_under_sea_speed_and_preserves_h264_upstream asserts upstream sea_speed_cam1_hls {, server 127.0.0.1:18889;, keepalive 8;, proxy_pass http://sea_speed_cam1_hls/cam1/;, proxy_http_version 1.1, proxy_set_header Connection ""
- TEST-002 | Covers: loud verify negative coverage | Level: unit | Priority: P0 | Evidence: NEGATIVE-VERIFY=PASS — verify() raises ConfigError for: missing upstream block, missing keepalive 8, missing Connection "" header, legacy direct proxy_pass (session transcript)
- TEST-003 | Covers: idempotent render | Level: unit | Priority: P0 | Evidence: test_renderer_is_idempotent (byte-identical re-render) + CLI render/verify PASS on a fresh fixture (CAM1_PROTECTED_H264_RENDER=PASS, CAM1_PROTECTED_H264_CONFIG=PASS)
- TEST-004 | Covers: auth-render pipeline compatibility | Level: integration | Priority: P0 | Evidence: test_combined_auth_render_protects_new_cam1_and_retires_all_cams + test_sea_speed_auth_v1 split-layout include pipeline (invokes the cam renderer render CLI, then auth render + both verifies)
- Regression: full suite 777 passed / 4 skipped / 119 subtests; ruff clean on changed files; no shell files changed (bash -n not applicable).

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE
- Correct-course note: the pin audit found two renderer-adjacent pins
  outside the edit set and both are recorded here instead of widening
  scope: tests/test_sea_speed_auth_v1.py ~:50 is a legacy *input*
  fixture line (not a rendered-output expectation — full suite green
  with the file untouched), and tests/test_camera1_direct_h264_cutover.py:148
  pins docs/operations/CAMERA1_DIRECT_H264_CUTOVER.md, which this task
  does not modify, so the assertion still passes unchanged.
