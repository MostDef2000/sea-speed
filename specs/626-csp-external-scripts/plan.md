# Plan — Issue #626 CSP-ready frontend: inline scripts → external files

- Issue: #626
- Specification: specs/626-csp-external-scripts/spec.md

## Architecture

Extraction map (base 8f409d2, verified positions):

- `frontend/sea-speed/index.html`: inline block :93-124 (IIFE crossing-line
  editor) → `crossing-line.js`, connected where the block stood (before the
  hls.js CDN tag :125); inline block :127-216 (main logic) → `main.js`,
  connected where the block stood (after overlay-canvas.js :126, before
  live-sync.js :217).
- `frontend/sea-speed/cameras/index.html`: inline block :101+ →
  `cameras/cameras.js`, connected where the block stood (after the hls.js
  CDN tag :100).
- `frontend/sea-speed/road/index.html`: inline cfg block :62-72 →
  `road/config.js` (before the hls.js CDN tag :73); inline main block :76+
  → `road/main.js`, connected where the block stood (after
  overlay-canvas.js :75).
- `frontend/sea-speed/unavailable.html`: `onclick="location.reload()"` on
  the retry button (:19) → `id="retry-button"` + `unavailable.js`
  (`addEventListener`), script tag before `</body>`.
- `deploy/vps/deploy.sh` (:22-29 copy list) gains the six new files.
- Guard oracle `tests/test_626_csp_no_inline_scripts.py` pins the CSP-ready
  invariant (no inline scripts, no on* attributes, deploy.sh completeness).

## Decisions

- **Verbatim move, zero refactoring of moved code**: the extraction is
  mechanical; any logic edit inside the moved blocks would turn a
  CSP-readiness change into a behavior change and blow up the review
  surface. JS-assigned `.onclick=` handlers stay (CSP-legal per R-8).
- **External files at the exact former positions**: script execution order
  is load-bearing (index main block needs hls.js + overlay-canvas.js;
  road main needs live-sync.js + overlay-canvas.js; crossing-line editor is
  DOM-only and deliberately runs before hls.js). Same-position `src` tags
  preserve semantics without defer/async analysis.
- **unavailable.html via id + addEventListener**: the only HTML-attribute
  handler in the front; an id plus a tiny external file is the minimal
  CSP-legal replacement.
- **Guard test as the acceptance oracle**: the test asserts the negative
  (absence of inline scripts / on* attributes) across all four HTML files
  and the deploy.sh copy-list completeness — it fails on base (RED) and
  passes after extraction (GREEN), and it keeps future inline additions
  from silently re-breaking CSP readiness.
- **deploy.sh gains the new files in the same PR**: a merged frontend that
  references files the deploy does not copy would 404 in production; the
  guard test pins the pairing.

## Affected contours

- VPS contour: `frontend/sea-speed/**` (4 HTML edited, 6 new `.js`) and
  `deploy/vps/deploy.sh` — reaches production through deploy-vps.yml after
  merge (lane A, authorized chain).
- No CONTROL_PLANE files touched: scripts/**, .github/**, contracts/**,
  data/**, schemas/** stay out of the diff.
- Frozen renderer oracles (test_589, test_618, edge-vhost renderer) and
  `scripts/operations/nginx_sea_speed_auth.py` byte-untouched.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: verbatim extraction with same-position script tags preserves execution order; the guard test pins absence of inline blocks and the presence of every new file; full battery re-run after the change | Validation: tests/test_626_csp_no_inline_scripts.py + full battery | Residual risk: a runtime-only regression (e.g. a missed DOM id) would not show in unit tests — mitigated by verbatim-move discipline and post-deploy browser acceptance by the owner | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: SEC | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: this change only removes inline script (strictly CSP-hardening); the enforcement flip on the edge is a separate lane-B operation with its own gates and rollback (Caddyfile backup exists); no header or auth logic touched in this PR | Validation: diff scope check (frontend/** + deploy.sh only) | Residual risk: CSP enforcement itself may surface violations from other origins on mostdef.ru — out of scope, observed during the flip window | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: deploy.sh completeness is pinned by the guard test (every new .js referenced); deploy-vps.yml dispatch happens only after green CI on the merged main SHA with the full 40-hex SHA | Validation: guard test + deploy workflow run observation | Residual risk: standard VPS-contour risk covered by the deploy runbook (rollback = previous SHA) | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_626_csp_no_inline_scripts.py — per-HTML-file assertion: every `<script>` tag carries `src=`, no `on[a-z]+=` attributes (RED on base 8f409d2: inline blocks present)
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: same file — each of the six new `.js` files exists and is non-empty (RED on base: files absent)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: same file — deploy/vps/deploy.sh references each new `.js` filename (RED on base: copy list lacks them)
- TEST-004 | Covers: AC-004 | Level: integration | Priority: P1 | Evidence: RED differential — guard test run on base 8f409d2 before extraction → FAILED; after extraction → OK; test file byte-identical through the fix
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P1 | Evidence: full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` green; `git diff --stat` empty on the frozen renderer oracles

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no change lands | Retry: correct authorization/scope evidence then re-enter | Rollback: NOT REQUIRED before mutation | Evidence: owner `commit approved` (2026-11-09, full chain), base 8f409d2
- TX-002 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not mergeable | Retry: fix CI/validator failures on the branch | Rollback: NOT REQUIRED | Evidence: CI green on exact head, validate_sdd + validate_change_contract green
- TX-003 | Stage: STATE-COMMIT | Mutation: YES (repository only) | Failure disposition: FATAL | State after failure: merge incomplete or CI red | Retry: only with green CI on the exact head | Rollback: revert the merge commit | Evidence: squash merge record
- TX-004 | Stage: PRODUCTION-APPLY | Mutation: YES (VPS front) | Failure disposition: FATAL | State after failure: previous front remains served | Retry: re-dispatch deploy-vps.yml after fixing | Rollback: redeploy previous main SHA via deploy-vps.yml | Evidence: deploy-vps.yml run on the merged main SHA (full 40-hex), acceptance probes after

## Validation

- Focused guard run `python3 -W error::ResourceWarning -m unittest
  tests.test_626_csp_no_inline_scripts -v`: RED on base 8f409d2 — Ran 4
  tests, FAILED (failures=17); GREEN after extraction — Ran 4 tests, OK
  (0.001s); test file byte-identical through the fix, sha256
  09ba135058843b6236a57d178ee54dad9871cfe17cbc0b084009c5a01b6f2ef9.
- Full battery: `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p "test_*.py"` → Ran 1421 tests in 166.915s, OK (skipped=2) —
  baseline 1417 OK (skipped=2) + exactly the 4 new guard methods.
- ruff on changed files (CI config scripts/quality/ruff.toml, 10 changed
  .py): All checks passed.
- validate_sdd: Sea Speed SDD validation passed (EXIT=0).
- Peer verification: independent read-only re-derivation by a second
  worker — verbatim roundtrip byte-exact on all 4 pages, 0 assert-diff
  lines across the 7 repointed test files, deploy.sh touchpoint
  consistency checked, own battery re-run 1421 OK (skipped=2) — verdict
  APPROVE, no divergence with the implementing worker (2:0).

## Runtime feedback

- RF-001: after merge → deploy-vps.yml dispatch (full merged-main SHA,
  canonical_issue 626) → acceptance probes → edge CSP flip (lane B:
  Caddyfile `-Report-Only` removal, `caddy validate`, `systemctl reload
  caddy`) → external + browser acceptance by the owner.
- RF-002: rollback for the front = redeploy previous main SHA; rollback for
  the CSP flip = restore `/etc/caddy/Caddyfile.bak.20261109T044035Z-sec589`
  + `caddy validate` + reload.
