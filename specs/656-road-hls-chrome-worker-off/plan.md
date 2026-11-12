# Plan: road/water/cameras hls.js first + worker off

- Spec: specs/656-road-hls-chrome-worker-off/spec.md

## Architecture
Frontend JS served via Caddy to mostdef.ru/sea-speed/*. `attachHls()` in road/main.js chooses between hls.js (MSE) and native playback; water and cameras pages are already hls.js-first. The site CSP (edge-set, out of scope here) has no worker-src, so hls.js blob: workers are blocked; enableWorker:false keeps hls.js on the main thread.

## Decisions
- hls.js branch first in road attachHls(): Chrome's canPlayType('application/vnd.apple.mpegurl') lies with 'maybe' while unable to demux native HLS, so native-first (PR #655) stalls forever at readyState 0.
- enableWorker:false in all three Hls configs: the CSP blocks blob: workers before any segment fetch.
- Native playback stays as the no-MSE fallback (iOS Safari).
- Startup grace ~15s from MANIFEST_PARSED in road and water: the playlist is regular HLS (2s segments, TARGETDURATION 4) and hls.js needs ~5–8s to first frame, so the old watchdogs (road 1s polling requiring readyState>=2; water 2500ms armed on `waiting` with an empty buffer) doom-looped. Strict post-start stall detection arms on first `playing` of the generation; waiting/stalled are gated during startup; startup state resets per generation in destroyMedia()/destroyStreamMedia(). cameras/cameras.js stays watchdog-free (control group).

## Affected contours
- `frontend/sea-speed/road/main.js` (VPS contour: mostdef.ru/sea-speed/road/)
- `frontend/sea-speed/main.js`, `frontend/sea-speed/cameras/cameras.js` (VPS contour)
- `tests/test_frontend_contract.py` (executed twins)
- `specs/656-road-hls-chrome-worker-off/` (spec, plan, tasks)

## Validation
- Executed frontend twins (unittest): Chrome-lie reconnect stays on hls.js with enableWorker:false; no-MSE fallback sets native src; water worker-off config; source scan of all three pages.
- Watchdog twins: startup grace survives live-sync startup; startup timeout reconnects exactly once after the ~15s budget; post-start strict stall detection still reconnects. Proven RED on base SHA 133a4a7 (road reconnect ~2s, water ~3.5s without the fix), green with the fix: 38 passed, 9 subtests.
- Full suite: 1380 tests OK; new twins proven RED on the base JS (fail without the fix).
- Post-deploy Playwright on prod as an authenticated viewer: readyState 4, currentTime advancing, segments 200 / zero 404, console clean.

## Runtime feedback
- Chrome canPlayType('application/vnd.apple.mpegurl') === 'maybe' is a lie for demuxing purposes; native-first stalls at readyState 0, networkState 2.
- hls.js 1.5.7 decodes the mediamtx fMP4 stream fine once actually used (supersedes the PR #655 runtime-feedback claim).
- CSP worker-src is absent at the edge; blob: worker blocked before any segment fetch.

## Risk profile
- Risk profile: NOT REQUIRED

## Test design
- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: ROAD_CHROME_LIE_SCENARIO executed twin (reconnect stays on hls.js, enableWorker:false, native src never set)
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: ROAD_NO_MSE_SCENARIO executed twin (native src set, zero Hls instances)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P1 | Evidence: source-scan twin of all three operator pages (new Hls config carries enableWorker:false)
- TEST-004 | Covers: AC-004 | Level: runtime-manual | Priority: P0 | Evidence: post-deploy Playwright on prod as authenticated viewer | Reason: production-only visual acceptance
- TEST-005 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: ROAD_STARTUP_GRACE_SCENARIO + WATER_STARTUP_GRACE_SCENARIO executed twins (no reconnect during ~15s startup despite live-sync buffering)
- TEST-006 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: ROAD_STARTUP_TIMEOUT / WATER_STARTUP_TIMEOUT twins (exactly one "startup timeout" reconnect after the budget)
- TEST-007 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: ROAD_POST_START_STALL / WATER_POST_START_STALL regression guards (strict stall watchdog still reconnects after first playback)

## Correct-course check
- Trigger: PRODUCTION_LEARNING
- Issue impact: issue #656 opened for the corrected diagnosis; post-deploy acceptance of deploy #53 found the third blocker — road/water startup watchdog doom-loop (issue comment 6815532835, control-group proof via cameras)
- Specification impact: specs/656-road-hls-chrome-worker-off created; supersedes the PR #655 runtime-feedback claim; requirement 4 (startup grace) + AC-005/AC-006 + NFR-006 added
- Plan impact: startup-grace decision added; TEST-005/006/007 added
- Tasks impact: watchdog twins, fix and re-acceptance tasks added
- Authorization impact: NONE
- Follow-up: CSP worker-src 'self' blob: on the Caddy edge (lane B/C, #656); main.js crossing handler {enabled:true,line} bug and dual panel ownership (#656)

## Deployment transaction audit
- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged, no changes applied | Retry: N/A | Rollback: N/A | Evidence: Change Contract and SDD validators green on PR #657
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: Server assets unchanged, old JS still served | Retry: N/A | Rollback: N/A | Evidence: Deploy workflow ancestry and trusted-CI gates on the merged main SHA
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: New JS served via Caddy, previous assets intact | Retry: Re-deploy previous SHA | Rollback: Revert to e8b8910f04e23bca239e6e6fa1be85276b283d63 | Evidence: Lane-A deploy workflow run artifacts
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: Acceptance probes fail, video not playing | Retry: Re-run probes | Rollback: Revert to previous SHA | Evidence: Playwright acceptance (readyState 4, segments 200, zero 404)
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Merge commit recorded in git | Retry: Re-merge | Rollback: Revert merge commit | Evidence: Merge commit SHA on main
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: JOURNAL entry pending | Retry: Re-record | Rollback: N/A | Evidence: JOURNAL.md entry
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Probe logs missing | Retry: Re-run probes | Rollback: N/A | Evidence: Playwright console and network logs, acceptance screenshot
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: Previous SHA restored on server | Retry: Re-attempt rollback | Rollback: N/A | Evidence: Rollback commit SHA
- Adjacent-stage review: COMPLETE
- Production-learning root cause: Chrome canPlayType('application/vnd.apple.mpegurl') lies 'maybe' while unable to demux native HLS, and the site CSP lacks worker-src so hls.js blob: workers are blocked; the PR #655 native-first diagnosis was wrong. Second learning (deploy #53 acceptance): the streams are regular HLS and hls.js needs ~5–8s to first frame — the road/water startup watchdogs killed the stream during that window (doom-loop); cameras without a watchdog plays the same streams (control group)
- Production-learning adjacent-stage findings: water and cameras pages shared the worker blocker (fixed here); main.js crossing handler {enabled:true,line} bug and dual panel ownership recorded as follow-up (#656); water page HLS_URL points at cam1 (oddity, out of scope)
