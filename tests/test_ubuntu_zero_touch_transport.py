"""Zero-touch Ubuntu transport contract (issue #398 wave 5 conversion).

Earlier revisions of this file pinned the transport with raw source-text
``assertIn`` markers on the workflow YAML and the two shell scripts. Text
pins pass on comments and stale code alike — the Ubuntu deploy workflow even
carried a comment block whose only purpose was to keep the old
source-protection pins green while the real checks moved into the shared
composite action. Every text pin now has an executable or structural twin:

- Workflow pins read the PARSED workflow (``yaml.safe_load``): step env
  wiring, run-text literals taken from parsed steps, and the composite-action
  walk (workflow -> ``./.github/actions/verify-exact-release`` -> source
  protection before policy) — all comment-blind.
- The gate's forced-command entrypoint is EXECUTED: the real ``fail()`` +
  ``validate_request()`` + entrypoint slice runs against stub ``id``/``sudo``
  binaries and proves the protocol regex, the field validation and the exact
  ``sudo -n <gate> --execute`` hand-off. The script's hardcoded ``PATH=``
  reset is the one omitted line (documented below); it exists to pin the
  host PATH and would only defeat the stub dir.
- The bootstrap's allowlist machinery is EXECUTED: the real
  ``effective_allowusers`` / ``allowusers_contains`` /
  ``set_allowusers_membership`` / ``restore_sshd_hardening`` functions run
  with the readonly system paths redirected into a tmp fixture and stub
  ``sshd``/``systemctl`` binaries — add, idempotent add, remove, last-
  principal refusal, effective-policy divergence and both rollback paths.
- The bootstrap's password boundary is EXECUTED as a round-trip: the real
  ``usermod --password '*NP*'`` + ``getent shadow`` read-back/verify lines
  run against a fixture shadow file (passing and locked variants).
- Pins that only a root host can exercise (sudoers installation, gate
  ownership/mode, deploy-transaction internals behind the root+network
  gate) stay byte-verbatim STATIC_POLICY pins with in-code justifications;
  specs/398-wave5/plan.md carries the full pin->twin mapping table.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
VERIFY_RELEASE_ACTION = ROOT / ".github/actions/verify-exact-release/action.yml"
GATE_SCRIPT = ROOT / "scripts/operations/sea_speed_ubuntu_zero_touch_gate.sh"
BOOTSTRAP_SCRIPT = ROOT / "scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh"


def load_workflow(path: Path) -> dict:
    """Parse a workflow/composite-action YAML file into its structure.

    PyYAML resolves the bare ``on:`` trigger key to boolean True; both
    spellings are accepted so the trigger block stays reachable.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} did not parse to a mapping"
    return data


def iter_strings(node) -> list[str]:
    """Every string value in the parsed structure (keys and values)."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        out: list[str] = []
        for key, value in node.items():
            out.extend(iter_strings(key))
            out.extend(iter_strings(value))
        return out
    if isinstance(node, list):
        return [s for item in node for s in iter_strings(item)]
    return []


def steps_of(data: dict) -> list[dict]:
    """All steps of a workflow, or of a composite action."""
    jobs = data.get("jobs")
    if isinstance(jobs, dict):
        return [step for job in jobs.values() for step in (job or {}).get("steps") or []]
    return list((data.get("runs") or {}).get("steps") or [])


def run_text(step: dict) -> str:
    return str(step.get("run") or "")


def code_lines(source: str) -> list[str]:
    """Non-comment, non-blank lines (comment-blind ban surface for shell)."""
    return [
        line for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


class UbuntuZeroTouchTransportTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_workflow_uses_vps_proxyjump_and_zero_operator_fallback(self):
        # Parsed-structure twin (issue #398 wave 5): the transport wiring is
        # read from the parsed steps — the ssh config literals from the run
        # block of the step that writes the config, the credential names from
        # that step's env values, the protocol invocation from the execute
        # step, and the zero-operator evidence from the summary step.
        data = load_workflow(WORKFLOWS / "deploy-ubuntu-worker.yml")
        steps = steps_of(data)
        transport = next(
            step for step in steps
            if step.get("name") == "Configure restricted VPS ProxyJump to Ubuntu Worker"
        )
        env_values = "\n".join(str(value) for value in transport["env"].values())
        for secret in (
            "UBUNTU_DEPLOY_SSH_PRIVATE_KEY",
            "UBUNTU_DEPLOY_SSH_KNOWN_HOSTS",
            "VPS_SSH_PRIVATE_KEY",
            "VPS_SSH_KNOWN_HOSTS",
        ):
            self.assertIn(secret, env_values)
        config_run = transport["run"]
        for marker in (
            "ProxyJump sea-speed-vps-jump",
            "HostName 10.123.239.102",
            "User sea-speed-deploy",
            "StrictHostKeyChecking yes",
            "ClearAllForwardings yes",
        ):
            self.assertIn(marker, config_run)
        execute = next(
            step for step in steps
            if step.get("name") == "Execute restricted Ubuntu deployment protocol"
        )
        self.assertIn(
            "sea-speed-ubuntu-deploy-v1 $DEPLOY_SHA $CANONICAL_ISSUE $ARTIFACT_SHA",
            execute["run"],
        )
        summary = next(step for step in steps if step.get("name") == "Deployment summary")
        self.assertIn("Operator actions expected: 0", summary["run"])
        # The one-command fallback stays retired everywhere in the parsed
        # structure (comments included would be weaker; parsed strings are
        # the executable surface).
        joined = "\n".join(iter_strings(data))
        for banned in ("ubuntu-worker-one-command.sh", "Build one-command fallback", "StrictHostKeyChecking=no"):
            self.assertNotIn(banned, joined)

    def test_gate_is_exact_forced_command_and_recomputes_artifact(self):
        # Split twin (issue #398 wave 5): the entrypoint half is EXECUTED in
        # GateForcedCommandExecutedTests below; this half pins the
        # execute_root() internals that only a root host with network can
        # run (origin fetch, deterministic artifact recompute, deploy
        # transaction) as an ORDERED function-scoped scan — stronger than
        # the raw whole-file assertIn it replaces, and blind to comments
        # outside the function.
        gate = self.read("scripts/operations/sea_speed_ubuntu_zero_touch_gate.sh")
        start = gate.index("execute_root() {")
        end = gate.index('\n}\n\nif [[ "${1:-}" == "--execute" ]]', start)
        execute_root = gate[start:end]
        anchors = (
            "target is not present in origin/main",
            "target is not on current main first-parent history",
            "deploy/worker/ubuntu/deploy-authorized.sh",
            "build_exact_artifacts.py",
            "artifact SHA-256 does not match deterministic exact Ubuntu artifact",
        )
        positions = [execute_root.index(anchor) for anchor in anchors]
        self.assertEqual(positions, sorted(positions), "execute_root gate order drifted")
        self.assertIn("rev-list --first-parent", execute_root)
        # STATIC_POLICY: the entrypoint must never interpret the client
        # command — bans kept on the comment-stripped code surface so a
        # documentary comment cannot redden them.
        code = "\n".join(code_lines(gate))
        self.assertNotIn("eval ", code)
        self.assertNotIn('bash -c "$SSH_ORIGINAL_COMMAND"', code)

    def test_gate_cleans_local_stage_before_execute_root_returns(self):
        gate = self.read("scripts/operations/sea_speed_ubuntu_zero_touch_gate.sh")
        start = gate.index("execute_root() {")
        end = gate.index('\n}\n\nif [[ "${1:-}" == "--execute" ]]', start)
        execute_root = gate[start:end]
        self.assertIn("trap cleanup EXIT", execute_root)
        self.assertIn('cat "$manifest"\n  cleanup\n  trap - EXIT', execute_root)
        self.assertLess(execute_root.index('cat "$manifest"'), execute_root.index("trap - EXIT"))

    def test_bootstrap_installs_only_dedicated_restricted_boundary(self):
        # STATIC_POLICY: sudoers/authorized_keys installation runs once per
        # worker lifetime as real root on the real host; executing the slice
        # here would stub the very ownership/mode/visudo checks these pins
        # exist for. The constants are read back from the script's own
        # declarations and the bans are comment-blind.
        bootstrap = self.read("scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh")
        self.assertEqual(
            re.search(r'readonly DEPLOY_USER="([^"]+)"', bootstrap).group(1),
            "sea-speed-deploy",
        )
        self.assertIn('restrict,command="%s"', bootstrap)
        self.assertIn("visudo -cf", bootstrap)
        self.assertIn("NOPASSWD:", bootstrap)
        self.assertIn("sea-speed-ubuntu-zero-touch-gate --execute *", bootstrap)
        code = "\n".join(code_lines(bootstrap))
        self.assertNotIn("NOPASSWD: ALL", code)
        self.assertNotIn("ssh-keygen -t", code)
        self.assertIn("--remove", bootstrap)

    def test_bootstrap_disables_password_without_locking_public_key_account(self):
        # The write/read-back/verify chain is EXECUTED in
        # BootstrapPasswordBoundaryExecutedTests below. The removal-path
        # lock and the evidence literal stay as source pins: the removal
        # branch is root-host-only and the evidence line is the operation's
        # fail-closed contract (STATIC_POLICY).
        bootstrap = self.read("scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh")
        self.assertIn("PASSWORD_AUTH=DISABLED_PUBLICKEY_ACCOUNT=ACCESSIBLE", bootstrap)
        self.assertNotIn('passwd -l "$DEPLOY_USER"', bootstrap)
        self.assertIn('usermod -L "$DEPLOY_USER"', bootstrap)

    def test_bootstrap_transactionally_admits_deploy_user_to_existing_sshd_allowlist(self):
        # The transactional machinery is EXECUTED in
        # BootstrapAllowUsersExecutedTests below (add / idempotent add /
        # remove / last-principal refusal / divergence / both rollbacks).
        # What remains here is the canonical path declaration and the
        # main-flow evidence literal (root-host-only, STATIC_POLICY).
        bootstrap = self.read("scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh")
        self.assertEqual(
            re.search(r'readonly SSHD_HARDENING_PATH="([^"]+)"', bootstrap).group(1),
            "/etc/ssh/sshd_config.d/00-sea-speed-hardening.conf",
        )
        self.assertIn("SSHD_ALLOWUSERS=", bootstrap)
        self.assertNotIn("AllowUsers sea-speed-deploy\n", bootstrap)

    def test_effective_allowusers_parser_accumulates_all_sshd_rows(self):
        # Executed twin in BootstrapAllowUsersExecutedTests: the real awk
        # parser runs against a multi-row sshd -T fixture and must emit every
        # principal exactly once, space-joined.
        bootstrap = self.read("scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh")
        start = bootstrap.index("effective_allowusers() {")
        end = bootstrap.index("\n}\n\nallowusers_contains()", start)
        self.assertIn("for (i = 2; i <= NF; i++)", bootstrap[start:end])

    def test_source_protection_is_checked_before_transport(self):
        # Parsed composite walk (issue #398 wave 5): all three production
        # workflows verify protected source through the shared composite
        # action (the two deploy workflows carry the old markers only as
        # comments — the raw-text pins passed on them). The composite runs
        # source protection with both required contexts, and the Ubuntu
        # workflow runs it before any transport configuration.
        composite = load_workflow(VERIFY_RELEASE_ACTION)
        composite_steps = steps_of(composite)
        protection = next(
            step for step in composite_steps
            if "verify_source_protection.py" in run_text(step)
        )
        self.assertIn('--require-context "Repository validation"', protection["run"])
        self.assertIn('--require-context "quality-integration"', protection["run"])
        policy = next(
            step for step in composite_steps
            if "evaluate_production_policy.py" in run_text(step)
        )
        self.assertLess(
            composite_steps.index(protection),
            composite_steps.index(policy),
            "source protection must run before the policy evaluation",
        )
        for name in ("deploy-vps.yml", "deploy-ubuntu-worker.yml"):
            data = load_workflow(WORKFLOWS / name)
            self.assertTrue(
                any(step.get("uses") == "./.github/actions/verify-exact-release" for step in steps_of(data)),
                name,
            )
        router = load_workflow(WORKFLOWS / "deploy-runtime-autonomous.yml")
        router_protection = next(
            step for step in steps_of(router)
            if "verify_source_protection.py" in run_text(step)
        )
        self.assertIn('--require-context "Repository validation"', router_protection["run"])
        self.assertIn('--require-context "quality-integration"', router_protection["run"])
        ubuntu_steps = steps_of(load_workflow(WORKFLOWS / "deploy-ubuntu-worker.yml"))
        verify_index = next(
            index for index, step in enumerate(ubuntu_steps)
            if step.get("uses") == "./.github/actions/verify-exact-release"
        )
        transport_index = next(
            index for index, step in enumerate(ubuntu_steps)
            if step.get("name") == "Configure restricted VPS ProxyJump to Ubuntu Worker"
        )
        self.assertLess(verify_index, transport_index)


def _gate_entrypoint_source() -> str:
    """The real gate script's constants + fail()/validate_request() + entrypoint.

    The script's hardcoded ``PATH=/usr/sbin:/usr/bin:/sbin:/bin`` reset is the
    one omitted pair of lines: it pins the host PATH on the real worker and
    would only defeat the test's stub dir. Everything else is real script
    bytes, including the protocol regex and the ``exec sudo`` hand-off.
    """
    source = GATE_SCRIPT.read_text(encoding="utf-8")
    readonly_block = "\n".join(
        line for line in source[:source.index("fail() {")].splitlines()
        if line.startswith("readonly ")
    )
    helpers = source[source.index("fail() {"):source.index("execute_root() {")]
    entry = source[source.index('if [[ "${1:-}" == "--execute" ]]; then'):]
    return "set -euo pipefail\n" + readonly_block + "\n" + helpers + entry


def _gate_helpers_source() -> str:
    """The real gate script's constants + fail()/validate_request() helpers.

    Used to execute validators that are reachable only on paths the
    entrypoint harness cannot take (the root-gated ``--execute`` path); the
    entrypoint block is deliberately excluded so sourcing defines functions
    without running the dispatch.
    """
    source = GATE_SCRIPT.read_text(encoding="utf-8")
    readonly_block = "\n".join(
        line for line in source[:source.index("fail() {")].splitlines()
        if line.startswith("readonly ")
    )
    helpers = source[source.index("fail() {"):source.index("execute_root() {")]
    return "set -euo pipefail\n" + readonly_block + "\n" + helpers


class GateForcedCommandExecutedTests(unittest.TestCase):
    """The forced-command entrypoint, executed (issue #398 wave 5)."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="398-w5-gate."))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.stub_dir = self.tmp / "stubs"
        self.stub_dir.mkdir()
        self.sudo_calls = self.tmp / "sudo_calls.txt"
        _write_executable(self.stub_dir / "id", "#!/bin/sh\necho sea-speed-deploy\n")
        _write_executable(
            self.stub_dir / "sudo",
            '#!/bin/sh\nprintf \'%s\\n\' "$@" >> "$SUDO_CALLS"\n',
        )
        self.script = self.tmp / "gate_entry.sh"
        self.script.write_text(_gate_entrypoint_source(), encoding="utf-8")
        self.helpers = self.tmp / "gate_helpers.sh"
        self.helpers.write_text(_gate_helpers_source(), encoding="utf-8")

    def _run(self, original_command: str) -> subprocess.CompletedProcess[str]:
        self.sudo_calls.unlink(missing_ok=True)
        env = {
            **os.environ,
            "PATH": f"{self.stub_dir}:{os.environ['PATH']}",
            "SSH_ORIGINAL_COMMAND": original_command,
            "SUDO_CALLS": str(self.sudo_calls),
        }
        return subprocess.run(
            ["bash", str(self.script)], capture_output=True, text=True, env=env,
        )

    def _run_function(self, function: str, *args: str) -> subprocess.CompletedProcess[str]:
        """Execute a helper function (real script bytes) from the extracted
        helpers source — for validators reachable only on paths the
        entrypoint harness cannot take (e.g. root-gated --execute)."""
        driver = self.tmp / "fn_driver.sh"
        driver.write_text(f'source "{self.helpers}"\n{function} "$@"\n', encoding="utf-8")
        env = {
            **os.environ,
            "PATH": f"{self.stub_dir}:{os.environ['PATH']}",
            "SUDO_CALLS": str(self.sudo_calls),
        }
        return subprocess.run(
            ["bash", str(driver), *args], capture_output=True, text=True, env=env,
        )

    def _sudo_calls(self) -> list[str]:
        if not self.sudo_calls.exists():
            return []
        return self.sudo_calls.read_text(encoding="utf-8").splitlines()

    def test_protocol_command_is_parsed_and_handed_to_sudo_exact(self):
        target = "a" * 40
        artifact = "b" * 64
        result = self._run(f"sea-speed-ubuntu-deploy-v1 {target} 7 {artifact}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self._sudo_calls(),
            [
                "-n",
                "/usr/local/sbin/sea-speed-ubuntu-zero-touch-gate",
                "--execute",
                target,
                "7",
                artifact,
            ],
        )

    def test_unsupported_command_fails_closed_before_sudo(self):
        result = self._run("systemctl restart nginx")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unsupported restricted SSH command", result.stderr)
        self.assertEqual(self._sudo_calls(), [])

    def test_malformed_protocol_fields_are_rejected_before_sudo(self):
        # The entrypoint protocol regex is the FIRST validator: a command whose
        # fields are malformed never matches, so the entrypoint fails closed
        # with the generic rejection before validate_request (or sudo) runs.
        cases = (
            f"sea-speed-ubuntu-deploy-v1 {'A' * 40} 7 {'b' * 64}",
            f"sea-speed-ubuntu-deploy-v1 {'a' * 40} 0 {'b' * 64}",
            f"sea-speed-ubuntu-deploy-v1 {'a' * 40} 7 {'b' * 63}",
        )
        for command in cases:
            with self.subTest(command=command):
                result = self._run(command)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("unsupported restricted SSH command", result.stderr)
                self.assertEqual(self._sudo_calls(), [])

    def test_validate_request_messages_pin_each_malformed_field(self):
        # validate_request's specific messages are reachable on the --execute
        # (root) path; executed directly here so each field's fail literal is
        # pinned by real function bytes, not source text.
        cases = (
            ("A" * 40, "target must be a lowercase 40-character SHA"),
            ("a" * 40, "issue must be a positive integer"),
            ("b" * 63, "artifact SHA-256 must be lowercase 64 hex"),
        )
        for target, issue, artifact, message in (
            (cases[0][0], "7", "b" * 64, cases[0][1]),
            ("a" * 40, "0", "b" * 64, cases[1][1]),
            ("a" * 40, "7", cases[2][0], cases[2][1]),
        ):
            with self.subTest(field=message):
                result = self._run_function("validate_request", target, issue, artifact)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(message, result.stderr)


def _bootstrap_machinery_source(fixture: Path) -> str:
    """The bootstrap's allowlist machinery with system paths redirected.

    Documented sandbox adaptations (mechanical, behavior-preserving): the
    four readonly absolute system paths are redirected into the fixture tree
    and the path constants are exported so the ``sshd`` stub can read the
    canonical hardening file the script rewrites. DEPLOY_USER keeps the
    value declared by the real script; the function bodies are real script
    bytes.
    """
    source = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
    deploy_user = re.search(r'readonly DEPLOY_USER="([^"]+)"', source).group(1)
    machinery = source[source.index("reload_sshd() {"):source.index("public_key_file=")]
    header = "\n".join([
        "set -euo pipefail",
        f'readonly DEPLOY_USER="{deploy_user}"',
        f'readonly DEPLOY_HOME="{fixture / "home"}"',
        f'readonly GATE_PATH="{fixture / "gate" / "sea-speed-ubuntu-zero-touch-gate"}"',
        f'readonly SUDOERS_PATH="{fixture / "etc" / "sudoers.d" / "sea-speed-ubuntu-zero-touch"}"',
        f'readonly SSHD_HARDENING_PATH="{fixture / "etc" / "ssh" / "sshd_config.d" / "00-sea-speed-hardening.conf"}"',
        "export DEPLOY_HOME GATE_PATH SUDOERS_PATH SSHD_HARDENING_PATH",
    ])
    return header + "\n" + machinery


SSHD_STUB = """#!/bin/sh
if [ "$1" = "-t" ]; then exit "${SSHD_T_RC:-0}"; fi
if [ "$1" = "-T" ]; then
  if [ -n "$SSHD_EFFECTIVE_FILE" ]; then
    cat "$SSHD_EFFECTIVE_FILE"
  else
    # Real `sshd -T` normalizes keywords to lowercase in its dump; the raw
    # hardening file uses canonical camelCase, so emulate the normalization.
    grep -iE '^[[:space:]]*AllowUsers[[:space:]]' "$SSHD_HARDENING_PATH" 2>/dev/null \
      | awk '{$1 = tolower($1); print}' || true
  fi
  exit 0
fi
exit 0
"""

SYSTEMCTL_STUB = """#!/bin/sh
printf '%s\\n' "$*" >> "$SYSTEMCTL_CALLS"
exit "${SYSTEMCTL_RC:-0}"
"""

USERMOD_STUB = """#!/bin/sh
printf '%s\\n' "$@" >> "$USERMOD_CALLS"
password=""
while [ $# -gt 0 ]; do
  if [ "$1" = "--password" ]; then password="$2"; fi
  shift
done
if [ -n "$USERMOD_PASSWORD_OVERRIDE" ]; then password="$USERMOD_PASSWORD_OVERRIDE"; fi
if [ -n "$password" ] && [ -n "$SHADOW_FILE" ]; then
  printf 'sea-speed-deploy:%s:19999:0:99999:7:::\\n' "$password" > "$SHADOW_FILE"
fi
exit 0
"""

GETENT_STUB = """#!/bin/sh
if [ "$1" = "shadow" ] && [ -n "$SHADOW_FILE" ]; then
  cat "$SHADOW_FILE"
  exit 0
fi
if [ "$1" = "passwd" ]; then
  printf 'sea-speed-deploy:x:19999:19999::/var/lib/sea-speed-deploy:/bin/bash\\n'
  exit 0
fi
exit 1
"""


class BootstrapAllowUsersExecutedTests(unittest.TestCase):
    """The bootstrap's AllowUsers machinery, executed (issue #398 wave 5)."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="398-w5-allowusers."))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.fixture = self.tmp / "root"
        (self.fixture / "etc" / "ssh" / "sshd_config.d").mkdir(parents=True)
        self.hardening = self.fixture / "etc" / "ssh" / "sshd_config.d" / "00-sea-speed-hardening.conf"
        self.stub_dir = self.tmp / "stubs"
        self.stub_dir.mkdir()
        self.systemctl_calls = self.tmp / "systemctl_calls.txt"
        _write_executable(self.stub_dir / "sshd", SSHD_STUB)
        _write_executable(
            self.stub_dir / "systemctl",
            SYSTEMCTL_STUB.replace("$SYSTEMCTL_CALLS", str(self.systemctl_calls)),
        )
        self.machinery = self.tmp / "machinery.sh"
        self.machinery.write_text(_bootstrap_machinery_source(self.fixture), encoding="utf-8")

    def _run_machinery(self, call: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        driver = self.tmp / "driver.sh"
        driver.write_text(f'source "{self.machinery}"\n{call}\n', encoding="utf-8")
        env = {
            **os.environ,
            "PATH": f"{self.stub_dir}:{os.environ['PATH']}",
            **(extra_env or {}),
        }
        return subprocess.run(
            ["bash", str(driver)], capture_output=True, text=True, env=env, cwd=self.tmp,
        )

    def _write_hardening(self, *allowusers_rows: str) -> None:
        lines = ["# commissioned worker hardening"]
        lines.extend(allowusers_rows)
        self.hardening.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_effective_allowusers_accumulates_every_sshd_row(self):
        self._write_hardening("AllowUsers admin", "AllowUsers deployer")
        result = self._run_machinery("effective_allowusers")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "admin deployer")
        contained = self._run_machinery("allowusers_contains admin")
        self.assertEqual(contained.returncode, 0, contained.stderr)
        missing = self._run_machinery("allowusers_contains intruder")
        self.assertEqual(missing.returncode, 1)

    def test_add_preserves_existing_principals_and_appends_deploy_user(self):
        self._write_hardening("AllowUsers admin")
        result = self._run_machinery("set_allowusers_membership add")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.hardening.read_text(encoding="utf-8"),
            "# commissioned worker hardening\nAllowUsers admin sea-speed-deploy\n",
        )

    def test_add_is_idempotent_when_principal_already_listed(self):
        self._write_hardening("AllowUsers admin sea-speed-deploy")
        before = self.hardening.read_bytes()
        result = self._run_machinery("set_allowusers_membership add")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.hardening.read_bytes(), before)

    def test_remove_drops_only_the_deploy_principal(self):
        self._write_hardening("AllowUsers admin sea-speed-deploy")
        result = self._run_machinery("set_allowusers_membership remove")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.hardening.read_text(encoding="utf-8"),
            "# commissioned worker hardening\nAllowUsers admin\n",
        )

    def test_remove_refuses_to_drop_the_last_principal(self):
        self._write_hardening("AllowUsers sea-speed-deploy")
        before = self.hardening.read_bytes()
        result = self._run_machinery("set_allowusers_membership remove")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn("refusing to remove the last AllowUsers principal", result.stderr)
        self.assertEqual(self.hardening.read_bytes(), before)

    def test_add_fails_closed_when_effective_policy_diverges(self):
        # changed=false path: the principal is already in the file but the
        # EFFECTIVE policy (what sshd actually serves) lacks it.
        self._write_hardening("AllowUsers admin sea-speed-deploy")
        effective = self.tmp / "effective.conf"
        effective.write_text("allowusers admin\n", encoding="utf-8")
        result = self._run_machinery(
            "set_allowusers_membership add",
            {"SSHD_EFFECTIVE_FILE": str(effective)},
        )
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn("deploy principal missing from effective AllowUsers", result.stderr)

    def test_invalid_sshd_config_rolls_back_the_allowlist_update(self):
        self._write_hardening("AllowUsers admin")
        before = self.hardening.read_bytes()
        result = self._run_machinery("set_allowusers_membership add", {"SSHD_T_RC": "1"})
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn("original config restored", result.stderr)
        self.assertEqual(self.hardening.read_bytes(), before)

    def test_failed_reload_rolls_back_the_allowlist_update(self):
        self._write_hardening("AllowUsers admin")
        before = self.hardening.read_bytes()
        self.systemctl_calls.unlink(missing_ok=True)
        result = self._run_machinery("set_allowusers_membership add", {"SYSTEMCTL_RC": "1"})
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn("original config restored", result.stderr)
        self.assertEqual(self.hardening.read_bytes(), before)
        # reload_sshd prefers the canonical unit and falls back to sshd; the
        # failed update reload AND the rollback's restore_sshd_hardening each
        # run that pair, so the real script records the sequence twice.
        calls = self.systemctl_calls.read_text(encoding="utf-8").splitlines()
        self.assertEqual(calls, ["reload ssh", "reload sshd", "reload ssh", "reload sshd"])

    def test_missing_existing_principal_after_reload_rolls_back(self):
        # Executed twin (issue #398 wave 5 peer-review fix): after a SUCCESSFUL
        # reload, the real script re-verifies EVERY new_users principal against
        # the effective policy — a missing pre-existing principal restores the
        # original hardening file and fails closed with rc 7. The effective
        # override serves the post-reload policy (lowercase keyword, as real
        # sshd -T emits) containing the deploy user but lacking admin; the
        # initial effective read at the top of set_allowusers_membership sees
        # the same file and does not divert the flow (the hardening file exists
        # with exactly one AllowUsers line, so the update path proceeds).
        self._write_hardening("AllowUsers admin")
        before = self.hardening.read_bytes()
        effective = self.tmp / "effective.conf"
        effective.write_text("allowusers sea-speed-deploy\n", encoding="utf-8")
        result = self._run_machinery(
            "set_allowusers_membership add",
            {"SSHD_EFFECTIVE_FILE": str(effective)},
        )
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn("existing AllowUsers principal missing after reload: admin", result.stderr)
        self.assertEqual(self.hardening.read_bytes(), before)


class BootstrapPasswordBoundaryExecutedTests(unittest.TestCase):
    """The '*NP*' password boundary write/read-back/verify chain, executed."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="398-w5-password."))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.stub_dir = self.tmp / "stubs"
        self.stub_dir.mkdir()
        self.shadow = self.tmp / "shadow"
        self.usermod_calls = self.tmp / "usermod_calls.txt"
        _write_executable(
            self.stub_dir / "usermod",
            USERMOD_STUB.replace("$USERMOD_CALLS", str(self.usermod_calls)),
        )
        _write_executable(
            self.stub_dir / "getent",
            GETENT_STUB.replace("$SHADOW_FILE", str(self.shadow)),
        )
        source = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        block = source[source.index('usermod --password'):source.index('install -d -o "$DEPLOY_USER"')]
        self.script = self.tmp / "password_boundary.sh"
        self.script.write_text(
            "set -euo pipefail\n"
            'readonly DEPLOY_USER="sea-speed-deploy"\n'
            + block,
            encoding="utf-8",
        )

    def _run(self) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "PATH": f"{self.stub_dir}:{os.environ['PATH']}",
            "SHADOW_FILE": str(self.shadow),
        }
        return subprocess.run(
            ["bash", str(self.script)], capture_output=True, text=True, env=env,
        )

    def test_non_locking_password_marker_round_trips_through_shadow(self):
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            ["--password", "*NP*", "sea-speed-deploy"],
            [self.usermod_calls.read_text(encoding="utf-8").split()],
        )
        self.assertIn("*NP*", self.shadow.read_text(encoding="utf-8"))

    def test_locked_shadow_field_fails_closed(self):
        # A leading '!' locks the account at sshd's account-access gate —
        # exactly the regression the read-back verify exists to catch. The
        # override simulates usermod laying down a locked field.
        result_env = {"USERMOD_PASSWORD_OVERRIDE": "!"}
        env = {
            **os.environ,
            "PATH": f"{self.stub_dir}:{os.environ['PATH']}",
            "SHADOW_FILE": str(self.shadow),
            **result_env,
        }
        result = subprocess.run(
            ["bash", str(self.script)], capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 6, result.stderr)
        self.assertIn("deploy account password-auth boundary mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
