# Plan: Run production-facing CI on Python 3.14

- Specification: specs/391-python314-prod-ci/spec.md

## Architecture

Merge-facing CI is a five-job surface over CPython: `quality-integration.yml`
provisions setup-python four times (job static-contract-security, line 31;
property-fuzz-reliability, line 74; exact-artifact-e2e, line 94;
release-deployment-evidence, line 127) and `pr-validation.yml` once (job
validate, line 33). Each pin is a single scalar under a SHA-pinned setup-python
step; changing the scalar switches the interpreter for every step of that job
while actions, permissions, concurrency groups, and job wiring stay
byte-identical. The production worker runtime is declared in
`deploy/worker/ubuntu/runtime-lock.json` (CPython 3.14), so after the bump CI
and production share the same interpreter generation.

## Decisions

- DEC-1: Bump only the five setup-python pins to "3.14". setup-python resolves
  the latest available 3.14.x, which satisfies the runtime lock's
  major.minor (3.14) contract.
- DEC-2: Deploy-classified workflows remain explicitly on "3.12" and are
  classified tooling-only: deploy-vps.yml (line 78), deploy-ubuntu-worker.yml
  (line 73), and deploy-runtime-autonomous.yml (line 69) run artifact builders,
  validators, and deploy plumbing — not the application behavioral suite or the
  production worker payload. Changing them would trip the Deployment
  Transaction Audit (validate_sdd.py flags any `.github/workflows/deploy*`
  change) for zero behavioral benefit, so they stay untouched.
- DEC-3: main-quality-status.yml is left untouched: it has no setup-python step
  and uses the runner default python (line 40) only to shape a JSON status
  payload as a status publisher downstream of the quality gate.
- DEC-4: No new test files. The existing suites are the verification: CI
  execution on 3.14 is itself the acceptance test, because #391 is a
  CI-parity change, not a behavior change.
- DEC-5: Do not touch action SHAs, permissions, concurrency, or job wiring;
  the only intended workflow diff is the interpreter scalar.

## Affected contours

- `.github/workflows/quality-integration.yml` (4 pins) and
  `.github/workflows/pr-validation.yml` (1 pin) — CI control plane only.
- New SDD directory `specs/391-python314-prod-ci/` (documentation contour).
- No application code, no deploy/ files, no schemas, no tests, no runtime hosts.

## Validation

- `git diff --stat` and `git diff` — exactly the five allowed files.
- `grep -n 'python-version'` on both workflow files — 5x "3.14", 0x "3.12".
- `python3 -m py_compile scripts/ci/*.py scripts/quality/*.py scripts/release/*.py`.
- `python3 scripts/ci/validate_sdd.py` (no --event) for SDD structure.
- `python3 scripts/ci/validate_repo.py`, `validate_contracts.py`,
  `scripts/quality/validate_quality_contracts.py`,
  `scripts/quality/validate_workflow_policy.py`.
- `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`
  on CPython 3.14.4 — full behavioral suite.
- `scripts/quality/build_exact_artifacts.py` at the base commit plus
  `validate_exact_artifacts.py` on the manifest.
- At PR time: green `quality-integration` and `pr-validation` runs on 3.14
  (exact-green-head evidence).

## Runtime feedback

- RF-001: Operator actions expected: 0; CI executes the gates autonomously.
- RF-002: Evidence to record in the PR: workflow grep output, unittest counts on
  3.14.4, validator outputs, exact-artifact validation, CI run links.

## Risk profile

- Risk profile: NOT REQUIRED

Rationale: control-plane-only change (CI interpreter pins), fully reversible by
restoring the scalar, no production mutation surface, no deploy/ or
scripts/release/ paths touched, and the full suite is already proven green on
CPython 3.14.4 locally (649 tests, OK, 3 skipped) before merge. The change
cannot alter application behavior; it only shifts the interpreter that the
already-green suites run on.

## Test design

- TEST-001 | Covers: R-1,R-2,R-3 | Level: integration | Priority: P0 | Evidence: git diff shows exactly the 5 allowed files; grep shows 5x "3.14" and 0x "3.12" in the two workflows
- TEST-002 | Covers: R-4,R-5 | Level: unit | Priority: P0 | Evidence: full unittest suite on CPython 3.14.4 with -W error::ResourceWarning (observed: Ran 649 tests, OK, skipped=3)
- TEST-003 | Covers: R-3,R-5 | Level: integration | Priority: P0 | Evidence: validate_sdd.py, validate_repo.py, validate_contracts.py, validate_quality_contracts.py, validate_workflow_policy.py, py_compile, and exact-artifact build+validate all pass locally
- TEST-004 | Covers: R-1,R-2 | Level: end-to-end | Priority: P1 | Evidence: green quality-integration.yml (4 jobs) and pr-validation.yml runs on CPython 3.14 at exact-green-head; CI execution is the acceptance test per DEC-4

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE
