# Delivery Tasks: Water unified passage speed

- Specification: `specs/072-water-unified-passage-speed/spec.md`
- Issue: #346
- Branch: `issue-346-water-unified-passage-speed`
- Authorization: Task 2 `OUTCOME APPROVED`; execution resumes from accepted protected main `e383c836253a8d9c3d824ed8f7c9cd8c1b6be1b5`.
- Runtime contour: Ubuntu Worker REQUIRED; VPS NOT REQUIRED.
- Change Contract risk profile: REQUIRED because Water speed-calculation ownership and measured-passage semantics change in production.

## Delivery tasks

- T001 — Add explicit fresh instantaneous calibrated telemetry (`speed_sample_fresh`, `speed_instant_kmh`) without treating held display speed as new evidence.
- T002 — Compute Water calibrated telemetry before `PassageEngine.update` and pass it into passage state.
- T003 — Add bounded passage-level calibrated samples with default minimum/smoothing aligned to existing detection-first configuration.
- T004 — Make calibrated fallback measured after sufficient fresh evidence and record sample count plus min/avg/max metadata.
- T005 — Preserve calibrated evidence across stitched ByteTrack fragments because state belongs to the passage, not the track ID.
- T006 — Give completed strict `two_gate` measurement precedence over calibrated fallback.
- T007 — Preserve calibrated measured result on finalize; finalize insufficient calibrated evidence as incomplete/null.
- T008 — Remove independent Water post-passage live speed overwrite and publish live speed copied from canonical passage state.
- T009 — Preserve Road logic, API schema, frontend, detector/tracker/ROI and network/media topology unchanged.
- T010 — Add deterministic passage lifecycle and worker wiring regressions.
- T011 — Run SDD/risk/Change Contract validation and exact-head Repository validation + quality-integration.
- T012 — Fresh-read base/head/scope/reviews, merge exact green head, and require exact-main Quality.
- T013 — Deploy exact-main Ubuntu Worker only and require runtime progression/runtime_verified evidence.
- T014 — Confirm in production that canonical live measured speed corresponds to a numeric latest passage rather than `не измерена`.

## Requirements traceability

- AC-001 | Task: T001,T003,T004,T010 | Evidence: 10/12/14 fresh samples -> calibrated measured 12.0 with sample/min/avg/max metadata | Coverage: COVERED
- AC-002 | Task: T001,T010 | Evidence: held non-fresh telemetry does not increment passage evidence | Coverage: COVERED
- AC-003 | Task: T003,T005,T010 | Evidence: samples across stitched track IDs complete one passage | Coverage: COVERED
- AC-004 | Task: T006,T010 | Evidence: later strict A->B result replaces calibrated fallback | Coverage: COVERED
- AC-005 | Task: T007,T010 | Evidence: measured fallback survives finalize; insufficient samples become incomplete/null | Coverage: COVERED
- AC-006 | Task: T002,T008,T010 | Evidence: source-order contract plus absence of `_det["speed_kmh"] = _inst` overwrite | Coverage: COVERED
- AC-007 | Task: T009,T010 | Evidence: exact diff and existing Road regression suite | Coverage: COVERED
- AC-008 | Task: T011,T012,T013 | Evidence: exact-head/exact-main checks plus protected Ubuntu Worker deployment evidence | Coverage: COVERED
- AC-009 | Task: T013,T014 | Evidence: production live measured speed and matching persisted latest passage numeric speed | Coverage: RUNTIME-MANUAL | Reason: requires a real vessel with sufficient calibrated evidence in the production camera field

## Definition of Done

- Issue/spec/plan/tasks current — #346 Task 2 and SDD 072 describe one canonical Water passage speed lifecycle.
- Exact changed-file scope verified — only approved Worker files, approved tests and SDD 072; API/frontend/Road pages/detector/tracker/ROI/topology remain zero-diff.
- Required deterministic tests green — fresh threshold, held exclusion, track churn, gate precedence, finalize behavior and Worker ordering/overwrite contract.
- Required CI green — exact PR head Repository validation and quality-integration succeed.
- Exact-green-head merge complete — merge only after fresh base/head/scope/review verification.
- Exact-main Quality green — protected main exact commit has required aggregate Quality evidence.
- Deployment state resolved — Ubuntu Water Worker exact-main is runtime_verified or explicit rollback is recorded; VPS deployment is not required.
- Runtime acceptance resolved — a production passage with canonical live measured speed persists numeric measured speed instead of `не измерена`.
- Road regression resolved — no Road semantic/source behavior change attributable to Task 2.
- Deferred work recorded — Task 3 Water detection/tracking recall remains separate in #346.
- Risks resolved or explicitly accepted — speed-semantics risk is bounded by deterministic evidence, Worker-only deployment, exact rollback and production acceptance.
- Waivers resolved or current — no waiver expected; any waiver must satisfy repository policy.

## Completion gate

Task 2 is complete only when source/CI/exact-main Worker deployment are green and production evidence demonstrates that a canonical measured Water live speed is persisted on the corresponding passage rather than rendered as `не измерена`.