# Feature Specification: Water live overlay sync guard

- Feature: 071-water-live-overlay-sync-guard
- Issue: #346
- Status: ACTIVE
- Owner outcome: Water AI bbox is rendered only when live metadata can be matched to current HLS media time; unmatched metadata fails closed by clearing the AI canvas.
- Authorization: `issue-346-task1-water-live-overlay-sync-v1`, base `b1bb74eabb6af7e5d1c9ba59f77a33ad91aa6d9a`.

## Product outcome

`/sea-speed/` keeps one continuous Water HLS player and the existing metadata-only AI canvas architecture, but removes fail-open rendering paths that could draw the latest AI envelope when no trustworthy media-time match exists. If HLS media time is unavailable, or if neither an interpolation bracket nor a sufficiently recent earlier envelope exists, the AI canvas is cleared until synchronized metadata becomes available.

## User scenarios

### Scenario 1 - Normal synchronized playback

Given Water HLS media time is available and live metadata brackets the current media position, the operator sees interpolated AI boxes over the corresponding vessel positions.

### Scenario 2 - Missing media-time mapping

Given the browser cannot resolve current HLS media time, Water live AI canvas is cleared. The latest metadata envelope is not rendered as a substitute.

### Scenario 3 - Gap in live metadata

Given no valid interpolation bracket exists, the renderer may use only the closest earlier envelope when it is no more than 2000 ms behind compensated media time. Otherwise the AI canvas is cleared.

### Scenario 4 - Worker lifecycle

Stopping the Water Worker clears AI metadata state while the same HLS video continues. Starting the Worker resumes fresh synchronized metadata without HLS reconnect or source switch.

## Requirements

- R1: Water MUST retain exactly one HLS player bound to `waterMainVideo`.
- R2: Water Worker lifecycle MUST remain metadata-only and MUST NOT restart or switch HLS.
- R3: If `getMediaMs()` returns null, `renderForVideoFrame()` MUST clear the live AI canvas and MUST NOT draw the latest buffered envelope.
- R4: If no valid bracket exists, only the closest earlier envelope within 2000 ms of compensated media time MAY be rendered.
- R5: If no sufficiently recent earlier envelope exists, the live AI canvas MUST be cleared; unmatched latest/future metadata MUST NOT be rendered.
- R6: Existing timestamp bracketing, interpolation, generation/frame ordering and lag compensation remain unchanged.
- R7: Detection, tracking, speed, PassageEngine, API/storage schemas, Road behavior and media/security topology MUST remain unchanged.

## Acceptance criteria

- AC-001: Water source contains `if(raw==null){clearLive();return}` and no raw-null latest-buffer draw path.
- AC-002: The no-bracket path draws only `closestEarlierEnvelope(mediaMs)` when capture time is at least `mediaMs-2000`; otherwise it calls `clearLive()`.
- AC-003: No unconditional `drawLive(liveBuffer[liveBuffer.length-1])` fallback remains in Water `renderForVideoFrame()`.
- AC-004: `SeaSpeedLiveSync.bracketForMedia`, `maxGapMs:500`, interpolation and existing lag compensation remain present.
- AC-005: Exactly one `new Hls(` remains and it attaches to `waterMainVideo`; Worker OFF clears Water AI overlay without touching HLS.
- AC-006: Exact changed-file review proves no worker/API/Road/shared-live-sync/media-topology source changes.
- AC-007: Required repository/SDD/Change Contract validation, exact-head CI, exact-green-head merge, exact-main Quality, protected VPS deployment and authenticated visual acceptance complete.

## NFR assessment

- NFR-071-001 | Area: RELIABILITY | Target: never knowingly draw temporally unmatched Water AI metadata | Validation: static source contracts plus authenticated production observation | Evidence: Water source/test and runtime acceptance | Status: CONCERNS
- NFR-071-002 | Area: COMPATIBILITY | Target: preserve one-HLS lifecycle and existing Water Worker metadata-only behavior | Validation: structural contracts and full Quality | Evidence: source/test/CI | Status: PASS
- NFR-071-003 | Area: SCOPE | Target: zero worker/API/Road/live-sync/media-topology change | Validation: exact changed-file review | Evidence: PR diff | Status: PASS
- NFR-071-004 | Area: USABILITY | Target: a vessel may temporarily have no box during sync gaps, but must not show a confidently misplaced stale box | Validation: authenticated production visual inspection | Evidence: runtime acceptance | Status: CONCERNS

## Runtime feedback

- Reported production symptom: Water bbox can appear beside a vessel while Road appears stable.
- Root cause for Task 1: Water fail-open renderer could draw latest metadata when media-time matching failed.
- Task 2 unified speed semantics and Task 3 detection/track recall remain explicitly deferred in #346.
