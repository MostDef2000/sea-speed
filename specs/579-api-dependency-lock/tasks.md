# Tasks — Issue #579 canonical API dependency lock + gradual ruff/mypy extension

- Issue: #579
- Spec: specs/579-api-dependency-lock/spec.md
- Plan: specs/579-api-dependency-lock/plan.md
- Base: fd024d6 (branch fix/579-api-dependency-lock-gradual-lint)

## Delivery tasks

- [x] T-1 `api/requirements-api.txt` — canonical pinned input: exact
  `name==version` pins only (ruff==0.16.10, mypy==1.18.2, pyyaml==6.0.3
  carried from the CI inline pins; fastapi==0.162.0, uvicorn==0.54.0,
  httpx==0.28.1, python-multipart==0.0.33 verified-latest at resolution time
  2026-11-03), header
  comments documenting the file's purpose and each pin's verified need
  (api/app imports fastapi; TestClient needs httpx; uvicorn is the VPS API
  server).
- [x] T-2 `api/requirements-api.lock.txt` — compiled with uv==0.9.8
  (`uv pip compile --generate-hashes --python-version 3.14`), marker
  `# sea-speed-api-lock-v1` prepended (same pattern as the worker resolver),
  308 sha256 hash pins; reproducibility proven by a second compile diffing
  empty after marker/output-path normalization.
- [x] T-3 `scripts/quality/validate_api_dependency_lock.py` — stdlib-only
  argparse CLI (`main() -> int` + `raise SystemExit(main())`), uv-format lock
  parsing (continuation lines, `# via` provenance; option lines and any
  unrecognized line rejected fail-closed rather than silently skipped),
  PEP 503 name normalization, the six fail-closed modes, repo
  convention exit codes.
- [x] T-4 `scripts/quality/ruff.strict.toml` — strict tier
  (E9,F,W,I,B,UP; py314; fix=false) with the gradual-protocol header (opt-in
  per module during review, never mass-enabled).
- [x] T-5 `scripts/quality/mypy.ini` — appended
  `[mypy-scripts.quality.validate_api_dependency_lock]` / `strict = True`;
  existing content (including the mypy 1.18.2 rationale) untouched.
- [x] T-6 `.github/workflows/quality-integration.yml` — lock install step
  after the setup steps; ruff step drops its inline pin; new ruff strict step
  over the validator; mypy step drops its inline pin and lists the validator;
  "Install test-only YAML parser" step removed; all other steps byte-identical.
- [x] T-7 `.github/workflows/security.yml` — "Audit pinned API requirements"
  step (`pip-audit -r api/requirements-api.txt`) after the worker audit.
- [x] T-7b `.github/workflows/resolve-runtime-lock.yml` — the single
  structurally-pinned `resolve` job gains the API-lock steps: compile
  `api/requirements-api.txt` with `--generate-hashes --python-version` from
  the dispatch input (default PyPI, no pytorch index), prepend the
  `# sea-speed-api-lock-v1` marker, hash-pin-count summary, upload artifact
  `api-requirements-lock-txt`. (The work-order sketch said "second job";
  the test-protected #398-wave5 structural pin requires
  `jobs == ["resolve"]` exactly, so the steps live inside the existing job —
  same trigger and concurrency semantics either way.)
- [x] T-8 SDD trio (this directory) conforming to scripts/ci/validate_sdd.py.
- [x] T-9 Evidence battery — all ten work-order evidence items observed and
  recorded in the completion gate below.

## Completion gate

- Focused RED suite `python3 -W error::ResourceWarning -m unittest
  tests.test_api_dependency_lock -v`: OBSERVED "Ran 14 tests ... OK" (14/14,
  zero skips — pyyaml present).
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p 'test_*.py'` (run on the lock-installed clean venv — CI parity
  after this change): OBSERVED "Ran 1275 tests in 77.710s / OK
  (skipped=2)" — 0 failures, 0 errors; the 2 skips are pre-existing
  environment/code-state conditionals (systemd-analyze unavailable on the
  delivery host; main.py no longer defines write_json_file), unrelated to
  this change. The 15 #582 HTTP integration tests newly RUN in this
  lock-installed environment (they error at setUpClass without
  python-multipart — the reason that pin is in the lock input).
- ruff base `ruff check --config scripts/quality/ruff.toml .`: OBSERVED "All
  checks passed!" (exit 0).
- ruff strict `ruff check --config scripts/quality/ruff.strict.toml
  scripts/quality/validate_api_dependency_lock.py`: OBSERVED "All checks
  passed!" (exit 0).
- mypy strict list incl. validator: OBSERVED "Success: no issues found in 6
  source files" (exit 0).
- Validator on real files: OBSERVED "API dependency lock valid:
  api/requirements-api.lock.txt covers api/requirements-api.txt
  (# sea-speed-api-lock-v1)" (exit 0).
- Lock install proof (clean venv; `uv venv --seed` because python3 -m venv
  lacks ensurepip on the delivery host — equivalent clean-venv semantics with
  pip present): OBSERVED "Successfully installed ... fastapi-0.162.0 ...
  mypy-1.18.2 ... python-multipart-0.0.33 ... pyyaml-6.0.3 ... ruff-0.16.10
  ... uvicorn-0.54.0" (exit 0, pip hash verification active).
- `python3 scripts/quality/validate_workflow_policy.py`: OBSERVED "Workflow
  policy valid: protected public main -> exact quality -> standing policy ->
  restricted VPS/Ubuntu zero-touch execution" (exit 0).
- `python3 scripts/quality/validate_quality_contracts.py`: OBSERVED "Quality
  contracts valid: 7 contracts, 6 fixtures" (exit 0).
- `python3 scripts/ci/validate_sdd.py`: OBSERVED "Sea Speed SDD validation
  passed" (exit 0; also validate_repo.py "Tracked files checked: 842" and
  validate_contracts.py "Canonical files checked: 66" both exit 0).
- Lock reproducibility: OBSERVED second compile byte-identical after marker +
  `-o` output-path normalization (diff empty).
- `git status --porcelain`: OBSERVED only the admitted paths plus the
  pre-existing untracked tests/test_api_dependency_lock.py.

## Requirements traceability

- AC-001 | Task: T-1 | Evidence: api/requirements-api.txt content (exact pins + rationale header); T-8 prerequisite | Coverage: COVERED
- AC-002 | Task: T-2, T-3 | Evidence: tests/test_api_dependency_lock.py::test_real_repo_files_exit_zero + observed validator exit 0 on the real files | Coverage: COVERED
- AC-003 | Task: T-3 | Evidence: tests/test_api_dependency_lock.py::ApiDependencyLockValidatorTests (T-1..T-7) observed OK | Coverage: COVERED
- AC-004 | Task: T-2 | Evidence: second uv compile diff empty after marker/output-path normalization (observed) | Coverage: COVERED
- AC-005 | Task: T-6 | Evidence: tests/test_api_dependency_lock.py T-9..T-12 observed OK against the edited quality-integration.yml | Coverage: COVERED
- AC-006 | Task: T-7 | Evidence: tests/test_api_dependency_lock.py::test_security_pip_audits_api_requirements observed OK | Coverage: COVERED
- AC-007 | Task: T-7b | Evidence: tests/test_api_dependency_lock.py::test_resolve_runtime_lock_has_api_lock_job observed OK | Coverage: COVERED
- AC-008 | Task: T-4, T-5, T-9 | Evidence: observed clean ruff strict + mypy strict outputs; base ruff gate clean; full battery green | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (api/requirements-api.txt + api/requirements-api.lock.txt + scripts/quality/validate_api_dependency_lock.py + scripts/quality/ruff.strict.toml + scripts/quality/mypy.ini + 3 workflow files + this trio; tests/** untouched)
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (no deploy in this change; VPS contour consumes the lock on a future routine deploy through the unchanged deploy-vps transaction)
- [ ] Runtime acceptance resolved (CI is the runtime for this change; first production consumption is the next routine VPS deploy after merge)
- [x] Deferred work recorded (strict tier currently covers only the validator module by design — the gradual protocol adds modules during review; no other deferred work)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
