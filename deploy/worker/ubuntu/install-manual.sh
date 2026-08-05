#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install-manual.sh <40-character-source-commit> [install-root]

Run from the root of an exact Sea Speed checkout. This script prepares a
manual Ubuntu worker installation only. It does not install NVIDIA drivers,
CUDA, PyTorch, systemd services, secrets, models, or production data.
EOF
}

expected_commit="${1:-}"
install_root="${2:-/opt/sea-speed-worker}"

if [[ ! "$expected_commit" =~ ^[0-9a-f]{40}$ ]]; then
  usage >&2
  echo "ERROR source commit must be a lowercase 40-character SHA" >&2
  exit 2
fi

for command_name in git python3 ffmpeg; do
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

if [[ ! -f deploy/worker/ubuntu/requirements-runtime.txt ]]; then
  echo "ERROR runtime requirements missing" >&2
  exit 6
fi

mkdir -p "$install_root/releases/$expected_commit"
mkdir -p "$install_root/shared/models"
mkdir -p "$install_root/shared/datasets"
mkdir -p "$install_root/shared/output"
mkdir -p "$install_root/shared/config"

release_root="$install_root/releases/$expected_commit"
if [[ -e "$release_root/source" ]]; then
  echo "ERROR release already prepared: $release_root/source" >&2
  exit 7
fi

mkdir "$release_root/source"
git archive "$expected_commit" | tar -x -C "$release_root/source"

python3 -m venv "$release_root/venv"
"$release_root/venv/bin/python" -m pip install --upgrade pip setuptools wheel

if ! "$release_root/venv/bin/python" -c 'import torch' >/dev/null 2>&1; then
  cat >&2 <<'EOF'
ERROR PyTorch is not installed in the release environment.
Install the hardware-compatible PyTorch build after verifying the NVIDIA
runtime, then rerun dependency installation manually:
  <venv>/bin/python -m pip install -r deploy/worker/ubuntu/requirements-runtime.txt
The installer does not guess a CUDA or PyTorch build before hardware exists.
EOF
  exit 8
fi

"$release_root/venv/bin/python" -m pip install \
  -r "$release_root/source/deploy/worker/ubuntu/requirements-runtime.txt"

if [[ ! -f "$install_root/shared/config/worker.env" ]]; then
  cp "$release_root/source/deploy/worker/ubuntu/worker.env.example" \
    "$install_root/shared/config/worker.env.example"
  chmod 600 "$install_root/shared/config/worker.env.example"
fi

printf '%s\n' "$expected_commit" > "$release_root/source-commit"
printf 'PREPARED %s\n' "$release_root"
printf 'PROTECTED %s\n' "$install_root/shared/config"
printf 'PROTECTED %s\n' "$install_root/shared/models"
printf 'PROTECTED %s\n' "$install_root/shared/datasets"
printf 'PROTECTED %s\n' "$install_root/shared/output"
printf 'UNKNOWN worker_runtime=server_not_commissioned\n'
