# Spec: #626 — sea-speed frontend: inline scripts → external files (CSP-ready)

- Issue: #626
- Specification: specs/626-csp-external-scripts/spec.md
- Authorization: commit approved (owner admission, 2026-11-09, full chain:
  refactor → tests → CI → PR → merge → VPS front deploy → edge CSP
  enforcement); base 8f409d2

## Product outcome

The sea-speed frontend pages (`/`, `/cameras/`, `/road/`,
`/unavailable.html`) carry zero inline `<script>` blocks and zero
HTML-attribute event handlers, so the edge CSP for mostdef.ru `/sea-speed*`
can flip from `Content-Security-Policy-Report-Only` to an enforcing
`Content-Security-Policy` without `unsafe-inline` in `script-src`. Page
behavior is unchanged: crossing-line editor, camera grid, road view, HLS
playback, overlay canvas and live sync work exactly as before.

## User scenarios

- SC-1: a visitor opens `/`, `/cameras/` or `/road/` — every feature
  (crossing-line editor, camera grid, road view, HLS video, overlay canvas,
  live sync) behaves identically to the pre-refactor page; external files
  are connected at the exact positions of the former inline blocks, so
  script execution order (hls.js → overlay-canvas.js → main; live-sync.js
  after the index main block) is preserved.
- SC-2: an operator flips the edge CSP from Report-Only to enforcing — the
  browser console shows no CSP violations originating from sea-speed pages
  (no inline script blocked, no attribute handler blocked).
- SC-3: the deploy pipeline copies the new external `.js` files to the VPS
  together with the existing static assets — `deploy/vps/deploy.sh` lists
  every new file.

## Requirements

- R-1: `frontend/sea-speed/index.html` — the inline block at :93-124 (IIFE
  crossing-line editor, DOM-dependent, no hls.js dependency) moves verbatim
  to `frontend/sea-speed/crossing-line.js`, connected with a `src` script
  tag at the same position (before the hls.js CDN tag); the inline block at
  :127-216 (main logic, depends on hls.js/overlay-canvas.js) moves verbatim
  to `frontend/sea-speed/main.js`, connected at the same position (after
  overlay-canvas.js, before live-sync.js).
- R-2: `frontend/sea-speed/cameras/index.html` — the inline block at :101+
  moves verbatim to `frontend/sea-speed/cameras/cameras.js`, connected at
  the same position (after the hls.js CDN tag).
- R-3: `frontend/sea-speed/road/index.html` — the inline cfg block at
  :62-72 moves verbatim to `frontend/sea-speed/road/config.js`, connected
  at the same position (before the hls.js CDN tag); the inline main block
  at :76+ moves verbatim to `frontend/sea-speed/road/main.js`, connected at
  the same position (after overlay-canvas.js).
- R-4: `frontend/sea-speed/unavailable.html` — the single HTML-attribute
  handler `<button onclick="location.reload()">` (:19) becomes an id'd
  button plus `addEventListener('click', ...)` in a new external
  `frontend/sea-speed/unavailable.js`, connected before `</body>`.
- R-5: `deploy/vps/deploy.sh` — the front copy list gains every new `.js`
  file (crossing-line.js, main.js, cameras/cameras.js, road/config.js,
  road/main.js, unavailable.js).
- R-6: `tests/test_626_csp_no_inline_scripts.py` — guard oracle: for each of
  the four HTML files, no `<script>` tag without a `src` attribute and no
  `on[a-z]+=` attribute handlers; every new `.js` file exists and is
  non-empty; `deploy/vps/deploy.sh` references every new `.js` filename.
  RED on base 8f409d2 (inline blocks present), GREEN after the refactor.
- R-7: existing tests and renderer scripts stay byte-untouched:
  `tests/test_589_security_headers_renderer.py`,
  `tests/test_618_basic_auth_hsts.py`,
  `tests/test_sea_speed_edge_vhost_renderer.py`,
  `scripts/operations/nginx_sea_speed_auth.py`.
- R-8: JS-assigned handlers (`.onclick = ...`) inside the moved code stay
  as-is — CSP does not block JS property assignment, only HTML attributes
  and inline blocks.

## Acceptance criteria

- AC-001: the four HTML files contain no inline script blocks (every
  `<script>` tag carries `src=`) and no `on*=` attribute handlers.
- AC-002: the six new external `.js` files carry the exact former inline
  code (verbatim move, no logic edits); script connection order preserved.
- AC-003: `deploy/vps/deploy.sh` copies all six new `.js` files.
- AC-004: the guard test is RED on base 8f409d2 and GREEN after the
  refactor (test file byte-identical through the fix).
- AC-005: full battery green; frozen renderer oracles byte-unchanged.

## Runtime feedback

- RF-001: production effect requires the VPS front deploy (deploy-vps.yml,
  VPS impact) after merge, then the edge CSP flip from Report-Only to
  enforcing (lane B, separate operation with its own gates) — both out of
  scope for this refactor's code, covered by the authorized chain.
- RF-002: strictly mechanical extraction — no logic changes inside the
  moved code; the moved files keep their DOM-dependent initialization
  order.

## NFR assessment

- NFR-001 | Area: security / CSP readiness | Target: zero inline script blocks and zero on* attributes in the four HTML files, so edge script-src can drop `unsafe-inline` | Validation: tests/test_626_csp_no_inline_scripts.py (RED on base 8f409d2, GREEN after) | Evidence: focused run recorded in plan.md | Status: PASS
- NFR-002 | Area: behavior preservation | Target: verbatim code move, connection order preserved, no logic edits in moved code | Validation: diff inspection (moved blocks byte-identical modulo extraction) + full battery green | Evidence: diff inspection recorded in plan.md | Status: PASS
- NFR-003 | Area: deploy completeness | Target: every new `.js` reaches the VPS through deploy.sh | Validation: guard test asserting deploy.sh references each new file | Evidence: guard test | Status: PASS
