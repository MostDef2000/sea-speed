# Spec: favicon for all six Sea Speed pages

- Issue: #677

## Product outcome
Every Sea Speed page — the water operator page (`frontend/sea-speed/index.html`), road (`frontend/sea-speed/road/index.html`), cameras (`frontend/sea-speed/cameras/index.html`), objects (`frontend/sea-speed/objects/index.html`), the service-unavailable page (`frontend/sea-speed/unavailable.html`) and the public landing (`frontend/root/index.html`) — carries the same inline SVG data-URI favicon `<link>` in its `<head>`, so browsers show the Sea Speed brand mark (dark-navy rounded square #041725 with cyan waves #81d5e0) instead of a missing-`/favicon.ico` default on every tab. The icon is embedded as a percent-encoded `data:image/svg+xml,` URI rather than shipped as a static file precisely so that `deploy/vps/deploy.sh` needs no change: an inline data-URI is copied with the HTML it lives in, while a favicon file would be a new deploy-script-copied asset. No page URL, script, style, or deploy path changes.

## User scenarios
- Owner opens any Sea Speed page in a browser; the tab shows the Sea Speed brand icon instead of the default blank/`/favicon.ico`-404 glyph, on all six pages identically.
- The browser makes no extra network request for the icon: the SVG is inline in the HTML (297 bytes decoded, ~450 bytes encoded per page), so the worst-case 190 KB/s pipe (issue #659 measurements) pays a one-time ~450-byte HTML increase per page and zero additional requests.
- The unavailable page and the public landing — served by different vhosts/paths than the operator pages — show the same icon, because the data-URI is self-contained and path-independent.

## Requirements
1. Each of the six pages gains exactly one line: the pinned `<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,...">` tag from `shared/sea-speed-favicon/favicon-datauri.txt` (449 bytes with trailing newline), inserted inside `<head>` immediately after the `<title>` element, on its own line, with the file's existing indentation style. The tag is byte-identical in all six pages.
2. No other line changes: no reordering, reformatting, or edits to any other element; the diff is exactly one added line per page.
3. `deploy/vps/deploy.sh` is NOT changed (the inline data-URI exists precisely to avoid touching it); no `*.js`, `api/**`, `.github/**`, or other test file changes.
4. The favicon `<link>` is pinned by a stdlib oracle test (`tests/test_677_favicon.py`, house style of `tests/test_665_water_page_assets.py` / `tests/test_626_csp_no_inline_scripts.py`) that is RED on base and GREEN after the change.

## Acceptance criteria
- AC-001: each of the six pages contains exactly one `<link>` with `rel="icon"`, `type="image/svg+xml"`, `href` starting with `data:image/svg+xml,`, placed inside `<head>`; the six hrefs are byte-identical to each other and to the shared source line. RED authenticity — the oracle fails on base cefd446 (no page has any `<link>` tag).
- AC-002: the data-URI percent-decodes to a string that parses as XML (`xml.dom.minidom.parseString`, root `<svg>`) and is ≤ 600 bytes, and the decoded SVG contains the brand colours `#041725` and `#81d5e0` (guards against a silently swapped icon).
- AC-003: diff shape — exactly one added line per page across the six HTML files, zero other modifications; `deploy/vps/deploy.sh` and all forbidden paths untouched.
- AC-004: full test battery green with the new oracle included; no existing test weakened, skipped or mocked.

## Runtime feedback
- Issue #677 (2026-11-14): none of the six pages contains any `<link>` element at all on base cefd446 (verified by grep and by the RED oracle run) — every tab renders the browser-default icon and each page view issues a doomed `/favicon.ico` request.
- The icon artwork is fixed upstream in `shared/sea-speed-favicon/favicon-datauri.txt` (single source line, 449 bytes incl. newline); this change only pins it into the pages.

## NFR assessment
- NFR-001 | Area: Security | Target: No new credentials, endpoints, files or exposure; no deploy-script or edge change | Validation: Diff review plus the oracle's byte-equality pin | Evidence: the change adds one inline `data:` URI per page — no new fetchable asset, no `deploy/vps/deploy.sh` change, no new CSP-relevant resource (data: images are not script-src material; the #626 script CSP posture is untouched) | Status: PASS
- NFR-002 | Area: Performance | Target: negligible page-weight increase and zero extra HTTP requests for the icon | Validation: decoded-SVG size cap pinned at ≤ 600 bytes in the oracle | Evidence: decoded SVG is 297 bytes; the encoded href adds ~450 bytes per page; the icon is inline so the browser issues no favicon network request | Status: PASS
- NFR-003 | Area: Maintainability | Target: one icon everywhere, drift-proof | Validation: the oracle asserts the six hrefs are byte-identical to each other and pins XML validity, size and brand colours | Evidence: tests/test_677_favicon.py (4 tests, RED on base cefd446 with 9 failures, GREEN after the change) | Status: PASS
