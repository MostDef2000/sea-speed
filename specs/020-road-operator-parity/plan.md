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

For exact runtime release `fd449af7bdbd4036517f321b96de31fe206f623b`, the VPS least-privilege Auth boundary is source-bound. PR #207 changed `scripts/operations/nginx_sea_speed_auth.py`, which is an asset in the root-owned privileged bundle. Therefore the VPS contour requires one root-owned exact-source bootstrap before the canonical Connector VPS deployment can pass its pre-mutation privilege admission.

## Decisions

- D-001: Reproduce canonical Operator structure/styles in the Road document instead of changing the Water Operator reference.
- D-002: Reuse existing Road analytics and protected preview endpoints; do not create a second preview architecture.
- D-003: Extend the existing worker-control protocol with fixed Road paths rather than introduce arbitrary target parameters.
- D-004: Persist Road desired state separately from Water so operator actions do not couple the two services.
- D-005: Preserve exact commit/runtime identity checks when Road is stopped; skip only frame/state progression because intentional stop makes progression impossible.
- D-006: Keep private Worker-to-VPS telemetry/config ingress unchanged and explicitly enumerate browser-control routes that must never enter it.
- D-007: Runtime deployment is MIXED and must be Ubuntu-first/VPS-second under a fresh exact-main production envelope.
- D-008: Treat any source change to the root-owned Auth privileged bundle as requiring `ONE_COMMAND_FALLBACK` for the VPS contour. The bootstrap installs only the exact repository-owned helper/bundle/minimal sudoers boundary; Connector deployment remains the only post-bootstrap VPS release transaction.

## Affected contours

- VPS: REQUIRED. Road frontend, FastAPI Road worker-control routes and nginx security regression are included in exact runtime release `fd449af7bdbd4036517f321b96de31fe206f623b`. Execution capability is `ONE_COMMAND_FALLBACK` because the exact root-owned Auth privilege bundle must be bootstrapped before Connector retry.
- Ubuntu Worker/relay: REQUIRED. Fixed Road control paths, independent desired state and exact update/rollback/deployment semantics change. Execution capability is `ONE_COMMAND_FALLBACK`.
- Windows: retired and not an active production contour.
- Operator actions expected: `2`. Ubuntu action `1/2` is already accepted for exact runtime release `fd449af7bdbd4036517f321b96de31fe206f623b`; VPS root privilege-bundle bootstrap is action `2/2` and remains pending.
- The current three-path production-learning correction is CONTROL_PLANE/SDD only and creates no new runtime release identity.

## Validation

Source validation for the original product release covers Python syntax/import contracts, shell syntax, frontend static contract, fixed control allowlists, independent desired-state behavior, nginx private-ingress exclusion, synchronized analytics-profile Road control/private-source regression, exact updater/rollback/deploy transaction semantics, SDD validation, exact-artifact validation, exact approved 21-path scope, PR Validation and aggregate Quality integration.

Production-learning correction validation is exact and bounded to `spec.md`, `plan.md` and `tasks.md`; it must pass PR Validation and aggregate Quality on the same corrective head, expected-head merge, and post-merge Quality. It must not alter runtime-installed source, the Outcome Contract, protected topology, production authorization fingerprint fields or the already authorized exact runtime target.

Runtime validation after correction resumes from existing evidence: Ubuntu exact deployment is already accepted. Next, execute one repository-owned root VPS privilege-bundle bootstrap for exact `fd449af7bdbd4036517f321b96de31fe206f623b`, then retry the canonical Connector VPS deployment. Authenticated browser acceptance verifies layout parity, Road preview auto-connect, Stream Stop/Play, Road Worker Stop while preview stays available and Water stays unchanged, Road Worker Start with advancing exact-source Road state, calibration/diagnostics/events, and protected public Authentik boundary.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: accept only fixed Water/Road targets and fixed agent/API paths; never accept service names or commands | Validation: worker-control and API contract tests | Residual risk: bounded control agent remains privileged but only fixed services are addressable | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: persist independent Road desired state and preserve it through update/rollback/deploy verification | Validation: exact updater/rollback/deploy tests | Residual risk: runtime service state can still be unhealthy for environmental reasons and must fail closed | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: mirror canonical Operator layout markers and reuse existing Road analytics/preview endpoints | Validation: frontend contract and browser smoke | Residual risk: visual browser differences require final manual acceptance | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: deploy Ubuntu before VPS and retain automatic rollback on exact Ubuntu activation failure | Validation: deployment transaction evidence | Residual risk: mixed rollout may temporarily leave old VPS UI against new backward-compatible Ubuntu control, which is safe | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: retain exact private M2M endpoint list and explicitly forbid all browser-control paths | Validation: nginx renderer plus analytics-profile regression | Residual risk: future endpoint additions require the same fail-closed regression | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-006 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: classify source-bound VPS privileged-bundle changes as `ONE_COMMAND_FALLBACK`, count the root bootstrap in the operator action budget, and fail closed before source activation when bundle identity mismatches | Validation: production-learning evidence from run `32022719065`, exact SDD correction CI and subsequent exact bootstrap/Connector retry | Residual risk: a future bundle-affecting change could again be misclassified unless capability derivation stays synchronized with the privilege-boundary contract | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002,AC-003 | Level: integration | Priority: P0 | Evidence: tests/test_frontend_contract.py and tests/test_auth_session_frontend_contract.py
- TEST-002 | Covers: AC-004,AC-005 | Level: unit | Priority: P0 | Evidence: tests/test_worker_operator_control.py and tests/test_api_contract.py
- TEST-003 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_exact_updater.py and tests/test_ubuntu_worker_rollback.py
- TEST-004 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_deploy_authorized.py
- TEST-005 | Covers: AC-008 | Level: unit | Priority: P0 | Evidence: tests/test_ubuntu_worker_systemd.py
- TEST-006 | Covers: AC-009,AC-010 | Level: integration | Priority: P0 | Evidence: tests/test_sea_speed_auth_v1.py and tests/test_analytics_profiles.py
- TEST-007 | Covers: AC-010 | Level: end-to-end | Priority: P0 | Evidence: exact-head PR Validation and aggregate Quality integration plus post-merge main Quality
- TEST-008 | Covers: AC-011 | Level: runtime-manual | Priority: P0 | Evidence: Issue #206 Ubuntu/VPS deployment manifests and authenticated Road browser smoke
- TEST-009 | Covers: AC-012 | Level: control-plane | Priority: P0 | Evidence: exact three-path corrective PR diff, PR Validation, aggregate Quality, post-merge Quality, production-learning Issue evidence, exact root bootstrap output and Connector VPS retry

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Product outcome and protected runtime semantics are unchanged. Production evidence corrected the delivery capability/action budget for the already authorized exact runtime release.
- Specification impact: FR-015 and AC-012 record the exact-source VPS privilege-bundle bootstrap requirement and combined two-action budget; runtime feedback records the accepted Ubuntu action and fail-closed VPS attempt.
- Plan impact: VPS execution capability is corrected to `ONE_COMMAND_FALLBACK`; operator actions expected are corrected to `2`; production-learning validation, RISK-006, TEST-009 and adjacent-stage review are added.
- Tasks impact: source/merge steps for PR #207 are marked complete, Ubuntu runtime action is marked complete, and VPS-second is corrected to require root bootstrap before Connector retry.
- Authorization impact: RESOLVED. A fresh complete six-field three-path Scope was presented immediately before the operator replied `OUTCOME APPROVED`; durable admission evidence is Issue #206 comment `5315197764`.
- Follow-up: Merge only the exact green three-path correction. Then execute only the remaining VPS root bootstrap for exact runtime release `fd449af7bdbd4036517f321b96de31fe206f623b`, retry the canonical Connector VPS deployment, and continue runtime/browser acceptance.

## Production-learning adjacent-stage review

- Previous stage review: Ubuntu-first mutation and verification completed successfully for exact `fd449af7bdbd4036517f321b96de31fe206f623b`; protected configuration reconciled; Water desired state remained `stopped`; Road desired state remained `running`; Road runtime progression passed.
- Failing stage review: VPS pre-mutation privilege admission in runtime orchestrator #115 / `32022719065` verified source, Quality, authorization, release provenance and SSH, then failed closed with `ERROR privileged bundle source SHA does not match request` and `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES` before completed candidate activation.
- Next stage review: deployment manifest collection/upload was skipped because VPS mutation did not complete; no VPS release is accepted from the failed attempt. The admissible next mutation is the repository-owned exact root privilege-bundle bootstrap, followed by Connector retry for the same authorized runtime SHA.
- Rollback review: no new VPS candidate was accepted, so the prior accepted VPS runtime remains the effective rollback/live baseline. Ubuntu rollback remains the previously captured exact source/protected-state transaction if later runtime acceptance fails.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains unchanged and execution is rejected | Retry: only after exact target quality, release provenance and durable production authorization are valid | Rollback: not applicable because no mutation occurred | Evidence: runtime router authorization and exact-target first-parent checks
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: existing accepted runtime remains authoritative; source-bound VPS privileged bundle mismatch blocks candidate activation | Retry: Ubuntu requires protected-config/desired-state/rollback preflight; VPS additionally requires exact-source root privilege-bundle bootstrap before Connector deployment when bundle assets changed | Rollback: privilege installer transaction restores previous helper/bundle/sudoers state on bootstrap failure; otherwise no release rollback is needed before candidate activation | Evidence: Ubuntu protected backup/preflight, VPS privilege status output and root bootstrap output
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: Ubuntu updater restores previous exact service topology on activation failure; VPS deploy owns its existing candidate rollback transaction | Retry: only after actual state is re-resolved and failure audit is complete | Rollback: Ubuntu automatic exact rollback plus protected-config restore; VPS existing automatic release/auth-boundary rollback | Evidence: updater/deploy logs and rollback markers
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: any unverified candidate is rolled back or execution fails closed with actual state recorded | Retry: only after verification failure root cause and adjacent stages are reviewed | Rollback: exact prior Ubuntu release and prior VPS release/boundary | Evidence: exact source/runtime identity, desired-state checks, health, Road freshness and public auth smoke
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: active release markers/manifests are not accepted unless verification passed | Retry: after exact runtime identity is restored or revalidated | Rollback: restore prior active source marker/release if commit cannot be completed safely | Evidence: active-source marker, VPS current-release marker and deployment manifests
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified active runtime remains accepted; temporary/stale cleanup may remain | Retry: safe after accepted runtime state without changing active release | Rollback: no rollback of a verified release for housekeeping-only failure | Evidence: cleanup/pruning warnings and retained current/previous releases
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: runtime may be healthy but task cannot become DONE without durable evidence | Retry: re-read machine-observable state and persist sanitized evidence; do not redeploy solely to regenerate evidence | Rollback: not applicable to evidence recording | Evidence: Issue #206 comments, exact run IDs, manifests, browser acceptance record
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: previous exact release/config/service state is restored or task records a critical unresolved production state | Retry: prohibited until full transaction audit and adjacent-stage review resolve safety | Rollback: exact known previous Ubuntu/VPS release and protected predeployment state | Evidence: rollback command markers, exact previous SHA, restored service/health checks

## Runtime feedback

- Original product source merge/main: `fd449af7bdbd4036517f321b96de31fe206f623b`; this remains the authorized runtime release target.
- Current production-learning correction base: `fd449af7bdbd4036517f321b96de31fe206f623b`; correction repository scope is exactly three SDD paths and creates no new runtime-installed source.
- Ubuntu execution capability: `ONE_COMMAND_FALLBACK`; action `1/2` completed and runtime acceptance for the Ubuntu deployment transaction passed.
- VPS execution capability: corrected from `CONNECTOR` to `ONE_COMMAND_FALLBACK`; action `2/2` is the exact root privilege-bundle bootstrap. Connector remains the post-bootstrap VPS deployment transport.
- Runtime orchestrator #115 / `32022719065` failed only because the exact-source root bundle was not bootstrapped; the workflow's source/Quality/authorization/provenance/SSH admission gates passed and candidate deployment evidence was not accepted.
- Existing production authorization fingerprint remains bound to the unchanged Outcome Contract, runtime contour fields, security impact, production-impact rationale and rollback target for exact runtime release `fd449af7bdbd4036517f321b96de31fe206f623b`; this correction does not change those fingerprint inputs.
- Final browser parity remains runtime-manual evidence because static tests can prove structure/contracts but not protected visual usability and live media behavior.
