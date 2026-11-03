# Spec: #579 — Canonical hash-pinned API dependency lock + gradual ruff/mypy extension

- Issue: #579
- Spec: specs/579-api-dependency-lock/spec.md
- Plan: specs/579-api-dependency-lock/plan.md
- Tasks: specs/579-api-dependency-lock/tasks.md
- Base: fd024d6 (branch fix/579-api-dependency-lock-gradual-lint)
- Authorization: the #579 scope (api/requirements-api.txt + api/requirements-api.lock.txt +
  scripts/quality/validate_api_dependency_lock.py + scripts/quality/ruff.strict.toml +
  scripts/quality/mypy.ini strict section + quality-integration/security/resolve-runtime-lock
  workflow edits + this trio) admitted by the delivery orchestrator; the RED test module
  tests/test_api_dependency_lock.py (14 tests) pre-exists on the base and is test-protected.

## Product outcome

The API + test + CI-tooling dependency graph gets a single canonical, hash-pinned
dependency input. Today the API's runtime dependencies (fastapi, uvicorn), the HTTP
integration tests' transport (httpx) and the CI tooling pins (ruff, mypy, pyyaml) are
either undeclared or scattered as inline `pip install x==y` steps in
quality-integration.yml — nothing hash-verifies what CI actually installs, and the
worker runtime already has the hash-lock pattern (#392) while the API side has none.
After this change: `api/requirements-api.txt` is the pinned input (exact `name==version`
lines, documented rationale per pin), `api/requirements-api.lock.txt` is the
uv-compiled `--generate-hashes` lock carrying the `# sea-speed-api-lock-v1` marker,
`scripts/quality/validate_api_dependency_lock.py` proves marker/coverage/hash integrity
(exit 0/1 CLI), CI installs from the lock instead of inline pins, security.yml
pip-audits the pinned input, the operator-triggered resolver workflow gains
API-lock resolution steps in its single structurally-pinned `resolve` job,
and a gradual strict tier (ruff.strict.toml + a mypy strict section) starts
holding explicitly listed new modules to stricter lint/typing — never mass-enabled.

## User scenarios

- SC-1: a contributor adds or bumps a pin in `api/requirements-api.txt` — the
  resolver workflow (operator-triggered dispatch, default PyPI) compiles a fresh
  hash-locked artifact; the contributor commits input + lock together and the
  validator plus pip-audit gate the PR.
- SC-2: the static-contract-security CI job installs
  `api/requirements-api.lock.txt` once, before any tooling step — ruff, mypy and
  the test-time pyyaml all come from the hash-verified lock; a tampered or
  corrupted artifact fails the install closed instead of silently installing.
- SC-3: the lock drifts from the requirements input (name missing or version
  differs), loses its marker, or ships a hash-less entry — the validator exits 1
  with one clear stderr line, so drift cannot merge.
- SC-4: a reviewer lands a new small module — during review it is added to the
  ruff strict invocation list and given a `strict = True` mypy section, one
  module at a time; the legacy tree is never mass-enabled.
- SC-5: an operator re-resolves the lock via workflow dispatch — the resolve
  job prints the marker line and a hash-pin count and uploads
  `api-requirements-lock-txt` as an artifact, mirroring the worker resolver's
  operator experience.

## Requirements

- R-1: `api/requirements-api.txt` — canonical pinned input; every non-comment
  line is an exact `name==version` pin; header comments state the file's purpose
  and the per-pin rationale (ruff/mypy/pyyaml carried from the CI inline pins;
  fastapi = api/app imports; httpx = TestClient transport; uvicorn = production
  API server).
- R-2: `api/requirements-api.lock.txt` — compiled with uv 0.9.8
  (`uv pip compile --generate-hashes --python-version 3.14`), first line
  `# sea-speed-api-lock-v1`, reproducible (second compile byte-identical after
  marker/output-path normalization).
- R-3: `scripts/quality/validate_api_dependency_lock.py` — stdlib-only argparse
  CLI (`--requirements`, `--lock` with repo defaults), exit 0 valid, exit 1 with
  one clear stderr line for: missing/empty lock, wrong marker, uncovered pin
  (name absent or version differs), zero-hash lock entry, malformed
  requirements line; parses the uv continuation format and rejects option
  lines (and any other unrecognized line) fail-closed — pip would honor them.
- R-4: quality-integration.yml (static-contract-security) installs from the
  lock before any tooling step, drops the inline ruff/mypy/pyyaml pins, gains a
  ruff strict step over the validator, and lists the validator in the mypy
  invocation; everything else stays byte-identical.
- R-5: security.yml dependency-audit runs `pip-audit -r api/requirements-api.txt`
  after the worker audit.
- R-6: the resolver workflow's `resolve` job (structurally pinned as the
  workflow's only job by tests/test_ubuntu_worker_runtime_hash_lock.py) also
  compiles `api/requirements-api.txt` with `--generate-hashes
  --python-version` from the dispatch input, prepends the
  `# sea-speed-api-lock-v1` marker, prints a hash-pin-count summary and
  uploads the `api-requirements-lock-txt` artifact — from default PyPI, with
  no pytorch index.
- R-7: gradual strict tiers — `scripts/quality/ruff.strict.toml`
  (E9,F,W,I,B,UP; py314; fix=false) and a
  `[mypy-scripts.quality.validate_api_dependency_lock]` `strict = True` section
  apply ONLY to explicitly listed modules; the protocol (opt-in during review,
  never mass-enabled) is documented in the config headers.

## Acceptance criteria

- AC-001: `api/requirements-api.txt` exists, contains only comment lines, blank
  lines and exact `name==version` pins, and its header documents the file's
  purpose and each pin's rationale (verified need: api/app imports fastapi;
  tests/test_api_http_integration.py drives the app via TestClient→httpx;
  uvicorn is the VPS API server).
- AC-002: `api/requirements-api.lock.txt` exists, its first line is exactly
  `# sea-speed-api-lock-v1`, it was produced by
  `uv pip compile --generate-hashes --python-version 3.14` from the input, and
  `python3 scripts/quality/validate_api_dependency_lock.py` exits 0 on the real
  files (test T-8).
- AC-003: the validator CLI exits 0 on a valid fixture and exits 1 with a
  non-empty one-line stderr message for each failure mode: missing/empty lock,
  wrong first-line marker, pin name absent from lock, pin version mismatch,
  zero-hash lock entry, malformed requirements line (tests T-1..T-7).
- AC-004: lock reproducibility — a second
  `uv pip compile --generate-hashes` run to a scratch path is byte-identical
  to the committed lock after normalizing the prepended marker and the `-o`
  output path echoed in uv's header comment.
- AC-005: quality-integration.yml (static-contract-security) contains a step
  that pip-installs from `api/requirements-api.lock.txt`, contains no
  `pip install ruff==`/`mypy==`/`pyyaml==` inline pins, runs
  `ruff check --config scripts/quality/ruff.strict.toml` over the validator,
  and its mypy invocation lists the validator module (tests T-9..T-12).
- AC-006: security.yml contains a step running
  `pip-audit -r api/requirements-api.txt` (test T-13).
- AC-007: resolve-runtime-lock.yml contains a job that runs
  `uv pip compile --generate-hashes` over `api/requirements-api.txt`, prepends
  the `# sea-speed-api-lock-v1` marker and uploads the lock via
  upload-artifact (test T-14).
- AC-008: the strict tiers hold the validator module —
  `ruff check --config scripts/quality/ruff.strict.toml
  scripts/quality/validate_api_dependency_lock.py` and the mypy strict module
  list including the validator both pass clean — while the base-tier repo-wide
  ruff gate and the full test battery stay green.

## Runtime feedback

- No runtime code path changes in this change: api/app/**, deploy/** and
  worker/** are untouched. The VPS contour is affected only through the
  dependency input its API service consumes on FUTURE deploys — the deploy
  transaction itself is unchanged, and the first production consumption is the
  next routine VPS deploy after merge (existing deploy-vps transaction,
  existing rollback). Failure modes introduced are fail-closed by design: a
  hash mismatch fails `pip install` closed; a drifted or marker-less lock
  fails the validator (exit 1) and turns CI red before merge; the resolver is
  operator-triggered only and performs no repository write. If a resolved
  version proves broken at runtime, the pin in requirements-api.txt is
  reverted and the lock re-resolved — the previous lock remains the rollback
  input until then.

## NFR assessment

- NFR-001 | Area: supply-chain integrity | Target: 100% of locked packages carry at least one --hash=sha256 digest and CI installs run with pip hash verification active | Validation: validator zero-hash failure mode (T-5) plus a clean-venv `pip install -r api/requirements-api.lock.txt` proof | Evidence: completion-gate observed outputs (validator exit 0; venv install success) | Status: PASS
- NFR-002 | Area: reproducibility | Target: two independent uv compiles of the same input are byte-identical after marker/output-path normalization | Validation: second compile to a scratch path + diff | Evidence: completion-gate diff result (empty) | Status: PASS
- NFR-003 | Area: CI latency | Target: static-contract-security job keeps its 15-minute timeout; one lock install replaces three scattered inline installs | Validation: step inspection + local timed install from the lock | Evidence: workflow diff and venv install log in the completion gate | Status: PASS
- NFR-004 | Area: maintainability (gradual strict adoption) | Target: strict tier applies only to explicitly listed modules; zero strict-tier findings on the validator; base ruff.toml repo-wide gate unchanged and clean | Validation: ruff strict run over the validator module + base ruff run over the tree | Evidence: completion-gate ruff/mypy observed outputs | Status: PASS
