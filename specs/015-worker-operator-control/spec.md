# Feature Specification: Worker operator control

- Feature: 015-worker-operator-control
- Issue: #178
- Status: VPS release-pruning remediation validation
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
- FR-015: VPS exact deployment and automatic rollback verification MUST use the accepted Auth v1 FastAPI loopback origin `http://127.0.0.1:8010/api/health` by default; the retired `127.0.0.1:8000` origin MUST NOT be the deployment health default.
- FR-016: Deploy VPS admission MUST retain exact lowercase SHA and current-`main` first-parent membership checks without a producer-to-early-exit pipeline that can turn a valid match into a `pipefail`/SIGPIPE false-negative.
- FR-017: After candidate activation, origin/public verification and persistence of the current/previous release identities plus deployment manifest have succeeded, pruning releases that are neither current nor previous MUST be best-effort. A stale-release removal failure MUST emit a warning and MUST NOT invalidate the already verified deployment; current and previous release identities MUST never be pruning targets.

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
- AC-015: Source regression evidence proves `deploy/vps/deploy.sh` defaults `SEA_SPEED_ORIGIN_HEALTH_URL` to `http://127.0.0.1:8010/api/health`, contains no stale `http://127.0.0.1:8000/api/health` default, and uses the same origin verifier for both deployment and automatic rollback verification.
- AC-016: Source regression evidence proves Deploy VPS no longer uses `git rev-list --first-parent origin/main | grep -q` under `pipefail`, still enumerates `origin/main` first-parent history, admits an exact matching SHA through an explicit membership result, and preserves fail-closed rejection when no first-parent match exists.
- AC-017: Source regression evidence proves `prune_releases` excludes both current and previous identities, wraps stale `rm -rf` in a non-fatal conditional with an explicit warning on failure, and successful deployment persists previous/current state plus the runtime-verified deployment manifest before pruning begins.

## NFR assessment

- NFR-001 | Area: SECURITY | Target: only authenticated browser identity plus bearer-authenticated private fixed-operation agent may mutate worker state; no arbitrary service/command surface | Validation: unit/integration contract tests | Evidence: tests/test_worker_operator_control.py and tests/test_sea_speed_auth_v1.py | Status: PASS
- NFR-002 | Area: RELIABILITY | Target: worker-control outage or protocol incompatibility fails closed within bounded timeout and never interrupts HLS | Validation: API proxy contract plus frontend invariant tests | Evidence: tests/test_worker_operator_control.py and tests/test_frontend_contract.py | Status: PASS
- NFR-003 | Area: OPERABILITY | Target: intentional stopped/running state survives exact update/rollback maintenance semantics | Validation: updater/rollback contract tests | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py | Status: PASS
- NFR-004 | Area: COMPATIBILITY | Target: Camera 1 HLS URL and existing live Play/Stop controls remain unchanged | Validation: frontend contract test | Evidence: tests/test_frontend_contract.py | Status: PASS
- NFR-005 | Area: PERFORMANCE | Target: worker-control status/action upstream timeout is bounded to <= 5 seconds by configuration clamp | Validation: API contract assertions | Evidence: tests/test_worker_operator_control.py | Status: PASS
- NFR-006 | Area: RELEASE_PROVENANCE | Target: MIXED release provenance contains deterministic exact artifacts for VPS and Ubuntu Worker while preserving the existing quality-evidence v1 `vps`/legacy-`edge` contract | Validation: deterministic build, extraction/digest/syntax validation, quality-evidence validation, and exact-manifest/release-artifact binding | Evidence: tests/quality/test_quality_architecture.py | Status: PASS
- NFR-007 | Area: OPERABILITY | Target: VPS deployment and rollback health verification use the accepted FastAPI origin on loopback port 8010 and cannot silently regress to the retired port 8000 default | Validation: source contract regression tests plus exact-head CI | Evidence: tests/test_vps_deploy_origin_health.py, tests/test_camera_preview_gallery.py, and tests/test_sea_speed_auth_v1.py | Status: PASS
- NFR-008 | Area: RELIABILITY | Target: Deploy VPS first-parent admission accepts a valid current-main/first-parent SHA without `pipefail` SIGPIPE false-negatives while preserving rejection of non-first-parent commits | Validation: workflow architecture regression plus exact-head CI | Evidence: tests/quality/test_quality_architecture.py | Status: PASS
- NFR-009 | Area: RELIABILITY | Target: stale-release cleanup permission failures cannot overturn an already persisted, runtime-verified VPS deployment, while current and previous rollback identities remain protected from pruning | Validation: deploy-script regression contract plus exact-head CI | Evidence: tests/test_vps_deploy_origin_health.py | Status: PASS

## Compatibility and boundaries

- Stable public media interface: `/sea-speed/media/cam1/index.m3u8`.
- Stable worker runtime semantics: detection/tracking/speed/calibration/event behavior unchanged.
- Additive browser API: `/sea-speed/api/worker/control`, `/start`, `/stop`.
- Private Ubuntu agent: fixed status/start/stop HTTP surface on a configured RFC1918 listener.
- Private worker-control compatibility identity: `sea_speed_worker_control_v1`; mismatches fail closed rather than falling back.
- VPS deployment origin identity: accepted FastAPI origin `127.0.0.1:8010`; public protected health remains an authentication-boundary smoke, not origin-health proof.
- Deploy admission identity: exact lowercase 40-character target SHA must remain on current `main` first-parent history; implementation must not weaken that requirement while removing the `grep -q`/`pipefail` false-negative.
- VPS release retention: current and previous releases form the protected rollback pair; older release cleanup is post-verification housekeeping and cannot revoke a verified deployment solely because stale files are not removable by the deploy user.
- Release evidence: the exact-artifacts manifest retains `vps` and legacy `edge` in its quality-evidence-compatible inventory and adds `ubuntu-worker` as release-specific exact provenance. Release-manifest v2 directly binds the Ubuntu archive and the complete exact-manifest hash; this does not activate `edge_v2` or change media ownership.
- Out of scope: MediaMTX/relay lifecycle, Camera 2, Windows Worker, browser SSH, arbitrary systemd control, new credentials, secret migration, AI algorithm changes.

## Runtime feedback

- Runtime acceptance: PENDING corrected release-pruning deployment evidence, then pending Ubuntu worker-control/HLS acceptance.
- Last independently read-only verified VPS baseline before run #27: `6bf909c13d48df1d44b87a62d0686b61d8c3af45`, `sea-speed-api` active and healthy on `127.0.0.1:8010`. Deploy VPS run #27 subsequently proved the candidate `1d7c8478a467f28f4519111bae06f5d2f7fa5e61` healthy on origin 8010 and passed all public smoke checks before failing in stale-release pruning; because post-deployment evidence upload was skipped, exact post-run state must be re-read before the next runtime mutation.
- Regressions/learning #1: pre-production release admission for merged PR #179 stopped before any runtime write because exact-artifact tooling did not provide an `ubuntu-worker` artifact required by release-manifest v2 for the declared MIXED contour; PR #180 remediated that provenance gap.
- Regressions/learning #2: authorized Deploy VPS run #25 for `1d0aa285d5f30165980c4d628a97da7e23b66ffe` reached production but both deployment and automatic rollback verification used stale loopback port 8000. Read-only operator evidence immediately after the run proved the restored release was healthy on the accepted port 8010, so the deployment result was a verifier false-negative rather than an API outage; PR #181 remediated the source default.
- Regressions/learning #3: authorized Deploy VPS run #26 received exact `INPUT_COMMIT=1d7c8478a467f28f4519111bae06f5d2f7fa5e61` while runner `origin/main` was the same SHA, but the first-parent admission pipeline `git rev-list ... | grep -Fxq` failed under `set -o pipefail` because the early successful `grep -q` close caused `git rev-list` SIGPIPE. The run stopped before quality verification, authorization verification, SSH, or runtime mutation; PR #182 remediated the control-plane guard.
- Regressions/learning #4: authorized Deploy VPS run #27 passed first-parent admission, exact quality, production authorization, release provenance and SSH; candidate origin health on 8010 plus Operator/private-health/Objects/Cameras/Root public smoke checks all passed. The script then returned exit 1 because `prune_releases` attempted `rm -rf` on older release `8248fd6ff54bb4fd197dfef45a31c75f3b39ace5` and the deploy user lacked permission. The success path had already written previous/current state and the runtime-verified deployment manifest before pruning, so cleanup failure is post-verification housekeeping rather than candidate-health failure.
- Corrective action: current separately approved 5-path VPS remediation makes stale-release pruning warning-only while preserving current/previous protection, adds ordering/regression evidence, and updates this SDD. API/frontend/media/worker semantics are unchanged.
- Production authorization impact: the run #27 envelope for `1d7c8478a467f28f4519111bae06f5d2f7fa5e61` cannot authorize the new VPS-affecting remediation merge SHA. After exact-green merge and post-merge quality, a fresh `PRODUCTION APPROVED <new-sha>` envelope is required before another VPS deployment.
