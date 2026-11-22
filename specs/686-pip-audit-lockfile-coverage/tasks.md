# Tasks: pip-audit lockfile coverage — audit the full hash-locked dependency graphs

- Spec: specs/686-pip-audit-lockfile-coverage/spec.md
- Plan: specs/686-pip-audit-lockfile-coverage/plan.md
- Issue: #686

## Delivery tasks
- [x] Coverage gap confirmed on branch agent/wave4-686-pip-audit-lockfiles: `dependency-audit` audited only `api/requirements-api.txt` (7 pins) and `deploy/worker/ubuntu/requirements-runtime.txt` (7 pins), while `api/requirements-api.lock.txt` (23 pins) and `deploy/worker/ubuntu/requirements-runtime.lock.txt` (57 pins) left 16 API and 50 worker transitive pins unaudited
- [x] pip-audit pinned in `.github/workflows/security.yml`: the install step is `pip install pip-audit==2.10.1`, replacing the bare unpinned install
- [x] Existing direct-manifest audits kept byte-identical: `pip-audit -r deploy/worker/ubuntu/requirements-runtime.txt` and `pip-audit -r api/requirements-api.txt` are unchanged inside `dependency-audit`
- [x] Full API lockfile audit added: `pip-audit --disable-pip -r api/requirements-api.lock.txt --format json --output pip-audit-api-lock.json`
- [x] Full worker lockfile audit added: `pip-audit --disable-pip -r deploy/worker/ubuntu/requirements-runtime.lock.txt --format json --output pip-audit-worker-lock.json`
- [x] Report provenance added: an `if: always()` step uploads `pip-audit-api-lock.json` and `pip-audit-worker-lock.json` as `pip-audit-reports-${{ github.sha }}` through the existing SHA-pinned `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02` at 14-day retention
- [x] Negative self-test added: feeds `requests==2.20.0` (CVE-2018-18074, CVE-2023-32681) through the same `pip-audit --disable-pip` command under an explicit guard that exits non-zero if the audit unexpectedly succeeds, with no `continue-on-error` and no step-level `if`
- [x] Emergent YAML fix applied: the self-test step name is quoted (`"Negative self-test: known-vulnerable pin must fail the audit"`) because the original unquoted colon broke YAML parsing; the workflow parses cleanly
- [x] No other workflow change: `secret-scan`, `security-result`, the `on:` events, `permissions`, `concurrency`, timeouts, both direct-manifest audit commands and every action SHA pin are byte-identical
- [x] New tests in `tests/quality/test_security_merge_gate.py` (additive only, 5 cases): exact pip-audit pin, both verbatim lockfile commands, the SHA-pinned artifact upload with both report filenames, the negative self-test shape, and a premise that the lockfiles carry 16 API and 50 worker transitive-only pins
- [x] RED then GREEN proof: RED before the change 5 failed / 9 passed; GREEN after 11 passed plus 80 subtests
- [x] Full battery and static gates green: 1444 tests OK (skipped=2); repo, contracts, quality, workflow and token validators PASS; ruff PASS; workflow YAML parse OK
- [x] Write the SDD trio `specs/686-pip-audit-lockfile-coverage/{spec,plan,tasks}.md`
- [ ] PR Change Contract declares exactly `Production impact: CONTROL_PLANE`, `VPS deployment: NOT REQUIRED`, `Ubuntu worker/relay update: NOT REQUIRED`, `Production safety envelope: NOT REQUIRED`, `VPS execution capability: NOT APPLICABLE`, `Ubuntu worker execution capability: NOT APPLICABLE`, `Operator actions expected: 0`, plus `Risk profile: REQUIRED` and `Specification: specs/686-pip-audit-lockfile-coverage/spec.md`
- [ ] Exact-head CI on the PR is green, including the new quality cases, the SDD validator for this trio, the contracts, quality, workflow and token validators, and ruff
- [ ] Exact-green-head merge of the PR to main
- [ ] The merged SHA's Security run is green with the `pip-audit-reports-<sha>` artifact carrying `pip-audit-api-lock.json` and `pip-audit-worker-lock.json`

## Completion gate
- The workflow diff is confined to `dependency-audit` in `.github/workflows/security.yml`: the exact pip-audit pin, two additive `--disable-pip` lockfile audits, one `if: always()` artifact upload and one negative self-test; both direct-manifest audits, `secret-scan`, `security-result`, the triggers, permissions, concurrency, timeouts and every action pin are unchanged
- The test diff adds five cases to `tests/quality/test_security_merge_gate.py` only, weakens no existing assertion, and the full battery stays at 1444 tests OK (skipped=2) with validators and ruff green and the workflow YAML parsing cleanly
- The PR Change Contract declares the CONTROL_PLANE fields listed in the delivery tasks, because the diff is under `.github/workflows/**` and the autonomous policy derives `Production impact: CONTROL_PLANE` from the path
- Exact-head CI green on the PR, PR merged to main with exact-green-head evidence, and the merged-SHA Security run green with the JSON reports uploaded
- Acceptance is provenance and gate behaviour, not a runtime probe: the uploaded artifact shows the full resolved graph, and the negative self-test proves a known-vulnerable pin fails the gate; production runtime is not touched

## Requirements traceability
- AC-001 | Task: pip-audit is pinned to an exact version and both full lockfiles are audited with the verbatim `--disable-pip --format json --output` commands while the two direct-manifest audits stay unchanged | Evidence: tests/quality/test_security_merge_gate.py::SecurityMergeGateTests.test_pip_audit_install_is_pinned and ::test_dependency_audit_lockfile_commands, RED 5 failed / 9 passed before the change and GREEN after; the premise case ::test_lockfiles_cover_transitive_only_pins observes 16 API and 50 worker transitive-only pins | Coverage: COVERED
- AC-002 | Task: both JSON reports are uploaded as `pip-audit-reports-${{ github.sha }}` by the SHA-pinned upload action with `if: always()` and 14-day retention, making the full resolved graph visible in CI | Evidence: tests/quality/test_security_merge_gate.py::SecurityMergeGateTests.test_lockfile_audit_reports_uploaded asserts a SHA-pinned `actions/upload-artifact` step whose path carries `pip-audit-api-lock.json` and `pip-audit-worker-lock.json`; `.github/workflows/security.yml` lines 80-88 show `if: always()` and `retention-days: 14` | Coverage: COVERED
- AC-003 | Task: a negative self-test feeds `requests==2.20.0` through the same `pip-audit --disable-pip` command under an explicit non-zero guard, with no `continue-on-error` and no step-level `if`, so an unexpectedly clean audit fails the gate | Evidence: tests/quality/test_security_merge_gate.py::SecurityMergeGateTests.test_negative_vulnerable_pin_self_test asserts the pin, the same audit mode, the absence of a swallow mechanism, the guard branching on the audit result and the non-zero exit path; `.github/workflows/security.yml` lines 90-103 exit 1 on an unexpectedly clean audit | Coverage: COVERED
- AC-004 | Task: the existing gitleaks scan, direct-manifest pip-audit gates and `security-result` aggregation remain intact, and the full battery plus validators stay green with no weakened assertion | Evidence: full Python suite 1444 tests OK (skipped=2) including the pre-#686 `test_baseline_protections` and `test_mutations_detected`; repo, contracts, quality, workflow and token validators PASS; ruff PASS; workflow YAML parse OK | Coverage: COVERED

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
