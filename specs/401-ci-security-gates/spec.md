# Spec: CI security gates (gitleaks + pip-audit)

- Issue: #401
- Specification: specs/401-ci-security-gates/spec.md

## Product outcome

A standalone CI security gate — `.github/workflows/security.yml`, named
"Security gates" — runs on every pull request and every push to main (plus
manual dispatch) and provides two autonomous detection gates:

1. full-history secret scanning with a checksum-verified pinned gitleaks
   8.30.0 binary, and
2. a dependency vulnerability audit of the pinned worker runtime requirements
   (`deploy/worker/ubuntu/requirements-runtime.txt`) with pip-audit on
   CPython 3.14.

The gate is strictly additive: it is not wired into the autonomous deployment
chain (the router triggers on `quality-integration` success only), it
introduces no new repository permissions beyond the top-level
`permissions: contents: read`, and it weakens no existing gate. Scanner
findings or known-vulnerable pins fail the corresponding job and leave
evidence (SARIF artifact, pip-audit output) for deliberate remediation.

## User scenarios

- US-1: A contributor opens a PR or pushes to main; the "Security gates"
  workflow runs both jobs autonomously with zero operator actions, and any
  failure is visible as a failing check on the PR/commit.
- US-2: A secret-shaped string exists in the repository history; the
  gitleaks job fails with verbose finding output and uploads a SARIF report
  artifact (`gitleaks-report-<sha>`, uploaded with `if: always()` so failed
  scans keep evidence) that names file, rule and commit for disposition.
- US-3: A pinned worker runtime dependency gains a known vulnerability; the
  pip-audit job exits nonzero and its output names the package, installed
  version and advisory, so the pin can be remediated deliberately.
- US-4: A maintainer reviews the PR; the gate design is verifiable from the
  workflow source itself: allowlisted actions pinned to full 40-hex SHAs,
  checksum-verified binary install, no download-to-shell pipes.

## Requirements

- R-1: The `secret-scan` job checks out full history (`fetch-depth: 0`,
  `persist-credentials: false`), installs gitleaks **8.30.0** from the
  official GitHub release (canonical tarball asset verified against an
  inline sha256 pin observed from the official release checksums manifest
  with `sha256sum -c` before execution), and runs
  `gitleaks detect --source . --report-format sarif --report-path
  gitleaks-report.sarif --redact -v` — nonzero exit on findings fails the
  job; the SARIF report is uploaded via `actions/upload-artifact` with
  `if: always()`.
- R-2: The `dependency-audit` job provisions CPython **3.14** (merge-facing
  CI interpreter per repo convention), installs pip-audit, and runs
  `pip-audit -r deploy/worker/ubuntu/requirements-runtime.txt` — the
  documented audit source (7 pinned entries: ultralytics 8.4.117,
  lap 0.5.13, opencv-python 5.0.0.93, opencv-python-headless 5.0.0.93,
  numpy 2.4.4, requests 2.34.2, python-dotenv 1.2.2); nonzero exit on known
  vulnerabilities fails the job.
- R-3: The workflow must pass the repository workflow-policy validator
  (`scripts/quality/validate_workflow_policy.py`): explicit top-level
  `permissions:` block (`contents: read`), closed action allowlist
  (`actions/checkout`, `actions/setup-python`, `actions/upload-artifact`
  only, each pinned to a full 40-hex SHA copied from the sibling workflows —
  never invented), no `pull_request_target`, no `permissions: write-all`, no
  curl/wget-piped-into-shell (the design is actionless: third-party security
  actions are not on the allowlist, so gitleaks/pip-audit run as plain
  `run:` steps), and no heredocs.
- R-4: Trivy container image scanning is **not applicable**, with written
  justification: there are zero Dockerfiles anywhere in the repository;
  the only compose files (`deploy/worker/ubuntu/authentik/compose.yml`,
  `deploy/vps/authentik/compose.yml`) reference upstream Authentik
  infrastructure images that are built and published upstream, not built
  from this repository, so there is no repo-built image surface to scan.
- R-5: A dedicated api dependency audit surface is **not applicable**, with
  written justification: the repository contains no api requirements file,
  lock file or pyproject dependency declaration (`api/` holds application
  code only); the worker runtime requirements file is the single audited
  dependency surface, per the issue condition.
- R-6: Scope isolation: the change adds exactly
  `.github/workflows/security.yml` and `specs/401-ci-security-gates/`
  (spec/plan/tasks) and modifies no existing workflow, validator, test,
  deploy path or spec directory.

## Acceptance criteria

- AC-001: The workflow-policy validator passes with `.github/workflows/security.yml`
  present — proving R-3 (explicit top-level `permissions: contents: read`,
  allowlisted actions pinned to full 40-hex SHAs, no pull_request_target,
  no write-all, no download-to-shell pipes, no heredocs).
  Validation: `python3 scripts/quality/validate_workflow_policy.py`.
- AC-002: The SDD validator passes for `specs/401-ci-security-gates/` —
  spec/plan/tasks structure, `- Issue: #401` linkage, NFR assessment, risk
  profile, test design, correct-course check, traceability and Definition of
  Done all valid.
  Validation: `python3 scripts/ci/validate_sdd.py`.
- AC-003: The repository validator passes — proving the additive change
  keeps every required path, naming, secret-pattern and structure rule
  intact.
  Validation: `python3 scripts/ci/validate_repo.py`.
- AC-004: The contract validator passes — canonical contract set and
  documentation links intact.
  Validation: `python3 scripts/ci/validate_contracts.py`.
- AC-005: The quality-contract validator passes — versioned quality
  contracts, fixtures, rollout and accepted-risk state untouched.
  Validation: `python3 scripts/ci/validate_quality_contracts.py`.
- AC-006: The full behavioral suite holds its documented baseline on
  CPython 3.14 — 649 tests, OK, 3 skipped — proving the additive gate
  causes no regression.
  Validation: `python3 -m unittest discover -s tests -q`.

## Runtime feedback

- RF-001: Operator actions expected: 0; both jobs execute autonomously on
  PR, push to main and manual dispatch.
- RF-002: Evidence recorded in the PR: CI run links (PR-triggered and
  push-to-main runs of "Security gates"), the gitleaks SARIF artifact,
  and pip-audit output.
- RF-003: Known initial state (observed on base 83e4fa6): gitleaks 8.30.0
  scans the full history (1489 commits, ~8.08 MB) and reports **zero
  findings** (exit 0) — no allowlist configuration is added and none is
  needed. Any future finding fails the job closed by design, with the SARIF
  artifact kept as disposition evidence. (Provenance note: an earlier
  observation with the retired gitleaks 8.9.0 ruleset reported 25
  `generic-api-key` false positives on 40-hex commit SHAs quoted in
  historical `specs/**` prose; the shipped 8.30.0 ruleset no longer flags
  them, so no disposition remains.)
- RF-004: The gate is standalone: `deploy-runtime-autonomous.yml` routes on
  `quality-integration` runs only, so a red "Security gates" run surfaces as
  evidence without altering the deployment transaction chain.

## NFR assessment

- NFR-SECURITY | Area: Security | Target: Security impact NONE — strictly additive detection gate; no permission widening (top-level contents: read only), no secrets introduced, no existing gate weakened, bypassed or removed | Validation: scripts/quality/validate_workflow_policy.py plus diff review of the single new workflow file | Evidence: validator output and PR files-changed list recorded in the PR | Status: PASS
- NFR-SUPPLY-CHAIN | Area: supply chain | Target: gitleaks binary pinned to release tag v8.30.0 and verified against an inline sha256 pin observed from the official release checksums manifest before first execution; actions pinned to full 40-hex SHAs copied from sibling workflows | Validation: sha256sum -c step precedes binary execution in the workflow; local reproduction of the install flow on base 83e4fa6 (independent download hashed to the pinned digest) | Evidence: local verification output (sha256 MATCH; ./gitleaks version → 8.30.0; full-history detect → zero findings) recorded in the PR | Status: PASS
- NFR-SCOPE | Area: maintainability | Target: diff limited to the 4 allowed files (1 workflow + 3 SDD artifacts); no existing workflow, validator, test or deploy path touched | Validation: git diff --stat review | Evidence: PR files-changed list | Status: PASS
