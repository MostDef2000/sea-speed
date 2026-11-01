# Spec: #578 — One documented command that reproducibly runs the full test battery

- Issue: #578
- Specification: specs/578-one-command-test-run/spec.md
- Authorization: the #578 scope (scripts/run_tests.py + tests/test_run_tests_script.py +
  README "Running the tests" section + this trio; audit #534 section P2-02) admitted by the
  delivery orchestrator; base 4ce5b6b (branch fix/578-one-command-test-run).

## Product outcome

A contributor on a clean checkout runs one documented command —
`python3 scripts/run_tests.py` — and gets the full Quality-integration
battery reproduced locally with no implicit environment dependencies: the
script gates the interpreter to the CI-pinned CPython 3.14, verifies
(installing when missing) the single declared dependency `pyyaml==6.0.3`,
proves via an import-hygiene scan that the tests tree imports nothing beyond
the standard library, the declared pin and the repository itself, and then
runs the exact two `unittest` commands from
`.github/workflows/quality-integration.yml`. Today the battery's only
non-stdlib dependency is installed by a separate CI step (the auditor's
reproducibility gap), no document explains how to run the tests, and
runner drift (pytest versus unittest, wrong Python) produced audit #534
P2-02's false findings. After the change a green local run means exactly
what a green CI run means, and pasted output is self-describing.

## User scenarios

- SC-1: a contributor clones the repository on a clean machine with Python
  3.14 and runs `python3 scripts/run_tests.py` — the script verifies the
  interpreter, installs `pyyaml==6.0.3` if missing (printing the exact pip
  command), scans the tests tree, runs both CI battery commands and prints a
  one-line PASS summary carrying the resolved environment identity.
- SC-2: a contributor on Python 3.13 (or PyPy, or 3.12) runs the command —
  it fails closed before installing or running anything, printing the
  observed version, the required 3.14 pin and the reason (CI parity).
- SC-3: a contributor on a locked-down host runs
  `python3 scripts/run_tests.py --skip-install` with pyyaml absent — the
  script fails closed naming the unsatisfied pin instead of invoking pip.
- SC-4: someone adds `import requests` to a test file — the next run lists
  `file:line:module` for the undeclared import and fails closed before the
  battery starts, so implicit environment dependencies cannot re-enter the
  test path.
- SC-5: the battery result means what CI means: the same two unittest
  invocations with `-W error::ResourceWarning`, output streamed (not
  captured), first failure stops the run with a non-zero exit and a one-line
  FAIL summary.

## Acceptance criteria

- AC-001: `python3 scripts/run_tests.py` from the repository root performs,
  in order and failing closed: the Python version gate, the declared
  -dependency gate, the import-hygiene scan, then the exact CI battery, and
  prints a final one-line summary naming the commands run and the overall
  PASS/FAIL state.
- AC-002: the version gate accepts CPython 3.14.x and rejects any other
  implementation or major.minor (3.13 and 3.12 covered by tests), printing
  the observed version, the required version and the reason, exiting
  non-zero.
- AC-003: the dependency gate accepts `yaml.__version__ == 6.0.3`, rejects a
  missing or mismatched pyyaml (and reports any probe crash as a problem
  line), installs with exactly
  `{sys.executable} -m pip install pyyaml==6.0.3` (command printed), then
  re-verifies against a FRESH import — the cached `sys.modules` entries of
  the declared imports are purged after the install, so a wrong-version host
  passes on the first run once the pin is installed — and fails closed if
  still unsatisfied; `--skip-install` fails closed without installing.
- AC-004: the import-hygiene scan AST-walks every `tests/**/*.py` including
  conditional imports, classifies each top-level import as stdlib, declared
  or repo-local (relative imports are repo-local by definition; an import
  in the body of a try whose handler catches
  ModuleNotFoundError/ImportError is reported as guarded-optional, while
  handler bodies, orelse and finalbody inherit the outer state), lists
  `file:line:module` for anything unclassified and fails closed; an
  unparsable test file fails closed with a self-describing file:line error;
  the real tests tree passes with zero unclassified imports.
- AC-005: the battery step runs exactly the two commands from
  quality-integration.yml (`unittest discover -s tests -p 'test_*.py'` and
  `unittest tests.quality.test_quality_architecture`, both with
  `-W error::ResourceWarning`) via subprocess with passthrough output from
  the repository root, returning the first non-zero exit.
- AC-006: the script is stdlib-only and ruff-clean under
  scripts/quality/ruff.toml; README documents the one command and the
  stdlib-only-apart-from-the-pyyaml-pin property; the full battery, ruff and
  the repository validators stay green with the battery delta accounted.

## Requirements

- R-1: `scripts/run_tests.py` (new, stdlib-only, runnable as
  `python3 scripts/run_tests.py` from the repository root) implements the
  four gated steps with no flags beyond `--skip-install`.
- R-2: the declared-dependency table in the script initially contains
  exactly `pyyaml==6.0.3`, mirroring the workflow's "Install test-only YAML
  parser" step; the gate verifies importability and `__version__` against
  the pin (any probe crash is reported as a problem line, not a traceback)
  and prints the resolved environment identity (Python version, dependency
  versions); after a successful install the gate purges the cached
  `sys.modules` entries of every declared import name so the re-verification
  performs a fresh import — a wrong-version host passes on the first run
  once the pin is installed.
- R-3: the import-hygiene scan classifies top-level import names against
  `sys.stdlib_module_names`, the declared table, and repo-local resolution
  under the sys.path roots effective during the battery (repository root,
  the `tests/` discovery root, `worker/`); relative imports are repo-local;
  the guarded-optional exemption covers only the body of a try whose handler
  catches ModuleNotFoundError/ImportError (handler bodies, orelse and
  finalbody inherit the outer state); an unparsable test file fails closed
  with a self-describing file:line error instead of a traceback.
- R-4: `tests/test_run_tests_script.py` (new) covers the version gate
  (3.14 accepted; 3.13/3.12 and non-CPython rejected), the dependency gate
  (pinned accepted; missing/mismatched rejected; probe crash reported;
  installer injected — no network, no real pip; the install path
  re-verifies through the real importlib path against a stale pre-seeded
  `sys.modules` cache, a test that fails on the unfixed implementation), the
  import-hygiene classification (real tree clean; synthetic undeclared
  import flagged; declared/repo-local/relative/guarded accepted; the guard
  does not leak into handler/orelse/finally; unparsable files fail closed)
  and the battery identity against the parsed workflow (parsed twin per the
  #573 convention).
- R-5: README.md gains a short "Running the tests" section documenting the
  one command, the four steps and the reproducibility property.
- R-6: the SDD trio `specs/578-one-command-test-run/{spec,plan,tasks}.md` is
  created; no other files change (`.github/**`, existing tests and all other
  scripts are untouched).

## Runtime feedback

- RF-001: Operator actions expected: 0 — developer tooling only; no runtime
  contour (VPS, Ubuntu Worker/relay) is touched, so there is no deploy and
  no runtime acceptance step. Acceptance evidence is the local one-command
  run plus exact-head CI on the merge PR.
- RF-002: strictly additive change — no product behavior, workflow, schema
  or stored data is affected; the script only reads the repository and runs
  the CI battery commands locally.

## NFR assessment

- NFR-001 | Area: reproducibility | Target: one documented command reproduces the full battery on a clean checkout — CPython 3.14 gate, declared pyyaml==6.0.3 pin, zero undeclared test imports, CI-identical battery commands | Validation: tests/test_run_tests_script.py (23 methods / 11 subtests) plus an observed full `python3 scripts/run_tests.py` run on the final tree | Evidence: completion gate in tasks.md | Status: PASS
- NFR-002 | Area: fail-closed behavior | Target: every gate (version, dependency, import hygiene) exits non-zero with a self-describing message instead of running a drifted environment | Validation: rejection tests for 3.13/3.12/non-CPython, wrong/missing pyyaml, --skip-install, synthetic `import requests`, and a non-module-error guard | Evidence: focused pytest run recorded in tasks.md | Status: PASS
- NFR-003 | Area: performance | Target: negligible — the AST import scan of the tests tree completes in well under a second (~980 imports observed) and adds no battery runtime | Validation: timed scan during development; script overhead is two gates plus one scan before the unchanged battery | Evidence: plan.md Validation section | Status: PASS
