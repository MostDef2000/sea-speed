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
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
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

    def test_two_phase_hash_locked_install_replaces_direct_index_install(self) -> None:
        self.assertIn("-m pip download", self.source)
        self.assertGreaterEqual(self.source.count("--require-hashes"), 2)
        self.assertIn("--only-binary=:all:", self.source)
        self.assertIn("--no-index", self.source)
        self.assertIn('--find-links "$wheelhouse_dir"', self.source)
        self.assertIn('-r "$lock_file_path"', self.source)
        self.assertIn("grep -v '^--' \"$lock_file_path\"", self.source)
        self.assertNotIn('pip install -r "$requirements_path"', self.source)
        download = self.source.index("-m pip download")
        install = self.source.index("-m pip install")
        self.assertLess(download, install)

    def test_fail_closed_validation_precedes_any_mutation(self) -> None:
        self.assertIn("if ! validate_runtime_lock; then", self.source)
        self.assertIn("ERROR runtime lock inputs are invalid", self.source)
        self.assertIn("ERROR runtime lock graph is empty", self.source)
        self.assertIn("PASS runtime_lock_validated", self.source)
        validation = self.source.index("if ! validate_runtime_lock; then")
        root_check = self.source.index('if [[ "$EUID" -ne 0 ]]; then')
        venv_creation = self.source.index("python3 -m venv")
        self.assertLess(validation, root_check)
        self.assertLess(validation, venv_creation)

    def test_runtime_id_v2_payload_covers_all_three_definition_files(self) -> None:
        self.assertIn('lock_file_path="$script_dir/requirements-runtime.lock.txt"', self.source)
        self.assertIn("lock_path.read_bytes()", self.source)
        self.assertIn("requirements_path.read_bytes()", self.source)
        self.assertIn("lock_file_path.read_bytes()", self.source)

    def test_manifest_records_lock_hash_and_finalizes_lock_file(self) -> None:
        self.assertIn('"requirements_lock_sha256"', self.source)
        self.assertIn("runtime manifest requirements_lock_sha256 mismatch", self.source)
        self.assertIn("runtime manifest graph drift", self.source)
        self.assertIn('cp "$lock_file_path" "$staged_root/requirements-runtime.lock.txt"', self.source)
        self.assertIn("chmod 0444", self.source)
        self.assertIn("$staged_root/requirements-runtime.lock.txt", self.source)

    def test_verify_ready_runtime_extends_to_lock_file_and_manifest(self) -> None:
        self.assertIn('[[ -f "$runtime_root/requirements-runtime.lock.txt" ]]', self.source)
        self.assertIn(
            'cmp -s "$lock_file_path" "$runtime_root/requirements-runtime.lock.txt"',
            self.source,
        )
        self.assertIn(
            'verify_python "$runtime_root/venv/bin/python" "$runtime_root/runtime-manifest.json"',
            self.source,
        )

    def test_runtime_lock_json_schema_2_carries_provenance(self) -> None:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        self.assertEqual(lock["schema_version"], 2)
        self.assertEqual(
            lock["resolved_lock"],
            {"file": "requirements-runtime.lock.txt", "sha256": ""},
        )
        self.assertEqual(lock["pytorch"]["index_provenance"], "official PyTorch cu130 index")
        self.assertEqual(lock["pytorch"]["pypi_index_url"], "https://pypi.org/simple")
        self.assertEqual(sorted(lock["pytorch"]["artifact_sha256"]), ["torch", "torchvision"])
        for artifact in lock["pytorch"]["artifact_sha256"].values():
            self.assertEqual(artifact, "")  # CI resolution lands in commit 2

    def test_placeholder_lock_carries_schema_marker_but_no_pins(self) -> None:
        lines = [line.strip() for line in LOCK_FILE.read_text(encoding="utf-8").splitlines()]
        self.assertIn("# sea-speed-runtime-lock-v1", lines)
        content = [line for line in lines if line and not line.startswith("#")]
        self.assertEqual(content, [])  # placeholder: no resolved pins yet

    def test_resolver_workflow_is_dispatch_only_without_deploy_logic(self) -> None:
        import yaml

        workflow_path = ROOT / ".github/workflows/resolve-runtime-lock.yml"
        text = workflow_path.read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
        triggers = doc.get(True) or doc.get("on") or {}
        self.assertEqual(list(triggers), ["workflow_dispatch"])
        self.assertEqual(doc["permissions"], {"contents": "read"})
        self.assertEqual(list(doc["jobs"]), ["resolve"])
        self.assertIn("--generate-hashes", text)
        self.assertIn("uv pip compile", text)
        self.assertIn("actions/upload-artifact", text)
        self.assertNotIn("secrets:", text)
        self.assertNotIn("deploy-authorized", text)


if __name__ == "__main__":
    unittest.main()
