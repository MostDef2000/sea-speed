# Plan — Issue #579 canonical API dependency lock + gradual ruff/mypy extension

- Issue: #579
- Spec: specs/579-api-dependency-lock/spec.md
- Base: fd024d6 (branch fix/579-api-dependency-lock-gradual-lint)

## Architecture

Three cooperating pieces, mirroring the proven #392 worker-lock pattern on the
API side. (1) Input: `api/requirements-api.txt` pins exactly what the API
boundary, its HTTP integration tests and the CI tooling need — the three
carried-over CI tool pins (ruff==0.16.10, mypy==1.18.2, pyyaml==6.0.3) plus
the verified API runtime/test needs (fastapi: imported by every api/app
module; httpx: TestClient's transport in tests/test_api_http_integration.py;
python-multipart: required by the API's own Form/File/UploadFile routes;
uvicorn: the production API server behind the VPS `sea-speed-api` systemd
service). (2) Resolution: the operator-triggered resolver workflow's single
structurally-pinned `resolve` job compiles the input with
`uv pip compile --generate-hashes --python-version <input>` from default PyPI
and prepends the `# sea-speed-api-lock-v1` marker, mirroring the worker
resolver's shape within the same job (the #398-wave5 structural pin forbids a
second job). (3) Consumption + enforcement: quality-integration.yml installs the lock once
up front (replacing the three scattered inline pins), and
`scripts/quality/validate_api_dependency_lock.py` — stdlib-only, subprocess-
tested CLI — proves marker/coverage/hash integrity locally and can be wired
into any gate; security.yml pip-audits the pinned input. The gradual strict
tier rides the same PR: ruff.strict.toml and a mypy strict section hold only
the explicitly listed validator module to the stricter standard.

## Decisions

- **Pin exactly what is needed, verified, not assumed**: api/app/*.py imports
  only fastapi as a third-party package; tests/test_api_http_integration.py
  drives the real app through fastapi.testclient.TestClient, whose transport
  is httpx (no server process); uvicorn is included because the VPS
  `sea-speed-api` service runs api/app/main.py in direct uvicorn app-dir mode
  (specs/396-wave1/plan.md) — the canonical API input owns its server
  dependency even though tests never import it. Each choice is documented in
  the requirements header.
- **Carry the tool pins exactly**: ruff==0.16.10 and mypy==1.18.2 move from
  inline CI installs into the lock unchanged (the mypy 1.18.2 rationale stays
  documented in scripts/quality/mypy.ini), and pyyaml==6.0.3 replaces the
  "Install test-only YAML parser" step — one resolution, one audit surface.
- **uv 0.9.8 + --generate-hashes + marker**, same as the worker lock (#392):
  proven format, validator-parseable, and the marker makes a committed lock
  distinguishable from raw uv output.
- **Validator observes the CLI surface, not internals**: the RED tests
  execute the script via subprocess and assert exit codes + stderr, so the
  internal structure stays free to change; the validator is stdlib-only so it
  runs anywhere the battery runs.
- **Gradual strict tiers, never mass-enabled**: ruff.strict.toml and the mypy
  strict section start with exactly one module (the new validator). New
  modules opt in during review; the headers document the protocol so the
  tier cannot silently creep over the legacy tree.
- **Latest-at-resolution-time for the API packages**: fastapi==0.162.0,
  uvicorn==0.54.0, httpx==0.28.1, python-multipart==0.0.33 are the PyPI
  latest at resolution time
  (2026-11-03), pinned exactly like every other line so the validator's
  `name==version` contract holds for the whole input.

## Affected contours

- VPS — derived from the `api/**` path policy
  (data/contracts/change-control-policy-v1.json classifies
  api/requirements-api*.txt as VPS): the lock becomes the dependency input the
  VPS API service consumes on future deploys. This PR ships no deploy-path
  mutation, no api/app code change and no runtime behavior change; the first
  production consumption is the next routine VPS deploy after merge, through
  the existing deploy-vps transaction and its existing rollback.
- CONTROL_PLANE — quality-integration.yml, security.yml,
  resolve-runtime-lock.yml, the validator, ruff.strict.toml and mypy.ini are
  CI/control-plane only.
- Ubuntu worker/relay — NOT affected: deploy/worker/** and the worker lock
  are untouched.

## Validation

- RED-first: tests/test_api_dependency_lock.py (14 tests, test-protected)
  failed 14/14 on the base (observed) and must pass 14/14 on the delivered
  tree without edits.
- Full battery: `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p 'test_*.py'` — 0 failures, 0 errors (exact counts recorded in the
  completion gate).
- Lint/typing: base `ruff check --config scripts/quality/ruff.toml .` clean;
  strict `ruff check --config scripts/quality/ruff.strict.toml
  scripts/quality/validate_api_dependency_lock.py` clean; mypy strict module
  list including the validator clean.
- Validator: `python3 scripts/quality/validate_api_dependency_lock.py` exit 0
  on the real files.
- Install proof: clean venv (`uv venv --seed`; python3 -m venv lacks
  ensurepip on the delivery host — equivalent clean-venv semantics, pip
  present) `pip install -r api/requirements-api.lock.txt` succeeds with hash
  verification active.
- Policy/SDD: `python3 scripts/quality/validate_workflow_policy.py`,
  `python3 scripts/quality/validate_quality_contracts.py`,
  `python3 scripts/ci/validate_sdd.py` all exit 0.
- Reproducibility: second uv compile diff empty after marker/output-path
  normalization.

## Runtime feedback

- CI is the runtime for this change: a drifted/marker-less/hash-less lock
  fails the validator (exit 1) or the hash-verified install, both fail-closed
  before any test runs. The resolver workflow performs resolution only — no
  repository write, no secrets, no deploy logic. First production consumption
  (VPS API dependency resolution) happens on the next routine VPS deploy after
  merge through the unchanged deploy-vps transaction; any breakage surfaces
  there and rolls back by the existing previous-release mechanism, while the
  lock itself reverts by pinning the previous versions and re-resolving.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: the lock is compiled with --generate-hashes (308 sha256 digests), the validator rejects any zero-hash entry and any pin not covered by the lock, security.yml pip-audits the pinned input, and the install proof runs in a clean venv where pip enforces the digests | Validation: tests T-5/T-8 plus the observed clean-venv install and pip-audit wiring | Residual risk: a compromised upstream artifact whose digest was captured at resolution time from a tampered index remains outside local control (same exposure class as the #392 worker lock; accepted) | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: reproducibility proof (second compile byte-identical after marker/output-path normalization), exact `name==version` input pins only, marker check + coverage check in the validator, lock consumed by CI from the committed file rather than re-resolved | Validation: reproducibility diff evidence + validator failure-mode tests T-2..T-6 | Residual risk: a future uv major version could change lock formatting; re-resolution is operator-triggered and the diff is reviewable before commit | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the static job installs one resolved lock instead of three scattered inline pins; the lock is exercised locally (full battery + venv install) before merge; job timeout unchanged at 15 minutes | Validation: full battery + install timing observed in the completion gate | Residual risk: PyPI unavailability blocks CI installs as it does today for the inline pins (no new failure class) | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: validator CLI contract — exit 0 valid; exit 1 + one clear stderr line for missing/empty lock, wrong marker, uncovered pin name, version drift, zero-hash entry, malformed requirements line (T-1..T-7) | Level: unit | Priority: P0 | Evidence: tests/test_api_dependency_lock.py ApiDependencyLockValidatorTests (subprocess CLI, runtime fixtures under /tmp/opencode/579/)
- TEST-002 | Covers: real repo input + lock validate clean end-to-end (T-8) | Level: integration | Priority: P0 | Evidence: tests/test_api_dependency_lock.py::test_real_repo_files_exit_zero + observed validator exit 0
- TEST-003 | Covers: CI consumption wiring — lock install step, no inline tool pins, ruff strict step, mypy module list, pip-audit of the API input, resolver job with --generate-hashes + marker + artifact (T-9..T-14) | Level: integration | Priority: P0 | Evidence: tests/test_api_dependency_lock.py::ApiDependencyLockCiConsumptionTests (yaml.safe_load over the real workflows)
- TEST-004 | Covers: lock installability with hash verification in a clean environment | Level: integration | Priority: P1 | Evidence: uv venv --seed + pip install -r api/requirements-api.lock.txt observed success
- TEST-005 | Covers: no regression — full repository battery stays green with the lock-installed environment (fastapi/httpx present enables the HTTP integration tests) | Level: integration | Priority: P0 | Evidence: discover battery exact counts in the completion gate
- TEST-006 | Covers: strict tiers hold the validator module (ruff strict + mypy --strict) | Level: unit | Priority: P1 | Evidence: observed clean ruff/mypy outputs in the completion gate

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: none required — the admitted scope was implemented as specified;
  the RED suite turned GREEN without any test edit and no production learning,
  architecture pivot or material scope change surfaced during implementation.

## Deployment transaction audit

This change ships no deploy-path mutation: deploy/**, scripts/release/** and
deploy workflows are untouched, and the VPS API service consumes the new lock
only on a future routine deploy. The audit below covers the change's own
lifecycle plus the affected (unchanged) VPS deploy transaction stages that the
`api/**` contour classification binds this change to.

- TX-ADMISSION | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no merge; the PR is not admissible until the Change Contract matches the exact diff (VPS contour derived from api/requirements-api*.txt, Risk profile REQUIRED) | Retry: after correcting the PR body to match the exact diff, re-run admission | Rollback: not applicable — no runtime state exists at this stage | Evidence: PR Change Contract plus validate_change_contract.py observed pass on the PR head
- TX-PRE-MUTATION | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: CI red on the PR head (validator exit 1, hash-verified install failure, pip-audit finding or battery failure); no repository or runtime state is mutated | Retry: fix the input/lock/validator within the admitted scope and re-run CI | Rollback: not applicable — nothing was applied | Evidence: quality-integration and security workflow runs on the PR head
- TX-MUTATION | Stage: MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: not reachable for this change — the PR performs no deploy mutation; the future VPS deploy that consumes the lock runs the UNCHANGED deploy-vps transaction, which stages a candidate release only after its existing gates pass | Retry: not applicable to this change; the existing deploy transaction retries per its own contract | Rollback: the existing deploy-vps rollback (previous exact release) remains the only rollback path and is unchanged | Evidence: deploy-vps workflow contract unchanged in the diff (no deploy/** or deploy workflow files touched)
- TX-VERIFICATION | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: a future deploy consuming a broken lock would fail its existing verification stage (service health probes) with the previous release still active or restored by the existing transaction | Retry: per the existing deploy-vps verification contract | Rollback: existing deploy-vps rollback to the previous verified release | Evidence: existing deploy-vps verification steps (unchanged by this PR) plus the CI-side proof that the lock installs cleanly (venv evidence) | 
- TX-STATE-COMMIT | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: no state commit happens in this change; the repository commit itself is gated by exact-green-head CI before merge | Retry: re-run CI at the exact head | Rollback: git revert of the merge commit restores the previous dependency input | Evidence: exact-green-head Quality run on the merged main SHA
- TX-HOUSEKEEPING | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: resolver artifacts expire per their 30-day retention; no host or repository housekeeping is introduced | Retry: re-dispatch the resolver workflow | Rollback: not applicable — artifacts are ephemeral | Evidence: resolve-runtime-lock.yml artifact retention configuration
- TX-EVIDENCE | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: missing or inconsistent evidence blocks PR admission and merge | Retry: rebuild evidence at the exact head and re-run CI | Rollback: not applicable — evidence collection mutates nothing | Evidence: the completion-gate outputs in tasks.md plus the workflow runs at the exact head
- TX-ROLLBACK | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: if a post-merge VPS deploy consuming the new lock fails, the existing deploy-vps transaction restores the previous verified release; the lock itself reverts by committing the previous pins and re-resolving | Retry: operator re-runs the deploy after remediation per the existing rollback contract | Rollback: previous exact VPS release remains the declared rollback target; no new rollback mechanism is introduced | Evidence: existing deploy-vps rollback evidence path (unchanged) plus the previous lock recoverable from git history
