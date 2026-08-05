#!/usr/bin/env bash
set -euo pipefail

status=0

pass() {
  printf 'PASS %s\n' "$1"
}

fail() {
  printf 'FAIL %s\n' "$1" >&2
  status=1
}

unknown() {
  printf 'UNKNOWN %s\n' "$1"
}

if [[ "$(uname -s)" == "Linux" ]]; then
  pass "operating_system=linux"
else
  fail "operating_system=linux"
fi

if command -v python3 >/dev/null 2>&1; then
  python_version="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
  pass "python3=$python_version"
else
  fail "python3=missing"
fi

if command -v ffmpeg >/dev/null 2>&1; then
  ffmpeg_version="$(ffmpeg -version 2>/dev/null | sed -n '1s/^ffmpeg version \([^ ]*\).*/\1/p')"
  pass "ffmpeg=${ffmpeg_version:-present}"
else
  fail "ffmpeg=missing"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  gpu_name="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n 1 || true)"
  driver_version="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n 1 || true)"
  if [[ -n "$gpu_name" && -n "$driver_version" ]]; then
    pass "nvidia_gpu=$gpu_name"
    pass "nvidia_driver=$driver_version"
  else
    fail "nvidia_smi=query_failed"
  fi
else
  unknown "nvidia_smi=not_installed"
fi

for path in worker scripts deploy docs; do
  if [[ -e "$path" ]]; then
    pass "repository_path=$path"
  else
    fail "repository_path_missing=$path"
  fi
done

if [[ -f worker/hls_motion_yolo_worker_events.py ]]; then
  pass "worker_source=present"
else
  fail "worker_source=missing"
fi

if [[ -f .env ]]; then
  pass "local_env_file=present_not_read"
else
  unknown "local_env_file=not_created"
fi

if [[ -n "${HLS_URL:-}" ]]; then
  pass "environment_name=HLS_URL"
else
  unknown "environment_name=HLS_URL_not_set"
fi

if [[ -n "${SEA_SPEED_API_URL:-}" ]]; then
  pass "environment_name=SEA_SPEED_API_URL"
else
  unknown "environment_name=SEA_SPEED_API_URL_not_set"
fi

if [[ -n "${SEA_SPEED_API_TOKEN:-}" ]]; then
  pass "environment_name=SEA_SPEED_API_TOKEN"
else
  unknown "environment_name=SEA_SPEED_API_TOKEN_not_set"
fi

unknown "pytorch_cuda=requires_python_environment"
unknown "hls_connectivity=requires_local_credentials_and_network"
unknown "api_connectivity=requires_local_token_and_network"
unknown "worker_runtime=requires_installed_server"

exit "$status"
