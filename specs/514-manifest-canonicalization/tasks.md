# Tasks: #514 runtime manifest canonicalization (write+verify)

- Issue: #514
- Specification: specs/514-manifest-canonicalization/spec.md

## Delivery tasks

- T-514-001: RECON — re-read the cited prepare-runtime.sh regions on main b337549 and confirm the root cause (lock pins `.lower()`-normalized vs manifest keys baked from lowercased dist metadata Name; verify lookup miss → actual=None; finalize_runtime verify-without-manifest + re-bake same key → 3/3 recurrence); read tests/test_ubuntu_worker_runtime_rebuild.py and the harness override contract
- T-514-002: Implement the fix — ONE `SEA_SPEED_PYPI_CANON_SRC` definition + export in prepare-runtime.sh; exec-inject into the verify block (graph keys, requirements cross-check, read-time `installed_canonical` map + canonical lookup) and the write block (dist metadata Name key); no other behavior change (manifest fields/hashes/JSON formatting byte-identical)
- T-514-003: Tests — 4 new harness-driven cases in tests/test_ubuntu_worker_runtime_rebuild.py: metadata-Name-keyed manifest verifies WITHOUT rebuild (RED on base, exact incident signature); genuinely-missing negative control still fails+rebuilds; re-baked keys asserted canonical + re-verified (recurrence closed); structural pin (one definition, two injections, no `.lower()` in verify block)
- T-514-004: Verification battery — full pytest (1031 baseline + 4 new, 4 skipped); focused rebuild module; sibling prepare-runtime suites; bash -n prepare-runtime.sh; validate_repo; validate_sdd; gate CLI; ruff (zero new findings); RED-vs-base contrast via SEA_SPEED_426_PREPARE_RUNTIME_PATH; single commit on sdd/514-manifest-canonicalization, NOT pushed (orchestrator-owned push/PR/CI/merge/deploy)

## Completion gate

- [ ] T-514-001
- [ ] T-514-002
- [ ] T-514-003
- [ ] T-514-004
- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete

## Requirements traceability

- AC-001 | Task: T-514-002, T-514-003 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T-514-003, T-514-004 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-514-002, T-514-003 | Evidence: TEST-004 | Coverage: COVERED
- AC-004 | Task: T-514-003 | Evidence: TEST-003 | Coverage: COVERED
- AC-005 | Task: T-514-001 | Evidence: TEST-001, reviewer enumeration | Coverage: COVERED
- AC-006 | Task: T-514-004 | Evidence: TEST-005 | Coverage: COVERED

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — rides the next routine Ubuntu-worker deploy (DEPLOY-TRIGGER, полоса A) — orchestrator-owned; #514 closes after two consecutive clean deploy observations (no RUNTIME_VERIFY_FAILED+RUNTIME_REBUILT pair)
- [ ] Runtime acceptance resolved — health gate probe on the next worker deploy — orchestrator-owned
- [ ] Deferred work recorded — validate_runtime_lock keeps `.lower()` (deliberate; committed lock inputs are canonical; non-canonical future lock spelling fails closed); export-line structural pin candidate for a future hygiene commit (review nit N2)
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-008 mitigated in plan.md
- [ ] Waivers resolved or current — none
