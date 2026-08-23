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

- AC-001 | Task: T2 | Evidence: tests/test_unified_registry.py::test_persists_water_passage_into_objects_registry | Coverage: COVERED
- AC-002 | Task: T4 | Evidence: tests/test_unified_registry.py::test_repeated_updates_refresh_without_duplicates | Coverage: COVERED
- AC-003 | Task: T4 | Evidence: tests/test_unified_registry.py::test_operator_fields_survive_mirroring | Coverage: COVERED
- AC-004 | Task: T2, T4 | Evidence: tests/test_unified_registry.py::test_startup_backfill_is_idempotent | Coverage: COVERED
- AC-005 | Task: T4 | Evidence: tests/test_unified_registry.py::test_domain_water_filter_returns_passages | Coverage: COVERED
- AC-006 | Task: T3, T4 | Evidence: tests/test_unified_registry.py::RegistryPageContractTests::test_domain_selector_enabled_with_switch_handler | Coverage: COVERED
- AC-007 | Task: T4 | Evidence: tests/test_unified_registry.py::RegistryPageContractTests::test_referrer_pre_selection_preserved | Coverage: COVERED
- AC-008 | Task: T3, T4 | Evidence: tests/test_unified_registry.py::RegistryPageContractTests::test_single_registry_nav_link | Coverage: COVERED
- AC-009 | Task: T5 | Evidence: local unittest discovery run log (445 OK, 2 pre-existing skips) | Coverage: COVERED
- AC-010 | Task: T6 | Evidence: required CI runs on exact PR head in Issue #259 checkpoint | Coverage: COVERED
- AC-011 | Task: T7 | Evidence: post-deploy verification comment to be recorded in Issue #259 | Coverage: RUNTIME-MANUAL | Reason: physical VPS runtime behavior observable only after protected deployment
- AC-012 | Task: T6 | Evidence: scripts/ci/validate_change_contract.py PASS on PR #260 body | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [x] Deferred work recorded (none)
- [x] Risks resolved or explicitly accepted (RISK-037-001..004 MITIGATED)
- [x] Waivers resolved or current (none)

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
