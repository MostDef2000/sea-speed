"""Repo-owned token pre-flight probe contract (issue #583) — RED-first tests.

The implementation does NOT exist on the base: there is no
``scripts/quality/validate_token_preflight.py``, no
``data/contracts/token-inventory-v1.json``, no
``.github/workflows/token-preflight.yml``, no quality-integration step, no
mypy strict section, and no ``specs/583-token-preflight`` trio or
``docs/operations/TOKEN_PREFLIGHT.md`` runbook. Every test in this module that
targets one of those artifacts is therefore expected to FAIL or ERROR on the
base and to turn GREEN only once the admitted design lands.

The binding contract pinned here (clauses C1..C6):

C1. ``data/contracts/token-inventory-v1.json`` — schema
    ``sea-speed-token-inventory/v1`` with exactly three contracted token
    identities (name / kind / expiry_status / expiry / review_date / probe).

C2. ``scripts/quality/validate_token_preflight.py`` — stdlib-only CLI
    (``--inventory``, ``--today``, ``--probe``; ``--today`` + ``--probe`` is a
    usage error, exit 2). Offline mode does schema validation + date
    evaluation only (no network, no credential env reads, no host file reads).
    ``WARNING_DAYS = 21``. Probe mode reads the credential env var named by
    ``credential_pointer`` and performs a single ``GET https://api.github.com/zen``
    with a Bearer header, fixed User-Agent, 10s timeout, redirects disabled,
    TLS verified; 200 -> PROBE-OK, 401 -> PROBE-UNAUTHORIZED, 403 ->
    PROBE-FORBIDDEN, 5xx/network/timeout -> retry (3 attempts, sleep 1s then
    2s), any other status -> fail, no retry. Output is one line per finding
    (``<MARKER>: <token-name> <short safe detail>``), ERROR lines to stderr,
    info/WARN to stdout, final line exactly ``TOKEN-PREFLIGHT PASS`` or
    ``TOKEN-PREFLIGHT FAIL``; exit 0 pass / 1 fail / 2 usage. In ``--probe``
    mode a ``GITHUB_STEP_SUMMARY`` section is appended on PASS and FAIL; an
    unwritable summary path is ``SUMMARY-WRITE-FAILED`` + exit 1. The tests
    patch only the transport and env seams: ``fetch_status`` and ``time.sleep``
    (probe/retry tests), ``urllib.request.build_opener`` and
    ``urllib.request.urlopen`` (transport tests), and ``os.getenv`` /
    ``os.environ.get`` (offline env-read test). ``load_inventory``,
    ``evaluate_dates``, ``probe_token`` and ``main`` are called, not patched.

C3. ``.github/workflows/token-preflight.yml`` — weekly (cron ``17 9 * * 2``) +
    dispatch, ``contents: read``, main-only guard, ubuntu-latest, 5-minute
    timeout, pinned checkout (persist-credentials false) + setup-python 3.14,
    runs ``python scripts/quality/validate_token_preflight.py --probe``, and
    references NO ``secrets.`` anywhere.

C4. quality-integration.yml — a new step "Validate token inventory and dates"
    between "Validate repository and canonical contracts" and "Validate JSON
    and Python syntax"; the ruff strict invocation and the mypy invocation both
    list the new validator module.

C5. ``scripts/quality/mypy.ini`` — a ``[mypy-scripts.quality.validate_token_preflight]``
    section with ``strict = True``.

C6. ``specs/583-token-preflight/{spec,plan,tasks}.md`` and
    ``docs/operations/TOKEN_PREFLIGHT.md`` exist (structural markers only;
    ``validate_sdd.py`` enforces the rest).

Test strategy (mirrors ``tests/test_api_dependency_lock.py``):

* The validator is loaded by file path via
  ``importlib.util.spec_from_file_location`` so the tests are robust to package
  layout. On the base the file is absent, so the load seam raises ImportError —
  the expected RED failure mode for every module-dependent test.
* Unit tests patch ``fetch_status`` (and ``sleep``) on the loaded module to pin
  the probe/retry/credential-handling behaviour with zero network.
* Transport tests patch the urllib opener to pin the fixed URL, Bearer header,
  timeout, redirect rejection, and response closure of ``fetch_status``.
* Subprocess tests cover ONLY the offline CLI surface (valid inventory with
  ``--today``, malformed inventory, the ``--today`` + ``--probe`` usage error,
  and the committed default inventory). They assert exact exit codes AND marker
  strings, never a bare nonzero.
* Structural tests parse the real YAML/JSON with ``yaml.safe_load`` /
  ``json.loads`` and assert the contracted shape. They skip LOUDLY when PyYAML
  is unavailable (the stdlib-only property-fuzz job); PyYAML 6.0.3 is present in
  the battery jobs, so they RUN there.

Fixtures are built at runtime in a temp dir under ``/tmp/opencode/583/``. No
test touches the network. Synthetic credential strings are constructed at
runtime (never a literal) and asserted to never leak into stdout/stderr/summary.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest import mock

# PyYAML is a test-only dependency (battery jobs install pyyaml==6.0.3). The
# stdlib-only property-fuzz job runs this module without it, so the
# yaml-consuming structural tests skip LOUDLY there instead of breaking the
# import (same pattern as tests/test_api_dependency_lock.py).
try:
    import yaml  # noqa: F401
    HAS_YAML = True
except ModuleNotFoundError:  # pragma: no cover - exercised by the stdlib-only CI job
    HAS_YAML = False

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts/quality/validate_token_preflight.py"
INVENTORY = ROOT / "data/contracts/token-inventory-v1.json"
WORKFLOWS = ROOT / ".github/workflows"
TOKEN_PREFLIGHT_WORKFLOW = WORKFLOWS / "token-preflight.yml"
QUALITY_INTEGRATION_WORKFLOW = WORKFLOWS / "quality-integration.yml"
MYPY_INI = ROOT / "scripts/quality/mypy.ini"
SDD_DIR = ROOT / "specs/583-token-preflight"
RUNBOOK = ROOT / "docs/operations/TOKEN_PREFLIGHT.md"
WORKFLOW_POLICY = ROOT / "scripts/quality/validate_workflow_policy.py"

# Scratch fixtures live here only (work-order constraint); auto-cleaned.
TMP_BASE = Path("/tmp/opencode/583")
TMP_BASE.mkdir(parents=True, exist_ok=True)

SCHEMA = "sea-speed-token-inventory/v1"
WARNING_DAYS = 21
ZEN_URL = "https://api.github.com/zen"
CHECKOUT_PIN = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"
SETUP_PYTHON_PIN = "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065"
PROBE_RUN_COMMAND = "python scripts/quality/validate_token_preflight.py --probe"
NEW_STEP_NAME = "Validate token inventory and dates"
ANCHOR_BEFORE = "Validate repository and canonical contracts"
ANCHOR_AFTER = "Validate JSON and Python syntax"
API_LOCK_VALIDATOR = "scripts/quality/validate_api_dependency_lock.py"
TOKEN_VALIDATOR = "scripts/quality/validate_token_preflight.py"

TOKEN_KEYS = {
    "name", "kind", "expiry_status", "expiry", "review_date",
    "probe", "credential_pointer", "expected_scopes", "note",
}

# The three contracted token identities (C1): name -> contracted fields.
EXPECTED_TOKENS: dict[str, dict[str, Any]] = {
    "sea-speed-worker-quality-read": {
        "kind": "classic",
        "expiry_status": "no-expiry",
        "expiry": None,
        "review_date": "2027-04-14",
        "probe": "none",
    },
    "sea-speed-opencode-connector": {
        "kind": "classic",
        "expiry_status": "dated",
        "expiry": "2026-12-31",
        "review_date": None,
        "probe": "none",
    },
    "SYNC_PR_TOKEN": {
        "kind": "fine-grained",
        "expiry_status": "unknown",
        "expiry": None,
        "review_date": None,
        "probe": "none",
    },
}


def _load_validator_module():
    """Load the validator by file path (robust to package layout).

    Raises ImportError on the base (file absent) — the expected RED failure
    mode for every module-dependent test.
    """
    if not VALIDATOR.is_file():
        raise ImportError(f"validator module missing: {VALIDATOR}")
    spec = importlib.util.spec_from_file_location("validate_token_preflight_583", VALIDATOR)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot create import spec for {VALIDATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    VALIDATOR_MODULE = _load_validator_module()
except Exception:  # noqa: BLE001 - RED phase: any load failure means "not implemented"
    VALIDATOR_MODULE = None


def _synthetic_credential(prefix: str = "ghp_") -> str:
    """Build a synthetic credential at runtime (never a literal in source)."""
    return prefix + "x" * 36


def _probe_inventory(credential_env: str = "TEST_PROBE_TOKEN", review_date: str = "2099-01-01") -> dict:
    """A minimal valid inventory with a single api-zen entry and OK dates."""
    return {
        "schema": SCHEMA,
        "tokens": [
            {
                "name": "probe-token",
                "kind": "classic",
                "expiry_status": "no-expiry",
                "expiry": None,
                "review_date": review_date,
                "probe": "api-zen",
                "credential_pointer": credential_env,
                "expected_scopes": None,
                "note": "probe test entry",
            }
        ],
    }


def _none_probe_inventory() -> dict:
    """A minimal valid inventory whose only entry is probe: none."""
    return {
        "schema": SCHEMA,
        "tokens": [
            {
                "name": "none-token",
                "kind": "classic",
                "expiry_status": "no-expiry",
                "expiry": None,
                "review_date": "2099-01-01",
                "probe": "none",
                "credential_pointer": None,
                "expected_scopes": None,
                "note": "not-probed test entry",
            }
        ],
    }


def _dated_inventory(name: str, expiry_status: str, expiry: str | None, review_date: str | None) -> dict:
    """A minimal valid inventory with a single probe:none entry and given dates.

    ``expiry_status``/``expiry``/``review_date`` must satisfy the schema
    invariants (dated -> non-null expiry; no-expiry -> null expiry + non-null
    review_date; unknown -> null expiry) so the date evaluation is the only
    thing under test.
    """
    return {
        "schema": SCHEMA,
        "tokens": [
            {
                "name": name,
                "kind": "classic",
                "expiry_status": expiry_status,
                "expiry": expiry,
                "review_date": review_date,
                "probe": "none",
                "credential_pointer": None,
                "expected_scopes": None,
                "note": "date matrix test entry",
            }
        ],
    }


def _request_header(request: urllib.request.Request, name: str) -> str | None:
    """Case-insensitive header lookup on a urllib Request."""
    for key, value in request.headers.items():
        if key.lower() == name.lower():
            return value
    return None


class _FakeResponse:
    """A context-manager stand-in for an HTTP response (tracks closure)."""

    def __init__(self, status: int) -> None:
        self.status = status
        self.closed = False
        self._body = b""

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        self.close()
        return False

    def close(self) -> None:
        self.closed = True


class _FakeOpener:
    """A stand-in for a urllib OpenerDirector that records every open() call.

    Mimics a no-redirect opener: 3xx raises HTTPError (no follow), 4xx/5xx
    raise HTTPError, 2xx returns a _FakeResponse.
    """

    def __init__(self, status: int = 200, network_error: Exception | None = None) -> None:
        self.status = status
        self.network_error = network_error
        self.calls: list[tuple[Any, Any]] = []
        self.last_response: _FakeResponse | None = None

    def open(self, request: Any, timeout: Any = None, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((request, timeout))
        if self.network_error is not None:
            raise self.network_error
        status = self.status
        if 300 <= status < 400:
            raise urllib.error.HTTPError(request.full_url, status, "redirect", {}, None)
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "error", {}, io.BytesIO(b""))
        response = _FakeResponse(status)
        self.last_response = response
        return response


class _ValidatorModuleMixin(unittest.TestCase):
    """Base for module-dependent tests: ERROR with ImportError on the base."""

    def setUp(self) -> None:
        super().setUp()
        if VALIDATOR_MODULE is None:
            raise ImportError(
                "scripts/quality/validate_token_preflight.py is missing or "
                "unloadable (RED phase); the validator module cannot be imported"
            )
        self.validator = VALIDATOR_MODULE
        self._tmp = tempfile.TemporaryDirectory(dir=str(TMP_BASE))
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _write_inventory(self, data: dict, name: str = "inventory.json") -> Path:
        path = self.tmp / name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def _run_main(self, argv: list[str], set_env: dict | None = None, unset: tuple = ()) -> tuple[int, str, str]:
        """Run validator.main(argv) with controlled env; return (code, out, err)."""
        stdout = io.StringIO()
        stderr = io.StringIO()
        saved: dict[str, str | None] = {}
        for name in unset:
            if name in os.environ:
                saved[name] = os.environ[name]
                del os.environ[name]
        try:
            for name, value in (set_env or {}).items():
                saved.setdefault(name, os.environ.get(name))
                os.environ[name] = value
            with redirect_stdout(stdout), redirect_stderr(stderr):
                try:
                    code = self.validator.main(argv)
                except SystemExit as exc:
                    code = exc.code if exc.code is not None else 0
        finally:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        return int(code), stdout.getvalue(), stderr.getvalue()

    def _patch_probe_seams(self, fetch_status_side_effect: Any = None, fetch_status_return: Any = None):
        """Patch fetch_status + sleep on the loaded module; return (fetch, sleep)."""
        fetch_mock = mock.Mock()
        if fetch_status_side_effect is not None:
            fetch_mock.side_effect = fetch_status_side_effect
        else:
            fetch_mock.return_value = fetch_status_return
        p_fetch = mock.patch.object(self.validator, "fetch_status", fetch_mock)
        p_fetch.start()
        self.addCleanup(p_fetch.stop)
        sleep_mock = mock.Mock()
        p_sleep = mock.patch("time.sleep", sleep_mock)
        p_sleep.start()
        self.addCleanup(p_sleep.stop)
        if hasattr(self.validator, "sleep"):
            p_mod_sleep = mock.patch.object(self.validator, "sleep", sleep_mock)
            p_mod_sleep.start()
            self.addCleanup(p_mod_sleep.stop)
        return fetch_mock, sleep_mock

    def _assert_no_secret_leak(self, stdout: str, stderr: str, secret: str, summary_text: str = "") -> None:
        for stream_name, text in (("stdout", stdout), ("stderr", stderr), ("summary", summary_text)):
            self.assertNotIn(secret, text, f"synthetic credential leaked into {stream_name}")


class TokenPreflightInventoryTests(unittest.TestCase):
    """C1: the committed token inventory file and its contracted identities."""

    def test_inventory_file_exists(self) -> None:
        self.assertTrue(INVENTORY.is_file(), f"missing inventory: {INVENTORY}")

    def test_inventory_schema_and_root_keys(self) -> None:
        data = json.loads(INVENTORY.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)
        self.assertEqual(set(data.keys()), {"schema", "tokens"})
        self.assertEqual(data["schema"], SCHEMA)
        self.assertIsInstance(data["tokens"], list)
        self.assertTrue(data["tokens"], "tokens list must be non-empty")

    def test_inventory_has_exactly_the_three_contracted_identities(self) -> None:
        data = json.loads(INVENTORY.read_text(encoding="utf-8"))
        tokens = data["tokens"]
        self.assertEqual(len(tokens), 3, "expected exactly three contracted tokens")
        names = [t.get("name") for t in tokens]
        self.assertEqual(set(names), set(EXPECTED_TOKENS.keys()), f"unexpected token names: {names}")
        for token in tokens:
            self.assertEqual(set(token.keys()), TOKEN_KEYS, f"token {token.get('name')} has wrong keys")
            expected = EXPECTED_TOKENS[token["name"]]
            for field, value in expected.items():
                self.assertEqual(token[field], value, f"token {token['name']}.{field} mismatch")


@unittest.skipUnless(
    HAS_YAML,
    "PyYAML not installed (stdlib-only property-fuzz job); battery jobs run these workflow-contract tests",
)
class TokenPreflightWorkflowTests(unittest.TestCase):
    """C3: the token-preflight.yml workflow structure."""

    def _workflow(self) -> dict:
        data = yaml.safe_load(TOKEN_PREFLIGHT_WORKFLOW.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "token-preflight.yml did not parse to a mapping"
        return data

    def _triggers(self, workflow: dict) -> dict:
        # YAML 1.1 parses a bare `on:` key as boolean True; handle both.
        return workflow.get(True, workflow.get("on", {})) or {}

    def _job(self, workflow: dict) -> dict:
        jobs = workflow.get("jobs") or {}
        self.assertEqual(len(jobs), 1, "expected exactly one job")
        return next(iter(jobs.values()))

    def test_workflow_name(self) -> None:
        self.assertEqual(self._workflow().get("name"), "Token pre-flight")

    def test_schedule_cron_exact(self) -> None:
        triggers = self._triggers(self._workflow())
        schedule = triggers.get("schedule") or []
        crons = [entry.get("cron") for entry in schedule if isinstance(entry, dict)]
        self.assertIn("17 9 * * 2", crons, f"schedule cron not pinned to '17 9 * * 2': {crons}")

    def test_workflow_dispatch_present(self) -> None:
        triggers = self._triggers(self._workflow())
        self.assertIn("workflow_dispatch", triggers, "workflow_dispatch trigger missing")

    def test_permissions_contents_read_only(self) -> None:
        self.assertEqual(self._workflow().get("permissions"), {"contents": "read"})

    def test_job_main_only_guard(self) -> None:
        job = self._job(self._workflow())
        self.assertEqual(job.get("if"), "github.ref == 'refs/heads/main'")

    def test_job_runs_on_and_timeout(self) -> None:
        job = self._job(self._workflow())
        self.assertEqual(job.get("runs-on"), "ubuntu-latest")
        self.assertEqual(job.get("timeout-minutes"), 5)

    def test_checkout_pinned_no_credentials(self) -> None:
        job = self._job(self._workflow())
        checkout = next(
            (s for s in job.get("steps", []) if s.get("uses") == CHECKOUT_PIN), None,
        )
        self.assertIsNotNone(checkout, f"checkout step not pinned to {CHECKOUT_PIN}")
        self.assertEqual((checkout or {}).get("with", {}).get("persist-credentials"), False)

    def test_setup_python_pinned_3_14(self) -> None:
        job = self._job(self._workflow())
        setup = next(
            (s for s in job.get("steps", []) if s.get("uses") == SETUP_PYTHON_PIN), None,
        )
        self.assertIsNotNone(setup, f"setup-python step not pinned to {SETUP_PYTHON_PIN}")
        self.assertEqual((setup or {}).get("with", {}).get("python-version"), "3.14")

    def test_run_command_exact(self) -> None:
        job = self._job(self._workflow())
        runs = [s.get("run") for s in job.get("steps", []) if isinstance(s.get("run"), str)]
        self.assertIn(PROBE_RUN_COMMAND, runs, f"probe run command missing: {runs}")

    def test_no_secrets_reference_anywhere(self) -> None:
        source = TOKEN_PREFLIGHT_WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("secrets.", source, "token-preflight.yml must not reference any secrets.")


@unittest.skipUnless(
    HAS_YAML,
    "PyYAML not installed (stdlib-only property-fuzz job); battery jobs run these workflow-contract tests",
)
class TokenPreflightQualityIntegrationTests(unittest.TestCase):
    """C4: the quality-integration.yml edits (new step + ruff/mypy listings)."""

    def _workflow(self) -> dict:
        data = yaml.safe_load(QUALITY_INTEGRATION_WORKFLOW.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "quality-integration.yml did not parse to a mapping"
        return data

    def _step_names(self, job: dict) -> list[str]:
        return [s.get("name") for s in job.get("steps", []) if isinstance(s.get("name"), str)]

    def _step_runs(self, workflow: dict) -> list[str]:
        runs: list[str] = []
        for job in (workflow.get("jobs") or {}).values():
            for step in (job or {}).get("steps") or []:
                run = step.get("run")
                if isinstance(run, str):
                    runs.append(run)
        return runs

    def test_new_step_present_and_positioned(self) -> None:
        workflow = self._workflow()
        job = (workflow.get("jobs") or {}).get("static-contract-security")
        self.assertIsNotNone(job, "static-contract-security job missing")
        names = self._step_names(job)
        self.assertIn(NEW_STEP_NAME, names, f"new step {NEW_STEP_NAME!r} missing")
        self.assertIn(ANCHOR_BEFORE, names, f"anchor step {ANCHOR_BEFORE!r} missing")
        self.assertIn(ANCHOR_AFTER, names, f"anchor step {ANCHOR_AFTER!r} missing")
        self.assertGreater(
            names.index(NEW_STEP_NAME), names.index(ANCHOR_BEFORE),
            f"{NEW_STEP_NAME!r} must come after {ANCHOR_BEFORE!r}",
        )
        self.assertLess(
            names.index(NEW_STEP_NAME), names.index(ANCHOR_AFTER),
            f"{NEW_STEP_NAME!r} must come before {ANCHOR_AFTER!r}",
        )

    def test_new_step_runs_offline_validator(self) -> None:
        workflow = self._workflow()
        job = (workflow.get("jobs") or {}).get("static-contract-security") or {}
        step = next(
            (s for s in job.get("steps", []) if s.get("name") == NEW_STEP_NAME), None,
        )
        self.assertIsNotNone(step, f"new step {NEW_STEP_NAME!r} missing")
        run = (step or {}).get("run")
        self.assertIsInstance(run, str)
        self.assertIn("python scripts/quality/validate_token_preflight.py", run)
        self.assertNotIn("--probe", run, "the quality-integration step must run offline (no --probe)")

    def test_ruff_strict_lists_both_validators(self) -> None:
        runs = self._step_runs(self._workflow())
        self.assertTrue(
            any(
                "ruff check --config scripts/quality/ruff.strict.toml" in r
                and API_LOCK_VALIDATOR in r
                and TOKEN_VALIDATOR in r
                for r in runs
            ),
            "ruff strict invocation does not list both validator modules",
        )

    def test_mypy_lists_both_validators(self) -> None:
        runs = self._step_runs(self._workflow())
        self.assertTrue(
            any(
                "mypy" in r and API_LOCK_VALIDATOR in r and TOKEN_VALIDATOR in r
                for r in runs
            ),
            "mypy invocation does not list both validator modules",
        )


class TokenPreflightMypyTests(unittest.TestCase):
    """C5: the mypy strict section for the new validator module."""

    def test_mypy_strict_section_present(self) -> None:
        self.assertTrue(MYPY_INI.is_file(), f"missing mypy config: {MYPY_INI}")
        source = MYPY_INI.read_text(encoding="utf-8")
        self.assertIn("[mypy-scripts.quality.validate_token_preflight]", source)
        # The section must set strict = True.
        section = source.split("[mypy-scripts.quality.validate_token_preflight]", 1)
        self.assertEqual(len(section), 2, "strict section header not found")
        self.assertIn("strict = True", section[1])


class TokenPreflightSddTests(unittest.TestCase):
    """C6: the SDD trio and the operations runbook exist with key markers."""

    def test_sdd_trio_exists(self) -> None:
        for name in ("spec.md", "plan.md", "tasks.md"):
            self.assertTrue((SDD_DIR / name).is_file(), f"missing SDD artifact: {SDD_DIR / name}")

    def test_spec_issue_marker(self) -> None:
        spec = (SDD_DIR / "spec.md").read_text(encoding="utf-8")
        self.assertIn("- Issue: #583", spec)

    def test_plan_risk_marker(self) -> None:
        plan = (SDD_DIR / "plan.md").read_text(encoding="utf-8")
        self.assertIn("- Risk profile: REQUIRED", plan)

    def test_runbook_exists(self) -> None:
        self.assertTrue(RUNBOOK.is_file(), f"missing runbook: {RUNBOOK}")


class TokenPreflightWorkflowPolicyTests(unittest.TestCase):
    """The generic workflow policy accepts all workflows incl. the new one."""

    def test_workflow_policy_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, str(WORKFLOW_POLICY)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")


class TokenPreflightValidatorOfflineSubprocessTests(unittest.TestCase):
    """C2 offline CLI surface via subprocess (no --probe). RED: validator absent."""

    def _run(self, argv: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), *argv],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def _write(self, data: dict, name: str = "inventory.json") -> Path:
        path = TMP_BASE / name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def test_offline_valid_inventory_pass(self) -> None:
        # A valid inventory with all dates OK -> exit 0 + PASS marker.
        inventory = _probe_inventory()  # api-zen entry, but offline mode never probes it
        path = self._write(inventory, "offline-valid.json")
        result = self._run(["--inventory", str(path), "--today", "2026-11-03"])
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn("TOKEN-PREFLIGHT PASS", combined)

    def test_offline_default_inventory_pass(self) -> None:
        # The committed default inventory validates clean on a date where all
        # entries are OK (RED: the file and the validator are both absent).
        result = self._run(["--today", "2026-11-03"])
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn("TOKEN-PREFLIGHT PASS", combined)

    def test_offline_malformed_inventory_fail(self) -> None:
        # A wrong schema value is a validation failure -> exit 1 + FAIL marker.
        inventory = _probe_inventory()
        inventory["schema"] = "wrong-schema"
        path = self._write(inventory, "offline-malformed.json")
        result = self._run(["--inventory", str(path), "--today", "2026-11-03"])
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn("TOKEN-PREFLIGHT FAIL", combined)

    def test_usage_error_today_and_probe(self) -> None:
        # --today combined with --probe is a usage error -> exit 2 with a
        # usage-error message. (On the base the validator is absent and Python
        # also exits 2 with "can't open file", so the marker assertion is what
        # makes this test RED: a file-not-found message carries no usage marker.)
        result = self._run(["--today", "2026-11-03", "--probe"])
        self.assertEqual(result.returncode, 2, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        stderr_lower = result.stderr.lower()
        self.assertTrue(
            any(marker in stderr_lower for marker in ("probe", "usage", "today", "error")),
            f"expected a usage-error message about --today/--probe on stderr, got: {result.stderr!r}",
        )


class TokenPreflightValidatorOfflineUnitTests(_ValidatorModuleMixin):
    """C2 offline mode: schema + dates only, never probing or reading env."""

    def test_offline_never_calls_fetch_status_or_reads_credential_env(self) -> None:
        inventory = _probe_inventory(credential_env="TEST_PROBE_TOKEN")
        path = self._write_inventory(inventory)
        os.environ["TEST_PROBE_TOKEN"] = _synthetic_credential()
        self.addCleanup(lambda: os.environ.pop("TEST_PROBE_TOKEN", None))

        fetch_mock, _ = self._patch_probe_seams(fetch_status_return=200)
        accessed: list[str] = []
        real_getenv = os.getenv
        real_environ_get = os.environ.get

        def recording_getenv(name, *a, **k):
            accessed.append(name)
            return real_getenv(name, *a, **k)

        def recording_environ_get(name, *a, **k):
            accessed.append(name)
            return real_environ_get(name, *a, **k)

        with mock.patch("os.getenv", side_effect=recording_getenv), \
             mock.patch.object(os.environ, "get", side_effect=recording_environ_get):
            code, stdout, stderr = self._run_main(
                ["--inventory", str(path), "--today", "2026-11-03"],
            )
        combined = stdout + stderr
        self.assertEqual(code, 0, msg=combined)
        self.assertIn("TOKEN-PREFLIGHT PASS", combined)
        self.assertEqual(fetch_mock.call_count, 0, "offline mode must never call fetch_status")
        self.assertNotIn("TEST_PROBE_TOKEN", accessed, "offline mode must not read the credential env var")


class TokenPreflightProbeUnitTests(_ValidatorModuleMixin):
    """C2 probe mode: credential handling, status mapping, retry policy."""

    def _probe_run(self, inventory: dict, set_env: dict | None, fetch_status_side_effect=None, fetch_status_return=None):
        path = self._write_inventory(inventory)
        fetch_mock, sleep_mock = self._patch_probe_seams(
            fetch_status_side_effect=fetch_status_side_effect,
            fetch_status_return=fetch_status_return,
        )
        code, stdout, stderr = self._run_main(
            ["--probe", "--inventory", str(path)],
            set_env=set_env,
            unset=("GITHUB_STEP_SUMMARY",),
        )
        return code, stdout, stderr, fetch_mock, sleep_mock

    def test_probe_ok(self) -> None:
        cred = _synthetic_credential()
        code, stdout, stderr, fetch_mock, _ = self._probe_run(
            _probe_inventory(), {"TEST_PROBE_TOKEN": cred}, fetch_status_return=200,
        )
        combined = stdout + stderr
        self.assertEqual(code, 0, msg=combined)
        self.assertIn("PROBE-OK", combined)
        self.assertIn("TOKEN-PREFLIGHT PASS", combined)
        self.assertEqual(fetch_mock.call_count, 1)
        self._assert_no_secret_leak(stdout, stderr, cred)

    def test_probe_unauthorized_no_retry(self) -> None:
        cred = _synthetic_credential()
        code, stdout, stderr, fetch_mock, _ = self._probe_run(
            _probe_inventory(), {"TEST_PROBE_TOKEN": cred}, fetch_status_return=401,
        )
        combined = stdout + stderr
        self.assertEqual(code, 1, msg=combined)
        self.assertIn("PROBE-UNAUTHORIZED", combined)
        self.assertIn("TOKEN-PREFLIGHT FAIL", combined)
        self.assertEqual(fetch_mock.call_count, 1, "401 must not retry")
        self._assert_no_secret_leak(stdout, stderr, cred)

    def test_probe_forbidden_no_retry(self) -> None:
        cred = _synthetic_credential()
        code, stdout, stderr, fetch_mock, _ = self._probe_run(
            _probe_inventory(), {"TEST_PROBE_TOKEN": cred}, fetch_status_return=403,
        )
        combined = stdout + stderr
        self.assertEqual(code, 1, msg=combined)
        self.assertIn("PROBE-FORBIDDEN", combined)
        self.assertIn("TOKEN-PREFLIGHT FAIL", combined)
        self.assertEqual(fetch_mock.call_count, 1, "403 must not retry")
        self._assert_no_secret_leak(stdout, stderr, cred)

    def test_probe_retry_on_5xx_then_fail(self) -> None:
        cred = _synthetic_credential()
        code, stdout, stderr, fetch_mock, sleep_mock = self._probe_run(
            _probe_inventory(), {"TEST_PROBE_TOKEN": cred}, fetch_status_side_effect=[500, 500, 500],
        )
        combined = stdout + stderr
        self.assertEqual(code, 1, msg=combined)
        self.assertIn("TOKEN-PREFLIGHT FAIL", combined)
        self.assertEqual(fetch_mock.call_count, 3, "5xx must retry to 3 attempts total")
        sleep_values = [float(c.args[0]) for c in sleep_mock.call_args_list if c.args]
        self.assertEqual(sleep_values, [1.0, 2.0], "retry must sleep 1s then 2s")
        self._assert_no_secret_leak(stdout, stderr, cred)

    def test_probe_retry_on_network_error_then_fail(self) -> None:
        cred = _synthetic_credential()
        code, stdout, stderr, fetch_mock, sleep_mock = self._probe_run(
            _probe_inventory(),
            {"TEST_PROBE_TOKEN": cred},
            fetch_status_side_effect=[
                urllib.error.URLError("timeout"),
                urllib.error.URLError("timeout"),
                urllib.error.URLError("timeout"),
            ],
        )
        combined = stdout + stderr
        self.assertEqual(code, 1, msg=combined)
        self.assertIn("TOKEN-PREFLIGHT FAIL", combined)
        self.assertEqual(fetch_mock.call_count, 3, "network error must retry to 3 attempts total")
        sleep_values = [float(c.args[0]) for c in sleep_mock.call_args_list if c.args]
        self.assertEqual(sleep_values, [1.0, 2.0], "retry must sleep 1s then 2s")
        self._assert_no_secret_leak(stdout, stderr, cred)

    def test_missing_credential_unset(self) -> None:
        code, stdout, stderr, fetch_mock, _ = self._probe_run(
            _probe_inventory(), {}, fetch_status_return=200,
        )
        combined = stdout + stderr
        self.assertEqual(code, 1, msg=combined)
        self.assertIn("MISSING-CREDENTIAL", combined)
        self.assertIn("TOKEN-PREFLIGHT FAIL", combined)
        self.assertEqual(fetch_mock.call_count, 0, "missing credential must make zero requests")

    def test_missing_credential_whitespace_only(self) -> None:
        code, stdout, stderr, fetch_mock, _ = self._probe_run(
            _probe_inventory(), {"TEST_PROBE_TOKEN": "   \t  "}, fetch_status_return=200,
        )
        combined = stdout + stderr
        self.assertEqual(code, 1, msg=combined)
        self.assertIn("MISSING-CREDENTIAL", combined)
        self.assertEqual(fetch_mock.call_count, 0, "whitespace-only credential must make zero requests")

    def test_invalid_credential_surrounding_whitespace(self) -> None:
        cred = _synthetic_credential()
        code, stdout, stderr, fetch_mock, _ = self._probe_run(
            _probe_inventory(), {"TEST_PROBE_TOKEN": f"  {cred}  "}, fetch_status_return=200,
        )
        combined = stdout + stderr
        self.assertEqual(code, 1, msg=combined)
        self.assertIn("INVALID-CREDENTIAL", combined)
        self.assertEqual(fetch_mock.call_count, 0, "invalid credential must not be normalized or sent")
        self._assert_no_secret_leak(stdout, stderr, cred)

    def test_probe_none_is_not_probed(self) -> None:
        code, stdout, stderr, fetch_mock, _ = self._probe_run(
            _none_probe_inventory(), {}, fetch_status_return=200,
        )
        combined = stdout + stderr
        self.assertIn("NOT-PROBED", combined)
        self.assertEqual(fetch_mock.call_count, 0, "probe:none entries must never be probed")


class TokenPreflightSummaryUnitTests(_ValidatorModuleMixin):
    """C2 GITHUB_STEP_SUMMARY behaviour in --probe mode."""

    def _summary_run(self, summary_path: Path, fetch_status_return: int) -> tuple[int, str, str]:
        inventory = _probe_inventory()
        path = self._write_inventory(inventory)
        cred = _synthetic_credential()
        fetch_mock, _ = self._patch_probe_seams(fetch_status_return=fetch_status_return)
        code, stdout, stderr = self._run_main(
            ["--probe", "--inventory", str(path)],
            set_env={"TEST_PROBE_TOKEN": cred, "GITHUB_STEP_SUMMARY": str(summary_path)},
        )
        return code, stdout, stderr

    def test_summary_written_on_pass(self) -> None:
        summary = self.tmp / "summary-pass.md"
        code, stdout, stderr = self._summary_run(summary, fetch_status_return=200)
        combined = stdout + stderr
        self.assertEqual(code, 0, msg=combined)
        self.assertTrue(summary.is_file(), "GITHUB_STEP_SUMMARY file was not written")
        text = summary.read_text(encoding="utf-8")
        self.assertIn("## Token pre-flight", text)
        self.assertIn("docs/operations/TOKEN_PREFLIGHT.md", text)
        self._assert_no_secret_leak(stdout, stderr, _synthetic_credential(), summary_text=text)

    def test_summary_written_on_fail(self) -> None:
        summary = self.tmp / "summary-fail.md"
        code, stdout, stderr = self._summary_run(summary, fetch_status_return=401)
        combined = stdout + stderr
        self.assertEqual(code, 1, msg=combined)
        self.assertTrue(summary.is_file(), "GITHUB_STEP_SUMMARY file must be written on FAIL too")
        text = summary.read_text(encoding="utf-8")
        self.assertIn("## Token pre-flight", text)
        self.assertIn("docs/operations/TOKEN_PREFLIGHT.md", text)
        self._assert_no_secret_leak(stdout, stderr, _synthetic_credential(), summary_text=text)

    def test_summary_unwritable_path_fails(self) -> None:
        # Point GITHUB_STEP_SUMMARY at a directory: writing to it must fail
        # closed with SUMMARY-WRITE-FAILED + exit 1.
        summary_dir = self.tmp / "summary-dir"
        summary_dir.mkdir()
        inventory = _probe_inventory()
        path = self._write_inventory(inventory)
        cred = _synthetic_credential()
        self._patch_probe_seams(fetch_status_return=200)
        code, stdout, stderr = self._run_main(
            ["--probe", "--inventory", str(path)],
            set_env={"TEST_PROBE_TOKEN": cred, "GITHUB_STEP_SUMMARY": str(summary_dir)},
        )
        combined = stdout + stderr
        self.assertEqual(code, 1, msg=combined)
        self.assertIn("SUMMARY-WRITE-FAILED", combined)


class TokenPreflightTransportTests(_ValidatorModuleMixin):
    """C2 fetch_status HTTP mechanics via a patched urllib opener (no network)."""

    def _patch_opener(self, fake_opener: _FakeOpener, recorded_handlers: list) -> None:
        def fake_build_opener(*handlers: Any, **kwargs: Any) -> _FakeOpener:
            recorded_handlers.extend(handlers)
            return fake_opener

        def _no_network(*args: Any, **kwargs: Any) -> None:
            raise AssertionError(
                "fetch_status must not use plain urlopen (redirects would forward the credential)"
            )

        patches = [mock.patch("urllib.request.build_opener", side_effect=fake_build_opener)]
        if hasattr(self.validator, "build_opener"):
            patches.append(mock.patch.object(self.validator, "build_opener", side_effect=fake_build_opener))
        patches.append(mock.patch("urllib.request.urlopen", side_effect=_no_network))
        if hasattr(self.validator, "urlopen"):
            patches.append(mock.patch.object(self.validator, "urlopen", side_effect=_no_network))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_fetch_status_url_bearer_timeout(self) -> None:
        cred = _synthetic_credential()
        opener = _FakeOpener(status=200)
        handlers: list = []
        self._patch_opener(opener, handlers)
        status = self.validator.fetch_status(cred, 10)
        self.assertEqual(status, 200)
        self.assertEqual(len(opener.calls), 1)
        request, timeout = opener.calls[0]
        self.assertEqual(request.full_url, ZEN_URL)
        self.assertEqual(_request_header(request, "Authorization"), f"Bearer {cred}")
        self.assertTrue(_request_header(request, "User-Agent"), "a fixed User-Agent header is required")
        self.assertEqual(timeout, 10, "the 10s timeout must be passed to the opener")

    def test_fetch_status_redirect_rejection(self) -> None:
        cred = _synthetic_credential()
        opener = _FakeOpener(status=301)
        handlers: list = []
        self._patch_opener(opener, handlers)
        status = self.validator.fetch_status(cred, 10)
        # A no-redirect opener surfaces a 3xx as an HTTPError; fetch_status must
        # not follow it (exactly one request, no credential forwarding) and must
        # report the 3xx code rather than a redirect target.
        self.assertEqual(len(opener.calls), 1, "a redirect must not be followed (no credential forwarding)")
        self.assertEqual(status, 301)
        self.assertTrue(
            handlers,
            "the opener must be built with a custom (no-redirect) handler, not the default",
        )

    def test_fetch_status_response_closed(self) -> None:
        cred = _synthetic_credential()
        opener = _FakeOpener(status=200)
        self._patch_opener(opener, [])
        self.validator.fetch_status(cred, 10)
        self.assertIsNotNone(opener.last_response)
        self.assertTrue(opener.last_response.closed, "the HTTP response must be closed (ResourceWarning discipline)")

    def test_fetch_status_401(self) -> None:
        opener = _FakeOpener(status=401)
        self._patch_opener(opener, [])
        self.assertEqual(self.validator.fetch_status(_synthetic_credential(), 10), 401)

    def test_fetch_status_500(self) -> None:
        opener = _FakeOpener(status=500)
        self._patch_opener(opener, [])
        self.assertEqual(self.validator.fetch_status(_synthetic_credential(), 10), 500)

    def test_fetch_status_network_error_is_not_200(self) -> None:
        opener = _FakeOpener(network_error=urllib.error.URLError("timeout"))
        self._patch_opener(opener, [])
        try:
            result = self.validator.fetch_status(_synthetic_credential(), 10)
        except (urllib.error.URLError, OSError):
            result = None  # raising on a network error is acceptable
        self.assertNotEqual(result, 200, "a network error must not be reported as 200")


class TokenPreflightDateMatrixSubprocessTests(unittest.TestCase):
    """C2 date-evaluation contract via subprocess --today fixtures (offline, deterministic).

    Pins the expiry/review boundary matrix against the committed validator:
    expiry < today -> EXPIRED; today <= expiry <= today+21 -> EXPIRY-DUE
    (inclusive both ends); review_date <= today+21 (incl. overdue) -> REVIEW-DUE;
    a dated/no-expiry entry beyond the window -> OK; unknown expiry ->
    UNKNOWN-EXPIRY (non-failing). Error findings route to stderr, info/warn to
    stdout, and the final line is exactly TOKEN-PREFLIGHT PASS/FAIL.
    """

    TODAY = date(2026, 11, 3)

    def _run(self, argv: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), *argv],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def _write(self, data: dict, name: str) -> Path:
        path = TMP_BASE / name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def _run_date_case(self, inventory: dict, name: str) -> subprocess.CompletedProcess:
        path = self._write(inventory, name)
        return self._run(["--inventory", str(path), "--today", self.TODAY.isoformat()])

    def test_expiry_yesterday_is_expired(self) -> None:
        result = self._run_date_case(
            _dated_inventory("tok", "dated", (self.TODAY - timedelta(days=1)).isoformat(), None),
            "date-expired.json",
        )
        self.assertEqual(result.returncode, 1, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn("EXPIRED", result.stderr, "EXPIRED (error) must be routed to stderr")
        self.assertNotIn("EXPIRED", result.stdout, "EXPIRED (error) must not appear on stdout")
        self.assertIn("TOKEN-PREFLIGHT FAIL", result.stdout)

    def test_expiry_today_is_expiry_due(self) -> None:
        result = self._run_date_case(
            _dated_inventory("tok", "dated", self.TODAY.isoformat(), None),
            "date-due-today.json",
        )
        self.assertEqual(result.returncode, 1, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn("EXPIRY-DUE", result.stderr, "EXPIRY-DUE (error) must be routed to stderr")
        self.assertNotIn("EXPIRY-DUE", result.stdout, "EXPIRY-DUE (error) must not appear on stdout")
        self.assertIn("TOKEN-PREFLIGHT FAIL", result.stdout)

    def test_expiry_today_plus_21_is_expiry_due(self) -> None:
        result = self._run_date_case(
            _dated_inventory("tok", "dated", (self.TODAY + timedelta(days=21)).isoformat(), None),
            "date-due-plus21.json",
        )
        self.assertEqual(result.returncode, 1, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn(
            "EXPIRY-DUE", result.stderr,
            "EXPIRY-DUE at the inclusive upper bound (today+21) must be routed to stderr",
        )
        self.assertNotIn("EXPIRY-DUE", result.stdout)
        self.assertIn("TOKEN-PREFLIGHT FAIL", result.stdout)

    def test_expiry_today_plus_22_is_ok(self) -> None:
        result = self._run_date_case(
            _dated_inventory("tok", "dated", (self.TODAY + timedelta(days=22)).isoformat(), None),
            "date-ok-plus22.json",
        )
        self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn("OK: ", result.stdout, "an OK (info) finding must be routed to stdout")
        self.assertIn("TOKEN-PREFLIGHT PASS", result.stdout)

    def test_review_yesterday_is_review_due(self) -> None:
        result = self._run_date_case(
            _dated_inventory("tok", "no-expiry", None, (self.TODAY - timedelta(days=1)).isoformat()),
            "date-review-overdue.json",
        )
        self.assertEqual(result.returncode, 1, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn("REVIEW-DUE", result.stderr, "REVIEW-DUE (error) must be routed to stderr")
        self.assertNotIn("REVIEW-DUE", result.stdout, "REVIEW-DUE (error) must not appear on stdout")
        self.assertIn("TOKEN-PREFLIGHT FAIL", result.stdout)

    def test_review_today_plus_21_is_review_due(self) -> None:
        result = self._run_date_case(
            _dated_inventory("tok", "no-expiry", None, (self.TODAY + timedelta(days=21)).isoformat()),
            "date-review-plus21.json",
        )
        self.assertEqual(result.returncode, 1, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn(
            "REVIEW-DUE", result.stderr,
            "REVIEW-DUE at the inclusive upper bound (today+21) must be routed to stderr",
        )
        self.assertNotIn("REVIEW-DUE", result.stdout)
        self.assertIn("TOKEN-PREFLIGHT FAIL", result.stdout)

    def test_review_today_plus_22_is_ok(self) -> None:
        result = self._run_date_case(
            _dated_inventory("tok", "no-expiry", None, (self.TODAY + timedelta(days=22)).isoformat()),
            "date-review-plus22.json",
        )
        self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn("OK: ", result.stdout, "an OK (info) finding must be routed to stdout")
        self.assertIn("TOKEN-PREFLIGHT PASS", result.stdout)

    def test_unknown_expiry_is_warn_and_pass(self) -> None:
        result = self._run_date_case(
            _dated_inventory("tok", "unknown", None, None),
            "date-unknown.json",
        )
        self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn("UNKNOWN-EXPIRY", result.stdout, "UNKNOWN-EXPIRY (warn) must be routed to stdout")
        self.assertNotIn("UNKNOWN-EXPIRY", result.stderr, "UNKNOWN-EXPIRY (warn) must not appear on stderr")
        self.assertIn("TOKEN-PREFLIGHT PASS", result.stdout)


class TokenPreflightAggregationUnitTests(_ValidatorModuleMixin):
    """C2 aggregation: a date failure must not suppress a probe finding."""

    def test_expired_date_and_unauthorized_probe_both_reported(self) -> None:
        # One inventory with (a) an expired dated token and (b) an api-zen entry
        # whose fetch_status is patched to 401. Both findings must appear in the
        # same run: the date failure (EXPIRED) must not suppress the probe
        # (PROBE-UNAUTHORIZED).
        inventory = {
            "schema": SCHEMA,
            "tokens": [
                {
                    "name": "expired-token",
                    "kind": "classic",
                    "expiry_status": "dated",
                    "expiry": "2020-01-01",
                    "review_date": None,
                    "probe": "none",
                    "credential_pointer": None,
                    "expected_scopes": None,
                    "note": "expired dated token",
                },
                {
                    "name": "probe-token",
                    "kind": "classic",
                    "expiry_status": "no-expiry",
                    "expiry": None,
                    "review_date": "2099-01-01",
                    "probe": "api-zen",
                    "credential_pointer": "TEST_PROBE_TOKEN",
                    "expected_scopes": None,
                    "note": "probe test entry",
                },
            ],
        }
        path = self._write_inventory(inventory)
        cred = _synthetic_credential()
        self._patch_probe_seams(fetch_status_return=401)
        code, stdout, stderr = self._run_main(
            ["--probe", "--inventory", str(path)],
            set_env={"TEST_PROBE_TOKEN": cred},
            unset=("GITHUB_STEP_SUMMARY",),
        )
        combined = stdout + stderr
        self.assertEqual(code, 1, msg=combined)
        self.assertIn("EXPIRED", combined, "the expired dated token must be reported")
        self.assertIn("PROBE-UNAUTHORIZED", combined, "the probe must still run despite the date failure")
        self.assertIn("TOKEN-PREFLIGHT FAIL", combined)
        self._assert_no_secret_leak(stdout, stderr, cred)


class TokenPreflightStreamRoutingUnitTests(_ValidatorModuleMixin):
    """C2 stream routing: error findings to stderr, info/warn to stdout."""

    def test_error_to_stderr_info_warn_to_stdout(self) -> None:
        # An expired dated token (EXPIRED, error) plus an unknown-expiry token
        # (UNKNOWN-EXPIRY, warn); both are probe:none so each also yields
        # NOT-PROBED (info). EXPIRED must land on stderr; UNKNOWN-EXPIRY and
        # NOT-PROBED must land on stdout.
        inventory = {
            "schema": SCHEMA,
            "tokens": [
                {
                    "name": "expired-token",
                    "kind": "classic",
                    "expiry_status": "dated",
                    "expiry": "2020-01-01",
                    "review_date": None,
                    "probe": "none",
                    "credential_pointer": None,
                    "expected_scopes": None,
                    "note": "expired dated token",
                },
                {
                    "name": "unknown-token",
                    "kind": "fine-grained",
                    "expiry_status": "unknown",
                    "expiry": None,
                    "review_date": None,
                    "probe": "none",
                    "credential_pointer": None,
                    "expected_scopes": None,
                    "note": "unknown expiry token",
                },
            ],
        }
        path = self._write_inventory(inventory)
        # No api-zen entry, so fetch_status is never called; patch it anyway so
        # no accidental network request is possible.
        self._patch_probe_seams(fetch_status_return=200)
        code, stdout, stderr = self._run_main(
            ["--probe", "--inventory", str(path)],
            unset=("GITHUB_STEP_SUMMARY",),
        )
        self.assertEqual(code, 1, msg=f"stdout={stdout}\nstderr={stderr}")
        self.assertIn("EXPIRED", stderr, "EXPIRED (error) must be routed to stderr")
        self.assertNotIn("EXPIRED", stdout, "EXPIRED (error) must not appear on stdout")
        self.assertIn("UNKNOWN-EXPIRY", stdout, "UNKNOWN-EXPIRY (warn) must be routed to stdout")
        self.assertNotIn("UNKNOWN-EXPIRY", stderr, "UNKNOWN-EXPIRY (warn) must not appear on stderr")
        self.assertIn("NOT-PROBED", stdout, "NOT-PROBED (info) must be routed to stdout")
        self.assertNotIn("NOT-PROBED", stderr, "NOT-PROBED (info) must not appear on stderr")


if __name__ == "__main__":
    unittest.main()
