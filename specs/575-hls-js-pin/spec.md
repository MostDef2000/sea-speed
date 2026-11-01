# Spec: #575 — pin hls.js to the production-proven 1.5.7 artifact with SRI

- Issue: #575
- Specification: specs/575-hls-js-pin/spec.md
- Authorization: the #575 scope (three frontend pages + the frontend contract
  test + this trio; audit #534 section P2-07) admitted by the delivery
  orchestrator; base 871cc50 (branch fix/575-hls-js-pin).

## Product outcome

All three operator pages (water `/`, cameras `/cameras/`, road `/road/`) load
hls.js from the production-proven pinned artifact
`https://cdn.jsdelivr.net/npm/hls.js@1.5.7/dist/hls.min.js` with Subresource
Integrity (`integrity="sha384-1B+J55elPxu+trIhW7QThjZg3evX8C5P6zjB82Xnn46RKPAXpL+vkanRSjCidsJv"`,
`crossorigin="anonymous"` — jsdelivr serves CORS headers). The floating
`@latest` tag disappears from the water and cameras pages (it could serve any
future hls.js major, including breaking releases, with no integrity check);
the road page — already pinned to the same artifact — gains the same
integrity/crossorigin attributes. The frontend contract test pins the exact
src, integrity and crossorigin per page and guards against any `@latest`
hls.js tag returning.

## User scenarios

- SC-1: an operator opens any of the three pages — the browser fetches the
  exact 1.5.7 artifact, verifies its sha384 hash, and HLS playback works
  exactly as on the road page today (same artifact, already production-proven).
- SC-2: a compromised or breaking-change CDN response under
  `hls.js@latest` can no longer reach the water/cameras pages: the tag is
  gone, and any reintroduction fails the contract test.
- SC-3: a developer bumps or edits the hls.js script tag — any drift from the
  pinned URL, the exact integrity value or `crossorigin="anonymous"` fails
  `tests/test_frontend_contract.py` with the page and attribute named.

## Acceptance criteria

- AC-001: water and cameras pages load hls.js from the exact pinned 1.5.7
  `/dist/hls.min.js` URL with the exact sha384 integrity and
  `crossorigin="anonymous"`; the road page carries the same two attributes on
  its existing pinned tag.
- AC-002: no operator page loads hls.js from a `@latest` tag (structural
  guard over all three pages).
- AC-003: focused contract run, full battery, ruff and validate_sdd all green
  with the battery delta accounted (+2 methods, +6 subtests).

## Requirements

- R-1: `frontend/sea-speed/index.html` and `frontend/sea-speed/cameras/index.html`
  replace `hls.js@latest` with the pinned URL
  `https://cdn.jsdelivr.net/npm/hls.js@1.5.7/dist/hls.min.js` plus
  `integrity="sha384-1B+J55elPxu+trIhW7QThjZg3evX8C5P6zjB82Xnn46RKPAXpL+vkanRSjCidsJv"`
  and `crossorigin="anonymous"`; `frontend/sea-speed/road/index.html` keeps
  its URL and gains the same two attributes. The explicit `/dist/hls.min.js`
  path form is used everywhere (same as road today).
- R-2: `tests/test_frontend_contract.py` adds structured SS pins (attribute
  maps extracted from `<script ...>` tags on comment-stripped source, matching
  the file's existing regex-extraction style — no raw-substring pins): per
  page, the single hls.js tag's `src` equals the pinned URL exactly,
  `integrity` equals the exact sha384 value and `crossorigin` equals
  `anonymous`; plus one guard that no hls script tag on any of the three
  pages uses `@latest`.
- R-3: the SDD trio `specs/575-hls-js-pin/{spec,plan,tasks}.md` is created;
  no other files change.

## Runtime feedback

- RF-001: Operator actions expected: 0 — frontend static assets ride the
  normal VPS release contour (release contour; no dedicated deploy, no
  manual step). Runtime acceptance = exact-head CI green on the merge PR,
  then the standard post-deploy probe: the three pages load and HLS playback
  starts (the browser verifies the SRI hash natively; a hash mismatch would
  block the script and surface as no playback, caught by the probe).
- RF-002: the pinned artifact is byte-identical to what the road page already
  serves in production — no new third-party code is introduced; the water and
  cameras pages stop tracking the moving `@latest` tag.

## NFR assessment

- NFR-001 | Area: supply-chain integrity | Target: every operator page loads hls.js only from the pinned 1.5.7 artifact with a valid sha384 SRI and CORS-anonymous request | Validation: tests/test_frontend_contract.py::HlsScriptPinTests (structured attribute pins per page + @latest guard) | Evidence: focused pytest run 25 passed + 6 subtests; integrity value cross-checked against the jsdelivr registry record (sha256 match) during recon | Status: PASS
- NFR-002 | Area: performance | Target: no runtime cost beyond the browser's native SRI verification; artifact identical to the road page's proven 1.5.7 build | Validation: same URL already served in production on /sea-speed/road/ | Evidence: road page has served the pinned artifact since its release without playback regressions | Status: PASS
