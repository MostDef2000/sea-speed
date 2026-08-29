# Feature Specification: Water media-time provenance

- Feature: 073-water-media-time-provenance
- Issue: #346
- Status: ACTIVE
- Owner outcome: Water AI detections render on the corresponding visible vessel even when HLS does not expose a trustworthy absolute program timestamp; unmatched metadata remains fail-closed.
- Authorization: Task 1B `OUTCOME APPROVED`, base `4ed8c5e39c7d1e5fe5c9bf1fbd84bb87835e835e`.

## Product outcome

`/sea-speed/` keeps one continuous Water HLS player and the metadata-only AI canvas. Water overlay selection MUST stop treating Worker `capture_time_unix_ms` (`worker_receive_utc`) as if it were the browser HLS absolute media clock. Instead, when Water live metadata exists, the selector projects the browser's current HLS distance-to-live-edge onto the Worker capture timeline and selects/interpolates the envelope for that relative target. If no finite live-edge latency or valid target envelope exists, the overlay remains clear. Road synchronization is unchanged.

## User scenarios

### Scenario 1 - HLS absolute program time absent

Given Worker is online and emits Water detections, and HLS has no valid absolute program date time, but the player exposes finite live-edge latency, Water derives `targetCapture = newestWorkerCapture - playbackLatency` and renders the same-generation bracket for that target.

### Scenario 2 - Browser and Worker clocks differ

Given browser wall clock and Worker wall clock have an arbitrary fixed offset, Water selection remains stable because only relative HLS latency is projected onto the Worker capture timeline.

### Scenario 3 - No trustworthy relative latency

Given neither hls.js latency nor native seekable-edge latency is finite and bounded, Water clears the AI canvas rather than drawing the newest metadata item.

### Scenario 4 - Road

Road continues to use its existing absolute-media-time synchronization behavior and receives no behavior change from the Water-specific resolver.

### Scenario 5 - Worker lifecycle

Worker OFF clears Water metadata while HLS continues. Worker ON resumes fresh metadata; no HLS source switch or reconnect is introduced by this feature.

## Requirements

- R1: Water MUST retain exactly one HLS player on `waterMainVideo`.
- R2: Water live metadata remains `worker_receive_utc`; the frontend MUST NOT assume it shares an absolute clock with HLS program time.
- R3: For Water buffers, synchronization MUST prefer finite HLS playback latency mapped onto the newest Worker capture timestamp.
- R4: hls.js `latency` is preferred; native `seekable.end - currentTime` is an allowed fallback.
- R5: Relative latency outside `[0, 30s]` or otherwise non-finite MUST be rejected.
- R6: Selection remains same-generation and keeps the existing maximum interpolation-gap bound.
- R7: No unconditional newest-envelope fallback may be introduced.
- R8: Road behavior, Worker source, detector/tracker, ROI, speed/passages, API/storage schema and media/auth/network topology remain unchanged in the implementation if the frontend-only solution is sufficient.

## Acceptance criteria

- AC-001: A Water buffer with 10.0s, 10.2s, 10.4s, 10.6s capture timestamps and 0.5s HLS live latency resolves target 10.1s and interpolates the 10.0/10.2 envelopes.
- AC-002: Applying an arbitrary fixed offset to all Worker capture timestamps produces the same selected envelope identities and interpolation fraction.
- AC-003: Missing, negative, non-finite, or greater-than-30s playback latency fails closed when no valid absolute target exists.
- AC-004: Water page can reach the relative selector when absolute start/program time is absent or invalid; it does not terminate before the selector solely because an optional browser absolute timestamp is unavailable.
- AC-005: Existing no-latest-fallback and bounded stale/future protections remain present.
- AC-006: Road source and behavior are unchanged.
- AC-007: exact-head Repository validation + quality-integration, exact-green-head merge, exact-main Quality and required protected runtime deployment complete.
- AC-008: authenticated production observation with `AI active` and `DETECTIONS/TRACKS > 0` shows bbox on the corresponding vessel and no systematic displaced bbox.

## NFR assessment

- NFR-073-001 | Area: RELIABILITY | Target: positive Water detections remain renderable without optional absolute HLS timestamps | Validation: deterministic relative-timeline tests + production observation | Status: CONCERNS until runtime acceptance.
- NFR-073-002 | Area: SAFETY | Target: no stale/latest guessing when latency cannot be resolved | Validation: fail-closed tests/source contracts | Status: PASS.
- NFR-073-003 | Area: COMPATIBILITY | Target: Road and one-HLS lifecycle unchanged | Validation: exact diff + existing regression suite | Status: PASS.
- NFR-073-004 | Area: PERFORMANCE | Target: no new network poll or decoder loop | Validation: source inspection | Status: PASS.
- NFR-073-005 | Area: SECURITY | Target: no auth/token/topology change | Validation: exact changed-file scope | Status: PASS.

## Production learning

Two runtime-verified frontend releases still produced an empty Water AI canvas while the authenticated UI reported positive detections/tracks. The remaining defect is not detector recall: absolute Water media-time resolution can be unavailable/invalid or semantically incompatible with `worker_receive_utc`. Task 1B replaces that cross-clock assumption with relative live-edge mapping while preserving fail-closed behavior.

## Runtime feedback

- Production release `4ed8c5e39c7d1e5fe5c9bf1fbd84bb87835e835e` reached `runtime_verified` and HLS health checks passed.
- Authenticated Water observation then showed `AI active`, `DETECTIONS=3`, `TRACKS=3` with no rendered bbox, proving the remaining failure is in frontend temporal selection rather than detector availability.
- Task 1B acceptance remains open until the relative live-edge mapping is deployed and a moving vessel with positive detections renders an aligned bbox.
