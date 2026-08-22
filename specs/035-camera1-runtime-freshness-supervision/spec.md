# Feature Specification: Camera 1 Runtime Freshness Supervision

- Feature: 035-camera1-runtime-freshness-supervision
- Issue: #255
- Status: Source implementation
- Authorization base: `9b569dc84a6fb87d9e48d75d84ed65f260da1ede`
- Owner outcome: Camera 1 must self-recover when the VPS H264 producer remains active but stops advancing HLS, without waiting for a deploy or operator SSH.

## Product outcome

Continuously supervise the accepted Camera 1 H264 compatibility output on the VPS. A valid but non-advancing local HLS playlist is treated as stale output, not as service health. When the fixed Ubuntu private relay is readable, the supervisor may restart only `sea-speed-camera1-h264.service` and must prove HLS progression after that restart. Healthy HLS is a no-op. An unreadable relay, malformed HLS, or cooldown window fails closed without a restart.

This feature complements Issue #226. The existing privileged reconcile remains the deployment-time freshness gate; this feature closes the lifetime gap between deployments.

The fixed topology remains:

`physical camera -> Ubuntu private RTSP relay -> VPS H264 producer -> 127.0.0.1:18889/cam1/ -> nginx -> authenticated /sea-speed/media/cam1/index.m3u8`.

## Incident evidence

On 2026-08-22 the VPS reported `sea-speed-camera1-h264.service=active` for more than six hours while local HLS remained at media sequence `405` / `seg_000410.m4s`. The playlist `Last-Modified` corresponded to about 20:55 Vladivostok while the browser showed a loop from about 20:54. A simultaneous fixed RTSP frame probe against `rtsp://10.123.239.102:8554/cam1` passed. FFmpeg logs immediately before output stopped contained HEVC reference/GOP decoding errors. The producer therefore entered a live-process/stale-output state that systemd `Restart=` cannot detect.

## User scenarios

### Scenario 1 - Healthy stream

Given local Camera 1 HLS advances across the fixed sampling interval, when the timer invokes the watchdog, then it emits a no-op freshness result, does not probe the relay and does not restart any service.

### Scenario 2 - Stale output with healthy relay

Given local HLS is valid but its media sequence is static, no restart cooldown is active, and the fixed private relay produces a decodable frame, when the watchdog runs, then it records a restart attempt, restarts exactly `sea-speed-camera1-h264.service`, verifies that service is active, and succeeds only after post-restart HLS progression is proven.

### Scenario 3 - Stale output with unavailable relay

Given local HLS is static but the fixed relay cannot produce a frame, when the watchdog runs, then it fails without restarting the H264 producer or any other service.

### Scenario 4 - Repeated stale condition

Given a restart attempt occurred less than five minutes earlier and HLS is static again, when the watchdog runs, then it emits cooldown state and performs no relay probe or service restart. This bounds failure amplification and restart storms.

### Scenario 5 - Unsupported caller control

Given the watchdog is invoked by its fixed root-owned systemd service, then CLI arguments, environment overrides, alternate URLs, alternate service names and arbitrary commands are not accepted.

## Functional requirements

- FR-001: The runtime watchdog MUST accept no command-line arguments and MUST expose no environment-variable topology overrides.
- FR-002: The local playlist MUST be exactly `http://127.0.0.1:18889/cam1/index.m3u8`.
- FR-003: Freshness MUST be determined from valid `#EXT-X-MEDIA-SEQUENCE` values sampled across a fixed three-second interval.
- FR-004: Advancing HLS MUST be a no-op and MUST NOT invoke FFmpeg or `systemctl restart`.
- FR-005: Unavailable or malformed local HLS MUST fail closed without a restart.
- FR-006: Static HLS outside cooldown MUST probe exactly `rtsp://10.123.239.102:8554/cam1` using `ffmpeg -rtsp_transport tcp -timeout 10000000` and one decoded frame before any restart.
- FR-007: Relay-probe failure MUST cause failure before any restart.
- FR-008: The only restart target MUST be `sea-speed-camera1-h264.service`; nginx, HLS HTTP, MediaMTX, Authentik and AI worker services MUST remain outside the watchdog command surface.
- FR-009: A successful restart MUST be followed by exact-service active verification and newly advancing HLS; otherwise the watchdog MUST fail.
- FR-010: A restart attempt MUST establish a five-minute cooldown before invoking the restart so a post-restart failure cannot cause a restart storm.
- FR-011: Watchdog executions MUST use a root-owned private state directory and non-blocking lock so overlapping invocations cannot independently restart the producer.
- FR-012: A root-owned oneshot service and timer MUST run the watchdog automatically after activation and repeatedly thereafter; the timer cadence MUST allow normal recovery within 90 seconds of a stale condition becoming observable.
- FR-013: The existing exact-source `install-auth-privilege-boundary.sh` transaction MUST install the watchdog executable and both unit files, daemon-reload systemd, enable/start only the fixed timer, verify timer enabled/active, and restore prior files/timer state on installation failure.
- FR-014: The existing Issue #226 deployment-time privileged recovery MUST remain intact and independent.
- FR-015: Physical camera, Ubuntu relay configuration, ZeroTier topology, MediaMTX mappings, nginx/Auth, browser URL, API/frontend/storage and Water/Road workers MUST not change.
- FR-016: Runtime contour is VPS only. Ubuntu Worker/relay deployment is NOT REQUIRED; the relay is a read-only recovery prerequisite.

## Acceptance criteria

- AC-001: Unit test proves advancing HLS causes zero relay probes and zero restarts.
- AC-002: Unit test proves static HLS plus healthy relay invokes the exact fixed FFmpeg argv and exactly one `systemctl restart sea-speed-camera1-h264.service`, then requires post-restart progression.
- AC-003: Unit test proves relay failure causes no restart.
- AC-004: Unit test proves cooldown suppresses relay probe and restart.
- AC-005: Unit test proves post-restart static HLS fails while retaining cooldown evidence.
- AC-006: Static analysis/test proves the runtime entry point has no selectable URL/service/command and contains no unrelated protected service names.
- AC-007: Unit-file tests prove a root oneshot runs the fixed installed executable and a timer invokes it automatically on a bounded cadence.
- AC-008: Installer tests/static assertions prove exact-source installation owns only the fixed watchdog executable/service/timer and rollback logic includes their prior state.
- AC-009: Final PR diff is a subset of Issue #255 authorized paths and contains no secret/runtime media.
- AC-010: Required PR Validation and aggregate Quality pass on the exact final PR head before expected-head merge.
- AC-011: Exact-main push Quality succeeds before runtime policy evaluation.
- AC-012: Production exact-source bootstrap reports watchdog installed and timer active under standing production delegation / canonical execution controls.
- AC-013: Production acceptance reproduces or observes `active producer + static HLS`, then demonstrates autonomous recovery to advancing local and authenticated Camera 1 within 90 seconds, with no restart of protected unrelated services.

## NFR assessment

- NFR-001 | SECURITY | Target: no caller-controlled privileged topology or arbitrary command | Validation: no-argument entry point, fixed constants, unit/install tests | Status: PASS
- NFR-002 | FAIL_CLOSED | Target: no restart from malformed HLS or unavailable relay; post-restart freshness mandatory | Validation: focused unit tests | Status: PASS
- NFR-003 | BLAST_RADIUS | Target: only fixed H264 service restart | Validation: captured argv and forbidden-name assertions | Status: PASS
- NFR-004 | AVAILABILITY | Target: autonomous recovery between deployments, normally <=90s | Validation: timer cadence + production incident replay/acceptance | Status: CONCERNS pending runtime acceptance
- NFR-005 | STORM_CONTROL | Target: no repeated restart loop after unsuccessful recovery | Validation: 300-second persisted cooldown test | Status: PASS
- NFR-006 | CONCURRENCY | Target: one active watchdog transaction | Validation: non-blocking root-private file lock | Status: PASS
- NFR-007 | PROVENANCE | Target: installed supervisor bytes come from exact authorized checkout and installation rollback is available | Validation: existing exact-source installer identity checks plus watchdog install/rollback coverage | Status: PASS
- NFR-008 | BACKWARD_COMPATIBILITY | Target: preserve Issue #226 reconcile recovery and all accepted camera/browser topology | Validation: no helper/nginx/MediaMTX/Ubuntu changes required | Status: PASS
