# Implementation Plan: Road Operator parity

- Specification: specs/020-road-operator-parity/spec.md
- Issue: #206
- Status: Implementing

## Architecture

The canonical Water Operator remains the visual/interaction reference and is not modified. The Road page implements the same operator shell with fixed Road adapters:

- analytics: `/sea-speed/api/analytics/road1/**`;
- preview: existing protected on-demand logical `road1` preview start plus bounded global preview stop;
- browser control: additive authenticated `/sea-speed/api/worker/control/road1[/start|/stop]`;
- private agent protocol: fixed `/v1/road1/status|start|stop` mapped only to `sea-speed-road-worker.service`;
- Road desired state: `/opt/sea-speed-worker/shared/road-runtime/operator-desired-state`;
- Water desired state remains `/opt/sea-speed-worker/shared/runtime/operator-desired-state`.

The Ubuntu control agent remains one independent hardened root service but accepts exactly two compile-time targets: `water` and `road1`. It never accepts a service name, shell command or path from browser/API input. The systemd control unit gains write permission only to `shared/runtime` and `shared/road-runtime`.

Mixed production rollout is ordered Ubuntu first, VPS second. Ubuntu introduces compatible Road control and desired-state semantics before VPS exposes the Road browser controls. Source integration itself performs no production mutation.

## Decisions

- D-001: Reproduce canonical Operator structure/styles in the Road document instead of changing the Water Operator reference.
- D-002: Reuse existing Road analytics and protected preview endpoints; do not create a second preview architecture.
- D-003: Extend the existing worker-control protocol with fixed Road paths rather than introduce arbitrary target parameters.
- D-004: Persist Road desired state separately from Water so operator actions do not couple the two services.
- D-005: Preserve exact commit/runtime identity checks when Road is stopped; skip only frame/state progression because intentional stop makes progression impossible.
- D-006: Keep private Worker-to-VPS telemetry/config ingress unchanged and explicitly enumerate browser-control routes that must never enter it.
- D-007: Runtime deployment is MIXED and must be Ubuntu-first/VPS-second under a fresh exact-main production envelope.

## Affected contours

- VPS: REQUIRED. Road frontend, FastAPI Road worker-control routes and nginx security regression are included in the exact VPS release.
- Ubuntu Worker/relay: REQUIRED. Fixed Road control paths, independent desired state and exact update/rollback/deployment semantics change.
- Windows: retired and not an active production contour.
- Operator actions expected: 1 because Ubuntu restricted zero-touch transport is not provisioned and the repository-owned `ONE_COMMAND_FALLBACK` remains the accepted capability.

## Validation

Source validation covers Python syntax/import contracts, shell syntax, frontend static contract, fixed control allowlists, independent desired-state behavior, nginx private-ingress exclusion, exact updater/rollback/deploy transaction semantics, SDD validation, exact-artifact validation, PR Validation and aggregate Quality integration.

Runtime validation after separate authorization covers Ubuntu exact deployment and manifest, then VPS exact deployment. Authenticated browser acceptance verifies layout parity, Road preview auto-connect, Stream Stop/Play, Road Worker Stop while preview stays available and Water stays unchanged, Road Worker Start with advancing exact-source Road state, calibration/diagnostics/events, and protected public Authentik boundary.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: accept only fixed Water/Road targets and fixed agent/API paths; never accept service names or commands | Validation: worker-control and API contract tests | Residual risk: bounded control agent remains privileged but only fixed services are addressable | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: persist independent Road desired state and preserve it through update/rollback/deploy verification | Validation: exact updater/rollback/deploy tests | Residual risk: runtime service state can still be unhealthy for environmental reasons and must fail closed | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: mirror canonical Operator layout markers and reuse existing Road analytics/preview endpoints | Validation: frontend contract and browser smoke | Residual risk: visual browser differences require final manual acceptance | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: deploy Ubuntu before VPS and retain automatic rollback on exact Ubuntu activation failure | Validation: deployment transaction evidence | Residual risk: mixed rollout may temporarily leave old VPS UI against new backward-compatible Ubuntu control, which is safe | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: retain exact private M2M endpoint list and explicitly forbid all browser-control paths | Validation: nginx renderer regression | Residual risk: future endpoint additions require the same fail-closed regression | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002,AC-003 | Level: integration | Priority: P0 | Evidence: tests/test_frontend_contract.py and tests/test_auth_session_frontend_contract.py
- TEST-002 | Covers: AC-004,AC-005 | Level: unit | Priority: P0 | Evidence: tests/test_worker_operator_control.py and tests/test_api_contract.py
- TEST-003 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py
- TEST-004 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_deploy_authorized.py
- TEST-005 | Covers: AC-008 | Level: unit | Priority: P0 | Evidence: tests/test_ubuntu_worker_systemd.py
- TEST-006 | Covers: AC-009 | Level: integration | Priority: P0 | Evidence: tests/test_sea_speed_auth_v1.py
- TEST-007 | Covers: AC-010 | Level: end-to-end | Priority: P0 | Evidence: exact-head PR Validation and aggregate Quality integration plus post-merge main Quality
- TEST-008 | Covers: AC-011 | Level: runtime-manual | Priority: P0 | Evidence: Issue #206 Ubuntu/VPS deployment manifests and authenticated Road browser smoke

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: Continue the approved implementation and normal exact-green delivery lifecycle.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains unchanged and execution is rejected | Retry: only after exact-main quality, release provenance and durable production authorization are valid | Rollback: not applicable because no mutation occurred | Evidence: runtime router authorization and exact-main checks
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: existing Ubuntu and VPS releases remain active | Retry: after capability, protected-config, desired-state and rollback-target preflight passes | Rollback: not applicable because no runtime mutation occurred | Evidence: Ubuntu protected backup/preflight and VPS protected-baseline evidence
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: Ubuntu updater restores previous exact service topology on activation failure; VPS deploy owns its existing candidate rollback transaction | Retry: only after actual state is re-resolved and failure audit is complete | Rollback: Ubuntu automatic exact rollback plus protected-config restore; VPS existing automatic release/auth-boundary rollback | Evidence: updater/deploy logs and rollback markers
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: any unverified candidate is rolled back or execution fails closed with actual state recorded | Retry: only after verification failure root cause and adjacent stages are reviewed | Rollback: exact prior Ubuntu release and prior VPS release/boundary | Evidence: exact source/runtime identity, desired-state checks, health, Road freshness and public auth smoke
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: active release markers/manifests are not accepted unless verification passed | Retry: after exact runtime identity is restored or revalidated | Rollback: restore prior active source marker/release if commit cannot be completed safely | Evidence: active-source marker, VPS current-release marker and deployment manifests
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified active runtime remains accepted; temporary/stale cleanup may remain | Retry: safe after accepted runtime state without changing active release | Rollback: no rollback of a verified release for housekeeping-only failure | Evidence: cleanup/pruning warnings and retained current/previous releases
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: runtime may be healthy but task cannot become DONE without durable evidence | Retry: re-read machine-observable state and persist sanitized evidence; do not redeploy solely to regenerate evidence | Rollback: not applicable to evidence recording | Evidence: Issue #206 comments, exact run IDs, manifests, browser acceptance record
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: previous exact release/config/service state is restored or task records a critical unresolved production state | Retry: prohibited until full transaction audit and adjacent-stage review resolve safety | Rollback: exact known previous Ubuntu/VPS release and protected predeployment state | Evidence: rollback command markers, exact previous SHA, restored service/health checks

## Runtime feedback

- Current source base at admission: `f80204de6a86147fdafc70cec1cc1463ad66ddaa`.
- Ubuntu execution capability: `ONE_COMMAND_FALLBACK`; VPS execution capability: `CONNECTOR`.
- Runtime deployment is not authorized by source approval. A fresh production fingerprint bound to the exact merged main SHA is required.
- Final browser parity remains runtime-manual evidence because static tests can prove structure/contracts but not protected visual usability and live media behavior.
