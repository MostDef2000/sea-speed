# Spec: Road video overlay sync — clean HLS + timestamped AI canvas (main window)

- Issue: #312
- Status: ACTIVE
- Runtime contour: MIXED (VPS + Ubuntu Worker/relay)

## Product outcome

Preserve the existing clean Road live stream wherever it currently exists; make the Road main window a synchronized composition of that protected clean HLS video and a timestamp-buffered AI canvas. Worker binds each Road detection to an honest per-frame capture timestamp; API transports it as `sea_speed_road_live_v2` with receipt time and monotonic sequence; VPS HLS carries `EXT-X-PROGRAM-DATE-TIME`; browser buffers metadata and renders only a valid time-bracket for the video frame actually displayed, interpolating smoothly and clearing on any uncertain/stale condition. Clean stream never shows baked boxes; no second annotated video stream is introduced.

## User scenarios

- Operator opens Road: clean HLS plays; AI boxes/IDs/speed glide smoothly over the same video, p95 skew ≤150ms and max ≤250ms across resize/fullscreen/DPR=1,2, no lead/lag jitter.
- Metadata delayed 0–500ms or SSE reconnects: buffered history keeps correct bracket, HLS continues, canvas does not extrapolate into future.
- Worker restarts: generation bump discards old tracks immediately, first fresh envelope renders on next matching video frame.
- Stale/uncertain (>1s, out-of-order, wrong generation, missing PDT/clock): overlay clears, clean HLS remains visible.
- Anonymous unauthenticated live POST or wrong private peer/path: rejected fail-closed (403/404), no data stored.

## Requirements

- R1: Honest per-frame Road timing — worker captures `capture_time_unix_ms` at the production FFmpeg reader boundary (worker receive/decode), plus `processed_time_unix_ms`, `generation`, `frame_no`; rawvideo latest-complete-frame slot never returns partial bytes; coalesces to newest complete frame.
- R2: Live envelope v2 (`sea_speed_road_live_v2`) immutable normalized, carries exact `road1/road-v1/road`, frame identity, `capture_time_unix_ms`/`processed_time_unix_ms`/`timestamp_semantics=worker_receive_utc`, dimensions, normalized `x*_norm`/`y*_norm`, `speed_kmh`, crossings snapshot; deep-immutable; generation stable per process.
- R3: Authenticated bounded SSE — private `POST /api/analytics/road1/live` exact peer/method/path, `require_auth()` bearer, full schema/size validation, `deque(maxlen=120)` + monotonic `live_seq`, SSE `id:` + bounded replay + keepalive, disk-free, non-blocking to inference.
- R4: HLS time binding — existing VPS preview FFmpeg retains all encode settings and adds `program_date_time` flag so playlist carries `#EXT-X-PROGRAM-DATE-TIME`.
- R5: Timestamp-synchronized browser render — SSE `/sea-speed/api/analytics/road1/live/stream` mapped to internal `/api/.../stream`, `hls.js` `playingDate` → displayed media UTC, bounded metadata buffer > max HLS latency (≈15s), `requestVideoFrameCallback` presentation-time lookup, binary-search bracket, interpolate only same-generation same-track_id within bounded gap and bounded clock uncertainty, never extrapolate, ±1 CSS px content-box alignment.
- R6: Fail-closed fallback — valid video + valid bracket → draw; otherwise clean HLS with empty canvas; no video → existing state JPEG fallback; never draws latest-known over unrelated frame.

## NFR assessment

- NFR-058-001 | Area: usability | Target: overlay alignment ±1 CSS px across 1920/1080 content-box resize/fullscreen/DPR=1,2 | Validation: canvas transform unit + runtime manual | Evidence: tests/test_frontend_contract.py | Status: PASS
- NFR-058-002 | Area: reliability | Target: stale/uncertain >1s or generation mismatch clears overlay immediately | Validation: browser TTL/generation unit tests | Evidence: tests/test_frontend_contract.py, tests/test_road_overlay_sync.py | Status: PASS
- NFR-058-003 | Area: performance | Target: worker effective FPS and p95 inference not regressed >5%; SSE sustains ≥8 env/s at 10 FPS without blocking | Validation: deterministic unit + synthetic integration | Evidence: tests/test_detection_runtime_optimization.py, tests/test_road_overlay_sync.py | Status: PASS
- NFR-058-004 | Area: reliability | Target: p95 skew ≤150ms, max ≤250ms HLS-displayed-frame vs AI bracket, otherwise canvas cleared | Validation: Node-backed browser sync math + synthetic runtime | Evidence: tests/test_road_overlay_sync.py | Status: PASS
- NFR-058-005 | Area: security | Target: private live POST authenticated, exact peer/method/path allowlist, anonymous denied, public SSE under Authentik | Validation: auth contract tests | Evidence: tests/test_sea_speed_auth_v1.py | Status: PASS
- NFR-058-006 | Area: observability | Target: envelope carries honest capture/processed timestamps, generation, frame_no, worker commit, separate FPS fields | Validation: schema/telemetry tests | Evidence: schemas/telemetry.schema.json, tests/test_telemetry_contract.py | Status: PASS

## Acceptance criteria

- AC-001: Worker per-frame slot presents only complete frames with honest `capture_time_unix_ms`; live envelope is `sea_speed_road_live_v2` immutable deep-copy with correct identity and timestamp semantics.
- AC-002: Private `POST /api/analytics/road1/live` requires exact peer/method/path + bearer auth, validates schema/size, stores into bounded deque with monotonic sequence; missing/wrong token → 403.
- AC-003: Internal SSE `/api/analytics/road1/live/stream` emits `id:` sequence, replays bounded history, survives deque rollover (>120 inserts) and slow clients without memory growth; VPS HLS playlist contains `#EXT-X-PROGRAM-DATE-TIME`.
- AC-004: Browser buffers live metadata by media UTC (`playingDate`/`getStartDate`), draws only valid bracket on `requestVideoFrameCallback`, interpolates same-generation same-track_id within bounded gap, clears otherwise, ±1px alignment.

## Runtime feedback

- Observed defect 2026-08-25: `POST live failed: HTTP 404` — private nginx allowlist omits `/api/analytics/road1/live`; SSE deque-len tracking freezes after 120; HLS lacks PDT; current interpolation uses arrival time not media time.
