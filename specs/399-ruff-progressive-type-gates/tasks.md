# Tasks: Ruff and progressive mypy quality gates

- Specification: specs/399-ruff-progressive-type-gates/spec.md

## Delivery tasks

- T-399-001: Insert the two steps into the `static-contract-security` job of
  `.github/workflows/quality-integration.yml` — `Ruff lint (non-mutating)`
  (`pip install ruff==0.16.10`; `ruff check .`) and `Progressive mypy (strict
  baseline)` (`pip install mypy==1.18.2`; `mypy --config-file mypy.ini` over
  the five strict modules) — after the JSON/py_compile step and before the
  unittest step, matching neighboring step style; no other workflow line
  changes (implements R-1, R-2, R-6)
- T-399-002: Create `ruff.toml` at the repository root: `target-version =
  "py314"`, `fix = false`, `[lint] select = ["E9", "F"]` with the written
  deferral rationale for E4/E7 and E501 (implements R-1, R-6)
- T-399-003: Create `mypy.ini` at the repository root: permissive global
  section (`python_version = 3.14`, `warn_unused_ignores`,
  `warn_redundant_casts`, `no_implicit_optional`) plus `strict = True`
  sections for scripts/quality/common, worker/analytics_profiles,
  worker/detection_performance, scripts/release/production_policy and
  scripts/ci/validate_delivery_checkpoint, with the progressive-adoption and
  narrow-suppression policy comments (implements R-2)
- T-399-004: Apply the calibrated source fixes resolving all 14 baseline
  findings mechanically (spec R-3 list): remove the 10 unused
  imports/names, the 3 dead locals, the f-string prefix, and add the five
  `collections.deque[float]` annotations in worker/detection_performance.py;
  no `# noqa` or `# type: ignore` comments (implements R-3, R-4)
- T-399-005: Document the gate in `docs/quality/testing-policy.md` under
  "Static analysis (Ruff and mypy)": domain placement, pins with rationale,
  progressive-strict adoption policy, suppression rules, non-mutating
  property and the exact local commands (implements R-5)
- T-399-006: Write the SDD trio under `specs/399-ruff-progressive-type-gates/`
  with NFR assessment, Risk profile NOT REQUIRED, test design, correct-course
  check, requirements traceability and Definition of Done (implements R-5,
  R-6)
- T-399-007: Run the full local battery — `ruff check .`, the mypy strict
  command, workflow-policy/repo/contract/quality-contract validators,
  py_compile and the unittest suite on CPython 3.14 (expected baseline
  Ran 649 tests, OK, skipped=3) — and verify scope isolation with
  `git diff --stat` (implements R-3, R-4, R-5)
- T-399-008: Open the PR with the Change Contract (CONTROL_PLANE), record
  "Quality integration gate" CI evidence with both new steps green, reach
  exact-green-head CI and merge; close out the Definition of Done

## Completion gate

- [ ] T-399-001
- [ ] T-399-002
- [ ] T-399-003
- [ ] T-399-004
- [ ] T-399-005
- [ ] T-399-006
- [ ] T-399-007
- [ ] T-399-008

## Deferred work

- None blocking. Widening the Ruff rule set beyond E9+F (default E4/E7
  families, E501) and growing the mypy strict set beyond the initial five
  modules are deliberate follow-up adoption decisions taken at code review,
  not work deferred by this task (plan DEC-3, DEC-5).

## Requirements traceability

- AC-001 | Task: T-399-001,T-399-002,T-399-004 | Evidence: `Ruff lint (non-mutating)` step present in static-contract-security (after JSON/py_compile, before unittest); local `ruff check .` exits 0 with the calibrated tree (R-1, R-6) | Coverage: COVERED
- AC-002 | Task: T-399-001,T-399-003,T-399-004 | Evidence: `Progressive mypy (strict baseline)` step present in the same position; local mypy 1.18.2 over the five strict modules exits 0 (R-2, R-6) | Coverage: COVERED
- AC-003 | Task: T-399-007 | Evidence: local battery green — ruff zero findings, mypy strict clean, validate_workflow_policy.py/validate_repo.py/validate_contracts.py/validate_quality_contracts.py pass, py_compile passes, unittest Ran 649 tests OK skipped=3 (R-3, R-4) | Coverage: COVERED
- AC-004 | Task: T-399-005 | Evidence: docs/quality/testing-policy.md carries the "Static analysis (Ruff and mypy)" section with domain placement, pins/rationale, progressive-strict policy, suppression rules and exact commands; `Status: Active` marker untouched (R-5) | Coverage: COVERED
- AC-005 | Task: T-399-007 | Evidence: `git diff --stat` shows exactly the 18 allowed files; no validator, test, deploy path, data/quality file or other workflow modified (R-4) | Coverage: COVERED
- AC-006 | Task: T-399-008 | Evidence: PR Change Contract valid and classified CONTROL_PLANE; exact-green-head merge of the linked PR with required CI green, recorded by the Delivery Orchestrator (R-4) | Coverage: COVERED
- R-1 | Task: T-399-001,T-399-002 | Evidence: ruff.toml committed (select E9+F, fix=false, py314) and the pinned non-mutating step in the aggregate's static domain; no blanket ignores introduced (AC-001) | Coverage: COVERED
- R-2 | Task: T-399-001,T-399-003 | Evidence: mypy.ini committed with permissive global section and five strict per-module sections; pinned install and config-file invocation in the workflow (AC-002) | Coverage: COVERED
- R-3 | Task: T-399-004 | Evidence: the 14 findings (10 F401, 3 F841, 1 F541) resolved mechanically per the spec R-3 list; ruff check . reports zero findings (AC-001, AC-003) | Coverage: COVERED
- R-4 | Task: T-399-004,T-399-007 | Evidence: only the two workflow steps inserted (markers byte-identical); validators, behavioral suite and exact-artifact gates pass unchanged (AC-003, AC-005) | Coverage: COVERED
- R-5 | Task: T-399-005,T-399-006 | Evidence: deterministic local commands documented in docs/quality/testing-policy.md and mirrored in the workflow (AC-004) | Coverage: COVERED
- R-6 | Task: T-399-001,T-399-002 | Evidence: fix=false config, analysis-only mypy step, no heredocs, no new uses: entries — CI cannot rewrite source (AC-001, AC-002) | Coverage: COVERED

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
