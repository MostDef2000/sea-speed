# Feature Specification: Road operator Water-interface parity

- Feature: 070-road-water-interface-parity
- Issue: #343
- Status: ACTIVE
- Owner outcome: Road operators get the same compact operator composition and media lifecycle already accepted on Water, while all Road-specific data, controls, APIs and analytics semantics remain fixed to `road1` / `road-v1`.
- Authorization: `issue-343-road-water-interface-parity-v1`, base `01eec30cf162b922fc076dd5545ae8a2b114df4e`.

## Product outcome

`/sea-speed/road/` adopts the current Water dashboard hierarchy: compact lighthouse-first single-row header, dominant main camera, independent crossing-statistics and recent-events cards in the right rail, and one default-collapsed `Разметка и калибровка` area below the camera containing the existing Road ROI, speed lines, counting line and speed calibration controls plus diagnostics. The separate `LIVE CAMERA / Чистый поток` card is removed.

The visible Road camera becomes one continuous HLS player. The Road AI worker is an independent metadata layer: Worker OFF leaves the same HLS video advancing and clears AI metadata; Worker ON resumes fresh live metadata on the same video without reconnecting or switching media sources.

## User scenarios

### Scenario 1 - Observe Road using the Water composition

Given an authenticated operator opens `/sea-speed/road/`, the compact header and large Road camera are visible first, there is no separate clean-stream card, and crossing statistics plus the latest Road events are visually independent cards to the right.

### Scenario 2 - Stop and start Road AI without interrupting video

Given Road HLS is playing, when the operator stops the Road AI worker, the same video continues advancing and AI boxes disappear. When the worker starts again, fresh Road live envelopes resume over the already-playing video without HLS recreation.

### Scenario 3 - Edit Road geometry under the camera

The default-collapsed `Разметка и калибровка` block exposes the existing ROI, speed-line, counting-line and speed-factor operations without changing API payloads, formulas or persistence semantics.

### Scenario 4 - Review Road crossings and events

The right rail presents Road crossing totals/class breakdown sourced from existing `road1` state and up to three existing Road detection events. Registry navigation remains domain-scoped to Road.

### Scenario 5 - Recover media independently of AI

Real HLS media/network failures use the existing bounded retry/recovery lifecycle on the visible Road video. Worker lifecycle never triggers media reconnect. Annotated snapshot refresh is allowed only as bounded fallback when HLS playback is unhealthy.

### Scenario 6 - Use Road on mobile

On narrow portrait viewports the order is header/status -> main camera -> crossings -> latest events -> controls/diagnostics, matching the accepted Water hierarchy.

## Requirements

- R1: Road MUST use the same compact lighthouse-first single-row header/status/session composition as Water while retaining reciprocal `Вода` navigation.
- R2: The visible `clean-live` / `Чистый поток` card and second Road HLS consumer MUST be removed.
- R3: `roadMainVideo` MUST be the sole Road `<video>` element and sole HLS media target.
- R4: HLS watchdog/recovery MUST bind to `roadMainVideo`; the existing preview start/stop API remains the only Road stream-control surface.
- R5: Road Worker Start/Stop MUST NOT create, destroy, reconnect, pause or switch the HLS source. Worker OFF clears stale Road live-buffer/canvas state; Worker ON resumes fresh metadata.
- R6: `last_overlay_url` MUST NOT refresh cyclically while HLS advances; it MAY be used as a changed-URL fallback while playback is unhealthy.
- R7: Road ROI, speed-lines, crossing-line and calibration API/persistence semantics MUST remain unchanged.
- R8: Existing Road crossing data and up to three Road events MUST be presented as separate right-rail cards; no new backend endpoint is introduced.
- R9: Water frontend, API/worker source, live-sync module, detection/tracking/YOLO, formulas/schemas, camera/RTSP, MediaMTX/nginx/Auth/ZeroTier and private topology MUST remain unchanged.

## Acceptance criteria

- AC-001: Road source contains the Water-parity layout markers: `single-row-header`, `road-operator-workspace`, `primary-camera`, `right-information-rail`, `crossing-stats`, `recent-events`, `under-camera-controls`, `collapsible-state`, and `collapsible-log`.
- AC-002: Road contains exactly one `<video id="roadMainVideo">`; `clean-live`, `Чистый поток`, `cleanPreviewVideo` and a second HLS constructor are absent.
- AC-003: Exactly one `new Hls(...)` is created and attached to `roadMainVideo`; watchdog/recovery progress and media listeners use that same video.
- AC-004: Worker OFF clears Road AI overlay state while HLS remains intact; Worker ON does not invoke Road stream connect/disconnect.
- AC-005: Healthy HLS suppresses periodic `last_overlay_url` refresh; snapshot fallback is bounded to unhealthy playback and changed URLs.
- AC-006: Existing Road endpoint constants and fixed worker target `road1` remain unchanged; no protected Water/API/worker/live-sync/media-topology source diff exists.
- AC-007: `Разметка и калибровка` is a default-closed details block under the camera and preserves all existing editor control IDs and behavior.
- AC-008: Right rail independently renders Road crossing totals/class breakdown and up to three Road events plus Road-scoped registry navigation.
- AC-009: Required repository/SDD/Change Contract validation, exact-head CI, exact-green-head merge, exact-main Quality, protected VPS deployment and authenticated Road Worker OFF->ON->OFF continuity acceptance complete without Ubuntu Worker source deployment.

## NFR assessment

- NFR-070-001 | Area: RELIABILITY | Target: one Road browser HLS decoder/lifecycle; Road Worker lifecycle cannot restart video | Validation: static frontend contract plus production OFF->ON->OFF observation | Evidence: Road frontend/tests/runtime acceptance | Status: CONCERNS
- NFR-070-002 | Area: PERFORMANCE | Target: remove duplicate Road HLS consumer and regular hidden overlay JPEG refresh during healthy playback | Validation: source contract and runtime inspection | Evidence: one HLS constructor/media target; bounded fallback | Status: CONCERNS
- NFR-070-003 | Area: COMPATIBILITY | Target: zero Water/API/worker/schema/live-sync/media-topology change and unchanged Road analytics formulas | Validation: exact changed-file review plus Quality | Evidence: PR diff and CI | Status: PASS
- NFR-070-004 | Area: USABILITY | Target: Road mirrors accepted Water desktop/mobile hierarchy and controls are default-collapsed | Validation: structural contract plus authenticated production visual inspection | Evidence: frontend contract and runtime screenshot/acceptance | Status: CONCERNS

## Runtime feedback

- Water reference layout and single-HLS lifecycle: previously accepted in production.
- Road parity runtime acceptance: PENDING.
- CPU/transcoding topology remains separate work and is explicitly outside #343.
