# Feature Specification: Worker operator control

- Feature: 015-worker-operator-control
- Issue: #178
- Status: Single dynamic Stream action remediation
- Owner outcome: Allow an authenticated Sea Speed operator to start and stop only the Ubuntu AI worker while Camera 1 live HLS remains independent and uninterrupted, with compact contextual controls in the top status strip.

## Product outcome

Sea Speed Operator exposes bounded Worker control that changes only `sea-speed-worker.service`. Camera 1 HLS remains owned by the independent relay/media contour. The operator surface uses one contextual Worker action and exactly one contextual Stream action: Stream shows Play when HLS is not desired/active and Stop when HLS is desired/active. The Live camera card contains the clean video and camera information but no duplicate Stream action.

## User scenarios

### Scenario 1 - stop AI processing without losing live video
Given Camera 1 live playback is available and the AI worker is running, when an authenticated operator selects the worker stop action, only `sea-speed-worker.service` becomes inactive, the control service remains available, and HLS remains independently playable.

### Scenario 2 - restart AI processing
Given the AI worker was intentionally stopped, when the operator selects the worker start action, the same installed exact-release worker service starts without changing Camera 1 relay/HLS configuration.

### Scenario 3 - fail closed when worker control is unavailable
Given VPS cannot reach/authenticate/confirm the fixed Ubuntu control protocol, no alternate command path is used and the UI reports control unavailability without changing the live stream.

### Scenario 4 - one compact contextual action per controllable status
Given the Operator UI is open, Worker has exactly one contextual icon action and Stream has exactly one contextual icon action. Stream action displays Play when HLS is not desired/active and Stop when it is desired/active. The Live camera card contains no Stream action button. Worker start/stop executes directly without an extra confirmation popup.

## Requirements

- FR-001: The top status strip MUST expose exactly one `streamControlBtn` adjacent to Stream status and exactly one `workerControlBtn` adjacent to Worker status.
- FR-002: Browser worker-control requests MUST be accepted only with trusted Authentik identity forwarded by the existing `/sea-speed/**` boundary.
- FR-003: VPS FastAPI MUST proxy only fixed worker-control operations (`status`, `start`, `stop`) to one configured private Ubuntu control origin.
- FR-004: VPS-to-Ubuntu worker-control traffic MUST use the existing bearer secret and validated RFC1918 origin; redirects/arbitrary paths are forbidden.
- FR-005: Ubuntu control agent MUST bind privately, require the bearer token, and operate only on literal `sea-speed-worker.service`.
- FR-006: Ubuntu control agent MUST NOT accept arbitrary service names, shell commands, command arguments, camera-relay operations or MediaMTX operations.
- FR-007: Worker Stop MUST persist desired state `stopped`; Worker Start MUST persist `running` and restore prior desired state if startup fails.
- FR-008: Dedicated worker-control service MUST remain independent of `sea-speed-worker.service`.
- FR-009: Exact-release activation/rollback MUST preserve intentional stopped/running desired state.
- FR-010: Existing Camera 1 HLS URL `/sea-speed/media/cam1/index.m3u8`, MediaMTX/relay lifecycle and browser connect/disconnect semantics MUST remain unchanged in purpose.
- FR-011: Detection, tracking, speed, calibration and event semantics MUST remain unchanged; no `worker/**` source changes are part of this UI remediation.
- FR-012: Source integration MUST NOT mutate production; runtime changes require separate exact-SHA production authorization.
- FR-013: Successful Ubuntu worker-control responses MUST carry `sea_speed_worker_control_v1`; VPS rejects missing/different markers.
- FR-014: Exact-artifact tooling MUST retain deterministic `ubuntu-worker` provenance established by the accepted implementation.
- FR-015: VPS deployment/rollback health MUST use accepted FastAPI loopback origin `http://127.0.0.1:8010/api/health` by default.
- FR-016: Deploy VPS admission MUST retain exact lowercase SHA/current-main first-parent membership checks without pipefail/SIGPIPE false-negatives.
- FR-017: Stale VPS release pruning after verified persistence MUST be best-effort; current/previous releases are protected.
- FR-018: Ubuntu updater quality verification MUST use supported `--workflow-file quality-integration.yml` contract.
- FR-019: Ubuntu activation/rollback MUST preserve exact worker-control unit topology for modern/legacy releases and fail closed on partial targets.
- FR-020: Ubuntu updater EXIT housekeeping MUST preserve the primary updater status.
- FR-021: Stream MUST NOT expose simultaneous Play and Stop buttons. A single `streamControlBtn` MUST dynamically render the currently available action, update `aria-label` and `title`, route Play to the existing `connectStream` lifecycle and Stop to the existing `disconnectStream` lifecycle, and remain outside the Live camera card. Worker remains a single icon-only dynamic action and has no `confirm(...)` gate.

## Acceptance criteria

- AC-001: Top status strip contains exactly one Stream action button and exactly one Worker action button; no legacy `connectBtn` or `disconnectBtn` exists.
- AC-002: Authenticated browser GET of worker-control status returns bounded Ubuntu service state; missing trusted identity fails closed.
- AC-003: Browser start/stop requests reach only fixed FastAPI/Ubuntu paths.
- AC-004: Ubuntu agent rejects missing/wrong bearer token and exposes no arbitrary command/service shape.
- AC-005: Ubuntu agent operates only on literal `sea-speed-worker.service` plus fixed status queries.
- AC-006: Desired state is persisted/restored correctly around start/stop failure.
- AC-007: Independent worker-control systemd unit remains available when worker is stopped.
- AC-008: Exact updater/rollback preserve intentional worker state.
- AC-009: Existing private Ubuntu->VPS ingress does not expose worker-control routes.
- AC-010: HLS public identity remains `/sea-speed/media/cam1/index.m3u8`; worker control contains no MediaMTX/relay lifecycle mutation.
- AC-011: PR Validation and aggregate Quality integration succeed on the same exact final head with authorized scope and no unresolved review threads.
- AC-012: Runtime evidence proves worker Stop/Start does not interrupt Camera 1 HLS; final current UI smoke must also pass.
- AC-013: Protocol marker/compatibility mismatch fails closed.
- AC-014: Deterministic release provenance remains valid for VPS/Ubuntu Worker/legacy edge inventories.
- AC-015: VPS origin health contract remains on port 8010.
- AC-016: VPS first-parent admission remains pipefail-safe.
- AC-017: VPS stale pruning remains warning-only after verified persistence.
- AC-018: Ubuntu updater uses real quality-verifier CLI contract.
- AC-019: Ubuntu modern/legacy control-service topology is rollback-safe.
- AC-020: Ubuntu cleanup preserves primary process status.
- AC-021: Frontend contract proves exactly one `streamControlBtn`, dynamic Play/Stop SVG rendering, dynamic `aria-label`/`title`, no `connectBtn`/`disconnectBtn`, no Stream control in Live camera, one Worker action, and no worker confirmation popup.

## NFR assessment

- NFR-001 | Area: SECURITY | Target: authenticated browser + bearer-authenticated fixed-operation agent only | Validation: worker-control and auth contract tests | Evidence: worker-control/auth tests | Status: PASS
- NFR-002 | Area: RELIABILITY | Target: worker-control outage/mismatch fails closed and never interrupts HLS | Validation: worker-control and frontend lifecycle tests | Evidence: worker/frontend tests | Status: PASS
- NFR-003 | Area: OPERABILITY | Target: intentional worker state survives update/rollback | Validation: exact updater and rollback tests | Evidence: updater/rollback tests | Status: PASS
- NFR-004 | Area: COMPATIBILITY | Target: HLS URL/lifecycle unchanged while a single contextual Stream action replaces simultaneous Play+Stop controls | Validation: frontend contract and aggregate CI | Evidence: frontend contract | Status: PASS
- NFR-005 | Area: PERFORMANCE | Target: worker-control timeout remains bounded | Validation: worker-control API timeout tests | Evidence: API tests | Status: PASS
- NFR-006 | Area: RELEASE_PROVENANCE | Target: deterministic exact artifacts remain valid | Validation: exact-artifact and quality architecture jobs | Evidence: quality architecture | Status: PASS
- NFR-007 | Area: OPERABILITY | Target: VPS health/rollback uses loopback 8010 | Validation: VPS deploy origin-health regression | Evidence: deploy regression | Status: PASS
- NFR-008 | Area: RELIABILITY | Target: first-parent admission avoids SIGPIPE false negatives | Validation: deployment admission regression | Evidence: workflow regression | Status: PASS
- NFR-009 | Area: RELIABILITY | Target: stale pruning cannot invalidate verified deployment | Validation: VPS stale-pruning regression | Evidence: deploy regression | Status: PASS
- NFR-010 | Area: RELIABILITY | Target: Ubuntu admission/rollback topology remains exact | Validation: Ubuntu updater and rollback regression | Evidence: updater/rollback tests | Status: PASS
- NFR-011 | Area: RELIABILITY | Target: updater housekeeping remains status-neutral | Validation: executable EXIT-trap cleanup regression | Evidence: EXIT-trap regression | Status: PASS
- NFR-012 | Area: OPERATOR_UX | Target: one contextual Stream action and one contextual Worker action in the top strip, no duplicate Stream action, accessible dynamic labels/titles | Validation: frontend contract plus production browser smoke | Evidence: tests/test_frontend_contract.py + Issue #178 runtime-manual evidence | Status: CONCERNS

## Compatibility and boundaries

- Stable media interface: `/sea-speed/media/cam1/index.m3u8`.
- Stable Worker runtime semantics: detection/tracking/speed/calibration/event behavior unchanged.
- Stable worker-control API/agent/security boundaries remain unchanged.
- Current remediation is VPS frontend + frontend tests/SDD only.
- Out of scope: API behavior, MediaMTX/relay lifecycle, Ubuntu/Windows runtime mutation, credentials/secrets, AI algorithm changes.

## Runtime feedback

- Worker-control production acceptance is COMPLETE on Ubuntu exact source `8dc74762a344dbf763d3ce1e7ecb1bac6872affb`: Worker Stop/Start was confirmed while Camera 1 HLS remained continuously available.
- VPS UI source `0c2651629f517f939b8d18cacbc624654e8c4e11` was deployed/runtime-verified, but final browser acceptance identified two simultaneous Stream buttons and therefore did not satisfy the intended compact contextual interaction.
- Fresh source authorization for the exact five-path single-Stream-action remediation was supplied immediately after the visible six-field Scope block on 2026-08-16.
- A fresh exact-SHA VPS production envelope is required only after the remediation merge; Ubuntu Worker and Windows Worker require no update for this change.
