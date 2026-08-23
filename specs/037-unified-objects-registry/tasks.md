# Tasks: Unified objects registry

- Feature: 037-unified-objects-registry
- Specification: specs/037-unified-objects-registry/spec.md
- Plan: specs/037-unified-objects-registry/plan.md
- Issue: #259
- Status: Source implementation

## Delivery tasks

- [x] T1: SDD artifacts (spec/plan/tasks) for Issue 259.
- [x] T2: API `persist_passage_object` + wiring in `post_cam1_passage` +
  startup `import_existing_passages` backfill (`api/app/main.py`).
- [x] T3: Registry page domain selector enabled with in-place scope switching
  and single nav link (`frontend/sea-speed/objects/index.html`).
- [x] T4: Unit tests `tests/test_unified_registry.py` (AC-001..AC-005, AC-007,
  AC-008 static contracts, mirror-failure isolation).
- [x] T5: Local validation: unittest discovery, repository validators, quality
  validators, exact-artifact build.
- [x] T6: PR with exact Change Contract; required CI green on exact head;
  exact-green-head merge.
- [ ] T7: Post-deploy runtime acceptance (AC-011) recorded in Issue 259.

## Requirements traceability

| AC | Requirement | Task | Evidence |
| --- | --- | --- | --- |
| AC-001 | R1 | T2/T4 | test_persists_water_passage_into_objects_registry |
| AC-002 | R1/R2 | T4 | test_repeated_updates_refresh_without_duplicates |
| AC-003 | R3 | T4 | test_operator_fields_survive_mirroring |
| AC-004 | R5 | T4 | test_startup_backfill_is_idempotent |
| AC-005 | R1 | T4 | test_domain_water_filter_returns_passages |
| AC-006 | R6 | T3/T4 | static contract test domain selector enabled + switch handler |
| AC-007 | R7 | T4 | static contract test referrer pre-selection preserved |
| AC-008 | R8 | T3/T4 | static contract test single registry nav link |
| AC-009 | all | T5 | local unittest run log |
| AC-010 | all | T6 | required CI runs on PR head |
| AC-011 | outcome | T7 | post-deploy evidence comment in Issue 259 |
| AC-012 | contract | T6 | validate_change_contract.py PASS |

## Completion gate

All AC checked with evidence; required CI green on merged main; deployment
policy decision recorded; runtime acceptance comment posted.

## Definition of Done

- [x] All planned tasks completed or explicitly deferred with reason
- [x] Tests written and passing locally
- [x] Change Contract matches final diff
- [x] No secrets, no runtime artifacts committed
- [x] Specs current (spec/plan/tasks reflect implementation)
- [x] Required CI green
- [x] Waivers resolved or current (none)
