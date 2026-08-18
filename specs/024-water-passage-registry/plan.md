# Implementation Plan: Water Passage Architecture

- Specification: specs/024-water-passage-registry/spec.md
- Issue: #218
- Status: Implementing

## Architecture

Introduce pure-Python `worker/water_passage.py` as the bounded passage domain layer. `WaterPassageEngine` maps current ByteTrack fragments to active passages, keeps only fixed-size observation deques, chooses materially improving snapshot candidates, and delegates speed calculation to a `SpeedEstimator` instance owned by each passage.

`TwoGateSpeedEstimator` is the first strategy. It receives timestamped anchor observations, detects finite-segment crossings of Gate A and Gate B in either order, and returns a measurement result. The Worker integration posts passage metadata through a new idempotent `/api/cam1/passages` boundary. Existing Water YOLO admission remains continuous and ROI-bounded; Road retains its legacy event path. Existing `water_event_candidates` remains as a compatibility/delivery guard but successful Water transport is now passage transport.

The VPS creates a separate `water_passages` SQLite table and one `/media/passages/<stable passage filename>` object per retained passage. Upsert is keyed by `passage_id`. Retention deletes only oldest completed passages; if the cap cannot be satisfied without deleting active rows, the transaction fails closed. Pruned media is deleted after DB commit. No per-frame observation table exists.

The Water operator history switches from legacy Water events to passage rows. A card can transition from measuring/null speed to measured speed/direction because its identity is stable by `passage_id`.

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

## Affected contours

- VPS: REQUIRED — `api/app/main.py` adds bounded passage persistence/API/media and Water frontend reads it.
- Ubuntu Worker/relay: REQUIRED — shared executable Worker source imports and executes passage logic.
- Windows Worker: retired; NOT APPLICABLE.
- Runtime execution capability at source time: VPS `CONNECTOR`; Ubuntu `ONE_COMMAND_FALLBACK` unless restricted transport is independently proven before release.
- Operator actions expected: 1 under current capability evidence.
- Mixed compatibility: VPS-first is mandatory; old Worker can continue legacy event transport while VPS is upgraded.

## Validation

Local deterministic validation covers pure passage behavior, pluggable speed strategy, bounded RAM state, SQLite upsert/retention/media cleanup, frontend markers and artifact allowlists. Existing CI then supplies full Water/Road/API/ROI/profile regressions plus SDD/contract/static security gates. PR admission requires exact authorized-path comparison, machine-valid mixed-contour Change Contract, Risk profile REQUIRED and Quality verdict PASS or CONCERNS with concrete finding. Merge requires fresh main/head/scope/review checks and expected-head protection, followed by exact-main Quality.

Production is separate. After a new exact-SHA production envelope, deploy VPS first and prove passage API/UI/storage health, then deploy Ubuntu and observe source/runtime/AI progression plus a natural vessel passage. Accuracy tuning is deferred; acceptance checks lifecycle correctness and bounded data behavior.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: DATA | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: independent hard 300-row cap, completed-first deterministic pruning, stable one-file snapshots, fail-closed active overflow | Validation: API retention/media tests | Residual risk: a prolonged pathological active-only flood can reject new passage persistence | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: bounded time+distance stitch criteria, active-passage cap, explicit new-pass fallback | Validation: deterministic stitch/new-pass tests plus runtime observation | Residual risk: two nearby simultaneous vessels can still be mis-associated without visual ReID | Owner: Delivery Orchestrator | Status: ACCEPTED FOR TEST STAGE
- RISK-003 | Category: COMPAT | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: VPS-first rollout; old Worker remains compatible with upgraded VPS; rollback Worker before VPS | Validation: Change Contract plus production rollout evidence | Residual risk: partial rollout must remain visibly incomplete until both contours pass | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: PERF | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: fixed-size RAM deques and no per-frame network/SQLite writes; persist only state transitions/material snapshot improvements | Validation: unit contracts and production telemetry | Residual risk: scene with many simultaneous vessels may increase bounded in-memory work | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: BUS | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: declare speed accuracy out of scope; expose `speed_method`/status/metadata so later estimator replacement is non-breaking | Validation: strategy contract tests | Residual risk: test-stage numeric speed may be approximate | Owner: Product/operator | Status: ACCEPTED

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: unit | Priority: P0 | Evidence: `tests/test_water_passage.py` bounded stitch/new-pass tests
- TEST-002 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: bounded observation deque test
- TEST-003 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: injected fake `SpeedEstimator` test
- TEST-004 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: A→B/B→A and incomplete `TwoGateSpeedEstimator` tests
- TEST-005 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: material best-snapshot replacement test
- TEST-006 | Covers: AC-007,AC-008,AC-009 | Level: integration | Priority: P0 | Evidence: AST-isolated API SQLite/media retention tests
- TEST-007 | Covers: AC-010 | Level: regression | Priority: P0 | Evidence: existing Water/Road/profile/ROI suites in aggregate Quality
- TEST-008 | Covers: AC-011,AC-012 | Level: static integration | Priority: P0 | Evidence: frontend and exact-artifact contract tests
- TEST-009 | Covers: AC-013 | Level: integration | Priority: P0 | Evidence: Connector exact diff, PR Validation, aggregate Quality, expected-head merge, exact-main Quality
- TEST-010 | Covers: AC-014 | Level: runtime-manual | Priority: P0 | Evidence: separately authorized VPS-first/Ubuntu-second natural-vessel acceptance in Issue #218

## Correct-course check

- Trigger: PRODUCT_ARCHITECTURE
- Issue impact: #218 remains the canonical Issue; its initial two-gate wording is superseded by final authorization comment `5325409717` making speed strategy pluggable.
- Specification impact: passage identity, bounded RAM observations, speed lifecycle and independent 300-row persistence are now explicit contracts.
- Plan impact: `two_gate` becomes one strategy behind `SpeedEstimator`; mixed rollout and rollback ordering are explicit.
- Tasks impact: source, tests, SDD, CI/merge and separately authorized mixed-contour acceptance are required.
- Authorization impact: RESOLVED — final eleven-path authorization is comment `5325409717`; production remains unauthorized.
- Follow-up: after this architecture is accepted on real passages, a separate Outcome may add bounded persistent vessel identity/ReID and another may improve metric speed accuracy.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Root cause / architecture finding: #212 Water event identity was bound to transient ByteTrack tracks and event emission timing, so speed becoming available later could not update the same business record and tracker churn could create multiple event identities for one physical pass. Storage also had no passage-specific retention boundary.
- Adjacent-stage findings: detector/profile/ROI/MediaMTX/Auth are not causal; VPS must precede Worker because the new consumer requires a new endpoint; exact artifact allowlists must include the new Worker module; existing Road flow remains an independent compatibility boundary; raw trajectories are unnecessary persistent data.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: current accepted VPS/Worker remain unchanged | Retry: only after exact merged SHA has successful exact-main Quality and matching production authorization | Rollback: not applicable | Evidence: Issue #218, merged PR, exact SHA, Quality, authorization fingerprint
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: prior runtimes remain active | Retry: fix exact artifact/release/host preflight without runtime mutation | Rollback: not applicable | Evidence: release manifests, exact artifact inventory including `worker/water_passage.py`, current runtime states
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: partially mutated contour is not accepted | Retry: only after root cause is resolved for the same authorized SHA | Rollback: repository-owned exact rollback; VPS transaction first, Ubuntu second | Evidence: deploy transaction markers and exact source identities
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed contour remains unaccepted and later contour must not substitute for it | Retry: reverify after bounded remediation | Rollback: if VPS fails, do not deploy Worker; if Worker fails, rollback Worker while upgraded VPS may remain compatible pending decision | Evidence: VPS API/UI/DB cap, Ubuntu source/service/frame/AI, natural passage lifecycle
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: exact release must not be marked accepted without verification | Retry: commit state only after verification | Rollback: restore prior current-release/manifest bindings | Evidence: deployment manifests and current-release markers
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime may remain accepted while stale temp media/release cleanup is pending | Retry: cleanup without changing active source | Rollback: none for housekeeping-only failure | Evidence: retained passage/media counts and release cleanup output
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: Outcome cannot reach DONE | Retry: collect/persist sanitized observable evidence without redeploying solely for documentation | Rollback: not applicable | Evidence: Issue #218 comments, exact Quality/run identity, passage/storage/runtime acceptance
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: previous compatible Worker/VPS state is restored or unresolved production state is recorded fail-closed | Retry: prohibited until actual runtime state is verified | Rollback: Ubuntu first, then VPS if needed, preserving compatibility ordering | Evidence: rollback markers, prior exact SHA, API/Worker health and desired states

## Runtime feedback

- Current source authorization base is `a2b27333d38ab6b430c51e814256535ca878b3fb`.
- Current accepted executable Water Worker before this Outcome is `a43ad7bec5bbcd80887bad842ab28c20b135381a`; this new Outcome changes both Worker and VPS source and therefore requires a fresh exact merged production envelope.
- Production accuracy of speed is intentionally not a test-stage gate; architecture, lifecycle, bounded state and replaceability are the target.
