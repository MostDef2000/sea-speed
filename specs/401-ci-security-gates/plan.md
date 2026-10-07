# Plan: CI security gates (gitleaks + pip-audit)

- Specification: specs/401-ci-security-gates/spec.md

## Architecture

One new standalone workflow, `.github/workflows/security.yml` ("Security
gates"), with two jobs on ubuntu-latest, each `timeout-minutes: 10`:

- `secret-scan` — `actions/checkout` with `fetch-depth: 0` (gitleaks
  full-history scanning needs every commit; the shallow default would only
  scan the tip) and `persist-credentials: false` (the scanner never needs
  push credentials, so the token is not persisted); then a checksum-verified
  install of gitleaks 8.30.0 (download the canonical release tarball asset,
  `echo "<pinned sha256>  <asset name>" | sha256sum -c -` **before** any
  execution, extract, print version); then `gitleaks detect --source .
  --report-format sarif --report-path gitleaks-report.sarif --redact -v`;
  finally `actions/upload-artifact` uploads the SARIF report with
  `if: always()` so evidence survives a failing scan.
- `dependency-audit` — `actions/setup-python` on "3.14" (merge-facing CI
  interpreter per repo convention, matching quality-integration.yml and
  pr-validation.yml), `pip install pip-audit`, then
  `pip-audit -r deploy/worker/ubuntu/requirements-runtime.txt`.

Both jobs run on `ubuntu-latest`, share the top-level
`permissions: contents: read`, trigger on `pull_request`, `push` to main and
`workflow_dispatch`, and use the sibling-style concurrency block
(`security-${{ github.workflow }}-${{ github.ref }}`, cancel-in-progress).

Why actionless: the repository policy validator enforces a **closed action
allowlist** — exactly `{actions/checkout, actions/setup-python,
actions/setup-node, actions/upload-artifact}` pinned to full 40-hex SHAs —
over every `.github/workflows/*.y*ml`. Third-party security actions (gitleaks
action, pip-audit action) are not on the allowlist, so both scanners run as
plain `run:` steps. Download-to-shell pipes are forbidden by the same
validator, so the gitleaks binary is downloaded to a file and verified with
`sha256sum -c` against an in-repo digest pin before execution
(checksum-verify-before-execute); the only pipe used is
`echo <digest> | sha256sum -c -`, which pipes into a checksum verifier, not
a shell.

## Decisions

- DEC-1: Actionless design — verified against
  `scripts/quality/validate_workflow_policy.py` ALLOWED_ACTIONS before
  writing the workflow; every `uses:` is `actions/checkout@11d5960a326750d5838078e36cf38b85af677262`,
  `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065` or
  `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02` — the
  exact full SHAs already pinned in pr-validation.yml and
  quality-integration.yml (copied, never invented).
- DEC-2: gitleaks pinned to **v8.30.0** (current latest v8 tag), observed via
  `git ls-remote --tags https://github.com/gitleaks/gitleaks` with
  version-aware sorting (`sort -V`; note: lexicographic tail ordering
  underestimates — it initially suggested v8.9.0, which was corrected by
  re-observing with version sort before any publication).
- DEC-3: Checksum verification pins the observed tarball digest **inline in
  the workflow**: `79a3ab579b53f71efd634f3aaf7e04a0fa0cf206b7ed434638d1547a2470a66e`
  for `gitleaks_8.30.0_linux_x64.tar.gz`. Provenance: the canonical release
  manifest `gitleaks_8.30.0_checksums.txt` was fetched from the official
  release (the plain `checksums.txt` asset name does not exist — HTTP 404,
  curl probe; the manifest download via GET succeeded, HEAD returns 401),
  its `linux_x64` entry read, and then independently verified by downloading
  the tarball and hashing it (sha256 MATCH). Pinning the digest in-repo is
  stronger than runtime-manifest trust: the tarball and the manifest share
  the GitHub release distribution channel, so the in-repo observed digest
  breaks that symmetry. The tarball is saved under its canonical asset name
  so `sha256sum -c` resolves. A future version bump is a deliberate change
  that must re-observe and update the digest.
- DEC-4: pip-audit CLI is installed unpinned (`pip install pip-audit`) per
  the issue condition — a documented residual risk: a future pip-audit
  release could change rules/behavior. Compensating controls: the job fails
  closed on known vulnerabilities, and pinning remains possible later
  without changing the audit source.
- DEC-5: dependency-audit provisions CPython 3.14 — the merge-facing CI
  interpreter convention established by #391 (quality-integration.yml and
  pr-validation.yml both pin "3.14").
- DEC-6: Initial-state observation — on base 83e4fa6 gitleaks 8.30.0 scans
  the full history (1489 commits, ~8.08 MB) and reports **zero findings**
  (exit 0), so the gate starts green with no allowlist configuration and
  none is added (no `.gitleaks.toml` in this change). Any future finding
  fails the job closed by design, with the SARIF artifact as disposition
  evidence. Nothing is weakened to obtain green. (Provenance note: a 25-
  finding `generic-api-key` false-positive observation existed during
  development against the retired 8.9.0 ruleset — 40-hex commit SHAs quoted
  in historical `specs/**` prose; the shipped 8.30.0 ruleset no longer
  flags them, so no disposition or deferred work remains.)
- DEC-7: SARIF upload uses `if: always()` so a failing scan still keeps
  evidence; the artifact is named `gitleaks-report-${{ github.sha }}` with
  14-day retention, mirroring quality-integration.yml's upload style.
- DEC-8: `fetch-depth: 0` only in secret-scan; dependency-audit uses the
  shallow default because it only reads the pinned requirements file from
  the checkout, and `persist-credentials: false` on both checkouts.

## Affected contours

- CONTROL_PLANE only: `.github/workflows/security.yml` (new file in
  `.github/workflows/**`).
- `specs/401-ci-security-gates/` — SDD documentation contour
  (spec/plan/tasks trio), unclassified.
- No application code, no deploy/ files, no schemas, no tests, no scripts,
  no runtime hosts, no changes to any existing workflow or spec directory.

## Validation

- `python3 scripts/quality/validate_workflow_policy.py` — workflow policy
  validator over every workflow, including security.yml.
- `python3 scripts/ci/validate_sdd.py` (no --event) — SDD structure for all
  feature dirs including specs/401-ci-security-gates/.
- `python3 scripts/ci/validate_repo.py` — repository structure/secret rules.
- `python3 scripts/ci/validate_contracts.py` — canonical contract set.
- `python3 scripts/ci/validate_quality_contracts.py` — quality contracts,
  fixtures, rollout and accepted-risk state.
- `python3 -m unittest discover -s tests -q` — behavioral suite baseline
  (649 tests, OK, skipped=3) on CPython 3.14.
- Local supply-chain reproduction of the gitleaks install flow: fetch the
  canonical manifest, read the `linux_x64` entry, download the tarball and
  hash it independently → sha256 MATCH with the pinned digest; extract,
  `./gitleaks version` → 8.30.0; then a full-history detect over this base
  → zero findings, exit 0 (the documented initial state).
- `git diff --stat` — exactly the 4 allowed files.
- At PR time: "Security gates" workflow runs on the PR (both jobs
  exercised), green quality-integration/pr-validation at exact-green-head.

## Runtime feedback

- RF-001: Operator actions expected: 0; both gates run autonomously on
  pull_request, push to main and workflow_dispatch.
- RF-002: Evidence to record in the PR: CI run links ("Security gates" PR
  run and push-to-main run), the gitleaks SARIF artifact, and pip-audit
  output; local battery outputs for the validators and suite.

## Risk profile

- Risk profile: NOT REQUIRED

Rationale: Security impact NONE — the change is an additive detection gate;
nothing existing is weakened, bypassed or removed, and the workflow declares
top-level `permissions: contents: read` with credential persistence
disabled. Not destructive: it mutates nothing outside its job workspace and
is not wired into the deployment transaction chain (the autonomous router
triggers on quality-integration only). No other high-risk aspect: no
production mutation surface, no deploy/ or scripts/release/ paths, no
application behavior change. Impact classified CONTROL_PLANE
(`.github/workflows/**` plus an SDD documentation contour). The secret-scan
gate is green on current main history (zero findings, DEC-6) and remains
fail-closed for any future finding — that is a detection property of the
gate, not a delivery risk introduced by this change.

## Test design

- TEST-001 | Covers: R-3 | Level: integration | Priority: P0 | Evidence: python3 scripts/quality/validate_workflow_policy.py passes with security.yml present (AC-001; validator enforces top-level permissions, closed action allowlist with full 40-hex SHAs, no pull_request_target, no download-to-shell pipes)
- TEST-002 | Covers: R-3,R-6 | Level: integration | Priority: P0 | Evidence: python3 scripts/ci/validate_sdd.py, validate_repo.py, validate_contracts.py, validate_quality_contracts.py all pass (AC-002..AC-005)
- TEST-003 | Covers: R-6 | Level: unit | Priority: P0 | Evidence: python3 -m unittest discover -s tests -q on CPython 3.14 shows the documented baseline (Ran 649 tests, OK, skipped=3) (AC-006)
- TEST-004 | Covers: R-1 | Level: end-to-end | Priority: P0 | Evidence: local reproduction on base 83e4fa6 (tarball hashed independently → sha256 MATCH with the pinned digest, ./gitleaks version → 8.30.0, full-history detect → zero findings, exit 0, SARIF written) plus the post-merge CI run of the secret-scan job (R-1; initial state per DEC-6)
- TEST-005 | Covers: R-2 | Level: end-to-end | Priority: P1 | Evidence: post-merge CI run of dependency-audit — setup-python 3.14, pip install pip-audit, pip-audit over deploy/worker/ubuntu/requirements-runtime.txt (R-2)
- TEST-006 | Covers: R-4,R-5 | Level: integration | Priority: P2 | Evidence: repo-wide search shows zero Dockerfile* files and no api requirements/lock/pyproject; written justifications in spec.md R-4/R-5

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE
