"""Executed rebuild-path harness for prepare-runtime.sh (issue #426).

Covers the #406 autonomous-deploy failure class: an on-box EXISTING shared
runtime dir that no longer passes verify_ready_runtime (e.g. an apt python
upgrade invalidating the recorded runtime-manifest) previously aborted the
whole deploy transaction closed (exit 12 -> updater_failed ->
DEPLOY_CONFIG_ROLLED_BACK) with no which-check evidence and no convergence
path short of manual on-box steps. Since #426 the failure branch quarantines
the dir (evidence preserved, never deleted), records WHICH sub-check failed,
and deterministically rebuilds through the existing fresh staging + atomic
install path.

The harness executes the REAL script end-to-end in a sandbox (uid != 0, no
network, no real pip, no systemd):

- The script copy under test is byte-identical to the selected source except
  ONE documented sandbox adaptation: the EUID root gate becomes conditional
  on SEA_SPEED_426_ALLOW_NON_ROOT so the unprivileged sandbox can reach the
  runtime logic. The repo script keeps the unconditional root gate — that is
  pinned structurally below (test_root_gate_is_unconditional_in_repo_script).
- The three runtime definition files are fixture-built around one package
  that is actually installed in the test interpreter, so verify_python's
  implementation/ABI/version/manifest checks are REAL executed checks.
- PATH stubs: python3 (a fake ``python3 -m venv`` that lays down a wrapper
  venv/bin/python dispatching ``-m pip`` to a stub pip and exec'ing the real
  interpreter for every other invocation), pip (records download/install,
  optional fail knob), chown (root-only operation, recorded no-op). Real
  coreutils everywhere else (mktemp, cp, mv, cmp, chmod, rmdir, sed, grep,
  sort, find), so the quarantine rename and the finalize mv are the real
  atomic same-filesystem renames.
- SEA_SPEED_426_PREPARE_RUNTIME_PATH selects the script under test (same
  override pattern as SEA_SPEED_392/406/412) for RED-vs-base runs.

Issue #514 extends this harness: the manifest write path baked keys from the
lowercased dist metadata ``Name`` (``typing_extensions``) while the verify
path looked them up by the lock pin spelling (``typing-extensions``), so the
manifest lookup missed with ``actual=None`` and every deploy rebuilt the
immutable 0444 runtime. The tests below reproduce that exact shape
against an interpreter-installed non-canonical dist.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "deploy/worker/ubuntu/prepare-runtime.sh"
PREPARE_OVERRIDE_ENV = "SEA_SPEED_426_PREPARE_RUNTIME_PATH"
BASH = shutil.which("bash") or "/bin/bash"
ROOT_GATE = 'if [[ "$EUID" -ne 0 ]]; then'


def prepare_script() -> Path:
    return Path(os.environ.get(PREPARE_OVERRIDE_ENV, str(PREPARE)))


def fixture_package() -> tuple[str, str]:
    """An (name, version) pair actually installed in the test interpreter."""
    for candidate in ("pip", "packaging", "setuptools", "pytest"):
        try:
            return candidate, importlib.metadata.version(candidate)
        except importlib.metadata.PackageNotFoundError:
            continue
    for dist in importlib.metadata.distributions():
        name = (dist.metadata.get("Name") or "").strip()
        if name:
            return name.lower(), dist.version
    raise RuntimeError("no installed distribution available for the fixture lock")


_SYNTHETIC_DIST_PARENT: Path | None = None


def _synthesize_noncanonical_dist() -> tuple[str, str, str]:
    """Deterministically build the #514 incident shape.

    A CI runner may have NO installed distribution with a non-canonical
    metadata Name (pip/setuptools/pytest are all canonical), so the fixture
    cannot depend on the interpreter's installed set. A minimal
    ``typing_extensions-4.16.0.dist-info`` tree is created in a temp dir and
    the parent dir is exposed via :func:`canonicalization_dist_path` so the
    executed tests can put it on the subprocess PYTHONPATH —
    importlib.metadata discovers it there exactly like a real install.
    """
    global _SYNTHETIC_DIST_PARENT
    name, version = "typing_extensions", "4.16.0"
    if _SYNTHETIC_DIST_PARENT is None:
        _SYNTHETIC_DIST_PARENT = Path(tempfile.mkdtemp(prefix="sea-speed-514-dist"))
        dist_info = _SYNTHETIC_DIST_PARENT / f"{name}-{version}.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(
            "Metadata-Version: 2.1\n"
            f"Name: {name}\n"
            f"Version: {version}\n"
            "Summary: synthetic fixture dist for the #514 canonicalization tests\n",
            encoding="utf-8",
        )
        (dist_info / "top_level.txt").write_text(f"{name}\n", encoding="utf-8")
    return name, "typing-extensions", version


def canonicalization_dist_path() -> Path | None:
    """Parent dir of the synthetic non-canonical dist, when one was
    synthesized (None when a natural installed dist satisfied the fixture)."""
    return _SYNTHETIC_DIST_PARENT


def fixture_canonicalization_package() -> tuple[str, str, str]:
    """(metadata Name, canonical name, version) of an installed dist whose
    metadata Name is not PEP 503-canonical.

    Prefers ``typing_extensions`` so the fixture reproduces the #514 incident
    exactly (lock pin ``typing-extensions`` vs manifest key
    ``typing_extensions``). When no natural candidate is installed (bare CI
    runners), the incident shape is synthesized deterministically instead of
    erroring — the behavioral assertions are identical either way.
    """
    fallback: tuple[str, str, str] | None = None
    for dist in importlib.metadata.distributions():
        name = (dist.metadata.get("Name") or "").strip()
        if not name:
            continue
        canonical = re.sub(r"[-_.]+", "-", name).lower()
        if canonical == name.lower():
            continue
        if name.lower() == "typing_extensions":
            return name, canonical, dist.version
        if fallback is None:
            fallback = (name, canonical, dist.version)
    if fallback is not None:
        return fallback
    return _synthesize_noncanonical_dist()


def write_definition_files(work: Path) -> str:
    """Fixture runtime definition files; returns the derived runtime_id."""
    package, version = fixture_package()
    return write_definition_files_pinned(work, package, version)


def write_definition_files_pinned(work: Path, package: str, version: str) -> str:
    """Fixture runtime definition files pinned to an explicit name/version."""
    lock_file_bytes = (
        "# sea-speed-runtime-lock-v1\n"
        f"{package}=={version} --hash=sha256:{'a5' * 32}\n"
    ).encode("utf-8")
    (work / "requirements-runtime.lock.txt").write_bytes(lock_file_bytes)
    requirements_bytes = f"{package}=={version}\n".encode("utf-8")
    (work / "requirements-runtime.txt").write_bytes(requirements_bytes)
    lock = {
        "schema_version": 2,
        "python": {
            "implementation": platform.python_implementation(),
            "major": sys.version_info.major,
            "minor": sys.version_info.minor,
        },
        "pytorch": {
            "index_url": "https://fixture.invalid/whl",
            "index_provenance": "fixture sandbox index",
            "pypi_index_url": "https://fixture.invalid/simple",
            "packages": {},
            "artifact_sha256": {},
        },
        "runtime_requirements": "requirements-runtime.txt",
        "resolved_lock": {
            "file": "requirements-runtime.lock.txt",
            "sha256": hashlib.sha256(lock_file_bytes).hexdigest(),
        },
        "verification_imports": ["json"],
    }
    lock_bytes = (json.dumps(lock, indent=2) + "\n").encode("utf-8")
    (work / "runtime-lock.json").write_bytes(lock_bytes)
    runtime_id = hashlib.sha256(
        lock_bytes + b"\0" + requirements_bytes + b"\0" + lock_file_bytes
    ).hexdigest()
    return runtime_id


CHOWN_STUB = r"""#!/usr/bin/env bash
# Root-only operation: the sandbox runs unprivileged, so chown is a recorded
# no-op (the real finalize_runtime call site stays pinned structurally).
printf '%s\n' "chown $*" >> "${CHOWN_LOG:?}"
exit 0
"""

PIP_STUB = r"""#!/usr/bin/env bash
# Stand-in for the real pip module: records the phase and fails the install
# phase when PIP_INSTALL_FAIL is set (simulated staging failure, scenario b).
mode="other"
for arg in "$@"; do
  case "$arg" in
    download) mode="download" ;;
    install) mode="install" ;;
  esac
done
printf '%s\n' "pip $mode" >> "${PIP_STUB_LOG:?}"
if [[ "$mode" == "install" && -n "${PIP_INSTALL_FAIL:-}" ]]; then
  echo "pip: simulated install failure" >&2
  exit 1
fi
exit 0
"""

PY3_STUB = r"""#!/usr/bin/env bash
# python3 stand-in: only `python3 -m venv` is faked (a wrapper venv python
# that dispatches `-m pip` to the pip stub and execs the real interpreter for
# everything else, so verify_python/write_manifest run REAL python checks);
# every other invocation execs the real interpreter unchanged.
if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
  venv_dir="${3:?}"
  mkdir -p "$venv_dir/bin"
  cat > "$venv_dir/bin/python" <<'WRAPPER'
#!/usr/bin/env bash
if [[ "${1:-}" == "-m" && "${2:-}" == "pip" ]]; then
  shift 2
  exec __PIP_STUB__ "$@"
fi
exec __REAL_PYTHON__ "$@"
WRAPPER
  chmod 0755 "$venv_dir/bin/python"
  exit 0
fi
exec __REAL_PYTHON__ "$@"
"""


class PrepareRuntimeRebuildContractTests(unittest.TestCase):
    """Structural pins for the #426 rebuild wiring in the repo script."""

    def setUp(self) -> None:
        self.source = prepare_script().read_text(encoding="utf-8")

    def test_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(prepare_script())], check=True)

    def test_root_gate_is_unconditional_in_repo_script(self) -> None:
        # The executed harness relaxes the EUID gate only in its transformed
        # copy; the repo script must keep the unconditional fail-closed gate.
        self.assertIn(ROOT_GATE, self.source)

    def test_verify_ready_runtime_is_unchanged(self) -> None:
        # The healthy reuse path keeps the exact same ordered checks.
        for marker in (
            '[[ -f "$runtime_root/ready" ]] || return 1',
            '[[ -x "$runtime_root/venv/bin/python" ]] || return 1',
            '[[ -f "$runtime_root/runtime-manifest.json" ]] || return 1',
            '[[ "$(cat "$runtime_root/ready")" == "runtime_id=$runtime_id" ]] || return 1',
            'cmp -s "$lock_path" "$runtime_root/runtime-lock.json" || return 1',
            'cmp -s "$requirements_path" "$runtime_root/requirements-runtime.txt" || return 1',
            'cmp -s "$lock_file_path" "$runtime_root/requirements-runtime.lock.txt" || return 1',
            'verify_python "$runtime_root/venv/bin/python" "$runtime_root/runtime-manifest.json" >/dev/null',
        ):
            self.assertIn(marker, self.source)

    # test_rebuild_evidence_markers_present and
    # test_classify_mirrors_verify_ready_runtime_check_order retired (issue
    # #398 wave 2): their invariants are asserted behaviorally by the executed
    # class — rebuild/quarantine/fail-closed evidence markers on real runs
    # (scenarios (a)/(b)) and the full 11-sub-check classify matrix with
    # check=<name> evidence (test_failing_check_evidence_names_each_sub_check),
    # which proves order and naming for every verify_ready_runtime sub-check.

    def test_quarantine_preserves_evidence_and_never_deletes(self) -> None:
        # STATIC_POLICY: the transaction never deletes the failing runtime —
        # ANY rm of the runtime root is a violation, so the absence pins stay
        # textual. Quarantine preservation is asserted behaviorally by the
        # executed scenarios (a) (quarantine dir + prior bytes intact) and (b)
        # (staging failure keeps the quarantine as evidence), so the
        # mktemp/rmdir/mv mechanism order is not re-pinned here.
        self.assertNotIn('rm -rf "$runtime_root"', self.source)
        self.assertNotIn('rm -r "$runtime_root"', self.source)

    def test_rebuild_skips_legacy_adoption_and_runs_fresh_staging(self) -> None:
        guard = self.source.index('if [[ -z "$rebuild_reason" ]]; then')
        adopted = self.source.index("RUNTIME_ADOPTED runtime_id=")
        fallback_blocked = self.source.index("RUNTIME_NETWORK_FALLBACK_BLOCKED")
        rebuilt = self.source.index("RUNTIME_REBUILT runtime_id=")
        self.assertLess(guard, adopted)
        self.assertLess(guard, fallback_blocked)
        # The rebuild emission happens after finalize (fresh staging path).
        finalize = self.source.index('finalize_runtime "$staged_root" "network-cache:$wheel_cache"')
        self.assertLess(finalize, rebuilt)
        rebuilt_close = self.source.rindex("fi\nprintf 'RUNTIME_ID %s\\n' \"$runtime_id\"")
        self.assertLess(rebuilt, rebuilt_close)

    # test_healthy_path_emissions_are_unchanged retired (issue #398 wave 2):
    # executed twins assert the same healthy-path emissions on real runs —
    # scenario (c) pins the exact stdout including RUNTIME_REUSED, and the
    # issue-514 rebaked test asserts RUNTIME_CREATED on the fresh-install path.

    def test_manifest_names_share_one_pypi_canonicalization(self) -> None:
        # Issue #514 structural pin: exactly ONE textual PEP 503 definition,
        # injected into BOTH the manifest write path and the manifest verify
        # path, so the two normalizations cannot drift apart again.
        self.assertEqual(self.source.count("def _pypi_canon("), 1)
        self.assertIn('re.sub(r"[-_.]+", "-", name).lower()', self.source)
        self.assertEqual(
            self.source.count('exec(os.environ["SEA_SPEED_PYPI_CANON_SRC"])'),
            2,
            "the shared canonicalization must be wired into exactly the "
            "write_manifest and verify_python python blocks",
        )
        # Write side: manifest keys baked canonically from dist metadata.
        self.assertIn(
            'name = _pypi_canon((dist.metadata.get("Name") or "").strip())',
            self.source,
        )
        # Verify side: manifest keys canonicalized at read time (0444
        # manifests on target boxes are immutable, so tolerance lives here).
        self.assertIn("_pypi_canon(key): value for key, value in installed.items()", self.source)
        # No legacy lowercase-only name normalization survives in the
        # verify_python block.
        verify_block = self.source[self.source.index("verify_python() {") : self.source.index("write_manifest() {")]
        self.assertNotIn(".lower()", verify_block)


class PrepareRuntimeRebuildExecutedTests(unittest.TestCase):
    """Executed end-to-end scenarios (a)-(d) against the real script."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="sea-speed-426-exec."))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        self.runtime_id = write_definition_files(self.work)
        self.install_root = self.work / "install"
        self.runtime_parent = self.install_root / "runtimes"
        self.runtime_root = self.runtime_parent / self.runtime_id

    # -- fixture helpers ---------------------------------------------------

    def _venv_python_wrapper(self, venv_bin: Path) -> Path:
        python_bin = venv_bin / "python"
        python_bin.write_text(f"#!/usr/bin/env bash\nexec {sys.executable} \"$@\"\n", encoding="utf-8")
        python_bin.chmod(0o755)
        return python_bin

    def _manifest_bytes(
        self,
        requirements_lock_sha256: str,
        installed_packages: dict | None = None,
    ) -> bytes:
        package, version = fixture_package()
        manifest = {
            "schema_version": 1,
            "runtime_id": self.runtime_id,
            "origin": "fixture",
            "python": {
                "implementation": platform.python_implementation(),
                "version": platform.python_version(),
            },
            "runtime_lock_sha256": hashlib.sha256(
                (self.work / "runtime-lock.json").read_bytes()
            ).hexdigest(),
            "requirements_sha256": hashlib.sha256(
                (self.work / "requirements-runtime.txt").read_bytes()
            ).hexdigest(),
            "requirements_lock_sha256": requirements_lock_sha256,
            "installed_packages": (
                installed_packages
                if installed_packages is not None
                else {package: version}
            ),
        }
        return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")

    def _existing_runtime(
        self, kind: str, *, manifest_installed_packages: dict | None = None
    ) -> Path:
        """Build a pre-existing runtime dir that fails exactly `kind`."""
        runtime_root = self.runtime_root
        (runtime_root / "venv" / "bin").mkdir(parents=True)
        for name in (
            "runtime-lock.json",
            "requirements-runtime.txt",
            "requirements-runtime.lock.txt",
        ):
            shutil.copy(self.work / name, runtime_root / name)
        self._venv_python_wrapper(runtime_root / "venv" / "bin")
        lock_sha = hashlib.sha256(
            (self.work / "requirements-runtime.lock.txt").read_bytes()
        ).hexdigest()
        if kind == "manifest_file":
            pass  # manifest intentionally absent
        elif kind == "manifest_python":
            (runtime_root / "runtime-manifest.json").write_bytes(
                self._manifest_bytes("f0" * 32)  # wrong lock hash
            )
        else:
            (runtime_root / "runtime-manifest.json").write_bytes(
                self._manifest_bytes(lock_sha, manifest_installed_packages)
            )
        if kind != "ready_file":
            content = f"runtime_id={self.runtime_id}\n"
            if kind == "ready_marker":
                content = "runtime_id=deadbeef\n"
            (runtime_root / "ready").write_text(content, encoding="utf-8")
        if kind == "cmp_runtime_lock":
            with open(runtime_root / "runtime-lock.json", "ab") as handle:
                handle.write(b"# drift\n")
        if kind == "cmp_requirements":
            with open(runtime_root / "requirements-runtime.txt", "ab") as handle:
                handle.write(b"# drift\n")
        if kind == "cmp_lock_file":
            with open(runtime_root / "requirements-runtime.lock.txt", "ab") as handle:
                handle.write(b"# drift\n")
        # Missing-file sub-checks: the runtime-root copy of the named
        # definition file is absent, so verify_ready_runtime fails at the
        # corresponding [[ -f ... ]] check (issue #398 wave 2: the failing
        # sub-check evidence is now exercised for every sub-check).
        if kind == "runtime_lock_file":
            (runtime_root / "runtime-lock.json").unlink()
        elif kind == "requirements_file":
            (runtime_root / "requirements-runtime.txt").unlink()
        elif kind == "lock_file":
            (runtime_root / "requirements-runtime.lock.txt").unlink()
        if kind == "venv_python":
            (runtime_root / "venv" / "bin" / "python").unlink()
        return runtime_root

    def _transformed_script(self) -> Path:
        source = prepare_script().read_text(encoding="utf-8")
        self.assertIn(ROOT_GATE, source)
        adapted = source.replace(
            ROOT_GATE,
            'if [[ "$EUID" -ne 0 && -z "${SEA_SPEED_426_ALLOW_NON_ROOT:-}" ]]; then',
            1,
        )
        script = self.work / "prepare-runtime.sh"
        script.write_text(adapted, encoding="utf-8")
        return script

    def _run_prepare(self, env_extra: dict | None = None) -> subprocess.CompletedProcess:
        bin_dir = self.work / "bin"
        bin_dir.mkdir(exist_ok=True)
        pip_stub = bin_dir / "sea-speed-426-pip-stub"
        pip_stub.write_text(PIP_STUB, encoding="utf-8")
        pip_stub.chmod(0o755)
        py3_stub = bin_dir / "python3"
        py3_stub.write_text(
            PY3_STUB.replace("__PIP_STUB__", str(pip_stub)).replace(
                "__REAL_PYTHON__", sys.executable
            ),
            encoding="utf-8",
        )
        py3_stub.chmod(0o755)
        chown_stub = bin_dir / "chown"
        chown_stub.write_text(CHOWN_STUB, encoding="utf-8")
        chown_stub.chmod(0o755)
        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "SEA_SPEED_426_ALLOW_NON_ROOT": "1",
            "PIP_STUB_LOG": str(self.work / "pip.log"),
            "CHOWN_LOG": str(self.work / "chown.log"),
        }
        dist_path = getattr(self, "_514_dist_path", None)
        if dist_path is not None:
            existing = env.get("PYTHONPATH")
            env["PYTHONPATH"] = (
                f"{dist_path}{os.pathsep}{existing}" if existing else str(dist_path)
            )
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [BASH, str(self._transformed_script()), "--install-root", str(self.install_root)],
            capture_output=True,
            text=True,
            env=env,
        )

    def _quarantine_dirs(self) -> list[Path]:
        return sorted(self.runtime_parent.glob(f".quarantine.{self.runtime_id}.*"))

    # -- scenarios ---------------------------------------------------------

    def test_verification_failure_rebuilds_and_converges(self) -> None:
        # (a) existing runtime fails verification -> which-check evidence,
        # quarantine, deterministic rebuild; the NEXT run reuses the fresh
        # runtime through the script's own verify_ready_runtime gate.
        self._existing_runtime("ready_file")
        first = self._run_prepare()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn(
            f"RUNTIME_VERIFY_FAILED runtime_id={self.runtime_id} check=ready_file",
            first.stderr,
        )
        self.assertIn("RUNTIME_QUARANTINED runtime_id=", first.stderr)
        self.assertIn(
            f"RUNTIME_REBUILT runtime_id={self.runtime_id} reason=ready_file",
            first.stdout,
        )
        self.assertNotIn("RUNTIME_REUSED", first.stdout)
        self.assertNotIn("RUNTIME_CREATED", first.stdout)
        quarantined = self._quarantine_dirs()
        self.assertEqual(len(quarantined), 1)
        # Evidence preserved: the quarantined dir still lacks the ready marker.
        self.assertFalse((quarantined[0] / "ready").exists())
        # The fresh runtime is complete and passes verification.
        self.assertTrue((self.runtime_root / "ready").is_file())
        self.assertTrue((self.runtime_root / "venv" / "bin" / "python").stat().st_mode & 0o111)
        self.assertEqual(
            (self.runtime_root / "runtime-lock.json").read_bytes(),
            (self.work / "runtime-lock.json").read_bytes(),
        )
        self.assertIn("pip download", (self.work / "pip.log").read_text(encoding="utf-8"))
        self.assertIn("pip install", (self.work / "pip.log").read_text(encoding="utf-8"))
        second = self._run_prepare()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn(f"RUNTIME_REUSED runtime_id={self.runtime_id}", second.stdout)
        self.assertNotIn("RUNTIME_REBUILT", second.stdout)

    def test_rebuild_staging_failure_fails_closed_preserving_quarantine(self) -> None:
        # (b) staging/install failure -> fail-closed exit, no partial runtime
        # at the final path, quarantine dir preserved as evidence.
        self._existing_runtime("ready_file")
        result = self._run_prepare({"PIP_INSTALL_FAIL": "1"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            f"RUNTIME_VERIFY_FAILED runtime_id={self.runtime_id} check=ready_file",
            result.stderr,
        )
        self.assertIn("RUNTIME_QUARANTINED runtime_id=", result.stderr)
        self.assertIn(
            f"RUNTIME_REBUILD_FAILED runtime_id={self.runtime_id} reason=ready_file",
            result.stderr,
        )
        self.assertNotIn("RUNTIME_REBUILT", result.stdout)
        self.assertNotIn("RUNTIME_CREATED", result.stdout)
        self.assertFalse(self.runtime_root.exists(), "no partial runtime at the final path")
        quarantined = self._quarantine_dirs()
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(
            (quarantined[0] / "runtime-lock.json").read_bytes(),
            (self.work / "runtime-lock.json").read_bytes(),
        )
        # No staged runtime left behind anywhere in runtimes/.
        self.assertEqual(list(self.runtime_parent.glob(".prepare.*")), [])

    def test_healthy_runtime_is_reused_byte_identically(self) -> None:
        # (c) healthy path pin: exact stdout, empty stderr, no quarantine.
        self._existing_runtime("healthy")
        result = self._run_prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "PASS runtime_lock_validated\n"
            f"RUNTIME_REUSED runtime_id={self.runtime_id}\nRUNTIME_ID {self.runtime_id}\n",
        )
        self.assertEqual(result.stderr, "")
        self.assertEqual(self._quarantine_dirs(), [])

    def test_failing_check_evidence_names_each_sub_check(self) -> None:
        # (d) which-check evidence correctness for EVERY verify_ready_runtime
        # sub-check (issue #398 wave 2): the executed matrix replaces the
        # structural order-mirror pin — each failing runtime kind must produce
        # its named check evidence in classify order.
        cases = {
            "ready_file": "ready marker file missing",
            "venv_python": "venv python executable missing",
            "runtime_lock_file": "runtime lock json missing from runtime root",
            "requirements_file": "runtime requirements missing from runtime root",
            "lock_file": "runtime lock file missing from runtime root",
            "manifest_file": "runtime manifest missing from runtime root",
            "ready_marker": "ready marker runtime_id drift",
            "cmp_runtime_lock": "lock json byte drift",
            "cmp_requirements": "requirements byte drift",
            "cmp_lock_file": "lock file byte drift",
            "manifest_python": "manifest lock-hash drift",
        }
        for kind, description in cases.items():
            with self.subTest(kind=kind, description=description):
                self._existing_runtime(kind)
                result = self._run_prepare()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    f"RUNTIME_VERIFY_FAILED runtime_id={self.runtime_id} check={kind}",
                    result.stderr,
                    description,
                )
                self.assertIn(
                    f"RUNTIME_REBUILT runtime_id={self.runtime_id} reason={kind}",
                    result.stdout,
                )
                self.assertTrue(self.runtime_root.exists())
                if kind == "manifest_python":
                    self.assertIn("RUNTIME_VERIFY_DETAIL", result.stderr)
                    self.assertIn(
                        "runtime manifest requirements_lock_sha256 mismatch", result.stderr
                    )
                else:
                    self.assertNotIn("RUNTIME_VERIFY_DETAIL", result.stderr)
                # Reset: move the rebuilt runtime away so the next sub-case
                # starts from a clean runtimes/ dir (the finalized runtime is
                # read-only, hence the u+w walk first).
                subprocess.run(["chmod", "-R", "u+w", str(self.runtime_root)], check=True)
                shutil.rmtree(self.runtime_root)
                shutil.rmtree(self.runtime_parent)

    def test_rebuild_origin_and_ownership_wiring_executed(self) -> None:
        # Wiring evidence on the executed path: finalize ran with the recorded
        # chown no-op (root-only in production) and the final dir is 0555.
        self._existing_runtime("ready_file")
        result = self._run_prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("chown -R root:root", (self.work / "chown.log").read_text(encoding="utf-8"))
        self.assertEqual(oct(self.runtime_root.stat().st_mode & 0o7777), "0o555")

    # -- issue #514: manifest key canonicalization --------------------------

    def _use_issue_514_fixture(self) -> tuple[str, str]:
        """Rebuild the definition files around the #514 incident shape.

        The lock pins the canonical spelling (e.g. ``typing-extensions``)
        while the installed dist's metadata Name is the non-canonical spelling
        (``typing_extensions``) — exactly how the pre-fix write_manifest keyed
        the manifest. Returns (metadata Name, pinned version) and refreshes
        the runtime-id-derived paths.
        """
        metadata_name, canonical_name, version = fixture_canonicalization_package()
        self.assertNotEqual(metadata_name, canonical_name)
        # When the incident shape was synthesized (bare CI runner), the
        # executed script's python (the real interpreter) must see the
        # synthetic dist for write_manifest/verify distributions() scans.
        self._514_dist_path = canonicalization_dist_path()
        self.runtime_id = write_definition_files_pinned(self.work, canonical_name, version)
        self.runtime_root = self.runtime_parent / self.runtime_id
        return metadata_name, version

    def test_issue_514_metadata_name_manifest_key_verifies_without_rebuild(self) -> None:
        # RED-then-GREEN: an on-box manifest baked by the pre-fix write path
        # keys the installed package by the lowercased metadata Name
        # (typing_extensions) while the lock graph spells it canonically
        # (typing-extensions). Manifests are chmod 0444 immutable on target
        # boxes, so the verifier must canonicalize keys at read time: this
        # must REUSE the runtime on the first run — no verify failure, no
        # quarantine, no rebuild (on base this fails with actual=None).
        metadata_name, version = self._use_issue_514_fixture()
        self._existing_runtime(
            "healthy", manifest_installed_packages={metadata_name: version}
        )
        result = self._run_prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("RUNTIME_VERIFY_FAILED", result.stderr)
        self.assertNotIn("RUNTIME_REBUILT", result.stdout)
        self.assertEqual(self._quarantine_dirs(), [])
        self.assertIn(f"RUNTIME_REUSED runtime_id={self.runtime_id}", result.stdout)

    def test_issue_514_genuinely_missing_manifest_package_still_fails(self) -> None:
        # Negative control: read-time canonicalization must not invent
        # entries. A manifest without the pinned package under ANY spelling
        # still fails verification with the exact graph-drift evidence and
        # rebuilds (unchanged from base by design).
        self._use_issue_514_fixture()
        self._existing_runtime("healthy", manifest_installed_packages={})
        result = self._run_prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            f"RUNTIME_VERIFY_FAILED runtime_id={self.runtime_id} check=manifest_python",
            result.stderr,
        )
        self.assertIn("RUNTIME_VERIFY_DETAIL", result.stderr)
        self.assertIn("runtime manifest graph drift", result.stderr)
        self.assertIn("actual=None", result.stderr)
        self.assertIn(
            f"RUNTIME_REBUILT runtime_id={self.runtime_id} reason=manifest_python",
            result.stdout,
        )
        self.assertEqual(len(self._quarantine_dirs()), 1)

    def test_issue_514_rebaked_manifest_keys_are_canonical_and_reverify(self) -> None:
        # Closes the #514 recurrence loop (3/3 deploys on base): the fresh
        # staging finalize path re-bakes the manifest through the fixed
        # write_manifest, so its keys are now canonical; the NEXT deploy
        # verifies WITH the manifest and reuses. On base the re-baked key
        # stayed non-canonical and every subsequent deploy re-failed.
        metadata_name, version = self._use_issue_514_fixture()
        canonical_name = re.sub(r"[-_.]+", "-", metadata_name).lower()
        first = self._run_prepare()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn(f"RUNTIME_CREATED runtime_id={self.runtime_id}", first.stdout)
        manifest = json.loads(
            (self.runtime_root / "runtime-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["installed_packages"].get(canonical_name), version)
        self.assertNotIn(metadata_name, manifest["installed_packages"])
        second = self._run_prepare()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn(f"RUNTIME_REUSED runtime_id={self.runtime_id}", second.stdout)
        self.assertNotIn("RUNTIME_VERIFY_FAILED", second.stderr)
        self.assertNotIn("RUNTIME_REBUILT", second.stdout)


if __name__ == "__main__":
    unittest.main()
