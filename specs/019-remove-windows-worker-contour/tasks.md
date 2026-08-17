# Delivery tasks — retire Windows Worker production contour

Specification: `specs/019-remove-windows-worker-contour/spec.md`
Issue: #199

## Delivery tasks

- TASK-001: Update canonical change-control policy and Change Contract validation/template so active runtime derivation contains only VPS and Ubuntu Worker/relay; classify Windows scripts/docs as non-runtime archival/control-plane.
- TASK-002: Remove Windows runtime execution routing and delete the obsolete Windows package workflow while preserving protected VPS/Ubuntu routing.
- TASK-003: Update production authorization compatibility so modern fingerprints bind only active VPS/Ubuntu fields while immutable historical Windows-shaped PRs retain their historical payload shape.
- TASK-004: Stop new `windows-worker` release creation; preserve historical manifest readability; remove Windows scripts from exact edge quality artifacts and make their reintroduction fail closed.
- TASK-005: Converge AGENTS, canonical governance/delivery/runtime/release contracts, review lenses and operational/architecture docs on exactly two active production contours.
- TASK-006: Mark retained Windows helper documentation as deprecated non-production local/archive tooling without modifying generic portable Worker behavior or historical evidence.
- TASK-007: Add/update regression coverage for two-contour classification, routing, authorization, manifests, artifact inventory, contract convergence and portable legacy Worker defaults.
- TASK-008: Validate exact 40-path branch scope, open the linked PR, remediate only within authorized scope, require exact-head PR Validation + aggregate Quality, expected-head merge and post-merge checks.
- TASK-009: Persist exact migration evidence to Issue #199 and close the Issue after post-merge green verification. No production authorization or runtime action is required.

## Requirements traceability

- AC-001 | Task: TASK-001,TASK-007 | Evidence: `tests/test_change_contract.py` proves shared Worker is Ubuntu-only and VPS+shared Worker is two-contour MIXED | Coverage: COVERED
- AC-002 | Task: TASK-001,TASK-006,TASK-007 | Evidence: `tests/test_change_contract.py` proves Windows scripts/docs derive no runtime and legacy Windows fields fail new Change Contracts | Coverage: COVERED
- AC-003 | Task: TASK-005,TASK-007 | Evidence: `tests/test_delivery_contract_convergence.py` plus canonical docs/contracts assert exactly two active production contours | Coverage: COVERED
- AC-004 | Task: TASK-002,TASK-007 | Evidence: `scripts/quality/validate_workflow_policy.py` and `tests/quality/test_quality_architecture.py` prove no Windows router output/fallback/package workflow | Coverage: COVERED
- AC-005 | Task: TASK-003,TASK-007 | Evidence: `tests/test_production_authorization.py` proves modern two-contour payload and historical Windows payload-shape compatibility | Coverage: COVERED
- AC-006 | Task: TASK-004,TASK-007 | Evidence: `tests/test_release_manifest.py` proves new builder rejects Windows while legacy release/deployment validation remains readable | Coverage: COVERED
- AC-007 | Task: TASK-004,TASK-007 | Evidence: exact-artifact validator and `tests/quality/test_quality_architecture.py` prove no `.cmd`, `.ps1`, or `worker/windows/**` path enters edge artifact | Coverage: COVERED
- AC-008 | Task: TASK-008,TASK-009 | Evidence: exact 40-path PR diff, exact-head PR Validation/Quality, expected-head merge, post-merge checks and Issue #199 terminal evidence | Coverage: COVERED

## Completion gate

Completion requires all of the following:

- exact diff equals the authorized 40 paths, including deletion of `.github/workflows/package-worker.yml` and creation of the three SDD 019 files;
- new Change Contracts contain only VPS/Ubuntu runtime declarations;
- shared Worker classification is Ubuntu-only and archival Windows tooling has no runtime contour;
- modern authorization/runtime routing contains no Windows field/path, while historical evidence compatibility tests remain green;
- new release builder rejects Windows and exact edge artifact contains no Windows script;
- PR Validation and aggregate Quality integration pass on one exact final head;
- fresh main/head/scope/reviews/threads pass expected-head merge gates;
- post-merge exact-main PR Validation and Quality pass;
- Issue #199 records migration evidence and closes as completed;
- production/runtime deployment state is `NOT REQUIRED` for this CONTROL_PLANE migration.

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [ ] Deferred work recorded
- [ ] Risks resolved or explicitly accepted
- [ ] Waivers resolved or current

Deployment state resolves as `NOT REQUIRED`; runtime acceptance resolves as `NOT REQUIRED`. Deferred work consists only of unrelated Issue #197 provenance remediation and any future explicitly approved runtime architecture changes; neither is part of Issue #199.
