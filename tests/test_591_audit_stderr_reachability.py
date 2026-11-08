"""Issue #591: the require_role() audit line must reach STDERR under default startup.

``api/app/identity.py`` logs the authorized mutation-ATTEMPT record
("authorized mutation attempt: user=%s role=%s action=%s") at INFO level on
its module logger. The app has NO logging configuration anywhere, and the
production server (uvicorn 0.54.0, app-dir mode — see
api/requirements-api.txt:29-30) leaves the root logger unconfigured by
default, so the logging lastResort handler (WARNING and above only) drops
the INFO record: the audit line never reaches stderr/journald.

These tests pin the OUTCOME, not the mechanism: under a default startup
(no ``logging.basicConfig``/``dictConfig``/handler wiring anywhere in the
test), exercising an authorized mutation attempt through the real HTTP
boundary must emit the audit line to STDERR with the exact user/role/action
fields.

Idempotence is pinned RELATIVELY: the same authorized attempt under a
single app init establishes a baseline line count N; the same attempt
after importlib.reload of the identity and app modules (the module-init /
app-creation path re-run) must emit exactly N lines — a non-idempotent
handler attachment would multiply the count. N is measured, never a
literal: the probe route /api/cam1/roi is an alias that delegates to the
analytics route, and BOTH guards emit an authorization-attempt record
(specs/530-roles/plan.md D-4, pinned by
tests/test_sea_speed_rbac.py::test_calibration_alias_records_attempt) —
that alias semantics is out of scope for #591 and deliberately not
coupled into these reachability assertions.

Honest stderr proof: the app import + guarded request run in a SUBPROCESS
(``sys.executable -c``) whose stderr is captured with context-managed pipes
(the suite runs under ``-W error::ResourceWarning``). In-process
caplog/assertLogs would NOT prove stderr reachability — the whole point is
that the record must survive the unconfigured-root-logger default and land
on the process stderr stream.

Import-mode coverage: the production mode is uvicorn app-dir (``main`` /
``identity`` bare module names, ``api/app`` on sys.path); the package mode
(``api.app.main`` / ``api.app.identity``) is covered as the alternate. The
logger NAME varies with import mode, so the assertions never reference it —
only the message content.

Environment: each test points ``SEA_SPEED_BASE_DIR`` at a fresh temp
directory (the #582 config override) and sets the same gitleaks-safe auth
fixtures as tests/test_api_http_integration.py; the child env is a copy of
the parent env with those names overridden, so the parent process is never
mutated. No network binds: TestClient's in-process transport inside the
subprocess.

RED on base: the child returns 200 (the authorized attempt passes
require_role) but the audit line is ABSENT from stderr (lastResort drops
INFO) — the stderr assertions fail. GREEN once the fix wires an idempotent
stderr handler for the identity module logger at app startup/module init.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _optional_module_available(module_name: str) -> bool:
    """Probe for an optional dependency without importing it.

    The import-hygiene scan (scripts/run_tests.py) AST-collects every
    Import/ImportFrom in tests/**/*.py: an unguarded site-packages import
    fails the run, and a guarded one lands in the exact guarded-optional
    inventory asserted by tests/test_run_tests_script.py. Probing through
    ``importlib.util.find_spec`` keeps the same skip-when-absent semantics
    as the guarded-optional idiom while staying invisible to the static
    scan AND without caching the module in sys.modules (a module-level
    ``import fastapi`` here would run before tests/test_api_http_integration.py
    during discovery and break its PREEXISTING_MODULES eviction contract,
    which tests/test_roi_normalization.py's stubs depend on).
    """
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


# Guarded-optional semantics (tests/test_api_http_integration.py): when
# fastapi/httpx are absent the whole module skips and the battery stays
# green unchanged; where the declared pins are installed the tests run for
# real.
HTTP_TESTS_ENABLED = (
    _optional_module_available("fastapi") and _optional_module_available("httpx")
)

# Gitleaks-safe fixture values, identical to tests/test_api_http_integration.py:
# low-entropy throwaway constants for a disposable temp environment, never
# real secrets.
BEARER_FIXTURE = "integration-fixture-582"
EDGE_HEADER_FIXTURE = "edge-fixture-582"
WORKER_TOKEN_FIXTURE = "worker-fixture-582"
ADMIN_USER_FIXTURE = "fixture-admin-582"
# 40 hex chars (deployed_source_commit validates SHA_RE), minimal entropy.
DEPLOYED_COMMIT_FIXTURE = "a" * 40

# Loopback is rejected by the app's own worker_control_origin guard before
# any connection is attempted: deterministic fail-closed, zero network.
UNREACHABLE_WORKER_CONTROL_URL = "http://127.0.0.1:19001"

# The audit record's stable message content (identity.py require_role):
# "authorized mutation attempt: user=%s role=%s action=%s". The logger NAME
# varies with import mode (identity vs api.app.identity), so only the
# message content is asserted.
AUDIT_MARKER = "authorized mutation attempt"
EXPECTED_AUDIT_FIELDS = (
    f"user={ADMIN_USER_FIXTURE}",
    "role=admin",
    "action=post_cam1_roi",
)

# Every environment name the child interpreter receives; each is set in the
# child env copy (parent env is never mutated).
MANAGED_ENV_NAMES = (
    "SEA_SPEED_BASE_DIR",
    "SEA_SPEED_DEPLOYED_COMMIT_FILE",
    "SEA_SPEED_API_TOKEN",
    "SEA_SPEED_EDGE_AUTH_SECRET",
    "SEA_SPEED_ADMIN_USERS",
    "SEA_SPEED_WORKER_CONTROL_TOKEN",
    "SEA_SPEED_WORKER_CONTROL_URL",
    "SEA_SPEED_SOURCE_COMMIT",
)


def _child_script(mode: str, reload_app: bool) -> str:
    """Build the child-interpreter script for one import mode.

    ``mode="app-dir"`` mirrors the production uvicorn app-dir startup
    (api/app on sys.path, bare ``main``/``identity`` module names);
    ``mode="package"`` is the package-context import (``api.app.main`` /
    ``api.app.identity``). ``reload_app=True`` re-runs the module-init /
    app-creation path a second time (identity first, then the app module,
    so the app re-binds the reloaded identity) — the idempotence probe.

    The script performs NO logging configuration: default startup means the
    root logger stays unconfigured, exactly like production.
    """
    if mode == "app-dir":
        path_setup = 'sys.path.insert(0, os.path.join(os.getcwd(), "api", "app"))'
        app_module = "main"
        identity_module = "identity"
    else:
        path_setup = "sys.path.insert(0, os.getcwd())"
        app_module = "api.app.main"
        identity_module = "api.app.identity"
    lines = [
        "import importlib",
        "import json",
        "import os",
        "import sys",
        "",
        path_setup,
        "",
        f"import {app_module} as app_module",
        f"import {identity_module} as identity_module",
    ]
    if reload_app:
        lines += [
            "importlib.reload(identity_module)",
            "importlib.reload(app_module)",
        ]
    lines += [
        "from fastapi.testclient import TestClient",
        "",
        "headers = {",
        f'    "X-Authentik-Username": "{ADMIN_USER_FIXTURE}",',
        f'    "X-Sea-Speed-Edge-Auth": "{EDGE_HEADER_FIXTURE}",',
        "}",
        "payload = {",
        '    "enabled": True,',
        '    "polygon_norm": [',
        '        {"x_norm": 0.1, "y_norm": 0.1},',
        '        {"x_norm": 0.5, "y_norm": 0.1},',
        '        {"x_norm": 0.5, "y_norm": 0.8},',
        "    ],",
        "}",
        "with TestClient(app_module.app) as client:",
        '    response = client.post("/api/cam1/roi", json=payload, headers=headers)',
        'print(json.dumps({"status": response.status_code}))',
        "",
    ]
    return "\n".join(lines)


@unittest.skipUnless(
    HTTP_TESTS_ENABLED,
    "fastapi/httpx are not installed (the audit stderr tests run where the "
    "declared pins are installed)",
)
class SeaSpeedAuditStderrReachabilityTests(unittest.TestCase):
    """The require_role() audit line reaches process stderr, and repeated
    app init does not multiply its emission."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="sea-speed-591-audit-")
        self.addCleanup(temp.cleanup)
        self.base_dir = Path(temp.name)
        self.deployed_file = self.base_dir / "deploy-state" / "current-release"
        self.deployed_file.parent.mkdir(parents=True, exist_ok=True)
        self.deployed_file.write_text(DEPLOYED_COMMIT_FIXTURE + "\n", encoding="utf-8")

    def run_child(self, mode: str, reload_app: bool) -> subprocess.CompletedProcess:
        """Run the app import + one authorized ROI save in a fresh interpreter."""
        env = dict(os.environ)
        env.update(
            {
                "SEA_SPEED_BASE_DIR": str(self.base_dir),
                "SEA_SPEED_DEPLOYED_COMMIT_FILE": str(self.deployed_file),
                "SEA_SPEED_API_TOKEN": BEARER_FIXTURE,
                "SEA_SPEED_EDGE_AUTH_SECRET": EDGE_HEADER_FIXTURE,
                "SEA_SPEED_ADMIN_USERS": ADMIN_USER_FIXTURE,
                "SEA_SPEED_WORKER_CONTROL_TOKEN": WORKER_TOKEN_FIXTURE,
                "SEA_SPEED_WORKER_CONTROL_URL": UNREACHABLE_WORKER_CONTROL_URL,
            }
        )
        # deployed_source_commit prefers this env var over the commit file;
        # remove it so the fixture file is the authoritative source (same
        # convention as tests/test_api_http_integration.py).
        env.pop("SEA_SPEED_SOURCE_COMMIT", None)
        return subprocess.run(
            [sys.executable, "-c", _child_script(mode, reload_app)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def assert_audit_line_on_stderr(self, completed: subprocess.CompletedProcess) -> None:
        """Presence + exact fields on stderr. Deliberately NO count pin:
        the probe route is an alias whose delegation emits one record per
        guard (spec D-4) — reachability does not own that semantics."""
        self.assertEqual(
            completed.returncode,
            0,
            f"child interpreter failed\nstdout: {completed.stdout!r}\n"
            f"stderr: {completed.stderr!r}",
        )
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        # 200 proves the request passed require_role (verified admin
        # identity, role >= minimum) and the mutation succeeded — the audit
        # record was emitted by the code under test, not swallowed earlier.
        self.assertEqual(
            payload["status"],
            200,
            f"expected 200 from the authorized ROI save\n"
            f"stdout: {completed.stdout!r}\nstderr: {completed.stderr!r}",
        )
        stderr = completed.stderr
        self.assertIn(
            AUDIT_MARKER,
            stderr,
            f"audit line missing from stderr under default startup\n"
            f"stderr was: {stderr!r}",
        )
        for field in EXPECTED_AUDIT_FIELDS:
            self.assertIn(
                field,
                stderr,
                f"audit field {field!r} missing from stderr\nstderr was: {stderr!r}",
            )

    def assert_audit_count_unchanged_by_reload(
        self, mode: str, baseline: subprocess.CompletedProcess, reloaded: subprocess.CompletedProcess
    ) -> None:
        """Relative idempotence pin: the reload scenario must emit exactly
        the baseline (single-init) line count — never a literal."""
        self.assert_audit_line_on_stderr(baseline)
        self.assert_audit_line_on_stderr(reloaded)
        baseline_count = baseline.stderr.count(AUDIT_MARKER)
        reloaded_count = reloaded.stderr.count(AUDIT_MARKER)
        self.assertEqual(
            reloaded_count,
            baseline_count,
            f"[{mode}] repeated app init changed the audit line count "
            f"({baseline_count} single-init -> {reloaded_count} after reload); "
            f"a non-idempotent handler attachment would duplicate the line\n"
            f"baseline stderr: {baseline.stderr!r}\n"
            f"reloaded stderr: {reloaded.stderr!r}",
        )

    # -- 1. audit line reaches stderr under default startup ----------------

    def test_audit_line_reaches_stderr_under_default_startup_app_dir_mode(self):
        """Production import mode (uvicorn app-dir): the line lands on stderr."""
        completed = self.run_child(mode="app-dir", reload_app=False)
        self.assert_audit_line_on_stderr(completed)

    def test_audit_line_reaches_stderr_under_default_startup_package_mode(self):
        """Alternate import mode (api.app.* package context): same outcome."""
        completed = self.run_child(mode="package", reload_app=False)
        self.assert_audit_line_on_stderr(completed)

    # -- 2. idempotence: repeated app init must not multiply the line count -

    def test_audit_line_count_unchanged_after_repeated_app_init_app_dir_mode(self):
        """App-dir mode: baseline count under single init, then reload
        identity + app (app-creation path twice) — count must be unchanged."""
        baseline = self.run_child(mode="app-dir", reload_app=False)
        reloaded = self.run_child(mode="app-dir", reload_app=True)
        self.assert_audit_count_unchanged_by_reload("app-dir", baseline, reloaded)

    def test_audit_line_count_unchanged_after_repeated_app_init_package_mode(self):
        """Package mode: same relative idempotence probe via api.app.*."""
        baseline = self.run_child(mode="package", reload_app=False)
        reloaded = self.run_child(mode="package", reload_app=True)
        self.assert_audit_count_unchanged_by_reload("package", baseline, reloaded)


if __name__ == "__main__":
    unittest.main()
