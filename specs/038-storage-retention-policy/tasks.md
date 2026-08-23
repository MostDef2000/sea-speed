# Tasks: Storage retention policy

- Feature: 038-storage-retention-policy
- Specification: specs/038-storage-retention-policy/spec.md
- Plan: specs/038-storage-retention-policy/plan.md
- Issue: #261
- Status: Source implementation

## Delivery tasks

- [x] T1: SDD artifacts (spec/plan/tasks) for Issue 261.
- [x] T2: Per-domain prune in `prune_objects_registry` returning evicted snapshot URLs.
- [x] T3: Events-media sweep with grace period, reference check, unsafe-name guard and hourly throttle; startup invocation.
- [x] T4: Passage mirror sync on passage pruning + startup reconciliation.
- [x] T5: Tests: new `tests/test_storage_retention.py`; update `tests/test_api_contract.py` and `tests/test_unified_registry.py` to per-domain semantics.
- [x] T6: Local validation (unittest discovery, repository validators, quality validators).
- [x] T7: PR with exact Change Contract; required CI green on exact head; exact-green-head merge.
- [ ] T8: Post-deploy runtime acceptance (AC-010) recorded in Issue 261.

## Requirements traceability

- AC-001 | Task: T2, T5 | Evidence: tests/test_storage_retention.py::test_per_domain_retention_keeps_100_each | Coverage: COVERED
- AC-002 | Task: T3 | Evidence: tests/test_storage_retention.py::test_sweep_deletes_unreferenced_old_snapshots | Coverage: COVERED
- AC-003 | Task: T3 | Evidence: tests/test_storage_retention.py::test_sweep_keeps_recent_files | Coverage: COVERED
- AC-004 | Task: T3 | Evidence: tests/test_storage_retention.py::test_media_sweep_ignores_unsafe_names | Coverage: COVERED
- AC-005 | Task: T3 | Evidence: tests/test_storage_retention.py::test_sweep_throttled_to_hourly | Coverage: COVERED
- AC-006 | Task: T4 | Evidence: tests/test_storage_retention.py::test_passage_prune_removes_mirror_rows | Coverage: COVERED
- AC-007 | Task: T4 | Evidence: tests/test_storage_retention.py::test_reconciliation_removes_orphan_mirrors | Coverage: COVERED
- AC-008 | Task: T6 | Evidence: local unittest discovery run log | Coverage: COVERED
- AC-009 | Task: T7 | Evidence: required CI runs on exact PR head in Issue #261 checkpoint | Coverage: COVERED
- AC-010 | Task: T8 | Evidence: post-deploy verification comment to be recorded in Issue #261 | Coverage: RUNTIME-MANUAL | Reason: physical VPS storage behavior observable only after protected deployment
- AC-011 | Task: T7 | Evidence: scripts/ci/validate_change_contract.py PASS on PR body | Coverage: COVERED

## Completion gate

All AC checked with evidence; required CI green on merged main; deployment
policy decision recorded; runtime acceptance comment posted.

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [x] Deferred work recorded (none)
- [x] Risks resolved or explicitly accepted (RISK-038-001..004 MITIGATED)
- [x] Waivers resolved or current (none)
