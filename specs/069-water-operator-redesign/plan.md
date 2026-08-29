# Implementation Plan: Water operator dashboard redesign

- Specification: `specs/069-water-operator-redesign/spec.md`
- Issue: #326
- Branch: `issue-326-water-single-hls`
- Authorization base main: `779aed5868de67cbd106693c76db4dc77915627d`
- Approved scope identity: `issue-326-water-single-hls-v2`

## Architecture

The refinement stays inside the authenticated Water frontend. `frontend/sea-speed/index.html` keeps the approved dashboard but collapses the historical two-player browser plumbing into one media pipeline:

```text
/sea-speed/media/cam1/index.m3u8
        -> one Hls instance
        -> waterMainVideo
        -> liveOverlayCanvas (AI metadata only)
```

The Water worker remains independently controlled through the existing API. Worker OFF does not affect HLS; it clears live AI buffer/canvas state. Worker ON does not reconnect HLS; new SSE/live metadata is synchronized over the already-playing video. `frontend/sea-speed/live-sync.js` remains unchanged.

## Decisions

- Remove hidden `video#video.stream-probe` completely.
- Keep `waterMainVideo` as the sole Water media element and sole HLS target.
- Keep one Hls.js object; `window.hls` / `window.waterHls` may reference the same instance only for compatibility with the existing live-sync timestamp lookup.
- Rebind playback health, watchdog, decode/network recovery and reconnect event listeners to `waterMainVideo`.
- Worker Start/Stop must never call stream connect/disconnect or replace HLS media.
- On worker inactive state, clear `liveBuffer`, interpolation/lag state and `liveOverlayCanvas`, and reject/purge stale envelopes until the worker is active again.
- Continue polling `/sea-speed/api/cam1/state`, but do not mutate `overlayImg.src` while HLS playback is healthy. Cache the last fallback URL so an unhealthy player loads only a changed fallback snapshot.
- Preserve HLS retry constants and all `SeaSpeedLiveSync` interpolation/bracketing behavior.
- Keep the approved dashboard layout, collapsible controls, crossings/passages, registry links and Road page unchanged.

## Affected contours

- VPS frontend: REQUIRED — `frontend/sea-speed/index.html` lifecycle only.
- VPS API: NOT REQUIRED.
- Ubuntu Worker/relay: NOT REQUIRED.
- Road operator: protected / unchanged.
- nginx/Auth/MediaMTX/ZeroTier/Camera/FFmpeg topology: protected / unchanged.
- Existing SDD and frontend contract test: updated for the admitted refinement.

## Risk profile

- Risk profile: NOT REQUIRED

The source diff is a bounded VPS frontend reliability refinement. Security, API/event/state/storage schemas, destructive migrations and worker/media topology remain unchanged. Production deployment still requires the existing protected VPS deployment transaction and exact-main acceptance.

## Test design

- TEST-069-101 | Covers: AC-001, AC-002 | Level: unit | Priority: P0 | Evidence: static frontend contract proves exactly one Water video, no stream-probe, exactly one `new Hls(`, and sole media attach target `waterMainVideo`.
- TEST-069-102 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: static frontend contract proves watchdog/recovery listeners and currentTime checks reference `waterMainVideo`.
- TEST-069-103 | Covers: AC-004 | Level: runtime-manual | Priority: P0 | Evidence: authenticated production Worker OFF→ON→OFF observation proves overlay clearing/resume while the same video advances continuously.
- TEST-069-104 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: static contract proves healthy-playback guard and cached fallback URL around `last_overlay_url`.
- TEST-069-105 | Covers: AC-006, AC-007 | Level: integration | Priority: P0 | Evidence: existing live-sync markers, dashboard contracts, protected Road boundary and full repository CI.
- TEST-069-106 | Covers: AC-008 | Level: end-to-end | Priority: P0 | Evidence: exact-head CI, exact-main Quality, VPS deployment and authenticated runtime continuity check.

## Deployment transaction audit

- TX-069-ADMISSION | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no source or production mutation admitted | Retry: repair authorization or contract evidence, then re-evaluate | Rollback: not required because no mutation occurred | Evidence: Issue #326 authorization receipt for `issue-326-water-single-hls-v2`.
- TX-069-PRE | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on prior accepted exact-main | Retry: rerun only after exact-main Quality and production policy are green | Rollback: not required because production is unchanged | Evidence: exact-main Quality, source protection and production-policy evidence.
- TX-069-MUTATION | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: deployment workflow restores or retains the prior accepted release | Retry: only after the exact deployment failure is diagnosed and prerequisites are satisfied | Rollback: protected VPS rollback to the previous exact accepted main | Evidence: VPS deployment workflow and exact-source execution log.
- TX-069-VERIFY | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate release is not accepted as runtime-verified | Retry: re-verify after bounded remediation or rollback | Rollback: previous accepted exact release if verification cannot pass | Evidence: deployment manifest, origin/media health and authenticated Water continuity acceptance.
- TX-069-COMMIT | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: release state must not claim the candidate as accepted | Retry: repeat state commit only for the same verified exact source | Rollback: restore previous current-release pointer if state commit is inconsistent | Evidence: exact-source `/opt/sea-speed-deploy/state/current-release` manifest evidence.
- TX-069-HOUSE | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: accepted runtime remains serving while cleanup warning is recorded | Retry: bounded cleanup may be retried independently | Rollback: not required for non-critical cleanup | Evidence: workflow cleanup/prune status.
- TX-069-EVIDENCE | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: delivery remains non-terminal until durable evidence is complete | Retry: recollect or republish exact evidence without changing source | Rollback: not required because evidence collection is non-mutating | Evidence: Issue checkpoint, CI statuses and deployment artifacts.
- TX-069-ROLLBACK | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: incident remains open and production state is reported explicitly | Retry: retry rollback only after diagnosing the exact rollback failure | Rollback: target is the previous accepted exact-main release | Evidence: protected rollback execution audit when invoked.

## Validation

- Validate SDD structure/linkage and Change Contract.
- Run `tests/test_frontend_contract.py` and the repository test/quality suite required by current main.
- Verify branch diff is limited to `frontend/sea-speed/index.html`, `tests/test_frontend_contract.py` and the three SDD 069 files.
- Require exact-head Repository validation and `quality-integration` green.
- Fresh-read main/head/scope/reviews before exact-green-head merge.
- Require exact-main Quality before runtime deployment.
- Require protected VPS deployment; Ubuntu Worker deployment is not part of this change.
- Runtime acceptance: authenticated Water video advances continuously through Worker OFF→ON→OFF, AI canvas clears while stopped and resumes only with fresh envelopes.

## Correct-course check

- Trigger: MATERIAL_SCOPE_CHANGE
- Issue impact: refinement remains canonical #326.
- Specification impact: SDD 069 now admits the bounded single-HLS Water lifecycle refinement.
- Plan impact: historical two-player allowance is replaced by a single-player lifecycle.
- Tasks impact: T101-T110 track the refinement through runtime acceptance.
- Authorization impact: scope identity `issue-326-water-single-hls-v2` is authorized by the fresh immediately-following `OUTCOME APPROVED` receipt.
- Follow-up: complete exact-head CI, merge, exact-main Quality, protected VPS deployment and authenticated Worker OFF→ON→OFF continuity evidence under the fresh authorization.

## Runtime feedback

- Prior redesign/collapse production acceptance: PASS/accepted by operator.
- New runtime target: one HLS browser consumer and seamless Worker OFF→ON→OFF overlay transition.
- #335 CPU/transcoding topology is separate deferred work and is not changed here.
