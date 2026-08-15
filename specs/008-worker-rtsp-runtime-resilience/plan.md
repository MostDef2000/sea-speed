# Implementation Plan: Worker RTSP Runtime Resilience

- Specification: specs/008-worker-rtsp-runtime-resilience/spec.md
- Issue: #159
- Status: Draft

## Architecture

Keep the existing detection/tracking/calibration worker module intact and isolate the production Ubuntu media remediation in a new `worker/ubuntu_worker_entrypoint.py`. The systemd unit runs this entrypoint through the existing observed runner. For RTSP input the entrypoint replaces only `start_media_reader` with a resilient FFmpeg raw-video reader using TCP, bounded `select`/`os.read` frame acquisition, and bounded FFmpeg subprocess recreation. For non-RTSP input it delegates to the existing worker reader. This avoids changing Windows Worker behavior and preserves the already merged calibration ownership logic.

Pin the critical top-level Worker runtime packages to the versions observed on the previously working runtime. Keep CUDA torch/torchvision outside the generic requirements file, but require the exact CUDA 13.0 pair before runtime requirements are installed.

Add a non-secret runtime progression verifier that reads the observed-runner heartbeat. During `update-exact.sh --activate`, back up the previous unit, start the candidate, verify exact ExecStart, then require exact-SHA frame and state-post counters to advance. Only after that gate passes is `active-source-commit` moved to the candidate. Any activation/gate failure restores the previous unit/service when available.

## Decisions

### D-001 - Use FFmpeg TCP for Ubuntu production RTSP

- Decision: Route `rtsp://` input through a supervised FFmpeg subprocess using `-rtsp_transport tcp`.
- Reason: The exact production RTSP endpoint advanced continuously through FFmpeg TCP while both old and candidate PyAV-based Worker releases stalled after initial frames.
- Alternatives rejected: Continuing PyAV with more point probes would retain the demonstrated failure mode; changing the camera/source URL would modify an unrelated production boundary.

### D-002 - Use an Ubuntu-only entrypoint wrapper

- Decision: Override the core worker's media-reader function from an Ubuntu production entrypoint rather than rewriting the shared worker algorithm.
- Reason: It confines the remediation to the failing Ubuntu runtime while preserving detection, tracking, speed, calibration, and Windows behavior.
- Alternatives rejected: A broad rewrite of `hls_motion_yolo_worker_events.py` would increase regression surface for a media-runtime defect.

### D-003 - Bound read stalls and recreate FFmpeg

- Decision: Read rawvideo with a configured timeout and recreate FFmpeg after timeout/EOF/read failure up to a bounded restart count.
- Reason: A live process that no longer advances frames is unhealthy even when systemd reports `active`.
- Alternatives rejected: Unbounded blocking reproduces the production failure; relying only on systemd process liveness cannot detect it.

### D-004 - Commit activation only after progression

- Decision: Keep the previous active marker authoritative until the candidate proves exact-SHA frame and state-post progression; restore the previous unit/service on failure.
- Reason: Exact unit identity and `systemctl active` were insufficient production gates.
- Alternatives rejected: Manual post-deploy diagnosis leaves a failed candidate active and creates repetitive operator recovery work.

### D-005 - Pin critical runtime versions

- Decision: Pin Ultralytics, OpenCV, NumPy, requests, and python-dotenv, and require the exact known CUDA torch/torchvision pair.
- Reason: The failed release preparation demonstrated unqualified dependency drift between release environments.
- Alternatives rejected: Floating top-level dependencies make exact-SHA source releases non-reproducible at runtime.

## Affected contours

- Repository: Ubuntu Worker entrypoint, Worker service template, exact updater, manual installer/runtime requirements, runtime progression verifier, focused tests, and this SDD.
- VPS: No source change in this remediation; later rollout of the already merged frontend calibration behavior remains required on the same new exact release SHA.
- Ubuntu worker/relay: Worker media ingestion and exact-release activation behavior change; relay/camera source configuration does not.
- Windows worker/AI: NONE; shared worker detection/tracking/calibration logic remains unchanged.
- Public interfaces: NONE.

## Validation

- Static/CI: Python compile/contracts, shell syntax, repository/SDD validation, exact updater/manual-install/systemd tests, worker RTSP/calibration contract tests, normal PR/quality/package gates.
- Integration: Verify the branch changes only the authorized runtime/deployment/SDD scope and preserves calibration computation while removing baked calibration rendering.
- Runtime acceptance: Worker first on the exact merged SHA: exact activation gate passes, worker stays online, frames/state posts continue advancing through the acceptance window, AI overlay is fresh, and no baked ROI/A/B appears. Then deploy the VPS frontend on the same exact SHA and perform one browser acceptance of persistent single-owner calibration geometry.

## Rollout and rollback

- Rollout: Merge only after source CI. Obtain fresh `PRODUCTION APPROVED <merged-sha>`. Deploy Worker first with repo-owned exact updater. Proceed to VPS only after Worker runtime/visual acceptance.
- Rollback: Updater automatically restores the previous Worker release on candidate activation-gate failure. After successful activation, use the existing repo-owned exact rollback command if a later runtime regression requires rollback. VPS retains its independent previous-release rollback boundary.

## Runtime feedback

- Actual architecture after acceptance: PENDING
- Differences from plan: Implementation uses an Ubuntu-only entrypoint wrapper so the shared worker module and Windows behavior remain unchanged while satisfying the approved FFmpeg production-ingestion outcome.
- Deferred cleanup: Operational documentation may be refreshed after production acceptance if the final runtime behavior differs from existing manual-update prose.
