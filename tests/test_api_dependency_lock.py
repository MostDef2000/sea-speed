"""Canonical API dependency lockfile contract (issue #579) — RED-first tests.

The implementation does NOT exist on the base: there is no
``scripts/quality/validate_api_dependency_lock.py`` and no CI consumption
wiring. Every test in this module is therefore expected to FAIL or ERROR on
the base and to turn GREEN only once the admitted design lands.

Two contracts are pinned:

1. Validator CLI (T-1..T-8). The admitted contract is a stdlib-only CLI::

       python3 scripts/quality/validate_api_dependency_lock.py
           [--requirements PATH] [--lock PATH]

   Exit 0 = valid; exit 1 with a clear one-line message on stderr for each of
   the failure modes (missing/empty lock, wrong marker, uncovered pin,
   version drift, hash-less lock entry, malformed requirements line). The
   observable behaviour of a CLI is its exit code and stderr, so these tests
   EXECUTE the CLI via ``subprocess`` rather than importing an internal
   entry point (whose name is not part of the contract). That keeps the tests
   robust to the implementation's internal structure while still asserting the
   exact CLI surface. No skip is used for the validator: on the base the
   missing script yields a non-zero exit and a failing assertion.

2. CI consumption (T-9..T-14). The real workflow YAML files are parsed with
   ``yaml.safe_load`` and asserted structurally (comment-blind). These tests
   skip LOUDLY when PyYAML is unavailable, following the established pattern
   in ``tests/quality/test_quality_architecture.py`` (the stdlib-only
   property-fuzz job runs without it).

Fixtures are built at runtime in a temp dir under ``/tmp/opencode/579/``; no
network and no dependency on the real lock file for T-1..T-7.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# PyYAML is a test-only dependency (battery jobs install pyyaml==6.0.3). The
# stdlib-only property-fuzz job runs this module without it, so the
# yaml-consuming workflow tests skip LOUDLY there instead of breaking the
# import (same pattern as tests/quality/test_quality_architecture.py).
try:
    import yaml  # noqa: F401
    HAS_YAML = True
except ModuleNotFoundError:  # pragma: no cover - exercised by the stdlib-only CI job
    HAS_YAML = False

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts/quality/validate_api_dependency_lock.py"
WORKFLOWS = ROOT / ".github/workflows"

LOCK_MARKER = "# sea-speed-api-lock-v1"
API_REQUIREMENTS = ROOT / "api" / "requirements-api.txt"
API_LOCK = ROOT / "api" / "requirements-api.lock.txt"

# Scratch fixtures live here only (work-order constraint); auto-cleaned.
TMP_BASE = Path("/tmp/opencode/579")
TMP_BASE.mkdir(parents=True, exist_ok=True)

_HASH = "0" * 64  # a well-formed 64-char sha256 digest for fixtures


def _load_workflow(name: str) -> dict:
    """Parse a workflow YAML file into its structure (comment-blind)."""
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{name} did not parse to a mapping"
    return data


def _step_runs(workflow: dict) -> list[str]:
    """Every step ``run`` string across all jobs of a workflow."""
    runs: list[str] = []
    for job in (workflow.get("jobs") or {}).values():
        for step in (job or {}).get("steps") or []:
            run = step.get("run")
            if isinstance(run, str):
                runs.append(run)
    return runs


def _job_runs(job: dict) -> list[str]:
    runs: list[str] = []
    for step in (job or {}).get("steps") or []:
        run = step.get("run")
        if isinstance(run, str):
            runs.append(run)
    return runs


def _job_uses(job: dict) -> list[str]:
    uses: list[str] = []
    for step in (job or {}).get("steps") or []:
        uses_step = step.get("uses")
        if isinstance(uses_step, str):
            uses.append(uses_step)
    return uses


class ApiDependencyLockValidatorTests(unittest.TestCase):
    """Validator CLI contract (T-1..T-8). No skips: the validator must exist."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(dir=str(TMP_BASE))
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _write(self, name: str, content: str) -> Path:
        path = self.tmp / name
        path.write_text(content, encoding="utf-8")
        return path

    def _run_validator(self, requirements: Path, lock: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--requirements", str(requirements),
                "--lock", str(lock),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_valid_minimal_lock_and_pins_exit_zero(self) -> None:
        # T-1: a well-formed marker + a fully hashed, covered pin is valid.
        req = self._write("requirements.txt", "alpha==1.0.0\n")
        lock = self._write(
            "lock.txt",
            f"{LOCK_MARKER}\n"
            "alpha==1.0.0 \\\n"
            f"    --hash=sha256:{_HASH}\n"
            "    # via -r requirements.txt\n",
        )
        result = self._run_validator(req, lock)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_missing_marker_first_line_exit_one(self) -> None:
        # T-2: first line must be exactly the marker.
        req = self._write("requirements.txt", "alpha==1.0.0\n")
        lock = self._write(
            "lock.txt",
            "# some other header\n"
            "alpha==1.0.0 \\\n"
            f"    --hash=sha256:{_HASH}\n",
        )
        result = self._run_validator(req, lock)
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertTrue(result.stderr.strip(), "expected a stderr message")

    def test_pin_name_absent_from_lock_exit_one(self) -> None:
        # T-3: a requirements pin whose name is not in the lock is uncovered.
        req = self._write("requirements.txt", "alpha==1.0.0\nbeta==2.0.0\n")
        lock = self._write(
            "lock.txt",
            f"{LOCK_MARKER}\n"
            "alpha==1.0.0 \\\n"
            f"    --hash=sha256:{_HASH}\n",
        )
        result = self._run_validator(req, lock)
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertTrue(result.stderr.strip(), "expected a stderr message")

    def test_pin_version_mismatch_exit_one(self) -> None:
        # T-4: a pin whose version differs from the lock entry is a drift.
        req = self._write("requirements.txt", "alpha==1.0.0\n")
        lock = self._write(
            "lock.txt",
            f"{LOCK_MARKER}\n"
            "alpha==1.0.1 \\\n"
            f"    --hash=sha256:{_HASH}\n",
        )
        result = self._run_validator(req, lock)
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertTrue(result.stderr.strip(), "expected a stderr message")

    def test_locked_package_without_hash_exit_one(self) -> None:
        # T-5: a locked package entry with zero --hash lines is invalid.
        req = self._write("requirements.txt", "alpha==1.0.0\n")
        lock = self._write(
            "lock.txt",
            f"{LOCK_MARKER}\n"
            "alpha==1.0.0\n",
        )
        result = self._run_validator(req, lock)
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertTrue(result.stderr.strip(), "expected a stderr message")

    def test_malformed_requirements_line_exit_one(self) -> None:
        # T-6: a non-comment, non-empty requirements line that is not
        # name==version is malformed.
        req = self._write("requirements.txt", "foo\n")
        lock = self._write(
            "lock.txt",
            f"{LOCK_MARKER}\n"
            "foo==1.0.0 \\\n"
            f"    --hash=sha256:{_HASH}\n",
        )
        result = self._run_validator(req, lock)
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertTrue(result.stderr.strip(), "expected a stderr message")

    def test_missing_lock_file_exit_one(self) -> None:
        # T-7: a missing (or empty) lock file is invalid.
        req = self._write("requirements.txt", "alpha==1.0.0\n")
        missing_lock = self.tmp / "does-not-exist.lock.txt"
        result = self._run_validator(req, missing_lock)
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertTrue(result.stderr.strip(), "expected a stderr message")

    def test_real_repo_files_exit_zero(self) -> None:
        # T-8: the real repo requirements + lock exist and validate clean.
        # RED on the base: neither file nor the validator exists yet.
        self.assertTrue(API_REQUIREMENTS.is_file(), "api/requirements-api.txt missing")
        self.assertTrue(API_LOCK.is_file(), "api/requirements-api.lock.txt missing")
        result = self._run_validator(API_REQUIREMENTS, API_LOCK)
        self.assertEqual(result.returncode, 0, msg=result.stderr)


@unittest.skipUnless(
    HAS_YAML,
    "PyYAML not installed (stdlib-only property-fuzz job); battery jobs run these workflow-contract tests",
)
class ApiDependencyLockCiConsumptionTests(unittest.TestCase):
    """CI consumption contract (T-9..T-14) against the real workflow YAML."""

    def test_quality_integration_installs_from_api_lock(self) -> None:
        # T-9: a step pip-installs from the canonical API lock file.
        runs = _step_runs(_load_workflow("quality-integration.yml"))
        self.assertTrue(
            any("pip install" in r and "api/requirements-api.lock.txt" in r for r in runs),
            "no step pip-installs from api/requirements-api.lock.txt",
        )

    def test_quality_integration_has_no_inline_tool_pins(self) -> None:
        # T-10: the inline ruff==/mypy==/pyyaml== pins are gone.
        runs = _step_runs(_load_workflow("quality-integration.yml"))
        for banned in ("pip install ruff==", "pip install mypy==", "pip install pyyaml=="):
            self.assertFalse(
                any(banned in r for r in runs),
                f"inline pin still present: {banned}",
            )

    def test_quality_integration_ruff_strict_step_on_validator(self) -> None:
        # T-11: a ruff strict step runs ruff.strict.toml over the validator.
        runs = _step_runs(_load_workflow("quality-integration.yml"))
        self.assertTrue(
            any(
                "ruff check --config scripts/quality/ruff.strict.toml" in r
                and "scripts/quality/validate_api_dependency_lock.py" in r
                for r in runs
            ),
            "no ruff strict step over the validator module",
        )

    def test_quality_integration_mypy_includes_validator(self) -> None:
        # T-12: the mypy invocation lists the validator module.
        runs = _step_runs(_load_workflow("quality-integration.yml"))
        self.assertTrue(
            any(
                "mypy" in r and "scripts/quality/validate_api_dependency_lock.py" in r
                for r in runs
            ),
            "mypy invocation does not include the validator module",
        )

    def test_security_pip_audits_api_requirements(self) -> None:
        # T-13: security.yml pip-audits the API requirements file.
        runs = _step_runs(_load_workflow("security.yml"))
        self.assertTrue(
            any("pip-audit" in r and "api/requirements-api.txt" in r for r in runs),
            "no pip-audit step for api/requirements-api.txt",
        )

    def test_resolve_runtime_lock_has_api_lock_job(self) -> None:
        # T-14: a job compiles the API requirements with --generate-hashes,
        # prepends the API marker, and uploads the lock as an artifact.
        workflow = _load_workflow("resolve-runtime-lock.yml")
        found = False
        for job in (workflow.get("jobs") or {}).values():
            runs = "\n".join(_job_runs(job))
            uses = "\n".join(_job_uses(job))
            if (
                "uv pip compile" in runs
                and "--generate-hashes" in runs
                and "api/requirements-api.txt" in runs
                and LOCK_MARKER in runs
                and "upload-artifact" in uses
            ):
                found = True
                break
        self.assertTrue(
            found,
            "no job resolves the API lock (uv pip compile --generate-hashes "
            "+ marker + artifact upload)",
        )


if __name__ == "__main__":
    unittest.main()
