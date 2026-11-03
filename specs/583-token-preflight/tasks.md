# Tasks — Issue #583 repo-owned token pre-flight probe

- Issue: #583
- Spec: specs/583-token-preflight/spec.md
- Plan: specs/583-token-preflight/plan.md
- Base: de868bb (branch fix/579-api-dependency-lock-gradual-lint, content-identical to origin/main)

## Delivery tasks

- [x] T-1 `data/contracts/token-inventory-v1.json` — the three contracted
  token identities (worker quality-read classic/no-expiry/review 2027-04-14
  on-box pointer; opencode-connector classic dated 2026-12-31; SYNC_PR_TOKEN
  fine-grained unknown expiry, probe none per the #558 REST-401-vs-push
  evidence), pointer-only credential references, nine contracted keys each.
- [x] T-2 `scripts/quality/validate_token_preflight.py` — stdlib-only
  validator: `--inventory`/`--today`/`--probe` CLI (`main(argv=None) -> int`
  + `raise SystemExit(main())`), `WARNING_DAYS = 21`, duplicate-JSON-key and
  duplicate-name rejection, full schema cross-field rules, credential-shape
  rejection naming index+field without echoing content, date evaluation
  (EXPIRED / EXPIRY-DUE / REVIEW-DUE / UNKNOWN-EXPIRY / OK), probe mode with
  MISSING-CREDENTIAL / INVALID-CREDENTIAL zero-request guards, Bearer /zen
  fetch via a no-redirect opener (10s timeout, fixed User-Agent, closed
  responses), 401/403 no-retry, 5xx/network retry 3 attempts (1s+2s),
  sanitized one-line findings (errors to stderr), exact final PASS/FAIL line,
  GITHUB_STEP_SUMMARY section on PASS and FAIL with SUMMARY-WRITE-FAILED
  fail-closed, module seams (`load_inventory`, `evaluate_dates`,
  `fetch_status`, `probe_token`, `main`).
- [x] T-3 `.github/workflows/token-preflight.yml` — weekly cron
  `17 9 * * 2` + workflow_dispatch, `permissions: contents: read`, single
  main-guarded job (ubuntu-latest, timeout 5), pinned checkout with
  persist-credentials: false, pinned setup-python 3.14, probe run command,
  zero secrets references.
- [x] T-3b `.github/workflows/quality-integration.yml` — offline step
  "Validate token inventory and dates" between "Validate repository and
  canonical contracts" and "Validate JSON and Python syntax"; ruff strict and
  mypy invocations list the new validator; nothing else altered.
- [x] T-4 `scripts/quality/mypy.ini` — appended
  `[mypy-scripts.quality.validate_token_preflight]` / `strict = True`;
  existing content untouched.
- [x] T-5 SDD trio (this directory) conforming to scripts/ci/validate_sdd.py.
- [x] T-6 `docs/operations/TOKEN_PREFLIGHT.md` — runbook: scope/inventory and
  coverage matrix, schedule + manual execution, alarm ownership, notification
  acceptance, marker interpretation (incl. UNKNOWN-EXPIRY and the #558
  REST-401-vs-push discrepancy), remediation, limits/dead-man risk, rollback,
  api-zen activation path.
- [x] T-7 Evidence battery — all work-order evidence items observed and
  recorded in the completion gate below.

## Completion gate

- RED evidence: `/tmp/opencode/583/red-evidence.txt` — OBSERVED "Ran 46
  tests ... FAILED (failures=12, errors=33)" on the base (validator,
  inventory, workflow, trio and runbook all absent).
- Focused suite `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p 'test_token_preflight.py' -v`: OBSERVED "Ran 56 tests in ...s /
  OK" (56/56, zero skips — pyyaml present so the structural tests run; 10
  date-matrix/aggregation/stream-routing tests were added after the peer
  review, raising the suite from the originally recorded 46).
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p 'test_*.py'`: OBSERVED "Ran 1331 tests in ...s / OK (skipped=17)"
  — 0 failures, 0 errors; the 17 skips are pre-existing environment
  conditionals on the delivery host, and the two "unexpected .opencode path"
  stderr lines are the deliberate negative-path output of
  test_delivery_todo_contract (validate_paths rejection fixtures), not
  failures.
- ruff base `ruff check --config scripts/quality/ruff.toml .`: OBSERVED "All
  checks passed!" (exit 0).
- ruff strict `ruff check --config scripts/quality/ruff.strict.toml
  scripts/quality/validate_api_dependency_lock.py
  scripts/quality/validate_token_preflight.py`: OBSERVED "All checks passed!"
  (exit 0).
- mypy strict (mypy 1.18.2 installed to a scratch target, matching the CI
  pin): OBSERVED "Success: no issues found in 1 source file" (exit 0) for
  `python3 -m mypy --config-file scripts/quality/mypy.ini
  scripts/quality/validate_token_preflight.py`.
- Offline validator on the committed inventory: OBSERVED "OK:
  sea-speed-worker-quality-read no expiry; review 2027-04-14" /
  "OK: sea-speed-opencode-connector expiry 2026-12-31" / "UNKNOWN-EXPIRY:
  SYNC_PR_TOKEN expiry unknown; owner lookup pending (non-failing)" /
  "TOKEN-PREFLIGHT PASS" (exit 0).
- `python3 scripts/quality/validate_workflow_policy.py`: OBSERVED "Workflow
  policy valid: protected public main -> exact quality -> standing policy ->
  restricted VPS/Ubuntu zero-touch execution" (exit 0).
- `python3 scripts/ci/validate_repo.py`: OBSERVED "Sea Speed repository
  validation passed / Tracked files checked: 850" (exit 0).
- `python3 scripts/ci/validate_contracts.py`: OBSERVED "Sea Speed contract
  validation passed / Canonical files checked: 66 / Resumable delivery
  entrypoints checked: 9" (exit 0).
- `python3 scripts/quality/validate_quality_contracts.py`: OBSERVED "Quality
  contracts valid: 7 contracts, 6 fixtures" (exit 0).
- `python3 scripts/ci/validate_sdd.py`: OBSERVED "Sea Speed SDD validation
  passed" (exit 0).
- `git status --short`: OBSERVED only the admitted paths plus the
  pre-existing untracked tests/test_token_preflight.py.

## Requirements traceability

- AC-001 | Task: T-1 | Evidence: tests/test_token_preflight.py TokenPreflightInventoryTests observed OK against data/contracts/token-inventory-v1.json | Coverage: COVERED
- AC-002 | Task: T-2 | Evidence: tests/test_token_preflight.py TokenPreflightValidatorOfflineSubprocessTests observed OK (exit codes + exact markers) | Coverage: COVERED
- AC-003 | Task: T-2 | Evidence: tests/test_token_preflight.py::test_offline_never_calls_fetch_status_or_reads_credential_env observed OK | Coverage: COVERED
- AC-004 | Task: T-2 | Evidence: tests/test_token_preflight.py TokenPreflightProbeUnitTests observed OK (status mapping, retry sleeps, zero-request credential failures, leak assertions) | Coverage: COVERED
- AC-005 | Task: T-2 | Evidence: tests/test_token_preflight.py TokenPreflightSummaryUnitTests observed OK | Coverage: COVERED
- AC-006 | Task: T-2 | Evidence: tests/test_token_preflight.py TokenPreflightTransportTests observed OK (patched opener, zero network) | Coverage: COVERED
- AC-007 | Task: T-3 | Evidence: tests/test_token_preflight.py TokenPreflightWorkflowTests observed OK against .github/workflows/token-preflight.yml | Coverage: COVERED
- AC-008 | Task: T-3b | Evidence: tests/test_token_preflight.py TokenPreflightQualityIntegrationTests observed OK against the edited quality-integration.yml | Coverage: COVERED
- AC-009 | Task: T-4 | Evidence: tests/test_token_preflight.py::TokenPreflightMypyTests observed OK + mypy strict run clean | Coverage: COVERED
- AC-010 | Task: T-5, T-6, T-7 | Evidence: tests/test_token_preflight.py TokenPreflightSddTests + TokenPreflightWorkflowPolicyTests observed OK; validate_sdd.py exit 0 | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (data/contracts/token-inventory-v1.json + scripts/quality/validate_token_preflight.py + .github/workflows/token-preflight.yml + quality-integration.yml + scripts/quality/mypy.ini + this trio + docs/operations/TOKEN_PREFLIGHT.md; tests/** untouched)
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (no deploy in this change; CONTROL_PLANE contour only)
- [ ] Runtime acceptance resolved (CI is the runtime for this change; the first scheduled probe run on main after merge is the activation evidence)
- [x] Deferred work recorded (all three inventory entries are probe: none today — the api-zen activation path is documented in the runbook and requires a deliberate contract change incl. the pinned workflow test; no other deferred work)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
