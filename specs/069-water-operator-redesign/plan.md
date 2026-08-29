# Implementation Plan: Water operator dashboard redesign

- Specification: `specs/069-water-operator-redesign/spec.md`
- Issue: #326
- Branch: `issue-326-water-operator-redesign`
- Authorization base main: `ab1ecd1264bf60570c95fae4161743b3b449af1c`

## Architecture

The change remains inside the existing static authenticated Water frontend. `frontend/sea-speed/index.html` continues to own the Water operator dashboard and existing HLS/live overlay/editor JavaScript. The desktop shell is reorganized from three visible columns into a primary content column plus a right information rail. A non-visible media probe may remain for the existing HLS health/reconnect machinery, but the clean-stream presentation is removed. The existing `cam1` crossing summary and passages endpoints remain the only data sources for the new right-side cards.

`frontend/sea-speed/objects/index.html` remains the canonical registry/crossing-history UI. A query-state adapter (`scope=water&view=crossings`) activates the existing crossing layer; it does not introduce a second crossing-history implementation or API.

## Decisions

- Keep all current Water editor element IDs and POST/GET contracts so ROI, speed lines, speed calibration, and crossing-line actions retain behavior.
- Preserve the synchronized `waterMainVideo` + `liveOverlayCanvas` code path and current HLS retry/watchdog constants. Do not change timing constants, live endpoint semantics, or worker behavior.
- Retain a hidden `video#video` media probe if required by the current stream-health implementation; it is runtime plumbing, not a visible clean-stream card.
- Use `/sea-speed/api/analytics/cam1/crossings/summary` for date-window totals and class breakdown. Map the existing `left_to_right` and `right_to_left` counters to dashboard IN/OUT labels without altering stored direction semantics.
- Do not fabricate a persisted latest-crossing timestamp. The UI may show an unavailable marker until a crossing-count change is observed during the current page session; that client observation is explicitly transient.
- Link `История` to `/sea-speed/objects/?scope=water&view=crossings`; registry query-state handling must activate its existing crossing layer and keep Water scope.
- Link `Все проходы` to `/sea-speed/objects/?scope=water` and continue rendering at most three records from the current passages endpoint.
- Keep `frontend/sea-speed/road/index.html` unchanged.

## Affected contours

- VPS frontend: REQUIRED; static authenticated Water page and registry page change.
- VPS API: source/schema change NOT REQUIRED; existing endpoints only.
- Ubuntu Worker/relay: NOT REQUIRED.
- Road operator page: protected / unchanged.
- Authentik, nginx topology, MediaMTX, storage schema, telemetry schema: protected / unchanged.

## Risk profile

- Risk profile: NOT REQUIRED

The canonical Change Contract derives no full-risk trigger for this exact diff: production impact is VPS frontend only, while security impact, API/event/state/storage schema impact, destructive/data migration impact, and other high-risk triggers are all NONE/NO. Production deployment safety remains governed separately by the required VPS safety envelope and deployment transaction audit below.

## Test design

- TEST-069-001 | Covers: AC-001, AC-002, AC-003 | Level: unit | Priority: P0 | Evidence: `tests/test_frontend_contract.py` structural and operational-marker assertions
- TEST-069-002 | Covers: AC-004, AC-005 | Level: unit | Priority: P0 | Evidence: `tests/test_frontend_contract.py` plus `tests/test_unified_registry.py` crossing-dashboard/direct-view contract assertions
- TEST-069-003 | Covers: AC-006 | Level: unit | Priority: P1 | Evidence: passage card endpoint/limit/link markers in `tests/test_frontend_contract.py`
- TEST-069-004 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: repository validators and relevant/full unittest suite in PR Validation/Quality
- TEST-069-005 | Covers: AC-008 | Level: end-to-end | Priority: P0 | Evidence: exact-head CI, exact-main Quality, protected VPS deployment and authenticated `/sea-speed/` acceptance
- TEST-069-006 | Covers: mobile usability and primary-camera hierarchy | Level: runtime-manual | Priority: P1 | Evidence: production responsive inspection at wide desktop, iPhone Pro and iPhone Pro Max portrait dimensions

## Deployment transaction audit

- TX-069-ADMISSION | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: source publication remains prohibited | Retry: repeat only after valid authorization evidence | Rollback: not applicable because no mutation occurred | Evidence: Issue #326 authorization receipt and checkpoint
- TX-069-PRE | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: current production remains on prior exact-main | Retry: rerun protected preflight after resolving failed gate | Rollback: not applicable because deployment has not started | Evidence: exact-main Quality and production-policy preflight
- TX-069-MUTATION | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: protected deploy workflow reports failed transaction and prior release remains rollback target | Retry: only repository-owned protected retry after evidence review | Rollback: deploy workflow rollback path targets previous exact-main | Evidence: VPS deployment workflow/job evidence
- TX-069-VERIFY | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: deployment is not accepted | Retry: repeat bounded runtime verification after repair/redeploy | Rollback: protected rollback when verification indicates deployed regression | Evidence: authenticated HTTP/runtime checks and deployment manifest
- TX-069-COMMIT | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: release state must not claim accepted runtime without successful verification | Retry: repository-owned transaction continuation only | Rollback: restore prior release-state identity through protected rollback | Evidence: exact-source deployment state/provenance
- TX-069-HOUSE | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: accepted runtime remains valid while housekeeping evidence records the fault | Retry: bounded repository-owned housekeeping retry | Rollback: no runtime rollback solely for non-critical housekeeping failure | Evidence: workflow cleanup/job status
- TX-069-EVIDENCE | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: task cannot reach DONE without durable runtime evidence | Retry: regenerate/read exact evidence after source identity remains unchanged | Rollback: runtime rollback only if evidence reveals product regression | Evidence: Issue terminal evidence, release/deployment manifests and Quality status
- TX-069-ROLLBACK | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: task remains blocked or requires human decision if protected rollback cannot restore prior source | Retry: repository-owned rollback retry under standing delegation | Rollback: target is `ab1ecd1264bf60570c95fae4161743b3b449af1c` or the exact previous accepted main if main advances legitimately before deployment | Evidence: protected rollback execution audit and post-rollback runtime checks

## Validation

- Validate SDD structure/linkage and Change Contract against exact changed files.
- Run frontend/registry contract tests and the repository unittest suite required by current main policy.
- Verify exact branch diff contains only the seven approved paths and no secret/runtime artifacts.
- Require exact-head Repository validation and `quality-integration` green before merge.
- Fresh-read base/head/scope/review immediately before exact-green-head merge.
- Require exact-main Quality after merge before runtime policy/deploy progression.
- Require protected VPS deployment evidence and authenticated Water runtime acceptance; Ubuntu Worker deployment is not part of this change.

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: continue within the admitted Issue #326 Water frontend scope; any protected-boundary expansion requires a new authorization cycle

## Runtime feedback

- Expected deployment: VPS frontend through existing protected exact-source pipeline.
- Runtime acceptance targets: `/sea-speed/` authenticated load, synchronized AI feed and status progression, crossing summary/date controls, History direct-link, three-record passage panel, ROI/speed/crossing/calibration controls, and responsive layout.
- Rollback target at admission: `ab1ecd1264bf60570c95fae4161743b3b449af1c`.
- Current runtime verdict: PENDING.
