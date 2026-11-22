# Tasks — Issue #688 hls.js 1.7.4 refresh with verified SRI

- Issue: #688
- Specification: specs/688-hls-js-refresh/spec.md

## Delivery tasks

- T-1: `frontend/sea-speed/index.html` (water `/sea-speed/water/`) — replace
  only the version and integrity in the single hls.js script tag with
  `hls.js@1.7.4` and
  `sha384-p9vgU/7IYJWd3I4STrtqxqR/2cAQlhIX7D/HrTnIMEjjcUox165b7se7sxmm3zDg`;
  keep every other attribute and the tag position. DONE.
- T-2: `frontend/sea-speed/road/index.html` (`/sea-speed/road/`) — same
  version/integrity replacement, preserving tag order and attributes. DONE.
- T-3: `frontend/sea-speed/cameras/index.html` (`/sea-speed/cameras/`) — same
  replacement, preserving its two-space indentation and attributes. DONE.
- T-4: this SDD trio — record rationale, byte verification, API compatibility,
  Gherkin, traceability and runtime-manual acceptance. DONE.
- Tests: owned by the separate test worker — `tests/test_688_hls_pin.py` (new)
  plus updates to `tests/test_frontend_contract.py`,
  `tests/test_665_water_page_assets.py`, `tests/browser/fixture-server.mjs`,
  `tests/browser/operator-pages.spec.mjs`. Not edited here.

## Completion gate

Observed during this implementation (no tests written by this worker):

- Before → after script tags:
  - water `frontend/sea-speed/index.html:106`: `hls.js@1.5.7` + integrity
    `sha384-1B+J55elPxu+trIhW7QThjZg3evX8C5P6zjB82Xnn46RKPAXpL+vkanRSjCidsJv`
    → `hls.js@1.7.4` +
    `sha384-p9vgU/7IYJWd3I4STrtqxqR/2cAQlhIX7D/HrTnIMEjjcUox165b7se7sxmm3zDg`
  - road `frontend/sea-speed/road/index.html:67`: same before → after change.
  - cameras `frontend/sea-speed/cameras/index.html:97`: same before → after
    change (two-space indentation preserved).
- The three tags normalize to one identical line — OBSERVED:
  `sort | uniq -c` over the three grep hits printed
  `3 <script src="https://cdn.jsdelivr.net/npm/hls.js@1.7.4/dist/hls.min.js" integrity="sha384-p9vgU/7IYJWd3I4STrtqxqR/2cAQlhIX7D/HrTnIMEjjcUox165b7se7sxmm3zDg" crossorigin="anonymous"></script>`.
- `python3 scripts/ci/validate_sdd.py` — OBSERVED: `Sea Speed SDD validation
  passed` (exit 0).
- SDD delivery-quality layer checked directly against the trio (NFR, risk, test
  design, correct-course, deployment transaction audit, traceability, DoD) —
  OBSERVED: `feature quality layer OK`.
- `git status --short` — OBSERVED:
  `M frontend/sea-speed/cameras/index.html`, `M frontend/sea-speed/index.html`,
  `M frontend/sea-speed/road/index.html`, `?? specs/688-hls-js-refresh/`.
- `git diff --stat` (tracked files) — OBSERVED: 3 files changed, 3 insertions(+),
  3 deletions(-); only the three HTML pages.

Runtime acceptance: PENDING (RUNTIME-MANUAL) — requires the VPS deploy and
private authenticated streams; no playback result is claimed here.

SRI-refusal Gherkin scenario (spec.md "A corrupted CDN response is refused"):
MANUAL / not automated. The browser fixture (`tests/browser/fixture-server.mjs`)
serves a local hls.js stub with a null integrity attribute, so a corrupted-CDN
SRI refusal has no executable check; native browser SRI enforcement is the only
verification and is exercised only by a real CDN mismatch. No test is invented
for it.

## Requirements traceability

- AC-001 | Task: T-1+T-2+T-3 | Evidence: direct byte inspection of the three pages (completion gate) plus the test worker's pins — `tests/test_688_hls_pin.py` and the updated `tests/test_frontend_contract.py` assert the 1.7.4 src, exact sha384 integrity and `crossorigin="anonymous"` per page | Coverage: COVERED
- AC-002 | Task: T-1+T-2+T-3 | Evidence: normalized tag extraction yields three identical hls.js tags; no `hls.js@1.5.7` remains in the three pages (completion gate), reinforced by the updated pin tests in `tests/test_frontend_contract.py` and `tests/test_688_hls_pin.py` (and the updated browser fixtures `tests/browser/fixture-server.mjs`, `tests/browser/operator-pages.spec.mjs`) | Coverage: COVERED
- AC-003 | Task: T-4 | Evidence: SDD trio created; `python3 scripts/ci/validate_sdd.py` passes; `git status --short` / `git diff --stat` list only the three HTML pages and this trio (completion gate) | Coverage: COVERED
- AC-004 | Task: post-deploy operator probe | Evidence: `/sea-speed/water/`, `/sea-speed/road/`, `/sea-speed/cameras/` — cam1 and road1 live playback with no SRI or hls.js error | Coverage: RUNTIME-MANUAL | Reason: requires the VPS deploy and private authenticated live streams, which cannot be exercised in this sandbox

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (three HTML pages + this SDD trio)
- [x] Required tests and evidence complete (tests owned by a separate worker; markup evidence recorded here)
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (VPS deploy required for runtime acceptance)
- [ ] Runtime acceptance resolved (RUNTIME-MANUAL — cam1 and road1 playback pending the deploy)
- [x] Deferred work recorded (runtime playback probe deferred to the post-deploy operator check)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
