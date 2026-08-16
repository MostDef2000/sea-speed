# Implementation Plan: Water and road analytics profiles

- Specification: specs/018-water-road-analytics-profiles/spec.md
- Issue: #197
- Status: Production remediation

## Architecture

1. **Profile normalization boundary.** `worker/analytics_profiles.py` owns detector defaults and model-class-to-domain mapping. Both the legacy in-process detector and supervised Ubuntu child normalize detections before they enter the existing tracking/speed/event pipeline.
2. **Process isolation.** The existing `sea-speed-worker.service` runs `water-v1`; `sea-speed-road-worker.service` runs `road-v1`. They share source bytes, immutable Python runtime and model store, but use separate process-local tracker state, working directories, outputs and heartbeats.
3. **Protected runtime binding.** A repository-owned configuration helper derives logical `road1` media from the sanitized private preview catalog. For worker-to-VPS API traffic it derives Road endpoints from the already-provisioned protected Camera 1 private M2M endpoint; public Authentik URLs are rejected for this machine path.
4. **Additive API generalization.** Supported analytics camera identities are `cam1` and `road1`. New generic routes use per-camera state/events/config paths; legacy Camera 1 routes delegate to the same helpers. SQLite remains additive and historical rows remain intact.
5. **Security-boundary separation.** Public `/sea-speed/**` remains Authentik-protected. A separate ZeroTier/RFC1918 private nginx listener remains allowlisted to the exact Ubuntu peer and now exposes only the explicit Camera 1 and logical `road1` worker paths/methods. Browser worker-control, generic analytics wildcard routes, Objects and preview APIs are excluded.
6. **Release provenance.** The corrective diff is exactly the newly authorized 10 paths. It affects VPS and Ubuntu Worker/relay only and changes no shared `worker/**`; Windows is not an applicable corrective contour. The original PR #198 42-path/Windows classification remains historical evidence rather than being rewritten.

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
- Decision: Keep the original #198 VPS + Ubuntu + Windows applicability as audit history, but classify the production-learning corrective diff from its own exact changed paths: VPS + Ubuntu only.
- Reason: Runtime applicability is derived per exact diff. The corrective source set contains `deploy/vps/**`, `deploy/worker/ubuntu/**`, `scripts/operations/**`, tests and SDD, and no `worker/**`.
- Alternatives rejected: Re-deploy an unused Windows target for source it does not consume; rewrite historical #198 evidence.

### D-007 - Derive Road M2M origin from protected Camera 1 config
- Decision: `configure-analytics-profiles.py` derives Road state/events URLs from the protected Camera 1 `SEA_SPEED_API_URL` only after validating private HTTP, literal non-loopback RFC1918 IPv4, explicit port, no credentials/query/fragment and exact `/api/cam1/state` path.
- Reason: The Camera 1 private endpoint is already a protected runtime input bound to the exact VPS M2M listener. Derivation avoids committing or inventing a second network origin and fails closed on the public Authentik URL that caused the production defect.
- Alternatives rejected: hardcode public `mostdef.ru`; add a second protected secret/config input solely for Road; disable Authentik for public API paths.

### D-008 - Extend private ingress by exact route matrix only
- Decision: Add exactly POST Road state/events and GET Road ROI/speed-config/speed-lines to the existing peer-restricted private listener. Keep the listener catch-all 404 and do not expose a generic `/api/analytics/` prefix.
- Reason: Road worker needs the same narrow machine operations as Camera 1 while the browser/operator API surface must remain authenticated and broader APIs must not become M2M-accessible accidentally.
- Alternatives rejected: wildcard analytics proxy; public Authentik bypass; browser-control exposure; a second VPS listener.

## Affected contours

- Repository: exact 10-path production-learning remediation authorized on Issue #197.
- VPS: REQUIRED after corrected source merge and separate production authorization because the exact private nginx M2M route matrix changes.
- Ubuntu Worker/relay: REQUIRED after corrected source merge and separate production authorization because protected `road-worker.env` must be regenerated from the corrected helper and Road service revalidated.
- Ubuntu private preview relay: media relay implementation/catalog topology unchanged; the already established sanitized `road1` relay remains in place.
- Windows Worker: NOT APPLICABLE to the corrective diff because no shared `worker/**` or Windows-specific source changes.
- Security: public Authentik remains unchanged; only the existing private exact-peer listener gains exact Road worker operations.

## Validation

- Unit: profile defaults and protected Road API-origin validation/fail-closed cases.
- Integration: Auth v1 renderer/verifier exact private path/method matrix, no generic analytics/control exposure, protected config writing, mode 0600, existing deploy-authorized protected-input contract.
- End-to-end source: exact 10-path compare, PR Validation, aggregate Quality integration, significant-SDD production-learning validation, fresh merge gate and post-merge push/main quality.
- Runtime-manual after separate production authorization: exact VPS nginx candidate/activation and public Auth regression; exact Ubuntu corrected source/config; Road Worker health and fresh `road1` state/source/frame progression; Road events/objects; clean preview start/media/stop; no main Water Worker start unless separately intended.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: logical road1 only in repository; protected catalog/env; repository secret/binary scanning; API never accepts arbitrary RTSP | Validation: source tests + runtime protected-config evidence | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: PERF | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: corrective source does not change inference workload; retain bounded 5 FPS and verify Road progression after transport repair | Validation: runtime-manual frame/AI progression and GPU observation | Residual risk: LOW if progression remains stable | Owner: Delivery Orchestrator | Status: OPEN
- RISK-003 | Category: DATA | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: corrective diff changes no API/storage schema and performs no migration; Road state/event files remain isolated | Validation: exact changed-file scope and API contract regression | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: keep worker detection/inference source untouched; repair only transport/config boundary | Validation: exact no-`worker/**` compare plus existing worker tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: VPS exact candidate SHA/backup/nginx validation; Ubuntu exact source and protected env; rollout VPS boundary before Road config restart; verify actual API freshness before acceptance | Validation: Auth cutover tests + runtime exact state progression | Residual risk: MEDIUM until production acceptance | Owner: Delivery Orchestrator | Status: OPEN
- RISK-006 | Category: BUS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: water taxonomy remains unchanged and outside this remediation | Validation: existing class rejection tests | Residual risk: MEDIUM because baseline taxonomy is intentionally narrow | Owner: Product owner | Status: ACCEPTED
- RISK-007 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: corrective diff contains no shared Windows worker source; keep historical #198 evidence separate and Issue #199 owns contour retirement | Validation: exact changed-file classification | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-008 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: fixed tuple of exact private paths and methods, peer allowlist plus deny-all, generic `/api/analytics/` and browser-control explicitly absent, public Auth unchanged | Validation: renderer/verifier behavioral and tamper tests | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-009 | Category: OPS | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: validate generated Road origin from protected Camera 1 private M2M config and require VPS-side fresh state/source/frame evidence; worker-side HTTP success alone is not acceptance | Validation: helper fail-closed tests + production VPS freshness gate | Residual risk: MEDIUM until runtime evidence | Owner: Delivery Orchestrator | Status: OPEN

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: unit | Priority: P1 | Evidence: `tests/test_analytics_profiles.py`
- TEST-002 | Covers: AC-003,RISK-004 | Level: integration | Priority: P1 | Evidence: unchanged worker contract and exact changed-file comparison
- TEST-003 | Covers: AC-004,AC-005,RISK-003 | Level: integration | Priority: P1 | Evidence: existing API contract suite
- TEST-004 | Covers: AC-006,AC-007 | Level: end-to-end | Priority: P2 | Evidence: existing frontend contract plus post-remediation browser smoke
- TEST-005 | Covers: AC-008,RISK-005 | Level: integration | Priority: P1 | Evidence: `tests/test_ubuntu_worker_deploy_authorized.py`
- TEST-006 | Covers: AC-009,RISK-001 | Level: integration | Priority: P2 | Evidence: existing model preparation/exact-artifact evidence
- TEST-007 | Covers: AC-010,RISK-005 | Level: integration | Priority: P1 | Evidence: existing VPS deploy transaction suite plus Auth cutover regression
- TEST-008 | Covers: AC-011,AC-012,RISK-007 | Level: integration | Priority: P0 | Evidence: GitHub exact compare, PR Validation, Quality integration and post-merge quality
- TEST-009 | Covers: AC-013 | Level: runtime-manual | Priority: P1 | Evidence: retained exact model/CUDA/protected road source evidence plus corrected VPS/Ubuntu runtime identity
- TEST-010 | Covers: AC-014,RISK-009 | Level: integration | Priority: P0 | Evidence: `tests/test_analytics_profiles.py` private-origin derivation and invalid-origin matrix
- TEST-011 | Covers: AC-015,RISK-008 | Level: integration | Priority: P0 | Evidence: `tests/test_sea_speed_auth_v1.py` exact route/method/peer and tamper rejection
- TEST-012 | Covers: AC-016,RISK-002,RISK-005,RISK-009 | Level: runtime-manual | Priority: P0 | Evidence: new exact-SHA VPS + Ubuntu deployment, Road state/source/frame progression, events/objects/preview and Auth/Camera1 regression evidence

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Issue #197 remains the canonical product outcome, but runtime evidence disproved the assumption that worker-local progress and HTTP success implied VPS Road state delivery; a separately authorized 10-path remediation is now required.
- Specification impact: Adds an explicit private M2M Road transport contract, exact ingress route matrix, fail-closed protected-origin derivation and corrective VPS+Ubuntu-only runtime applicability.
- Plan impact: Replaces the prior source-stage course check with the production-learning root cause, full adjacent-stage audit, fix-forward rollout and exact verification of API state commit.
- Tasks impact: Adds corrective source, tests, SDD, exact 10-path PR/CI/merge and new-production-authorization tasks without reopening detection/model/API schema implementation.
- Authorization impact: Material security-boundary/path scope expansion beyond the original 42 paths was presented in a fresh complete six-field Scope and immediately authorized by the operator with `OUTCOME APPROVED` on 2026-08-17; production remains separately unauthorized for the future corrected SHA.
- Follow-up: Complete the exact 10-path source remediation, merge only an exact green head, verify post-merge quality, compute the new authorization fingerprint, then obtain one fresh exact-SHA production authorization with execution intent before any VPS or Ubuntu mutation.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: current production remains on the previously authorized source and boundary | Retry: repair exact-main, quality, release-manifest or production-authorization evidence before runtime access | Rollback: NOT REQUIRED because no mutation occurred | Evidence: current-main first-parent, exact PR/Issue linkage, aggregate quality and production authorization verifier
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: existing public Auth, private M2M listener, Road relay/model/config remain unchanged | Retry: correct missing exact artifact or protected runtime input before candidate activation | Rollback: discard candidate only | Evidence: exact artifacts, nginx rendered candidate digest, protected worker env/catalog/model checks
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: VPS nginx may have the corrected exact-route candidate active and Ubuntu may have corrected exact source/config active only inside their separately authorized transactions | Retry: recover actual VPS and Ubuntu state before retrying | Rollback: restore captured nginx backup and previous Ubuntu exact release/config identity as contour-specific rollback targets | Evidence: VPS cutover/deploy logs and Ubuntu exact deployment transaction
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted if public Auth/Camera1 regresses or Road state remains stale | Retry: only after root-cause analysis of actual response/state path; do not infer success from worker heartbeat alone | Rollback: use captured per-contour previous exact identity when verification failure is caused by the candidate | Evidence: nginx config verifier, public Auth smoke, Road worker health, VPS `road1` exact source and advancing frame state, events/objects/preview
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: runtime acceptance remains unresolved if exact deployment manifests or API state cannot bind the corrected source | Retry: read actual runtime and API state first, then repeat only the incomplete evidence/state commit | Rollback: previous exact VPS/Ubuntu targets remain authoritative until corrected manifests and freshness are valid | Evidence: deployment manifests, active source identity, persisted `road1` state/event evidence
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified corrected runtime remains active unless cleanup touches an active release/config | Retry: independent cleanup after acceptance | Rollback: NOT REQUIRED solely for stale release cleanup | Evidence: deployment housekeeping logs and retained backup inventory
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: runtime may be healthy but Issue #197 cannot claim corrected acceptance without VPS freshness and product evidence | Retry: recollect read-only state/events/preview/Auth evidence without unnecessary mutation | Rollback: decide from actual runtime health rather than missing paperwork alone | Evidence: Issue #197 exact-SHA production, runtime and browser acceptance comments
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if rollback verification also fails, runtime truth is unknown and automated mutation stops | Retry: read-only recovery plus a separately authorized repair decision | Rollback: no recursive or guessed rollback beyond the captured known-good VPS/Ubuntu identities | Evidence: restored nginx/source/config identity, service state and public/private health verification

- Adjacent-stage review: COMPLETE
- Production-learning root cause: `configure-analytics-profiles.py` generated Road state/events URLs on the public Authentik-protected `/sea-speed/**` surface while the existing private Worker ingress exposed only Camera 1 endpoints; the Road HTTP client followed the authentication redirect and worker-local logging treated the final non-error response as POST success even though FastAPI never committed `road1` state.
- Production-learning adjacent-stage findings: admission and source CI lacked a cross-boundary contract test for generated Road M2M URLs; pre-mutation model, sanitized relay and protected config preservation were correct; mutation successfully started the Road service but left the private API route matrix incomplete; verification over-weighted worker heartbeat/AI progression until the independent VPS freshness check exposed `worker_online=false`, missing source commit and frame zero; state-commit therefore never occurred for Road; evidence collection correctly blocked acceptance; no destructive API/schema or public-Auth mutation occurred, so fix-forward source remediation with captured nginx/Ubuntu rollback targets is safer than an unrelated catalog/model rollback.

## Rollout and rollback

- Source rollout: fresh branch from exact `39cc330b61dc50aede4b809ee2dfc7a712b698d9` -> exact 10-path compare -> PR linked #197/spec 018 -> PR Validation + aggregate Quality integration on one exact head -> fresh main/head/scope/review verification -> expected-head merge -> post-merge push/main quality.
- Corrective production rollout: only after fresh exact merged-SHA production authorization; first activate/verify the VPS exact private M2M route matrix while preserving public Authentik and Camera 1 behavior; then deploy the exact Ubuntu corrective source, regenerate protected `road-worker.env` from the existing private Camera 1 M2M origin, restart/verify only the Road service as required by the authorized transaction, and prove VPS `road1` freshness/events/objects/preview. The main Water Worker remains stopped unless its separate operator-desired state requires otherwise.
- Corrective production rollback: VPS uses the root-only nginx backup captured before activation; Ubuntu uses the previously active exact release/config identity captured by the repository-owned transaction. Do not roll back the already-correct sanitized Road catalog or model solely because M2M state delivery fails. Windows has no corrective rollout or rollback action.

## Runtime feedback

- Original source integration: complete on `39cc330b61dc50aede4b809ee2dfc7a712b698d9`; historical #198 evidence remains immutable.
- Production learning: Road media/model/AI/frame progression succeeded but VPS Road state stayed empty, exposing the M2M/Auth boundary mismatch and false-positive worker-side POST evidence.
- Corrective source integration: IN PROGRESS on `agent/road-m2m-auth-boundary-remediation` under the fresh exact 10-path authorization.
- Corrective production acceptance: PENDING a new exact merged SHA and fresh production authorization for VPS + Ubuntu Worker/relay only.
- Windows corrective runtime: NOT APPLICABLE; Issue #199 remains the separate governance cleanup for retiring the unused Windows contour.
