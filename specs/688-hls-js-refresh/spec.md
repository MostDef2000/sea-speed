# Spec: #688 — refresh hls.js to 1.7.4 with verified Subresource Integrity

- Issue: #688
- Specification: specs/688-hls-js-refresh/spec.md
- Authorization: issue #688 scope admitted by the delivery orchestrator
  (branch `agent/wave7-688-685`, base `92561a5d8cda9b85734743778709098826ba21ec`).
  This worker owns the production HTML change (`frontend/sea-speed/index.html`,
  `frontend/sea-speed/road/index.html`, `frontend/sea-speed/cameras/index.html`)
  and this SDD trio; test updates are owned by a separate test worker
  (`tests/test_688_hls_pin.py` (new), plus updates to
  `tests/test_frontend_contract.py`, `tests/test_665_water_page_assets.py`,
  `tests/browser/fixture-server.mjs`, `tests/browser/operator-pages.spec.mjs`).

## Product outcome

All three operator pages (water `/sea-speed/water/`, cameras
`/sea-speed/cameras/`, road `/sea-speed/road/`) load hls.js from the
current non-prerelease release `1.7.4` instead of the aging `1.5.7` pin,
still with Subresource Integrity (`sha384`) and
`crossorigin="anonymous"`. The script tag keeps every other attribute and
its document position byte-identical; only the version in the URL and the
integrity digest change.

This is **preventive maintenance**, not an incident response: no CVE is
claimed for the current 1.5.7 pin by this change. The refresh keeps the
pinned third-party player on a maintained release line, keeps SRI mandatory,
and leaves the player configuration, CSP, streaming and deployment contours
untouched.

## Candidate rationale

- `hls.js@1.7.4` was the npm registry `latest` non-prerelease dist-tag at
  analysis time (published 2026-10-28); the current pin is `1.5.7`.
- Candidate selection criterion: newest stable release whose `/dist/hls.min.js`
  artifact can be byte-verified end to end (CDN ↔ npm tarball ↔ published
  registry integrity) and whose public API surface covers every call the
  three players make.
- The change is intentionally a version bump only. No API migration, no
  option retuning, no player code change.

## Byte-verification procedure and observed results

Procedure (performed by the orchestrator during admission, restated here as
the reproducible acceptance evidence):

1. Download the pinned CDN artifact
   `https://cdn.jsdelivr.net/npm/hls.js@1.7.4/dist/hls.min.js` twice through
   the sandbox proxy; compare the two downloads.
2. Download the npm tarball
   `https://registry.npmjs.org/hls.js/-/hls.js-1.7.4.tgz`; compute its
   `sha512` digest and compare against the registry-published
   `dist.integrity` for 1.7.4.
3. Extract `package/dist/hls.min.js` from the tarball and compare it
   byte-for-byte with both CDN downloads.
4. Compute `sha384` over those exact bytes for the `integrity` attribute.

Observed results:

- CDN download twice: **623 915 bytes** each, byte-identical (`cmp` OK).
- npm tarball `sha512`:
  `3GlxGdPvT2YHvQYOt+yOzT/DEior/qJVNIylHA77kgeoBTdQQqi70GwefNEUmHQeNGyjC8U62+bruqW/Tpm+tg==`
  — matches the registry-published `dist.integrity` **exactly**.
- Extracted `package/dist/hls.min.js` is byte-identical to both CDN
  downloads.
- Computed SRI (`sha384`) from those exact bytes:
  `sha384-p9vgU/7IYJWd3I4STrtqxqR/2cAQlhIX7D/HrTnIMEjjcUox165b7se7sxmm3zDg`

## API compatibility check

Every hls.js symbol/option used by the three players is present in 1.7.4
(orchestrator-verified by grep of the exact 1.7.4 CDN bytes):

`playingDate`, `enableWorker`, `lowLatencyMode`, `backBufferLength`,
`maxBufferLength`, `liveSyncDurationCount`, `liveMaxLatencyDurationCount`,
`recoverMediaError`, `attachMedia`, `loadSource`, `startLoad`,
`Events.MANIFEST_PARSED`, `Events.ERROR`, `Hls.isSupported`,
`Hls.Events.MEDIA_ATTACHED`, `Hls.ErrorTypes.NETWORK_ERROR`,
`Hls.ErrorTypes.MEDIA_ERROR`, `hls.destroy`, `hls.latency`, `hls.media`.

No removed or renamed API affects the player code; the tag swap is the whole
change.

## User scenarios

- SC-1: an operator opens any of the three pages — the browser fetches the
  pinned 1.7.4 artifact, verifies its sha384 digest natively, and HLS
  playback behaves as before the refresh.
- SC-2: a tampered or corrupted CDN response is rejected browser-side by SRI;
  the page does not execute unverified third-party code.
- SC-3: a developer edits one of the three script tags — any drift from the
  pinned 1.7.4 URL, the exact sha384 digest, `crossorigin="anonymous"` or the
  per-page tag identity is detectable by the frontend contract test owned by
  the test worker.

### Gherkin acceptance examples

```gherkin
Feature: hls.js 1.7.4 refresh with verified SRI on every operator page

  Rule: Every operator page loads the same verified 1.7.4 artifact

    Scenario: Water page loads the pinned artifact
      Given the water operator page at /sea-speed/water/
      When the browser parses the page
      Then the hls.js script tag src is "https://cdn.jsdelivr.net/npm/hls.js@1.7.4/dist/hls.min.js"
      And its integrity is "sha384-p9vgU/7IYJWd3I4STrtqxqR/2cAQlhIX7D/HrTnIMEjjcUox165b7se7sxmm3zDg"
      And its crossorigin is "anonymous"

    Scenario: Road and cameras pages load the identical tag
      Given the road page at /sea-speed/road/ and the cameras page at /sea-speed/cameras/
      When the three hls.js script tags are compared
      Then all three tags are identical apart from leading indentation

  Rule: The refresh is a version bump only

    Scenario: No other page attribute or player option changes
      Given the pre-refresh tag with every attribute except version and integrity
      When the refresh is applied
      Then only the version segment of src and the integrity value differ
      And crossorigin="anonymous" and the tag position are unchanged

  Rule: SRI protects the runtime

    Scenario: A corrupted CDN response is refused
      Given a CDN response whose bytes do not match the pinned sha384 digest
      When the browser loads the page
      Then the script is blocked by Subresource Integrity and HLS does not start

  Rule: Real playback is verified outside this sandbox

    Scenario: Operator playback probe after the VPS deploy
      Given the refreshed pages are live on the VPS
      When an operator opens /sea-speed/water/, /sea-speed/road/ and /sea-speed/cameras/
      Then each page starts live playback for its assigned public cameras
      And cam1 and road1 are observed playing without SRI or player errors
```

## Acceptance criteria

- AC-001: the water, road and cameras pages load hls.js from exactly
  `https://cdn.jsdelivr.net/npm/hls.js@1.7.4/dist/hls.min.js` with
  `integrity="sha384-p9vgU/7IYJWd3I4STrtqxqR/2cAQlhIX7D/HrTnIMEjjcUox165b7se7sxmm3zDg"`
  and `crossorigin="anonymous"`; every other attribute and the tag position
  are unchanged.
- AC-002: after the change the three hls.js script tags are identical to each
  other apart from leading indentation, and no `hls.js@1.5.7` reference
  remains in the three pages.
- AC-003: the SDD trio `specs/688-hls-js-refresh/{spec,plan,tasks}.md` exists
  with the verification evidence, `python3 scripts/ci/validate_sdd.py` passes,
  and the changed-file set stays inside the admitted paths (three HTML pages
  plus this trio).
- AC-004: real authenticated playback is confirmed on all three pages with
  public cam1 and road1 — **RUNTIME-MANUAL**, not verifiable in this sandbox.

## Requirements

- R-1: replace only the version and integrity inside the three existing
  hls.js `<script>` tags; keep tag order, `crossorigin="anonymous"` and every
  other attribute byte-identical. The resulting tag is
  `<script src="https://cdn.jsdelivr.net/npm/hls.js@1.7.4/dist/hls.min.js" integrity="sha384-p9vgU/7IYJWd3I4STrtqxqR/2cAQlhIX7D/HrTnIMEjjcUox165b7se7sxmm3zDg" crossorigin="anonymous"></script>`.
- R-2: no CSP change, no player configuration change, no ffmpeg/streaming
  change, no retroactive edit to the #575/#665/#675 artifacts. Production HTML
  is owned by this worker; test updates are owned by the separate test worker
  (`tests/test_688_hls_pin.py` new, plus `tests/test_frontend_contract.py`,
  `tests/test_665_water_page_assets.py`, `tests/browser/fixture-server.mjs`,
  `tests/browser/operator-pages.spec.mjs`).
- R-3: record the version-refresh rationale, the byte-verification evidence,
  the API compatibility review, and the runtime-manual acceptance in this
  SDD trio.

## Runtime feedback

- RF-001: Operator actions expected: 0 at merge time — frontend static assets
  ride the normal VPS release contour; no dedicated manual deploy step.
  Runtime acceptance is RUNTIME-MANUAL after the deploy: open
  `/sea-speed/water/`, `/sea-speed/road/` and `/sea-speed/cameras/` and
  confirm live playback for cam1 and road1 with no SRI or hls.js error.
- RF-002: private authenticated live streams cannot be exercised inside this
  sandbox, so the orchestrator records playback as pending rather than
  claiming it.

## NFR assessment

- NFR-001 | Area: supply-chain integrity | Target: every operator page loads hls.js only from the pinned 1.7.4 artifact with a valid sha384 SRI and a CORS-anonymous request | Validation: SRI digest computed from bytes that match the npm tarball and the registry-published sha512; orchestrator byte-verification procedure above; test worker's frontend contract pins (separate ownership) | Evidence: 623 915-byte CDN artifact downloaded twice byte-identical; npm tarball sha512 equals published dist.integrity; sha384-p9vgU/7IYJWd3I4STrtqxqR/2cAQlhIX7D/HrTnIMEjjcUox165b7se7sxmm3zDg | Status: PASS
- NFR-002 | Area: compatibility | Target: no player-code change is needed because every hls.js API/option in use exists in 1.7.4 | Validation: API compatibility review in this spec (grep of the exact 1.7.4 CDN bytes) | Evidence: playingDate, enableWorker, lowLatencyMode, backBufferLength, maxBufferLength, liveSyncDurationCount, liveMaxLatencyDurationCount, recoverMediaError, attachMedia, loadSource, startLoad, MANIFEST_PARSED, ERROR, Hls.isSupported, Hls.Events.MEDIA_ATTACHED, Hls.ErrorTypes.NETWORK_ERROR, Hls.ErrorTypes.MEDIA_ERROR, hls.destroy, hls.latency, hls.media all present in 1.7.4 | Status: PASS
- NFR-003 | Area: performance | Target: no runtime cost beyond the browser's native SRI verification; the served artifact stays a single minified file from the same CDN path | Validation: same `/dist/hls.min.js` path and same request mode as before | Evidence: one script tag per page, unchanged crossorigin/attributes | Status: PASS
- NFR-004 | Area: availability | Target: real authenticated playback works on all three pages after deploy | Validation: RUNTIME-MANUAL post-deploy operator probe (cam1, road1) | Evidence: pending the VPS deploy; recorded as PENDING in tasks.md | Status: CONCERNS
