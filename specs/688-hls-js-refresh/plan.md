# Plan — Issue #688 hls.js 1.7.4 refresh with verified SRI

- Issue: #688
- Specification: specs/688-hls-js-refresh/spec.md

## Architecture

Smallest-change supply-chain maintenance on the static frontend contour: the
three operator pages' single hls.js `<script>` tag moves from
`hls.js@1.5.7` to `hls.js@1.7.4`. The tag keeps its CDN path
(`/dist/hls.min.js`), its `crossorigin="anonymous"` CORS mode and its document
position; only the version in `src` and the sha384 `integrity` value change.
No build step, no bundling, no player code, no worker/API surface: pages keep
loading one minified hls.js file from jsdelivr at boot.

The version bump is justified as preventive maintenance: `1.7.4` is the npm
registry `latest` non-prerelease release (published 2026-10-28), the current
`1.5.7` pin is aging, and every API/option the players use exists unchanged in
1.7.4. No CVE is claimed for 1.5.7 by this issue.

Production HTML is owned by this worker; test updates are owned by the
separate test worker (`tests/test_688_hls_pin.py` new, plus
`tests/test_frontend_contract.py`, `tests/test_665_water_page_assets.py`,
`tests/browser/fixture-server.mjs`, `tests/browser/operator-pages.spec.mjs`).
This trio records the production change and its evidence; the HTML change is
verifiable by direct byte inspection.

## Decisions

- **Refresh to 1.7.4 with SRI on all three pages**: newest stable release whose
  artifact was byte-verified end to end. The integrity value is the sha384 of
  the exact bytes served by the CDN, cross-checked against the npm tarball and
  the registry-published sha512 during admission (see spec.md).
- **Version + integrity only**: no player configuration retune, no CSP change,
  no ffmpeg/streaming change. The tag remains a single `<script>` with
  `crossorigin="anonymous"` (mandatory for SRI on CORS-fetched scripts).
- **Same `/dist/hls.min.js` path everywhere**: identical tag on all three
  pages; cameras keeps its two-space indentation, water and road keep
  column-zero placement, so the tags are byte-identical apart from leading
  indentation.
- **No inventory or deploy-script change**: the three HTML files are already
  required by both VPS inventories and are staged by `deploy.sh`; the refresh
  rides the normal release contour.
- **Runtime acceptance is RUNTIME-MANUAL**: private authenticated live streams
  are out of reach inside this sandbox, so playback is recorded as pending
  until the post-deploy probe.

## Affected contours

- Frontend static assets (deployed to VPS — release contour):
  `frontend/sea-speed/index.html` (water `/sea-speed/water/`),
  `frontend/sea-speed/road/index.html` (`/sea-speed/road/`),
  `frontend/sea-speed/cameras/index.html` (`/sea-speed/cameras/`).
- This SDD trio: `specs/688-hls-js-refresh/{spec,plan,tasks}.md`.
- Explicitly untouched: `tests/**` (separate test worker), `api/`, `worker/`,
  `deploy/`, `.github/`, `scripts/`, lockfiles, inventories, player config,
  CSP. No retroactive edits to #575, #665 or #675 artifacts.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: 1.7.4 keeps every API/option the three players use (spec.md API compatibility check); no player code or option changes; the previous 1.5.7 pin remains the documented rollback target | Validation: byte-level tag inspection in this trio; post-deploy operator playback probe (RUNTIME-MANUAL); frontend contract pins owned by the test worker | Residual risk: a version-specific behavior change in live latency/ABR could surface only under real streams — caught by the post-deploy cam1/road1 probe and rolled back by restoring the previous exact release | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: SEC | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: SRI sha384 computed from bytes that match both the CDN artifact and the npm tarball whose sha512 equals the registry's published dist.integrity; version-pinned jsdelivr URLs are immutable | Validation: spec.md byte-verification procedure and observed results; browser enforces SRI natively at runtime | Residual risk: a jsdelivr-side artifact swap under the same version would block the script browser-side — visible immediately as no playback | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: static-asset-only change; three files already staged by deploy.sh and required by both inventories; no manifest or deploy-plumbing edit | Validation: exact changed-file scope check plus validate_sdd and the standard VPS deploy verification | Residual risk: standard release-contour deploy risk (handled by the existing deploy transaction and rollback) | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: direct inspection of the three pages shows the pinned 1.7.4 src, exact sha384 integrity and crossorigin="anonymous", with the tag line otherwise unchanged (before/after captured in tasks.md)
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P1 | Evidence: normalized extraction of the three hls.js tags yields three identical lines; a repo grep finds no `hls.js@1.5.7` left in the three pages
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: `python3 scripts/ci/validate_sdd.py` passes and `git status --short` / `git diff --stat` list only the allowed paths (recorded in tasks.md)
- TEST-004 | Covers: AC-004 | Level: runtime-manual | Priority: P1 | Evidence: post-deploy operator probe of `/sea-speed/water/`, `/sea-speed/road/` and `/sea-speed/cameras/` — cam1 and road1 live playback with no SRI or hls.js error; pending until the VPS deploy

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

This audit models the VPS-only rollout of the refreshed static frontend; it
does not redeploy Ubuntu or Windows. A VPS deployment is required for the
change to reach operators.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: the production VPS remains on the accepted previous release | Retry: correct the exact SHA/scope/authorization evidence and re-enter the protected VPS deploy workflow | Rollback: NOT REQUIRED before mutation | Evidence: exact merged main SHA, green trusted Quality run for that SHA, owner-approved #688 scope
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: a candidate release may be staged while the current VPS release stays active | Retry: verify staged release identity plus current/previous markers, then retry | Rollback: NOT REQUIRED while the active release is unchanged | Evidence: exact VPS artifact/release manifest and current/previous release markers
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: a candidate release may be active but is not accepted until verification passes | Retry: only after the deploy transaction restores or proves a coherent current release | Rollback: the existing VPS deploy rollback restores the previous exact release | Evidence: repository-owned deploy-vps activation logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: the candidate is not accepted | Retry: resolve health/public-smoke failure once the actual current release is known | Rollback: automatic previous-release verification through the accepted loopback origin and protected public smoke | Evidence: origin health, public smoke, exact frontend release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment evidence is incomplete and completion is forbidden | Retry: verify actual runtime before persisting evidence | Rollback: the previous exact VPS release remains the declared rollback target | Evidence: current/previous markers plus a runtime-verified deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: the verified runtime stays valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale-cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: the deployed runtime may be healthy but pinned-tag acceptance remains incomplete | Retry: recollect the three-page pinned-tag probe without redeployment while runtime identity is unchanged | Rollback: decide from actual page/runtime behavior, not evidence upload alone | Evidence: deployment manifest plus an external read-only probe of the hls.js script tags on /sea-speed/water/, /sea-speed/road/ and /sea-speed/cameras/
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if the previous exact release cannot be restored/verified, stop automated mutation and recover the actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous exact VPS release | Evidence: existing VPS rollback logs and verified origin/public health

## Validation

- Three hls.js tags inspected before and after; see tasks.md completion gate
  for the observed before/after lines and the identical-tag check.
- `python3 scripts/ci/validate_sdd.py` — OBSERVED (see tasks.md).
- `git status --short` and `git diff --stat` — OBSERVED (see tasks.md).
- Runtime playback probe — RUNTIME-MANUAL, pending the VPS deploy; not
  claimed as done.

## Runtime feedback

- RF-001: Operator actions expected: 0 at merge time — the change rides the
  normal VPS release contour. After the deploy, an operator opens the three
  pages and confirms live playback for cam1 and road1.
- RF-002: the refresh introduces no new runtime configuration; the only
  third-party code is the SRI-verified 1.7.4 artifact.
