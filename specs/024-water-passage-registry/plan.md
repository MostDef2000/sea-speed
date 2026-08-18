# Implementation Plan: Water Passage Architecture

- Specification: specs/024-water-passage-registry/spec.md
- Issue: #218
- Status: Correct-course remediation

## Architecture

Introduce pure-Python `worker/water_passage.py` as the bounded passage domain layer. `WaterPassageEngine` maps current ByteTrack fragments to active passages, keeps only fixed-size observation deques, chooses materially improving snapshot candidates, and delegates speed calculation to a `SpeedEstimator` instance owned by each passage.

`TwoGateSpeedEstimator` is the first strategy. It receives timestamped anchor observations, detects finite-segment crossings of Gate A and Gate B in either order, and returns a measurement result. The Worker integration posts passage metadata through a new idempotent `/api/cam1/passages` boundary. Existing Water YOLO admission remains continuous and ROI-bounded; Road retains its legacy event path. Existing `water_event_candidates` remains as a compatibility/delivery guard but successful Water transport is now passage transport.

The VPS creates a separate `water_passages` SQLite table and one `/media/passages/<stable passage filename>` object per retained passage. Upsert is keyed by `passage_id`. Retention deletes only oldest completed passages; if the cap cannot be satisfied without deleting active rows, the transaction fails closed. Pruned media is deleted after DB commit. No per-frame observation table exists.

The Water operator history switches from legacy Water events to passage rows. A card can transition from measuring/null speed to measured speed/direction because its identity is stable by `passage_id`.

The post-merge production preflight now also owns one narrow recovery transaction for the operator-observed protected `/sea-speed/` HTTP 500. `deploy/vps/deploy.sh` stages the exact release and validates the restricted helper first, then reads the anonymous protected Operator HTTP status before any live source/service/current-release mutation. Normal `302|401|403` continues without recovery. Exactly HTTP 500 invokes the same `reconcile` request through the root-owned helper. Any other response fails closed.

The privileged helper first attempts the existing `--require-protected-baseline` cutover path. Recovery is admitted only when that exact prepare fails with the existing explicit `/sea-speed/ ... HTTP 500` marker. The helper then retries the same exact source-managed prepare/activate pipeline without the healthy-baseline prerequisite. This relaxation is not generic: source bundle digests, fixed Authentik/ZeroTier topology and cutover renderer remain unchanged. If recovery activation fails, the helper restores the exact pre-recovery nginx backup bytes under the bounded `/etc/nginx` and `/var/lib/sea-speed-auth-v1/backups` roots, validates nginx syntax/service state and returns failure. Successful recovery emits `SEA_SPEED_AUTH_RECOVERY=PASS`; `deploy.sh` then independently re-reads `/sea-speed/` and requires `302|401|403` before normal Water VPS mutation proceeds.

## Decisions

- D-001: Treat `passage_id` as the Water business identity for one physical pass; ByteTrack IDs remain transient fragments.
- D-002: Use bounded temporal + spatial stitching only as an architectural first step; permanent cross-passage ReID is explicitly deferred.
- D-003: Keep raw observations in Worker RAM deques only; persist compact passage state and measurement metadata.
- D-004: Define speed through a strategy boundary. `two_gate` is the first implementation, not a permanent storage/UI contract.
- D-005: Make speed lifecycle update-in-place on the passage so initial detection cannot permanently freeze `speed_kmh=null`.
- D-006: Use one stable remote snapshot filename per passage and one transient local crop, replacing the same media object when a materially better candidate appears.
- D-007: Keep the existing newest-100 Objects Registry untouched; Water passage persistence is additive and independently capped at 300.
- D-008: Fail closed when passage retention cannot make space without deleting active rows.
- D-009: Package `worker/water_passage.py` explicitly in both Ubuntu Worker and edge exact artifacts because artifact construction is allowlist-based.
- D-010: Mixed rollout order is VPS first, then Ubuntu Worker. Old Worker events remain compatible with the new VPS; new Worker passage transport is not compatible with an old VPS lacking `/api/cam1/passages`.
- D-011: Rollback order is Ubuntu Worker first to the prior accepted executable, then VPS if required; this prevents a new Worker from targeting a rolled-back VPS API.
- D-012: Treat current protected `/sea-speed/` HTTP 500 as a VPS release blocker. Recovery must complete before Water live-source mutation and before Ubuntu rollout.
- D-013: Do not add a new generic root command/action. Reuse the exact `reconcile` request and fixed source-managed cutover; only the helper internally recognizes the explicit HTTP 500 baseline failure and enters the bounded fallback.
- D-014: Recovery rollback proves exact pre-recovery nginx byte restoration plus nginx syntax/service health. It does not falsely require the already-broken public HTTP baseline to become healthy during rollback.
- D-015: HTTP 200 at the anonymous protected Operator entrypoint is not a recovery success; it is treated as a fail-closed auth-boundary violation. Only `302|401|403` is healthy for the pre-source gate.

## Affected contours

- VPS: REQUIRED — passage persistence/API/UI plus bounded Auth v1 recovery/deployment transaction behavior.
- Ubuntu Worker/relay: REQUIRED — shared executable Worker source imports and executes passage logic after VPS acceptance.
- Windows Worker: retired; NOT APPLICABLE.
- Runtime execution capability at source time: VPS `CONNECTOR`, but a changed exact privileged-helper bundle may require the existing protected privilege-bootstrap checkpoint before canonical deployment; Ubuntu `ONE_COMMAND_FALLBACK` unless restricted transport is independently proven before release.
- Mixed compatibility: VPS-first is mandatory; Ubuntu remains blocked while `/sea-speed/` is HTTP 500 or VPS passage/API acceptance is incomplete.

## Validation

Local/deterministic validation covers pure passage behavior, pluggable speed strategy, bounded RAM state, SQLite upsert/retention/media cleanup, frontend markers and artifact allowlists. Recovery validation adds three layers: helper unit tests prove only the exact 500 marker enters fallback and failed recovery activation requires the exact-baseline restorer; VPS transaction tests prove recovery happens before live source mutation and non-recoverable statuses fail closed; existing Auth v1/transaction/quality suites retain the fixed topology and no-arbitrary-root contracts.

PR admission requires exact authorized-path comparison, machine-valid mixed-contour Change Contract, Risk profile REQUIRED and Quality verdict PASS or CONCERNS with concrete finding. Merge requires fresh main/head/scope/review checks and expected-head protection, followed by exact-main Quality.

Production is separate. After the remediation merges, the previous production fingerprint is stale. A new exact-SHA production envelope is required. The runtime sequence is: exact privileged-helper/release admission -> bounded Auth 500 recovery if needed -> prove `/sea-speed/` auth-gated -> deploy/verify VPS passage API/UI/storage -> deploy exact Ubuntu Worker -> natural-vessel passage acceptance. Numerical speed accuracy remains deferred.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: DATA | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: independent hard 300-row cap, completed-first deterministic pruning, stable one-file snapshots, fail-closed active overflow | Validation: API retention/media tests | Residual risk: prolonged active-only flood can reject new passage persistence | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: bounded time+distance stitch criteria, active-passage cap, explicit new-pass fallback | Validation: deterministic stitch/new-pass tests plus runtime observation | Residual risk: nearby simultaneous vessels can still be mis-associated without visual ReID | Owner: Delivery Orchestrator | Status: ACCEPTED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: VPS-first rollout; old Worker remains compatible with upgraded VPS; rollback Worker before VPS | Validation: Change Contract plus production rollout evidence | Residual risk: partial rollout remains incomplete until both contours pass | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: PERF | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: fixed-size RAM deques and no per-frame network/SQLite writes; persist only state transitions/material snapshot improvements | Validation: unit contracts and production telemetry | Residual risk: many simultaneous vessels increase bounded in-memory work | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: BUS | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: speed accuracy out of scope; expose `speed_method`/status/metadata for later replacement | Validation: strategy contract tests | Residual risk: test-stage numeric speed may be approximate | Owner: Product/operator | Status: ACCEPTED
- RISK-006 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: recovery only after exact HTTP 500 marker from protected-baseline verifier; exact root-owned bundle; fixed topology; bounded path roots; no new request action; exact rollback on failed activation | Validation: helper unit tests, transaction tests, aggregate Auth v1 regressions | Residual risk: recovery cannot repair a fundamentally unhealthy Authentik upstream and must fail closed | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-007 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: recover before live Water source mutation; re-read protected status before continuing; Ubuntu remains blocked until VPS accepted | Validation: simulated HTTP 500 deploy transaction and production acceptance | Residual risk: privilege bundle bootstrap may still be a protected human checkpoint when helper bytes change | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: unit | Priority: P0 | Evidence: `tests/test_water_passage.py` bounded stitch/new-pass tests
- TEST-002 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: bounded observation deque test
- TEST-003 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: injected fake `SpeedEstimator` test
- TEST-004 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: A→B/B→A and incomplete `TwoGateSpeedEstimator` tests
- TEST-005 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: material best-snapshot replacement test
- TEST-006 | Covers: AC-007,AC-008,AC-009 | Level: integration | Priority: P0 | Evidence: AST-isolated API SQLite/media retention tests
- TEST-007 | Covers: AC-010 | Level: integration | Priority: P0 | Evidence: existing Water/Road/profile/ROI suites in aggregate Quality
- TEST-008 | Covers: AC-011,AC-012 | Level: integration | Priority: P0 | Evidence: frontend and exact-artifact contract tests
- TEST-009 | Covers: AC-013 | Level: integration | Priority: P0 | Evidence: Connector exact diff, PR Validation, aggregate Quality, expected-head merge, exact-main Quality
- TEST-010 | Covers: AC-014 | Level: runtime-manual | Priority: P0 | Evidence: separately authorized VPS-first/Ubuntu-second natural-vessel acceptance in Issue #218
- TEST-011 | Covers: AC-015 | Level: integration | Priority: P0 | Evidence: `tests/test_vps_deploy_transaction.py` HTTP 500 recovery-before-source test
- TEST-012 | Covers: AC-016 | Level: integration | Priority: P0 | Evidence: helper fallback tests for exact 500 vs non-500 and failed activation restorer plus runtime authenticated/anonymous HTTP evidence

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: #218 remains canonical. Operator reported protected `/sea-speed/` HTTP 500 after PR #219 merged but before production mutation.
- Root cause: canonical deploy order had a circular admission dependency. Public frontend smoke rejected 500 before `run_auth_boundary`, while the privileged cutover's `--require-protected-baseline` rejected 500 before it could reconcile the boundary.
- Adjacent-stage review: `deploy.sh`, restricted helper, cutover semantics, Auth v1 renderer/topology, release ordering and rollback were reviewed together. No model/Worker/MediaMTX/RTSP/data change is causal.
- Specification impact: adds FR-017..019 and AC-015..016 for bounded pre-source HTTP 500 recovery.
- Plan impact: adds a pre-source Auth recovery checkpoint and exact broken-baseline rollback semantics; normal healthy protected-baseline reconciliation remains unchanged.
- Tasks impact: source remediation, focused tests, a new exact PR/merge/main Quality cycle and a fresh production fingerprint are required.
- Authorization impact: RESOLVED — expanded source authorization is Issue #218 comment `5327660150`; old production fingerprint is invalidated; production remains unauthorized.
- Follow-up: if runtime diagnostics show Authentik itself is unhealthy rather than a recoverable nginx/outpost boundary, recovery fails closed and a new causal remediation Scope is required rather than widening this path.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Root cause / architecture finding: the source architecture from #219 is valid, but existing production ingress is currently blocked by an Auth v1 HTTP 500 and the old transaction ordering could not self-repair that fail-closed state.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: current accepted VPS/Worker remain unchanged | Retry: only after exact merged SHA has successful exact-main Quality, matching fresh production authorization and exact privileged bundle admission | Rollback: not applicable | Evidence: Issue #218, merged PR, exact SHA, Quality, authorization fingerprint
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: Water API/frontend/current-release remain unchanged; failed recovery restores exact pre-recovery nginx bytes | Retry: only for the same exact authorized SHA after causal preflight issue is resolved | Rollback: exact nginx backup, syntax/service verification; no broken-baseline health fiction | Evidence: `AUTH_V1_RECOVERY_PRE_SOURCE=PASS` or exact failure/rollback markers
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: partially mutated contour is not accepted | Retry: only after root cause is resolved for same authorized SHA | Rollback: repository-owned exact source rollback; VPS transaction before Ubuntu | Evidence: deploy transaction markers and exact source identities
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed contour remains unaccepted and Ubuntu must not substitute | Retry: reverify after bounded remediation | Rollback: if VPS fails, do not deploy Worker; if Worker fails, rollback Worker | Evidence: protected `/sea-speed/`, VPS API/UI/DB cap, Ubuntu source/service/frame/AI, natural passage lifecycle
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: exact release is not accepted without verification | Retry: commit state only after verification | Rollback: restore prior current-release/manifest bindings | Evidence: deployment manifests/current-release markers
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime may remain accepted while stale cleanup is pending | Retry: cleanup without changing active source | Rollback: none | Evidence: passage/media counts and release cleanup output
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: Outcome cannot reach DONE | Retry: collect sanitized evidence without redeploy solely for documentation | Rollback: not applicable | Evidence: Issue #218 comments, Quality/run identity, recovery and passage acceptance
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: previous compatible state restored or unresolved state recorded fail-closed | Retry: prohibited until actual runtime state verified | Rollback: Ubuntu first, then VPS if needed; recovery-phase rollback restores pre-recovery nginx only | Evidence: rollback markers, prior exact SHA, API/Worker/auth health

## Runtime feedback

- Initial source authorization base was `a2b27333d38ab6b430c51e814256535ca878b3fb`; PR #219 merged to `e814d32f9b743d674ce87556313e264debd0bc14` and exact-main Quality passed.
- Current accepted executable Water Worker before this Outcome remains `a43ad7bec5bbcd80887bad842ab28c20b135381a`.
- Operator-observed production ingress now reports HTTP 500 on `/sea-speed/`; no new Water production mutation has occurred under #218.
- Root-cause checkpoint: Issue #218 comment `5327488945`. Expanded source authorization: comment `5327660150`.
- Production accuracy of speed remains intentionally outside this test-stage gate; architecture, lifecycle, bounded state, recoverable protected ingress and replaceability are the target.
