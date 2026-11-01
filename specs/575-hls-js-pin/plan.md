# Plan — Issue #575 hls.js production pin with Subresource Integrity

- Issue: #575
- Specification: specs/575-hls-js-pin/spec.md

## Architecture

Smallest-change supply-chain hardening on the static frontend contour: the
three operator pages' `<script>` tags move from a floating `@latest` CDN
reference (water, cameras) / unpinned URL (road) to one exact,
production-proven artifact with Subresource Integrity. No build step, no
bundling, no worker/API surface: the pages keep loading hls.js from jsdelivr
at boot; only the tag attributes change. The contract is pinned by the
existing structural (SS) test layer in tests/test_frontend_contract.py —
markup has no executable surface for tag attributes, so the pin is a parsed
attribute-map scan in the file's established style (regex extraction over
comment-stripped source, like `unique_ids` and the anchor scans).

## Decisions

- **Pin 1.5.7 with SRI on all three pages**: the version the road page has
  already proven in production; the integrity value is the sha384 of the
  exact jsdelivr artifact, cross-checked against the jsdelivr registry record
  (sha256 match) during recon. `crossorigin="anonymous"` is mandatory — SRI
  checks are skipped for non-CORS requests, and jsdelivr serves the required
  CORS headers.
- **Explicit `/dist/hls.min.js` path everywhere**: same form as the road page
  today; no bare-package URLs (jsdelivr would have to resolve them).
- **Structured test pins, not raw substrings**: a `script_tags()` helper
  extracts attribute dicts from every `<script ...>` opener on
  comment-stripped source (a commented-out tag can never satisfy the pin),
  mirroring the file's `unique_ids`/anchor-scan style. Assertions name the
  page and the broken attribute.
- **Validator untouched**: `575` has no prefix collision
  (validate_prefix_uniqueness skips prefixes with <2 dirs) — no grandfather
  line, no scripts/ci changes.

## Affected contours

- Frontend static assets (deployed to VPS — release contour):
  frontend/sea-speed/index.html, frontend/sea-speed/cameras/index.html,
  frontend/sea-speed/road/index.html.
- Control plane: tests/test_frontend_contract.py (new SS twin class).
- This SDD trio. Nothing else — no api/, worker/, deploy/, scripts/,
  .github/ changes.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: the pinned artifact is byte-identical to the one the road page already serves in production; the integrity value was cross-checked against the jsdelivr registry record (sha256 match) during recon; version-pinned jsdelivr URLs are immutable | Validation: contract tests pin the exact src+integrity+crossorigin per page; post-deploy probe confirms HLS playback on all three pages | Residual risk: a jsdelivr-side artifact change under the same version would break playback browser-side — caught by the post-deploy probe and the pinned tests | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: static-asset-only change; no manifest, deploy plumbing or API changes; rides the normal release contour with automatic rollback on failed gates | Validation: full battery + ruff + validate_sdd green before merge | Residual risk: standard release-contour deploy risk | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: focused pytest run of tests/test_frontend_contract.py (25 passed + 6 subtests) — per-page src/integrity/crossorigin equality pins
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P1 | Evidence: focused pytest run — the @latest guard fails if any hls script tag on the three pages uses the floating tag
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: full battery, ruff and validate_sdd runs recorded in tasks.md

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

This audit models the VPS-only rollout of the pinned static frontend; it does
not redeploy Ubuntu or Windows.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production VPS remains on the accepted previous release | Retry: correct exact SHA/quality/authorization evidence then re-enter the protected VPS deploy workflow | Rollback: NOT REQUIRED before mutation | Evidence: exact merged main SHA, push/main Quality integration, owner-approved #534 decomposition chain (commit approved 2026-11-01)
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate release may be staged while current VPS release remains active | Retry: verify staged exact release and previous/current identities then retry | Rollback: NOT REQUIRED while active release is unchanged | Evidence: exact VPS artifact/release manifest and current/previous release markers
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS release may be active but is not accepted until verification succeeds | Retry: only after existing deploy transaction restores or proves a coherent current release | Rollback: existing VPS deploy rollback restores previous exact release | Evidence: repository-owned deploy-vps activation logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: resolve health/public-smoke failure after actual current release is known | Rollback: automatic previous-release verification through accepted loopback origin and protected public smoke | Evidence: origin health, public smoke, exact frontend release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment evidence is incomplete and completion is forbidden | Retry: verify actual runtime before persisting evidence | Rollback: previous exact VPS release remains the declared rollback target | Evidence: current/previous markers plus runtime-verified deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but pinned-tag acceptance remains incomplete | Retry: recollect the three-page pinned-tag probe without redeployment when exact runtime identity is unchanged | Rollback: decide from actual page/runtime behavior, not evidence upload alone | Evidence: deployment manifest plus external read-only probe of the pinned hls.js script tags on /sea-speed/, /sea-speed/cameras/, /sea-speed/road/
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if previous exact release cannot be restored/verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous exact VPS release | Evidence: existing VPS rollback logs and verified origin/public health

## Validation

- Focused run `python3 -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/534/pytest-tmp tests/test_frontend_contract.py -q`: OBSERVED 25 passed + 6 subtests (base 23 passed / 0 subtests; delta +2 methods, +6 subtests).
- Full battery `python3 -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/534/pytest-tmp tests/ -q`: OBSERVED 1234 passed / 2 skipped / 312 subtests (baseline 1232/2/306 on base 871cc50; delta +2 methods, +6 subtests) — orchestrator-observed on the final tree.
- ruff (CI config, repo-wide): `ruff check --config scripts/quality/ruff.toml .` clean — OBSERVED.
- `python3 scripts/ci/validate_sdd.py` plain run passes with the new trio — OBSERVED; `--event` simulation green after this audit section.

## Runtime feedback

- RF-001: Operator actions expected: 0 — the change rides the normal VPS
  release contour; runtime acceptance = exact-head CI green plus the
  standard post-deploy probe (three pages load, HLS playback starts; the
  browser verifies the SRI hash natively).
- RF-002: no new third-party artifact is introduced — the pinned 1.5.7 bytes
  are already in production via the road page.
