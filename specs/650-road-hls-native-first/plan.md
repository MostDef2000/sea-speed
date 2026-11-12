# Plan: road1 native HLS first + MediaSource reset

- Spec: specs/650-road-hls-native-first/spec.md

## Architecture
Frontend JS (`frontend/sea-speed/road/main.js`) served via Caddy to mostdef.ru/sea-speed/road/. The `attachHls()` function chooses between native browser HLS and hls.js fallback. `destroyMedia()` resets the video element's MediaSource. No backend changes.

## Decisions
- Use native HLS first (`canPlayType("application/vnd.apple.mpegurl")`) because hls.js v1.5.7 cannot decode mediamtx fMP4.
- Use `roadMainVideo.src=""` + `load()` instead of `removeAttribute("src")` to fully release the old MediaSource/blob URL.

## Affected contours
- `frontend/sea-speed/road/main.js` (VPS contour: mostdef.ru/sea-speed/road/)
- `specs/650-road-hls-native-first/` (spec, plan, tasks)

## Validation
- Playwright in real Chromium: readyState 4, videoWidth 1920, videoHeight 1080, 12/12 segments 200, zero 404.
- CI green on PR, merge to main, lane-A deploy, acceptance probes pass.

## Runtime feedback
- hls.js v1.5.7 cannot decode mediamtx fMP4 stream (readyState 0, waiting timeout loop).
- Native browser HLS decodes fMP4 fine (readyState 4, 1920x1080).
- `removeAttribute("src")` does not release old MediaSource/blob URL; `src=""` + `load()` does.

## Risk profile
- Risk profile: NOT REQUIRED

## Test design
- TEST-001 | Covers: AC-001, AC-002 | Level: end-to-end | Priority: P0 | Evidence: Playwright verification: readyState 4, 12/12 segments 200, zero 404

## Correct-course check
- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit
- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged, no changes applied | Retry: N/A | Rollback: N/A | Evidence: CI green on PR #654
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: Server config unchanged, old JS still served | Retry: N/A | Rollback: N/A | Evidence: Pre-deploy config verified on server
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: New JS served via Caddy, previous config intact | Retry: Re-deploy previous SHA | Rollback: Revert to 6020fc400f43ff5b6638ed8bb63538393ce59514 | Evidence: Lane-A deploy workflow artifacts
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: Acceptance probes fail, video not playing | Retry: Re-run probes | Rollback: Revert to previous SHA | Evidence: Probe results (readyState 4, segments 200)
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Merge commit recorded in git | Retry: Re-merge | Rollback: Revert merge commit | Evidence: Merge commit SHA on main
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: JOURNAL entry pending | Retry: Re-record | Rollback: N/A | Evidence: JOURNAL.md entry
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Probe logs missing | Retry: Re-run probes | Rollback: N/A | Evidence: Playwright console + network logs
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: Previous SHA restored on server | Retry: Re-attempt rollback | Rollback: N/A | Evidence: Rollback commit SHA