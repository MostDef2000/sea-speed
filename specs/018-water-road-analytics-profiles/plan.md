# Implementation Plan: Water and road analytics profiles

- Specification: specs/018-water-road-analytics-profiles/spec.md
- Issue: #197
- Status: Production remediation

## Architecture

1. **Profile normalization boundary.** `worker/analytics_profiles.py` owns detector defaults and model-class-to-domain mapping. Both the legacy in-process detector and supervised Ubuntu child normalize detections before they enter the existing tracking/speed/event pipeline.
2. **Process isolation.** The existing `sea-speed-worker.service` runs `water-v1`; `sea-speed-road-worker.service` runs `road-v1`. They share source bytes, immutable Python runtime and model store, but use separate process-local tracker state, working directories, outputs and heartbeats.
3. **Protected runtime binding.** A repository-owned configuration helper derives logical `road1` media from the sanitized private preview catalog. For worker-to-VPS API traffic it derives Road endpoints from the already-provisioned protected Camera 1 private M2M endpoint; public Authentik URLs are rejected for this machine path.
4. **Additive API generalization.** Supported analytics camera identities are `cam1` and `road1`. New generic routes use per-camera state/events/config paths; legacy Camera 1 routes delegate to the same helpers. SQLite remains additive and historical rows remain intact.
5. **Security-boundary separation.** Public `/sea-speed/**` remains Authentik-protected. A separate ZeroTier/RFC1918 private nginx listener remains allowlisted to the exact Ubuntu peer and exposes only explicit Camera 1 and logical `road1` worker paths/methods. Browser worker-control, generic analytics wildcard routes, Objects and preview APIs are excluded.
6. **Release provenance by corrective diff.** Historical PR #198 remains VPS + Ubuntu + Windows audit truth. First production-learning PR #200 changed exactly 10 VPS+Ubuntu paths and no shared `worker/**`. The second production-learning remediation changes exactly 12 VPS/workflow/quality/test/SDD paths, changes no Ubuntu or shared worker source, and is therefore VPS-only with Ubuntu and Windows NOT APPLICABLE to this exact diff.
7. **Canonical VPS boundary transaction.** The protected VPS Connector workflow binds the current non-secret private topology, validates an exact VPS artifact containing the Auth cutover and both nginx renderers before SSH, and invokes one target transaction. `deploy/vps/deploy.sh` owns code release plus boundary reconciliation; `sea-speed-auth-cutover.sh` owns protected-baseline admission, candidate SHA binding, nginx activation, public/private verification and exact protected-backup rollback. A deployment manifest with `auth_v1_road_private_m2m=passed` is required before workflow success.

## Decisions

### D-001 - Normalize at detector boundary
- Decision: Map model classes to domain semantics before tracking/event logic.
- Reason: Keeps ByteTrack, speed and event mechanics reusable and makes future detector replacement bounded to profile mapping.
- Alternatives rejected: Duplicate water worker; teach every downstream stage about model-specific labels.

### D-002 - Two Ubuntu services, one immutable runtime
- Decision: Separate water/road OS processes but share exact source/runtime/model store.
- Reason: ByteTrack state must never cross cameras, while duplicating multi-gigabyte Python/CUDA runtimes is operationally wasteful.
- Alternatives rejected: One process multiplexing two trackers; fully duplicated virtualenv/model stores.

### D-003 - Logical road identity only in source
- Decision: Repository knows `road1`; protected runtime inventory owns the private camera source.
- Reason: Existing preview architecture already provides credential separation and a sanitized relay catalog.
- Alternatives rejected: Commit RTSP URL/IP; expose arbitrary RTSP input through API/browser.

### D-004 - Additive API plus compatibility wrappers
- Decision: Keep `/api/analytics/{camera_id}` and global `/api/objects` while retaining `/api/cam1/**`.
- Reason: Enables road without a flag-day frontend/worker migration and preserves existing integrations.
- Alternatives rejected: Rename/remove Camera 1 routes; duplicate a complete `/api/road1/**` API surface.

### D-005 - External model staging with exact digest
- Decision: Never package `yolo26x.pt`; require local file + digest and exact-runtime CUDA self-test.
- Reason: Model binaries are generated/runtime artifacts and production activation must not depend on mutable network downloads.
- Alternatives rejected: Commit model; allow Ultralytics implicit download; silently fall back to a smaller model.

### D-006 - Preserve historical shared-worker classification
- Decision: Keep the original #198 VPS + Ubuntu + Windows applicability as audit history and derive every later correction from its own exact changed paths.
- Reason: Runtime applicability is an exact-diff property; neither production-learning correction rewrites historical evidence.
- Alternatives rejected: Re-deploy an unused Windows target for source it does not consume; rewrite historical #198 evidence.

### D-007 - Derive Road M2M origin from protected Camera 1 config
- Decision: `configure-analytics-profiles.py` derives Road state/events URLs from the protected Camera 1 `SEA_SPEED_API_URL` only after validating private HTTP, literal non-loopback RFC1918 IPv4, explicit port, no credentials/query/fragment and exact `/api/cam1/state` path.
- Reason: The Camera 1 private endpoint is already a protected runtime input bound to the exact VPS M2M listener. Derivation avoids committing or inventing a second network origin and fails closed on the public Authentik URL that caused the first production defect.
- Alternatives rejected: hardcode public `mostdef.ru`; add a second protected secret/config input solely for Road; disable Authentik for public API paths.

### D-008 - Extend private ingress by exact route matrix only
- Decision: Add exactly POST Road state/events and GET Road ROI/speed-config/speed-lines to the existing peer-restricted private listener. Keep the listener catch-all 404 and do not expose a generic `/api/analytics/` prefix.
- Reason: Road worker needs the same narrow machine operations as Camera 1 while browser/operator APIs must remain authenticated and broader APIs must not become M2M-accessible accidentally.
- Alternatives rejected: wildcard analytics proxy; public Authentik bypass; browser-control exposure; a second VPS listener.

### D-009 - Make private-boundary acceptance part of the canonical VPS transaction
- Decision: `.github/workflows/deploy-vps.yml` requires boundary reconciliation and accepts deployment only when the target deployment manifest contains passed `auth_v1_road_private_m2m` evidence.
- Reason: The first corrective production run demonstrated that API/frontend source identity alone is not evidence that source-managed nginx security routes were activated.
- Alternatives rejected: manual post-deploy VPS command; a second workflow; treating Auth cutover as optional evidence after workflow success.

### D-010 - Roll back only to an already-protected nginx baseline
- Decision: Canonical reconciliation supplies `--require-protected-baseline`. Before candidate mutation the cutover proves the live site already has Authentik, exact private listen/peer and legacy Camera 1 M2M protection. Post-mutation failure restores the captured root-only backup, reloads nginx and re-verifies that protected baseline. Legacy/manual cutover mode retains explicit non-automatic rollback semantics.
- Reason: Rollback must not reintroduce retired public `/cams/**` or an unknown pre-Auth configuration. The production starting point is already protected, so an exact verified backup is a bounded safe rollback target.
- Alternatives rejected: unconditional restore to arbitrary historical config; no rollback after candidate install; reconstruct rollback from generated source rather than captured runtime truth.

## Affected contours

- Repository: second correction is exactly the separately authorized 12-path VPS deployment-automation remediation on Issue #197.
- VPS: REQUIRED after the second corrective source merge and separate production authorization because the protected Connector transaction and nginx boundary activation/evidence semantics change.
- Ubuntu Worker/relay: NOT APPLICABLE to the second 12-path source diff. The pending first-correction Ubuntu runtime action remains paused until VPS private-boundary evidence is green.
- Ubuntu private preview relay: unchanged; existing sanitized `road1` relay remains in place.
- Windows Worker: NOT APPLICABLE; no shared `worker/**` or Windows-specific source changes.
- Security: public Authentik and the exact private route matrix remain the intended boundary; the change closes deployment automation/evidence, not the route scope itself.

## Validation

- Unit/integration: existing profile, protected-origin and exact nginx route/method/peer tests remain green.
- Deployment transaction: `tests/test_vps_deploy_transaction.py` executes the real `deploy/vps/deploy.sh` with isolated runtime boundaries and proves success evidence, API failure rollback, Auth-boundary failure after self-rollback, and already-current-source fail-closed behavior.
- Auth transaction contract: `tests/test_sea_speed_auth_v1.py` verifies protected-baseline and protected-backup rollback mechanics coexist with exact route/public-security invariants.
- Exact artifact: deterministic VPS artifact contains `sea-speed-auth-cutover.sh` plus both nginx renderers, validates Python/shell syntax and is quality-bound before SSH.
- Workflow policy: canonical VPS workflow fixes the approved non-secret private topology, builds/validates exact artifacts before SSH, invokes boundary reconciliation and rejects deployment evidence without the passed boundary check.
- End-to-end source: exact 12-path compare, PR Validation, aggregate Quality integration, significant-SDD production-learning validation, fresh merge gate and post-merge push/main quality.
- Runtime after separate authorization: exact VPS source identity, Auth v1 private Road matrix, public Auth/Camera1/H264 regressions and deployment-manifest boundary check must be green before any pending Ubuntu correction is resumed.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: logical road1 only in repository; protected catalog/env; repository secret/binary scanning; API never accepts arbitrary RTSP | Validation: source tests + runtime protected-config evidence | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: PERF | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: corrections do not change inference workload; retain bounded 5 FPS and verify Road progression after transport repair | Validation: runtime-manual frame/AI progression and GPU observation | Residual risk: LOW if progression remains stable | Owner: Delivery Orchestrator | Status: OPEN
- RISK-003 | Category: DATA | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: corrective diffs change no API/storage schema and perform no migration; Road state/event files remain isolated | Validation: exact changed-file scope and API contract regression | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: keep worker detection/inference source untouched; repair only transport/deployment boundaries | Validation: exact no-`worker/**` compare plus existing worker tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: exact candidate SHA, protected-baseline gate, root-only backup, bounded rollback, nginx/public checks and deployment-manifest acceptance are one canonical VPS transaction | Validation: Auth cutover and VPS deploy transaction tests plus production artifact | Residual risk: MEDIUM until production acceptance | Owner: Delivery Orchestrator | Status: OPEN
- RISK-006 | Category: BUS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: water taxonomy remains unchanged and outside remediation | Validation: existing class rejection tests | Residual risk: MEDIUM because baseline taxonomy is intentionally narrow | Owner: Product owner | Status: ACCEPTED
- RISK-007 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: second corrective diff contains no Ubuntu/shared/Windows worker source; keep historical evidence separate and Issue #199 owns contour retirement | Validation: exact changed-file classification | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-008 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: fixed exact private paths/methods, peer allowlist plus deny-all, generic `/api/analytics/` and browser-control absent, public Auth unchanged | Validation: renderer/verifier behavioral and tamper tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-009 | Category: OPS | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: worker-side HTTP success is never product acceptance; require VPS-side state/source/frame evidence after both VPS and Ubuntu corrections are active | Validation: production VPS freshness gate | Residual risk: MEDIUM until runtime evidence | Owner: Delivery Orchestrator | Status: OPEN
- RISK-010 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: canonical VPS workflow cannot finish with only API/frontend deployment; it requires `auth_v1_road_private_m2m=passed` from the target deployment manifest | Validation: workflow-policy and deployment-transaction tests | Residual risk: LOW after source CI, MEDIUM until first production execution | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-011 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: automatic rollback is admitted only after the pre-mutation live boundary is independently verified as already protected; rollback re-validates Authentik/private peer/H264/public behavior | Validation: cutover contract plus fault-path transaction tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: unit | Priority: P1 | Evidence: `tests/test_analytics_profiles.py`
- TEST-002 | Covers: AC-003,RISK-004 | Level: integration | Priority: P1 | Evidence: unchanged worker contract and exact changed-file comparison
- TEST-003 | Covers: AC-004,AC-005,RISK-003 | Level: integration | Priority: P1 | Evidence: existing API contract suite
- TEST-004 | Covers: AC-006,AC-007 | Level: end-to-end | Priority: P2 | Evidence: existing frontend contract plus post-remediation browser smoke
- TEST-005 | Covers: AC-008,RISK-005 | Level: integration | Priority: P1 | Evidence: `tests/test_ubuntu_worker_deploy_authorized.py`
- TEST-006 | Covers: AC-009,RISK-001 | Level: integration | Priority: P2 | Evidence: model preparation/exact-artifact evidence
- TEST-007 | Covers: AC-010,RISK-005 | Level: integration | Priority: P1 | Evidence: `tests/test_vps_deploy_transaction.py`
- TEST-008 | Covers: AC-011,AC-012,RISK-007 | Level: integration | Priority: P0 | Evidence: GitHub exact compare, PR Validation, Quality integration and post-merge quality
- TEST-009 | Covers: AC-013 | Level: runtime-manual | Priority: P1 | Evidence: retained exact model/CUDA/protected road source evidence plus corrected runtime identity
- TEST-010 | Covers: AC-014,RISK-009 | Level: integration | Priority: P0 | Evidence: `tests/test_analytics_profiles.py` private-origin derivation and invalid-origin matrix
- TEST-011 | Covers: AC-015,RISK-008 | Level: integration | Priority: P0 | Evidence: `tests/test_sea_speed_auth_v1.py` exact route/method/peer and tamper rejection
- TEST-012 | Covers: AC-016,RISK-002,RISK-005,RISK-009 | Level: runtime-manual | Priority: P0 | Evidence: exact authorized VPS boundary then pending Ubuntu correction, followed by Road state/source/frame/events/objects/preview and Auth/Camera1 regression evidence
- TEST-013 | Covers: AC-017,RISK-010 | Level: integration | Priority: P0 | Evidence: `tests/quality/test_quality_architecture.py` plus exact-artifact build/validator
- TEST-014 | Covers: AC-018,RISK-005,RISK-010,RISK-011 | Level: end-to-end | Priority: P0 | Evidence: real `deploy/vps/deploy.sh` under isolated fake runtime boundaries in `tests/test_vps_deploy_transaction.py`
- TEST-015 | Covers: AC-019,RISK-008,RISK-011 | Level: integration | Priority: P0 | Evidence: `tests/test_sea_speed_auth_v1.py` protected baseline, rollback and route/public-security markers
- TEST-016 | Covers: AC-020,RISK-007,RISK-010 | Level: end-to-end | Priority: P0 | Evidence: exact 12-path compare, PR/Quality exact head, expected-head merge and post-merge push/main quality

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #197 remains canonical. The first remediation fixed Road M2M source routing, but the authorized production attempt showed that the canonical VPS deployment workflow did not execute the source-managed nginx boundary transaction, so VPS success was insufficient evidence and Ubuntu execution was correctly paused.
- Specification impact: Adds explicit requirements that canonical VPS deployment own exact Auth v1 boundary reconciliation, exact-artifact inclusion, protected-baseline rollback and deployment-manifest boundary evidence.
- Plan impact: Replaces the prior assumption that `sea-speed-auth-cutover.sh` would be executed as a separate deterministic step with one protected Connector-owned VPS transaction and fault-path rollback tests.
- Tasks impact: Adds a separately authorized exact 12-path VPS-only source remediation, PR/CI/merge lifecycle and a new exact-SHA VPS production authorization before the pending Ubuntu correction can resume.
- Authorization impact: The second defect requires workflow/deploy/artifact/test paths outside the first 10-path authorization. A complete revised six-field 12-path Scope was shown immediately before the operator supplied fresh `OUTCOME APPROVED` on 2026-08-17. This source authorization does not authorize production.
- Follow-up: Complete the exact 12-path branch, merge only one exact green head, verify post-merge push/main quality, compute a fresh production authorization fingerprint, obtain fresh exact-SHA VPS production authority plus execution intent, run the protected VPS transaction, and resume the pending Ubuntu correction only after VPS boundary evidence is green.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on the current VPS source and existing protected nginx boundary; Ubuntu correction remains paused | Retry: repair exact-main/quality/release/authorization evidence before SSH | Rollback: NOT REQUIRED because no mutation occurred | Evidence: first-parent main, exact applicable PR/Issue, aggregate push/main quality, release manifest and production authorization verifier
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: live API/frontend/nginx remain unchanged | Retry: correct exact VPS artifact or protected-baseline/topology mismatch, then rerun the authorized transaction | Rollback: discard staged source/candidate only | Evidence: exact artifact contains cutover/renderers; `--require-protected-baseline`; Authentik/H264/public checks; candidate SHA256
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: target API/frontend may be candidate source and nginx may briefly be candidate boundary only inside the guarded transaction | Retry: only after actual rollback/manifest state is known | Rollback: Auth cutover restores captured verified protected nginx backup on post-mutation boundary failure; deploy transaction restores previous source/frontends if candidate source or boundary acceptance fails | Evidence: cutover backup/rollback markers and deploy transaction log
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted when nginx syntax/reload/service, exact renderer verification, Authentik, H264 or public Auth/Camera1 checks fail | Retry: inspect failing exact check after rollback; do not bypass or manually mark success | Rollback: protected nginx backup plus previous source release as applicable | Evidence: `SEA_SPEED_AUTH_CUTOVER=PASS`, exact private Road base, public status checks, rollback capability evidence
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: VPS workflow must not report runtime verification if `auth_v1_road_private_m2m` is absent/failed; current/previous release markers remain authoritative for source state | Retry: read deployment manifest and live boundary first, then repeat whole protected transaction only if authorized and safe | Rollback: previous source release and verified protected nginx backup remain known targets | Evidence: deployment manifest `runtime_verified=true`, state `runtime_verified`, `auth_v1_road_private_m2m=passed`
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified source/boundary remains active; stale release cleanup failure is warning-only | Retry: independent cleanup later | Rollback: NOT REQUIRED solely for stale release cleanup | Evidence: prune warning/success logs; retained protected nginx backups
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: runtime may be healthy but Issue #197 cannot advance to Ubuntu/product acceptance without exact VPS deployment artifact and boundary check | Retry: recollect/read deployment artifact and read-only live state; do not mutate merely to recreate paperwork | Rollback: decide from actual runtime health, not missing evidence alone | Evidence: GitHub deployment artifact, validated deployment manifest, Issue #197 exact-SHA runtime comment
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if protected nginx rollback verification or source rollback health also fails, runtime truth is unknown and automation stops | Retry: read-only recovery plus new human/production decision; no recursive guessed rollback | Rollback: only captured verified protected nginx backup and previous exact source release | Evidence: `SEA_SPEED_AUTH_ROLLBACK=PASS`, restored protected-baseline checks, previous source/API/frontend health and manifest state

- Adjacent-stage review: COMPLETE
- Production-learning root cause: the first corrective implementation added the correct Road private nginx route matrix and the correct Ubuntu private-origin derivation, but `.github/workflows/deploy-vps.yml` still invoked only `deploy/vps/deploy.sh`. That deploy script did not stage or execute `sea-speed-auth-cutover.sh`, so the protected Connector could complete API/frontend deployment while never mutating/verifying the source-managed M2M security boundary.
- Production-learning adjacent-stage findings: admission and first corrective source CI validated the renderer and helper independently but did not assert that the protected VPS workflow connected them; pre-mutation release artifacts omitted the Auth cutover/renderers; mutation updated API/frontend successfully and therefore looked healthy; verification checked API/public frontend smoke but had no mandatory private-boundary evidence; state-commit wrote a runtime-verified VPS manifest without a Road M2M boundary check; evidence collection faithfully reflected that incomplete manifest and subsequent VPS Road-state probing exposed the gap; rollback logic existed separately for source and nginx but the canonical transaction did not compose them. The second correction therefore binds exact artifacts, workflow invocation, protected-baseline rollback and manifest acceptance together rather than adding another manual command.

## Rollout and rollback

- Second corrective source rollout: fresh branch from exact `30e77e1f42397fddabc2a36fcfe922416a8efe57` -> exact 12-path compare -> PR linked #197/spec 018 -> PR Validation + aggregate Quality integration on one exact head -> fresh main/head/scope/review verification -> expected-head merge -> post-merge push/main quality.
- Second corrective production rollout: only after fresh exact merged-SHA VPS production authorization. Protected workflow builds/validates exact artifact, connects to VPS, deploys exact source, proves existing protected baseline, prepares SHA-bound nginx candidate, activates/verifies exact Road route matrix and public/Auth/Camera1/H264 behavior, and accepts only a deployment manifest with passed boundary evidence.
- Second corrective production rollback: post-mutation Auth failure restores and verifies the captured already-protected nginx backup; candidate source failure/boundary rejection restores previous source/frontends. Do not roll back sanitized Road catalog/model or weaken Authentik. If rollback verification fails, automated mutation stops.
- Pending first-correction Ubuntu rollout: remains paused until the second corrective VPS production transaction is accepted. The main Water Worker remains stopped unless its separate operator-desired state requires otherwise. Windows has no corrective action.

## Runtime feedback

- Original source integration: complete on `39cc330b61dc50aede4b809ee2dfc7a712b698d9`; historical #198 evidence remains immutable.
- First production learning: Road media/model/AI/frame progression succeeded but VPS Road state stayed empty, exposing the public-vs-private M2M mismatch and false-positive worker-side POST evidence.
- First corrective source integration: PR #200 merged as `30e77e1f42397fddabc2a36fcfe922416a8efe57`; helper and renderer source corrections are on main with green post-merge quality.
- Second production learning: the authorized `30e77...` VPS source deployment succeeded, but canonical VPS automation never invoked the Auth cutover; private Road route activation therefore remained unproven and Ubuntu correction was not executed.
- Second corrective source integration: IN PROGRESS on `agent/vps-road-m2m-deployment-automation` under the fresh exact 12-path source authorization.
- Second corrective production acceptance: PENDING a new exact merged SHA and fresh VPS production authorization. Ubuntu/Windows are NOT APPLICABLE to this exact second corrective diff.
- Pending Ubuntu first-correction runtime acceptance: PENDING and intentionally blocked behind successful VPS boundary evidence, not behind a new Ubuntu source change.
