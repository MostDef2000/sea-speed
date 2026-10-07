# Tasks: CI security gates (gitleaks + pip-audit)

- Specification: specs/401-ci-security-gates/spec.md

## Delivery tasks

- T-401-001: Create the workflow skeleton in `.github/workflows/security.yml`:
  name "Security gates"; triggers `pull_request:`, `push:` (branches: main),
  `workflow_dispatch:`; top-level `permissions: contents: read`; concurrency
  block mirroring sibling style; two `ubuntu-latest` jobs with
  `timeout-minutes: 10` (implements R-3)
- T-401-002: Implement the `secret-scan` job: `actions/checkout` pinned to
  the sibling SHA with `fetch-depth: 0` and `persist-credentials: false`;
  gitleaks 8.30.0 install with checksum verification before execution
  (download the canonical release tarball asset, verify against the inline
  sha256 pin observed from the official release manifest with
  `echo <digest> | sha256sum -c -`, extract, `./gitleaks version`; no
  download-to-shell pipes); full-history
  `gitleaks detect` with SARIF output and `--redact`; `actions/upload-artifact`
  pinned to the sibling SHA uploading `gitleaks-report.sarif` with
  `if: always()` (implements R-1)
- T-401-003: Implement the `dependency-audit` job: `actions/setup-python`
  pinned to the sibling SHA with `python-version: "3.14"`; `pip install
  pip-audit`; `pip-audit -r deploy/worker/ubuntu/requirements-runtime.txt`
  (implements R-2)
- T-401-004: Write the SDD trio under `specs/401-ci-security-gates/` with
  NFR assessment, Risk profile NOT REQUIRED, test design, correct-course
  check, requirements traceability and Definition of Done; document R-4
  (trivy N/A: zero Dockerfiles, compose images are upstream Authentik
  infrastructure) and R-5 (api dependency surface N/A: no api
  requirements/lock; audit source is requirements-runtime.txt) with written
  justifications (implements R-4, R-5)
- T-401-005: Run the full local battery — workflow-policy, SDD, repo,
  contract and quality-contract validators plus the unittest suite on
  CPython 3.14 — and reproduce the gitleaks install/scan flow locally
  (digest verification, version probe, zero-finding baseline detect
  observation); verify scope isolation with `git diff --stat` (implements
  R-3, R-6)
- T-401-006: Open the PR with the Change Contract, record "Security gates"
  CI evidence (run links, SARIF artifact, pip-audit output), reach
  exact-green-head CI and merge; close out the Definition of Done

## Completion gate

- [ ] T-401-001
- [ ] T-401-002
- [ ] T-401-003
- [ ] T-401-004
- [ ] T-401-005
- [ ] T-401-006

## Deferred work

- None. The full-history gitleaks 8.30.0 scan of current main (base 83e4fa6,
  1489 commits) reports zero findings, so no finding disposition, allowlist
  configuration or history-hygiene follow-up is required; the gate remains
  fail-closed for any future finding (plan.md DEC-6, spec.md RF-003).

## Requirements traceability

- AC-001 | Task: T-401-001,T-401-002,T-401-003 | Evidence: python3 scripts/quality/validate_workflow_policy.py passes with security.yml present — top-level permissions contents: read, allowlisted actions pinned to full 40-hex SHAs, no pull_request_target, no download-to-shell pipes (R-3) | Coverage: COVERED
- AC-002 | Task: T-401-004 | Evidence: python3 scripts/ci/validate_sdd.py passes for specs/401-ci-security-gates/ — structure, Issue linkage, NFR, risk, test design, traceability, DoD | Coverage: COVERED
- AC-003 | Task: T-401-005 | Evidence: python3 scripts/ci/validate_repo.py passes with the additive scope present — required paths, naming, secret-pattern and structure rules intact | Coverage: COVERED
- AC-004 | Task: T-401-005 | Evidence: python3 scripts/ci/validate_contracts.py passes — canonical contract set and documentation links intact | Coverage: COVERED
- AC-005 | Task: T-401-005 | Evidence: python3 scripts/ci/validate_quality_contracts.py passes — quality contracts, fixtures, rollout and accepted-risk state intact | Coverage: COVERED
- AC-006 | Task: T-401-005 | Evidence: python3 -m unittest discover -s tests -q on CPython 3.14 — Ran 649 tests, OK, skipped=3 (baseline unchanged) | Coverage: COVERED
- R-1 | Task: T-401-002 | Evidence: secret-scan job in security.yml — digest-verified gitleaks 8.30.0, fetch-depth 0 full-history detect, SARIF upload if: always(); local reproduction evidence in plan.md TEST-004 | Coverage: COVERED
- R-2 | Task: T-401-003 | Evidence: dependency-audit job in security.yml — setup-python 3.14, pip-audit over deploy/worker/ubuntu/requirements-runtime.txt | Coverage: COVERED
- R-3 | Task: T-401-001 | Evidence: actionless design verified against the closed action allowlist; validate_workflow_policy.py green (AC-001) | Coverage: COVERED
- R-4 | Task: T-401-004 | Evidence: written justification in spec.md R-4 — zero Dockerfiles repo-wide; compose images are upstream Authentik infrastructure, not repo-built | Coverage: COVERED
- R-5 | Task: T-401-004 | Evidence: written justification in spec.md R-5 — no api requirements/lock/pyproject in-repo; audit source is requirements-runtime.txt per the issue condition | Coverage: COVERED
- R-6 | Task: T-401-005 | Evidence: git diff shows exactly the 4 allowed files; no existing workflow, validator, test or deploy path modified | Coverage: COVERED

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [x] Required CI green — auto-synced on merge to main (886909f7)
- [x] Exact-green-head merge complete — auto-synced on merge to main (886909f7)
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [ ] Deferred work recorded
- [ ] Risks resolved or explicitly accepted
- [ ] Waivers resolved or current
