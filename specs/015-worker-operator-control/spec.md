# Feature Specification: Worker operator control

- Feature: 015-worker-operator-control
- Issue: #178
- Status: Ubuntu updater/legacy-control rollback remediation validation
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
- FR-011: Detection, tracking, speed, calibration and event semantics MUST remain unchanged; no `worker/**` source is modified by the operator-control feature implementation or its provenance/remediation changes.
- FR-012: Source integration MUST NOT mutate production. VPS and Ubuntu runtime changes require a later exact-SHA production safety envelope.
- FR-013: Every successful Ubuntu worker-control response MUST carry the fixed protocol marker `sea_speed_worker_control_v1`, and VPS FastAPI MUST reject a missing or different marker as an unavailable/incompatible control agent.
- FR-014: Exact-artifact tooling MUST build and validate a deterministic `ubuntu-worker` source artifact as release-specific provenance while preserving the existing quality-evidence v1 `vps` and legacy `edge` component contract. Release-manifest v2 MUST be able to bind the Ubuntu archive digest directly plus the SHA-256 of the complete exact-artifacts manifest.
- FR-015: VPS exact deployment and automatic rollback verification MUST use the accepted Auth v1 FastAPI loopback origin `http://127.0.0.1:8010/api/health` by default; the retired `127.0.0.1:8000` origin MUST NOT be the deployment health default.
- FR-016: Deploy VPS admission MUST retain exact lowercase SHA and current-`main` first-parent membership checks without a producer-to-early-exit pipeline that can turn a valid match into a `pipefail`/SIGPIPE false-negative.
- FR-017: After candidate activation, origin/public verification and persistence of the current/previous release identities plus deployment manifest have succeeded, pruning releases that are neither current nor previous MUST be best-effort. A stale-release removal failure MUST emit a warning and MUST NOT invalidate the already verified deployment; current and previous release identities MUST never be pruning targets.
- FR-018: Ubuntu `update-exact.sh` MUST invoke `scripts/quality/verify_quality_status.py` only through its supported exact-workflow CLI (`--workflow-file quality-integration.yml`) and MUST NOT pass the unsupported `--required-name` option. Regression evidence MUST execute the verifier help/parser surface rather than merely assert an invented argument string.
- FR-019: Ubuntu activation and explicit rollback MUST treat worker-control unit topology as part of exact release state. Failed activation MUST restore whether the previous control unit was present, enabled and active; rollback to a legacy target that predates worker control MUST stop/disable/remove the newer control unit and prove it absent; a target with only partial worker-control components MUST fail closed before acceptance.

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
- AC-018: Focused updater regression evidence runs the real quality-verifier CLI help/parser surface, requires `--workflow-file quality-integration.yml`, forbids `--required-name`, and retains the protected-token/exact-main checks.
- AC-019: Focused updater/rollback regression evidence proves a failed modern activation can restore a legacy no-control baseline, a successful rollback to a legacy target removes the modern control service, modern targets still require an exact active control unit, and incomplete target control components are rejected.

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
- NFR-010 | Area: RELIABILITY | Target: Ubuntu release admission uses an executable caller/verifier CLI contract and activation/rollback can restore the exact legacy-or-modern control-service topology without changing the active marker before acceptance | Validation: shell syntax plus real verifier CLI help and updater/rollback topology regression contracts | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py | Status: PASS

## Compatibility and boundaries

- Stable public media interface: `/sea-speed/media/cam1/index.m3u8`.
- Stable worker runtime semantics: detection/tracking/speed/calibration/event behavior unchanged.
- Additive browser API: `/sea-speed/api/worker/control`, `/start`, `/stop`.
- Private Ubuntu agent: fixed status/start/stop HTTP surface on a configured RFC1918 listener.
- Private worker-control compatibility identity: `sea_speed_worker_control_v1`; mismatches fail closed rather than falling back.
- VPS deployment origin identity: accepted FastAPI origin `127.0.0.1:8010`; public protected health remains an authentication-boundary smoke, not origin-health proof.
- Deploy admission identity: exact lowercase 40-character target SHA must remain on current `main` first-parent history.
- VPS release retention: current and previous releases form the protected rollback pair; older release cleanup is post-verification housekeeping.
- Ubuntu release admission: `verify_quality_status.py --workflow-file quality-integration.yml` is the supported exact-workflow caller contract; unsupported aliases are forbidden.
- Ubuntu rollback topology: modern releases include the independent control unit; legacy releases may intentionally have no control unit, and that absence is part of rollback state rather than a missing-file error.
- Release evidence: deterministic exact provenance retains `vps`, release-specific `ubuntu-worker`, and legacy `edge` inventory as already established.
- Out of scope: MediaMTX/relay lifecycle, Camera 2, Windows Worker, browser SSH, arbitrary systemd control, new credentials, secret migration, AI algorithm changes.

## Runtime feedback

- Runtime acceptance: VPS contour ACCEPTED on exact release `e2a4f39eab80849882a42cf6e892bba127223649`; Ubuntu worker-control/HLS acceptance remains pending.
- Current independently observed Ubuntu baseline before this remediation: active source `efdbdfd9612d425bf34a81384298e091de06ec15`, runtime ID `a9a9aaccd97e5c824ccc568504ad146936a4a69b5f8fe1ff36451ecd7317f88b`, worker active/enabled, `sea-speed-worker-control.service` absent/not installed, protected GitHub token root-owned mode 0600.
- Regressions/learning #1: pre-production release admission for merged PR #179 exposed missing Ubuntu exact provenance; PR #180 remediated it.
- Regressions/learning #2: Deploy VPS run #25 exposed stale loopback port 8000; PR #181 corrected the accepted origin to 8010.
- Regressions/learning #3: Deploy VPS run #26 exposed `grep -q`/`pipefail` first-parent false-negative; PR #182 corrected admission.
- Regressions/learning #4: Deploy VPS run #27 exposed fatal post-verification stale-release pruning; PR #183 made pruning warning-only and a later exact authorized deployment completed successfully with evidence.
- Regressions/learning #5: first Ubuntu preparation attempt for `1d0aa285d5f30165980c4d628a97da7e23b66ffe` stopped before release preparation because `update-exact.sh` passed unsupported `--required-name quality-integration` to the exact target's `verify_quality_status.py`. Adjacent-stage review then found that forward activation/explicit rollback did not correctly model the real legacy baseline where the control service is absent.
- Corrective action: current separately approved 9-path Ubuntu remediation aligns the caller with `--workflow-file quality-integration.yml`, adds executable CLI compatibility evidence, and makes control-service presence/absence transactional across failed activation and explicit rollback.
- Production authorization impact: no prior `PRODUCTION APPROVED` line transfers to the new Ubuntu-affecting remediation merge SHA. A fresh exact-SHA production safety envelope is required before preparation/activation continues.
