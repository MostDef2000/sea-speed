# Feature Specification: Water operator dashboard redesign

- Feature: 069-water-operator-redesign
- Issue: #326
- Status: ACTIVE
- Owner outcome: Water operators get one compact dashboard where the synchronized AI feed stays dominant, overlay editors sit directly below it, and crossing statistics plus recent passages are visible without a redundant clean-stream card.
- Refinement authorization: `issue-326-water-single-hls-v2`, base `779aed5868de67cbd106693c76db4dc77915627d`.

## Product outcome

`/sea-speed/` keeps the approved Water Operator composition and uses one continuous protected Camera 1 HLS player. AI processing is an independent metadata layer: with the Water worker stopped, the same video continues without AI boxes; with the worker running, timestamped AI boxes are drawn on `liveOverlayCanvas` over that same video without reconnecting or switching media sources. ROI, speed-line editing, speed calibration, crossing-line semantics, authenticated navigation, diagnostics, crossing statistics and passage data sources remain unchanged.

## User scenarios

### Scenario 1 - Observe the Water feed

Given an authenticated operator opens `/sea-speed/`, the compact header and large Water camera are visible first, there is no separate `LIVE CAMERA / Чистый поток` card, and only one browser video/HLS playback pipeline is active.

### Scenario 2 - Stop and start AI without interrupting video

Given Camera 1 HLS is playing, when the operator stops the Water AI worker, the video continues advancing and the AI canvas is cleared. When the operator starts the worker again, fresh SSE/live envelopes resume on the same video without HLS recreation or source switching.

### Scenario 3 - Recover media independently of AI

Given the HLS player has a real network/media stall, the existing bounded reconnect/recovery logic operates on `waterMainVideo`. AI worker state must not trigger media reconnect. The legacy annotated snapshot may be used only as a bounded fallback while the HLS player is not healthy; it must not be fetched cyclically while healthy HLS playback advances.

### Scenario 4 - Edit Water overlays below the camera

Given the operator needs to adjust ROI, speed lines, counting line, or speed calibration, the existing API operations and editor semantics remain under the main camera and crossing statistics stay separate from the line editor.

### Scenario 5 - Review crossings and passages

Existing `cam1` crossing-summary and passages endpoints remain the only sources for the independent `Пересечения` and `Последние проходы` cards, including the direct Water crossing-history link.

### Scenario 6 - Use the dashboard on mobile

On iPhone Pro / Pro Max portrait viewports the existing approved hierarchy and touch usability remain intact.

## Requirements

- R1: `/sea-speed/` MUST keep the approved compact lighthouse-first header and authenticated navigation/status controls.
- R2: The visible `clean-live` / `Чистый поток` card MUST remain absent.
- R3: `waterMainVideo` MUST be the only Water `<video>` element and the only HLS media target. The legacy hidden `video#video` / `stream-probe` consumer MUST be removed.
- R4: The HLS reconnect/watchdog lifecycle MUST use `waterMainVideo` for playback progress, `waiting`, `stalled`, `ended`, decode/network recovery and reconnect decisions.
- R5: Worker Start/Stop MUST NOT create, destroy, reconnect, pause, or switch the HLS source. Worker OFF clears stale AI live-buffer/canvas state; Worker ON resumes drawing fresh metadata envelopes.
- R6: `last_overlay_url` MUST NOT be refreshed on the regular state-poll cadence while HLS is healthy. It MAY be loaded once per changed fallback URL while playback is unavailable/stalled.
- R7: Existing `live-sync.js`, lag/interpolation timing constants, Water live API/SSE semantics, worker code, API code and media topology MUST remain unchanged.
- R8: ROI, speed lines, crossing-line editor, calibration, `State JSON`, `Operator log`, crossing statistics, passages and registry links MUST preserve their existing behavior and approved layout.
- R9: `frontend/sea-speed/road/index.html`, detection/tracking algorithms, speed/crossing formulas, API/storage/telemetry schemas, authentication, nginx/MediaMTX/ZeroTier and Camera/FFmpeg topology MUST remain unchanged.

## Acceptance criteria

- AC-001: Water source contains exactly one video element, `id="waterMainVideo"`; `id="video"` and `class="stream-probe"` are absent.
- AC-002: Exactly one `new Hls(...)` instance is created for Water playback and it attaches to `waterMainVideo`; compatibility globals may alias that same instance but MUST NOT create a second player.
- AC-003: Stream watchdog/recovery event listeners and playback progress calculations are bound to `waterMainVideo`.
- AC-004: Worker OFF immediately clears Water AI overlay state while HLS playback remains intact; Worker ON does not invoke HLS connect/disconnect and fresh live envelopes resume.
- AC-005: Healthy HLS playback suppresses periodic `last_overlay_url` image refresh; fallback image loading is bounded to unhealthy playback and changed fallback URLs.
- AC-006: Existing Water live-sync interpolation/bracketing markers and timing constants remain unchanged; Road/API/worker/media topology have zero source diff.
- AC-007: Existing approved dashboard layout, collapsible controls, crossings, passages, registry links and mobile baseline remain green in contract tests.
- AC-008: Repository/SDD/change-contract validation, required unit/quality CI, exact-green-head merge, exact-main Quality, protected VPS deployment and authenticated production Worker OFF→ON→OFF continuity acceptance complete without Ubuntu Worker deployment.

## NFR assessment

- NFR-069-001 | Area: RELIABILITY | Target: one browser HLS decoder/lifecycle for Water; AI worker lifecycle cannot restart the video | Validation: static contract + production Worker OFF→ON→OFF observation | Evidence: `frontend/sea-speed/index.html`, `tests/test_frontend_contract.py`, runtime acceptance | Status: CONCERNS
- NFR-069-002 | Area: PERFORMANCE | Target: no duplicate Water HLS playlist/segment consumer and no regular hidden overlay JPEG refresh during healthy playback | Validation: source contract and browser/runtime inspection | Evidence: one HLS constructor/media target; bounded fallback logic | Status: CONCERNS
- NFR-069-003 | Area: COMPATIBILITY | Target: zero Road/API/worker/schema/media-topology change and unchanged live-sync timing algorithm | Validation: exact changed-file review plus existing test suite | Evidence: PR diff and Quality | Status: PASS
- NFR-069-004 | Area: USABILITY | Target: approved desktop/mobile dashboard and collapsible calibration controls remain unchanged | Validation: existing structural contracts and authenticated production visual check | Status: PASS

## Runtime feedback

- Prior redesign visual acceptance: operator accepted.
- Single-HLS refinement runtime acceptance: PENDING.
- Known separate follow-up: VPS CPU/transcoding saturation investigation remains #335 and is explicitly out of this refinement.
- Follow-up work outside this authorization requires a separate scope cycle.
