# Feature Specification: Worker RTSP Runtime Resilience

- Feature: 008-worker-rtsp-runtime-resilience
- Issue: #159
- Status: Draft
- Owner outcome: Keep the AI Worker continuously ingesting the production RTSP camera stream and make exact-release activation fail closed when real frame/state progression is absent.

## Product outcome

The production Ubuntu Worker must continue producing fresh AI frames from the configured RTSP camera instead of remaining superficially `running` while media ingestion is stalled. A release activation must only become authoritative after the exact candidate proves frame and state-post progression; otherwise the previously active release must be restored automatically when available. The calibration ownership behavior already approved for Issue #159 remains unchanged.

## User scenarios

### Scenario 1 - Continuous RTSP ingestion

Given the production camera RTSP endpoint is delivering frames, when the Ubuntu Worker runs, then the Worker continuously advances annotated frames and state posts without depending on the in-process PyAV RTSP reader that stalled in production.

### Scenario 2 - Media reader stall

Given the FFmpeg RTSP subprocess stops producing frame bytes without exiting, when the configured frame timeout expires, then the Worker terminates and recreates the FFmpeg reader within a bounded restart budget instead of blocking indefinitely.

### Scenario 3 - Exact release activation

Given an exact quality-approved Worker release is activated over a previous active release, when the candidate service starts, then activation is committed only after the candidate heartbeat reports the exact source commit and both frame progression and successful state-post progression increase.

### Scenario 4 - Failed candidate activation

Given a previous active release is available, when candidate unit activation, service startup, exact ExecStart validation, or runtime progression fails, then the updater restores the previous unit and service and leaves the previous active-source marker authoritative.

## Requirements

- FR-001: The Ubuntu production Worker MUST use an FFmpeg subprocess with RTSP-over-TCP for configured `rtsp://` media input.
- FR-002: RTSP frame reads MUST have a bounded timeout and MUST recreate the FFmpeg reader after timeout, EOF, or read failure, up to a bounded restart budget.
- FR-003: Non-RTSP media input MUST retain the existing worker media-reader behavior.
- FR-004: Worker logs MUST use the existing redacted media label and MUST NOT print credential-bearing RTSP URLs or FFmpeg stderr containing those URLs.
- FR-005: Critical Worker Python runtime packages MUST be version-pinned, and the canonical CUDA Worker MUST require the exact `torch==2.13.0+cu130` and `torchvision==0.28.0+cu130` pair before release preparation completes.
- FR-006: `update-exact.sh --activate` MUST require an exact-SHA heartbeat in `running` phase followed by increasing `frame_progress_sequence` and increasing `state_post_success_count` with a successful latest state post.
- FR-007: If candidate activation or its runtime progression gate fails and a previous active release exists, the updater MUST automatically restore the previous systemd unit and service without moving the active-source marker to the failed candidate.
- FR-008: Worker ROI filtering and calibrated speed computation MUST remain unchanged, and the Worker MUST continue to omit ROI/speed-line calibration drawing from annotated image pixels.
- FR-009: VPS, API, authentication, camera source configuration, and public schemas MUST remain unchanged by this source change.

## Acceptance criteria

- AC-001: Contract tests prove the Ubuntu systemd Worker entrypoint selects FFmpeg RTSP-over-TCP, bounded frame reads, and bounded reader recreation without PyAV in the production entrypoint.
- AC-002: Runtime requirements and installer checks reject drift from the approved critical package versions and exact CUDA torch/torchvision pair.
- AC-003: Updater contract tests prove candidate activation includes an exact runtime progression gate and an automatic previous-release restore path.
- AC-004: On production rollout, the exact new Worker release remains online with continuously changing frames/state posts for the acceptance window and no baked ROI/A/B calibration geometry.
- AC-005: After the same exact release reaches the VPS, saved frontend ROI and A/B geometry remain visible once in normal mode and remain editable/clearable under the existing calibration ownership contract.

## Compatibility and boundaries

- Stable public interfaces: existing `/sea-speed` UI/API/state/event interfaces, `HLS_URL`, Worker environment, calibration data, detection metadata, and server-pull operator flow.
- Out of scope: camera firmware/source URL changes, VPS/nginx/auth topology changes, detection/tracking/speed formula changes, API/schema migrations, Windows Worker behavior changes, and production mutation before fresh exact-SHA production approval.
- Security constraints: protected Worker secrets remain outside Git; credential-bearing media URLs must not be emitted to Worker logs; exact-SHA and protected-token release verification remains fail-closed.

## Runtime feedback

- Runtime acceptance: PENDING
- Accepted production behavior: PENDING
- Regressions/learning: Production proved both the candidate and rollback Worker could stall after initial RTSP frames through the in-process PyAV path while a direct FFmpeg TCP probe of the same endpoint progressed continuously.
- Follow-up work: NONE YET
