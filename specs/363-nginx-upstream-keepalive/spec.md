# Spec: NGINX upstream keepalive for Camera 1 HLS

- Issue: #363
- Specification: specs/363-nginx-upstream-keepalive/spec.md

## Product outcome

Browser hls.js traffic for Camera 1 (`/sea-speed/media/cam1/` playlist
refreshes plus segment GETs) is proxied by NGINX to the MediaMTX HLS
listener at `127.0.0.1:18889`. The renderer
`scripts/operations/nginx_cam1_direct_h264.py` emitted a managed location
block with a direct `proxy_pass http://127.0.0.1:18889/cam1/;` and no
upstream connection reuse, so every proxied request opened a fresh
loopback connection and left a TIME-WAIT socket behind (~750 sockets of
churn observed on the VPS).

This change makes the rendered config declare a pooled upstream and
proxy through it:

```nginx
upstream sea_speed_cam1_hls {
    server 127.0.0.1:18889;
    keepalive 8;
}
```

with the managed location switched to
`proxy_pass http://sea_speed_cam1_hls/cam1/;`, `proxy_http_version 1.1;`
and `proxy_set_header Connection "";` — the documented NGINX keepalive
requirements — so upstream connections are pooled and reused instead of
torn down per request.

## User scenarios

- US-1: An operator renders the Camera 1 protected-H264 block for the
  mostdef.ru server; the output contains the `sea_speed_cam1_hls`
  upstream block (loopback backend, `keepalive 8`) and the managed
  location proxies through the named upstream with HTTP/1.1 and an empty
  `Connection` header.
- US-2: An operator runs `verify` against a rendered config that is
  missing the upstream block, the `keepalive 8;` directive or the
  `proxy_set_header Connection "";` header (or still carries the legacy
  direct `proxy_pass`); verification fails loudly with an explicit
  `ConfigError` naming the missing element instead of passing silently.
- US-3: The renderer is run twice over the same tree; the second run is
  a byte-identical no-op, and re-rendering over a previously rendered
  config never accumulates a duplicate `upstream` block.
- US-4: The auth cutover pipeline (cam renderer → auth renderer) keeps
  working end to end: the added upstream block does not confuse the auth
  renderer's server/location scanning or its verification.

## Scope

- `scripts/operations/nginx_cam1_direct_h264.py`: upstream block
  rendering, `proxy_pass` switch to the named upstream, keepalive
  directives in the managed location, idempotent upstream removal, and
  `verify()` hardening.
- `tests/test_camera1_direct_h264_cutover.py`: rendered-config pin
  updated to the new canonical render (and strengthened with the new
  directives).
- `tests/test_sea_speed_auth_v1.py`: audited; its ~:50 `proxy_pass
  http://127.0.0.1:18889/cam1/;` line is the legacy *input* fixture that
  the renderer converts (not a rendered-output expectation), so it is
  intentionally unchanged — confirmed by the full-suite run.
- SDD: this trio (`specs/363-nginx-upstream-keepalive/`).

Out of scope (forbidden paths): `api/**`, `deploy/**`, `.github/**`, all
other scripts/tests, and `docs/operations/CAMERA1_DIRECT_H264_CUTOVER.md`
(its renderer-adjacent content pin in
`tests/test_camera1_direct_h264_cutover.py:148` still passes because the
doc is unchanged; recorded in plan.md Correct-course).

## Requirements

- R-1: The rendered config declares exactly one
  `upstream sea_speed_cam1_hls { server 127.0.0.1:18889; keepalive 8; }`
  block, inserted immediately before the managed `mostdef.ru` server
  block (inside the enclosing `http{}` context in real configs), and
  re-rendering removes any previously emitted block with that name
  before inserting (idempotency, no duplicates).
- R-2: The managed `location ^~ /sea-speed/media/cam1/` block proxies to
  `http://sea_speed_cam1_hls/cam1/` (preserving the `/cam1/` URI rewrite
  suffix) and carries `proxy_http_version 1.1;` plus
  `proxy_set_header Connection "";` alongside the existing
  `proxy_buffering off;` / `proxy_cache off;` no-store directives.
- R-3: `verify(text, host)` stays deterministic and self-contained and
  fails loudly (`ConfigError`) when: the `sea_speed_cam1_hls` upstream
  block is missing or duplicated; its body lacks
  `server 127.0.0.1:18889;` or `keepalive 8;`; the managed block lacks
  `proxy_pass http://sea_speed_cam1_hls/cam1/;`,
  `proxy_http_version 1.1;` or `proxy_set_header Connection "";`.
- R-4: Test pins of this renderer are synchronized: the cutover test
  asserts the new canonical render; the whole `tests/` and `scripts/`
  trees are audited for other content pins of this renderer and none of
  them regress.

## Acceptance criteria

- AC-001: Rendered config contains the `upstream sea_speed_cam1_hls`
  block with `server 127.0.0.1:18889;` and `keepalive 8;`.
- AC-002: The managed Camera 1 location uses
  `proxy_pass http://sea_speed_cam1_hls/cam1/;` with
  `proxy_http_version 1.1;` and `proxy_set_header Connection "";`.
- AC-003: `verify()` raises `ConfigError` for each of: missing upstream
  block, missing `keepalive 8;`, missing `Connection ""` header, legacy
  direct `proxy_pass` — deterministic, no external state.
- AC-004: Rendering is idempotent over its own output (byte-identical)
  and the CLI `render`/`verify` entry point passes on a fresh fixture.
- AC-005: Full test suite green with updated pins; ruff clean on changed
  Python files; no other pin of this renderer broken.

## Runtime feedback

- RF-001: Operator actions expected: 0 — the config is rendered by the
  existing deploy pipeline; the deploy-side `nginx -t` gate remains the
  final syntax gate before reload.
- RF-002: Failure evidence: `ConfigError` messages from `verify()` (and
  the `CAM1_PROTECTED_H264_CONFIG=PASS` line on success); a malformed
  render can never reach reload silently because verify() runs at the
  end of every `render()` call.

## NFR assessment

- NFR-001 | Area: performance | Target: loopback upstream connections to MediaMTX are pooled and reused (keepalive 8, HTTP/1.1, empty Connection header), eliminating the per-request TIME-WAIT churn (~750 sockets) | Validation: rendered-config assertions for the upstream block, keepalive 8, proxy_http_version 1.1 and proxy_set_header Connection "" in the cutover suite | Evidence: test_renderer_moves_cam1_under_sea_speed_and_preserves_h264_upstream | Status: PASS
- NFR-002 | Area: reliability | Target: rendered nginx config stays structurally valid — exactly one upstream block, no duplicate accumulation across re-renders, byte-identical idempotent output | Validation: idempotency test + CLI render/verify on a fresh fixture + _remove_upstream re-render path | Evidence: test_renderer_is_idempotent, CAM1_PROTECTED_H264_RENDER=PASS / CAM1_PROTECTED_H264_CONFIG=PASS transcript | Status: PASS
- NFR-003 | Area: security | Target: backend remains loopback-only (127.0.0.1:18889); managed block still refuses Basic Auth and MediaMTX naming; auth cutover pipeline unchanged | Validation: verify() legacy checks retained + combined auth render test + split-layout include pipeline test | Evidence: test_combined_auth_render_protects_new_cam1_and_retires_all_cams, test_sea_speed_auth_v1 pipeline tests | Status: PASS
- NFR-004 | Area: observability | Target: verification failures name the exact missing element (upstream block, keepalive, Connection header, proxy_pass) with no external state or randomness | Validation: four negative verify cases each raise the expected ConfigError | Evidence: NEGATIVE-VERIFY=PASS session transcript (no upstream block / no keepalive 8 / no Connection header / legacy direct proxy_pass) | Status: PASS
- NFR-005 | Area: compatibility | Target: hls.js contract unchanged — same `/cam1/` path rewrite, same no-store cache headers, same legacy-marker migration behavior; no other rendered-output pin of the renderer breaks | Evidence: full suite 777 passed / 4 skipped / 119 subtests including the split-layout pipeline that invokes the cam renderer via CLI | Validation: full pytest run + pin audit (tests/ + scripts/) | Status: PASS
