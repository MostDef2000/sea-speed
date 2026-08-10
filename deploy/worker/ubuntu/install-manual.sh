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

for command_name in git python3 ffmpeg tar; do
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

mkdir -p "$install_root/releases"
mkdir -p "$install_root/shared/models"
mkdir -p "$install_root/shared/datasets"
mkdir -p "$install_root/shared/output"
mkdir -p "$install_root/shared/config"

release_root="$install_root/releases/$expected_commit"
source_root="$release_root/source"
venv_root="$release_root/venv"
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

if [[ ! -x "$venv_root/bin/python" ]]; then
  python3 -m venv "$venv_root"
  "$venv_root/bin/python" -m pip install --upgrade pip setuptools wheel
fi

if ! "$venv_root/bin/python" -c 'import torch' >/dev/null 2>&1; then
  cat >&2 <<EOF
NEXT_ACTION PyTorch is not installed in the prepared release environment.
Verify the NVIDIA driver on the physical server, obtain the compatible command
from the official PyTorch installation selector, and install it with:
  $venv_root/bin/python -m pip install <verified-pytorch-build>
Then rerun this exact installer command. The prepared source and protected
shared directories will be reused without overwrite.
EOF
  exit 20
fi

"$venv_root/bin/python" -m pip install \
  -r "$source_root/deploy/worker/ubuntu/requirements-runtime.txt"

"$venv_root/bin/python" -c \
  'import av, cv2, numpy, requests, torch, ultralytics; print("PASS runtime_imports")'

if [[ ! -e "$install_root/shared/config/worker.env" ]] && \
   [[ ! -e "$install_root/shared/config/worker.env.example" ]]; then
  cp "$source_root/deploy/worker/ubuntu/worker.env.example" \
    "$install_root/shared/config/worker.env.example"
  chmod 600 "$install_root/shared/config/worker.env.example"
fi

printf 'PREPARED %s\n' "$release_root"
printf 'SOURCE_COMMIT %s\n' "$expected_commit"
printf 'PROTECTED %s\n' "$install_root/shared/config"
printf 'PROTECTED %s\n' "$install_root/shared/models"
printf 'PROTECTED %s\n' "$install_root/shared/datasets"
printf 'PROTECTED %s\n' "$install_root/shared/output"
printf 'UNKNOWN worker_runtime=server_not_commissioned\n'
