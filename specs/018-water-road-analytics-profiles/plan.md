# Implementation Plan: Water and road analytics profiles

- Specification: specs/018-water-road-analytics-profiles/spec.md
- Issue: #197
- Status: Production remediation

## Architecture

1. **Profile normalization boundary.** `worker/analytics_profiles.py` remains the common water/road semantic normalization boundary; worker inference/tracking/speed behavior is unchanged by corrective work.
2. **Process isolation.** `sea-speed-worker.service` and `sea-speed-road-worker.service` remain separate Ubuntu processes sharing immutable source/runtime/model storage but not tracker/output/heartbeat state.
3. **Protected Road binding.** `road1` media remains resolved from the protected preview catalog and Road API endpoints remain derived from the protected Camera 1 private M2M origin.
4. **Public/private separation.** Public `/sea-speed/**` remains Authentik-protected. The private VPS listener remains exact-peer, exact-path, exact-method and deny-by-default.
5. **Canonical VPS transaction.** `deploy/vps/deploy.sh` owns exact code rollout, API/frontend health, private-boundary reconciliation, deployment manifest, source rollback and evidence. `sea-speed-auth-cutover.sh` owns protected nginx candidate/rollback semantics.
6. **Least-privilege VPS bridge.** Root-only nginx reconciliation remains exposed to the non-root deployment account only through `/usr/local/sbin/sea-speed-auth-privileged-helper`; the accepted `e7dd921...` production run proved this boundary and `auth_v1_road_private_m2m=passed`.
7. **Canonical Ubuntu transaction.** `.github/workflows/deploy-ubuntu-worker.yml` remains transport/admission orchestration only. `deploy/worker/ubuntu/deploy-authorized.sh` owns target-side protected config reconciliation, exact activation, verification, deployment evidence and rollback.
8. **Protected config checkpoint.** Before updater activation, `deploy-authorized.sh` backs up `worker.env` and optional `road-worker.env`, runs the exact release's `configure-analytics-profiles.py` against the fixed protected preview catalog and accepts only a regular mode-600 resulting Road env.
9. **Coupled rollback.** If configuration fails, no updater activation is attempted. If updater activation fails, protected config is restored after updater-owned runtime restoration and predeployment Worker/Road service state is re-established. If post-activation verification fails, protected config is restored before source rollback so the restored previous Road service starts with its matching protected config.
10. **Desired-state preservation.** Main Water Worker operator desired state remains an invariant. A desired-stopped Water Worker is never started merely to reconcile Road; a desired-running Water Worker remains running after successful deployment and is restored on failed transactions.

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
- Decision: Private ingress exposes only approved Road state/events/ROI/speed-config/speed-lines and legacy Camera 1 machine paths.
- Reason: Maintains least privilege at the HTTP boundary.
- Alternatives rejected: wildcard analytics ingress or browser worker-control exposure.

### D-009 - Boundary acceptance inside VPS deployment
- Decision: VPS success requires `auth_v1_road_private_m2m=passed` in deployment evidence.
- Reason: API/frontend source identity alone did not prove nginx boundary activation.
- Alternatives rejected: optional/manual post-deploy cutover.

### D-010 - Protected-baseline VPS rollback
- Decision: Candidate Auth mutation is admitted only from an already-protected baseline and restores that captured baseline on failure.
- Reason: Rollback must not recreate retired/unprotected public behavior.
- Alternatives rejected: arbitrary historical config restore or no automatic boundary rollback.

### D-011 - Fixed no-argument root helper
- Decision: Do not give GitHub Actions root SSH or broad NOPASSWD. Install one root-owned helper and root-owned exact bundle; sudoers permits the helper with explicit empty argument list only.
- Reason: The `f21b31...` production run proved root privilege is required for nginx but broad root execution is unnecessary.
- Alternatives rejected: root SSH credential; `NOPASSWD: ALL`; passwordless `bash`, `python`, `nginx`, `cp`, `install` or arbitrary systemctl.

### D-012 - Protected profile reconciliation belongs to deploy-authorized
- Decision: Call `configure-analytics-profiles.py` from the exact staged target inside `deploy-authorized.sh`, after authorization/main admission and protected-config backup but before `update-exact.sh --activate`.
- Reason: The workflow fallback is transport only, while the updater deliberately consumes already-prepared protected config. The target transaction is the only layer that owns authorization, protected local state, activation and rollback together.
- Alternatives rejected: separate operator configure command; workflow-side protected configuration; changing `update-exact.sh`; trusting stale `road-worker.env`.

### D-013 - Restore config before restoring previous runtime
- Decision: After post-activation identity failure, restore protected env files before invoking `rollback-exact.sh`; after updater-owned rollback on activation failure, restore config and then restore the predeployment Worker/Road service state.
- Reason: A previous Road service restarted before config restoration could otherwise continue with the new/stale env in its process even though files were later restored.
- Alternatives rejected: file-only rollback without service reload; source rollback first with mismatched config; destructive deletion of all protected config.

## Affected contours

- Repository: fourth correction is exactly the separately authorized 5-path Ubuntu transaction remediation on Issue #197.
- VPS: NOT REQUIRED / NOT APPLICABLE for this exact diff. Accepted `e7dd921d569d9b93d9ac1be9113f61a162102b19` VPS boundary evidence remains prerequisite runtime evidence and is not redeployed.
- Ubuntu Worker/relay: REQUIRED after exact-green merge and fresh exact-SHA production authorization.
- Ubuntu execution capability: `ONE_COMMAND_FALLBACK`; one server-pull/bootstrap action stages exact main and hands off to corrected `deploy-authorized.sh`.
- Windows Worker: NOT APPLICABLE; no shared `worker/**` or Windows-specific source changes.
- Security: protected config contents and topology are unchanged; transaction ordering/rollback are strengthened and no secret value is added to source or evidence.

## Validation

- `tests/test_ubuntu_worker_deploy_authorized.py`: shell syntax; authorization/config/activation/verification/state-commit ordering; explicit protected config backup/restore; configure failure cannot reach updater activation; updater failure restores config and prior service state; post-activation verification restores config before source rollback; Water desired state/prior Road state preservation; secret-free deployment-manifest marker.
- Existing `tests/test_analytics_profiles.py`: unchanged private M2M URL derivation and protected preview catalog contract for `configure-analytics-profiles.py`.
- Existing Ubuntu updater/rollback/systemd tests remain regression evidence; fourth correction changes none of those files.
- Exact source: 5-path compare, PR Validation, aggregate Quality integration, fresh main/head/scope/review gate, expected-head merge and post-merge push/main quality.
- Runtime after separate production authorization: one Ubuntu fallback -> protected config reconciliation marker -> exact release/runtime/service identity -> Road frame/state progression -> deployment manifest -> VPS-observed `road1` fresh exact source/advancing frame/events/objects/preview -> Water desired-state and public/Auth/Camera1 regressions.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: physical camera credentials/model binaries remain outside repository and API/browser | Validation: repository secret/binary checks and existing profile/runtime evidence | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: PERF | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: corrective source changes no inference workload | Validation: final runtime frame/AI progression | Residual risk: MEDIUM until runtime acceptance | Owner: Delivery Orchestrator | Status: OPEN
- RISK-003 | Category: DATA | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: no API/storage schema or migration change | Validation: exact scope and API regression | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: no worker inference code change | Validation: exact no-`worker/**` diff plus existing worker tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: accepted VPS boundary remains fixed prerequisite and is not touched by Ubuntu-only correction | Validation: existing `e7dd921...` runtime evidence | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-006 | Category: BUS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: water taxonomy/product behavior unchanged | Validation: existing class tests | Residual risk: MEDIUM | Owner: Product owner | Status: ACCEPTED
- RISK-007 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: Windows/VPS source unaffected by fourth correction | Validation: exact changed-file classification | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-008 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: exact peer/path/method nginx boundary retained | Validation: accepted VPS boundary evidence and unchanged source | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-009 | Category: OPS | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: final product acceptance requires VPS-observed Road source/frame freshness, not worker-local POST logs | Validation: production runtime acceptance | Residual risk: MEDIUM until runtime evidence | Owner: Delivery Orchestrator | Status: OPEN
- RISK-010 | Category: SEC | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: accepted fixed VPS helper boundary is unchanged | Validation: no VPS path in fourth diff | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-011 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: protected worker/road env are backed up before exact helper reconciliation and restored on every modeled failure path | Validation: focused deploy-authorized rollback tests | Residual risk: MEDIUM until production run | Owner: Delivery Orchestrator | Status: OPEN
- RISK-012 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: reconciliation reuses the existing fail-closed private-origin/credential-free validation and fixed protected preview catalog; logs expose markers only | Validation: analytics profile tests plus secret-negative deploy test | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-013 | Category: OPS | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: configuration reconciliation is ordered before updater activation; configure failure restores files without restarting services | Validation: ordering/failure-path test | Residual risk: MEDIUM until runtime acceptance | Owner: Delivery Orchestrator | Status: OPEN
- RISK-014 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: updater failure path restores protected config and explicitly re-establishes predeployment Water/Road active state after updater-owned rollback | Validation: focused deployment transaction test | Residual risk: MEDIUM until runtime acceptance | Owner: Delivery Orchestrator | Status: OPEN
- RISK-015 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: post-activation verify failure restores config before previous-source rollback so previous Road restarts against matching env | Validation: rollback ordering test and production evidence if exercised | Residual risk: MEDIUM until runtime acceptance | Owner: Delivery Orchestrator | Status: OPEN

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: unit | Priority: P1 | Evidence: `tests/test_analytics_profiles.py`
- TEST-002 | Covers: AC-003,AC-004,AC-005 | Level: integration | Priority: P1 | Evidence: unchanged worker/API contract suites
- TEST-003 | Covers: AC-006,AC-007 | Level: end-to-end | Priority: P2 | Evidence: existing frontend contract plus runtime browser smoke
- TEST-004 | Covers: AC-008,AC-009 | Level: integration | Priority: P1 | Evidence: existing Ubuntu/model/artifact tests
- TEST-005 | Covers: AC-014,AC-015 | Level: integration | Priority: P0 | Evidence: private-origin and Auth v1 route matrix tests
- TEST-006 | Covers: AC-016,RISK-002,RISK-009 | Level: runtime-manual | Priority: P0 | Evidence: final VPS/Ubuntu Road state/source/frame/events/objects/preview acceptance
- TEST-007 | Covers: AC-017,AC-021 | Level: integration | Priority: P1 | Evidence: accepted exact-artifact/VPS privilege tests
- TEST-008 | Covers: AC-018,AC-023 | Level: end-to-end | Priority: P1 | Evidence: accepted real VPS deployment transaction tests
- TEST-009 | Covers: AC-019 | Level: integration | Priority: P1 | Evidence: existing `tests/test_sea_speed_auth_v1.py`
- TEST-010 | Covers: AC-022,AC-024 | Level: integration | Priority: P1 | Evidence: accepted privilege installer/production evidence
- TEST-011 | Covers: AC-025,RISK-013 | Level: integration | Priority: P0 | Evidence: `tests/test_ubuntu_worker_deploy_authorized.py` ordering/configure-failure assertions
- TEST-012 | Covers: AC-026,RISK-011,RISK-014,RISK-015 | Level: integration | Priority: P0 | Evidence: protected-config/update/verify rollback assertions in `tests/test_ubuntu_worker_deploy_authorized.py`
- TEST-013 | Covers: AC-016,AC-025,AC-026,RISK-009 | Level: runtime-manual | Priority: P0 | Evidence: exact Ubuntu deployment manifest plus VPS-observed final Road freshness/events/objects/preview and Water desired-state evidence

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #197 remains canonical. After the third correction's exact `e7dd921d569d9b93d9ac1be9113f61a162102b19` VPS boundary was accepted, read-only inspection before Ubuntu execution proved the canonical Ubuntu target transaction would not regenerate protected `road-worker.env`; the pending fallback was therefore stopped before mutation.
- Specification impact: Adds the requirement that protected profile reconciliation and its rollback are part of the canonical Ubuntu target transaction, not a separate operator/workflow step.
- Plan impact: Moves config backup/reconciliation before exact updater activation, couples config restoration with runtime rollback and makes Water/Road predeployment state explicit.
- Tasks impact: Adds the exact 5-path fourth correction, focused rollback/order tests, fresh exact-merge production authorization and one Ubuntu fallback acceptance sequence.
- Authorization impact: `deploy/worker/ubuntu/deploy-authorized.sh` behavior and its focused test/SDD updates are a new exact 5-path source scope. A complete six-field Scope immediately preceded the operator's `OUTCOME APPROVED` on 2026-08-17. Source authorization does not authorize production.
- Follow-up: Complete exact 5-path source integration, obtain a fresh production authorization for the new merge SHA, run one repository-owned Ubuntu fallback, and continue automatically through final VPS-observed Road/product acceptance.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: Ubuntu runtime/config/services remain unchanged and accepted VPS boundary remains active | Retry: repair exact-main/quality/release/production-authorization evidence before target transaction | Rollback: NOT REQUIRED | Evidence: exact first-parent main, canonical Issue/PR, push/main quality, exact artifact/release evidence, production authorization verifier
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: only root-owned updater staging/config backup files may exist; worker/road protected config and services remain at predeployment state | Retry: correct missing/invalid protected input and rerun the same exact authorized transaction | Rollback: restore config backup if reconciliation started; no source/service rollback before updater activation | Evidence: `PROTECTED_CONFIG_BACKUP=PASS`, helper fail-closed markers, no `DEPLOY_MUTATION` before reconciliation success
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: protected config may have been reconciled and exact updater may have partially activated target before its own rollback | Retry: only after protected config plus predeployment service state are restored and exact active marker/runtime truth is known | Rollback: updater restores previous exact units/runtime; deploy-authorized restores protected env and re-establishes predeployment Water/Road state | Evidence: `PROTECTED_CONFIG_RECONCILED=YES`, updater/restore markers, active source marker and systemd identity
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: target is not accepted if worker/control/road exact source/runtime identity, road env mode or desired Water state fails | Retry: only after config restore and previous-source or same-source predeployment service-state restoration | Rollback: restore protected config before `rollback-exact.sh` when target became active; otherwise restore predeployment service state | Evidence: exact `verify_active_target` checks, `DEPLOY_ROLLED_BACK ... config_restored=true` or `PREDEPLOYMENT_SERVICE_STATE_RESTORED=YES`
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment manifest must not claim runtime verification unless protected config reconciliation and exact runtime/service verification passed | Retry: re-read active marker/runtime/services/config and rerun only under current exact authorization | Rollback: previous exact source/config remains rollback target if state commit cannot be trusted | Evidence: deployment manifest check `protected-road-profile-config-reconciled=passed`, exact source/runtime/road active/desired-state checks
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: accepted exact runtime/config remains active; temporary stage/backups may remain only if process cleanup itself is interrupted | Retry: independent cleanup after read-only runtime verification | Rollback: NOT REQUIRED solely for temporary-file cleanup | Evidence: EXIT cleanup behavior and updater housekeeping evidence
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: runtime may be healthy but final product outcome remains incomplete without deployment manifest and VPS-observed Road evidence | Retry: recollect read-only deployment/runtime/product evidence; do not mutate merely to recreate paperwork | Rollback: decide from runtime truth, not missing evidence alone | Evidence: Ubuntu deployment manifest, heartbeat/state progression, VPS `road1` state/events/objects/preview and public/Auth/Camera1 regression evidence
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if protected config restoration, updater/explicit source rollback or predeployment service-state restoration fails, runtime truth is unknown and automatic retry stops | Retry: read-only recovery plus a new protected human/production decision after exact state is established | Rollback: only backed-up protected env, previous exact source/runtime/units and captured predeployment Worker/Road states | Evidence: `PROTECTED_CONFIG_RESTORED=YES`, updater/rollback markers, service active/inactive checks and active source marker

- Adjacent-stage review: COMPLETE
- Production-learning root cause: the first correction fixed `configure-analytics-profiles.py`, but the canonical Ubuntu deployment transaction never invoked that helper. The workflow one-command fallback correctly staged exact source and handed off to `deploy-authorized.sh`; `deploy-authorized.sh` correctly verified production authorization and called the exact updater; however the updater intentionally treats `road-worker.env` as protected predeployment input. That left a gap between configuration semantics and activation semantics, allowing stale public Road API URLs to survive into an otherwise exact deployment.
- Production-learning adjacent-stage findings: admission/quality/provenance were correct; pre-mutation validated exact source but not freshness of protected Road config; mutation would have restarted Road using the pre-existing env; verification checked exact source/runtime/service identity but not that the env had just been reconciled; state-commit could therefore have reported runtime verification without proving the corrected private M2M config; housekeeping/evidence would not reveal the stale endpoint because secrets/config values are intentionally not printed; rollback restored source/services but had no coupled protected-config rollback. The fourth correction closes all adjacent gaps by moving exact helper reconciliation, explicit backup/restore and a manifest reconciliation marker into `deploy-authorized.sh`.

## Rollout and rollback

- Fourth corrective source rollout: fresh branch from `e7dd921d569d9b93d9ac1be9113f61a162102b19` -> exact 5-path compare -> PR linked #197/spec 018 -> PR Validation + aggregate Quality on one exact head -> fresh main/head/scope/review verification -> expected-head merge -> post-merge push/main quality.
- Fourth corrective production rollout: after fresh exact-SHA production authorization, one Ubuntu server-pull fallback stages the exact merged SHA and invokes corrected `deploy-authorized.sh`. The target transaction backs up/reconciles protected config, activates/verifies exact source/runtime/services, preserves Water desired state and writes deployment evidence. No separate configure/activate confirmation is allowed.
- Configure failure rollback: restore protected env backup; services were not restarted, so no service mutation rollback is required.
- Updater failure rollback: rely on updater-owned runtime restoration, then restore protected env and explicitly re-establish predeployment Water/Road active state so processes reload matching config.
- Post-activation verification rollback: restore protected env first, then use `rollback-exact.sh` for a different previous source so the previous Road service starts with matching config; for same-source reconciliation failure restore predeployment service state directly.
- Final product acceptance: VPS accepted boundary remains unchanged; prove exact new Ubuntu source/runtime, advancing Road frame/state and AI, VPS-observed `worker_online=true` with exact source/advancing frame, events/objects, clean preview start/media/stop, public Auth/Camera1 regression and unchanged Water desired state.

## Runtime feedback

- Original source integration: complete on `39cc330b61dc50aede4b809ee2dfc7a712b698d9`; historical #198 evidence remains immutable.
- First production learning: Road worker used the wrong public M2M surface and worker-local POST success was misleading.
- First corrective source: PR #200 merged as `30e77e1f42397fddabc2a36fcfe922416a8efe57`.
- Second production learning: VPS source deploy did not execute source-managed nginx boundary transaction.
- Second corrective source: PR #201 merged as `f21b31d38e95179445e68e5543a1c934a744d514`.
- Third production learning: authorized `f21b31...` Connector deployment reached Auth reconciliation, `sudo` required a password, and source automatically rolled back to `30e77...`.
- Third corrective source: PR #202 merged as `e7dd921d569d9b93d9ac1be9113f61a162102b19`; root bootstrap and canonical Connector VPS deployment subsequently passed the fixed-helper boundary and `auth_v1_road_private_m2m=passed` acceptance.
- Fourth production learning: read-only inspection before Ubuntu mutation proved `deploy-authorized.sh` omitted profile reconciliation and would consume stale `road-worker.env`; pending Ubuntu execution was stopped before mutation and Issue #197 records the finding.
- Fourth corrective source integration: IN PROGRESS on `agent/ubuntu-road-config-transaction` under fresh exact 5-path source authorization.
- Fourth corrective production acceptance: PENDING new exact merged SHA and fresh production authorization; one Ubuntu fallback remains the only expected operator runtime action.
