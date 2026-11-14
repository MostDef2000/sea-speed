# Plan: favicon for all six Sea Speed pages

- Spec: specs/677-favicon/spec.md

## Architecture
Pure-markup change with a pinning oracle. The icon is a 32×32 SVG (rounded-rect brand background `#041725`, two wave strokes `#81d5e0`/`#5eead4`) percent-encoded into a single `data:image/svg+xml,` URI and carried in one `<link rel="icon" type="image/svg+xml" href="...">` tag. The tag line is read verbatim from `shared/sea-speed-favicon/favicon-datauri.txt` (449 bytes incl. newline) and inserted as exactly one new line inside each page's `<head>`, immediately after the `<title>` element, with the page's own indentation (zero-indent for `frontend/sea-speed/index.html`, `road/index.html`, `objects/index.html`; two-space indent for `cameras/index.html`, `unavailable.html`, `frontend/root/index.html`). Because the URI is inline, no static file, no deploy-script copy step, and no cache-busting concern exists — the icon ships with the HTML it lives in. The oracle test (`tests/test_677_favicon.py`) pins presence, type, data-URI scheme, head placement, cross-page byte equality, XML validity, the ≤ 600-byte decoded cap and the brand colours.

## Decisions
- Inline data-URI instead of a favicon file: a file (`/favicon.ico` or a copied `favicon.svg`) would be a new static asset that `deploy/vps/deploy.sh` must copy to the VPS — a deploy-script change and a cache/404 surface. The work order forbids touching `deploy/vps/deploy.sh`; the inline data-URI exists precisely to avoid it. Cost: ~450 bytes per HTML page, paid once per page load, zero extra requests.
- One byte-identical tag in all six pages instead of per-page variants: one icon everywhere is the brand requirement, and byte equality is mechanically checkable (the oracle compares all six hrefs and each page's inserted line against the shared source file), eliminating the main failure mode — hand-retyped percent-encoded URIs drifting between pages.
- Placement immediately after `<title>` in `<head>`: deterministic anchor present in all six pages (verified), keeps the diff to one added line, and matches the metadata-block convention the pages already use (`charset` → `viewport` → (`theme-color`/`description`) → `title`).
- Stdlib raw-text regex oracle mirroring `tests/test_665_water_page_assets.py` / `tests/test_626_csp_no_inline_scripts.py`: the pages are static HTML, so a raw-text scan is the house-proven precision/effort point; `urllib.parse.unquote` + `xml.dom.minidom.parseString` (both stdlib) cover decode/validity without new dependencies.

## Affected contours
- VPS frontend: `frontend/sea-speed/index.html`, `frontend/sea-speed/road/index.html`, `frontend/sea-speed/cameras/index.html`, `frontend/sea-speed/objects/index.html`, `frontend/sea-speed/unavailable.html`, `frontend/root/index.html` (one added `<head>` line each)
- Tests: `tests/test_677_favicon.py` (new stdlib oracle)
- SDD: `specs/677-favicon/` (spec, plan, tasks)
- Explicitly unchanged: `deploy/vps/deploy.sh` (the inline data-URI exists precisely to avoid touching it), any `*.js`, `api/**`, `.github/**`, all other tests, all other frontend files.

## Validation
- Oracle: `cd sea-speed && python3 -m pytest tests/test_677_favicon.py -v` — 4 passed, 6 subtests passed.
- RED authenticity: the oracle run on base cefd446 in a throwaway detached worktree (`/tmp/opencode/677-favicon/red`, removed after the proof) fails 9×/1 passed — every page subfails with "expected exactly one rel=icon <link>, found 0".
- Byte equality: per-page extraction of the inserted line and its href compared byte-for-byte against `shared/sea-speed-favicon/favicon-datauri.txt` — OK ×6, all hrefs identical.
- XML validity: the percent-decoded URI parses via `xml.dom.minidom.parseString` to root `<svg>`, 297 bytes (cap 600), colours `#041725`/`#81d5e0` present.
- Diff shape: `git diff --stat` — 6 files changed, 6 insertions(+), 0 deletions.
- Full battery: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` (the repo's documented runner, `.github/workflows/quality-integration.yml`) green.
- `python3 scripts/ci/validate_sdd.py` green with the new trio.

## Runtime feedback
- Issue #677 (2026-11-14): base cefd446 contains zero `<link>` elements across the six pages (grep + RED oracle run); the favicon source line in `shared/sea-speed-favicon/favicon-datauri.txt` is the single upstream artwork source.

## Risk profile
- Risk profile: NOT REQUIRED

## Test design
- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_677_favicon.py FaviconDataUriTests.test_every_page_carries_exactly_one_svg_data_uri_favicon + test_all_six_hrefs_are_byte_identical (presence, rel/type/href pins, head placement, cross-page byte equality); RED on base cefd446 (9 failed, 1 passed), GREEN after the change (4 passed, 6 subtests passed)
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_677_favicon.py test_data_uri_decodes_to_valid_compact_svg (minidom parse, root svg, ≤ 600 bytes) + test_decoded_svg_keeps_brand_colours (#041725, #81d5e0)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: git diff --stat (6 files, 6 insertions, 0 deletions) plus full-diff review — one added line per page, nothing else; forbidden paths untouched (git status)
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` green with the new oracle included; no existing test modified

## Correct-course check
- Trigger: NONE
- Issue impact: none — the work order matches issue #677 as opened (favicon on all six pages, inline data-URI, deploy script untouched)
- Specification impact: none — the spec matches the locked design (one byte-identical line per page + stdlib oracle)
- Plan impact: none — no deviation discovered during implementation
- Tasks impact: none — delivery tasks executed as written
- Authorization impact: NONE (bounded worker work order from the delivery orchestrator on branch agent/677-favicon; the orchestrator owns the Git lifecycle)
- Follow-up: none in this change; the VPS frontend redeploy that ships the icon to production happens in the authorized delivery chain after merge (lane-A, orchestrator-owned)

## Test evidence summary
- RED (base cefd446, detached worktree): `9 failed, 1 passed in 0.09s` — all six pages subfail `expected exactly one rel=icon <link>, found 0`.
- GREEN (with diff): `4 passed, 6 subtests passed in 0.03s`.
- Byte equality: OK ×6 (`href_equal=True, line_byte_equal=True` per page), all hrefs identical.
- XML: root `<svg>`, 297 bytes decoded, `#041725`/`#81d5e0` present.
