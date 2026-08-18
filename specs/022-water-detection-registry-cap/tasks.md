# Delivery Tasks: Water detection activation and registry cap

- Specification: specs/022-water-detection-registry-cap/spec.md
- Plan: specs/022-water-detection-registry-cap/plan.md
- Issue: #212
- Status: Implementing

## Delivery tasks

- T-001 [P0] Change shared analytics default from `road-v1` to `water-v1` without altering either profile's model/tracker/threshold/class-map values. COMPLETE in source branch.
- T-002 [P0] Add deterministic combined SQLite Objects Registry retention helper with limit 100 and newest ordering `detected_at DESC, object_id DESC`. COMPLETE in source branch.
- T-003 [P0] Enforce retention after database initialization and after every successful new object insertion. COMPLETE in source branch.
- T-004 [P0] Add analytics-profile regression proving no-argument resolution selects Water and Road remains explicit/exact. COMPLETE in source branch.
- T-005 [P0] Add API persistence regressions for oversized initialization and successful-insert pruning while preserving existing API behavior. COMPLETE in source branch.
- T-006 [P0] Validate exact seven-path scope, syntax/SDD/secret absence and open the canonical PR linked to Issue #212. COMPLETE: PR #213 opened on exact seven-path ahead-only branch; initial PR Validation #445 exposed a Change Contract enum defect and the PR body was corrected to canonical `YES|NO` metadata without source-scope expansion.
- T-007 [P0] Reach exact-head PR Validation + aggregate Quality, remediate only inside approved scope and merge only exact green head. IN PROGRESS: PR Validation #446 exposed SDD-only validator mismatches; required User scenarios and canonical trigger/test-level/traceability enums were synchronized inside the approved SDD triplet.
- T-008 [P0] Verify exact-main post-merge Quality and compute future production authorization fingerprint for MIXED runtime release. PENDING.
- T-009 [P0] After separate production authorization, deploy VPS first and prove runtime registry count <=100 before/after new event ingestion. PENDING RUNTIME.
- T-010 [P0] Then deploy/activate Ubuntu Water worker on exact release and prove source/profile/model/service/frame/state/AI progression plus `vessel` detections entering registry. PENDING RUNTIME.
- T-011 [P0] Persist sanitized terminal evidence to Issue #212 and close only when all source/runtime acceptance is complete. PENDING.

## Requirements traceability

- AC-001 | Task: T-001,T-004 | Evidence: `tests/test_analytics_profiles.py` | Coverage: COVERED
- AC-002 | Task: T-002,T-003,T-005 | Evidence: `tests/test_api_contract.py` initialization retention test | Coverage: COVERED
- AC-003 | Task: T-002,T-003,T-005 | Evidence: `tests/test_api_contract.py` insert retention test | Coverage: COVERED
- AC-004 | Task: T-005 | Evidence: existing API contract suite | Coverage: COVERED
- AC-005 | Task: T-006 | Evidence: exact compare against approved seven paths; PR #213 changed-file count 7; `api/app/main.py` exact diff +22/-1 | Coverage: COVERED
- AC-006 | Task: T-007,T-008 | Evidence: exact-head PR Validation + aggregate Quality, expected-head merge, exact-main post-merge Quality | Coverage: COVERED
- AC-007 | Task: T-009,T-011 | Evidence: VPS deployment manifest and registry-count runtime evidence | Coverage: RUNTIME-MANUAL | Reason: production SQLite state is outside hosted CI
- AC-008 | Task: T-010,T-011 | Evidence: Ubuntu deployment manifest, exact Water service/telemetry/model/profile evidence and resulting object record | Coverage: RUNTIME-MANUAL | Reason: physical camera/GPU/service runtime is outside hosted CI

## Definition of Done

- Issue/spec/plan/tasks current: YES.
- Exact changed-file scope verified: YES — current compare from approved base contains exactly the approved seven paths and branch is ahead-only/behind=0.
- Required tests and evidence complete: NO — exact rerun CI and runtime evidence remain pending.
- Required CI green: PENDING — #445 metadata and #446 SDD contract defects are remediated; exact new-head checks required.
- Exact-green-head merge complete: NO.
- Deployment state resolved: NO — source authorization does not permit production mutation.
- Runtime acceptance resolved: NO — VPS registry and Ubuntu Water activation remain separately authorized future stages.
- Deferred work recorded: YES — snapshot/media cleanup, JSON event retention and any retention value redesign are explicitly out of scope.
- Risks resolved or explicitly accepted: YES for source design; irreversible loss of rows beyond newest 100 is explicitly accepted by the approved test-stage Outcome.
- Waivers resolved or current: YES — no waiver active.

## Completion gate

`COMPLETE` is forbidden until exact approved seven-path source is merged from an exact-green head with post-merge Quality, a fresh exact-SHA production authorization executes VPS-first then Ubuntu, VPS proves registry <=100, Ubuntu Water proves exact-source/model/profile/service/frame/state/AI acceptance with `vessel` object evidence, and Issue #212 contains terminal acceptance evidence.
