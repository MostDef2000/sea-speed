#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: prepare-runtime.sh [options]

Options:
  --install-root PATH   Worker installation root (default: /opt/sea-speed-worker)
  --runtime-id-only     Print the deterministic runtime ID and exit

The runtime ID is the SHA-256 of the exact runtime-lock.json bytes plus the
exact requirements-runtime.txt bytes plus the exact
requirements-runtime.lock.txt bytes. A ready runtime is immutable and reused
without pip or network access. The hash-locked requirements-runtime.lock.txt
is the complete dependency graph: fresh creation downloads every artifact with
verified sha256 hashes and installs offline from that verified wheel set.
During migration from a legacy per-release venv, a matching local venv is
copied locally into the shared runtime and no network fallback is allowed if
safe adoption cannot be verified.
EOF
}

install_root="/opt/sea-speed-worker"
runtime_id_only=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root)
      [[ $# -ge 2 ]] || { echo "ERROR --install-root requires a path" >&2; exit 2; }
      install_root="$2"
      shift 2
      ;;
    --runtime-id-only)
      runtime_id_only=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
lock_path="$script_dir/runtime-lock.json"
requirements_path="$script_dir/requirements-runtime.txt"
lock_file_path="$script_dir/requirements-runtime.lock.txt"

for required in "$lock_path" "$requirements_path" "$lock_file_path"; do
  if [[ ! -f "$required" ]]; then
    echo "ERROR runtime definition component missing: $required" >&2
    exit 3
  fi
done
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR required command missing: python3" >&2
  exit 3
fi

runtime_id="$(python3 - "$lock_path" "$requirements_path" "$lock_file_path" <<'PY'
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

lock_path = Path(sys.argv[1])
requirements_path = Path(sys.argv[2])
lock_file_path = Path(sys.argv[3])
payload = (
    lock_path.read_bytes()
    + b"\0"
    + requirements_path.read_bytes()
    + b"\0"
    + lock_file_path.read_bytes()
)
print(hashlib.sha256(payload).hexdigest())
PY
)"

if [[ ! "$runtime_id" =~ ^[0-9a-f]{64}$ ]]; then
  echo "ERROR failed to derive deterministic runtime ID" >&2
  exit 3
fi

if [[ "$runtime_id_only" == true ]]; then
  printf '%s\n' "$runtime_id"
  exit 0
fi

# Fail-closed runtime lock validation: the hash-locked complete dependency
# graph must be present and well-formed before any mutation (venv creation,
# pip download, adoption of a legacy venv). A missing, marker-less, empty or
# incomplete lock aborts the prepare step here, before the root check.
validate_runtime_lock() {
  python3 - "$lock_path" "$requirements_path" "$lock_file_path" <<'PY'
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

lock_path = Path(sys.argv[1])
requirements_path = Path(sys.argv[2])
lock_file_path = Path(sys.argv[3])

lock_file_bytes = lock_file_path.read_bytes()
lock_file_text = lock_file_bytes.decode("utf-8")
if "# sea-speed-runtime-lock-v1" not in lock_file_text:
    raise SystemExit("ERROR runtime lock file schema marker missing: " + lock_file_path.name)

# Join uv-style continuation lines ("... \") into logical requirement lines.
joined: list[str] = []
buffer = ""
for raw in lock_file_text.splitlines():
    line = raw.strip()
    if line.endswith("\\"):
        buffer += " " + line[:-1].strip()
        continue
    buffer += " " + line
    joined.append(buffer.strip())
    buffer = ""
if buffer.strip():
    joined.append(buffer.strip())

graph: dict[str, str] = {}
graph_hashes: dict[str, set[str]] = {}
for text in joined:
    if not text or text.startswith("#"):
        continue
    tokens = text.split()
    if tokens[0].startswith("-"):
        continue
    pinned = re.fullmatch(r"([A-Za-z0-9._-]+)==([^\s]+)", tokens[0])
    hashes = [token for token in tokens[1:] if token.startswith("--hash=sha256:")]
    if pinned is None or not hashes:
        raise SystemExit(f"ERROR runtime lock line is not sha256-hash-pinned: {text}")
    name = pinned.group(1).lower()
    graph[name] = pinned.group(2)
    graph_hashes.setdefault(name, set()).update(
        token.split(":", 1)[1] for token in hashes
    )
if not graph:
    raise SystemExit("ERROR runtime lock graph is empty (resolver output not committed yet)")

lock = json.loads(lock_path.read_text(encoding="utf-8"))
if lock.get("schema_version") != 2:
    raise SystemExit("ERROR runtime-lock.json schema_version must be 2 for hash-locked runtimes")
resolved = lock.get("resolved_lock")
if not isinstance(resolved, dict) or resolved.get("file") != lock_file_path.name:
    raise SystemExit("ERROR runtime-lock.json resolved_lock.file must point at the lock file")
if resolved.get("sha256") != hashlib.sha256(lock_file_bytes).hexdigest():
    raise SystemExit("ERROR runtime-lock.json resolved_lock.sha256 does not match the lock file bytes")
pytorch = lock.get("pytorch", {})
artifact_sha256 = pytorch.get("artifact_sha256")
if not isinstance(artifact_sha256, dict):
    raise SystemExit("ERROR runtime-lock.json pytorch.artifact_sha256 section missing")
for package_name, expected_version in sorted(pytorch.get("packages", {}).items()):
    if graph.get(package_name) != expected_version:
        raise SystemExit(f"ERROR runtime lock graph misses pytorch pin: {package_name}=={expected_version}")
    artifact = artifact_sha256.get(package_name, "")
    if not re.fullmatch(r"[0-9a-f]{64}", artifact):
        raise SystemExit(f"ERROR pytorch artifact sha256 missing or malformed: {package_name}")
    if artifact not in graph_hashes.get(package_name, set()):
        raise SystemExit(f"ERROR pytorch artifact sha256 drift against lock file: {package_name}")

requirements = requirements_path.read_text(encoding="utf-8")
for raw in requirements.splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    if "==" not in line:
        raise SystemExit(f"ERROR runtime requirement is not exact: {line}")
    name, _, expected_version = line.partition("==")
    if graph.get(name.strip().lower()) != expected_version.strip():
        raise SystemExit(f"ERROR runtime requirement absent from hash-locked graph: {line}")

print("PASS runtime_lock_validated")
PY
}

if ! validate_runtime_lock; then
  echo "ERROR runtime lock inputs are invalid; refusing to prepare a runtime" >&2
  exit 3
fi

if [[ "$EUID" -ne 0 ]]; then
  echo "ERROR run as root" >&2
  exit 1
fi
for command_name in cp mv mktemp chmod chown find sort cmp mkdir grep; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "ERROR required command missing: $command_name" >&2
    exit 3
  fi
done

runtime_parent="$install_root/runtimes"
runtime_root="$runtime_parent/$runtime_id"
wheel_cache="$install_root/cache/wheels"
active_marker="$install_root/shared/runtime/active-source-commit"
mkdir -p "$runtime_parent" "$wheel_cache"
chmod 0755 "$runtime_parent"
chmod 0750 "$install_root/cache" "$wheel_cache"

verify_python() {
  local python_bin="$1"
  local manifest_path="${2:-}"
  "$python_bin" - "$lock_path" "$requirements_path" "$lock_file_path" "$manifest_path" <<'PY'
from __future__ import annotations

import importlib
import json
import platform
import re
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

lock = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
requirements = Path(sys.argv[2]).read_text(encoding="utf-8")
lock_file_path = Path(sys.argv[3])
manifest_path = sys.argv[4] if len(sys.argv) > 4 else ""
python_lock = lock["python"]
if platform.python_implementation() != python_lock["implementation"]:
    raise SystemExit("runtime Python implementation mismatch")
if (sys.version_info.major, sys.version_info.minor) != (
    int(python_lock["major"]),
    int(python_lock["minor"]),
):
    raise SystemExit("runtime Python ABI mismatch")

# The hash-locked lock file is the complete graph: direct pins, every
# transitive dependency and the pytorch cu130 closure must be installed.
lock_file_text = lock_file_path.read_text(encoding="utf-8")
joined: list[str] = []
buffer = ""
for raw in lock_file_text.splitlines():
    line = raw.strip()
    if line.endswith("\\"):
        buffer += " " + line[:-1].strip()
        continue
    buffer += " " + line
    joined.append(buffer.strip())
    buffer = ""
if buffer.strip():
    joined.append(buffer.strip())

graph: dict[str, str] = {}
for text in joined:
    if not text or text.startswith("#"):
        continue
    tokens = text.split()
    if tokens[0].startswith("-"):
        continue
    pinned = re.fullmatch(r"([A-Za-z0-9._-]+)==([^\s]+)", tokens[0])
    hashes = [token for token in tokens[1:] if token.startswith("--hash=sha256:")]
    if pinned is None or not hashes:
        raise SystemExit(f"runtime lock line is not sha256-hash-pinned: {text}")
    graph[pinned.group(1).lower()] = pinned.group(2)
if not graph:
    raise SystemExit("runtime lock graph is empty")
expected: dict[str, str] = dict(graph)
for raw in requirements.splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    if "==" not in line:
        raise SystemExit(f"runtime requirement is not exact: {line}")
    name, expected_version = line.split("==", 1)
    if graph.get(name.strip().lower()) != expected_version.strip():
        raise SystemExit(f"runtime requirement absent from hash-locked graph: {line}")

for name, expected_version in sorted(expected.items()):
    try:
        actual = version(name)
    except PackageNotFoundError as exc:
        raise SystemExit(f"runtime package missing: {name}") from exc
    if actual != expected_version:
        raise SystemExit(
            f"runtime version mismatch: {name} expected={expected_version} actual={actual}"
        )

if manifest_path:
    import hashlib

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    expected_lock_hash = hashlib.sha256(lock_file_path.read_bytes()).hexdigest()
    if manifest.get("requirements_lock_sha256") != expected_lock_hash:
        raise SystemExit("runtime manifest requirements_lock_sha256 mismatch")
    installed = manifest.get("installed_packages", {})
    for name, expected_version in sorted(expected.items()):
        actual = installed.get(name)
        if actual != expected_version:
            raise SystemExit(
                f"runtime manifest graph drift: {name} expected={expected_version} actual={actual}"
            )

for module_name in lock["verification_imports"]:
    importlib.import_module(module_name)

print("PASS shared_runtime_imports_and_versions")
PY
}

write_manifest() {
  local python_bin="$1"
  local manifest_path="$2"
  local origin="$3"
  "$python_bin" - "$runtime_id" "$lock_path" "$requirements_path" "$lock_file_path" "$manifest_path" "$origin" <<'PY'
from __future__ import annotations

import hashlib
import json
import platform
import sys
from importlib.metadata import distributions
from pathlib import Path

runtime_id, lock_name, requirements_name, lock_file_name, manifest_name, origin = sys.argv[1:]
lock_path = Path(lock_name)
requirements_path = Path(requirements_name)
lock_file_path = Path(lock_file_name)
packages = {}
for dist in distributions():
    name = (dist.metadata.get("Name") or "").strip().lower()
    if name:
        packages[name] = dist.version
manifest = {
    "schema_version": 1,
    "runtime_id": runtime_id,
    "origin": origin,
    "python": {
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
    },
    "runtime_lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
    "requirements_sha256": hashlib.sha256(requirements_path.read_bytes()).hexdigest(),
    "requirements_lock_sha256": hashlib.sha256(lock_file_path.read_bytes()).hexdigest(),
    "installed_packages": dict(sorted(packages.items())),
}
Path(manifest_name).write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY
}

verify_ready_runtime() {
  [[ -f "$runtime_root/ready" ]] || return 1
  [[ -x "$runtime_root/venv/bin/python" ]] || return 1
  [[ -f "$runtime_root/runtime-lock.json" ]] || return 1
  [[ -f "$runtime_root/requirements-runtime.txt" ]] || return 1
  [[ -f "$runtime_root/requirements-runtime.lock.txt" ]] || return 1
  [[ -f "$runtime_root/runtime-manifest.json" ]] || return 1
  [[ "$(cat "$runtime_root/ready")" == "runtime_id=$runtime_id" ]] || return 1
  cmp -s "$lock_path" "$runtime_root/runtime-lock.json" || return 1
  cmp -s "$requirements_path" "$runtime_root/requirements-runtime.txt" || return 1
  cmp -s "$lock_file_path" "$runtime_root/requirements-runtime.lock.txt" || return 1
  verify_python "$runtime_root/venv/bin/python" "$runtime_root/runtime-manifest.json" >/dev/null
}

# Rebuild diagnostics (issue #426): mirrors the verify_ready_runtime sub-checks
# in the exact same order and prints the name of the FIRST failing check. The
# healthy path keeps using verify_ready_runtime verbatim; this helper runs only
# on the failure branch, to record which sub-check invalidated the existing
# runtime before it is quarantined and rebuilt.
classify_ready_runtime_failure() {
  [[ -f "$runtime_root/ready" ]] || { echo "ready_file"; return 0; }
  [[ -x "$runtime_root/venv/bin/python" ]] || { echo "venv_python"; return 0; }
  [[ -f "$runtime_root/runtime-lock.json" ]] || { echo "runtime_lock_file"; return 0; }
  [[ -f "$runtime_root/requirements-runtime.txt" ]] || { echo "requirements_file"; return 0; }
  [[ -f "$runtime_root/requirements-runtime.lock.txt" ]] || { echo "lock_file"; return 0; }
  [[ -f "$runtime_root/runtime-manifest.json" ]] || { echo "manifest_file"; return 0; }
  [[ "$(cat "$runtime_root/ready")" == "runtime_id=$runtime_id" ]] || { echo "ready_marker"; return 0; }
  cmp -s "$lock_path" "$runtime_root/runtime-lock.json" || { echo "cmp_runtime_lock"; return 0; }
  cmp -s "$requirements_path" "$runtime_root/requirements-runtime.txt" || { echo "cmp_requirements"; return 0; }
  cmp -s "$lock_file_path" "$runtime_root/requirements-runtime.lock.txt" || { echo "cmp_lock_file"; return 0; }
  if ! verify_python "$runtime_root/venv/bin/python" "$runtime_root/runtime-manifest.json" >/dev/null 2>&1; then
    echo "manifest_python"
    return 0
  fi
  echo "unknown"
}

# Non-empty iff the pre-existing runtime dir failed verification and was
# quarantined for a deterministic in-transaction rebuild (issue #426).
rebuild_reason=""

if [[ -e "$runtime_root" ]]; then
  if verify_ready_runtime; then
    printf 'RUNTIME_REUSED runtime_id=%s\n' "$runtime_id"
    printf 'RUNTIME_ID %s\n' "$runtime_id"
    exit 0
  fi
  rebuild_reason="$(classify_ready_runtime_failure)"
  : "${rebuild_reason:=unknown}"
  echo "RUNTIME_VERIFY_FAILED runtime_id=$runtime_id check=$rebuild_reason" >&2
  if [[ "$rebuild_reason" == "manifest_python" ]]; then
    verify_python "$runtime_root/venv/bin/python" "$runtime_root/runtime-manifest.json" 2>&1 |
      sed 's/^/RUNTIME_VERIFY_DETAIL /' >&2 || true
  fi
  # Quarantine, never delete: the failed dir is moved intact (still read-only)
  # to a hidden, collision-proof sibling inside runtimes/, following the
  # existing ".prepare.$runtime_id.XXXXXX" convention. mktemp allocates a
  # unique name; the throwaway placeholder dir is removed and the rename is a
  # same-filesystem mv, so the evidence bytes are preserved exactly.
  quarantine_root="$(mktemp -d "$runtime_parent/.quarantine.$runtime_id.XXXXXX")"
  rmdir "$quarantine_root"
  mv "$runtime_root" "$quarantine_root"
  echo "RUNTIME_QUARANTINED runtime_id=$runtime_id path=$quarantine_root" >&2
fi

finalize_runtime() {
  local staged_root="$1"
  local origin="$2"
  local staged_python="$staged_root/venv/bin/python"

  verify_python "$staged_python"
  cp "$lock_path" "$staged_root/runtime-lock.json"
  cp "$requirements_path" "$staged_root/requirements-runtime.txt"
  cp "$lock_file_path" "$staged_root/requirements-runtime.lock.txt"
  write_manifest "$staged_python" "$staged_root/runtime-manifest.json" "$origin"
  printf 'runtime_id=%s\n' "$runtime_id" > "$staged_root/ready"
  chown -R root:root "$staged_root"
  chmod -R a-w "$staged_root/venv"
  chmod 0444 \
    "$staged_root/runtime-lock.json" \
    "$staged_root/requirements-runtime.txt" \
    "$staged_root/requirements-runtime.lock.txt" \
    "$staged_root/runtime-manifest.json" \
    "$staged_root/ready"
  chmod 0555 "$staged_root"
  mv "$staged_root" "$runtime_root"
}

# A quarantined runtime is always rebuilt through the fresh staging path
# (issue #426): legacy adoption is a migration-only path and shares the same
# on-box python state that just failed verification.
if [[ -z "$rebuild_reason" ]]; then
legacy_active=false
candidates=()
if [[ -f "$active_marker" ]]; then
  active_commit="$(cat "$active_marker")"
  if [[ "$active_commit" =~ ^[0-9a-f]{40}$ ]]; then
    active_release="$install_root/releases/$active_commit"
    if [[ ! -f "$active_release/runtime-id" ]] && \
       [[ -x "$active_release/venv/bin/python" ]]; then
      legacy_active=true
      candidates+=("$active_release/venv")
    fi
  fi
fi

if [[ -d "$install_root/releases" ]]; then
  while IFS= read -r candidate; do
    duplicate=false
    for existing in "${candidates[@]:-}"; do
      if [[ "$candidate" == "$existing" ]]; then
        duplicate=true
        break
      fi
    done
    if [[ "$duplicate" != true ]]; then
      candidates+=("$candidate")
    fi
  done < <(find "$install_root/releases" -mindepth 2 -maxdepth 2 -type d -name venv -print | sort)
fi

for candidate in "${candidates[@]:-}"; do
  [[ -x "$candidate/bin/python" ]] || continue
  if verify_python "$candidate/bin/python" >/dev/null 2>&1; then
    candidate_release="$(basename "$(dirname "$candidate")")"
    staged_root="$(mktemp -d "$runtime_parent/.prepare.$runtime_id.XXXXXX")"
    cleanup_staged=true
    cleanup() {
      if [[ "${cleanup_staged:-false}" == true ]] && [[ -d "${staged_root:-}" ]]; then
        chmod -R u+w "$staged_root" 2>/dev/null || true
        rm -rf "$staged_root"
      fi
    }
    trap cleanup EXIT
    cp -a --reflink=auto "$candidate" "$staged_root/venv"
    finalize_runtime "$staged_root" "legacy-release:$candidate_release"
    cleanup_staged=false
    trap - EXIT
    printf 'RUNTIME_ADOPTED runtime_id=%s legacy_source_commit=%s network_download=false\n' \
      "$runtime_id" "$candidate_release"
    printf 'RUNTIME_ID %s\n' "$runtime_id"
    exit 0
  fi
done

if [[ "$legacy_active" == true ]]; then
  echo "ERROR legacy migration cannot safely adopt a matching local runtime" >&2
  echo "RUNTIME_NETWORK_FALLBACK_BLOCKED runtime_id=$runtime_id" >&2
  exit 21
fi
fi

staged_root="$(mktemp -d "$runtime_parent/.prepare.$runtime_id.XXXXXX")"
wheelhouse_dir="$(mktemp -d "$wheel_cache/.wheelhouse.$runtime_id.XXXXXX")"
cleanup_staged=true
cleanup() {
  if [[ "${cleanup_staged:-false}" == true ]]; then
    if [[ -d "${staged_root:-}" ]]; then
      chmod -R u+w "$staged_root" 2>/dev/null || true
      rm -rf "$staged_root"
    fi
    if [[ -d "${wheelhouse_dir:-}" ]]; then
      chmod -R u+w "$wheelhouse_dir" 2>/dev/null || true
      rm -rf "$wheelhouse_dir"
    fi
  fi
  # Fail-closed rebuild evidence (issue #426): this trap only runs when the
  # staging/install path died before finalize, so a pending rebuild reason
  # here means the rebuild failed closed; the quarantine dir is preserved.
  if [[ -n "${rebuild_reason:-}" ]]; then
    echo "RUNTIME_REBUILD_FAILED runtime_id=$runtime_id reason=$rebuild_reason" >&2
  fi
}
trap cleanup EXIT

python3 -m venv "$staged_root/venv"
runtime_python="$staged_root/venv/bin/python"
readarray -t index_values < <(python3 - "$lock_path" <<'PY'
import json
import sys
from pathlib import Path
lock = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(lock["pytorch"]["index_url"])
print(lock["pytorch"]["pypi_index_url"])
PY
)
pytorch_index="${index_values[0]}"
pypi_index="${index_values[1]}"

# Phase 1: download every artifact of the hash-locked graph — the PyPI-resolved
# requirements graph plus the pytorch cu130 closure — and verify each artifact
# sha256 at download time; any hash mismatch aborts before installation.
PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_CACHE_DIR="$wheel_cache" \
  "$runtime_python" -m pip download \
  --index-url "$pytorch_index" \
  --extra-index-url "$pypi_index" \
  --only-binary=:all: \
  --require-hashes \
  -r "$lock_file_path" \
  --dest "$wheelhouse_dir"

# Phase 2: install strictly offline from the verified wheel set. pip re-verifies
# every artifact hash and refuses anything outside the locked graph. Directive
# lines are stripped so the offline install cannot be re-pointed at an index.
grep -v '^--' "$lock_file_path" > "$staged_root/requirements-runtime.resolved.lock.txt"
PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_CACHE_DIR="$wheel_cache" \
  "$runtime_python" -m pip install \
  --no-index \
  --find-links "$wheelhouse_dir" \
  --require-hashes \
  -r "$staged_root/requirements-runtime.resolved.lock.txt"

finalize_runtime "$staged_root" "network-cache:$wheel_cache"
cleanup_staged=false
trap - EXIT
if [[ -n "$rebuild_reason" ]]; then
  printf 'RUNTIME_REBUILT runtime_id=%s reason=%s\n' "$runtime_id" "$rebuild_reason"
else
  printf 'RUNTIME_CREATED runtime_id=%s cache=%s hash_locked=true\n' "$runtime_id" "$wheel_cache"
fi
printf 'RUNTIME_ID %s\n' "$runtime_id"
