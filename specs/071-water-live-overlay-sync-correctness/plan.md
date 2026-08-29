# Implementation Plan: Water live overlay sync correctness

- Specification: `specs/071-water-live-overlay-sync-correctness/spec.md`
- Issue: #346
- Branch: `issue-346-water-sync-runtime-fix`
- Authorization base main: `b1bb74eabb6af7e5d1c9ba59f77a33ad91aa6d9a`
- Remediation base main: `50aec9a233b465f73993f92a69f8e9b22707a322`
- Approved scope identity: `issue-346-water-live-overlay-sync-task1-v1`

## Architecture

The accepted Water architecture remains unchanged:

```text
protected Water HLS -> one Hls instance -> waterMainVideo
Water live metadata -> SSE/poll buffer -> timestamp match -> liveOverlayCanvas
```

Task 1 changes only the final rendering decision. A bbox is drawn only from a valid same-generation bracket or from a closest-earlier envelope whose capture time is within 2000 ms of compensated media time. If current media time is unavailable or no trustworthy envelope exists, the canvas is cleared. Video playback, worker control, passage/speed semantics and shared transport remain independent.

The runtime-remediation correction removes one blanket newest-envelope age rejection that ran before temporal lookup. HLS may legitimately be several seconds behind the Worker live edge while the bounded metadata buffer still contains an envelope matching the displayed frame. Temporal bracket/closest-earlier selection, not distance from the newest envelope, remains the authority for drawing.

## Decisions

- Keep `frontend/sea-speed/live-sync.js` unchanged; its bracket and closest-earlier primitives remain valid.
- Keep the explicit `LIVE_NEAR_MAX_AGE_MS=2000` bound in the Water page.
- Treat unresolved HLS media time as `clearLive(); return` rather than arrival-order fallback.
- Remove the blanket `newest envelope vs media > 6000 ms` clear because it can reject a valid historical bracket before matching occurs.
- Preserve valid same-generation bracket interpolation with the existing 500 ms bracket-gap bound.
- In the no-bracket path, permit only closest-earlier metadata with capture time inside the explicit bounded window and never later than compensated media time.
- Never restore newest-buffer fallback drawing from Water `renderForVideoFrame()`.
- Add deterministic regression coverage for a valid historical bracket while the newest Worker envelope is more than six seconds ahead.
- Do not modify Road, worker, detection/tracking, speed/passages, API/storage, HLS topology or auth.

## Affected contours

- VPS frontend: REQUIRED — Water operator source only.
- VPS API: NOT REQUIRED.
- Ubuntu Worker/relay: NOT REQUIRED.
- Road operator: protected / unchanged.
- Water worker and passage/speed computation: protected / unchanged.
- nginx/Auth/MediaMTX/ZeroTier/Camera topology: protected / unchanged.

## Risk profile

- Risk profile: REQUIRED

Production learning triggered this remediation: the initial exact-source Task 1 release reached `runtime_verified` but authenticated product acceptance showed `AI active`, `DETECTIONS 1`, `TRACKS 1` with no rendered bbox. The remediation is still frontend-only and reversible, but the observed production acceptance failure makes explicit reliability risk treatment mandatory.

- RISK-071-001 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: bracket/closest-earlier matching remains fail-closed; remove only the pre-match newest-age rejection | Validation: deterministic historical-bracket regression + authenticated production observation | Residual risk: 2 | Owner: frontend | Status: MITIGATED
- RISK-071-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: no unconditional latest-buffer fallback; future and >2s stale no-bracket metadata still clear | Validation: Water sync guard regressions | Residual risk: 1 | Owner: frontend | Status: MITIGATED
- RISK-071-003 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: single HLS lifecycle and protected Road/worker/API contours remain zero-diff | Validation: exact changed-file scope + full Quality | Residual risk: 1 | Owner: delivery | Status: MITIGATED

## Test design

- TEST-071-001 | Covers: AC-001, AC-003 | Level: unit | Priority: P0 | Evidence: deterministic source contract proves unresolved media time and unmatched metadata clear the canvas and that newest-buffer fallback markers are absent.
- TEST-071-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: source contract and Water sync regression prove closest-earlier envelope requires capture time within `[mediaTime-2000, mediaTime]`, future-only metadata clears, and >2s-old metadata clears.
- TEST-071-003 | Covers: AC-004, AC-005 | Level: integration | Priority: P0 | Evidence: existing frontend contracts prove bracket interpolation, one-HLS lifecycle and metadata-only Worker control remain present.
- TEST-071-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: historical bracket at displayed media time remains selectable when newest Worker envelope is >6000 ms ahead.
- TEST-071-005 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: exact changed-file review and repository Quality prove protected contours are zero-diff.
- TEST-071-006 | Covers: AC-007 | Level: end-to-end | Priority: P0 | Evidence: exact-head CI, exact-main Quality and protected VPS runtime_verified.
- TEST-071-007 | Covers: AC-008 | Level: runtime-manual | Priority: P0 | Evidence: authenticated production observation with positive detections/tracks and visible aligned bbox when matching metadata exists.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: the frontend compared displayed HLS media time with only the newest Worker envelope and cleared the canvas before searching the bounded buffer, so normal HLS lag could suppress a valid older temporally matched bbox.
- Production-learning adjacent-stage findings: admission/source/merge/deployment/runtime health gates behaved correctly; mutation and runtime verification succeeded, while product-level authenticated visual verification exposed a frontend temporal-selection defect not represented by the previous deterministic test set; rollback remained available and no worker/API/media topology mutation occurred.
- TX-071-ADMISSION | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no source or production mutation admitted | Retry: repair authorization/contract evidence then re-evaluate | Rollback: not required | Evidence: Issue #346 Task 1 authorization receipt.
- TX-071-PRE | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on prior exact-main | Retry: after exact-main Quality and policy are green | Rollback: not required | Evidence: source protection, exact-main Quality, production-policy evidence.
- TX-071-MUTATION | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: deployment retains/restores prior release | Retry: after exact failure diagnosis/prerequisites | Rollback: protected VPS rollback to `50aec9a233b465f73993f92a69f8e9b22707a322` for remediation release | Evidence: VPS deployment log.
- TX-071-VERIFY | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: re-verify after bounded remediation or rollback | Rollback: prior exact release | Evidence: deployment manifest, health checks, authenticated Water observation.
- TX-071-COMMIT | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: candidate must not be recorded as accepted | Retry: repeat only for same verified exact source | Rollback: restore previous current-release pointer | Evidence: deployment state evidence.
- TX-071-HOUSE | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: serving runtime remains and cleanup warning is recorded | Retry: cleanup independently | Rollback: not required | Evidence: workflow cleanup/prune output.
- TX-071-EVIDENCE | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: delivery remains non-terminal | Retry: recollect exact evidence without source change | Rollback: not required | Evidence: Issue checkpoint, CI and deployment artifact.
- TX-071-ROLLBACK | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: incident remains open and state is reported explicitly | Retry: after exact rollback failure diagnosis | Rollback: previous accepted exact-main | Evidence: protected rollback audit if invoked.

## Validation

- Validate SDD structure/linkage and Change Contract.
- Run `tests/test_water_live_sync_guard.py`, `tests/test_water_overlay_sync.py`, and existing frontend/repository tests.
- Verify diff is limited to `frontend/sea-speed/index.html`, corresponding Water sync tests and SDD 071 files.
- Require exact-head Repository validation and `quality-integration` green.
- Fresh-read main/head/scope/reviews before exact-green-head merge.
- Require exact-main Quality before production deployment.
- Deploy protected VPS exact-main; Ubuntu Worker source deployment is NOT REQUIRED.
- Runtime acceptance: with positive Water detections/tracks, a temporally matched bbox renders; unmatched metadata still clears rather than drawing a displaced newest envelope.

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: #346 remains the same canonical Task 1 outcome; authenticated acceptance exposed an implementation defect inside the admitted sync boundary.
- Specification impact: no product-outcome expansion; SDD 071 remains frontend sync correctness only.
- Plan impact: replace the invalid pre-match newest-age rejection with authoritative buffered temporal matching.
- Tasks impact: T008-T009 record fault-path remediation and repeat delivery/runtime gates.
- Authorization impact: NONE — this is bounded remediation inside `issue-346-water-live-overlay-sync-task1-v1`; exact approved paths and protected contours are unchanged.
- Follow-up: Task 2 remains sequenced after Task 1 terminal acceptance; its separate authorization receipt is preserved.

## Runtime feedback

- Initial release `50aec9a233b465f73993f92a69f8e9b22707a322`: `runtime_verified`, but product acceptance FAIL because positive detector/tracker state rendered no bbox.
- Root cause: pre-match comparison against the newest metadata envelope cleared the canvas before an older buffer item matching the displayed HLS frame could be selected.
- Corrected behavior: let the bounded buffer match the displayed media time; fail closed only when no valid bracket/closest-earlier match exists.
- Task 2 speed semantics and Task 3 recall remain deferred.
