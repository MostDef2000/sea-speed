#!/usr/bin/env python3
"""One-command reproducible Sea Speed test battery (issue #578).

One documented command installs the declared dependencies and runs the full
battery reproducibly on a clean checkout, with no implicit environment
dependencies in the test path:

    python3 scripts/run_tests.py

Steps, in order, each failing closed:

0. Python version gate — requires CPython 3.14, the version pinned by
   ``.github/workflows/quality-integration.yml`` (setup-python). Any other
   major.minor or implementation is rejected with the observed version, the
   required version and the reason, before anything runs.
1. Declared-dependency gate — the battery is stdlib-only apart from the
   pins declared in ``DECLARED_DEPS`` (initially exactly ``pyyaml==6.0.3``,
   mirroring the workflow's "Install test-only YAML parser" step). A missing
   or mismatched pin is installed with the printed exact pip command and
   re-verified; the run fails closed if the pin is still unsatisfied.
   ``--skip-install`` fails closed instead of installing (locked-down hosts).
2. Import-hygiene scan — every top-level import name in ``tests/**/*.py`` is
   collected with ``ast.walk`` (so conditional imports are caught too) and
   classified as stdlib, declared, or repo-local (the name resolves to a
   file/dir under the repository root, the unittest discovery root ``tests/``,
   or ``worker/`` — the sys.path roots effective during the battery).
   Relative imports are repo-local by definition. Anything else is an
   implicit environment dependency: it is listed as ``file:line:module`` and
   fails the run. An import lexically inside a ``try`` whose handler catches
   ``ModuleNotFoundError``/``ImportError`` is reported as guarded-optional
   (the test carries its own fallback, e.g. the fastapi stub probe in
   ``tests/test_live_envelope_validators.py``) and does not fail the scan.
3. Battery — the two exact ``unittest`` commands from
   ``.github/workflows/quality-integration.yml`` (lines 72 and 92), run via
   subprocess with output passed through, stopping at the first failure.

The script itself is stdlib-only. Pasted output is self-describing: the
resolved Python and pyyaml identities are printed by the gates and repeated
in the final one-line summary.
"""
from __future__ import annotations

import argparse
import ast
import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ImportScanError(ValueError):
    """A test file could not be parsed during the import-hygiene scan (fail closed)."""

# CI parity: .github/workflows/quality-integration.yml pins Python 3.14 via
# actions/setup-python. The battery is only reproducible on that version.
REQUIRED_PYTHON = (3, 14)
REQUIRED_IMPLEMENTATION = "cpython"

# Declared battery dependencies: (pip package, pinned version, import name).
# The battery is stdlib-only apart from these pins; the pyyaml pin mirrors
# the "Install test-only YAML parser" step in quality-integration.yml.
DECLARED_DEPS = (
    ("pyyaml", "6.0.3", "yaml"),
)

# sys.path roots effective during the battery: the repository root (CI cwd),
# the unittest discovery root tests/ (discover -s tests) and worker/ (inserted
# by tests that import worker modules direct-file). A top-level import that
# resolves in none of these and is not stdlib or declared comes from
# site-packages — an implicit environment dependency.
LOCAL_IMPORT_ROOTS = ("", "tests", "worker")

# An import lexically inside a try whose handler catches one of these has an
# in-code fallback and is reported as guarded-optional instead of failing the
# scan (the battery must stay green without the guarded module installed).
GUARD_EXCEPTIONS = {"ModuleNotFoundError", "ImportError"}

# The exact CI battery (quality-integration.yml lines 72 and 92), in order.
BATTERY_COMMANDS = (
    (
        "unittest discover -s tests -p 'test_*.py' (repository behavioral tests)",
        ("-W", "error::ResourceWarning", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"),
    ),
    (
        "unittest tests.quality.test_quality_architecture (quality architecture tests)",
        ("-W", "error::ResourceWarning", "-m", "unittest", "tests.quality.test_quality_architecture", "-v"),
    ),
)


def format_version(version_info: tuple[int, ...]) -> str:
    """Render a version_info-like sequence as 'major.minor.micro'."""
    return ".".join(str(part) for part in tuple(version_info)[:3])


def check_python_version(
    version_info: tuple[int, ...] | None = None,
    implementation: str | None = None,
) -> tuple[bool, str]:
    """Gate step 0: require CPython 3.14 (the CI setup-python pin)."""
    version_info = sys.version_info if version_info is None else version_info
    implementation = sys.implementation.name if implementation is None else implementation
    observed = format_version(version_info)
    required = ".".join(str(part) for part in REQUIRED_PYTHON)
    reason = "the battery is only reproducible on the version pinned by CI setup-python"
    if implementation != REQUIRED_IMPLEMENTATION:
        return False, (
            f"observed {implementation} {observed}; required CPython {required} "
            f"({reason})"
        )
    if tuple(version_info)[:2] != REQUIRED_PYTHON:
        return False, (
            f"observed Python {observed}; required CPython {required} ({reason})"
        )
    return True, f"observed Python {observed} ({implementation}); matches the required {required} pin"


def declared_deps_identity() -> str:
    """One-line identity of the declared deps, e.g. 'pyyaml==6.0.3'."""
    return "; ".join(f"{pip_name}=={pin}" for pip_name, pin, _import_name in DECLARED_DEPS)


def verify_declared_deps(import_fn=None) -> list[str]:
    """Return one problem line per declared dep that is missing or mismatched."""
    import_fn = import_fn if import_fn is not None else importlib.import_module
    problems: list[str] = []
    for pip_name, pin, import_name in DECLARED_DEPS:
        try:
            module = import_fn(import_name)
        except ModuleNotFoundError:
            problems.append(f"{pip_name}=={pin}: import {import_name} failed (not installed)")
            continue
        except Exception as exc:  # fail closed on any probe crash, self-describing
            problems.append(f"{pip_name}=={pin}: import {import_name} failed ({exc})")
            continue
        version = getattr(module, "__version__", None)
        if version != pin:
            observed = "unknown version" if version is None else f"version {version}"
            problems.append(f"{pip_name}=={pin}: import {import_name} resolved to {observed}")
    return problems


def install_declared_deps(run=subprocess.run) -> int:
    """Install every declared dep with its exact pinned pip command."""
    for pip_name, pin, _import_name in DECLARED_DEPS:
        command = [sys.executable, "-m", "pip", "install", f"{pip_name}=={pin}"]
        print(f"[gate:deps] installing declared dependency: {' '.join(command)}", flush=True)
        completed = run(command, check=False)
        if completed.returncode != 0:
            print(f"[gate:deps] pip install failed with exit {completed.returncode}", flush=True)
            return completed.returncode
    return 0


def ensure_declared_deps(
    skip_install: bool = False,
    import_fn=None,
    install_fn=None,
) -> tuple[bool, str]:
    """Verify declared deps; install the pin when missing unless --skip-install."""
    import_fn = import_fn if import_fn is not None else importlib.import_module
    install_fn = install_fn if install_fn is not None else install_declared_deps
    problems = verify_declared_deps(import_fn=import_fn)
    if not problems:
        return True, f"declared dependencies satisfied: {declared_deps_identity()}"
    if skip_install:
        return False, (
            f"declared dependencies not satisfied ({'; '.join(problems)}); "
            "--skip-install is set, failing closed instead of installing"
        )
    if install_fn() != 0:
        return False, f"declared dependencies not satisfied ({'; '.join(problems)}); pip install failed"
    # The install replaced the distribution files, but the pre-install probe
    # may have cached the old module in sys.modules; purge every declared
    # import name so re-verification performs a fresh import instead of
    # silently re-reading the stale cached object (a wrong-version host would
    # otherwise fail this run and only pass on the next invocation).
    for _pip_name, _pin, import_name in DECLARED_DEPS:
        sys.modules.pop(import_name, None)
    problems = verify_declared_deps(import_fn=import_fn)
    if problems:
        return False, (
            f"declared dependencies still unsatisfied after install: {'; '.join(problems)}"
        )
    return True, f"declared dependencies installed and re-verified: {declared_deps_identity()}"


def _handler_catches_import_error(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return False
    candidates = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(node, ast.Name) and node.id in GUARD_EXCEPTIONS for node in candidates)


def collect_import_records(tree: ast.AST) -> list[tuple[int, str, int, bool]]:
    """(line, top-level name, relative level, guarded) for every import in the tree.

    ast.walk-equivalent full recursion, so imports nested in functions or
    try/except blocks (conditional imports) are collected too. An import in
    the BODY of a try whose handler catches ModuleNotFoundError/ImportError
    is marked guarded; handler bodies, orelse and finalbody inherit the
    OUTER guarded state — code there runs outside the guard, so an
    unguarded import cannot hide behind the try's exception handler.
    """
    records: list[tuple[int, str, int, bool]] = []

    def visit(node: ast.AST, guarded: bool) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                records.append((node.lineno, alias.name.split(".")[0], 0, guarded))
            return
        if isinstance(node, ast.ImportFrom):
            if node.level > 0:
                name = "." * node.level + (node.module or "")
                records.append((node.lineno, name, node.level, guarded))
            elif node.module:
                records.append((node.lineno, node.module.split(".")[0], 0, guarded))
            return
        if isinstance(node, ast.Try | ast.TryStar):
            # Only the try body is protected by the handlers; handler bodies,
            # orelse and finalbody run outside the guard and keep the outer
            # guarded state, so an unguarded import cannot hide behind the
            # try's exception handler.
            body_guarded = guarded or any(
                _handler_catches_import_error(handler) for handler in node.handlers
            )
            for statement in node.body:
                visit(statement, body_guarded)
            for handler in node.handlers:
                visit(handler, guarded)
            for statement in [*node.orelse, *node.finalbody]:
                visit(statement, guarded)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, guarded)

    visit(tree, False)
    return records


def classify_import(name: str, level: int, root: Path) -> str:
    """Classify a top-level import name: stdlib, declared, repo-local or unclassified."""
    if level > 0:
        return "relative"
    if name in sys.stdlib_module_names:
        return "stdlib"
    if any(name == import_name for _pip_name, _pin, import_name in DECLARED_DEPS):
        return "declared"
    for local_root in LOCAL_IMPORT_ROOTS:
        base = root / local_root if local_root else root
        if (base / name).is_dir() or (base / f"{name}.py").is_file():
            return "repo-local"
    return "unclassified"


def scan_test_imports(tests_dir: Path, root: Path) -> list[tuple[str, int, str, str]]:
    """AST-scan every tests/**/*.py import; returns (path, line, module, classification)."""
    records: list[tuple[str, int, str, str]] = []
    for path in sorted(tests_dir.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            raise ImportScanError(
                f"{path}:{exc.lineno}: test file does not parse ({exc.msg}); "
                "fix the syntax error before running the battery"
            ) from exc
        for line, name, level, guarded in collect_import_records(tree):
            classification = classify_import(name, level, root)
            if classification == "unclassified" and guarded:
                classification = "guarded-optional"
            records.append((str(path), line, name, classification))
    return records


def run_battery(python: str, run=None) -> int:
    """Run the exact quality-integration.yml battery commands; stop on first failure."""
    run = run if run is not None else subprocess.run
    for description, arguments in BATTERY_COMMANDS:
        command = [python, *arguments]
        print(f"[battery] {' '.join(command)}", flush=True)
        completed = run(command, cwd=ROOT, check=False)
        if completed.returncode != 0:
            print(
                f"[battery] FAILED (exit {completed.returncode}): {description}",
                flush=True,
            )
            return completed.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One-command reproducible Sea Speed test battery (issue #578).",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="fail closed instead of pip-installing a missing or mismatched declared dependency",
    )
    args = parser.parse_args(argv)

    print("== Sea Speed test battery (issue #578: one-command reproducible run) ==", flush=True)

    ok, message = check_python_version()
    print(f"[gate:python] {message}", flush=True)
    if not ok:
        print("== FAIL: Python version gate ==", flush=True)
        return 1

    ok, message = ensure_declared_deps(skip_install=args.skip_install)
    print(f"[gate:deps] {message}", flush=True)
    if not ok:
        print("== FAIL: declared-dependency gate ==", flush=True)
        return 1

    try:
        records = scan_test_imports(ROOT / "tests", ROOT)
    except ImportScanError as exc:
        print(f"[scan:imports] {exc}", flush=True)
        print("== FAIL: import-hygiene scan (test file does not parse) ==", flush=True)
        return 1
    counts: dict[str, int] = {}
    for _path, _line, _name, classification in records:
        counts[classification] = counts.get(classification, 0) + 1
    summary = ", ".join(f"{kind}={counts[kind]}" for kind in sorted(counts))
    undeclared = [record for record in records if record[3] == "unclassified"]
    if undeclared:
        print(f"[scan:imports] {len(records)} imports ({summary})", flush=True)
        print(f"[scan:imports] {len(undeclared)} undeclared import(s) — implicit environment dependencies:", flush=True)
        for path, line, name, _classification in undeclared:
            print(f"  {path}:{line}: {name}", flush=True)
        print("== FAIL: import-hygiene scan (undeclared test imports) ==", flush=True)
        return 1
    print(f"[scan:imports] {len(records)} imports across tests/**/*.py ({summary}) — OK", flush=True)

    exit_code = run_battery(sys.executable)
    identity = f"Python {format_version(sys.version_info)} {sys.implementation.name}"
    state = "PASS" if exit_code == 0 else "FAIL"
    print(
        f"== {state}: {len(BATTERY_COMMANDS)}/{len(BATTERY_COMMANDS)} CI battery commands green "
        f"({identity}, deps: {declared_deps_identity()}) ==",
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
