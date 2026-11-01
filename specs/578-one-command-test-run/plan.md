# Plan — Issue #578 one-command reproducible test run

- Issue: #578
- Specification: specs/578-one-command-test-run/spec.md

## Architecture

A single stdlib-only runner, `scripts/run_tests.py`, composes four fail-closed
steps in front of the unchanged CI battery. Step 0 gates the interpreter to
CPython 3.14 — the setup-python pin in `.github/workflows/quality-integration.yml`
— so the battery cannot run on a drifted Python. Step 1 verifies the declared
-dependency table (initially exactly `pyyaml==6.0.3`, the workflow's
"Install test-only YAML parser" pin) by importability plus `__version__`,
installs the exact pinned pip command when unsatisfied, re-verifies and fails
closed if still unsatisfied; `--skip-install` declines the install and fails
closed. Step 2 AST-walks every `tests/**/*.py` (full recursion, so conditional
imports are caught) and classifies each top-level import as stdlib, declared
or repo-local; anything unclassified is listed `file:line:module` and fails
the run before the battery starts. Step 3 runs the two exact unittest
commands from the workflow via subprocess with output passed through,
stopping at the first non-zero exit, and prints a one-line summary carrying
the resolved environment identity so pasted output is self-describing.

## Decisions

- **Reproduce CI exactly; do not add a second runner**: the script shells
  out to the two workflow commands verbatim (`-W error::ResourceWarning`
  included) instead of wrapping pytest. The auditor's false finding came
  from runner drift; the fix removes the drift rather than blessing a
  second invocation.
- **Declared-deps table inside the script, not a requirements file**: the
  table is the single source the gate verifies and installs from; a separate
  requirements file would be a second place for the pin to drift from the
  workflow's `pip install pyyaml==6.0.3`.
- **Import-hygiene resolution roots = repository root + tests/ + worker/**:
  these are the sys.path roots effective during the battery — the unittest
  discovery root (`discover -s tests`), the CI cwd (repository root) and the
  `worker/` dir tests insert to import worker modules direct-file. A
  top-level name resolving in none of them, and not stdlib or declared, can
  only come from site-packages — an implicit environment dependency. This
  classifies every name in the real tree (992 imports observed on the final
  tree, 0 unclassified).
- **Guarded-optional classification for in-code fallbacks**:
  `tests/test_live_envelope_validators.py:61` imports fastapi inside a try
  whose handler catches ModuleNotFoundError and injects a stub — the test
  carries its own fallback, so that import is not an environment dependency.
  The scan reports it as guarded-optional instead of failing; a guard
  catching anything else (e.g. ValueError) still fails closed, so the
  exemption cannot hide a real dependency. The guarded state covers only the
  try BODY: handler bodies, orelse and finalbody inherit the outer state, so
  an unguarded import cannot hide behind the try's exception handler.
- **Fresh import on post-install re-verification**: pip replaces the
  distribution files, but the pre-install probe caches the imported module
  in `sys.modules`; after a successful install the gate purges every
  declared import name from `sys.modules` so the re-verification performs a
  fresh import. Without the purge, a wrong-version host (e.g. pyyaml 6.0.2)
  fails the run even though the pin is now installed, and only a second
  invocation passes.
- **Injectable gates for testability**: the version gate accepts explicit
  version/implementation, the dependency gate accepts an import function and
  an installer, and the battery runner accepts a subprocess stand-in — the
  unit tests never touch the network, pip or the real battery. The one seam
  that must NOT be injected away — importlib caching — is exercised for
  real: the install-path test pre-seeds a stale module in `sys.modules` and
  lets the re-verification import through the genuine `importlib.import_module`.
- **Static scan scope**: the import-hygiene scan is static (import
  statements in `tests/**/*.py`); dynamic `__import__`/`importlib` calls and
  modules loaded direct-file are enforced by the battery itself on a clean
  environment, not by the scan — recorded in README and tasks.md deferred
  work.
- **Parsed workflow twin in the tests**: the battery-identity test reads the
  two `run:` strings from the parsed `quality-integration.yml` structure
  (issue #573 convention: parsed twins over raw text pins) and asserts the
  script's command tuples match token-for-token, so a future workflow edit
  that changes the battery fails this test instead of silently desyncing the
  local parity path.

## Affected contours

- Control plane (developer tooling, no runtime release): 
  `scripts/run_tests.py` (new), `tests/test_run_tests_script.py` (new),
  `README.md` ("Running the tests" section), this SDD trio.
- Contour reasoning: `scripts/run_tests.py` is executed by developers on a
  checkout; it ships in no release manifest, touches no deployable contour
  and is not in the SDD validator's significant-path set
  (`scripts/{ci,operations,quality,release}`). No `deploy/**`, workflow,
  api/**, worker/** or frontend/** file changes, so there is no VPS or
  Ubuntu Worker/relay release impact and no Deployment transaction audit is
  required (`validate_sdd.requires_deployment_transaction_audit` is False
  for this changed-file set and the NONE correct-course trigger).
- Nothing else: no `.github/**`, no existing test files, no other scripts.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: the script adds gates in front of the unchanged CI commands and never mutates the repository; the battery-identity unit test pins both command tuples token-for-token against the parsed workflow, and the import scan is validated against the real tests tree (992 imports, 0 unclassified) plus synthetic positives and negatives | Validation: tests/test_run_tests_script.py + full battery + ruff | Residual risk: a future workflow edit that changes the battery commands without updating BATTERY_COMMANDS is caught by the parsed-twin test at the next battery run | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: every gate fails closed with the observed and required values printed; `--skip-install` provides an explicit no-install path for locked-down hosts that still fails closed on a missing pin; the installer runs exactly one pinned pip command and nothing else | Validation: gate rejection tests (DependencyGateTests, PythonVersionGateTests) plus the observed full script run | Residual risk: contributors on non-3.14 interpreters cannot use the one-command path — that is the intended reproducibility contract, and the rejection message states the required pin | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: BUS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the script installs only its own declared pin into the running interpreter's environment, printing the exact command first; it never upgrades, downgrades or removes anything else | Validation: code review of install_declared_deps (single pinned command, no flags) | Residual risk: on shared or managed interpreters an automatic install may be unwanted — `--skip-install` is the documented escape hatch | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_run_tests_script.py::PythonVersionGateTests — 3.14.x accepted; 3.13/3.12 rejected with observed+required+reason; non-CPython rejected; live sys.state rejection; main() exits non-zero on version mismatch
- TEST-002 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_run_tests_script.py::DependencyGateTests — pinned yaml accepted; wrong/missing version rejected; probe crash reported as a problem line; --skip-install fails closed without calling the installer; installer command is exactly `pip install pyyaml==6.0.3`; the install path re-verifies through the REAL importlib path against a stale pre-seeded sys.modules cache (observed failing on the unfixed implementation and passing with the purge); install failure and post-install mismatch fail closed
- TEST-003 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: tests/test_run_tests_script.py::ImportHygieneScanTests — real tests tree 0 unclassified with yaml declared; the guarded fastapi probe classified guarded-optional; synthetic `import requests` flagged file:line:module; yaml/tests.support/scripts/relative accepted; non-module-error guard still flagged; the guarded state does not leak into handler bodies, orelse or finalbody; an unparsable test file raises ImportScanError naming file:line and main() exits non-zero without a traceback
- TEST-004 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: tests/test_run_tests_script.py::BatteryIdentityTests — script command tuples match the parsed quality-integration.yml run strings token-for-token; both commands run from the repository root; first failure stops the run
- TEST-005 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: observed full `python3 scripts/run_tests.py` run on the final tree — gates, scan and both CI battery commands green with the one-line summary (tasks.md completion gate)
- TEST-006 | Covers: AC-006 | Level: integration | Priority: P1 | Evidence: full pytest battery with delta accounted, repo-wide ruff, validate_sdd and the repository validators (tasks.md completion gate); ScriptHygieneTests pins the script stdlib-only

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Validation

- Focused run `python3 -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/578/pytest-tmp tests/test_run_tests_script.py -q`: OBSERVED 27 passed / 11 subtests passed.
- CI-idiom check `python3 -W error::ResourceWarning -m unittest tests.test_run_tests_script -v`: OBSERVED "Ran 27 tests ... OK".
- Import-hygiene scan on the real tree (final tree, incl. tests/test_run_tests_script.py): OBSERVED 992 imports — stdlib 873, repo-local 100, declared 18, guarded-optional 1 (the fastapi stub fallback at tests/test_live_envelope_validators.py:61), unclassified 0.
- FIX-2 two-direction check: with the sys.modules purge temporarily removed, the install-path test FAILS ("declared dependencies still unsatisfied after install: fakepkg==1.2.3: import fakepkg resolved to version 0.0.1" — the stale cache masking the install); with the purge restored it PASSES. Both directions observed.
- Full battery, one-command run, ruff and validators: OBSERVED values recorded in tasks.md.

## Runtime feedback

- RF-001: Operator actions expected: 0 — developer tooling with no runtime
  contour; merge-facing evidence is exact-head CI, and the local acceptance
  evidence is the observed one-command run in tasks.md.
- RF-002: no migration, no stored data, no runtime behavior change; the
  script is additive and read-only over the repository except for the
  declared-dependency pip install it prints before performing.
