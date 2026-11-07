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
- On opt-in (#576 diagnostic self-checks) the generated copy additionally
  carries bounded Bash operand probes (a private helper + probe calls) that
  write a bounded sidecar; the probes are best-effort and never affect the
  original process, and the transform is admitted only after a verified
  literal round-trip. The repo script is unchanged.
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

import contextlib
import hashlib
import importlib.metadata
import io
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "deploy/worker/ubuntu/prepare-runtime.sh"
PREPARE_OVERRIDE_ENV = "SEA_SPEED_426_PREPARE_RUNTIME_PATH"
BASH = shutil.which("bash") or "/bin/bash"
ROOT_GATE = 'if [[ "$EUID" -ne 0 ]]; then'

# Issue #576 diagnostic self-checks (RED phase): the diagnostic sidecar
# (implemented in a later GREEN phase) publishes a bounded block to the parent
# test stderr ONLY on opt-in nonzero results. The block is a sequence of
# newline-terminated records, each `D576<TAB>TYPE<TAB>key=value...`; the
# prefix below is the record prefix the self-checks assert on. In the RED
# phase (no instrumentation yet) the block is absent, so the parser fails with
# "missing diagnostics" — not a new API/TypeError.
DIAG_576_PREFIX = "D576\t"
# The unique child-verification seam in finalize_runtime (production line 462,
# count 1) and the SELF-CHECK-ONLY empty lock_path fault: the replacement is
# the anchor plus a newline plus `lock_path=""`, so the assignment lands AFTER
# child verification but BEFORE the three literal cp commands (which stay
# intact and then copy the emptied variable). The fault is diagnostic coverage
# (a known cp failure to exercise the sidecar), NOT a causal reproduction of
# the RF-CI001 "cp empty" incident.
CP_576_ANCHOR = 'verify_python "$staged_python"'
CP_576_FAULT = CP_576_ANCHOR + '\nlock_path=""'

# -- issue #576: GREEN g2a bounded Bash operand probes (opt-in only) --------
# The generated copy (opt-in diagnostic self-checks ONLY) additionally carries
# private Bash helpers (_d576_probe, _d576_child) plus probe calls that write a
# bounded sidecar of D576 OPERAND and CHILD records. The probes are best-effort
# (isolated subshell, private vars, return 0, stderr hidden) and never affect
# the original process; the original three cp commands stay literal and
# untouched.
# The transform is verified by reversing the exact literal replacements to
# reconstruct the root-only adapted source; only then is
# _diag_576_transform_ok set True. The repo script is unchanged.
#
# Each anchor below is a UNIQUE counted literal (count 1) in the root-only
# adapted source; the replacements are applied with str.replace (no regex).
# The helper is inserted after the variable-assignment block (so
# $lock_path/$requirements_path/$lock_file_path/$script_dir are defined before
# the helper body references them); the validated probes after the
# definition-file validation loop; each precopy probe immediately before its
# cp command; the CHILD probe immediately after the unique staged-python verify
# seam, so reaching it means that seam succeeded under set -e.
DIAG_576_VAR_BLOCK = (
    'script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"\n'
    'lock_path="$script_dir/runtime-lock.json"\n'
    'requirements_path="$script_dir/requirements-runtime.txt"\n'
    'lock_file_path="$script_dir/requirements-runtime.lock.txt"'
)
DIAG_576_VALIDATION_LOOP = (
    'for required in "$lock_path" "$requirements_path" "$lock_file_path"; do\n'
    '  if [[ ! -f "$required" ]]; then\n'
    '    echo "ERROR runtime definition component missing: $required" >&2\n'
    '    exit 3\n'
    '  fi\n'
    'done'
)
DIAG_576_CP_LOCK = '  cp "$lock_path" "$staged_root/runtime-lock.json"'
DIAG_576_CP_REQ = '  cp "$requirements_path" "$staged_root/requirements-runtime.txt"'
DIAG_576_CP_LOCKFILE = '  cp "$lock_file_path" "$staged_root/requirements-runtime.lock.txt"'
# The private Bash helper. It classifies the raw operand (expected/empty/
# redacted), records the actual raw length, the file-existence flags from the
# raw operand, the caller pid/line (expanded before entering the helper), and
# a category-only cp lookup (no function/alias body or name inventory). The
# sidecar write is bounded (<=512B row, <=16 rows, <=8192B) using metadata-only
# size and a bounded-prefix count; I/O errors never break the real run.
DIAG_576_HELPER = r'''_d576_probe() {
  (
    _d576_stage="$1"
    _d576_slot="$2"
    _d576_raw="$3"
    _d576_pid="$4"
    _d576_line="$5"
    # Classify against the ORIGINAL fixture paths rendered as LITERALS by the
    # Python transform (the __D576_DEF_*__ placeholders), never against
    # $script_dir-derived paths or the rebound $lock_path/$requirements_path/
    # $lock_file_path variables: a self-check fault may rebind $script_dir
    # (which would move a $script_dir-derived allowlist/sidecar) or rebind a
    # definition variable (leaking its raw bytes), and comparing the raw
    # operand against either would misclassify. The literal allowlist is
    # EXACT (one of the 3 rendered definition paths) AND must match the safe
    # ASCII path regex; empty is EMPTY; everything else is REDACTED before
    # collection.
    _d576_safe_re='^[A-Za-z0-9_./:+-]{1,256}$'
    if [[ -z "$_d576_raw" ]]; then
      _d576_value="EMPTY"
      _d576_class="empty"
    elif [[ "$_d576_raw" == __D576_DEF_LOCK__ || "$_d576_raw" == __D576_DEF_REQ__ || "$_d576_raw" == __D576_DEF_LOCKFILE__ ]] && [[ "$_d576_raw" =~ $_d576_safe_re ]]; then
      _d576_value="$_d576_raw"
      _d576_class="expected"
    else
      _d576_value="REDACTED"
      _d576_class="redacted"
    fi
    _d576_chars="${#_d576_raw}"
    _d576_exists=0
    _d576_file=0
    [[ -e "$_d576_raw" ]] && _d576_exists=1
    [[ -f "$_d576_raw" ]] && _d576_file=1
    _d576_cp_kind="$(type -t cp 2>/dev/null)"
    case "$_d576_cp_kind" in
      file|function|alias|builtin) ;;
      "") _d576_cp_kind="missing" ;;
      *) _d576_cp_kind="other" ;;
    esac
    _d576_cp_path="REDACTED"
    if [[ "$_d576_cp_kind" == "file" ]]; then
      _d576_cp_path="$(command -v cp 2>/dev/null)"
      if [[ "$_d576_cp_path" != "/usr/bin/cp" && "$_d576_cp_path" != "/bin/cp" && "$_d576_cp_path" != __D576_CP__ ]]; then
        _d576_cp_path="REDACTED"
      fi
    fi
    # The sidecar destination is a LITERAL rendered by the Python transform
    # (the __D576_SIDECAR__ placeholder), never $script_dir-derived: a
    # self-check fault that rebinds $script_dir cannot move the sidecar.
    _d576_sidecar=__D576_SIDECAR__
    _d576_tab=$'\t'
    _d576_rec="D576${_d576_tab}OPERAND${_d576_tab}stage=${_d576_stage}${_d576_tab}slot=${_d576_slot}${_d576_tab}value=${_d576_value}${_d576_tab}chars=${_d576_chars}${_d576_tab}class=${_d576_class}${_d576_tab}exists=${_d576_exists}${_d576_tab}file=${_d576_file}${_d576_tab}pid=${_d576_pid}${_d576_tab}line=${_d576_line}${_d576_tab}cp_kind=${_d576_cp_kind}${_d576_tab}cp_path=${_d576_cp_path}"
    if [[ ${#_d576_rec} -le 511 ]]; then
      _d576_size=0
      _d576_rows=0
      if [[ -f "$_d576_sidecar" ]]; then
        # METADATA-only size (stat), never an unbounded content read; the row
        # count reads ONLY a bounded 8192-byte prefix.
        _d576_size=$(command stat -c %s "$_d576_sidecar" 2>/dev/null)
        _d576_rows=$(head -c 8192 "$_d576_sidecar" 2>/dev/null | tr -cd '\n' | wc -c)
      fi
      # Validate the numeric counters BEFORE arithmetic: a bad counter is a
      # logging skip (observer-only), never a real process error.
      if [[ $_d576_size =~ ^[0-9]+$ ]] && [[ $_d576_rows =~ ^[0-9]+$ ]]; then
        if [[ $_d576_rows -lt 16 && $((_d576_size + ${#_d576_rec} + 1)) -le 8192 ]]; then
          printf '%s\n' "$_d576_rec" >> "$_d576_sidecar" 2>/dev/null
        fi
      fi
    fi
  ) 2>/dev/null || :
  return 0
}
_d576_child() {
  (
    # Reaching this line means the staged-python verify seam succeeded under
    # set -e (the call is inserted immediately after it), so status=found is
    # a faithful inference for the child runtime. The pinned name/version are
    # read from the FIRST line of the LITERAL rendered requirements path
    # (__D576_DEF_REQ__), parsed as name==version, and validated against the
    # same safe ASCII regex as the operand probes.
    _d576_child_req=__D576_DEF_REQ__
    _d576_child_sidecar=__D576_SIDECAR__
    _d576_child_tab=$'\t'
    _d576_child_name="REDACTED"
    _d576_child_version="REDACTED"
    _d576_child_status="error"
    _d576_child_line=""
    if [[ -f "$_d576_child_req" ]]; then
      # Byte-bounded (512) first-line read; truncation may invalidate a token (REDACTED/error) or leave it regex-valid.
      _d576_child_line="$(head -c 512 "$_d576_child_req" 2>/dev/null | head -n 1)" || _d576_child_line=""
    fi
    _d576_child_line="${_d576_child_line//[[:space:]]/}"
    if [[ "$_d576_child_line" == *"=="* ]]; then
      _d576_child_name="${_d576_child_line%%==*}"
      _d576_child_version="${_d576_child_line#*==}"
    fi
    _d576_child_safe_re='^[A-Za-z0-9_./:+-]{1,256}$'
    if [[ "$_d576_child_name" =~ $_d576_child_safe_re ]] && [[ "$_d576_child_version" =~ $_d576_child_safe_re ]]; then
      _d576_child_status="found"
    else
      _d576_child_name="REDACTED"
      _d576_child_version="REDACTED"
      _d576_child_status="error"
    fi
    _d576_child_rec="D576${_d576_child_tab}CHILD${_d576_child_tab}name=${_d576_child_name}${_d576_child_tab}version=${_d576_child_version}${_d576_child_tab}status=${_d576_child_status}"
    if [[ ${#_d576_child_rec} -le 511 ]]; then
      _d576_child_size=0
      _d576_child_rows=0
      if [[ -f "$_d576_child_sidecar" ]]; then
        _d576_child_size=$(command stat -c %s "$_d576_child_sidecar" 2>/dev/null)
        _d576_child_rows=$(head -c 8192 "$_d576_child_sidecar" 2>/dev/null | tr -cd '\n' | wc -c)
      fi
      if [[ $_d576_child_size =~ ^[0-9]+$ ]] && [[ $_d576_child_rows =~ ^[0-9]+$ ]]; then
        if [[ $_d576_child_rows -lt 16 && $((_d576_child_size + ${#_d576_child_rec} + 1)) -le 8192 ]]; then
          printf '%s\n' "$_d576_child_rec" >> "$_d576_child_sidecar" 2>/dev/null
        fi
      fi
    fi
  ) 2>/dev/null || :
  return 0
}'''
# The 3 validated probe calls (inserted after the definition-file validation
# loop): one per definition file, reading the raw variable as validated.
DIAG_576_VALIDATED_PROBES = (
    '_d576_probe validated lock "${lock_path-}" "$BASHPID" "$LINENO"\n'
    '_d576_probe validated requirements "${requirements_path-}" "$BASHPID" "$LINENO"\n'
    '_d576_probe validated resolved "${lock_file_path-}" "$BASHPID" "$LINENO"'
)
# The 3 precopy probe calls (inserted immediately before each cp command):
# they read the raw variable AFTER any self-check rebind (the fault assigns
# lock_path after verify_python, before these probes). $LINENO is the actual
# call-site line (BASH_LINENO[0] is the function-invocation line: 0 at top
# level, the caller line inside a function); ${var-} keeps the observer from
# tripping nounset before the original cp.
DIAG_576_PRECOPY_LOCK = '  _d576_probe precopy lock "${lock_path-}" "$BASHPID" "$LINENO"'
DIAG_576_PRECOPY_REQ = '  _d576_probe precopy requirements "${requirements_path-}" "$BASHPID" "$LINENO"'
DIAG_576_PRECOPY_LOCKFILE = '  _d576_probe precopy resolved "${lock_file_path-}" "$BASHPID" "$LINENO"'
# The CHILD probe call (inserted immediately after the unique verify seam
# CP_576_ANCHOR): it invokes the private _d576_child helper, which reads the
# pinned name==version from the LITERAL rendered requirements path and writes
# one bounded D576 CHILD record. Reaching the call means the verify seam
# succeeded under set -e, so status=found is a faithful inference.
DIAG_576_CHILD_CALL = '  _d576_child'


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
        # #576 diagnostic (opt-in only): reset the transform flag every
        # transformation, then compile the private Bash helper + insert the
        # bounded operand probes. The transform is admitted ONLY if reversing
        # the exact literal replacements reconstructs the root-only adapted
        # source; on any compile/anchor/IO failure we fall back to the
        # original root-adapted script (no new healthy-process failure).
        self._diag_576_transform_ok = False
        if getattr(self, "_diag_576_optin", False):
            try:
                instrumented = self._diag_576_instrument(adapted)
                if self._diag_576_verify_roundtrip(adapted, instrumented):
                    self._diag_576_transform_ok = True
                    adapted = instrumented
            except Exception:
                self._diag_576_transform_ok = False
        script = self.work / "prepare-runtime.sh"
        script.write_text(adapted, encoding="utf-8")
        return script

    def _diag_576_replacements(self) -> list[tuple[str, str]]:
        """The exact UNIQUE counted literal (anchor, replacement) list.

        Each anchor occurs exactly once in the root-only adapted source; the
        replacement re-embeds the anchor verbatim (the cp commands stay
        literal and untouched) so reversing (replacement -> anchor) exactly
        reconstructs the root-only adapted source.

        The probe helper's 5 raw template placeholders are rendered with the
        known fixture LITERALS (shlex.quote ONCE each): the 3 definition
        paths, the fixture bin/cp, and the sidecar. These are LITERALS (not
        $script_dir-derived), so a self-check fault that rebinds $script_dir
        cannot move the sidecar destination or misclassify the operands. The
        rendering is deterministic (same self.work), so the instrument and
        round-trip steps use the exact same rendered replacements.
        """
        helper = (
            DIAG_576_HELPER
            .replace(
                "__D576_DEF_LOCK__",
                shlex.quote(str(self.work / "runtime-lock.json")),
            )
            .replace(
                "__D576_DEF_REQ__",
                shlex.quote(str(self.work / "requirements-runtime.txt")),
            )
            .replace(
                "__D576_DEF_LOCKFILE__",
                shlex.quote(str(self.work / "requirements-runtime.lock.txt")),
            )
            .replace(
                "__D576_CP__",
                shlex.quote(str(self.work / "bin" / "cp")),
            )
            .replace(
                "__D576_SIDECAR__",
                shlex.quote(str(self.work / ".576diag.trace")),
            )
        )
        return [
            (DIAG_576_VAR_BLOCK, DIAG_576_VAR_BLOCK + "\n" + helper),
            (
                DIAG_576_VALIDATION_LOOP,
                DIAG_576_VALIDATION_LOOP + "\n" + DIAG_576_VALIDATED_PROBES,
            ),
            (DIAG_576_CP_LOCK, DIAG_576_PRECOPY_LOCK + "\n" + DIAG_576_CP_LOCK),
            (DIAG_576_CP_REQ, DIAG_576_PRECOPY_REQ + "\n" + DIAG_576_CP_REQ),
            (
                DIAG_576_CP_LOCKFILE,
                DIAG_576_PRECOPY_LOCKFILE + "\n" + DIAG_576_CP_LOCKFILE,
            ),
            (CP_576_ANCHOR, CP_576_ANCHOR + "\n" + DIAG_576_CHILD_CALL),
        ]

    def _diag_576_instrument(self, root_adapted: str) -> str:
        """Apply the literal replacements (no regex); each anchor must be unique."""
        instrumented = root_adapted
        for anchor, replacement in self._diag_576_replacements():
            if instrumented.count(anchor) != 1:
                raise ValueError(
                    "#576 diagnostic anchor not unique (count != 1): "
                    f"{anchor[:40]!r}..."
                )
            instrumented = instrumented.replace(anchor, replacement, 1)
        return instrumented

    def _diag_576_verify_roundtrip(self, root_adapted: str, instrumented: str) -> bool:
        """Reverse the exact replacements; True iff root-only adapted is rebuilt."""
        reversed_source = instrumented
        for anchor, replacement in self._diag_576_replacements():
            if replacement not in reversed_source:
                return False
            reversed_source = reversed_source.replace(replacement, anchor, 1)
        return reversed_source == root_adapted

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
        # #576 diagnostic (opt-in only): reset the sidecar before the run.
        if getattr(self, "_diag_576_optin", False):
            try:
                self._diag_576_reset_sidecar()
            except Exception:
                pass
        # Extract the final script (runs the real _transformed_script, or the
        # capture helper's patched version with the fault substitution).
        script = self._transformed_script()
        # Hash the final script bytes PRELAUNCH (after the self-check mutator).
        diag = None
        if getattr(self, "_diag_576_optin", False):
            try:
                diag = self._diag_576_collect(script, env)
            except Exception:
                diag = None
        proc = subprocess.run(
            [BASH, str(script), "--install-root", str(self.install_root)],
            capture_output=True,
            text=True,
            env=env,
        )
        if diag is not None and proc.returncode != 0:
            try:
                self._diag_576_publish(diag)
            except Exception:
                pass
        return proc

    # -- issue #576: parent-side bounded publisher (GREEN g1) ---------------
    # The diagnostic sidecar (written by the shell producer in a later step)
    # is read here (bounded) and published to the parent test stderr ONLY on
    # opt-in nonzero results. On success/unopted runs the parent stderr stays
    # quiet. The subprocess streams are never augmented; the original
    # CompletedProcess is returned unchanged.
    # Known limitation: the parent only sees records that reached the sidecar;
    # a producer-side omission (probe subshell killed early, a row dropped by the producer's own bounds) is invisible, and END truncated=1 covers parent-side omissions only.

    def _diag_576_sidecar(self) -> Path:
        return self.work / ".576diag.trace"

    def _diag_576_reset_sidecar(self) -> None:
        try:
            self._diag_576_sidecar().write_bytes(b"")
        except Exception:
            pass

    def _diag_576_fixture_pin(self) -> tuple[str, str, str]:
        """(branch, name, version) from the CURRENT written definition pin."""
        branch = (
            "synthetic" if getattr(self, "_514_dist_path", None) is not None else "natural"
        )
        name = version = "REDACTED"
        try:
            # Bounded 512-byte read.
            with open(self.work / "requirements-runtime.txt", "rb") as fh:
                line = fh.read(512).decode("utf-8", errors="replace").splitlines()[0].strip()
            if "==" in line:
                pkg, ver = line.split("==", 1)
                if re.fullmatch(r"[A-Za-z0-9_./:+-]{1,256}", pkg.strip()):
                    name = pkg.strip()
                if re.fullmatch(r"[A-Za-z0-9_./:+-]{1,256}", ver.strip()):
                    version = ver.strip()
        except Exception:
            pass
        return branch, name, version

    def _diag_576_signals(self, env: dict) -> tuple[str, str, str]:
        # PRESENCE ONLY (input keys), never unrelated env facts or value text:
        # bash_env_present = exact BASH_ENV key presence; env_present = exact
        # ENV key presence; exported_function_present = a standard exported
        # function KEY (prefix BASH_FUNC_ + suffix %%) is present. Values are
        # never scanned (no names/values dump).
        bash_env = "1" if "BASH_ENV" in env else "0"
        env_pres = "1" if "ENV" in env else "0"
        exported = (
            "1"
            if any(
                isinstance(k, str) and k.startswith("BASH_FUNC_") and k.endswith("%%")
                for k in env
            )
            else "0"
        )
        return bash_env, env_pres, exported

    def _diag_576_collect(self, script: Path, env: dict) -> dict:
        source_bytes = prepare_script().read_bytes()
        selected = hashlib.sha256(source_bytes).hexdigest()
        adapted = source_bytes.decode("utf-8").replace(
            ROOT_GATE,
            'if [[ "$EUID" -ne 0 && -z "${SEA_SPEED_426_ALLOW_NON_ROOT:-}" ]]; then',
            1,
        )
        root_adapted = hashlib.sha256(adapted.encode("utf-8")).hexdigest()
        executed = hashlib.sha256(script.read_bytes()).hexdigest()
        branch, name, version = self._diag_576_fixture_pin()
        # transform_ok reflects the VERIFIED private flag (the g2a round-trip
        # proof), never the hashes (selected/root_adapted/executed always
        # differ by construction and are not a transform-success signal).
        transform_ok = "1" if getattr(self, "_diag_576_transform_ok", False) else "0"
        return {
            "selected": selected,
            "root_adapted": root_adapted,
            "executed": executed,
            "transform_ok": transform_ok,
            "branch": branch,
            "name": name,
            "version": version,
            "signals": self._diag_576_signals(env),
        }

    def _diag_576_read_sidecar(self) -> tuple[list[str], bool]:
        """Bounded read (<=8193B) + strict parse of the sidecar records."""
        try:
            with open(self._diag_576_sidecar(), "rb") as fh:
                data = fh.read(8193)
        except Exception:
            return [], True  # missing/unreadable: partial header block, truncated
        truncated = len(data) == 8193
        if truncated:
            data = data[:8192]
        lines: list[bytes] = []
        start = 0
        for i, b in enumerate(data):
            if b == 0x0A:
                lines.append(data[start : i + 1])
                start = i + 1
        if start < len(data):
            truncated = True  # incomplete trailing line
        records: list[str] = []
        for line in lines:
            rec = self._diag_576_parse_sidecar_line(line)
            if rec is None:
                truncated = True
            else:
                records.append(rec)
        return records, truncated

    def _diag_576_parse_sidecar_line(self, line: bytes) -> str | None:
        # Raw bound FIRST (before decode/parse): a row >512 bytes including
        # its newline is rejected outright.
        if len(line) > 512:
            return None
        if not line.endswith(b"\n"):
            return None
        try:
            text = line.decode("ascii")
        except UnicodeDecodeError:
            return None
        if not text.startswith("D576\t"):
            return None
        parts = text[len("D576\t") :].rstrip("\n").split("\t")
        if len(parts) < 2:
            return None
        rtype = parts[0]
        if rtype not in ("OPERAND", "CHILD"):
            return None
        fields: dict[str, str] = {}
        for kv in parts[1:]:
            if "=" not in kv:
                return None
            key, value = kv.split("=", 1)
            if key in fields:
                return None
            fields[key] = value
        validated = (
            self._diag_576_validate_operand(fields)
            if rtype == "OPERAND"
            else self._diag_576_validate_child(fields)
        )
        if validated is None:
            return None
        record = (
            "D576\t" + rtype + "\t" + "\t".join(f"{k}={v}" for k, v in validated.items()) + "\n"
        )
        # Sanitization (redaction) can EXPAND a row (e.g. a 1-char value
        # becomes REDACTED): the serialized record must still be <=512 bytes
        # including its newline, else it is omitted (read_sidecar marks
        # truncated). Never return an overlong post-sanitization record.
        if len(record.encode("ascii")) > 512:
            return None
        return record

    def _diag_576_validate_operand(self, f: dict[str, str]) -> dict[str, str] | None:
        if set(f) != {
            "stage", "slot", "value", "chars", "class", "exists", "file",
            "pid", "line", "cp_kind", "cp_path",
        }:
            return None
        if f["stage"] not in ("validated", "precopy"):
            return None
        if f["slot"] not in ("lock", "requirements", "resolved"):
            return None
        if f["class"] not in ("expected", "empty", "redacted"):
            return None
        if not re.fullmatch(r"[0-9]+", f["chars"]):
            return None
        if f["exists"] not in ("0", "1") or f["file"] not in ("0", "1"):
            return None
        if not re.fullmatch(r"[1-9][0-9]*", f["pid"]) or not re.fullmatch(
            r"[1-9][0-9]*", f["line"]
        ):
            return None
        if f["cp_kind"] not in ("file", "function", "alias", "builtin", "other", "missing"):
            return None
        fixture_paths = {
            str(self.work / "runtime-lock.json"),
            str(self.work / "requirements-runtime.txt"),
            str(self.work / "requirements-runtime.lock.txt"),
        }
        raw = f["value"]
        if raw in fixture_paths:
            value, cls = raw, "expected"
        elif raw == "EMPTY":
            value, cls = "EMPTY", "empty"
        else:
            value, cls = "REDACTED", "redacted"
        cp_path = f["cp_path"]
        if cp_path not in ("/usr/bin/cp", "/bin/cp", str(self.work / "bin" / "cp")):
            cp_path = "REDACTED"
        out = dict(f)
        out["value"], out["class"], out["cp_path"] = value, cls, cp_path
        return out

    def _diag_576_validate_child(self, f: dict[str, str]) -> dict[str, str] | None:
        if set(f) != {"name", "version", "status"}:
            return None
        if f["status"] not in ("found", "missing", "error"):
            return None
        _, exp_name, exp_version = self._diag_576_fixture_pin()
        out = dict(f)
        out["name"] = f["name"] if f["name"] == exp_name else "REDACTED"
        out["version"] = f["version"] if f["version"] == exp_version else "REDACTED"
        return out

    def _diag_576_publish(self, diag: dict) -> None:
        """Emit the bounded D576 block to parent sys.stderr (failure+opt-in)."""
        source_rec = (
            "D576\tSOURCE\tselected_sha256=" + diag["selected"]
            + "\troot_adapted_sha256=" + diag["root_adapted"]
            + "\texecuted_sha256=" + diag["executed"]
            + "\ttransform_ok=" + diag["transform_ok"] + "\n"
        )
        fixture_rec = (
            "D576\tFIXTURE\tbranch=" + diag["branch"]
            + "\tname=" + diag["name"] + "\tversion=" + diag["version"] + "\n"
        )
        bash_env, env_pres, exported = diag["signals"]
        signals_rec = (
            "D576\tSIGNALS\tbash_env_present=" + bash_env
            + "\tenv_present=" + env_pres
            + "\texported_function_present=" + exported + "\n"
        )
        # EVERY published record (headers AND sidecar rows) must be <=512
        # bytes including its newline, measured AFTER sanitization: an
        # oversize record is OMITTED (never published) and the omission is
        # reported as truncation.
        truncated = False
        headers: list[str] = []
        for rec in (source_rec, fixture_rec, signals_rec):
            if len(rec.encode("ascii")) > 512:
                truncated = True
                continue
            headers.append(rec)
        header_size = sum(len(rec.encode("ascii")) for rec in headers)
        available = 8192 - header_size - 64  # reserve 64B for the END record
        sidecar_records, sidecar_truncated = self._diag_576_read_sidecar()
        if sidecar_truncated:
            truncated = True
        included: list[str] = []
        sidecar_size = 0
        for rec in sidecar_records:
            rec_size = len(rec.encode("ascii"))
            if rec_size > 512:
                truncated = True
                continue  # omit this oversize row, keep trying the rest
            if len(included) >= 12 or sidecar_size + rec_size > available:
                truncated = True
                break
            included.append(rec)
            sidecar_size += rec_size
        records = headers + included
        total = len(records) + 1
        records.append(
            "D576\tEND\trecords=" + str(total) + "\ttruncated=" + ("1" if truncated else "0") + "\n"
        )
        sys.stderr.write("".join(records))
        sys.stderr.flush()

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
        # First call instrumented opt-in: a CI failure publishes the bounded
        # D576 block to the parent stderr (visible in the CI job log); success stays quiet.
        first, captured_576 = self._run_prepare_capturing_parent_stderr()
        if first.returncode != 0 and captured_576:
            sys.stderr.write(captured_576)
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

    # -- issue #576: diagnostic self-checks (RED phase) ----------------------

    def _run_prepare_capturing_parent_stderr(
        self, fault_substitution: tuple[str, str] | None = None
    ) -> tuple[subprocess.CompletedProcess, str]:
        """Run the real _run_prepare with the parent test stderr captured.

        The private opt-in flag is set and restored around the single
        _run_prepare call (ignored by the baseline helpers in the RED phase).
        ``fault_substitution`` (anchor, replacement) injects one exact
        substitution into the GENERATED copy only: the real
        _transformed_script runs first, then the single substitution is applied
        to the generated bytes. The subprocess streams are unchanged; only the
        parent test stderr is captured. A minimal pass-through spy on
        subprocess.run (real call, unchanged args/kwargs) proves the single
        invocation and exact args; env/kwargs are never asserted or dumped.
        """
        had_optin = hasattr(self, "_diag_576_optin")
        prev_optin = getattr(self, "_diag_576_optin", None)
        self._diag_576_optin = True
        original_transformed = self._transformed_script
        if fault_substitution is not None:
            anchor, replacement = fault_substitution

            def patched_transformed() -> Path:
                script = original_transformed()
                text = script.read_text(encoding="utf-8")
                self.assertEqual(
                    text.count(anchor),
                    1,
                    "fault anchor must occur exactly once in the generated copy",
                )
                text = text.replace(anchor, replacement, 1)
                script.write_text(text, encoding="utf-8")
                return script

            self._transformed_script = patched_transformed
        old_stderr = sys.stderr
        diag_path = self.work / ".576diag.parent-stderr"
        original_run = subprocess.run  # capture BEFORE patch
        calls: list[tuple] = []

        def spy_run(*args, **kwargs):
            proc = original_run(*args, **kwargs)  # real call, unchanged
            calls.append((proc, tuple(args[0]), proc.returncode, proc.stdout, proc.stderr))
            return proc

        subprocess.run = spy_run
        try:
            with open(diag_path, "w", encoding="utf-8") as diag_file:
                sys.stderr = diag_file
                result = self._run_prepare()
        finally:
            subprocess.run = original_run
            sys.stderr = old_stderr
            self._transformed_script = original_transformed
            if had_optin:
                self._diag_576_optin = prev_optin
            else:
                delattr(self, "_diag_576_optin")
        # pass-through spy: exactly one real subprocess.run; identity + fields
        self.assertEqual(len(calls), 1, "exactly one subprocess.run call")
        proc, args_copy, rc, stdout, stderr = calls[0]
        self.assertIs(result, proc, "result IS the original CompletedProcess")
        self.assertEqual(tuple(result.args), args_copy)
        self.assertEqual(result.returncode, rc)
        self.assertEqual(result.stdout, stdout)
        self.assertEqual(result.stderr, stderr)
        self.assertEqual(
            result.args,
            [BASH, str(self.work / "prepare-runtime.sh"), "--install-root",
             str(self.install_root)],
        )
        parent_stderr = diag_path.read_text(encoding="utf-8")
        return result, parent_stderr

    def _parse_diag_576(self, text: str) -> list[tuple[str, dict[str, str]]]:
        """Parse and structurally validate the #576 diagnostic block.

        Returns a list of (type, fields) tuples in record order. This is a
        test-only structural validator: it asserts the block is nonempty,
        starts with the record prefix, is ASCII, bounded (<=8192 bytes,
        <=16 newline-terminated records, each <=512 bytes including its
        newline), and that every record is `D576<TAB>TYPE<TAB>key=value...`
        with an allowed TYPE and no duplicate keys. It does NOT assert
        per-field value oracles (those are later small steps).
        """
        # nonempty / prefix FIRST (missing-diagnostics RED)
        self.assertTrue(
            text,
            "missing diagnostics: #576 diagnostic block is empty",
        )
        self.assertTrue(
            text.startswith(DIAG_576_PREFIX),
            "missing diagnostics: #576 diagnostic block must start with the D576 record prefix",
        )
        # ASCII
        self.assertTrue(
            all(ord(ch) < 128 for ch in text),
            "#576 diagnostic block must be ASCII",
        )
        # <=8192 bytes block
        self.assertLessEqual(
            len(text.encode("ascii")),
            8192,
            "#576 diagnostic block exceeds 8192 bytes",
        )
        # newline-terminated records
        self.assertTrue(
            text.endswith("\n"),
            "#576 diagnostic block must be newline-terminated",
        )
        records = text.split("\n")[:-1]
        # <=16 records
        self.assertLessEqual(
            len(records),
            16,
            "#576 diagnostic block exceeds 16 records",
        )
        allowed_types = {"SOURCE", "FIXTURE", "OPERAND", "CHILD", "SIGNALS", "END"}
        parsed: list[tuple[str, dict[str, str]]] = []
        for record in records:
            # each <=512 bytes including newline
            self.assertLessEqual(
                len(record.encode("ascii")) + 1,
                512,
                f"#576 diagnostic record exceeds 512 bytes including newline: {record!r}",
            )
            # format D576<TAB>TYPE<TAB>key=value...
            self.assertTrue(
                record.startswith(DIAG_576_PREFIX),
                f"#576 diagnostic record must start with the D576 record prefix: {record!r}",
            )
            parts = record[len(DIAG_576_PREFIX):].split("\t")
            self.assertGreaterEqual(
                len(parts),
                2,
                f"#576 diagnostic record must be D576<TAB>TYPE<TAB>key=value...: {record!r}",
            )
            rtype = parts[0]
            self.assertIn(
                rtype,
                allowed_types,
                f"#576 diagnostic record type not allowed: {rtype!r}",
            )
            fields: dict[str, str] = {}
            for kv in parts[1:]:
                self.assertIn(
                    "=",
                    kv,
                    f"#576 diagnostic field must be key=value: {kv!r}",
                )
                key, value = kv.split("=", 1)
                self.assertNotIn(
                    key,
                    fields,
                    f"#576 diagnostic record has duplicate key: {key!r}",
                )
                fields[key] = value
            parsed.append((rtype, fields))
        return parsed

    def _assert_operand_576(self, f: dict[str, str]) -> None:
        """Field oracle for one #576 OPERAND record (exact keys + value classes)."""
        self.assertEqual(
            set(f),
            {"stage", "slot", "value", "chars", "class", "exists", "file",
             "pid", "line", "cp_kind", "cp_path"},
            "OPERAND record must have the exact key set",
        )
        for key in ("pid", "line"):
            self.assertRegex(
                f[key], r"^[1-9][0-9]*$", f"OPERAND {key} must be a positive decimal"
            )
        self.assertIn(
            f["cp_kind"],
            {"file", "function", "alias", "builtin", "other", "missing"},
            f"OPERAND cp_kind not allowed: {f['cp_kind']!r}",
        )
        cp_path = f["cp_path"]
        self.assertTrue(
            cp_path and len(cp_path) <= 256 and all(ord(c) < 128 for c in cp_path),
            f"OPERAND cp_path must be nonempty ASCII <=256: {cp_path!r}",
        )
        self.assertTrue(
            cp_path in ("/usr/bin/cp", "/bin/cp", "REDACTED")
            or cp_path.startswith(f"{self.work / 'bin'}{os.sep}"),
            f"OPERAND cp_path must be a known fixture bin or system cp: {cp_path!r}",
        )

    def test_576_failure_selfcheck(self) -> None:
        # #576 diagnostic self-check (failure path): a SELF-CHECK-ONLY empty
        # lock_path assignment in the GENERATED copy (after child
        # verification, before the precopy) makes the actual cp execute and
        # fail nonzero; the original cp stderr is retained in the subprocess
        # streams. The diagnostic sidecar (GREEN phase) would publish a
        # bounded block of D576 records to the parent test stderr; in the RED
        # phase the block is absent, so the parser fails with "missing
        # diagnostics" (not a new API/TypeError). The fault copy is diagnostic
        # coverage, NOT a causal reproduction of the RF-CI001 "cp empty"
        # incident.
        result, parent_stderr = self._run_prepare_capturing_parent_stderr(
            (CP_576_ANCHOR, CP_576_FAULT)
        )
        # The actual cp must execute and fail nonzero; the original cp stderr
        # is retained in the subprocess streams (unchanged by the sidecar).
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cp:", result.stderr)
        # The subprocess streams must NOT contain the diagnostic prefix (the
        # sidecar publishes to the parent test stderr, not the subprocess).
        self.assertNotIn(DIAG_576_PREFIX, result.stdout)
        self.assertNotIn(DIAG_576_PREFIX, result.stderr)
        # The parent test stderr must contain the diagnostic block (RED:
        # missing diagnostics). The parser validates the block structure; the
        # semantic requirements (all record types present, END last, records
        # total, truncated=0) are asserted after the parser.
        parsed = self._parse_diag_576(parent_stderr)
        self.assertGreater(
            len(parsed),
            0,
            "missing diagnostics: #576 diagnostic block has no records",
        )
        types_present = {rtype for rtype, _ in parsed}
        for required in ("SOURCE", "FIXTURE", "OPERAND", "CHILD", "SIGNALS", "END"):
            self.assertIn(
                required,
                types_present,
                f"missing diagnostics: record type {required!r} absent from parent stderr",
            )
        self.assertEqual(
            parsed[-1][0],
            "END",
            "missing diagnostics: END record must be last",
        )
        end_fields = parsed[-1][1]
        self.assertEqual(set(end_fields), {"records", "truncated"})
        self.assertEqual(
            end_fields.get("records"),
            str(len(parsed)),
            "missing diagnostics: END records field must equal the total record count",
        )
        self.assertEqual(
            end_fields.get("truncated"),
            "0",
            "missing diagnostics: END truncated field must be '0'",
        )
        # #576 SOURCE value oracles: exactly one SOURCE record.
        source_records = [f for t, f in parsed if t == "SOURCE"]
        self.assertEqual(len(source_records), 1, "exactly one SOURCE record")
        src = source_records[0]
        self.assertEqual(
            set(src),
            {"selected_sha256", "root_adapted_sha256", "executed_sha256", "transform_ok"},
        )
        self.assertEqual(
            src.get("selected_sha256"),
            hashlib.sha256(prepare_script().read_bytes()).hexdigest(),
        )
        adapted = prepare_script().read_text(encoding="utf-8").replace(
            ROOT_GATE,
            'if [[ "$EUID" -ne 0 && -z "${SEA_SPEED_426_ALLOW_NON_ROOT:-}" ]]; then',
            1,
        )
        self.assertEqual(
            src.get("root_adapted_sha256"),
            hashlib.sha256(adapted.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            src.get("executed_sha256"),
            hashlib.sha256((self.work / "prepare-runtime.sh").read_bytes()).hexdigest(),
        )
        self.assertEqual(src.get("transform_ok"), "1")
        # #576 OPERAND value oracles: exactly 3 validated records; the first
        # precopy record proves the observed lock_path variable was emptied.
        operand = [f for t, f in parsed if t == "OPERAND"]
        for f in operand:
            self._assert_operand_576(f)
        validated = [f for f in operand if f.get("stage") == "validated"]
        self.assertEqual(len(validated), 3, "exactly 3 validated OPERAND records")
        by_slot = {f.get("slot"): f for f in validated}
        self.assertEqual(set(by_slot), {"lock", "requirements", "resolved"})
        for slot, name in (
            ("lock", "runtime-lock.json"),
            ("requirements", "requirements-runtime.txt"),
            ("resolved", "requirements-runtime.lock.txt"),
        ):
            path = self.work / name
            f = by_slot[slot]
            self.assertEqual(f.get("value"), str(path))
            self.assertEqual(f.get("chars"), str(len(str(path))))
            self.assertEqual(f.get("exists"), "1")
            self.assertEqual(f.get("file"), "1")
            self.assertEqual(f.get("class"), "expected")
        precopy = [f for f in operand if f.get("stage") == "precopy"]
        self.assertGreaterEqual(len(precopy), 1, "at least one precopy OPERAND record")
        first = precopy[0]
        self.assertEqual(first.get("slot"), "lock")
        self.assertEqual(first.get("value"), "EMPTY")
        self.assertEqual(first.get("chars"), "0")
        self.assertEqual(first.get("class"), "empty")
        self.assertEqual(first.get("exists"), "0")
        self.assertEqual(first.get("file"), "0")
        # #576 FIXTURE/CHILD/SIGNALS value oracles (failure case).
        package, version = fixture_package()
        fixture_records = [f for t, f in parsed if t == "FIXTURE"]
        self.assertEqual(len(fixture_records), 1, "exactly one FIXTURE record")
        fx = fixture_records[0]
        self.assertEqual(set(fx), {"branch", "name", "version"})
        self.assertEqual(fx.get("branch"), "natural")
        self.assertEqual(fx.get("name"), package)
        self.assertEqual(fx.get("version"), version)
        child_records = [f for t, f in parsed if t == "CHILD"]
        self.assertEqual(len(child_records), 1, "exactly one CHILD record")
        child = child_records[0]
        self.assertEqual(set(child), {"name", "version", "status"})
        self.assertEqual(child.get("status"), "found")
        self.assertEqual(child.get("name"), package)
        self.assertEqual(child.get("version"), version)
        signals_records = [f for t, f in parsed if t == "SIGNALS"]
        self.assertEqual(len(signals_records), 1, "exactly one SIGNALS record")
        sig = signals_records[0]
        self.assertEqual(
            set(sig),
            {"bash_env_present", "env_present", "exported_function_present"},
            "SIGNALS record must have exactly the 3 signal keys",
        )
        for key in ("bash_env_present", "env_present", "exported_function_present"):
            self.assertIn(sig[key], ("0", "1"), f"SIGNALS {key} must be 0 or 1")

    def test_576_success_selfcheck(self) -> None:
        # #576 diagnostic self-check (success path): the same opt-in fresh
        # actual run SUCCEEDS and the parent test stderr / subprocess streams
        # are QUIET (no diagnostic block, no diagnostic prefix). This is a
        # quiet test: it PASSES in the RED phase (no instrumentation) and does
        # not itself prove the instrumentation; it pins that the success path
        # stays quiet when the sidecar is added (GREEN phase).
        result, parent_stderr = self._run_prepare_capturing_parent_stderr()
        # Normal output/result assertions (retained from the healthy fresh run).
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"RUNTIME_CREATED runtime_id={self.runtime_id}", result.stdout)
        self.assertIn(f"RUNTIME_ID {self.runtime_id}", result.stdout)
        # The parent test stderr must be EXACTLY empty (no diagnostic block on
        # success).
        self.assertEqual(parent_stderr, "")
        # The subprocess streams must NOT contain the diagnostic prefix.
        self.assertNotIn(DIAG_576_PREFIX, result.stdout)
        self.assertNotIn(DIAG_576_PREFIX, result.stderr)

    def test_576_disclosure_bounds_selfcheck(self) -> None:
        # #576 diagnostic self-check (disclosure/bounds): the test-copy fault
        # assigns the lock_path VARIABLE to an outside-allowlist test marker
        # (real newline + long benign runtime-constructed tail, no literal
        # credential-shaped strings), so the diagnostic variable itself sees
        # the bad value, not just a cp literal. The original real cp stderr
        # retains the marker (as before — the subprocess streams are
        # unchanged). The parent diagnostic block (GREEN phase) must NOT leak
        # the marker (head or tail) and must be bounded/escaped (outside
        # classified/redacted + truncation explicit). In the RED phase the
        # block is absent, so this fails FIRST on the missing block (not a
        # vacuous empty-output pass).
        tail = "x" * 300  # runtime-constructed benign tail
        marker = "SEA576OUTSIDE\n" + tail
        fault = (CP_576_ANCHOR, f"{CP_576_ANCHOR}\nlock_path={shlex.quote(marker)}")
        result, parent_stderr = self._run_prepare_capturing_parent_stderr(fault)
        # The actual cp must execute and fail nonzero; the original cp stderr
        # retains the marker's value (as before — the subprocess streams are
        # unchanged). cp shell-quotes the real-newline marker, so the raw
        # marker is not a literal substring; assert on the distinctive tail.
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(tail, result.stderr)
        # The parent diagnostic block must EXIST and be well-formed (non-vacuous
        # RED: fails first on the missing block, not on a vacuous empty-output
        # pass). The parser validates the block structure.
        parsed = self._parse_diag_576(parent_stderr)
        # The block must NOT leak the outside-allowlist marker: assert BOTH the
        # marker head and the 300x tail are absent (not merely the raw
        # newline-joined marker).
        self.assertNotIn(
            "SEA576OUTSIDE",
            parent_stderr,
            "disclosure: outside-allowlist marker head leaked into parent stderr",
        )
        self.assertNotIn(
            tail,
            parent_stderr,
            "disclosure: 300x tail leaked into parent stderr",
        )
        # #576 PRIVACY value oracle: the first precopy record (the
        # outside-marker lock_path) is redacted to the exact REDACTED marker.
        operand = [f for t, f in parsed if t == "OPERAND"]
        for f in operand:
            self._assert_operand_576(f)
        precopy = [f for f in operand if f.get("stage") == "precopy"]
        self.assertGreaterEqual(len(precopy), 1, "at least one precopy OPERAND record")
        first = precopy[0]
        self.assertEqual(first.get("slot"), "lock")
        self.assertEqual(first.get("value"), "REDACTED")
        self.assertEqual(first.get("class"), "redacted")
        self.assertEqual(first.get("chars"), str(len(marker)))
        self.assertEqual(first.get("exists"), "0")
        self.assertEqual(first.get("file"), "0")
        # Redaction does not mean the block was truncated.
        end = [f for t, f in parsed if t == "END"]
        self.assertEqual(len(end), 1, "exactly one END record")
        self.assertEqual(set(end[0]), {"records", "truncated"})
        self.assertEqual(end[0].get("truncated"), "0", "redaction does not mean truncated")

    def test_576_publisher_guard(self) -> None:
        # #576 publisher guard (g1b): a private publisher UNIT (no subprocess,
        # no Bash reproducer) that drives the REAL private helpers and pins the
        # peer-g1 REQUEST_CHANGES fixes:
        #   - SIGNALS measure BASH_ENV / ENV / exported-function KEY presence
        #     only (input keys), never unrelated env facts (PATH) or value text.
        #   - OPERAND validation rejects invalid stage / slot / class enums.
        #   - A raw sidecar row >512 bytes (incl. its newline) is rejected
        #     BEFORE decode/parse.
        #   - The publisher enforces <=512 bytes on EVERY record (headers
        #     included): an oversize FIXTURE header is omitted, END reports
        #     truncated=1 with the recomputed total, and every published
        #     record stays <=512 bytes.
        # transform_ok stays "0" (intentional partial g1 state; the g2 compiler
        # verifies the exact insertion round-trip before it may become "1").
        # Parent stderr is captured with stdlib io/contextlib only.

        # -- SIGNALS: input-key presence only ------------------------------
        with self.subTest(signals="presence"):
            present = {
                "BASH_ENV": "/tmp/sea576-bashrc",
                "ENV": "/tmp/sea576-envrc",
                "BASH_FUNC_sea576%%": "sea576 () { :; }",
            }
            self.assertEqual(self._diag_576_signals(present), ("1", "1", "1"))
        with self.subTest(signals="unrelated-path-and-value-text"):
            # PATH is an unrelated env fact; a value that merely CONTAINS
            # function text is not an exported-function KEY.
            unrelated = {
                "PATH": "/usr/bin:/bin",
                "SEA576_VALUE": "looks like () { a function body; }",
            }
            self.assertEqual(self._diag_576_signals(unrelated), ("0", "0", "0"))
        with self.subTest(signals="presence-not-truthiness"):
            # An empty-valued BASH_ENV is still PRESENT (key presence, not
            # value truthiness).
            self.assertEqual(self._diag_576_signals({"BASH_ENV": ""}), ("1", "0", "0"))

        # -- OPERAND: invalid stage / slot / class rejected ----------------
        lock_path = str(self.work / "runtime-lock.json")
        base = {
            "stage": "validated",
            "slot": "lock",
            "value": lock_path,
            "chars": str(len(lock_path)),
            "class": "expected",
            "exists": "1",
            "file": "1",
            "pid": "1",
            "line": "1",
            "cp_kind": "file",
            "cp_path": "/usr/bin/cp",
        }
        with self.subTest(operand="valid-base-accepted"):
            validated = self._diag_576_validate_operand(dict(base))
            self.assertIsNotNone(validated)
            self.assertEqual(validated["class"], "expected")
        for field in ("stage", "slot", "class"):
            with self.subTest(operand=f"reject-{field}"):
                bad = dict(base)
                bad[field] = "bogus"
                self.assertIsNone(self._diag_576_validate_operand(bad))

        # -- sidecar row: >512 bytes (incl. newline) rejected pre-decode ---
        prefix = "D576\tOPERAND\tstage=validated\tslot=lock\tvalue="
        suffix = (
            "\tchars=0\tclass=redacted\texists=0\tfile=0"
            "\tpid=1\tline=1\tcp_kind=other\tcp_path=/usr/bin/cp\n"
        )
        n512 = 512 - len(prefix) - len(suffix)
        with self.subTest(row="exactly-512-accepted"):
            line512 = (prefix + "x" * n512 + suffix).encode("ascii")
            self.assertEqual(len(line512), 512)
            self.assertIsNotNone(self._diag_576_parse_sidecar_line(line512))
        with self.subTest(row="oversize-513-rejected"):
            line513 = (prefix + "x" * (n512 + 1) + suffix).encode("ascii")
            self.assertEqual(len(line513), 513)
            self.assertIsNone(self._diag_576_parse_sidecar_line(line513))

        # -- publisher: oversize FIXTURE header omitted, bounds hold -------
        # Two valid 256-char fixture tokens build a 555-byte FIXTURE header
        # that exceeds the 512-byte record bound and must be omitted.
        diag = {
            "selected": "0" * 64,
            "root_adapted": "1" * 64,
            "executed": "2" * 64,
            "transform_ok": "0",
            "branch": "natural",
            "name": "a" * 256,
            "version": "b" * 256,
            "signals": ("0", "0", "0"),
        }
        with self.subTest(publish="oversize-fixture-omitted"):
            self._diag_576_reset_sidecar()
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                self._diag_576_publish(diag)
            text = buf.getvalue()
            # The 555-byte FIXTURE header must be omitted, never published.
            self.assertNotIn("FIXTURE", text)
            # The block is still well-formed and bounded.
            self.assertTrue(text.endswith("\n"))
            records = text.split("\n")[:-1]
            self.assertLessEqual(len(records), 16)
            self.assertLessEqual(len(text.encode("ascii")), 8192)
            for record in records:
                self.assertLessEqual(
                    len(record.encode("ascii")) + 1,
                    512,
                    f"published record exceeds 512 bytes: {record!r}",
                )
            self.assertEqual(records[0].split("\t")[1], "SOURCE")
            self.assertEqual(records[-1].split("\t")[1], "END")
            self.assertIn("SIGNALS", text)
            end_fields = dict(
                kv.split("=", 1) for kv in records[-1][len("D576\tEND\t"):].split("\t")
            )
            self.assertEqual(end_fields["records"], str(len(records)))
            self.assertEqual(end_fields["truncated"], "1")

    def test_576_logging_failure_is_observer_only(self) -> None:
        # #576 publisher-logging unit (g2io): the sidecar PATH is a DIRECTORY
        # before a healthy opt-in run, so every probe's sidecar write fails.
        # The logging failure must be OBSERVER-ONLY: the original healthy run
        # still succeeds (rc 0), the parent test stderr stays EXACTLY empty
        # (no diagnostic block on success), and the subprocess streams carry
        # no D576 prefix. Controlled publisher-logging unit, NOT an RF-CI-001
        # repro. The existing setUp provides a fresh fixture (no nested case
        # helpers); the sidecar directory is removed with self.work.
        sidecar = self._diag_576_sidecar()
        sidecar.mkdir()  # sidecar path is a DIRECTORY: every probe write fails
        result, parent_stderr = self._run_prepare_capturing_parent_stderr()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            parent_stderr,
            "",
            "parent stderr must be EXACTLY empty on a healthy run",
        )
        self.assertNotIn(DIAG_576_PREFIX, result.stdout)
        self.assertNotIn(DIAG_576_PREFIX, result.stderr)

    def test_576_probe_destination_is_immutable(self) -> None:
        # #576 probe destination immutability (g2paths): a SELF-CHECK-ONLY
        # script_dir rebind (after CP_576_ANCHOR) to an owned rebound dir must
        # NOT move the probe sidecar destination or misclassify the operands.
        # The probe helper binds the sidecar destination and the expected-path
        # allowlist as LITERALS rendered by the Python transform (not
        # $script_dir-derived), so the rebind is inert. The ORIGINAL definition
        # vars (lock_path/requirements_path/lock_file_path) are unchanged: they
        # were computed from the ORIGINAL script_dir at definition time, before
        # the rebind, so the real cp commands still copy the original files.
        # The real run succeeds (rc 0), the parent stderr is quiet, all 6
        # OPERAND records land in the ORIGINAL sidecar (not truncated), and NO
        # trace file appears under the rebound dir. The fault is diagnostic
        # coverage (a known rebind to exercise the literal bindings), NOT a
        # causal reproduction of the RF-CI001 incident.
        rebound = self.work / "rebound-576"
        rebound.mkdir()
        fault = (
            CP_576_ANCHOR,
            CP_576_ANCHOR + "\nscript_dir=" + shlex.quote(str(rebound)),
        )
        result, parent_stderr = self._run_prepare_capturing_parent_stderr(fault)
        # The real run succeeds: the rebind is inert (the original cp commands
        # still copy the ORIGINAL definition files, which are unchanged).
        self.assertEqual(result.returncode, 0, result.stderr)
        # The parent stderr is quiet (success path, no diagnostic block).
        self.assertEqual(
            parent_stderr,
            "",
            "parent stderr must be EXACTLY empty on a healthy run",
        )
        # NO trace file under the rebound dir: the sidecar destination is a
        # literal, not $script_dir-derived, so the rebind cannot move it.
        self.assertFalse(
            (rebound / ".576diag.trace").exists(),
            "probe sidecar must NOT be written under the rebound script_dir",
        )
        # All 6 OPERAND records are in the ORIGINAL sidecar, not truncated.
        records, truncated = self._diag_576_read_sidecar()
        self.assertFalse(truncated, "sidecar must not be truncated")
        operand = [rec for rec in records if "\tOPERAND\t" in rec]
        self.assertEqual(
            len(operand),
            6,
            "exactly 6 OPERAND records in the original sidecar",
        )
        # For all OPERAND records, the line field must point to an actual
        # generated line beginning `_d576_probe {stage} {slot} `.
        script_lines = (
            (self.work / "prepare-runtime.sh").read_text(encoding="utf-8").splitlines()
        )
        for rec in operand:
            fields = dict(
                kv.split("=", 1) for kv in rec[len("D576\tOPERAND\t"):].split("\t")
            )
            line_no = int(fields["line"])
            stage = fields["stage"]
            slot = fields["slot"]
            self.assertLessEqual(
                line_no,
                len(script_lines),
                f"line field {line_no} within script bounds",
            )
            actual_line = script_lines[line_no - 1]
            self.assertTrue(
                actual_line.strip().startswith(f"_d576_probe {stage} {slot} "),
                f"line {line_no} must begin `_d576_probe {stage} {slot} `, "
                f"got: {actual_line!r}",
            )

    def test_576_sidecar_read_overflow(self) -> None:
        # #576 read-bound characterization (g3): the 8193-byte read bound in
        # _diag_576_read_sidecar ALREADY exists; this unit pins it. A sidecar
        # of valid D576 OPERAND rows >8192 bytes must come back truncated with
        # only complete records, and the overflowing sidecar must make the
        # publisher's END record carry truncated=1.
        value = "x" * 300
        line = (
            "D576\tOPERAND\tstage=validated\tslot=lock\tvalue=" + value
            + "\tchars=" + str(len(value))
            + "\tclass=redacted\texists=0\tfile=0\tpid=1\tline=1"
            + "\tcp_kind=other\tcp_path=/usr/bin/cp\n"
        ).encode("ascii")
        self.assertLessEqual(len(line), 512)
        # sanity: the row is a valid record per the real parser
        self.assertIsNotNone(self._diag_576_parse_sidecar_line(line))
        n = 8192 // len(line) + 2  # guarantees the sidecar exceeds 8192 bytes
        sidecar = self._diag_576_sidecar()
        with self.subTest(read="overflow"):
            sidecar.write_bytes(line * n)
            records, truncated = self._diag_576_read_sidecar()
            self.assertTrue(truncated, "overflowing sidecar must be marked truncated")
            self.assertGreater(len(records), 0, "complete records must survive the bound")
            for rec in records:
                # every returned record is a complete, valid parsed record
                self.assertIsNotNone(
                    self._diag_576_parse_sidecar_line(rec.encode("ascii")),
                    f"returned record is not a complete valid record: {rec!r}",
                )
            self.assertLessEqual(
                sum(len(r.encode("ascii")) for r in records),
                8192,
                "total returned record bytes must respect the 8192 bound",
            )
        with self.subTest(read="incomplete-tail"):
            # valid records + a trailing partial line without a newline
            partial = line[: len(line) // 2]
            sidecar.write_bytes(line * 2 + partial)
            records, truncated = self._diag_576_read_sidecar()
            self.assertTrue(truncated, "incomplete trailing line must be marked truncated")
            self.assertEqual(len(records), 2, "only the 2 complete lines are returned")
        with self.subTest(publish="overflow-end-truncated"):
            # with the overflowing sidecar, the END record carries truncated=1.
            # Headers are kept in-bounds so the truncation is attributable to the
            # sidecar overflow, not header omission.
            sidecar.write_bytes(line * n)
            diag = {
                "selected": "0" * 64,
                "root_adapted": "1" * 64,
                "executed": "2" * 64,
                "transform_ok": "0",
                "branch": "natural",
                "name": "pkg",
                "version": "1.0",
                "signals": ("0", "0", "0"),
            }
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                self._diag_576_publish(diag)
            text = buf.getvalue()
            self.assertTrue(text.endswith("\n"))
            records = text.split("\n")[:-1]
            self.assertEqual(records[-1].split("\t")[1], "END")
            end_fields = dict(
                kv.split("=", 1) for kv in records[-1][len("D576\tEND\t"):].split("\t")
            )
            self.assertEqual(end_fields["truncated"], "1")


if __name__ == "__main__":
    unittest.main()
