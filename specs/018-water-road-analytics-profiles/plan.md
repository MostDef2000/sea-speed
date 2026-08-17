# Implementation Plan: Water and road analytics profiles

- Specification: specs/018-water-road-analytics-profiles/spec.md
- Issue: #197
- Status: Production remediation

## Architecture

1. **Profile normalization boundary.** `worker/analytics_profiles.py` remains the common water/road semantic normalization boundary; worker inference/tracking/speed behavior is unchanged by the corrective work.
2. **Process isolation.** `sea-speed-worker.service` and `sea-speed-road-worker.service` remain separate Ubuntu processes sharing immutable source/runtime/model storage but not tracker/output/heartbeat state.
3. **Protected Road binding.** `road1` media remains resolved from the protected preview catalog and Road API endpoints remain derived from the protected Camera 1 private M2M origin.
4. **Public/private separation.** Public `/sea-speed/**` remains Authentik-protected. The private VPS listener remains exact-peer, exact-path, exact-method and deny-by-default.
5. **Canonical VPS transaction.** `deploy/vps/deploy.sh` owns exact code rollout, API/frontend health, private-boundary reconciliation, deployment manifest, source rollback and evidence. `sea-speed-auth-cutover.sh` owns protected nginx candidate/rollback semantics.
6. **Least-privilege bridge.** Root-only nginx reconciliation is exposed to the non-root deployment account only through `/usr/local/sbin/sea-speed-auth-privileged-helper`. The sudoers rule permits exactly that command with no arguments. The helper reads one fixed request file, binds one exact source SHA, verifies a root-owned exact privileged bundle and staged release digests, then executes only root-owned cutover/renderers with fixed approved topology.
7. **Pre-mutation capability gate.** Exact release staging may occur before privilege admission, but no live API/frontend mutation, restart, current/previous release state mutation or deployment-manifest commit may occur until helper `status` proves the exact source/bundle match.
8. **One-time bootstrap.** The third corrective runtime contour is VPS only with `ONE_COMMAND_FALLBACK`: one operator/root bootstrap installs the exact root-owned helper/bundle/minimal sudoers rule. After installation, the existing Connector deployment continues without interactive sudo.

## Decisions

### D-001 - Normalize at detector boundary
- Decision: Keep model-class normalization before tracking/event logic.
- Reason: Preserves one reusable pipeline and existing accepted behavior.
- Alternatives rejected: duplicated worker implementations or downstream model-specific semantics.

### D-002 - Two Ubuntu services, one immutable runtime
- Decision: Keep isolated water/road services and shared immutable runtime/model store.
- Reason: Prevents tracker/state cross-camera contamination without duplicating CUDA runtime storage.
- Alternatives rejected: one multiplexed tracker process; duplicated runtime stores.

### D-003 - Logical road identity only in source
- Decision: Repository knows only logical `road1`; physical source remains protected runtime state.
- Reason: Preserves credential and topology separation.
- Alternatives rejected: commit physical RTSP details or accept arbitrary browser RTSP input.

### D-004 - Additive API compatibility
- Decision: Preserve generic analytics routes plus legacy `/api/cam1/**` wrappers.
- Reason: No flag-day migration or schema break is required.
- Alternatives rejected: route renames/removals or duplicate road-only API families.

### D-005 - External model staging
- Decision: Keep `yolo26x.pt` runtime-only and digest/CUDA self-tested.
- Reason: Model binaries remain outside Git/release artifacts.
- Alternatives rejected: commit/download/fallback model behavior.

### D-006 - Exact-diff runtime applicability
- Decision: Preserve historical PR #198 mixed applicability; classify every corrective diff independently.
- Reason: Runtime applicability is an exact changed-path property.
- Alternatives rejected: rewrite historical evidence or redeploy unused Windows runtime for unrelated corrections.

### D-007 - Private Road M2M origin
- Decision: Road worker endpoints derive only from validated private Camera 1 M2M origin.
- Reason: Public Authentik redirect flow is browser-facing and caused the first production defect.
- Alternatives rejected: public API URL, second committed origin, Authentik bypass.

### D-008 - Exact private route matrix
- Decision: Private ingress exposes only the approved Road state/events/ROI/speed-config/speed-lines matrix and legacy Camera 1 machine paths.
- Reason: Maintains least privilege at the HTTP boundary.
- Alternatives rejected: wildcard analytics ingress or browser worker-control exposure.

### D-009 - Boundary acceptance inside VPS deployment
- Decision: VPS success requires `auth_v1_road_private_m2m=passed` in deployment evidence.
- Reason: API/frontend source identity alone did not prove nginx boundary activation.
- Alternatives rejected: optional/manual post-deploy cutover.

### D-010 - Protected-baseline rollback
- Decision: Candidate Auth mutation is admitted only from an already-protected baseline and restores that captured baseline on failure.
- Reason: Rollback must not recreate retired/unprotected public behavior.
- Alternatives rejected: arbitrary historical config restore or no automatic boundary rollback.

### D-011 - Fixed no-argument root helper
- Decision: Do not give GitHub Actions root SSH or broad NOPASSWD. Install one root-owned helper and root-owned exact bundle; sudoers permits the helper with explicit empty argument list only.
- Reason: The `f21b31...` production run proved root privilege is required for nginx but broad root execution is unnecessary. A fixed helper constrains blast radius while preserving zero-touch Connector execution after one bootstrap.
- Alternatives rejected: root SSH credential; `NOPASSWD: ALL`; passwordless `bash`, `python`, `nginx`, `cp`, `install` or arbitrary systemctl; executing release-directory scripts as root.

## Affected contours

- Repository: third correction is exactly the separately authorized 11-path least-privilege remediation on Issue #197.
- VPS: REQUIRED after merge and fresh exact-SHA production authorization.
- VPS execution capability: `ONE_COMMAND_FALLBACK` for one root bootstrap, then Connector continuation for the same exact release transaction.
- Ubuntu Worker/relay: NOT APPLICABLE to the third corrective source diff; pending first-correction Ubuntu runtime action remains paused until VPS boundary evidence is green.
- Windows Worker: NOT APPLICABLE; no shared `worker/**` or Windows-specific source changes.
- Security: privilege boundary changes; public Authentik, private route matrix and network topology remain unchanged.

## Validation

- `tests/test_vps_auth_privilege_boundary.py`: exact request schema/actions/path, digest binding, symlink/path escape rejection, fixed topology, root-owned cutover execution and installer/sudoers contract.
- `tests/test_vps_deploy_transaction.py`: real deployment entrypoint with isolated fake runtime proves missing/mismatched helper stops before live mutation; accepted helper retains success, source rollback, Auth rollback, already-current fail-closed and housekeeping behavior.
- `tests/quality/test_quality_architecture.py`: exact VPS artifact contains installer/helper/cutover/renderers and deployment source uses the restricted privilege gate.
- `scripts/quality/build_exact_artifacts.py` / `validate_exact_artifacts.py`: deterministic packaging, digest/extraction/shell/Python syntax validation for privilege assets.
- Existing Auth v1/profile/API/frontend/worker tests remain regression evidence; no product/API/Ubuntu implementation changes are introduced.
- End-to-end source: exact 11-path compare, PR Validation, aggregate Quality integration, fresh main/head/scope/review gate, expected-head merge and post-merge push/main quality.
- Runtime after separate production authorization: root bootstrap evidence -> helper status exact SHA -> Connector VPS deploy -> deployment manifest with `auth_v1_road_private_m2m=passed` -> public/Auth/Camera1 regression -> only then pending Ubuntu Road continuation.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: physical camera credentials/model binaries remain outside repository and API/browser | Validation: repository secret/binary checks and existing profile/runtime evidence | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: PERF | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: corrective source changes no inference workload | Validation: final runtime frame/AI progression | Residual risk: MEDIUM until runtime acceptance | Owner: Delivery Orchestrator | Status: OPEN
- RISK-003 | Category: DATA | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: no API/storage schema or migration change | Validation: exact scope and API regression | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: no worker inference code change | Validation: exact no-`worker/**` diff plus existing worker tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: pre-mutation privilege status gate, exact helper/bundle SHA binding and existing source/nginx rollback transactions | Validation: real deploy fault-path tests and production evidence | Residual risk: MEDIUM until first accepted production run | Owner: Delivery Orchestrator | Status: OPEN
- RISK-006 | Category: BUS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: water taxonomy/product behavior unchanged | Validation: existing class tests | Residual risk: MEDIUM | Owner: Product owner | Status: ACCEPTED
- RISK-007 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: Ubuntu/Windows source unaffected by third correction | Validation: exact changed-file classification | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-008 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: exact peer/path/method nginx boundary retained | Validation: existing Auth v1 renderer/verifier tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-009 | Category: OPS | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: final product acceptance requires VPS-observed Road source/frame freshness, not worker-local POST logs | Validation: production runtime acceptance | Residual risk: MEDIUM until runtime evidence | Owner: Delivery Orchestrator | Status: OPEN
- RISK-010 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: sudoers permits one fixed helper with no args; helper verifies its own/root-bundle/staged digests and fixed topology, and never executes writable release code | Validation: privilege-boundary tests | Residual risk: LOW after CI, MEDIUM until root bootstrap inspection | Owner: Delivery Orchestrator | Status: OPEN
- RISK-011 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: installer stages and validates sudoers before activation and restores previous helper/bundle/sudoers on injected post-install failure | Validation: installer contract/fault tests and bootstrap output | Residual risk: MEDIUM until first bootstrap | Owner: Delivery Orchestrator | Status: OPEN
- RISK-012 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: privilege request is fixed-path mode 0600, exact-field schema only, canonical exact release path, no symlink components, exact SHA and digest bound | Validation: helper behavioral tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: unit | Priority: P1 | Evidence: `tests/test_analytics_profiles.py`
- TEST-002 | Covers: AC-003,AC-004,AC-005 | Level: integration | Priority: P1 | Evidence: unchanged worker/API contract suites
- TEST-003 | Covers: AC-006,AC-007 | Level: end-to-end | Priority: P2 | Evidence: existing frontend contract plus runtime browser smoke
- TEST-004 | Covers: AC-008,AC-009 | Level: integration | Priority: P1 | Evidence: existing Ubuntu/model/artifact tests
- TEST-005 | Covers: AC-014,AC-015 | Level: integration | Priority: P0 | Evidence: private-origin and Auth v1 route matrix tests
- TEST-006 | Covers: AC-016,RISK-002,RISK-009 | Level: runtime-manual | Priority: P0 | Evidence: final VPS/Ubuntu Road state/source/frame/events/objects/preview acceptance
- TEST-007 | Covers: AC-017,AC-021,RISK-010,RISK-012 | Level: integration | Priority: P0 | Evidence: `tests/test_vps_auth_privilege_boundary.py`, exact-artifact validator
- TEST-008 | Covers: AC-018,AC-023,RISK-005 | Level: end-to-end | Priority: P0 | Evidence: real `deploy/vps/deploy.sh` isolated transaction tests
- TEST-009 | Covers: AC-019 | Level: integration | Priority: P0 | Evidence: existing `tests/test_sea_speed_auth_v1.py`
- TEST-010 | Covers: AC-022,RISK-010,RISK-011 | Level: integration | Priority: P0 | Evidence: privilege installer contract/failure tests
- TEST-011 | Covers: AC-024,RISK-005,RISK-010 | Level: end-to-end | Priority: P0 | Evidence: exact 11-path compare, exact-head CI/merge/post-merge quality, then bootstrap + Connector production evidence

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #197 remains canonical. Exact production run `f21b31d38e95179445e68e5543a1c934a744d514` proved the second source design reached the correct root-only Auth transaction, but the non-root Connector deployment account lacked a non-interactive least-privilege way to execute it; `sudo` requested a password and the deployment rolled source back to `30e77e1f42397fddabc2a36fcfe922416a8efe57`.
- Specification impact: Adds least-privilege root helper/install requirements, pre-live-mutation privilege admission and one-command bootstrap semantics.
- Plan impact: Adds a fixed root-owned privileged bundle/helper boundary and moves privilege capability verification before live source mutation.
- Tasks impact: Adds the separately authorized exact 11-path third correction, root bootstrap runtime step and Connector retry/acceptance sequence.
- Authorization impact: The privilege helper/installer and tests are outside the earlier 12-path authorization. A fresh six-field exact 11-path Scope was shown immediately before the operator supplied `OUTCOME APPROVED` on 2026-08-17. Source authorization does not authorize production.
- Follow-up: Complete exact 11-path source integration, obtain a new exact-SHA production authorization, execute one root bootstrap on VPS, then continue the same authorized Connector VPS transaction automatically and resume Ubuntu only after VPS M2M evidence is green.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on current exact source and existing protected nginx; Ubuntu remains paused | Retry: repair exact-main/quality/release/authorization evidence before SSH | Rollback: NOT REQUIRED | Evidence: first-parent main, exact PR/Issue, aggregate push/main quality, release manifest, production authorization verifier
- TX-002 | Stage: PRE-MUTATION | Mutation: RELEASE-STAGING-ONLY | Failure disposition: FATAL | State after failure: live API/frontend/nginx/current-release/deployment-manifest remain unchanged; exact candidate release directory may be staged | Retry: install/reinstall exact privilege bundle with one authorized root bootstrap, then rerun Connector | Rollback: staged release may remain; no live rollback required | Evidence: exact artifact includes helper/installer/cutover/renderers; helper `status` exact SHA/digest markers; `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES` on absence/mismatch
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate API/frontend and/or candidate nginx may exist only after privilege preflight passed | Retry: only after actual rollback state is known | Rollback: Auth helper invokes cutover protected-backup rollback; deploy restores previous source/frontends on candidate failure | Evidence: deployment log, cutover rollback markers, source rollback health
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted if API, public frontend, Authentik, exact private Road matrix, H264 or protected-baseline verification fails | Retry: diagnose exact failing check after bounded rollback | Rollback: protected nginx backup plus previous exact source as applicable | Evidence: helper/cutover PASS markers, origin/public checks, private Road base and rollback capability
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: current/previous release markers and deployment manifest must not advance unless source and Auth boundary both pass | Retry: read live state/manifest before repeating | Rollback: previous source/protected nginx remain known targets | Evidence: `runtime_verified=true` plus `auth_v1_road_private_m2m=passed`
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: accepted source/boundary remain active; stale release cleanup may remain | Retry: independent cleanup | Rollback: NOT REQUIRED solely for stale release cleanup | Evidence: prune logs/warnings and retained root backups
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: runtime may be healthy but Ubuntu/product acceptance cannot advance without exact deployment/bootstrap evidence | Retry: recollect read-only evidence; do not mutate merely to recreate paperwork | Rollback: decide from runtime truth, not missing paperwork | Evidence: root bootstrap sanitized output, deployment artifact/manifest, Issue #197 evidence
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if installer rollback, protected-nginx rollback or source rollback verification fails, automation stops and runtime truth is treated as unknown | Retry: read-only recovery plus new protected human/production decision | Rollback: only previous installed privilege bundle/sudoers, captured protected nginx backup and previous exact source | Evidence: `SEA_SPEED_AUTH_PRIVILEGE_INSTALL_ROLLBACK=PASS`, Auth rollback markers, previous source/API/frontend health

- Adjacent-stage review: COMPLETE
- Production-learning root cause: the second correction correctly made `deploy/vps/deploy.sh` invoke the root-required Auth transaction, but design/CI assumed the existing non-root deployment account could satisfy `sudo -n` for that arbitrary `bash <release>/sea-speed-auth-cutover.sh` command. Production proved no such restricted sudo policy existed; sudo demanded a password. The source rollback worked, but privilege capability was discovered after candidate source mutation instead of being an explicit pre-mutation admission gate.
- Production-learning adjacent-stage findings: admission/quality correctly bound exact source and authorization but did not prove target privilege capability; pre-mutation staged the candidate and proceeded without a root-helper compatibility check; mutation successfully installed/restarted candidate source before the privilege failure; verification never reached nginx because sudo failed; state-commit correctly did not accept the candidate; housekeeping/evidence were skipped by workflow after failure; source rollback restored `30e77...` and public health. The third correction therefore adds an explicit least-privilege capability artifact, one-time bootstrap, exact digest-bound status preflight before live source mutation, and deterministic fault tests for absent/mismatched privilege state.

## Rollout and rollback

- Third corrective source rollout: fresh branch from `f21b31d38e95179445e68e5543a1c934a744d514` -> exact 11-path compare -> PR linked #197/spec 018 -> PR Validation + aggregate Quality on one exact head -> fresh main/head/scope/review verification -> expected-head merge -> post-merge push/main quality.
- Third corrective production rollout: after fresh exact-SHA production authorization, operator performs one root VPS server-pull/bootstrap from the exact merged SHA to run `install-auth-privilege-boundary.sh <sha> <deployment-user>`. Bootstrap output must show exact SHA, non-root deployment user, fixed-helper/no-args sudo scope and no root shell grant. The Orchestrator then reruns/continues the Connector VPS deployment for that exact SHA; helper status must pass before live source mutation and final manifest must contain `auth_v1_road_private_m2m=passed`.
- Privilege bootstrap rollback: installer restores prior helper/bundle/sudoers state on post-install failure and validates sudoers before activation. A failed bootstrap does not authorize a broad manual sudo workaround.
- VPS transaction rollback: existing source rollback and protected nginx backup rollback remain authoritative after privilege preflight succeeds.
- Pending first-correction Ubuntu rollout: resumes only after accepted VPS boundary evidence. Main Water Worker desired-stopped state remains preserved unless separately changed. Windows has no corrective action.

## Runtime feedback

- Original source integration: complete on `39cc330b61dc50aede4b809ee2dfc7a712b698d9`; historical #198 evidence remains immutable.
- First production learning: Road worker used the wrong public M2M surface and worker-local POST success was misleading.
- First corrective source: PR #200 merged as `30e77e1f42397fddabc2a36fcfe922416a8efe57`.
- Second production learning: VPS source deploy did not execute source-managed nginx boundary transaction.
- Second corrective source: PR #201 merged as `f21b31d38e95179445e68e5543a1c934a744d514` with green post-merge quality.
- Third production learning: authorized `f21b31...` Connector deployment reached Auth reconciliation, `sudo` required a password, and source automatically rolled back to `30e77...`. No broad root privilege was granted; Ubuntu remained paused.
- Third corrective source integration: IN PROGRESS on `agent/vps-auth-privilege-boundary` under the fresh exact 11-path source authorization.
- Third corrective production acceptance: PENDING new exact merged SHA and fresh production authorization; runtime starts with one root bootstrap, then Connector VPS acceptance. Ubuntu/Windows are NOT APPLICABLE to this exact source diff.
