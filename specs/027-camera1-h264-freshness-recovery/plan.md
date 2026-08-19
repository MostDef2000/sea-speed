# Implementation Plan: Camera 1 H264 Freshness Recovery

- Specification: specs/027-camera1-h264-freshness-recovery/spec.md
- Issue: #226
- Status: Source implementation

## Architecture

The accepted Camera 1 browser topology remains unchanged: Ubuntu private RTSP relay `cam1` feeds the VPS H264 compatibility producer, its local HLS is served at `127.0.0.1:18889/cam1/`, nginx exposes the protected `/sea-speed/media/cam1/` route, and Authentik gates browser access. The observed stale-frame incident is isolated to the VPS H264 compatibility producer because prior bounded diagnostics proved the Ubuntu relay could decode a frame while the local VPS HLS media did not advance.

The narrow implementation extends the already-installed exact-source-bound no-argument privileged helper. Existing Auth v1 `reconcile` remains the canonical privileged stage invoked by `deploy/vps/deploy.sh`. After Auth reconcile succeeds, the helper performs a fixed Camera 1 freshness stage. Healthy local HLS is a no-op. Valid but static local HLS triggers a fixed one-frame TCP probe against `rtsp://10.123.239.102:8554/cam1`; only after that probe succeeds may the helper restart `sea-speed-camera1-h264.service`. The helper then requires the local HLS media sequence to advance. Any failure raises the existing reconcile failure boundary, and the unchanged VPS deployment transaction therefore cannot commit `runtime_verified` state.

No separate camera-recovery request schema or caller-controlled root argument is introduced. This keeps the privilege surface bounded to the existing exact-source request file and fixed no-argument helper while adding no new service-selector or URL-selector capability.

## Decisions

- D-001: Preserve the existing Camera 1 browser URL, Ubuntu relay, nginx/Auth topology and AI Worker independence.
- D-002: Implement recovery inside the exact-source privileged `reconcile` transaction instead of adding a second privileged caller interface.
- D-003: Treat a valid playlist whose `#EXT-X-MEDIA-SEQUENCE` does not increase across a fixed three-second sample as the bounded stale-H264 signal.
- D-004: Treat unavailable or malformed local HLS as an unknown/non-H264-specific failure and fail without restart.
- D-005: Before restarting H264, require one decodable frame over TCP from exactly `rtsp://10.123.239.102:8554/cam1`.
- D-006: Restart exactly `sea-speed-camera1-h264.service`; do not restart nginx, HLS HTTP, MediaMTX, Water worker, or Road worker.
- D-007: After restart, require the exact H264 service to be active and require two new local HLS samples to prove media-sequence progression.
- D-008: Preserve `deploy/vps/deploy.sh` source because its existing `run_auth_boundary` gate already precedes both accepted `runtime_verified` state-commit paths; helper failure is sufficient to block deployment acceptance.
- D-009: Because helper bytes change, production uses `ONE_COMMAND_FALLBACK` with one exact-source `install-auth-privilege-boundary.sh` bootstrap before GitHub Actions VPS deployment.
- D-010: Ubuntu Worker/relay is a read-only prerequisite only; Ubuntu deployment remains NOT REQUIRED.

## Affected contours

- VPS runtime: REQUIRED — installed privileged helper behavior changes and canonical VPS deployment invokes it.
- VPS execution capability: ONE_COMMAND_FALLBACK.
- Operator actions expected: 1.
- Ubuntu Worker/relay: NOT REQUIRED; fixed private relay is read only during the VPS recovery prerequisite.
- Frontend/API/storage: unchanged.
- Physical camera and camera credentials: unchanged.
- nginx/Auth topology: unchanged.
- AI workers: unchanged.

## Validation

Source validation uses focused Python unit tests for the root helper plus existing Auth/installer tests. The test harness captures every privileged command and proves the fixed constants, no-op behavior, relay-before-restart ordering, one exact H264 restart, failure-before-restart when relay media is absent, and failure when post-restart HLS remains static. A deployment-contract assertion proves both accepted `runtime_verified` paths remain behind `run_auth_boundary`, which now includes Camera 1 freshness recovery.

The final PR diff must remain a subset of the eight authorized Issue #226 paths. PR Validation and aggregate Quality must pass on one exact head. Before merge, refresh current `main`, exact PR head, changed-file scope, review submissions and unresolved threads; merge only with expected-head protection. Exact-main Quality must pass before any production decision.

Production acceptance is separate: install the exact-source helper bundle once through the repository-owned root bootstrap, then use canonical GitHub Actions VPS deployment for the exact authorized release. Acceptance requires HLS freshness PASS in deployment evidence and an authenticated browser showing current advancing video.

## Risk profile

- Risk profile: REQUIRED

This change broadens a production root helper and can restart one production service, so security-boundary and operational risk are explicit. Risk is bounded by the existing no-argument sudo rule, exact-source bundle validation, fixed request schema, fixed service/URLs, relay-before-restart prerequisite, post-restart freshness gate, unchanged source rollback transaction, and separate exact-SHA production authorization.

- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: keep recovery inside the exact-source no-argument helper with fixed relay/HLS/service constants and no caller-selected root arguments | Validation: unsupported-action, no-argument, fixed-command and exact-source bundle tests | Residual risk: the helper can restart one fixed production service only after bounded prerequisites | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: treat unavailable or malformed HLS and unreadable relay as pre-restart fatal and require post-restart HLS sequence progression | Validation: no-op, relay-failure-before-restart and post-restart-static tests | Residual risk: an external camera or relay outage can still block VPS deployment without mutating unrelated services | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: advancing HLS sequence returns NOOP; captured commands contain no `ffmpeg` and no service restart
- TEST-002 | Covers: AC-002,AC-006 | Level: unit | Priority: P0 | Evidence: static HLS + fixed relay frame causes exactly one `systemctl restart sea-speed-camera1-h264.service`; forbidden service names absent
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: failed fixed relay probe raises before any restart
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: post-restart equal HLS sequences raise fail-closed error
- TEST-005 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: fixed constants plus existing unsupported-action rejection and no-argument installer assertions
- TEST-006 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: privileged reconcile test returns Auth PASS plus Camera 1 freshness PASS markers
- TEST-007 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: deployment source assertion keeps accepted `runtime_verified` behind successful `run_auth_boundary`
- TEST-008 | Covers: AC-009,AC-010 | Level: integration | Priority: P0 | Evidence: exact authorized-subset PR diff, exact-head PR Validation + aggregate Quality, expected-head merge, exact-main Quality
- TEST-009 | Covers: AC-011,AC-012 | Level: end-to-end | Priority: P0 | Evidence: exact-source privilege bootstrap PASS followed by canonical VPS deployment `runtime_verified`
- TEST-010 | Covers: AC-013 | Level: runtime-manual | Priority: P0 | Evidence: authenticated current-day advancing clean video and unchanged Water/Road worker state

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #226 isolates and closes the stale clean-stream failure mode without broadening the physical camera, relay, browser or analytics Outcome.
- Specification impact: adds explicit freshness semantics, fixed preconditions and privilege boundaries for Camera 1 H264 recovery.
- Plan impact: uses the existing reconcile gate rather than a new privileged API and defines one exact-source bootstrap before VPS deployment.
- Tasks impact: source CI/merge, separate exact-SHA production authorization, exact-source helper bootstrap, VPS deployment and browser acceptance are tracked independently.
- Authorization impact: source authorization is `OUTCOME APPROVED`; no production mutation is authorized until a later exact-main SHA envelope is recorded.
- Follow-up: after exact-green source merge, compute the release authorization fingerprint, obtain exact production authorization, perform the one helper bootstrap, run canonical VPS deployment, verify advancing HLS/browser output, then return to Issue #218 natural-vessel Water Passage acceptance.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: prior bounded runtime evidence showed the Ubuntu private relay produced media while VPS local HLS at `127.0.0.1:18889/cam1/index.m3u8` remained on the same media sequence across repeated samples; the browser consequently displayed a prior-day frame. The missing control was a freshness gate/recovery for the dedicated VPS H264 compatibility producer.
- Production-learning adjacent-stage findings: physical camera and Ubuntu relay media were available; nginx/Auth route correctly pointed at local H264 HLS; AI Worker state was independent; ordinary VPS deployment verified API/Auth but had no Camera 1 HLS advancement check; the least-privilege helper was exact-source-bound but supported only Auth reconcile/status. The bounded correction is therefore one fixed H264 freshness stage inside reconcile, not a topology change.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: previous accepted VPS runtime remains active; candidate cannot proceed | Retry: only exact main first-parent release with green exact-main Quality and durable production authorization | Rollback: not applicable before mutation | Evidence: source SHA, Issue #226, merged PR, Quality status and production authorization verifier
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: no Camera 1 service restart occurs | Retry: only after exact-source helper bundle is installed and local HLS/private relay prerequisites are re-evaluated | Rollback: not applicable because helper validates exact bundle and probes before restart | Evidence: privilege-boundary status PASS, valid local HLS static evidence, fixed private relay frame probe
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: only `sea-speed-camera1-h264.service` may have been restarted; no configuration or data mutation occurs | Retry: only after actual service/HLS state is observed | Rollback: no configuration rollback required for a restart-only operation; deployment source rollback remains canonical if candidate acceptance fails | Evidence: fixed systemctl command and service-active result
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate is not accepted if post-restart HLS sequence does not advance | Retry: after root cause is resolved and exact authorized deployment is rerun | Rollback: canonical source rollback executes if deployment candidate source had changed; Camera 1 restart itself has no persistent config delta | Evidence: two valid post-restart HLS samples with increasing media sequence and Camera 1 PASS markers
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment manifest/current-release cannot claim `runtime_verified` unless reconcile including Camera 1 freshness succeeded | Retry: only after full verification passes | Rollback: preserve/restore previous accepted source release through existing VPS deployment transaction | Evidence: deployment manifest exact source, `runtimeVerified=true`, `state=runtime_verified`
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains accepted; stale release cleanup may remain | Retry: safe after acceptance | Rollback: no rollback solely for housekeeping failure | Evidence: canonical release-prune output
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: runtime may be healthy but Issue #226 remains open until durable deployment/browser evidence is recorded | Retry: re-read machine state and record sanitized evidence without redeploying solely for evidence | Rollback: not applicable | Evidence: helper bootstrap markers, VPS run/job IDs, deployment artifact, HLS freshness markers, authenticated browser acceptance
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: previous accepted source release is restored or unresolved runtime state remains fail-closed | Retry: prohibited until current/previous release and Camera 1 freshness are understood | Rollback: existing exact previous VPS release; no nginx/relay/worker rollback is part of this Outcome | Evidence: canonical rollback markers, previous/current release identity and protected health smoke

## Runtime feedback

- Operator screenshot on 2026-08-19 shows `STREAM buffering` and the clean Camera 1 panel displaying a timestamp from 2026-08-18.
- Issue #218 comment `5337443938` records bounded VPS diagnostics: local HLS media sequence did not advance, while the Ubuntu private relay produced a frame.
- Existing runbooks confirm the browser is intentionally served from the dedicated VPS H264 compatibility output and that clean live is independent of the AI Worker.
- The source implementation therefore preserves `deploy/vps/deploy.sh` bytes and uses its existing reconcile-before-`runtime_verified` invariant. Camera freshness failure propagates through the same privileged reconcile result.
- Production remains pending separate exact-SHA authorization. Because helper bytes change, the exact release will require one repository-owned privilege-boundary bootstrap before canonical VPS deployment.
