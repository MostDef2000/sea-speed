# Spec: Run production-facing CI on Python 3.14

- Issue: #391
- Specification: specs/391-python314-prod-ci/spec.md

## Product outcome

The merge-facing CI gates — `quality-integration.yml` and `pr-validation.yml` —
provision CPython 3.14 instead of 3.12, matching the production worker runtime
declared in `deploy/worker/ubuntu/runtime-lock.json` (implementation CPython,
major 3, minor 14). After this change a green `quality-integration` run proves
that the full behavioral suite, the property/fuzz/architecture checks, the
contract validators, and the exact-artifact build all pass on the same
interpreter generation that production runs, so green CI is direct evidence of
production-interpreter compatibility.

## User scenarios

- US-1: A contributor opens a PR; `pr-validation` and `quality-integration` run
  the existing gates on CPython 3.14 and block regressions that only appear on
  the production interpreter generation.
- US-2: A maintainer merges to main; the push-triggered `quality-integration`
  run builds exact artifacts and quality evidence on CPython 3.14.
- US-3: A future interpreter bump (e.g. 3.15) reuses this pattern: only the
  five `setup-python` pins change, with no test, validator, or deploy edits.

## Requirements

- R-1: All four `python-version` pins in `.github/workflows/quality-integration.yml`
  (lines 31, 74, 94, 127 — jobs static-contract-security,
  property-fuzz-reliability, exact-artifact-e2e, release-deployment-evidence)
  change from "3.12" to "3.14".
- R-2: The single `python-version` pin in `.github/workflows/pr-validation.yml`
  (line 33, job validate) changes from "3.12" to "3.14".
- R-3: No other change in either workflow file, and no workflow outside these
  two files is modified.
- R-4: No new test files, fixtures, or validator changes; verification is the
  execution of the existing suites on CPython 3.14.
- R-5: The full local verification battery passes on CPython 3.14: SDD/repo/
  contract/quality/workflow validators, py_compile, the unittest suite with
  -W error::ResourceWarning, and the exact-artifact build/validate pair.

## Acceptance criteria

- AC-001: `grep -n 'python-version'` over the two workflow files shows exactly
  five "3.14" pins (quality-integration.yml lines 31, 74, 94, 127;
  pr-validation.yml line 33) and zero "3.12" lines.
- AC-002: CI provisioning on the exact-green-head shows CPython 3.14.x selected
  by setup-python in all four quality-integration jobs and the pr-validation
  job, matching `deploy/worker/ubuntu/runtime-lock.json` (CPython 3.14).
- AC-003: On CPython 3.14 the quality-integration gate is green end to end:
  behavioral suite with -W error::ResourceWarning, deterministic property
  checks, fuzz/recovery checks, quality architecture tests, validators, and
  exact-artifact build/validate plus quality evidence.
- AC-004: Deploy-classified workflows are untouched: deploy-vps.yml (line 78),
  deploy-ubuntu-worker.yml (line 73) and deploy-runtime-autonomous.yml (line 69)
  remain explicitly pinned to "3.12" (tooling-only classification);
  main-quality-status.yml remains unpinned runner python (no setup-python step).
- AC-005: The PR diff contains exactly the five allowed files (two workflow
  bumps plus the three SDD artifacts) and nothing else.

## Runtime feedback

- RF-001: Operator actions expected: 0; verification is CI execution plus the
  local battery recorded in the PR description.
- RF-002: Post-merge, the exact-main quality commit status
  (`sea-speed/quality-push-main`, published by main-quality-status.yml) reflects
  the 3.14 gate result on main.

## NFR assessment

- NFR-CI-PARITY | Area: CI parity | Target: merge-facing CI provisions CPython 3.14.x equal to deploy/worker/ubuntu/runtime-lock.json (CPython 3.14) | Validation: inspect setup-python logs of the green exact-green-head run | Evidence: GitHub Actions quality-integration run on 3.14 | Status: PASS
- NFR-SUITE-314 | Area: reliability | Target: full unittest suite green on CPython 3.14 with -W error::ResourceWarning at the documented baseline (649 tests, 3 skipped) | Validation: local run on CPython 3.14.4 plus CI run | Evidence: unittest counts and CI run recorded in the PR | Status: PASS
- NFR-SCOPE | Area: maintainability | Target: diff limited to the 5 allowed files; deploy workflows unchanged | Validation: git diff --stat review | Evidence: PR files-changed list | Status: PASS
