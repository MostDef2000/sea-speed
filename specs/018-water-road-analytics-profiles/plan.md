# Implementation Plan: Water and road analytics profiles

- Specification: specs/018-water-road-analytics-profiles/spec.md
- Issue: #197
- Status: Production remediation

## Architecture

1. **Profile normalization boundary.** `worker/analytics_profiles.py` remains the common water/road semantic normalization boundary; detection, tracking, ROI, speed and event-trigger behavior are unchanged by the fifth correction.
2. **Process isolation.** `sea-speed-worker.service` and `sea-speed-road-worker.service` remain separate Ubuntu processes sharing immutable source/runtime/model storage but not tracker/output/heartbeat state.
3. **Protected Road binding.** `road1` media remains resolved from the protected preview catalog and Road API endpoints remain derived from the protected Camera 1 private M2M origin.
4. **Public/private separation.** Public `/sea-speed/**` remains Authentik-protected. The private VPS listener remains exact-peer, exact-path, exact-method and deny-by-default.
5. **Accepted VPS boundary.** The accepted VPS release `e7dd921d569d9b93d9ac1be9113f61a162102b19` already proves the fixed least-privilege helper and `auth_v1_road_private_m2m=passed`; the fifth correction does not redeploy VPS.
6. **Canonical Ubuntu transaction.** `.github/workflows/deploy-ubuntu-worker.yml` remains admission/transport orchestration and `deploy/worker/ubuntu/deploy-authorized.sh` remains target-side protected-config reconciliation, exact activation, verification, deployment evidence and rollback owner.
7. **Accepted fourth correction.** PR #203 merged as `116dcf0f5f0d625f2b223a4549525ca7ddaa56d3`; its Ubuntu production transaction reconciled protected Road config before activation, advanced Road frames/state/AI and preserved Water desired-stopped state.
8. **Runtime source provenance boundary.** Ubuntu systemd already binds `SEA_SPEED_SOURCE_COMMIT=__SOURCE_COMMIT__`. The fifth correction makes `worker/ubuntu_worker_entrypoint.py` the Ubuntu-only adapter that validates this exact lowercase 40-SHA before runtime admission and injects it into state/event metadata before shared POST handling.
9. **Payload authority.** The systemd/environment source identity is authoritative. Caller metadata is copied and any existing `worker_source_commit` is replaced; protected token/media/config environment values are never copied into metadata.
10. **Shared-runtime stability.** `worker/hls_motion_yolo_worker_events.py`, API/storage schema, deployment scripts, service templates, VPS/Auth topology and analytics formulas are unchanged by this correction.

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

### D-006 - Historical contour truth remains immutable
- Decision: Keep PR #198's historical Windows applicability as audit truth while current corrective work follows the post-#199 two-contour governance.
- Reason: Governance changes are prospective and must not rewrite historical Change Contracts or production evidence.
- Alternatives rejected: editing old Issue/PR evidence or reactivating Windows for new work.

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

### D-010 - Fixed no-argument root helper
- Decision: Keep the accepted root-owned no-argument helper rather than root SSH or broad passwordless sudo.
- Reason: The accepted `e7dd921...` production run proves the least-privilege boundary works.
- Alternatives rejected: root SSH credential; `NOPASSWD: ALL`; arbitrary shell/interpreter privilege.

### D-011 - Protected profile reconciliation belongs to deploy-authorized
- Decision: Keep exact `configure-analytics-profiles.py` reconciliation inside `deploy-authorized.sh` before activation.
- Reason: Fourth production learning proved the target transaction must own protected configuration and rollback together.
- Alternatives rejected: separate operator configure command; workflow-side configuration; trusting stale env.

### D-012 - Restore config before previous runtime
- Decision: Keep fourth-correction rollback ordering that restores protected config before restoring/restarting a previous Road runtime.
- Reason: Previous source must restart against its matching protected configuration.
- Alternatives rejected: source rollback first or file-only restoration after service restart.

### D-013 - Preserve Water desired state
- Decision: A desired-stopped Water Worker remains stopped through Road correction rollout and rollback.
- Reason: Road remediation must not override operator control of the main Water contour.
- Alternatives rejected: unconditional service start during deployment.

### D-014 - Ubuntu entrypoint owns runtime source provenance
- Decision: Validate `SEA_SPEED_SOURCE_COMMIT` in the Ubuntu entrypoint, then wrap only shared `post_state` and `post_event` with copied metadata containing the authoritative source SHA.
- Reason: The source identity is already bound by Ubuntu systemd; the defect is the missing adapter between runtime identity and API metadata. This is the narrowest correction and avoids changing shared worker HTTP behavior or API/schema.
- Alternatives rejected: changing shared worker source; deriving SHA from Git/runtime filesystem; trusting payload-supplied identity; adding API inference of source identity.

## Affected contours

- Repository: fifth correction is exactly 5 authorized paths on Issue #197: `worker/ubuntu_worker_entrypoint.py`, new `tests/test_ubuntu_worker_runtime_provenance.py`, and feature 018 spec/plan/tasks.
- VPS: NOT REQUIRED / NOT APPLICABLE for this exact diff. Accepted `e7dd921d569d9b93d9ac1be9113f61a162102b19` private-M2M boundary remains prerequisite evidence and is not redeployed.
- Ubuntu Worker/relay: REQUIRED after exact-green merge and fresh exact-SHA production authorization.
- Ubuntu execution capability: `ONE_COMMAND_FALLBACK`; one repository-owned server-pull/bootstrap action stages exact main and hands off to existing `deploy-authorized.sh`.
- Active runtime topology: VPS + Ubuntu Worker/relay only. Issue #199 retired Windows; no new Change Contract field, release action or acceptance gate exists for Windows.
- Security/protected inputs: credentials, RTSP source, API token, model, private topology and protected env files are unchanged. Provenance injection reads only the non-secret exact source SHA.

## Validation

- `tests/test_ubuntu_worker_runtime_provenance.py`: exact SHA injection into state and event metadata; payload override prevention; missing/uppercase/non-hex/wrong-length fail-closed behavior; original POST boundary is not called on invalid identity; protected token/media/private API values are not copied into metadata; startup validates provenance before `BoundedYoloSupervisor`.
- Existing `tests/test_ubuntu_worker_ai_supervision.py`: Ubuntu entrypoint syntax, bounded AI supervisor and profile behavior remain present.
- Existing worker/profile/API/Ubuntu deployment suites remain regression evidence because shared worker, API/schema and deployment source are unchanged.
- Exact source: compare against authorization base `3544e0a4b6ef4afd4dddf4e0139f8218caeeeffb` must equal 5/5 authorized paths; PR Validation and aggregate Quality integration must succeed on the same exact final head; fresh main/head/scope/review gate and expected-head merge precede post-merge push/main quality.
- Runtime after separate production authorization: one Ubuntu fallback -> exact deployment manifest/runtime/service identity -> Road frame/state/AI progression -> VPS `road1` state with `worker_source_commit=<new exact SHA>` and advancing frame -> new Road event provenance -> Objects isolation -> clean preview start/HLS/media/stop -> Water desired-state and public Authentik/Camera1 regressions.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: provenance wrapper reads only `SEA_SPEED_SOURCE_COMMIT`; protected token/media/config values are not copied or logged | Validation: focused secret-negative test plus repository secret checks | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: shared worker/API/schema remain unchanged; wrapper delegates to captured original POST functions | Validation: focused behavioral test plus existing worker/API suites | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: invalid/missing source identity fails closed before supervisor/main runtime admission and before original POST calls | Validation: invalid-value matrix and startup-order assertion | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: authoritative environment identity overwrites caller metadata so stale/spoofed provenance cannot be persisted | Validation: state/event override tests and final VPS runtime acceptance | Residual risk: MEDIUM until production acceptance | Owner: Delivery Orchestrator | Status: OPEN
- RISK-005 | Category: PERF | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: one dict copy and one regex-validated cached-environment read per POST do not alter inference/media path | Validation: source inspection and advancing runtime frame/AI evidence | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-006 | Category: OPS | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: final acceptance is VPS-observed and source-bound; worker-local health alone cannot satisfy outcome | Validation: exact state/event source plus frame progression and preview acceptance | Residual risk: MEDIUM until runtime evidence | Owner: Delivery Orchestrator | Status: OPEN

## Test design

- TEST-001 | Covers: AC-001,AC-002,AC-003 | Level: unit | Priority: P1 | Evidence: existing profile/worker suites
- TEST-002 | Covers: AC-004,AC-005,AC-006,AC-007 | Level: integration | Priority: P1 | Evidence: existing API/frontend contract suites
- TEST-003 | Covers: AC-008,AC-009,AC-025,AC-026 | Level: integration | Priority: P1 | Evidence: existing Ubuntu systemd/model/deploy-authorized tests
- TEST-004 | Covers: AC-014,AC-015,AC-017,AC-018,AC-019,AC-021,AC-022,AC-023,AC-024 | Level: integration | Priority: P1 | Evidence: accepted private-M2M/VPS privilege/artifact/deploy transaction tests and production evidence
- TEST-005 | Covers: AC-011,AC-012,AC-020,AC-028 | Level: end-to-end | Priority: P0 | Evidence: exact GitHub diff/Change Contract/PR Validation/Quality/merge/post-merge evidence
- TEST-006 | Covers: AC-027,RISK-001,RISK-002,RISK-003,RISK-004 | Level: unit | Priority: P0 | Evidence: `tests/test_ubuntu_worker_runtime_provenance.py`
- TEST-007 | Covers: AC-013,AC-016,AC-029,RISK-006 | Level: runtime-manual | Priority: P0 | Evidence: exact Ubuntu deployment manifest plus VPS-observed source/frame/events/objects/preview and Water/public-auth regression evidence

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #197 remains canonical. Final VPS product acceptance after the successful fourth-correction Ubuntu rollout failed at `ERROR=ROAD_STATE_SOURCE_1`; runtime remained healthy, so rollback was not indicated and a source provenance correction is required.
- Specification impact: Adds FR-034/FR-035 and AC-027..029 requiring authoritative Ubuntu runtime source identity in state/event metadata and exact-source final acceptance under the current two-contour governance.
- Plan impact: Adds D-014, focused provenance risks/tests, and updates the deployment/evidence audit so exact source identity is verified end-to-end rather than inferred from local release/service state.
- Tasks impact: Adds fifth-correction implementation, focused tests, exact 5-path source lifecycle, new production authorization and final VPS-side provenance/product acceptance tasks.
- Authorization impact: A fresh complete six-field exact 5-path Scope based on current main `3544e0a4b6ef4afd4dddf4e0139f8218caeeeffb` immediately preceded `OUTCOME APPROVED`; admission is recorded in Issue #197 comment `5312856773`. Source authorization does not authorize Ubuntu mutation.
- Follow-up: Complete exact 5-path source integration, obtain a fresh production authorization for the new merged SHA, execute one Ubuntu fallback and continue through final VPS-observed state/event provenance, frame/events/objects/preview and regression acceptance.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: current accepted VPS boundary and Ubuntu runtime remain unchanged | Retry: repair exact-main ancestry, push/main quality, merged PR, release evidence or production authorization before target execution | Rollback: NOT REQUIRED | Evidence: exact first-parent main, Issue #197/merged corrective PR, aggregate quality, exact artifact/release evidence and authorization verifier
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: no service/source/config mutation; only temporary bootstrap staging may exist | Retry: correct missing exact source/artifact/authorization/protected prerequisites and rerun the same exact authorized transaction | Rollback: NOT REQUIRED | Evidence: workflow admission plus target `deploy-authorized.sh` authorization/config preflight markers
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: exact Ubuntu updater may have attempted source/unit activation while protected config rollback semantics remain owned by accepted fourth-correction transaction | Retry: only after updater/deploy-authorized rollback establishes exact active source/config/service truth | Rollback: previous exact Ubuntu source/runtime/units plus backed-up protected config and captured service state | Evidence: deployment transaction markers, active source marker and systemd identity
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: target may be active but is not accepted unless exact source/runtime/services and runtime progression pass; provenance-specific VPS evidence is still separate | Retry: source/runtime verification may be recollected read-only; failed runtime identity/health follows existing rollback path | Rollback: existing deploy-authorized/updater rollback for activation/runtime verification failures | Evidence: exact deployment manifest checks, Road service active, frame/state/AI progression, Water desired state
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment manifest must not claim `runtime_verified` unless target transaction checks passed | Retry: re-read active source/runtime/config/services and rerun only under current authorization if state commit is not trustworthy | Rollback: previous exact source/config remains available according to accepted updater transaction | Evidence: `deployment-manifest-ubuntu-worker.json` exact source/runtime/rollback/checks
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: accepted runtime remains active; temporary stage/old release cleanup may remain | Retry: independent cleanup after read-only runtime verification | Rollback: NOT REQUIRED solely for housekeeping | Evidence: target cleanup/updater retention markers
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: runtime may be healthy but Issue #197 remains incomplete if VPS state/event provenance, advancing frame, objects, preview or regressions are missing | Retry: recollect read-only VPS/Ubuntu evidence; do not mutate merely to recreate evidence | Rollback: decide from runtime truth, not absent evidence alone | Evidence: VPS `road1` state `worker_source_commit=<new SHA>`, source-bound recent events, frame progression, objects, preview media, Water/public Auth checks
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if existing protected config/source/service rollback cannot establish exact runtime truth, automatic retry stops | Retry: read-only recovery plus a new protected human/production decision after exact state is established | Rollback: only backed-up protected env, previous exact source/runtime/units and captured predeployment service states | Evidence: deploy-authorized/updater rollback markers, active source marker and service active/inactive checks

- Adjacent-stage review: COMPLETE
- Production-learning root cause: Ubuntu systemd correctly provided the exact release SHA through `SEA_SPEED_SOURCE_COMMIT`, and the fourth-correction deployment correctly activated/progressed the exact Road runtime, but `worker/ubuntu_worker_entrypoint.py` only adapted media and AI behavior. It never adapted shared `post_state`/`post_event`, while the shared worker serialized only metadata supplied by its analytics loop. Consequently the VPS stored fresh Road state without `worker_source_commit`, producing `null` at the final exact-source acceptance gate.
- Production-learning adjacent-stage findings: ADMISSION and PRE-MUTATION correctly bound the exact source/artifact/authorization; MUTATION and target VERIFICATION correctly proved exact release/service/frame/AI progression but did not prove the source SHA entered application metadata; STATE-COMMIT correctly recorded deployment identity but deployment identity is not API payload provenance; HOUSEKEEPING was unrelated; EVIDENCE was the first stage to compare VPS state provenance and exposed the omission; ROLLBACK was not indicated because runtime health and M2M writes were good and reverting would not create missing provenance. The fifth correction closes the interface gap at the Ubuntu adapter and adds focused fail-closed/source-spoof tests plus mandatory VPS-observed state/event source evidence.

## Rollout and rollback

- Fifth corrective source rollout: branch `agent/ubuntu-runtime-source-provenance` from `3544e0a4b6ef4afd4dddf4e0139f8218caeeeffb` -> exact 5-path compare -> PR linked to Issue #197/spec 018 -> PR Validation + aggregate Quality on one exact head -> fresh main/head/scope/review verification -> expected-head merge -> post-merge push/main quality.
- Fifth corrective production rollout: after a fresh exact-SHA production authorization/fingerprint/execution intent, one Ubuntu server-pull fallback stages the exact merged SHA and invokes the unchanged accepted `deploy-authorized.sh`; VPS is not redeployed.
- Production rollback: use existing Ubuntu deployment transaction rollback if activation/runtime verification fails. Do not rollback solely because product evidence is temporarily unavailable; first resolve actual runtime state read-only.
- Final product acceptance: require VPS-observed exact new source in Road state, advancing frame, source-bound Road events, isolated Road objects, clean preview start/HLS/media/stop, unchanged Water desired-stopped state and unchanged public Authentik protection.

## Runtime feedback

- Original PR #198 merged as `39cc330b61dc50aede4b809ee2dfc7a712b698d9`; historical delivery evidence remains immutable.
- First correction PR #200 merged as `30e77e1f42397fddabc2a36fcfe922416a8efe57` after the public-vs-private Road M2M defect.
- Second correction PR #201 merged as `f21b31d38e95179445e68e5543a1c934a744d514` after the VPS workflow omitted nginx boundary activation.
- Third correction PR #202 merged as `e7dd921d569d9b93d9ac1be9113f61a162102b19`; root bootstrap and canonical Connector deployment passed the fixed helper and private-M2M boundary.
- Fourth correction PR #203 merged as `116dcf0f5f0d625f2b223a4549525ca7ddaa56d3`; the authorized Ubuntu transaction passed protected config reconciliation, exact source/runtime activation, Road frame/state/AI progression and preserved Water desired-stopped state.
- Fifth production learning: final VPS acceptance of `116dcf...` failed at `ROAD_STATE_SOURCE_1`; source inspection proved the Ubuntu entrypoint omitted systemd-bound source provenance from shared state/event metadata. Runtime rollback was not indicated.
- Issue #199 / PR #204 retired Windows from active production governance; current main before this correction is `3544e0a4b6ef4afd4dddf4e0139f8218caeeeffb` with exactly VPS + Ubuntu Worker/relay active contours.
- Fifth corrective source integration: IN PROGRESS on the exact authorized 5-path branch; production remains pending a future merged SHA and fresh authorization.
