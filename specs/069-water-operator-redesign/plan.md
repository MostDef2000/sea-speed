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

- TEST-069-101 | Covers: AC-001, AC-002 | Level: unit/static | Priority: P0 | Evidence: exactly one Water video, no stream-probe, exactly one `new Hls(`, sole media attach target `waterMainVideo`.
- TEST-069-102 | Covers: AC-003 | Level: unit/static | Priority: P0 | Evidence: watchdog/recovery listeners and currentTime checks reference `waterMainVideo`.
- TEST-069-103 | Covers: AC-004 | Level: unit/static + runtime | Priority: P0 | Evidence: worker-inactive overlay clear/gating markers; production OFF→ON→OFF with continuous video.
- TEST-069-104 | Covers: AC-005 | Level: unit/static | Priority: P0 | Evidence: healthy-playback guard and cached fallback URL around `last_overlay_url`.
- TEST-069-105 | Covers: AC-006, AC-007 | Level: integration | Priority: P0 | Evidence: existing live-sync markers, dashboard contracts, protected Road boundary and full repository CI.
- TEST-069-106 | Covers: AC-008 | Level: end-to-end | Priority: P0 | Evidence: exact-head CI, exact-main Quality, VPS deployment and authenticated runtime continuity check.

## Deployment transaction audit

- TX-069-ADMISSION | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | Evidence: Issue #326 `issue-326-water-single-hls-v2` authorization receipt.
- TX-069-PRE | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains prior exact-main | Evidence: exact-main Quality + production policy.
- TX-069-MUTATION | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | Rollback: prior accepted exact-main through protected VPS deployment | Evidence: VPS workflow.
- TX-069-VERIFY | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | Evidence: deployment manifest plus authenticated Water playback continuity.
- TX-069-COMMIT | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | Evidence: exact-source current-release state.
- TX-069-HOUSE | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | Evidence: workflow cleanup status.
- TX-069-EVIDENCE | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | Evidence: Issue checkpoint, CI and deployment artifacts.
- TX-069-ROLLBACK | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | Target: exact previous accepted main | Evidence: protected rollback execution audit if required.

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

- Trigger: MATERIAL_PROTECTED_BOUNDARY_CHANGE — resolved by fresh six-field Scope and immediately-following `OUTCOME APPROVED`.
- Issue impact: refinement remains canonical #326.
- Specification impact: SDD 069 updated.
- Plan impact: two-player allowance removed; single-player lifecycle admitted.
- Tasks impact: refinement tasks added.
- Authorization impact: new identity `issue-326-water-single-hls-v2` supersedes the old protection of Water HLS lifecycle for this bounded diff.

## Runtime feedback

- Prior redesign/collapse production acceptance: PASS/accepted by operator.
- New runtime target: one HLS browser consumer and seamless Worker OFF→ON→OFF overlay transition.
- #335 CPU/transcoding topology is separate deferred work and is not changed here.
