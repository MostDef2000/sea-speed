#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: prepare-runtime.sh [options]

Options:
  --install-root PATH   Worker installation root (default: /opt/sea-speed-worker)
  --runtime-id-only     Print the deterministic runtime ID and exit

The runtime ID is the SHA-256 of the exact runtime-lock.json bytes plus the
exact requirements-runtime.txt bytes. A ready runtime is immutable and reused
without pip or network access. During migration from a legacy per-release venv,
a matching local venv is copied locally into the shared runtime and no network
fallback is allowed if safe adoption cannot be verified.
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

for required in "$lock_path" "$requirements_path"; do
  if [[ ! -f "$required" ]]; then
    echo "ERROR runtime definition component missing: $required" >&2
    exit 3
  fi
done
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR required command missing: python3" >&2
  exit 3
fi

runtime_id="$(python3 - "$lock_path" "$requirements_path" <<'PY'
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

lock_path = Path(sys.argv[1])
requirements_path = Path(sys.argv[2])
payload = lock_path.read_bytes() + b"\0" + requirements_path.read_bytes()
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

if [[ "$EUID" -ne 0 ]]; then
  echo "ERROR run as root" >&2
  exit 1
fi
for command_name in cp mv mktemp chmod chown find sort cmp mkdir; do
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
  "$python_bin" - "$lock_path" "$requirements_path" <<'PY'
from __future__ import annotations

import importlib
import json
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

lock = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
requirements = Path(sys.argv[2]).read_text(encoding="utf-8")
python_lock = lock["python"]
if platform.python_implementation() != python_lock["implementation"]:
    raise SystemExit("runtime Python implementation mismatch")
if (sys.version_info.major, sys.version_info.minor) != (
    int(python_lock["major"]),
    int(python_lock["minor"]),
):
    raise SystemExit("runtime Python ABI mismatch")

expected: dict[str, str] = dict(lock["pytorch"]["packages"])
for raw in requirements.splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    if "==" not in line:
        raise SystemExit(f"runtime requirement is not exact: {line}")
    name, expected_version = line.split("==", 1)
    expected[name.strip()] = expected_version.strip()

for name, expected_version in sorted(expected.items()):
    try:
        actual = version(name)
    except PackageNotFoundError as exc:
        raise SystemExit(f"runtime package missing: {name}") from exc
    if actual != expected_version:
        raise SystemExit(
            f"runtime version mismatch: {name} expected={expected_version} actual={actual}"
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
  "$python_bin" - "$runtime_id" "$lock_path" "$requirements_path" "$manifest_path" "$origin" <<'PY'
from __future__ import annotations

import hashlib
import json
import platform
import sys
from importlib.metadata import distributions
from pathlib import Path

runtime_id, lock_name, requirements_name, manifest_name, origin = sys.argv[1:]
lock_path = Path(lock_name)
requirements_path = Path(requirements_name)
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
  [[ -f "$runtime_root/runtime-manifest.json" ]] || return 1
  [[ "$(cat "$runtime_root/ready")" == "runtime_id=$runtime_id" ]] || return 1
  cmp -s "$lock_path" "$runtime_root/runtime-lock.json" || return 1
  cmp -s "$requirements_path" "$runtime_root/requirements-runtime.txt" || return 1
  verify_python "$runtime_root/venv/bin/python" >/dev/null
}

if [[ -e "$runtime_root" ]]; then
  if verify_ready_runtime; then
    printf 'RUNTIME_REUSED runtime_id=%s\n' "$runtime_id"
    printf 'RUNTIME_ID %s\n' "$runtime_id"
    exit 0
  fi
  echo "ERROR existing runtime ID is incomplete or fails verification: $runtime_root" >&2
  exit 12
fi

finalize_runtime() {
  local staged_root="$1"
  local origin="$2"
  local staged_python="$staged_root/venv/bin/python"

  verify_python "$staged_python"
  cp "$lock_path" "$staged_root/runtime-lock.json"
  cp "$requirements_path" "$staged_root/requirements-runtime.txt"
  write_manifest "$staged_python" "$staged_root/runtime-manifest.json" "$origin"
  printf 'runtime_id=%s\n' "$runtime_id" > "$staged_root/ready"
  chown -R root:root "$staged_root"
  chmod -R a-w "$staged_root/venv"
  chmod 0444 \
    "$staged_root/runtime-lock.json" \
    "$staged_root/requirements-runtime.txt" \
    "$staged_root/runtime-manifest.json" \
    "$staged_root/ready"
  chmod 0555 "$staged_root"
  mv "$staged_root" "$runtime_root"
}

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

staged_root="$(mktemp -d "$runtime_parent/.prepare.$runtime_id.XXXXXX")"
cleanup_staged=true
cleanup() {
  if [[ "${cleanup_staged:-false}" == true ]] && [[ -d "${staged_root:-}" ]]; then
    chmod -R u+w "$staged_root" 2>/dev/null || true
    rm -rf "$staged_root"
  fi
}
trap cleanup EXIT

python3 -m venv "$staged_root/venv"
runtime_python="$staged_root/venv/bin/python"
readarray -t pytorch_values < <(python3 - "$lock_path" <<'PY'
import json
import sys
from pathlib import Path
lock = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(lock["pytorch"]["index_url"])
print(lock["pytorch"]["packages"]["torch"])
print(lock["pytorch"]["packages"]["torchvision"])
PY
)
pytorch_index="${pytorch_values[0]}"
torch_version="${pytorch_values[1]}"
torchvision_version="${pytorch_values[2]}"

PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_CACHE_DIR="$wheel_cache" \
  "$runtime_python" -m pip install \
  --index-url "$pytorch_index" \
  --only-binary=:all: \
  "torch==$torch_version" \
  "torchvision==$torchvision_version"

PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_CACHE_DIR="$wheel_cache" \
  "$runtime_python" -m pip install -r "$requirements_path"

finalize_runtime "$staged_root" "network-cache:$wheel_cache"
cleanup_staged=false
trap - EXIT
printf 'RUNTIME_CREATED runtime_id=%s cache=%s\n' "$runtime_id" "$wheel_cache"
printf 'RUNTIME_ID %s\n' "$runtime_id"
