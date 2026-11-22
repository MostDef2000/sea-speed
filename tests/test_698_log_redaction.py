"""Issue #698: credential values are masked at every repo-owned log boundary.

The production side (api/app/log_redaction.py + the wired boundaries) is
already landed; these tests pin the OUTCOMES described in
specs/698-log-redaction/spec.md (AC-001..AC-008), never the mechanism beyond
what an observable requires.

Canary discipline: every credential used here is generated at RUNTIME
(uuid/random/base64) — no secret-shaped literal ever enters the source file.
Each positive assertion checks three things at once: the ``[REDACTED]``
marker AND the neighbouring useful text are PRESENT, and the COMPLETE canary
is ABSENT. Each negative line must come back BYTE-IDENTICAL.

RED spot-check (what fails if the production change were absent — the
orchestrator runs this against base_sha 67e31272):

* RedactLogTextPolicyTests  — importing ``api.app.log_redaction`` raises
  ModuleNotFoundError (module does not exist on base), so every test in the
  class errors before any assertion.
* IdentityAuditRedaction*   — the child interpreter dies with ImportError
  (identity.py imports RedactingFilter) so returncode != 0; on a partial
  base the raw canary would sit on stderr and assertNotIn(canary, stderr)
  fails.
* UvicornAccess*            — without install_api_redaction() the handler
  keeps the raw AccessFormatter, so the rendered line still contains the
  canary and assertNotIn fails; the double-install test finds no
  RedactingFormatter wrapper at all.
* RunnerForwardRedaction*   — on base the runner has no log_redaction
  import: the subprocess exits 1 (ImportError) so returncode != 0. If
  forward() stopped masking, assertNotIn(canary, stdout) fails; if
  record_line() received the REDACTED line instead of the original, the
  glued ``token=<canary>dropped=7`` line would leave dropped_frames at 0
  instead of 7.
* WorkerControlAgent*       — on base the agent exits on ImportError so the
  listener never starts (readiness probe fails); if log_message() printed
  the raw request line, assertNotIn(canary, output) fails.
* PackagingInventory*       — on base the inventories/deploy.sh have no
  api/app/log_redaction.py entry, so assertIn fails for every site.
* DirectStderrPrint* (5)    — the five wrapped direct ``print(...,
  file=sys.stderr)`` sites are AST-loaded from the REAL source; at base the
  prints are unwrapped, so the crafted exception's canary reaches the
  captured stderr and assertNotIn(canary, stderr) fails at every site.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import copy
import http.client
import io
import json
import logging
import os
import random
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from contextlib import contextmanager, redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app.log_redaction import (  # noqa: E402
    REDACTED,
    RedactingFormatter,
    install_api_redaction,
    redact_log_text,
)
from scripts.quality.build_exact_artifacts import COMPONENT_FILES  # noqa: E402
from scripts.quality.validate_exact_artifacts import REQUIRED_BY_COMPONENT  # noqa: E402
from tests.test_591_audit_stderr_reachability import (  # noqa: E402
    ADMIN_USER_FIXTURE,
    AUDIT_MARKER,
    BEARER_FIXTURE,
    DEPLOYED_COMMIT_FIXTURE,
    EDGE_HEADER_FIXTURE,
    EXPECTED_AUDIT_FIELDS,
    HTTP_TESTS_ENABLED,
    UNREACHABLE_WORKER_CONTROL_URL,
    WORKER_TOKEN_FIXTURE,
    _child_script,
)

AGENT_PATH = ROOT / "deploy" / "worker" / "ubuntu" / "worker-control-agent.py"
RUNNER_PATH = ROOT / "deploy" / "worker" / "ubuntu" / "observed-worker-runner.py"

# The control agent only binds non-loopback RFC1918 IPv4 (its own
# parse_private_listen gate); the sandbox docker bridge is bindable.
CONTROL_HOST = "172.17.0.1"


def _canary() -> str:
    """Runtime-generated credential-shaped canary (labelled-secret cases)."""
    return f"canary-{uuid.uuid4().hex}{uuid.uuid4().hex}"


def _hex_canary() -> str:
    """Runtime 64-char hex canary guaranteed to contain hex letters."""
    return uuid.uuid4().hex + "".join(random.choices("abcdef", k=16))


def _access_formatter_class():
    """Import uvicorn's AccessFormatter (guarded: uvicorn is an api-lock pin,
    not a declared battery dependency — the battery stays green without it)."""
    try:
        from uvicorn.logging import AccessFormatter
    except ImportError:
        return None
    return AccessFormatter


# ---------------------------------------------------------------------------
# 1. redact_log_text policy table
# ---------------------------------------------------------------------------


class RedactLogTextPolicyTests(unittest.TestCase):
    def test_authorization_bearer_header_value_is_masked(self) -> None:
        canary = _canary()
        out = redact_log_text(f"outgoing Authorization: Bearer {canary} accepted")
        self.assertIn("Authorization: Bearer " + REDACTED, out)
        self.assertIn("accepted", out)
        self.assertNotIn(canary, out)

    def test_authorization_bearer_header_map_repr_is_masked(self) -> None:
        canary = _canary()
        line = (
            "headers={'Authorization': 'Bearer " + canary + "', 'X-Req': 'req-1'}"
        )
        out = redact_log_text(line)
        self.assertIn("'Authorization': 'Bearer " + REDACTED + "'", out)
        self.assertIn("'X-Req': 'req-1'", out)
        self.assertNotIn(canary, out)

    def test_labelled_secret_forms_are_masked(self) -> None:
        canary = _canary()
        for label in ("api_key", "api-key", "access_token", "token"):
            with self.subTest(label=label):
                out = redact_log_text(f"config {label}={canary} saved")
                self.assertIn(f"{label}={REDACTED}", out)
                self.assertIn("config", out)
                self.assertIn("saved", out)
                self.assertNotIn(canary, out)

    def test_single_quoted_password_value_is_masked(self) -> None:
        canary = _canary()
        out = redact_log_text(f"login password='{canary}' rejected")
        self.assertIn(f"password='{REDACTED}'", out)
        self.assertIn("login", out)
        self.assertIn("rejected", out)
        self.assertNotIn(canary, out)

    def test_token_query_value_stops_at_ampersand_and_hash(self) -> None:
        canary = _canary()
        amp = redact_log_text(
            f"https://example.invalid/sea-speed/?token={canary}&page=2"
        )
        self.assertIn(f"token={REDACTED}&page=2", amp)
        self.assertIn("https://example.invalid/sea-speed/?", amp)
        self.assertNotIn(canary, amp)

        hash_line = redact_log_text(f"link https://x/y?token={canary}#frag")
        self.assertIn(f"token={REDACTED}#frag", hash_line)
        self.assertNotIn(canary, hash_line)

    def test_labelled_value_keeps_trailing_base64_padding_consumed(self) -> None:
        padded = _hex_canary() + "=="
        out = redact_log_text(f"api_key={padded} next")
        self.assertIn(f"api_key={REDACTED}", out)
        self.assertIn("next", out)
        self.assertNotIn(padded, out)
        self.assertNotIn(padded.rstrip("="), out)

    def test_negative_lines_are_byte_identical(self) -> None:
        sha_value = _hex_canary()  # labelled digest: must survive untouched
        benign = (
            # classic lookbehind trap: "key" inside "monkey"
            "monkey=banana",
            # labelled digest: single atom containing "=" mid-string
            f"sha256={sha_value}",
            # 32-digit numeric telemetry: digits are hex but carry no letter
            "telemetry seq=12345678901234567890123456789012 ok",
            # the #591 audit line itself
            "authorized mutation attempt: user=fixture-admin-582 role=admin"
            " action=post_cam1_roi",
            # worker telemetry line
            "telemetry effective_fps=29.5 avg_frame_age_ms=12.5 dropped=3",
            # benign FFmpeg diagnostics
            "frame= 1234 fps=29.97 size=  10kB time=00:00:01.00"
            " bitrate= 800.0kbits/s speed=1.0x",
            # unremarkable single-case word (>=32 chars): survives by design
            "note unremarkablelongsinglecasewordhere end",
        )
        for line in benign:
            with self.subTest(line=line):
                self.assertEqual(redact_log_text(line), line)

    def test_unlabeled_hex_atom_with_letter_is_masked(self) -> None:
        value = _hex_canary()
        out = redact_log_text(f"checksum {value} recorded")
        self.assertIn(f"checksum {REDACTED} recorded", out)
        self.assertNotIn(value, out)

    def test_unlabeled_base64_padding_and_mixed_case_are_masked(self) -> None:
        padded = base64.b64encode(os.urandom(31)).decode("ascii")
        self.assertTrue(padded.endswith("="), "fixture must carry '=' padding")
        out = redact_log_text(f"cache {padded} evicted")
        self.assertIn(f"cache {REDACTED} evicted", out)
        self.assertNotIn(padded, out)

        mixed = uuid.uuid4().hex.upper() + uuid.uuid4().hex
        out = redact_log_text(f"session {mixed} stored")
        self.assertIn(f"session {REDACTED} stored", out)
        self.assertNotIn(mixed, out)

    def test_redaction_is_idempotent(self) -> None:
        canary = _canary()
        line = (
            f"once Authorization: Bearer {canary} token={canary}"
            f" password='{canary}' twice"
        )
        once = redact_log_text(line)
        twice = redact_log_text(once)
        self.assertEqual(twice, once)
        self.assertNotIn(REDACTED + REDACTED, twice)
        self.assertNotIn(canary, twice)
        self.assertIn("once", twice)
        self.assertIn("twice", twice)


# ---------------------------------------------------------------------------
# 2. identity audit: real subprocess stderr, both import modes + reload
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    HTTP_TESTS_ENABLED,
    "fastapi/httpx are not installed (the audit tests run where the declared "
    "pins are installed, same guard as tests/test_591_audit_stderr_reachability)",
)
class IdentityAuditRedactionSubprocessTests(unittest.TestCase):
    """AC-001: the audit line reaches stderr with byte-identical
    user/role/action fields while a credential-bearing parameterized record
    on the SAME emitting logger comes out masked."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="sea-speed-698-audit-")
        self.addCleanup(temp.cleanup)
        self.base_dir = Path(temp.name)
        self.deployed_file = self.base_dir / "deploy-state" / "current-release"
        self.deployed_file.parent.mkdir(parents=True, exist_ok=True)
        self.deployed_file.write_text(DEPLOYED_COMMIT_FIXTURE + "\n", encoding="utf-8")

    def run_child(self, mode: str, reload_app: bool, canary: str) -> subprocess.CompletedProcess:
        # The pinned #591 child (import mode + reload + authorized ROI save)
        # plus ONE parameterized credential-bearing record on the identity
        # logger: record.args carries the canary, so only a working filter
        # can keep it off stderr.
        script = (
            _child_script(mode, reload_app)
            + "\nidentity_module._LOGGER.info("
            + "'audit credential exchange token=%s ok', "
            + repr(canary)
            + ")\n"
        )
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
        env.pop("SEA_SPEED_SOURCE_COMMIT", None)
        return subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def assert_audit_intact_and_canary_masked(
        self, completed: subprocess.CompletedProcess, canary: str, mode: str
    ) -> None:
        self.assertEqual(
            completed.returncode,
            0,
            f"[{mode}] child interpreter failed\nstdout: {completed.stdout!r}\n"
            f"stderr: {completed.stderr!r}",
        )
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(
            payload["status"],
            200,
            f"[{mode}] expected 200 from the authorized ROI save\n"
            f"stdout: {completed.stdout!r}\nstderr: {completed.stderr!r}",
        )
        stderr = completed.stderr
        # Audit structure is untouched (#591 behaviour, fixtures reused as-is).
        self.assertIn(AUDIT_MARKER, stderr, f"stderr was: {stderr!r}")
        for field in EXPECTED_AUDIT_FIELDS:
            self.assertIn(field, stderr, f"audit field missing; stderr: {stderr!r}")
        # The credential-bearing parameterized record is masked in place.
        self.assertIn("audit credential exchange", stderr, f"stderr: {stderr!r}")
        self.assertIn(f"token={REDACTED}", stderr, f"stderr: {stderr!r}")
        self.assertNotIn(canary, stderr, f"canary leaked to stderr: {stderr!r}")
        self.assertNotIn(canary, completed.stdout, "canary leaked to stdout")
        # Exactly one emission (a duplicated stderr handler would double it)
        # and no stacked marker from a double-applied filter.
        self.assertEqual(stderr.count("audit credential exchange"), 1)
        self.assertNotIn(REDACTED + REDACTED, stderr)

    def test_audit_fields_intact_and_canary_masked_app_dir_mode(self) -> None:
        canary = _canary()
        baseline = self.run_child("app-dir", False, canary)
        self.assert_audit_intact_and_canary_masked(baseline, canary, "app-dir")

        canary = _canary()
        reloaded = self.run_child("app-dir", True, canary)
        self.assert_audit_intact_and_canary_masked(reloaded, canary, "app-dir-reload")

    def test_audit_fields_intact_and_canary_masked_package_mode(self) -> None:
        canary = _canary()
        baseline = self.run_child("package", False, canary)
        self.assert_audit_intact_and_canary_masked(baseline, canary, "package")

        canary = _canary()
        reloaded = self.run_child("package", True, canary)
        self.assert_audit_intact_and_canary_masked(reloaded, canary, "package-reload")


# ---------------------------------------------------------------------------
# 3. uvicorn access log
# ---------------------------------------------------------------------------


class UvicornAccessRedactionTests(unittest.TestCase):
    def make_handler(self, formatter) -> tuple[logging.Logger, logging.StreamHandler]:
        logger = logging.getLogger("uvicorn.access")
        state = (logger.level, logger.propagate, list(logger.handlers))

        def restore() -> None:
            logger.setLevel(state[0])
            logger.propagate = state[1]
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
            for handler in state[2]:
                logger.addHandler(handler)

        self.addCleanup(restore)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        return logger, handler

    def test_access_line_masks_query_token_and_keeps_request_shape(self) -> None:
        formatter_cls = _access_formatter_class()
        if formatter_cls is None:
            self.skipTest("uvicorn is not installed (api-lock pin)")
        canary = _canary()
        logger, _handler = self.make_handler(formatter_cls())
        install_api_redaction()

        record = logging.LogRecord(
            "uvicorn.access",
            logging.INFO,
            __file__,
            1,
            '%s - "%s %s HTTP/%s" %d',
            (
                "172.17.0.5:53104",
                "GET",
                f"/sea-speed/api/health?token={canary}&page=2",
                "1.1",
                404,
            ),
            None,
        )
        logger.handle(record)
        out = _handler.stream.getvalue()
        self.assertNotIn(canary, out, f"query canary leaked: {out!r}")
        self.assertIn(f"token={REDACTED}&page=2", out, f"out: {out!r}")
        self.assertIn("page=2", out)
        self.assertIn("GET", out)
        self.assertIn("404", out)
        self.assertIn("172.17.0.5:53104", out)
        self.assertIn(REDACTED, out)

    def test_double_install_wraps_each_formatter_exactly_once(self) -> None:
        formatter_cls = _access_formatter_class()
        if formatter_cls is None:
            self.skipTest("uvicorn is not installed (api-lock pin)")
        original = formatter_cls()
        _logger, handler = self.make_handler(original)

        install_api_redaction()
        wrapped_once = handler.formatter
        install_api_redaction()
        wrapped_twice = handler.formatter

        self.assertIs(wrapped_twice, wrapped_once, "second install re-wrapped")
        self.assertIsInstance(wrapped_twice, RedactingFormatter)
        self.assertTrue(
            getattr(wrapped_twice, "_sea_speed_698_redacting_formatter", False)
        )
        # Exactly ONE wrapper: the inner formatter is the original object,
        # not another RedactingFormatter (no stacked redaction layers).
        self.assertIs(wrapped_twice._inner, original)
        self.assertNotIsInstance(wrapped_twice._inner, RedactingFormatter)


# ---------------------------------------------------------------------------
# 4. observed-worker-runner forward boundary
# ---------------------------------------------------------------------------


class RunnerForwardRedactionTests(unittest.TestCase):
    def test_runner_masks_streams_but_feeds_original_line_to_record_line(self) -> None:
        canary_out = _canary()
        canary_err = _canary()
        glued = _hex_canary()
        with tempfile.TemporaryDirectory(prefix="sea-speed-698-runner-") as temp:
            tmp = Path(temp)
            heartbeat = tmp / "worker-heartbeat.json"
            overlay = tmp / "latest_overlay.jpg"
            child = tmp / "fixture_child.py"
            child.write_text(
                "import sys\n"
                "import time\n"
                'print("Worker started", flush=True)\n'
                'print("telemetry effective_fps=29.5 avg_frame_age_ms=12.5",'
                " flush=True)\n"
                f'print("auth token={canary_out}", flush=True)\n'
                f'print("token={glued}dropped=7", flush=True)\n'
                f'print("inference secret={canary_err}",'
                " file=sys.stderr, flush=True)\n"
                'print("benign stderr line", file=sys.stderr, flush=True)\n'
                "time.sleep(0.3)\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER_PATH),
                    "--source-commit",
                    "a" * 40,
                    "--heartbeat",
                    str(heartbeat),
                    "--overlay",
                    str(overlay),
                    "--heartbeat-interval-sec",
                    "1",
                    str(child),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            # The heartbeat must be read before the temp dir is cleaned up.
            payload = json.loads(heartbeat.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr!r}")
        stdout, stderr = result.stdout, result.stderr

        # Exact safe text: benign lines byte-identical, canaries replaced.
        self.assertIn("Worker started", stdout)
        self.assertIn(
            "telemetry effective_fps=29.5 avg_frame_age_ms=12.5", stdout
        )
        self.assertIn(f"auth token={REDACTED}", stdout)
        self.assertIn(f"token={REDACTED}", stdout)
        self.assertIn(f"inference secret={REDACTED}", stderr)
        self.assertIn("benign stderr line", stderr)

        # Canary absent everywhere, stream separation preserved.
        for canary in (canary_out, canary_err, glued):
            self.assertNotIn(canary, stdout)
            self.assertNotIn(canary, stderr)
        self.assertNotIn(canary_err, stdout)
        self.assertNotIn(canary_out, stderr)
        self.assertNotIn("inference secret", stdout)
        self.assertNotIn("benign stderr line", stdout)
        self.assertNotIn("Worker started", stderr)

        # record_line received the ORIGINAL line: the glued canary hides
        # "dropped=7" from the (redacted) stream, yet the counter parsed it.
        self.assertEqual(payload["phase"], "exited")
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["effective_fps"], 29.5)
        self.assertEqual(payload["avg_frame_age_ms"], 12.5)
        self.assertEqual(payload["dropped_frames"], 7)
        self.assertIsNotNone(payload["last_output_at"])


# ---------------------------------------------------------------------------
# 5. worker-control-agent access line
# ---------------------------------------------------------------------------


class WorkerControlAgentRedactionTests(unittest.TestCase):
    def free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind((CONTROL_HOST, 0))
            return int(probe.getsockname()[1])

    def test_query_bearing_404_access_line_masks_token(self) -> None:
        port = self.free_port()
        env = dict(os.environ)
        env.update(
            {
                "SEA_SPEED_WORKER_CONTROL_TOKEN": "control-fixture-698",
                "SEA_SPEED_WORKER_CONTROL_LISTEN": f"{CONTROL_HOST}:{port}",
            }
        )
        proc = subprocess.Popen(
            [sys.executable, str(AGENT_PATH)],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        try:
            # Readiness: the private listener must come up (on base the agent
            # dies on ImportError before binding, so this never connects).
            deadline = time.monotonic() + 10.0
            ready = False
            while time.monotonic() < deadline:
                try:
                    with socket.create_connection((CONTROL_HOST, port), timeout=1.0):
                        ready = True
                    break
                except OSError:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)
            output_before = ""
            if not ready:
                proc.kill()
                output_before = proc.communicate(timeout=10)[0]
            self.assertTrue(
                ready,
                f"control agent did not bind {CONTROL_HOST}:{port}\n{output_before}",
            )

            canary = _canary()
            connection = http.client.HTTPConnection(CONTROL_HOST, port, timeout=10)
            try:
                connection.request(
                    "GET", f"/v1/status?token={canary}&page=2"
                )
                response = connection.getresponse()
                body = response.read()
                self.assertEqual(response.status, 404, body)
            finally:
                connection.close()
            time.sleep(0.5)  # access line is flushed during send_response
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                output = proc.communicate(timeout=10)[0]
            except subprocess.TimeoutExpired:
                proc.kill()
                output = proc.communicate(timeout=10)[0]

        self.assertNotIn(canary, output, f"query canary leaked: {output!r}")
        self.assertIn(f"token={REDACTED}&page=2", output, f"output: {output!r}")
        self.assertIn("page=2", output)
        self.assertIn("GET", output)
        self.assertIn("404", output)
        self.assertIn(REDACTED, output)
        self.assertIn(f"worker-control listen={CONTROL_HOST}:{port}", output)


# ---------------------------------------------------------------------------
# 6. packaging: inventories + deploy.sh mirror sites
# ---------------------------------------------------------------------------


class PackagingInventoryTests(unittest.TestCase):
    def test_log_redaction_is_required_by_active_contours_only(self) -> None:
        path = "api/app/log_redaction.py"
        # build_exact_artifacts COMPONENT_FILES: {"component": {"required": [...]}}
        for component in ("vps", "ubuntu-worker"):
            with self.subTest(inventory="build", component=component):
                self.assertIn(path, COMPONENT_FILES[component]["required"])
        with self.subTest(inventory="build", component="edge"):
            self.assertNotIn(path, COMPONENT_FILES["edge"]["required"])
        # validate_exact_artifacts REQUIRED_BY_COMPONENT: {"component": {paths}}
        for component in ("vps", "ubuntu-worker"):
            with self.subTest(inventory="validate", component=component):
                self.assertIn(path, REQUIRED_BY_COMPONENT[component])
        with self.subTest(inventory="validate", component="edge"):
            self.assertNotIn(path, REQUIRED_BY_COMPONENT["edge"])

    def test_deploy_sh_mirrors_log_redaction_through_every_site(self) -> None:
        text = (ROOT / "deploy" / "vps" / "deploy.sh").read_text(encoding="utf-8")
        sites = {
            "target definition": 'LOG_REDACTION_TARGET="$(dirname "$API_TARGET")/log_redaction.py"',
            "release_complete required check": '-f "$root/api/app/log_redaction.py"',
            "download_release required loop": "api/app/log_redaction.py \\",
            "download_release extract install": 'install -m 0644 "$extracted/api/app/log_redaction.py" "$TARGET_RELEASE/api/app/log_redaction.py"',
            "bootstrap baseline install": 'install -m 0644 "$LOG_REDACTION_TARGET" "$bootstrap_release/api/app/log_redaction.py"',
            ".next staging": 'install -m 0644 "$release_dir/api/app/log_redaction.py" "${LOG_REDACTION_TARGET}.next"',
            "activation mv before main.py": 'mv -f "${LOG_REDACTION_TARGET}.next" "$LOG_REDACTION_TARGET"',
        }
        for site, needle in sites.items():
            with self.subTest(site=site):
                self.assertIn(needle, text, f"deploy.sh missing {site}")


# ---------------------------------------------------------------------------
# 7. the five direct sys.stderr print sites (AC-002)
# ---------------------------------------------------------------------------

MAIN_SOURCE = ROOT / "api" / "app" / "main.py"
PASSAGE_MIRRORS_SOURCE = ROOT / "api" / "app" / "passage_mirrors.py"
ANALYTICS_SOURCE = ROOT / "api" / "app" / "analytics.py"
PASSAGE_ID = "P-TEST-0001"
EVENT_NAME = "orphan-698.jpg"
BENIGN_ERROR_TEXT = "backend unavailable"


def _extract_function(source: Path, name: str, namespace: dict) -> None:
    """Load ONE real function body into a controlled namespace.

    Repo AST pattern (tests/test_water_passage.py::load_api_functions):
    decorators are stripped (they reference the FastAPI app object, which is
    not part of the output boundary under test) and the body executed is the
    REAL production source, so the print sites are exactly the shipped ones.
    """
    tree = ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one {name} in {source}")
    function = copy.deepcopy(matches[0])
    function.decorator_list = []
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(source), "exec"), namespace)


class _Raises:
    """Callable that raises the CURRENT error — forces the error branch."""

    def __init__(self, error: BaseException) -> None:
        self.error = error

    def __call__(self, *args: object, **kwargs: object):
        raise self.error


class _FakeCursor:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def fetchall(self) -> list:
        return list(self._rows)

    def __iter__(self):
        # sqlite3 cursors are iterable; sweep_events_media iterates the
        # cursor directly while import_existing_passages calls fetchall().
        return iter(self._rows)


class _FakeConnection:
    """execute() -> cursor.fetchall() stub for the sqlite seam."""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    def execute(self, *_args: object, **_kwargs: object) -> _FakeCursor:
        return _FakeCursor(self._rows)


@contextmanager
def _fake_db(rows: list):
    yield _FakeConnection(rows)


class _HTTPException(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _form_default(*_args: object, **_kwargs: object) -> None:
    # FastAPI Form/File/Header defaults are evaluated at def time inside the
    # extracted function; their identity is irrelevant to the print boundary.
    return None


class DirectStderrPrintRedactionTests(unittest.TestCase):
    """AC-002: each wrapped direct ``print(..., file=sys.stderr)`` site masks
    a credential carried by the exception text, keeps the fixed prefix and
    neighbouring text, and leaves a benign error line byte-identical."""

    def capture(self, call) -> str:
        buffer = io.StringIO()
        with redirect_stderr(buffer):
            call()
        return buffer.getvalue()

    def assert_masked_line(self, stderr: str, prefix: str, canary: str) -> None:
        self.assertIn(prefix, stderr, f"fixed prefix missing: {stderr!r}")
        self.assertIn("backend token=" + REDACTED, stderr, f"stderr: {stderr!r}")
        self.assertIn(REDACTED, stderr)
        self.assertNotIn(canary, stderr, f"canary leaked: {stderr!r}")
        self.assertNotIn(REDACTED + REDACTED, stderr)

    def assert_benign_identical(self, stderr: str, prefix: str) -> None:
        self.assertEqual(stderr, prefix + BENIGN_ERROR_TEXT + "\n")

    def test_main_passage_registry_mirror_print_masks_credential(self) -> None:
        """Site 1 — api/app/main.py post_cam1_passage (AC-002)."""
        canary = _canary()
        holder = {"error": RuntimeError(f"backend token={canary}")}

        def persist_passage_object(_passage: dict) -> None:
            raise holder["error"]

        namespace: dict = {
            "json": json,
            "sys": sys,
            "Any": Any,
            "Dict": Dict,
            "Optional": Optional,
            "UploadFile": object,
            "Form": _form_default,
            "File": _form_default,
            "Header": _form_default,
            "HTTPException": _HTTPException,
            "require_auth": lambda _authorization: None,
            "store": SimpleNamespace(find_nonfinite_json_value=lambda _payload: None),
            "upsert_water_passage": lambda _payload, snapshot_bytes=None: {
                "passage_id": PASSAGE_ID
            },
            "persist_passage_object": persist_passage_object,
            "sweep_events_media": lambda: 0,
            "redact_log_text": redact_log_text,
        }
        _extract_function(MAIN_SOURCE, "post_cam1_passage", namespace)
        prefix = f"passage registry mirror failed for {PASSAGE_ID}: "
        metadata = json.dumps({"passage_id": PASSAGE_ID})

        stderr = self.capture(
            lambda: asyncio.run(namespace["post_cam1_passage"](metadata=metadata))
        )
        self.assert_masked_line(stderr, prefix, canary)

        holder["error"] = RuntimeError(BENIGN_ERROR_TEXT)
        stderr = self.capture(
            lambda: asyncio.run(namespace["post_cam1_passage"](metadata=metadata))
        )
        self.assert_benign_identical(stderr, prefix)

    def test_import_existing_passages_print_masks_credential(self) -> None:
        """Site 2 — api/app/passage_mirrors.py import_existing_passages."""
        canary = _canary()
        holder = {"error": RuntimeError(f"backend token={canary}")}

        def persist_passage_object(_passage: dict) -> None:
            raise holder["error"]

        namespace: dict = {
            "sys": sys,
            "redact_log_text": redact_log_text,
            "open_passages_db": lambda: _fake_db([{"passage_id": PASSAGE_ID}]),
            "persist_passage_object": persist_passage_object,
        }
        _extract_function(PASSAGE_MIRRORS_SOURCE, "import_existing_passages", namespace)
        prefix = f"passage registry mirror failed for {PASSAGE_ID}: "

        stderr = self.capture(namespace["import_existing_passages"])
        self.assert_masked_line(stderr, prefix, canary)

        holder["error"] = RuntimeError(BENIGN_ERROR_TEXT)
        stderr = self.capture(namespace["import_existing_passages"])
        self.assert_benign_identical(stderr, prefix)

    def test_delete_passage_mirrors_print_masks_credential(self) -> None:
        """Site 3 — api/app/passage_mirrors.py _delete_passage_mirrors."""
        canary = _canary()
        namespace: dict = {
            "sys": sys,
            "List": List,
            "redact_log_text": redact_log_text,
            "open_objects_db": _Raises(RuntimeError(f"backend token={canary}")),
        }
        _extract_function(PASSAGE_MIRRORS_SOURCE, "_delete_passage_mirrors", namespace)
        prefix = "passage mirror sync failed: "

        stderr = self.capture(lambda: namespace["_delete_passage_mirrors"]([PASSAGE_ID]))
        self.assert_masked_line(stderr, prefix, canary)

        namespace["open_objects_db"].error = RuntimeError(BENIGN_ERROR_TEXT)
        stderr = self.capture(lambda: namespace["_delete_passage_mirrors"]([PASSAGE_ID]))
        self.assert_benign_identical(stderr, prefix)

    def test_events_media_sweep_skipped_print_masks_credential(self) -> None:
        """Site 4 — api/app/analytics.py sweep_events_media (open_objects_db
        failure branch prints 'events media sweep skipped')."""
        canary = _canary()
        with tempfile.TemporaryDirectory(prefix="sea-speed-698-sweep-") as temp:
            namespace: dict = {
                "time": time,
                "Path": Path,
                "Optional": Optional,
                "sys": sys,
                "EVENTS_MEDIA_DIR": Path(temp),
                "_events_sweep_state": {"last": 0.0},
                "EVENTS_MEDIA_GRACE_SECONDS": 24 * 3600,
                "EVENTS_SWEEP_INTERVAL_SECONDS": 3600,
                "open_objects_db": _Raises(RuntimeError(f"backend token={canary}")),
                "redact_log_text": redact_log_text,
            }
            _extract_function(ANALYTICS_SOURCE, "sweep_events_media", namespace)
            prefix = "events media sweep skipped: "

            stderr = self.capture(lambda: namespace["sweep_events_media"](force=True))
            self.assert_masked_line(stderr, prefix, canary)

            namespace["open_objects_db"].error = RuntimeError(BENIGN_ERROR_TEXT)
            stderr = self.capture(lambda: namespace["sweep_events_media"](force=True))
            self.assert_benign_identical(stderr, prefix)

    def test_events_media_sweep_unlink_print_masks_credential(self) -> None:
        """Site 5 — api/app/analytics.py sweep_events_media (unlink failure
        branch prints 'events media sweep failed for <name>'). Only the
        filesystem operation is forced to fail with a crafted OSError; the
        print boundary under test is the real production source."""
        canary = _canary()
        with tempfile.TemporaryDirectory(prefix="sea-speed-698-unlink-") as temp:
            media = Path(temp)
            target = media / EVENT_NAME
            target.write_bytes(b"\xff\xd8fixture")

            def open_objects_db():
                return _fake_db([])

            namespace: dict = {
                "time": time,
                "Path": Path,
                "Optional": Optional,
                "sys": sys,
                "EVENTS_MEDIA_DIR": media,
                "_events_sweep_state": {"last": 0.0},
                "EVENTS_MEDIA_GRACE_SECONDS": 24 * 3600,
                "EVENTS_SWEEP_INTERVAL_SECONDS": 3600,
                "open_objects_db": open_objects_db,
                "redact_log_text": redact_log_text,
            }
            _extract_function(ANALYTICS_SOURCE, "sweep_events_media", namespace)
            prefix = f"events media sweep failed for {EVENT_NAME}: "
            # The grace period must be exceeded so unlink() is reached.
            future_now = lambda: time.time() + 200000  # noqa: E731

            path_cls = type(media)
            with mock.patch.object(
                path_cls, "unlink", side_effect=OSError(f"backend token={canary}")
            ):
                stderr = self.capture(
                    lambda: namespace["sweep_events_media"](force=True, now=future_now())
                )
            self.assert_masked_line(stderr, prefix, canary)

            with mock.patch.object(
                path_cls, "unlink", side_effect=OSError(BENIGN_ERROR_TEXT)
            ):
                stderr = self.capture(
                    lambda: namespace["sweep_events_media"](force=True, now=future_now())
                )
            self.assert_benign_identical(stderr, prefix)


# ---------------------------------------------------------------------------
# 8. F1 (peer review): JSON-style labelled credentials are a false negative
# ---------------------------------------------------------------------------


class JsonLabelledCredentialTests(unittest.TestCase):
    """F1: ``_LABEL_RE`` requires ``\\s*[:=]\\s*`` IMMEDIATELY after the label,
    so the JSON form ``{"token": "<canary>"}`` — a quote between key and
    colon — is not masked, and the atom heuristic only catches >=32-char
    digest-shaped values, so a short/mixed token survives untouched.

    The three positive tests are RED on the current regex (observed leak);
    the two negatives pin that the fix must keep the field-boundary
    lookbehind (monkey) and the labelled-digest exemption (sha256) intact."""

    def assert_json_structure_intact(self, out: str) -> None:
        self.assertTrue(out.startswith('{"'), out)
        self.assertTrue(out.endswith('"}'), out)
        self.assertEqual(out.count("{"), out.count("}"), out)

    def test_json_token_value_is_masked(self) -> None:
        canary = _canary()
        line = '{"token": "%s"}' % canary
        out = redact_log_text(line)
        self.assertNotIn(canary, out, f"JSON token canary leaked: {out!r}")
        self.assertIn('"token": "%s"' % REDACTED, out)
        self.assert_json_structure_intact(out)

    def test_json_access_token_value_is_masked(self) -> None:
        canary = _canary()
        line = '{"access_token": "%s"}' % canary
        out = redact_log_text(line)
        self.assertNotIn(canary, out, f"JSON access_token canary leaked: {out!r}")
        self.assertIn('"access_token": "%s"' % REDACTED, out)
        self.assert_json_structure_intact(out)

    def test_json_api_key_value_is_masked(self) -> None:
        canary = _canary()
        line = '{"api_key": "%s"}' % canary
        out = redact_log_text(line)
        self.assertNotIn(canary, out, f"JSON api_key canary leaked: {out!r}")
        self.assertIn('"api_key": "%s"' % REDACTED, out)
        self.assert_json_structure_intact(out)

    def test_json_monkey_field_stays_byte_identical(self) -> None:
        # Field-boundary lookbehind: "key" inside "monkey" must never match,
        # quoted-key support must not weaken it.
        line = '{"monkey": "banana"}'
        self.assertEqual(redact_log_text(line), line)

    def test_json_sha256_digest_field_stays_byte_identical(self) -> None:
        # Labelled digest fields are structured fields, not credentials:
        # spec (specs/698-log-redaction/spec.md) — "labelled digests are not
        # matched"; the byte-identity must survive the quoted-key fix.
        value = _hex_canary()
        line = '{"sha256": "%s"}' % value
        self.assertEqual(
            redact_log_text(line),
            line,
            "labelled JSON digest field must stay byte-identical",
        )


# ---------------------------------------------------------------------------
# 9. F2 (peer review): the production import trigger for
#    install_api_redaction (api/app/main.py:306)
# ---------------------------------------------------------------------------


def _wiring_child(mode: str, canary: str) -> str:
    """Child script: mirror the PRODUCTION uvicorn startup order.

    uvicorn.main.run builds ``Config`` first — ``Config.__init__`` calls
    ``configure_logging()``, which creates the ``uvicorn.access`` handler
    (real ``AccessFormatter``) — and only then ``load_app()`` imports the
    app module, whose import runs ``install_api_redaction()`` (main.py:306).
    The script snapshots both loggers' handler formatters before and after
    that import and prints them as JSON.
    """
    if mode == "app-dir":
        path_setup = 'sys.path.insert(0, os.path.join(os.getcwd(), "api", "app"))'
        app_str = "main:app"
    else:
        path_setup = "sys.path.insert(0, os.getcwd())"
        app_str = "api.app.main:app"
    lines = [
        "import json",
        "import logging",
        "import os",
        "import sys",
        "",
        path_setup,
        "",
        "import uvicorn",
        "# Production order: Config.__init__ -> configure_logging() creates the",
        "# uvicorn handlers; load_app() then imports the app module (main.py:306",
        "# runs install_api_redaction() while those handlers already exist).",
        f'config = uvicorn.Config(app="{app_str}")',
        "# uvicorn's default LOGGING_CONFIG gives uvicorn.error no direct handler",
        "# (its records propagate to the uvicorn logger); attach one so the error",
        "# side of the wrap is observable on this logger.",
        "error_handler = logging.NullHandler()",
        'error_handler.setFormatter(logging.Formatter("%(message)s"))',
        'logging.getLogger("uvicorn.error").addHandler(error_handler)',
        "",
        "def snapshot():",
        "    out = {}",
        '    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):',
        "        handlers = logging.getLogger(name).handlers",
        "        out[name] = {",
        '            "count": len(handlers),',
        '            "formatters": [',
        '                type(h.formatter).__module__ + "." + type(h.formatter).__name__',
        "                for h in handlers",
        "            ],",
        '            "all_wrapped": bool(handlers) and all(',
        '                getattr(h.formatter, "_sea_speed_698_redacting_formatter", False)',
        "                for h in handlers",
        "            ),",
        "        }",
        "    return out",
        "",
        "before = snapshot()",
        "config.load_app()  # the production app import",
        "after = snapshot()",
        "# Behavioral probe: an uvicorn.error record with exc_info carries a",
        "# credential inside its traceback; it propagates to the parent uvicorn",
        "# logger, whose default handler must not leak it.",
        "try:",
        f'    raise RuntimeError("backend token=" + {canary!r})',
        "except RuntimeError:",
        '    logging.getLogger("uvicorn.error").error("startup failed", exc_info=True)',
        'print(json.dumps({"before": before, "after": after}))',
        "",
    ]
    return "\n".join(lines)


@unittest.skipUnless(
    HTTP_TESTS_ENABLED,
    "fastapi/httpx are not installed (the wiring test runs where the "
    "declared pins are installed, same guard as tests/test_591...)",
)
class UvicornWiringSubprocessTests(unittest.TestCase):
    """F2: importing the REAL API app in BOTH import modes must leave every
    uvicorn access/error handler formatter wrapped in RedactingFormatter —
    proving main.py:306 actually invokes install_api_redaction(), rather
    than the helper merely working when called directly."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="sea-speed-698-wiring-")
        self.addCleanup(temp.cleanup)
        self.base_dir = Path(temp.name)
        self.deployed_file = self.base_dir / "deploy-state" / "current-release"
        self.deployed_file.parent.mkdir(parents=True, exist_ok=True)
        self.deployed_file.write_text(DEPLOYED_COMMIT_FIXTURE + "\n", encoding="utf-8")

    def run_child(self, mode: str, canary: str | None = None) -> subprocess.CompletedProcess:
        canary = canary or _canary()
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
        env.pop("SEA_SPEED_SOURCE_COMMIT", None)
        return subprocess.run(
            [sys.executable, "-c", _wiring_child(mode, canary)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def test_import_wires_redacting_formatters_in_both_modes(self) -> None:
        if _access_formatter_class() is None:
            self.skipTest("uvicorn is not installed (api-lock pin)")
        for mode in ("package", "app-dir"):
            with self.subTest(mode=mode):
                completed = self.run_child(mode)
                self.assertEqual(
                    completed.returncode,
                    0,
                    f"[{mode}] child failed\nstdout: {completed.stdout!r}\n"
                    f"stderr: {completed.stderr!r}",
                )
                payload = json.loads(completed.stdout.strip().splitlines()[-1])
                before_access = payload["before"]["uvicorn.access"]
                # Precondition: uvicorn's own configure_logging() created a
                # REAL AccessFormatter handler before the app import.
                self.assertGreaterEqual(
                    before_access["count"], 1, f"[{mode}] {before_access}"
                )
                self.assertTrue(
                    any("AccessFormatter" in name for name in before_access["formatters"]),
                    f"[{mode}] pre-import access formatter is not uvicorn's: {before_access}",
                )
                for name in ("uvicorn.access", "uvicorn.error"):
                    before = payload["before"][name]
                    after = payload["after"][name]
                    # Nothing wrapped before the import: the wrap is caused by
                    # importing the app, not by Config/uvicorn itself.
                    self.assertFalse(
                        before["all_wrapped"],
                        f"[{mode}] {name} already wrapped before app import: {before}",
                    )
                    self.assertGreaterEqual(
                        after["count"], 1, f"[{mode}] {name} has no handler: {after}"
                    )
                    self.assertTrue(
                        after["all_wrapped"],
                        f"[{mode}] {name} formatters NOT wrapped by app import: {after}",
                    )
                    for formatter_name in after["formatters"]:
                        self.assertIn("RedactingFormatter", formatter_name)

    def test_uvicorn_parent_logger_traceback_path_is_sanitized(self) -> None:
        """Peer review: uvicorn's default LOGGING_CONFIG gives ``uvicorn.error``
        NO handler of its own — its records (incl. tracebacks) propagate to the
        parent ``uvicorn`` logger, whose ``default`` handler carries a plain
        Formatter. ``install_api_redaction()`` must therefore wrap that handler
        too (specs/698-log-redaction/spec.md:96: "Uvicorn error / traceback ...
        formatter-appended traceback covered").

        Two assertions, production-faithful (no synthetic handler needed):
        after importing the real app the parent ``uvicorn`` handler formatter
        is a RedactingFormatter, and an exc_info record emitted through
        ``uvicorn.error`` reaches stderr with the traceback structure intact
        but the canary masked. RED on current code: ``uvicorn`` is not in
        ``_UVICORN_LOGGER_NAMES``."""
        if _access_formatter_class() is None:
            self.skipTest("uvicorn is not installed (api-lock pin)")
        for mode in ("package", "app-dir"):
            with self.subTest(mode=mode):
                canary = _canary()
                completed = self.run_child(mode, canary)
                self.assertEqual(
                    completed.returncode,
                    0,
                    f"[{mode}] child failed\nstdout: {completed.stdout!r}\n"
                    f"stderr: {completed.stderr!r}",
                )
                payload = json.loads(completed.stdout.strip().splitlines()[-1])
                parent_before = payload["before"]["uvicorn"]
                parent_after = payload["after"]["uvicorn"]
                # Config created the parent handler with a plain formatter and
                # the import must have wrapped it.
                self.assertFalse(
                    parent_before["all_wrapped"],
                    f"[{mode}] parent uvicorn handler wrapped before import: {parent_before}",
                )
                self.assertGreaterEqual(
                    parent_after["count"], 1, f"[{mode}] {parent_after}"
                )
                self.assertTrue(
                    parent_after["all_wrapped"],
                    f"[{mode}] parent uvicorn handler NOT wrapped by app import: "
                    f"{parent_after}",
                )
                for formatter_name in parent_after["formatters"]:
                    self.assertIn("RedactingFormatter", formatter_name)
                # Behavioral half: the propagated traceback must keep its
                # structure while the credential inside it is masked.
                stderr = completed.stderr
                self.assertNotIn(
                    canary, stderr, f"[{mode}] traceback leaked canary: {stderr!r}"
                )
                self.assertIn("Traceback (most recent call last):", stderr, stderr)
                self.assertIn("RuntimeError", stderr, stderr)
                self.assertIn(REDACTED, stderr, stderr)


if __name__ == "__main__":
    unittest.main()
