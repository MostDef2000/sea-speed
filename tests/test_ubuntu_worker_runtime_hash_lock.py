"""Runtime hash-lock tests for the shared Ubuntu worker runtime (#392).

Three kinds of coverage live here:

- PipHashMechanicsTests are EXECUTED environment tests: real pip against
  locally built fixture wheels with no network access. They prove the
  ``--require-hashes`` download/install mechanics prepare-runtime.sh relies on
  and therefore stay green against the base script — that is correct and
  expected; the script-level RED anchors live in the classes below.
- RuntimeIdAndLockTests are EXECUTED against the script selected by the
  module-wide SEA_SPEED_392_PREPARE_RUNTIME_PATH override (same pattern as
  #412/#395): runtime_id v2 derivation, byte-flip drift, the fail-closed
  placeholder-lock abort, and the two schema-2 cross-check negative paths
  (resolved_lock.sha256 mismatch, pytorch artifact_sha256 drift). Those
  script-behaviour tests fail RED against the base script, while the
  complete-lock root-gate guard in the same class stays green on base by
  design (the base script also stops at the root gate).
- StructuralPinsTests pin the two-phase install, the fail-closed markers, the
  manifest lock-hash/graph checks and the dispatch-only resolver workflow.
  The script-level pins fail RED against the base script; the lock/workflow
  pins read repository files and stay green on base by design.

Issue #398 wave 5 conversion: the remaining raw source-text pins on the
script now have executed twins against the REAL extracted functions —
``finalize_runtime`` (verify -> copy -> write_manifest -> ready -> 0444
finalize -> atomic mv) runs end-to-end in a tmp fixture with a stub
``chown`` (root-only op) and a wrapper venv python, and the manifest it
writes is re-verified and tampered to prove both fail-closed drift messages;
``verify_ready_runtime`` runs healthy (rc 0) and against a tampered/missing
staged lock copy (rc 1); the unpinned-lock-line abort executes the real
wrapper marker ("ERROR runtime lock inputs are invalid"); the directive-strip
``grep -v '^--'`` line is executed against a fixture lock file. The resolver
workflow bans are parsed-structure scans (``iter_strings``), comment-blind.
The two-phase pip flag sets, the guard ordering and the absence bans stay as
whitespace-normalized structural keeps (bash has no AST; wave-2 canon).
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "deploy/worker/ubuntu/prepare-runtime.sh"
LOCK = ROOT / "deploy/worker/ubuntu/runtime-lock.json"
REQUIREMENTS = ROOT / "deploy/worker/ubuntu/requirements-runtime.txt"
LOCK_FILE = ROOT / "deploy/worker/ubuntu/requirements-runtime.lock.txt"
PREPARE_OVERRIDE_ENV = "SEA_SPEED_392_PREPARE_RUNTIME_PATH"


def prepare_script() -> Path:
    return Path(os.environ.get(PREPARE_OVERRIDE_ENV, str(PREPARE)))


def build_wheel(dest: Path, name: str, version: str, summary: str) -> Path:
    """Build a minimal installable pure-python wheel zip (no network)."""
    dist = f"{name}-{version}.dist-info"
    wheel_path = dest / f"{name}-{version}-py3-none-any.whl"
    metadata = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\nSummary: {summary}\n"
    wheel_meta = "Wheel-Version: 1.0\nGenerator: test-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    record = f"{dist}/METADATA,,\n{dist}/WHEEL,,\n{dist}/RECORD,,\n"
    with zipfile.ZipFile(wheel_path, "w") as archive:
        archive.writestr(f"{dist}/METADATA", metadata)
        archive.writestr(f"{dist}/WHEEL", wheel_meta)
        archive.writestr(f"{dist}/RECORD", record)
    return wheel_path


def complete_lock_fixture() -> tuple[bytes, str]:
    """A valid schema-2 runtime-lock.json plus a hash-locked lock file."""
    lock_file_text = "\n".join(
        [
            "# sea-speed-runtime-lock-v1",
            "certifi==2026.1.1 \\",
            f"    --hash=sha256:{'a1' * 32} \\",
            f"    --hash=sha256:{'b2' * 32}",
            "    # via requests",
            "numpy==2.4.4 \\",
            f"    --hash=sha256:{'c3' * 32}",
            "    # via ultralytics",
            "requests==2.34.2 \\",
            f"    --hash=sha256:{'c9' * 32}",
            "    # via runtime requirements",
            "torch==2.13.0+cu130 \\",
            f"    --hash=sha256:{'d4' * 32}",
            "    # via pytorch cu130 closure",
            "torchvision==0.28.0+cu130 \\",
            f"    --hash=sha256:{'e5' * 32}",
            "    # via torch",
        ]
    ) + "\n"
    lock_file_bytes = lock_file_text.encode("utf-8")
    lock = {
        "schema_version": 2,
        "python": {"implementation": "CPython", "major": 3, "minor": 14},
        "pytorch": {
            "index_url": "https://download.pytorch.org/whl/cu130",
            "index_provenance": "official PyTorch cu130 index",
            "pypi_index_url": "https://pypi.org/simple",
            "packages": {"torch": "2.13.0+cu130", "torchvision": "0.28.0+cu130"},
            "artifact_sha256": {"torch": "d4" * 32, "torchvision": "e5" * 32},
        },
        "runtime_requirements": "requirements-runtime.txt",
        "resolved_lock": {"file": "requirements-runtime.lock.txt", "sha256": hashlib.sha256(lock_file_bytes).hexdigest()},
        "verification_imports": ["json"],
    }
    return lock_file_bytes, json.dumps(lock, indent=2) + "\n"


def canonical_package_name(name: str) -> str:
    """PEP 503-style normalization for fixture/lock name comparisons."""
    return name.strip().lower().replace("_", "-")


def lock_file_entries(lock_file_text: str) -> list[str]:
    """Join uv-style continuation lines into logical requirement entries."""
    joined: list[str] = []
    buffer = ""
    for raw in lock_file_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            buffer += line[:-1].strip() + " "
            continue
        joined.append((buffer + line).strip())
        buffer = ""
    return joined


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


def rmtree_force(path: Path) -> None:
    """shutil.rmtree that survives the 0444/0555 modes finalize_runtime bakes."""
    if not path.exists():
        return
    for root, dirs, files in os.walk(path, topdown=False):
        for name in dirs + files:
            target = Path(root) / name
            try:
                target.chmod(0o700 if target.is_dir() else 0o644)
            except OSError:
                pass
    try:
        path.chmod(0o700)
    except OSError:
        pass
    shutil.rmtree(path, ignore_errors=True)


def interpreter_visible_package() -> tuple[str, str]:
    """A name==version pin the harness interpreter resolves at runtime.

    Probed through ``python3`` (the interpreter the venv wrapper execs), not
    the test process, so the fixture pin and verify_python's
    importlib.metadata lookups always agree.
    """
    probe = (
        "from importlib.metadata import version\n"
        "import sys\n"
        "for name in sys.argv[1:]:\n"
        "    try:\n"
        "        print(name + '=' + version(name))\n"
        "        break\n"
        "    except Exception:\n"
        "        pass\n"
    )
    result = subprocess.run(
        ["python3", "-c", probe, "packaging", "setuptools", "pip", "pytest"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stdout.strip().splitlines()
    line = lines[0] if lines else ""
    if "=" not in line:
        raise unittest.SkipTest("no interpreter-installed package available for the fixture lock")
    name, _, pkg_version = line.partition("=")
    return name, pkg_version


def build_finalize_fixture(test: unittest.TestCase) -> tuple[Path, str, str, str]:
    """Fixture dir whose hash-locked graph pins an interpreter-installed package.

    Returns (fixture, package_name, package_version, runtime_id). The lock
    JSON carries the real interpreter identity so verify_python's ABI checks
    pass, and resolved_lock.sha256 matches the fixture lock file bytes.
    """
    fixture = Path(tempfile.mkdtemp(prefix="392-w5-executed."))
    test.addCleanup(rmtree_force, fixture)
    name, pkg_version = interpreter_visible_package()
    lock_file_text = (
        "# sea-speed-runtime-lock-v1\n"
        f"{name}=={pkg_version} \\\n"
        f"    --hash=sha256:{'ab' * 32}\n"
    )
    lock_file_bytes = lock_file_text.encode("utf-8")
    requirements_bytes = f"{name}=={pkg_version}\n".encode("utf-8")
    lock = {
        "schema_version": 2,
        "python": {
            "implementation": platform.python_implementation(),
            "major": sys.version_info.major,
            "minor": sys.version_info.minor,
        },
        "resolved_lock": {
            "file": "requirements-runtime.lock.txt",
            "sha256": hashlib.sha256(lock_file_bytes).hexdigest(),
        },
        "verification_imports": ["json"],
    }
    lock_json_bytes = (json.dumps(lock, indent=2) + "\n").encode("utf-8")
    (fixture / "runtime-lock.json").write_bytes(lock_json_bytes)
    (fixture / "requirements-runtime.txt").write_bytes(requirements_bytes)
    (fixture / "requirements-runtime.lock.txt").write_bytes(lock_file_bytes)
    runtime_id = hashlib.sha256(
        lock_json_bytes + b"\0" + requirements_bytes + b"\0" + lock_file_bytes
    ).hexdigest()
    return fixture, name, pkg_version, runtime_id


def prepare_function_source(start_marker: str, end_marker: str) -> str:
    """Slice a function body verbatim out of the override-selected script."""
    source = prepare_script().read_text(encoding="utf-8")
    start = source.index(start_marker)
    end = source.index(end_marker, start + len(start_marker))
    return source[start:end]


def prepare_canon_block() -> str:
    """The shared PEP 503 canonicalization block, verbatim (set + export)."""
    source = prepare_script().read_text(encoding="utf-8")
    start = source.index("SEA_SPEED_PYPI_CANON_SRC=")
    marker = "export SEA_SPEED_PYPI_CANON_SRC"
    end = source.index(marker, start) + len(marker)
    return source[start:end]


def run_prepare_harness(
    test: unittest.TestCase,
    fixture: Path,
    runtime_id: str,
    tail: str,
    runtime_root: Path,
) -> subprocess.CompletedProcess[str]:
    """Execute real prepare-runtime.sh functions in a tmp harness.

    Injects the script's globals (runtime_id, lock_path, requirements_path,
    lock_file_path, runtime_root), stubs chown (a root-only op; the sandbox
    runs unprivileged), prepends a venv/bin/python wrapper that execs the
    real python3, and appends the requested tail call. Every function body
    is verbatim script source.
    """
    (fixture / "releases").mkdir(exist_ok=True)
    staged_root = fixture / "staging" / "runtime"
    venv_bin = staged_root / "venv" / "bin"
    venv_bin.mkdir(parents=True, exist_ok=True)
    wrapper = venv_bin / "python"
    wrapper.write_text("#!/bin/sh\nexec python3 \"$@\"\n", encoding="utf-8")
    wrapper.chmod(0o755)
    harness = fixture / "harness.sh"
    harness.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"runtime_id={shlex.quote(runtime_id)}\n"
        f"lock_path={shlex.quote(str(fixture / 'runtime-lock.json'))}\n"
        f"requirements_path={shlex.quote(str(fixture / 'requirements-runtime.txt'))}\n"
        f"lock_file_path={shlex.quote(str(fixture / 'requirements-runtime.lock.txt'))}\n"
        f"runtime_root={shlex.quote(str(runtime_root))}\n"
        "# chown is a root-only operation; the sandbox runs unprivileged, so\n"
        "# the executed twin stubs it exactly like the rebuild battery does.\n"
        "chown() { :; }\n"
        "# The sandbox overlayfs refuses rename() of a write-protected directory\n"
        "# (production ext4 only requires w+x on the parents). The shim grants the\n"
        "# minimal temporary owner-write bit, performs the REAL atomic rename, and\n"
        "# re-applies the production 0555 mode at the destination.\n"
        "mv() {\n"
        "  local src=\"$1\" dst=\"$2\"\n"
        "  if [[ -d \"$src\" && ! -w \"$src\" ]]; then\n"
        "    chmod u+w \"$src\"\n"
        "    command mv \"$src\" \"$dst\"\n"
        "    [[ -d \"$dst\" ]] && chmod 0555 \"$dst\"\n"
        "    return 0\n"
        "  fi\n"
        "  command mv \"$@\"\n"
        "}\n"
        + prepare_canon_block()
        + "\n"
        + prepare_function_source("verify_python() {", "write_manifest() {")
        + "\n"
        + prepare_function_source("write_manifest() {", "verify_ready_runtime() {")
        + "\n"
        + prepare_function_source("verify_ready_runtime() {", "# Rebuild diagnostics")
        + "\n"
        + prepare_function_source("finalize_runtime() {", "# A quarantined runtime")
        + "\n"
        + tail
        + "\n",
        encoding="utf-8",
    )
    harness.chmod(0o755)
    return subprocess.run(["bash", str(harness)], capture_output=True, text=True)


class PipHashMechanicsTests(unittest.TestCase):
    """Environment tests: pip --require-hashes mechanics over fixture wheels.

    No network access anywhere; wheels are built in-test. These prove the
    mechanics the script relies on and stay green on the base script.
    """

    def _pip(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "pip", *args],
            capture_output=True,
            text=True,
            env={**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
        )

    def test_download_require_hashes_verifies_artifact_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            findlinks = root / "findlinks"
            findlinks.mkdir()
            wheel = build_wheel(findlinks, "fixturepkg", "1.0", summary="good bytes")
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            fragment = root / "pins.txt"
            fragment.write_text(f"fixturepkg==1.0 --hash=sha256:{digest}\n", encoding="utf-8")
            dest = root / "wheelhouse"
            result = self._pip(
                "download",
                "--no-index",
                "--find-links", str(findlinks),
                "--require-hashes",
                "-r", str(fragment),
                "--dest", str(dest),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((dest / wheel.name).is_file())

    def test_download_require_hashes_aborts_on_corrupted_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            findlinks = root / "findlinks"
            findlinks.mkdir()
            wheel = build_wheel(findlinks, "fixturepkg", "1.0", summary="good bytes")
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            fragment = root / "pins.txt"
            fragment.write_text(f"fixturepkg==1.0 --hash=sha256:{digest}\n", encoding="utf-8")
            # Same artifact name/version, different bytes: the exact drift the
            # lock file exists to catch.
            build_wheel(findlinks, "fixturepkg", "1.0", summary="tampered bytes")
            result = self._pip(
                "download",
                "--no-index",
                "--find-links", str(findlinks),
                "--require-hashes",
                "-r", str(fragment),
                "--dest", str(root / "wheelhouse"),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("hash", (result.stderr + result.stdout).lower())

    def test_install_no_index_require_hashes_installs_from_verified_wheels(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            findlinks = root / "findlinks"
            findlinks.mkdir()
            wheel = build_wheel(findlinks, "fixturepkg", "1.0", summary="good bytes")
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            fragment = root / "pins.txt"
            fragment.write_text(f"fixturepkg==1.0 --hash=sha256:{digest}\n", encoding="utf-8")
            target = root / "target"
            result = self._pip(
                "install",
                "--no-index",
                "--find-links", str(findlinks),
                "--require-hashes",
                "-r", str(fragment),
                "--target", str(target),
                "--no-cache-dir",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((target / "fixturepkg-1.0.dist-info").is_dir())

    def test_install_require_hashes_fails_on_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            findlinks = root / "findlinks"
            findlinks.mkdir()
            build_wheel(findlinks, "fixturepkg", "1.0", summary="actual bytes")
            fragment = root / "pins.txt"
            fragment.write_text(f"fixturepkg==1.0 --hash=sha256:{'ab' * 32}\n", encoding="utf-8")
            result = self._pip(
                "install",
                "--no-index",
                "--find-links", str(findlinks),
                "--require-hashes",
                "-r", str(fragment),
                "--target", str(root / "target"),
                "--no-cache-dir",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("hash", (result.stderr + result.stdout).lower())


class RuntimeIdAndLockTests(unittest.TestCase):
    """EXECUTED against the override-selected script.

    The runtime-id v2, byte-flip, placeholder-fail-closed and schema-2
    cross-check tests are the RED anchors on base; the complete-lock
    root-gate guard stays green on base by design.
    """

    def _fixture_dir(self) -> tuple[Path, Path]:
        """Copy the script plus its three definition files into a fixture dir."""
        source = Path(os.environ.get(PREPARE_OVERRIDE_ENV, str(PREPARE)))
        fixture = Path(tempfile.mkdtemp(prefix="392-runtime-id."))
        self.addCleanup(shutil.rmtree, fixture, ignore_errors=True)
        script = fixture / "prepare-runtime.sh"
        shutil.copy(source, script)
        shutil.copy(LOCK, fixture / "runtime-lock.json")
        shutil.copy(REQUIREMENTS, fixture / "requirements-runtime.txt")
        shutil.copy(LOCK_FILE, fixture / "requirements-runtime.lock.txt")
        return fixture, script

    def _runtime_id(self, script: Path) -> str:
        result = subprocess.run(
            ["bash", str(script), "--runtime-id-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def test_runtime_id_v2_formula_is_deterministic(self) -> None:
        fixture, script = self._fixture_dir()
        expected = hashlib.sha256(
            (fixture / "runtime-lock.json").read_bytes()
            + b"\0"
            + (fixture / "requirements-runtime.txt").read_bytes()
            + b"\0"
            + (fixture / "requirements-runtime.lock.txt").read_bytes()
        ).hexdigest()
        actual = self._runtime_id(script)
        self.assertEqual(actual, expected)
        self.assertEqual(actual, self._runtime_id(script))

    def test_any_single_byte_change_moves_the_runtime_id(self) -> None:
        fixture, script = self._fixture_dir()
        baseline = self._runtime_id(script)
        for component in ("runtime-lock.json", "requirements-runtime.txt", "requirements-runtime.lock.txt"):
            target = fixture / component
            original = target.read_bytes()
            mutated = original.replace(b"#", b"%", 1)
            if mutated == original:
                mutated = original + b"\n# drift probe\n"
            try:
                target.write_bytes(mutated)
                self.assertNotEqual(self._runtime_id(script), baseline, component)
            finally:
                target.write_bytes(original)
        self.assertEqual(self._runtime_id(script), baseline)

    def test_placeholder_lock_fails_closed_before_any_mutation(self) -> None:
        fixture, script = self._fixture_dir()
        # The committed lock file now carries the resolved hash-locked graph
        # (commit 2), so the empty-graph placeholder behavior is exercised
        # through a fixture the test builds itself.
        (fixture / "requirements-runtime.lock.txt").write_text(
            "# sea-speed-runtime-lock-v1\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("ERROR runtime lock graph is empty", result.stderr)
        self.assertIn("refusing to prepare a runtime", result.stderr)
        self.assertNotIn("RUNTIME_CREATED", result.stdout)

    def test_complete_lock_passes_validation_until_the_root_gate(self) -> None:
        fixture, script = self._fixture_dir()
        lock_file_bytes, lock_json = complete_lock_fixture()
        (fixture / "requirements-runtime.lock.txt").write_bytes(lock_file_bytes)
        (fixture / "runtime-lock.json").write_text(lock_json, encoding="utf-8")
        (fixture / "requirements-runtime.txt").write_text(
            "# torch wheels come from the cu130 index.\nnumpy==2.4.4\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
        )
        # Not root in the sandbox: validation passed, the root gate is the
        # reason the run stops.
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ERROR run as root", result.stderr)
        self.assertNotIn("refusing to prepare a runtime", result.stderr)

    def test_resolved_lock_sha256_mismatch_fails_closed(self) -> None:
        fixture, script = self._fixture_dir()
        lock_file_bytes, lock_json = complete_lock_fixture()
        (fixture / "requirements-runtime.lock.txt").write_bytes(lock_file_bytes)
        lock = json.loads(lock_json)
        lock["resolved_lock"]["sha256"] = "f0" * 32  # valid format, wrong bytes
        (fixture / "runtime-lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
        (fixture / "requirements-runtime.txt").write_text(
            "# torch wheels come from the cu130 index.\nnumpy==2.4.4\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn(
            "ERROR runtime-lock.json resolved_lock.sha256 does not match the lock file bytes",
            result.stderr,
        )
        self.assertIn("refusing to prepare a runtime", result.stderr)
        self.assertNotIn("RUNTIME_CREATED", result.stdout)

    def test_pytorch_artifact_sha256_drift_fails_closed(self) -> None:
        fixture, script = self._fixture_dir()
        lock_file_bytes, lock_json = complete_lock_fixture()
        (fixture / "requirements-runtime.lock.txt").write_bytes(lock_file_bytes)
        lock = json.loads(lock_json)
        # Valid 64-hex format, but absent from the lock file's own --hash
        # lines for torch: exactly the provenance drift the cross-check exists
        # to catch.
        lock["pytorch"]["artifact_sha256"]["torch"] = "9f" * 32
        (fixture / "runtime-lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
        (fixture / "requirements-runtime.txt").write_text(
            "# torch wheels come from the cu130 index.\nnumpy==2.4.4\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn(
            "ERROR pytorch artifact sha256 drift against lock file: torch",
            result.stderr,
        )
        self.assertIn("refusing to prepare a runtime", result.stderr)
        self.assertNotIn("RUNTIME_CREATED", result.stdout)


class StructuralPinsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = prepare_script().read_text(encoding="utf-8")

    # Issue #398 wave 2: the two-phase install and validation-order contracts
    # are asserted against whitespace-normalized pip invocations / guard
    # positions instead of raw byte-exact lines, so reformatting or adding
    # unrelated flags cannot fail them.
    def _pip_command(self, subcommand: str) -> str:
        """Whitespace-normalized text of the `-m pip <subcommand>` invocation."""
        lines = self.source.splitlines()
        for index, line in enumerate(lines):
            if f"-m pip {subcommand}" not in line:
                continue
            joined = [line]
            while joined[-1].rstrip().endswith("\\") and index + len(joined) < len(lines):
                joined.append(lines[index + len(joined)])
            return " ".join(" ".join(joined).replace("\\", " ").split())
        self.fail(f"pip {subcommand} invocation not found in prepare-runtime.sh")

    def test_two_phase_hash_locked_install_replaces_direct_index_install(self) -> None:
        # Phase 1 downloads the hash-locked graph from the indexes (verified at
        # download time); phase 2 installs strictly offline from the verified
        # wheel set. Flag sets are asserted per invocation, not anywhere in the
        # file, and download must precede install (issue #398 wave 2).
        download = self._pip_command("download")
        install = self._pip_command("install")
        for flag in ("--require-hashes", "--only-binary=:all:", "-r", "$lock_file_path"):
            self.assertIn(flag, download)
        for flag in ("--no-index", "--find-links", "$wheelhouse_dir", "--require-hashes", "-r"):
            self.assertIn(flag, install)
        # The directive-strip line is asserted by the EXECUTED
        # DirectiveStripExecutedTests twin below (issue #398 wave 5), which
        # runs the real line against the committed lock file and a poisoned
        # fixture. The direct-requirements install ban and the download-
        # before-install order stay as structural keeps (wave 2 canon).
        self.assertNotIn('pip install -r "$requirements_path"', self.source)
        self.assertLess(
            self.source.index("-m pip download"),
            self.source.index("-m pip install"),
        )

    def test_fail_closed_validation_precedes_any_mutation(self) -> None:
        # The "ERROR runtime lock inputs are invalid" wrapper marker is asserted
        # by the EXECUTED LockValidationExecutedTests twin below (issue #398
        # wave 5), which runs the real script against an unpinned lock line.
        # The graph-empty marker is asserted by the executed
        # test_placeholder_lock_fails_closed_before_any_mutation, and
        # "PASS runtime_lock_validated" by the executed healthy-path battery in
        # test_ubuntu_worker_runtime_rebuild.py, so they are not re-pinned here.
        positions = [
            self._source_position(r"if\s+!\s*validate_runtime_lock\s*;\s*then"),
            self._source_position(r'if\s+\[\[\s*"\$EUID"\s+-ne 0\s*\]\];\s*then'),
            self._source_position(r"python3\s+-m\s+venv"),
        ]
        self.assertEqual(positions, sorted(positions))

    def _source_position(self, pattern: str) -> int:
        match = re.search(pattern, self.source)
        if match is None:
            self.fail(f"fail-closed guard anchor not found: {pattern}")
        return match.start()

    # test_runtime_id_v2_payload_covers_all_three_definition_files retired
    # (issue #398 wave 2): the runtime-id payload invariant is asserted
    # behaviorally by test_runtime_id_v2_formula_is_deterministic and
    # test_any_single_byte_change_moves_the_runtime_id, which execute the real
    # formula against every definition file.

    # test_manifest_records_lock_hash_and_finalizes_lock_file retired
    # (issue #398 wave 5): the manifest lock-hash contract and the read-only
    # finalize are asserted by the EXECUTED FinalizeRuntimeExecutedTests twins
    # below — the real finalize_runtime runs end-to-end (verify -> copy ->
    # write_manifest -> ready -> 0444 -> atomic mv) and the manifest it writes
    # is re-verified and tampered to prove both drift messages fail closed.

    # test_verify_ready_runtime_extends_to_lock_file_and_manifest retired
    # (issue #398 wave 5): the parity gates are asserted by the EXECUTED
    # VerifyReadyRuntimeExecutedTests twins below (healthy rc 0; tampered and
    # missing staged lock copies rc 1).

    def test_runtime_lock_json_schema_2_carries_provenance(self) -> None:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        self.assertEqual(lock["schema_version"], 2)
        self.assertEqual(
            lock["resolved_lock"],
            {
                "file": "requirements-runtime.lock.txt",
                "sha256": hashlib.sha256(LOCK_FILE.read_bytes()).hexdigest(),
            },
        )
        self.assertTrue(lock["pytorch"]["index_provenance"])
        self.assertTrue(lock["pytorch"]["pypi_index_url"])
        entries = lock_file_entries(LOCK_FILE.read_text(encoding="utf-8"))
        for package, artifact in sorted(lock["pytorch"]["artifact_sha256"].items()):
            self.assertRegex(artifact, r"^[0-9a-f]{64}$", package)
            package_entries = [
                entry
                for entry in entries
                if canonical_package_name(entry.partition("==")[0]) == canonical_package_name(package)
            ]
            self.assertTrue(package_entries, f"pytorch package absent from the lock: {package}")
            self.assertTrue(
                any(f"--hash=sha256:{artifact}" in entry for entry in package_entries),
                f"artifact digest absent from the lock hash lines: {package}",
            )

    def test_committed_lock_carries_marker_and_full_hash_pinned_graph(self) -> None:
        text = LOCK_FILE.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# sea-speed-runtime-lock-v1"))
        entries = lock_file_entries(text)
        # Every direct requirement from requirements-runtime.txt must appear
        # exactly once in the committed graph, exact version, hash-pinned.
        for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            name, _, version = line.partition("==")
            pin = f"{canonical_package_name(name)}=={version.strip()}"
            matches = [
                entry
                for entry in entries
                if canonical_package_name(entry.partition("==")[0]) == canonical_package_name(name)
            ]
            self.assertEqual(len(matches), 1, f"direct requirement not uniquely pinned: {line}")
            self.assertTrue(matches[0].startswith(pin), f"lock pin drift: {line}")
            self.assertIn("--hash=sha256:", matches[0], f"lock pin not hash-pinned: {line}")
        # The pytorch closure pins must be present with their cu130 wheels and
        # verified artifact hashes.
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        for package, version in sorted(lock["pytorch"]["packages"].items()):
            pin = f"{package}=={version}"
            matches = [entry for entry in entries if entry.startswith(pin)]
            self.assertEqual(len(matches), 1, f"pytorch pin not uniquely present: {pin}")
            self.assertIn("--hash=sha256:", matches[0], f"pytorch pin not hash-pinned: {pin}")

    def test_resolver_workflow_is_dispatch_only_without_deploy_logic(self) -> None:
        # Structured parse (issue #398 wave 2): trigger, permission and job
        # shapes come from yaml.safe_load instead of an indentation walk, so
        # reformatting or reordering inside the workflow cannot fail the pins.
        # YAML 1.1 parses the bare `on:` key as boolean True.
        workflow_path = ROOT / ".github/workflows/resolve-runtime-lock.yml"
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

        # workflow_dispatch is the ONLY trigger of the workflow.
        triggers = workflow.get(True, workflow.get("on", {}))
        self.assertEqual(list(triggers), ["workflow_dispatch"])
        # contents: read is the ONLY permission granted anywhere at the
        # top level (job-level permission blocks would not satisfy the
        # strict equality even if added).
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        # resolve is the ONLY job; the lock is compiled with uv pip compile
        # --generate-hashes and uploaded as an artifact.
        self.assertEqual(list(workflow["jobs"]), ["resolve"])
        steps = workflow["jobs"]["resolve"]["steps"]
        runs = [step.get("run", "") for step in steps]
        self.assertTrue(
            any("uv pip compile" in run and "--generate-hashes" in run for run in runs),
            "lock compilation step lost uv pip compile --generate-hashes",
        )
        self.assertTrue(
            any(step.get("uses", "").startswith("actions/upload-artifact@") for step in steps),
            "resolved lock artifact upload step missing",
        )
        # Parsed-structure bans (issue #398 wave 5): no secret plumbing and no
        # deploy transport anywhere in the PARSED workflow (keys and values),
        # so a violation in any executable position fails regardless of
        # formatting; comments are not parsed structure and stay out of scope.
        self.assertFalse(
            any("secrets" in text for text in iter_strings(workflow)),
            "resolver workflow carries secret plumbing in its parsed structure",
        )
        self.assertFalse(
            any("deploy-authorized" in text for text in iter_strings(workflow)),
            "resolver workflow transports deploy-authorized logic",
        )


class FinalizeRuntimeExecutedTests(unittest.TestCase):
    """EXECUTED finalize_runtime twin (issue #398 wave 5).

    The real finalize_runtime (verify -> copy -> write_manifest -> ready
    marker -> 0444 finalize -> atomic mv) runs end-to-end in a tmp harness
    against a fixture lock pinning an interpreter-installed package. The
    manifest it writes is re-verified by the real verify_python, then
    tampered to prove both fail-closed drift messages.
    """

    ORIGIN = "network-cache:/tmp/392-w5-wheelhouse"

    def _finalize(self) -> tuple[Path, Path, str, str, str]:
        fixture, name, pkg_version, runtime_id = build_finalize_fixture(self)
        result = run_prepare_harness(
            self,
            fixture,
            runtime_id,
            "finalize_runtime "
            + shlex.quote(str(fixture / "staging" / "runtime"))
            + " "
            + shlex.quote(self.ORIGIN),
            fixture / "releases" / "runtime",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return fixture, fixture / "releases" / "runtime", runtime_id, name, pkg_version

    def test_finalize_runtime_writes_a_verified_readonly_runtime(self) -> None:
        fixture, runtime_root, runtime_id, name, pkg_version = self._finalize()
        # Ready marker carries the runtime id passthrough.
        self.assertEqual(
            (runtime_root / "ready").read_text(encoding="utf-8"),
            f"runtime_id={runtime_id}\n",
        )
        # Manifest: runtime id + origin passthrough, lock-file hash baked from
        # the staged copy, installed graph baked from the real interpreter.
        manifest = json.loads((runtime_root / "runtime-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["runtime_id"], runtime_id)
        self.assertEqual(manifest["origin"], self.ORIGIN)
        self.assertEqual(
            manifest["requirements_lock_sha256"],
            hashlib.sha256((fixture / "requirements-runtime.lock.txt").read_bytes()).hexdigest(),
        )
        self.assertEqual(manifest["installed_packages"].get(name), pkg_version)
        # Read-only finalize: the five contract files 0444, the runtime dir 0555.
        for member in (
            "runtime-lock.json",
            "requirements-runtime.txt",
            "requirements-runtime.lock.txt",
            "runtime-manifest.json",
            "ready",
        ):
            self.assertEqual(os.stat(runtime_root / member).st_mode & 0o777, 0o444, member)
        self.assertEqual(os.stat(runtime_root).st_mode & 0o777, 0o555)
        # Staged copies are byte-identical to the definition files.
        for shared in ("runtime-lock.json", "requirements-runtime.txt", "requirements-runtime.lock.txt"):
            self.assertEqual(
                (fixture / shared).read_bytes(),
                (runtime_root / shared).read_bytes(),
                shared,
            )

    def test_finalized_manifest_reverifies_with_the_real_verify_python(self) -> None:
        fixture, runtime_root, runtime_id, _, _ = self._finalize()
        result = run_prepare_harness(
            self,
            fixture,
            runtime_id,
            'verify_python "$runtime_root/venv/bin/python" "$runtime_root/runtime-manifest.json"',
            runtime_root,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS shared_runtime_imports_and_versions", result.stdout)

    def test_manifest_lock_hash_drift_fails_closed(self) -> None:
        fixture, runtime_root, runtime_id, _, _ = self._finalize()
        manifest_path = runtime_root / "runtime-manifest.json"
        os.chmod(manifest_path, 0o644)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["requirements_lock_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = run_prepare_harness(
            self,
            fixture,
            runtime_id,
            'verify_python "$runtime_root/venv/bin/python" "$runtime_root/runtime-manifest.json"',
            runtime_root,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("runtime manifest requirements_lock_sha256 mismatch", result.stderr)

    def test_manifest_graph_drift_fails_closed(self) -> None:
        fixture, runtime_root, runtime_id, name, pkg_version = self._finalize()
        manifest_path = runtime_root / "runtime-manifest.json"
        os.chmod(manifest_path, 0o644)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["installed_packages"][name] = "9.9.9"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = run_prepare_harness(
            self,
            fixture,
            runtime_id,
            'verify_python "$runtime_root/venv/bin/python" "$runtime_root/runtime-manifest.json"',
            runtime_root,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            f"runtime manifest graph drift: {name} expected={pkg_version} actual=9.9.9",
            result.stderr,
        )


class VerifyReadyRuntimeExecutedTests(unittest.TestCase):
    """EXECUTED verify_ready_runtime twin (issue #398 wave 5).

    The real function runs against a runtime finalized by the real
    finalize_runtime: healthy accepts with rc 0; a tampered staged lock copy
    and a missing staged lock copy each fail closed with rc 1.
    """

    def _finalized_runtime(self) -> tuple[Path, Path, str]:
        fixture, _, _, runtime_id = build_finalize_fixture(self)
        result = run_prepare_harness(
            self,
            fixture,
            runtime_id,
            "finalize_runtime "
            + shlex.quote(str(fixture / "staging" / "runtime"))
            + " "
            + shlex.quote("network-cache:/tmp/392-w5-wheelhouse"),
            fixture / "releases" / "runtime",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return fixture, fixture / "releases" / "runtime", runtime_id

    def test_verify_ready_runtime_accepts_a_healthy_finalized_runtime(self) -> None:
        fixture, runtime_root, runtime_id = self._finalized_runtime()
        result = run_prepare_harness(self, fixture, runtime_id, "verify_ready_runtime", runtime_root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_verify_ready_runtime_rejects_a_tampered_staged_lock_copy(self) -> None:
        fixture, runtime_root, runtime_id = self._finalized_runtime()
        lock_copy = runtime_root / "requirements-runtime.lock.txt"
        os.chmod(lock_copy, 0o644)
        lock_copy.write_bytes(lock_copy.read_bytes() + b"# tampered after finalize\n")
        result = run_prepare_harness(self, fixture, runtime_id, "verify_ready_runtime", runtime_root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_verify_ready_runtime_rejects_a_missing_staged_lock_copy(self) -> None:
        fixture, runtime_root, runtime_id = self._finalized_runtime()
        os.chmod(runtime_root, 0o755)
        (runtime_root / "requirements-runtime.lock.txt").unlink()
        result = run_prepare_harness(self, fixture, runtime_id, "verify_ready_runtime", runtime_root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)


class LockValidationExecutedTests(unittest.TestCase):
    """EXECUTED twin for the fail-closed lock-validation abort (issue #398
    wave 5): the real script runs against an unpinned lock line and must
    refuse with the wrapper marker before any mutation."""

    def test_unpinned_lock_line_aborts_before_any_mutation(self) -> None:
        fixture = Path(tempfile.mkdtemp(prefix="392-w5-lockval."))
        self.addCleanup(shutil.rmtree, fixture, ignore_errors=True)
        shutil.copy(prepare_script(), fixture / "prepare-runtime.sh")
        shutil.copy(LOCK, fixture / "runtime-lock.json")
        (fixture / "requirements-runtime.txt").write_text("numpy==2.4.4\n", encoding="utf-8")
        (fixture / "requirements-runtime.lock.txt").write_text(
            "# sea-speed-runtime-lock-v1\nnumpy==2.4.4\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["bash", str(fixture / "prepare-runtime.sh")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn(
            "ERROR runtime lock line is not sha256-hash-pinned: numpy==2.4.4",
            result.stderr,
        )
        self.assertIn("ERROR runtime lock inputs are invalid", result.stderr)
        self.assertIn("refusing to prepare a runtime", result.stderr)
        self.assertNotIn("RUNTIME_CREATED", result.stdout)


class DirectiveStripExecutedTests(unittest.TestCase):
    """EXECUTED twin for the directive-strip line (issue #398 wave 5).

    The real ``grep -v '^--' "$lock_file_path" > ...`` line is extracted from
    the override-selected script and executed: against the committed lock
    file (requirement entries survive) and against a poisoned fixture (a
    top-level --index-url directive must not survive).
    """

    def _strip_line(self) -> str:
        matches = [
            line.strip()
            for line in prepare_script().read_text(encoding="utf-8").splitlines()
            if "grep -v" in line and "'^--'" in line
        ]
        self.assertEqual(len(matches), 1, "directive-strip line not uniquely present in the script")
        return matches[0]

    def _run_strip(self, lock_source: Path, staged_root: Path) -> None:
        subprocess.run(
            [
                "bash",
                "-c",
                f"lock_file_path={shlex.quote(str(lock_source))}\n"
                f"staged_root={shlex.quote(str(staged_root))}\n"
                f"{self._strip_line()}\n",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_directive_strip_keeps_requirements_and_drops_directives(self) -> None:
        staged_root = Path(tempfile.mkdtemp(prefix="392-w5-strip."))
        self.addCleanup(shutil.rmtree, staged_root, ignore_errors=True)
        output = staged_root / "requirements-runtime.resolved.lock.txt"

        # Committed lock file: every requirement entry survives the strip.
        self._run_strip(LOCK, staged_root)
        stripped = output.read_text(encoding="utf-8")
        for line in stripped.splitlines():
            self.assertFalse(line.startswith("--"), f"directive survived the strip: {line}")
        for entry in lock_file_entries(LOCK.read_text(encoding="utf-8")):
            if entry.startswith("-"):
                continue
            self.assertIn(entry, lock_file_entries(stripped), f"requirement entry lost: {entry}")

        # Poisoned fixture: a top-level index directive must not survive.
        poisoned = staged_root / "poisoned.lock.txt"
        poisoned.write_text(
            "# sea-speed-runtime-lock-v1\n--index-url https://reindex.example/simple\n"
            + LOCK.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self._run_strip(poisoned, staged_root)
        stripped = output.read_text(encoding="utf-8")
        self.assertNotIn("reindex.example", stripped)
        for line in stripped.splitlines():
            self.assertFalse(line.startswith("--"), f"directive survived the strip: {line}")
        for entry in lock_file_entries(LOCK.read_text(encoding="utf-8")):
            if entry.startswith("-"):
                continue
            self.assertIn(entry, lock_file_entries(stripped), f"requirement entry lost: {entry}")


if __name__ == "__main__":
    unittest.main()
