"""One-command test battery script contract (issue #578).

``scripts/run_tests.py`` is the documented one-command entry point that makes
the full battery reproducible on a clean checkout (audit #534 P2-02): a
CPython 3.14 version gate matching the CI setup-python pin, a declared
-dependency gate (``pyyaml==6.0.3``, mirroring the workflow's YAML-parser
install), an import-hygiene scan that fails closed on undeclared third-party
imports in ``tests/**``, and finally the exact two ``unittest`` commands from
``.github/workflows/quality-integration.yml``. These tests pin that contract.
The workflow commands are read from the PARSED workflow structure (parsed
twin, issue #573 convention), so the script's battery identity cannot drift
from CI silently. The installer is always injected — no test touches the
network or a real pip.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/run_tests.py"
WORKFLOW = ROOT / ".github/workflows/quality-integration.yml"

spec = importlib.util.spec_from_file_location("run_tests_script_578", SCRIPT_PATH)
assert spec and spec.loader
RUN_TESTS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RUN_TESTS)


def load_workflow(path: Path) -> dict:
    """Parse a workflow YAML file into its structure (PyYAML resolves bare ``on:`` to True)."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} did not parse to a mapping"
    return data


def workflow_battery_commands() -> list[str]:
    """The ``run:`` strings from quality-integration.yml that invoke unittest."""
    data = load_workflow(WORKFLOW)
    commands = []
    for job in data["jobs"].values():
        for step in job.get("steps", []):
            run = step.get("run")
            if isinstance(run, str) and "unittest" in run:
                commands.append(run.strip())
    return commands


def fake_yaml_module(version: str | None) -> types.SimpleNamespace:
    """A stand-in for the imported yaml module with a controlled __version__."""
    if version is None:
        return types.SimpleNamespace()
    return types.SimpleNamespace(__version__=version)


def missing_import_fn(name: str):
    raise ModuleNotFoundError(f"No module named {name!r}")


class PythonVersionGateTests(unittest.TestCase):
    """Gate step 0: CPython 3.14 only, with observed/required/reason on rejection."""

    def test_accepts_pinned_cpython_3_14(self):
        for micro in (0, 4):
            with self.subTest(micro=micro):
                ok, message = RUN_TESTS.check_python_version((3, 14, micro), "cpython")
                self.assertTrue(ok)
                self.assertIn("3.14", message)

    def test_rejects_other_minor_versions(self):
        for version in ((3, 13, 5), (3, 12, 7)):
            with self.subTest(version=version):
                ok, message = RUN_TESTS.check_python_version(version, "cpython")
                self.assertFalse(ok)
                self.assertIn(f"{version[0]}.{version[1]}", message)  # observed version
                self.assertIn("3.14", message)  # required version
                self.assertIn("pinned", message)  # reason

    def test_rejects_non_cpython_implementation(self):
        ok, message = RUN_TESTS.check_python_version((3, 14, 4), "pypy")
        self.assertFalse(ok)
        self.assertIn("pypy", message)
        self.assertIn("CPython", message)

    def test_gate_reads_live_sys_state(self):
        with mock.patch.object(sys, "version_info", (3, 12, 7, "final", 0)), mock.patch.object(
            sys.implementation, "name", "cpython"
        ):
            ok, message = RUN_TESTS.check_python_version()
        self.assertFalse(ok)
        self.assertIn("3.12", message)

    def test_main_fails_closed_on_version_mismatch(self):
        with mock.patch.object(sys, "version_info", (3, 13, 5, "final", 0)), mock.patch.object(
            sys.implementation, "name", "cpython"
        ):
            self.assertEqual(RUN_TESTS.main([]), 1)


class DependencyGateTests(unittest.TestCase):
    """Gate step 1: the declared-deps table is verified, installed, re-verified."""

    def test_accepts_pinned_yaml(self):
        problems = RUN_TESTS.verify_declared_deps(
            import_fn=lambda name: fake_yaml_module("6.0.3")
        )
        self.assertEqual(problems, [])

    def test_rejects_version_mismatch(self):
        for version in ("6.0.2", None):
            with self.subTest(version=version):
                problems = RUN_TESTS.verify_declared_deps(
                    import_fn=lambda name, v=version: fake_yaml_module(v)
                )
                self.assertEqual(len(problems), 1)
                self.assertIn("pyyaml==6.0.3", problems[0])

    def test_rejects_missing_module(self):
        problems = RUN_TESTS.verify_declared_deps(import_fn=missing_import_fn)
        self.assertEqual(len(problems), 1)
        self.assertIn("not installed", problems[0])

    def test_skip_install_fails_closed_without_installing(self):
        installed: list[list[str]] = []

        def install_fn():
            installed.append([])
            return 0

        ok, message = RUN_TESTS.ensure_declared_deps(
            skip_install=True,
            import_fn=missing_import_fn,
            install_fn=install_fn,
        )
        self.assertFalse(ok)
        self.assertEqual(installed, [])
        self.assertIn("--skip-install", message)

    def test_installer_uses_exact_pinned_command(self):
        commands: list[list[str]] = []

        def run(command, **_kwargs):
            commands.append(list(command))
            return types.SimpleNamespace(returncode=0)

        self.assertEqual(RUN_TESTS.install_declared_deps(run=run), 0)
        self.assertEqual(
            commands,
            [[sys.executable, "-m", "pip", "install", "pyyaml==6.0.3"]],
        )

    def test_rejects_import_probe_crash(self):
        def crashing_import_fn(name):
            raise RuntimeError("boom")

        problems = RUN_TESTS.verify_declared_deps(import_fn=crashing_import_fn)
        self.assertEqual(len(problems), 1)
        self.assertIn("import yaml failed (boom)", problems[0])

    def test_install_reverification_imports_fresh_module(self):
        """The post-install re-check must import fresh, not read the stale cache.

        Regression guard: the pre-install probe caches the imported module in
        sys.modules, so without a purge the re-verification after a successful
        install re-reads the stale pre-install object and a wrong-version host
        fails the run even though pip installed the pin (it only passes on the
        next invocation). This test drives the REAL importlib path: a temp
        package on sys.path, a stale pre-seeded sys.modules entry simulating
        the cached pre-install import, and an installer that replaces the
        module file on disk the way pip does.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sys.path.insert(0, str(tmp_path))
            self.addCleanup(sys.path.remove, str(tmp_path))
            self.addCleanup(sys.modules.pop, "fakepkg", None)
            (tmp_path / "fakepkg.py").write_text('__version__ = "0.0.1"\n', encoding="utf-8")
            stale = types.ModuleType("fakepkg")
            stale.__version__ = "0.0.1"
            sys.modules["fakepkg"] = stale

            def install_fn():
                (tmp_path / "fakepkg.py").write_text('__version__ = "1.2.3"\n', encoding="utf-8")
                return 0

            with mock.patch.object(
                RUN_TESTS, "DECLARED_DEPS", (("fakepkg", "1.2.3", "fakepkg"),)
            ):
                ok, message = RUN_TESTS.ensure_declared_deps(install_fn=install_fn)
            self.assertTrue(ok, message)
            self.assertIn("re-verified", message)
            self.assertEqual(sys.modules["fakepkg"].__version__, "1.2.3")

    def test_install_failure_fails_closed(self):
        ok, message = RUN_TESTS.ensure_declared_deps(
            import_fn=missing_import_fn,
            install_fn=lambda: 1,
        )
        self.assertFalse(ok)
        self.assertIn("pip install failed", message)

    def test_still_mismatched_after_install_fails_closed(self):
        ok, message = RUN_TESTS.ensure_declared_deps(
            import_fn=lambda name: fake_yaml_module("6.0.2"),
            install_fn=lambda: 0,
        )
        self.assertFalse(ok)
        self.assertIn("still unsatisfied after install", message)


class ImportHygieneScanTests(unittest.TestCase):
    """Gate step 2: every tests/**/*.py import is stdlib, declared or repo-local."""

    def scan_source(self, source: str) -> list[tuple[str, int, str, str]]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "test_synthetic.py").write_text(source, encoding="utf-8")
            return RUN_TESTS.scan_test_imports(tmp_path, ROOT)

    def test_real_tests_tree_has_no_undeclared_imports(self):
        records = RUN_TESTS.scan_test_imports(ROOT / "tests", ROOT)
        unclassified = [record for record in records if record[3] == "unclassified"]
        self.assertEqual(unclassified, [])
        self.assertGreater(len(records), 100)  # the scan walked the real tree
        declared = {name for _path, _line, name, kind in records if kind == "declared"}
        self.assertIn("yaml", declared)

    def test_guarded_optional_probe_is_the_fastapi_stub_fallback(self):
        records = RUN_TESTS.scan_test_imports(ROOT / "tests", ROOT)
        guarded = [
            (Path(path).name, line, name)
            for path, line, name, kind in records
            if kind == "guarded-optional"
        ]
        self.assertEqual(
            guarded,
            [
                ("test_api_http_integration.py", 83, "fastapi"),
                ("test_api_http_integration.py", 84, "fastapi"),
                ("test_api_http_integration.py", 86, "httpx"),
                ("test_live_envelope_validators.py", 61, "fastapi"),
            ],
        )

    def test_flags_undeclared_third_party_import(self):
        records = self.scan_source("import requests\n")
        self.assertEqual(
            [(Path(path).name, line, name, kind) for path, line, name, kind in records],
            [("test_synthetic.py", 1, "requests", "unclassified")],
        )

    def test_declared_local_and_relative_imports_are_accepted(self):
        sources = {
            "declared": "import yaml\n",
            "repo-local package": "from tests.support import anything\n",
            "repo-local namespace": "import scripts\n",
            "relative module": "from .support import helper\n",
            "relative bare": "from . import sibling\n",
        }
        for label, source in sources.items():
            with self.subTest(kind=label):
                records = self.scan_source(source)
                kinds = {kind for _path, _line, _name, kind in records}
                self.assertNotIn("unclassified", kinds)
                self.assertNotIn("guarded-optional", kinds)

    def test_guarded_optional_import_is_accepted(self):
        source = (
            "try:\n"
            "    import fastapi\n"
            "except ModuleNotFoundError:\n"
            "    fastapi = None\n"
        )
        records = self.scan_source(source)
        self.assertEqual([kind for _p, _l, _n, kind in records], ["guarded-optional"])

    def test_guard_must_catch_module_errors(self):
        source = "try:\n    import requests\nexcept ValueError:\n    requests = None\n"
        records = self.scan_source(source)
        self.assertEqual([kind for _p, _l, _n, kind in records], ["unclassified"])

    def test_guard_does_not_leak_into_handler_orelse_or_finally(self):
        source = (
            "try:\n"
            "    import fastapi\n"
            "except ModuleNotFoundError:\n"
            "    import requests\n"
            "else:\n"
            "    import flask\n"
            "finally:\n"
            "    import django\n"
        )
        kinds = {name: kind for _p, _l, name, kind in self.scan_source(source)}
        self.assertEqual(
            kinds,
            {
                "fastapi": "guarded-optional",  # try body: the guarded probe
                "requests": "unclassified",  # handler body: outside the guard
                "flask": "unclassified",  # orelse: runs only after a successful body
                "django": "unclassified",  # finalbody: always outside the guard
            },
        )

    def test_scan_fails_closed_on_unparsable_test_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "test_broken.py").write_text("def broken(:\n", encoding="utf-8")
            with self.assertRaises(RUN_TESTS.ImportScanError) as ctx:
                RUN_TESTS.scan_test_imports(tmp_path, ROOT)
        message = str(ctx.exception)
        self.assertIn("test_broken.py", message)
        self.assertIn(":1:", message)
        self.assertIn("does not parse", message)

    def test_main_fails_closed_on_unparsable_test_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "tests").mkdir()
            (tmp_path / "tests" / "test_broken.py").write_text("def broken(:\n", encoding="utf-8")
            with (
                mock.patch.object(RUN_TESTS, "ROOT", tmp_path),
                mock.patch.object(RUN_TESTS, "check_python_version", return_value=(True, "test")),
                mock.patch.object(RUN_TESTS, "ensure_declared_deps", return_value=(True, "test")),
            ):
                self.assertEqual(RUN_TESTS.main([]), 1)


class BatteryIdentityTests(unittest.TestCase):
    """Step 3: the script runs the exact quality-integration.yml battery."""

    def test_battery_commands_match_the_parsed_workflow(self):
        workflow_commands = workflow_battery_commands()
        self.assertEqual(len(workflow_commands), 2)
        for workflow_run, (_description, arguments) in zip(
            workflow_commands, RUN_TESTS.BATTERY_COMMANDS
        ):
            tokens = [token.strip("'") for token in workflow_run.split()]
            self.assertEqual(tokens[0], "python")  # CI invokes the bare interpreter
            self.assertEqual(tokens[1:], list(arguments))

    def test_battery_runs_both_commands_from_the_repo_root(self):
        calls: list[tuple[list[str], str | None]] = []

        def run(command, cwd=None, check=None):
            calls.append((list(command), cwd))
            return types.SimpleNamespace(returncode=0)

        self.assertEqual(RUN_TESTS.run_battery("python", run=run), 0)
        self.assertEqual(len(calls), 2)
        for (command, cwd), (_description, arguments) in zip(calls, RUN_TESTS.BATTERY_COMMANDS):
            self.assertEqual(command, ["python", *arguments])
            self.assertEqual(cwd, ROOT)

    def test_battery_stops_on_first_failure(self):
        calls: list[list[str]] = []

        def run(command, **_kwargs):
            calls.append(list(command))
            return types.SimpleNamespace(returncode=3)

        self.assertEqual(RUN_TESTS.run_battery("python", run=run), 3)
        self.assertEqual(len(calls), 1)


class ScriptHygieneTests(unittest.TestCase):
    """The script itself must stay stdlib-only (no third-party imports)."""

    def test_script_imports_are_stdlib_only(self):
        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(sorted(imported - set(sys.stdlib_module_names)), [])
