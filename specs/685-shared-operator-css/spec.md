# 685 — Extract provably shared Water/Road operator CSS prefix

- Issue: #685
- Feature: 685-shared-operator-css
- Specification: specs/685-shared-operator-css/spec.md
- Risk profile: REQUIRED

## Product outcome

The Water operator page (`frontend/sea-speed/index.html`) and the Road operator
page (`frontend/sea-speed/road/index.html`) duplicate an identical, byte-for-byte
ordered prefix of base CSS rules (design tokens, reset, body, header, brand and
home-link styling). #685 extracts exactly that provably shared, ordered prefix
into one cached asset, `frontend/sea-speed/operator-common.css`, linked by both
pages with an absolute URL. Rendered output must remain identical; this is a
structural de-duplication with zero intended visual change.

The extraction is bounded precisely where the two pages diverge: the shared
prefix ends at the base `.objects-link{…}` rule (inclusive). It stops before
`.objects-link:hover,…` because Road widens that selector list with
`.objects-link.active`. Everything after that boundary — video/canvas stacking,
the 700px (Water) vs 760px (Road) breakpoints, fullscreen affordances and all
domain-specific rules — remains inline and untouched.

## User scenarios

Feature: Shared operator CSS prefix extraction

  Rule: The base operator prefix is byte-identical, in order, on both pages.

    Scenario: A Water operator page loads the shared stylesheet
      Given the Water page links `/sea-speed/operator-common.css`
      And its inline `<style>` begins at `.objects-link:hover`
      When the linked rules are prepended to the residual inline rules
      Then the resulting ordered rule sequence equals the pre-extraction page

    Scenario: A Road operator page loads the shared stylesheet
      Given the Road page links `/sea-speed/operator-common.css`
      And its inline `<style>` begins at `.objects-link:hover,…,.objects-link.active`
      When the linked rules are prepended to the residual inline rules
      Then the resulting ordered rule sequence equals the pre-extraction page
      And the `.objects-link.active` extension stays inline, not shared

  Rule: Deployment never leaves a live page referencing a missing or empty asset.

    Scenario: Upgrade installs the stylesheet before the HTML that links it
      Given a release that ships `operator-common.css`
      When the release is activated
      Then the stylesheet is moved live before the Water and Road HTML

    Scenario: Downgrade removes the stylesheet only after the HTML stops linking it
      Given a rollback to a release with no shared stylesheet
      When the release is activated
      Then the old HTML is restored first
      And the live stylesheet is removed only afterwards

  Rule: The first rollback onto a pre-#685 release is not blocked by a missing marker.

    Scenario: Pre-feature release carries neither the asset nor an `.absent` marker
      Given a release directory produced before #685 (no CSS, no marker)
      And that release's HTML does not reference `operator-common.css`
      When it is used as a rollback target
      Then it is accepted as a genuine pre-feature release
      And the live stylesheet is removed after the old HTML is restored

    Scenario: A release whose HTML references a missing or empty asset
      Given a release whose HTML links `operator-common.css`
      But the release ships no CSS asset (or an empty one)
      When it is used as a target
      Then activation fails closed before any live mutation

## Requirements

### R1 — One shared asset with the exact ordered prefix

Create `frontend/sea-speed/operator-common.css` containing the ordered rule
prefix shared by both pages, from `:root{` through the base `.objects-link{…}`
rule inclusive: 22 ordered rules, 2366 bytes, extracted verbatim from the Water
page (the two pages differ only in inter-rule whitespace, not in rule content).

### R2 — Absolute link on both pages, residual inline starts at the boundary

In both pages, insert `<link rel="stylesheet" href="/sea-speed/operator-common.css">`
immediately before the remaining `<style>` block and delete only the prefix. The
absolute URL is required because the Water page is aliased at `/sea-speed/water/`
and the Road page lives at `/sea-speed/road/`. The `.objects-link.active`
extension is left inline on Road; the `.objects-link:hover,…` selector list is
not shared.

### R3 — Ordered whole-rule equivalence (proof)

Reconstruct, per page, `linked prefix rules + residual inline rules` and compare
to that page's pre-extraction ordered rule sequence. The comparison splits each
`<style>` into top-level whole-rule strings (brace-depth parser, so `@media`
blocks stay one rule) and compares element-wise, preserving each rule's internal
whitespace while ignoring only whitespace between rules. Result: **True** for
both pages — Water base 129 rules = 22 linked + 107 residual; Road base 130 =
22 linked + 108 residual. Selector lists, declaration order, literals,
`!important` and at-rules are unchanged.

### R4 — Deployment inventory and install/rollback correctness

Add the asset to the VPS required inventories in
`scripts/quality/build_exact_artifacts.py` and
`scripts/quality/validate_exact_artifacts.py`. Extend `deploy/vps/deploy.sh`
with: `OPERATOR_COMMON_CSS_TARGET`/`_URL`; `release_complete`; the download
required loop; install-to-release; bootstrap capture (live file or `.absent`
marker); `ensure_current_release_has_operator_css`; `css_state` detection that
rejects HTML referencing a missing/empty asset; activation ordering (CSS before
HTML on upgrade, HTML restored before CSS removal on downgrade); and a
`verify_frontends` CSS check.

### R5 — Pre-feature rollback admissibility

The release immediately preceding #685 was produced by a `deploy.sh` with no
knowledge of this asset, so it carries **neither** the CSS file **nor** an
`.absent` marker. That "neither" state must not break the first rollback: it is
admissible only when the release's HTML does not reference `operator-common.css`
(a genuine pre-feature release); otherwise the deploy fails closed. A candidate
HTML that references a missing or empty asset is always rejected.

### Prefix boundary (normative)

- START: `:root{color-scheme:dark;…}` (first rule of `<style>`).
- END: the base `.objects-link{display:inline-flex;…white-space:nowrap}` rule,
  INCLUSIVE.
- EXCLUDED boundary rule: `.objects-link:hover,.objects-link:focus-visible{…}`
  (Water) and `.objects-link:hover,.objects-link:focus-visible,.objects-link.active{…}`
  (Road) — kept inline, because Road's selector list differs.
- Everything after the boundary stays inline in its page: camera-stage / canvas
  stacking, `#waterMainVideo` / `#roadMainVideo`, `@media(max-width:700px)` vs
  `@media(max-width:760px)`, fullscreen button, and all domain rules.

### Visual matrix (PENDING UI worker)

| # | Page | Path | Viewports | States to compare |
|---|------|------|-----------|-------------------|
| V-1 | Water | `/sea-speed/` | 1280, 1260, 900, 700, 430 px | default, stream active, ROI editing |
| V-2 | Road | `/sea-speed/road/` | 1280, 1260, 900, 760, 430 px | default, video active, fullscreen |
| V-3 | Cross-nav | header links | 1280, 430 px | Water↔Road/Cameras/Objects hover + `.objects-link.active` on Road |

Comparison method: post-change baseline screenshot per cell vs the pre-#685
baseline; residual must be empty. **Status: PENDING the UI worker** — these
results are not yet produced and must not be reported as done here.

### Ordered-rule equivalence proof method (reproducible)

1. `git show HEAD:<page>` → parse `<style>` into ordered whole-rule list
   `base` (brace-depth split).
2. Parse `operator-common.css` → `linked` (22 rules).
3. Parse the post-change page `<style>` → `residual`.
4. Assert `linked + residual == base` element-wise, internal whitespace preserved.
5. Water: `129 == 22 + 107`; Road: `130 == 22 + 108`.

### Deploy audit summary

`deploy/vps/deploy.sh` is in the diff, so the change is audited through the
8-stage transaction model in `plan.md` (`TX-001`…`TX-008`). Key invariants
enforced by the script: release completeness includes the asset; the target
release must carry a non-empty asset; upgrade ordering installs CSS before the
HTML; downgrade ordering restores HTML before removing CSS; a pre-feature target
(neither file) is accepted only if its HTML does not reference the asset;
`verify_frontends` checks the CSS is non-empty and HTTP-reachable when present.

### Rollback case (normative)

- Rollback target = `previous-release` (pre-#685, e.g. the #688 release).
- `ensure_current_release_has_operator_css` captures live state before mutation:
  live CSS present → copy into the rollback release; live CSS absent → verify
  the release HTML does not reference the asset, then write `.absent`; if it
  DOES reference a missing asset → fail closed before mutation.
- `install_release` independently tolerates a release with neither file: it
  derives `css_state=prefeature`, re-checks that the release HTML does not
  reference the asset, and proceeds as absent (HTML restored, then CSS removed).
  A referencing-but-missing candidate is rejected.

## Acceptance criteria

- AC-001: `frontend/sea-speed/operator-common.css` exists and holds the ordered shared prefix as 22 rules (from `:root` through base `.objects-link` inclusive), extracted verbatim, with no `.objects-link:hover`/`.active` rule and no domain rules.
- AC-002: Both `index.html` and `road/index.html` carry `<link rel="stylesheet" href="/sea-speed/operator-common.css">` immediately before `<style>`, and their residual inline `<style>` begins at `.objects-link:hover`, with `.objects-link.active` preserved inline only on Road.
- AC-003: Ordered whole-rule reconstruction equals the pre-extraction page for both pages (Water 129 = 22+107; Road 130 = 22+108), internal whitespace preserved.
- AC-004: `frontend/sea-speed/operator-common.css` is in the VPS required list of both `build_exact_artifacts.py` and `validate_exact_artifacts.py`, and validate's VPS set remains a subset of build's.
- AC-005: `deploy/vps/deploy.sh` declares `OPERATOR_COMMON_CSS_TARGET`/`_URL`, covers the asset in `release_complete`, the download loop, install-to-release, bootstrap capture, activation ordering and `verify_frontends`, passing `bash -n`.
- AC-006: `install_release`/`ensure_current_release_has_operator_css` accept a pre-feature release with neither file nor marker only when its HTML does not reference the asset, and reject any candidate HTML referencing a missing/empty asset.
- AC-007: Verification commands pass: `bash -n deploy/vps/deploy.sh` and `python3 -m py_compile scripts/quality/build_exact_artifacts.py scripts/quality/validate_exact_artifacts.py`.
- AC-008: Rendered visual parity across the matrix (V-1…V-3) is confirmed against the pre-#685 baseline by the UI worker (PENDING; not produced by this worker).

## Runtime feedback

- Static verification is complete (ordered-rule equivalence True; `bash -n` OK;
  `py_compile` OK; inventories converged; SDD validator green).
- Rendered visual parity (AC-008): the UI worker reviewed the 8 before/after
  screenshots and found the before and after variants visually identical; AC-008
  is not formally closed by this worker.
- The first pre-feature rollback path is reasoned and statically guarded but not
  exercised against a live VPS in this worker; its runtime confirmation is
  deferred to the deploy stage.

### Pre-existing visual debt (out of scope, NOT caused by #685)

The UI worker observed the following defects in BOTH the before and after
variants. They are therefore PRE-EXISTING and explicitly NOT regressions from
this CSS extraction; they are out of scope for #685 and are not fixed here.

- 390px horizontal overflow: the status strip is clipped (the DETECTIONS chip
  shows only "D"), the date inputs are clipped, and the "Показать"/"Текущее"
  buttons extend past the card border.
- Road mobile stage labels collide ("car #31 54.2km/h" / "truck #32 41.7km/h")
  and the A2/B2 labels overlap the boxes.
- Water mobile stage is tiny (~340×190) and the AI OVERLAY badge crowds the
  top-left corner.
- A tofu glyph (▯) renders at the bottom-right of the road stage on both
  viewports.
- Desktop small, dim secondary text (~9–11px) in counter labels, table headers
  and subtitles.
- Focus/hover states and keyboard behavior cannot be verified from static
  screenshots; the 700–760px breakpoint is not covered by the 390/1440
  viewports.

## NFR assessment

- NFR-001 | Area: Visual parity | Target: pixel-identical rendered layout on Water and Road across 1280/1260/900/760/700/430 widths | Validation: UI worker visual matrix (V-1..V-3) vs pre-#685 baseline | Evidence: pending UI-worker screenshots | Status: CONCERNS
- NFR-002 | Area: Payload and caching | Target: the 22 shared rules are served once from a cacheable asset instead of duplicated in both HTML documents | Validation: byte and rule count of operator-common.css | Evidence: 2366 bytes, 22 ordered rules | Status: PASS
- NFR-003 | Area: Deployment safety | Target: no live page references a missing or empty operator-common.css at any point of upgrade or downgrade | Validation: static review of css_state guard and activation ordering plus bash -n | Evidence: deploy/vps/deploy.sh review, bash -n OK | Status: CONCERNS
