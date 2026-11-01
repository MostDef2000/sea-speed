# Tasks — Issue #578 one-command reproducible test run

- Issue: #578
- Specification: specs/578-one-command-test-run/spec.md

## Delivery tasks

- T-1: scripts/run_tests.py — new stdlib-only one-command battery runner:
  step 0 CPython 3.14 version gate (observed/required/reason on rejection);
  step 1 declared-dependency gate (table initially exactly `pyyaml==6.0.3`
  mirroring quality-integration.yml, verify import + `__version__`, install
  via the printed exact `{sys.executable} -m pip install pyyaml==6.0.3`,
  re-verify, fail closed; `--skip-install` fails closed without installing);
  step 2 AST import-hygiene scan of every `tests/**/*.py` (stdlib / declared
  / repo-local under the battery's sys.path roots / relative; guarded
  in-code fallbacks reported as guarded-optional; unclassified imports listed
  file:line:module and fail closed); step 3 the exact two
  quality-integration.yml battery commands with passthrough output, stopping
  at the first failure, plus a one-line summary. DONE (focused green).
- T-2: tests/test_run_tests_script.py — new file, 27 methods / 11 subtests:
  version gate (3.14 accepted; 3.13/3.12/non-CPython rejected; live-sys
  rejection; main() exits non-zero), dependency gate (pinned accepted;
  missing/mismatched rejected; probe crash reported; installer injected — no
  network, no real pip; exact pinned install command pinned; install path
  re-verifies through the REAL importlib path against a stale pre-seeded
  sys.modules cache — fails on the unfixed implementation), import-hygiene
  classification (real tree clean; synthetic `import requests` flagged;
  declared/repo-local/relative/guarded accepted; non-module-error guard
  flagged; guard does not leak into handler/orelse/finally; unparsable test
  file fails closed in the scan and in main()), battery identity against the
  parsed workflow, script stdlib-only pin.
  DONE (focused green: 27 passed / 11 subtests).
- T-3: README.md — "Running the tests" section documenting the one command,
  the four gated steps and the stdlib-only-apart-from-pyyaml-pin
  reproducibility property. DONE.
- T-4: specs/578-one-command-test-run/ trio (this spec/plan/tasks). DONE.
- T-5: peer-review fixes (REQUEST_CHANGES round): post-install
  re-verification purges cached `sys.modules` entries for every declared
  import name before re-checking (a wrong-version host passes on the first
  run after the pin installs); the install-path test now drives the real
  importlib path with a stale pre-seeded cache and fails on the unfixed
  implementation (two-direction check observed); the guarded-import exemption
  is restricted to the try body (handler bodies, orelse and finalbody inherit
  the outer state); the scan fails closed with a self-describing error on an
  unparsable test file; the dependency probe reports any crash as a problem
  line; docs record the scan's static scope. DONE (focused green).

## Battery identity

Baseline on base 4ce5b6b: 1247 passed / 2 skipped / 346 subtests (pytest
rendering; observed on this tree with the new test file excluded — the work
order's 312-subtests figure is the pre-#577 baseline; the merged #577 trio
records 346 subtests on exactly this base commit). Delta: +27 test methods /
+11 subtests in tests/test_run_tests_script.py (23 methods before the peer
-review round, +4 review-fix methods: guard-leak restriction, scan
syntax-error gate, main gated failure, dependency probe crash) — expected
1274 passed / 2 skipped / 357 subtests. Observed: recorded in the completion
gate below.

## Completion gate

- Focused `python3 -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/578/pytest-tmp tests/test_run_tests_script.py -q`: OBSERVED 27 passed / 11 subtests passed.
- CI-idiom `python3 -W error::ResourceWarning -m unittest tests.test_run_tests_script -v`: OBSERVED "Ran 27 tests ... OK".
- Full battery `python3 -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/578/pytest-tmp tests/ -q`: OBSERVED 1274 passed / 2 skipped / 357 subtests — identity 1247 + 27 methods, 346 + 11 subtests, as accounted above (base 1247/2/346 re-observed on this tree with the new test file removed).
- One-command run `python3 scripts/run_tests.py` on the final tree: OBSERVED EXIT=0 — `[gate:python] observed Python 3.14.4 (cpython); matches the required 3.14 pin`, `[gate:deps] declared dependencies satisfied: pyyaml==6.0.3`, `[scan:imports] 992 imports across tests/**/*.py (declared=18, guarded-optional=1, repo-local=100, stdlib=873) — OK`, discover `Ran 1236 tests ... OK (skipped=2)`, quality architecture `Ran 8 tests ... OK`, `== PASS: 2/2 CI battery commands green (Python 3.14.4 cpython, deps: pyyaml==6.0.3) ==`.
- ruff `ruff check --config scripts/quality/ruff.toml .`: OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py`: OBSERVED "Sea Speed SDD validation passed".
- `python3 scripts/ci/validate_repo.py`: OBSERVED "Sea Speed repository validation passed" (826 tracked files).
- `python3 scripts/ci/validate_contracts.py`: OBSERVED "Canonical files checked: 66 / Resumable delivery entrypoints checked: 9".
- `python3 scripts/quality/validate_quality_contracts.py`: OBSERVED "Quality contracts valid: 7 contracts, 6 fixtures".
- `python3 scripts/quality/validate_workflow_policy.py`: OBSERVED "Workflow policy valid: protected public main -> exact quality -> standing policy -> restricted VPS/Ubuntu zero-touch execution".

## Requirements traceability

- AC-001 | Task: T-1+T-5 | Evidence: observed full `python3 scripts/run_tests.py` run — version gate, dependency gate, import scan, both CI battery commands, one-line PASS summary | Coverage: COVERED
- AC-002 | Task: T-1+T-2 | Evidence: PythonVersionGateTests — 3.14.x accepted; 3.13/3.12 rejected with observed+required+reason; non-CPython rejected; main() exits non-zero on version mismatch | Coverage: COVERED
- AC-003 | Task: T-1+T-2+T-5 | Evidence: DependencyGateTests — pinned yaml accepted; missing/mismatched rejected; probe crash reported as a problem line; --skip-install fails closed without installer; installer command exactly `pip install pyyaml==6.0.3`; install path re-verifies through the real importlib path against a stale pre-seeded cache (fails on the unfixed implementation, passes with the purge — both directions observed); failures closed | Coverage: COVERED
- AC-004 | Task: T-1+T-2+T-5 | Evidence: ImportHygieneScanTests — real tree 0 unclassified (992 imports; yaml declared; fastapi stub fallback guarded-optional); synthetic `import requests` flagged; declared/repo-local/relative accepted; non-module-error guard flagged; guard does not leak into handler/orelse/finally; unparsable test file fails closed in the scan and in main | Coverage: COVERED
- AC-005 | Task: T-1+T-2 | Evidence: BatteryIdentityTests — command tuples match the parsed quality-integration.yml run strings token-for-token; both run from the repository root; first failure stops the run | Coverage: COVERED
- AC-006 | Task: T-1+T-2+T-3 | Evidence: ScriptHygieneTests (script stdlib-only) + repo-wide ruff clean + full battery delta accounted + validate_sdd passed + README section (observed outputs in the completion gate) | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (scripts/run_tests.py + tests/test_run_tests_script.py + README.md section + this trio)
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (developer tooling — no runtime contour, no deploy)
- [ ] Runtime acceptance resolved (not applicable — no runtime contour; local one-command run is the acceptance evidence)
- [x] Deferred work recorded (the import-hygiene scan is static — import statements in tests/**/*.py; dynamic `__import__`/`importlib` calls and modules loaded direct-file are enforced by the battery itself on a clean environment, not by the scan; no other deferred work)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
