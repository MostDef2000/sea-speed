# Tasks — Issue #698 shared log redaction

- Issue: #698
- Specification: specs/698-log-redaction/spec.md

## Delivery tasks

- T-001 (code unit): add stdlib-only `api/app/log_redaction.py` with
  `redact_log_text`, `RedactingFilter`, `RedactingFormatter`,
  `install_api_redaction`; fixed marker `[REDACTED]`; idempotent.
- T-002 (code unit): wire `identity.py` filter (idempotent, keeps #591 handler
  and audit call), `main.py` import + `install_api_redaction()` + wrapped
  `:406` print, `passage_mirrors.py` and `analytics.py` imports + wrapped
  stderr prints. `store.py` untouched.
- T-003 (code unit): wire `observed-worker-runner.py` `forward()` (sanitize
  written string only) and `worker-control-agent.py` `log_message`.
- T-004 (packaging): add `api/app/log_redaction.py` to vps and ubuntu-worker
  required inventories, pin in the validator, mirror all `deploy.sh` sites.
- T-005 (SDD): this spec/plan/tasks trio with the audit table, exact regexes,
  masking contract, residual risks and Gherkin scenarios.
- T-006 (verification): py_compile, ruff, deploy.sh syntax + convergence,
  exact-artifact build/validate, focused boundary smokes, existing suite.
- T-007 (test worker, out of this scope): update
  `tests/quality/test_exact_artifact_convergence.py` (mirror count 9->10) and
  `tests/test_vps_deploy_transaction.py` release fixture (add
  `api/app/log_redaction.py`); add the redaction test module.

## Requirements traceability

- AC-001 | Task: T-002 | Evidence: identity filter smoke; test-worker integration test | Coverage: COVERED
- AC-002 | Task: T-002 | Evidence: wrapped stderr print smoke; test-worker integration test | Coverage: COVERED
- AC-003 | Task: T-001,T-002 | Evidence: uvicorn AccessFormatter smoke; test-worker integration test | Coverage: COVERED
- AC-004 | Task: T-003 | Evidence: runner forward smoke + telemetry counter check | Coverage: COVERED
- AC-005 | Task: T-003 | Evidence: control log_message smoke; existing operator-control tests | Coverage: COVERED
- AC-006 | Task: T-001 | Evidence: log_redaction idempotence/benign cases; test-worker unit tests | Coverage: COVERED
- AC-007 | Task: T-001,T-002 | Evidence: double-install smoke; test-worker reload probe | Coverage: COVERED
- AC-008 | Task: T-004 | Evidence: exact-artifact build+validate; convergence 10/10 | Coverage: COVERED

## Completion gate

- All in-scope Python files py_compile clean.
- ruff (base tier) clean on changed files.
- `bash -n deploy/vps/deploy.sh` clean; convergence check passes (10/10).
- `build_exact_artifacts.py` + `validate_exact_artifacts.py` green in a temp
  output dir.
- Focused boundary smokes observed green.
- Existing suite run; only the two known test-worker pin failures remain,
  explicitly recorded as expected and not caused by code regressions.

## Definition of Done

- Issue/spec/plan/tasks current
- Exact changed-file scope verified
- Required tests and evidence complete
- Required CI green
- Exact-green-head merge complete
- Deployment state resolved
- Runtime acceptance resolved
- Deferred work recorded
- Risks resolved or explicitly accepted
- Waivers resolved or current
