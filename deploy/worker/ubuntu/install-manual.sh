#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: install-manual.sh <40-character-source-commit> [install-root]

Run from the root of an exact Sea Speed checkout. This script prepares one
immutable source release and binds it to an immutable shared Worker runtime.
It does not install NVIDIA drivers, systemd services, secrets, models, or
production data. Heavy AI dependencies are reused by runtime ID whenever the
runtime definition is unchanged.
USAGE
}

expected_commit="${1:-}"
install_root="${2:-/opt/sea-speed-worker}"

if [[ ! "$expected_commit" =~ ^[0-9a-f]{40}$ ]]; then
  usage >&2
  echo "ERROR source commit must be a lowercase 40-character SHA" >&2
  exit 2
fi

for command_name in git python3 ffmpeg tar awk; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "ERROR required command missing: $command_name" >&2
    exit 3
  fi
done

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" ]]; then
  echo "ERROR run from a Git checkout" >&2
  exit 4
fi
cd "$repo_root"

actual_commit="$(git rev-parse HEAD)"
if [[ "$actual_commit" != "$expected_commit" ]]; then
  echo "ERROR checkout commit mismatch" >&2
  echo "expected=$expected_commit" >&2
  echo "actual=$actual_commit" >&2
  exit 5
fi

python3 scripts/worker/check_ubuntu_compatibility.py
bash deploy/worker/ubuntu/preflight.sh

for required in \
  deploy/worker/ubuntu/requirements-runtime.txt \
  deploy/worker/ubuntu/runtime-lock.json \
  deploy/worker/ubuntu/prepare-runtime.sh; do
  if [[ ! -f "$required" ]]; then
    echo "ERROR runtime preparation component missing: $required" >&2
    exit 6
  fi
done

mkdir -p "$install_root/releases"
mkdir -p "$install_root/shared/models"
mkdir -p "$install_root/shared/datasets"
mkdir -p "$install_root/shared/output"
mkdir -p "$install_root/shared/config"

release_root="$install_root/releases/$expected_commit"
source_root="$release_root/source"
runtime_id_file="$release_root/runtime-id"
mkdir -p "$release_root"

if [[ ! -e "$source_root" ]]; then
  mkdir "$source_root"
  git archive "$expected_commit" | tar -x -C "$source_root"
  printf '%s\n' "$expected_commit" > "$release_root/source-commit"
else
  if [[ ! -f "$release_root/source-commit" ]] || \
     [[ "$(cat "$release_root/source-commit")" != "$expected_commit" ]]; then
    echo "ERROR existing release provenance mismatch" >&2
    exit 7
  fi
fi

runtime_output="$(
  bash "$source_root/deploy/worker/ubuntu/prepare-runtime.sh" \
    --install-root "$install_root"
)"
printf '%s\n' "$runtime_output"
runtime_id="$(printf '%s\n' "$runtime_output" | awk '/^RUNTIME_ID [0-9a-f]{64}$/ {print $2}' | tail -n 1)"
if [[ ! "$runtime_id" =~ ^[0-9a-f]{64}$ ]]; then
  echo "ERROR shared runtime preparation did not return a valid runtime ID" >&2
  exit 8
fi

runtime_root="$install_root/runtimes/$runtime_id"
if [[ ! -x "$runtime_root/venv/bin/python" ]] || \
   [[ ! -f "$runtime_root/ready" ]] || \
   [[ "$(cat "$runtime_root/ready")" != "runtime_id=$runtime_id" ]]; then
  echo "ERROR prepared shared runtime verification failed" >&2
  exit 8
fi

if [[ -f "$runtime_id_file" ]] && [[ "$(cat "$runtime_id_file")" != "$runtime_id" ]]; then
  echo "ERROR existing release runtime binding mismatch" >&2
  exit 9
fi
printf '%s\n' "$runtime_id" > "$runtime_id_file"
chown root:root "$release_root/source-commit" "$runtime_id_file"
chmod 0644 "$release_root/source-commit" "$runtime_id_file"

if [[ ! -e "$install_root/shared/config/worker.env" ]] && \
   [[ ! -e "$install_root/shared/config/worker.env.example" ]]; then
  cp "$source_root/deploy/worker/ubuntu/worker.env.example" \
    "$install_root/shared/config/worker.env.example"
  chmod 600 "$install_root/shared/config/worker.env.example"
fi

printf 'PREPARED %s\n' "$release_root"
printf 'SOURCE_COMMIT %s\n' "$expected_commit"
printf 'RUNTIME_ID %s\n' "$runtime_id"
printf 'PROTECTED %s\n' "$install_root/shared/config"
printf 'PROTECTED %s\n' "$install_root/shared/models"
printf 'PROTECTED %s\n' "$install_root/shared/datasets"
printf 'PROTECTED %s\n' "$install_root/shared/output"
printf 'UNKNOWN worker_runtime=server_not_commissioned\n'
