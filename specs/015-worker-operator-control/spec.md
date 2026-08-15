# Feature Specification: Worker operator control

- Feature: 015-worker-operator-control
- Issue: #178
- Status: Correct-course remediation validation
- Owner outcome: Allow an authenticated Sea Speed operator to start and stop only the Ubuntu AI worker while Camera 1 live HLS remains independent and uninterrupted.

## Product outcome

Sea Speed Operator must expose a bounded worker-control action that changes only `sea-speed-worker.service`. The clean Camera 1 live stream remains owned by the independent relay/HLS contour and must continue to work when the AI worker is intentionally stopped.

## User scenarios

### Scenario 1 - stop AI processing without losing live video

Given Camera 1 live playback is available and the AI worker is running, when an authenticated operator selects `Stop worker`, then only `sea-speed-worker.service` becomes inactive, the control service remains available, and the HLS path remains independently playable.

### Scenario 2 - restart AI processing

Given the AI worker was intentionally stopped, when an authenticated operator selects `Start worker`, then the same installed exact-release worker service starts without changing Camera 1 relay/HLS configuration and the UI reports the observed running state.

### Scenario 3 - fail closed when control is unavailable or incompatible

Given the VPS cannot reach, authenticate to, or confirm the fixed protocol version of the Ubuntu control agent, when the UI refreshes or an operator attempts a worker action, then no alternate command path is used, no arbitrary service can be selected, and the UI reports control unavailability while leaving the live stream untouched.

## Requirements

- FR-001: The Operator UI MUST expose one worker-control button separate from the existing live-camera Play/Stop buttons.
- FR-002: Browser worker-control requests MUST be accepted only with trusted Authentik identity forwarded by the existing `/sea-speed/**` boundary.
- FR-003: VPS FastAPI MUST proxy only fixed worker-control operations (`status`, `start`, `stop`) to one configured private Ubuntu control origin.
- FR-004: VPS-to-Ubuntu worker-control traffic MUST use the existing `SEA_SPEED_API_TOKEN` bearer secret and a validated RFC1918 HTTP origin; redirects and arbitrary upstream paths MUST NOT be followed.
- FR-005: The Ubuntu control agent MUST bind to a private configured address, require the bearer token, and operate only on the literal `sea-speed-worker.service`.
- FR-006: The Ubuntu control agent MUST NOT accept arbitrary service names, shell commands, command arguments, camera-relay operations, or MediaMTX operations.
- FR-007: `Stop worker` MUST persist desired state `stopped` before stopping the AI worker; `Start worker` MUST persist desired state `running` and restore the previous desired state if startup fails.
- FR-008: The dedicated worker-control service MUST remain independent of `sea-speed-worker.service` so an intentionally stopped AI worker can be started again remotely.
- FR-009: Exact-release activation and rollback MUST preserve an intentional `stopped` desired state rather than treating the inactive worker as an automatic fault.
- FR-010: Existing Camera 1 HLS URL `/sea-speed/media/cam1/index.m3u8`, MediaMTX/relay lifecycle and browser Play/Stop behavior MUST remain unchanged.
- FR-011: Detection, tracking, speed, calibration and event semantics MUST remain unchanged; no `worker/**` source is modified by the operator-control feature implementation or its provenance remediation.
- FR-012: Source integration MUST NOT mutate production. VPS and Ubuntu runtime changes require a later exact-SHA production safety envelope.
- FR-013: Every successful Ubuntu worker-control response MUST carry the fixed protocol marker `sea_speed_worker_control_v1`, and VPS FastAPI MUST reject a missing or different marker as an unavailable/incompatible control agent.
- FR-014: Exact-artifact tooling MUST build and validate a deterministic `ubuntu-worker` source artifact as release-specific provenance while preserving the existing quality-evidence v1 `vps` and legacy `edge` component contract. Release-manifest v2 MUST be able to bind the Ubuntu archive digest directly plus the SHA-256 of the complete exact-artifacts manifest.

## Acceptance criteria

- AC-001: UI contains a distinct `Start worker` / `Stop worker` control adjacent to worker status and the existing live-camera Play/Stop controls remain present and unchanged in purpose.
- AC-002: Authenticated browser GET of worker-control status returns the bounded Ubuntu service state; missing trusted Authentik identity fails closed.
- AC-003: Authenticated browser start/stop requests can reach only fixed FastAPI routes and fixed Ubuntu agent paths.
- AC-004: Ubuntu agent rejects a missing/wrong bearer token and has no request shape for an arbitrary service or command.
- AC-005: Ubuntu agent start/stop functions invoke only `systemctl start sea-speed-worker.service` or `systemctl stop sea-speed-worker.service` plus fixed read-only status queries.
- AC-006: Operator stop records desired state `stopped`; operator start records `running`; a failed start restores the prior desired-state marker.
- AC-007: The separate worker-control systemd unit is installed/enabled independently and is not stopped by `systemctl stop sea-speed-worker.service`.
- AC-008: Exact updater and rollback accept an intentionally inactive worker when desired state is `stopped` and preserve that state.
- AC-009: Existing private Ubuntu->VPS worker API ingress does not expose `/api/worker/control/**`.
- AC-010: Source tests prove the public HLS identity remains `/sea-speed/media/cam1/index.m3u8` and worker-control code contains no MediaMTX/camera-relay stop/restart operation.
- AC-011: PR Validation and aggregate Quality integration succeed on the exact final PR head with exact approved scope and no unresolved review threads.
- AC-012: After separate production authorization, runtime-manual evidence proves stop/start changes AI worker state while Camera 1 HLS remains playable throughout.
- AC-013: Source tests prove the Ubuntu agent emits `sea_speed_worker_control_v1` and the VPS proxy has an explicit fail-closed protocol mismatch guard before returning successful control payloads.
- AC-014: Two independent exact-artifact builds produce byte-identical `vps`, `ubuntu-worker`, and `edge` archives/manifests; the validator accepts all three, quality-evidence v1 remains valid for its existing `vps`/`edge` inventory, and the exact-artifacts manifest separately records the Ubuntu artifact digest for later release-manifest v2 binding.

## NFR assessment

- NFR-001 | Area: SECURITY | Target: only authenticated browser identity plus bearer-authenticated private fixed-operation agent may mutate worker state; no arbitrary service/command surface | Validation: unit/integration contract tests | Evidence: tests/test_worker_operator_control.py and tests/test_sea_speed_auth_v1.py | Status: PASS
- NFR-002 | Area: RELIABILITY | Target: worker-control outage or protocol incompatibility fails closed within bounded timeout and never interrupts HLS | Validation: API proxy contract plus frontend invariant tests | Evidence: tests/test_worker_operator_control.py and tests/test_frontend_contract.py | Status: PASS
- NFR-003 | Area: OPERABILITY | Target: intentional stopped/running state survives exact update/rollback maintenance semantics | Validation: updater/rollback contract tests | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py | Status: PASS
- NFR-004 | Area: COMPATIBILITY | Target: Camera 1 HLS URL and existing live Play/Stop controls remain unchanged | Validation: frontend contract test | Evidence: tests/test_frontend_contract.py | Status: PASS
- NFR-005 | Area: PERFORMANCE | Target: worker-control status/action upstream timeout is bounded to <= 5 seconds by configuration clamp | Validation: API contract assertions | Evidence: tests/test_worker_operator_control.py | Status: PASS
- NFR-006 | Area: RELEASE_PROVENANCE | Target: MIXED release provenance contains deterministic exact artifacts for VPS and Ubuntu Worker while preserving the existing quality-evidence v1 `vps`/legacy-`edge` contract | Validation: deterministic build, extraction/digest/syntax validation, quality-evidence validation, and exact-manifest/release-artifact binding | Evidence: tests/quality/test_quality_architecture.py | Status: PASS

## Compatibility and boundaries

- Stable public media interface: `/sea-speed/media/cam1/index.m3u8`.
- Stable worker runtime semantics: detection/tracking/speed/calibration/event behavior unchanged.
- Additive browser API: `/sea-speed/api/worker/control`, `/start`, `/stop`.
- Private Ubuntu agent: fixed status/start/stop HTTP surface on a configured RFC1918 listener.
- Private worker-control compatibility identity: `sea_speed_worker_control_v1`; mismatches fail closed rather than falling back.
- Release evidence: the exact-artifacts manifest retains `vps` and legacy `edge` in its quality-evidence-compatible inventory and adds `ubuntu-worker` as release-specific exact provenance. Release-manifest v2 directly binds the Ubuntu archive and the complete exact-manifest hash; this does not activate `edge_v2` or change media ownership.
- Out of scope: MediaMTX/relay lifecycle, Camera 2, Windows Worker, browser SSH, arbitrary systemd control, new credentials, secret migration, AI algorithm changes.

## Runtime feedback

- Runtime acceptance: PENDING a new exact-SHA production authorization after remediation merge.
- Accepted production behavior: PENDING.
- Regressions/learning: pre-production release admission for merged PR #179 stopped before any runtime write because exact-artifact tooling did not provide an `ubuntu-worker` artifact required by release-manifest v2 for the declared MIXED contour.
- Corrective action: add fixed worker-control protocol compatibility plus deterministic Ubuntu Worker exact-artifact provenance inside the separately approved 9-path remediation scope.
- Previous production authorization: bound only to `dc0fd44dbea5ba38f8e18a4ba6ed3eeb93db3d11` and intentionally not reusable for the remediation merge SHA.
