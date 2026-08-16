#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install-systemd.sh <40-character-source-commit> [install-root] [service-user]

Installs the Sea Speed water worker, isolated road worker, and independent
bounded worker-control units for one exact prepared source release and its
recorded immutable shared runtime. The road unit is enabled only when protected
road-worker.env already exists. The script never starts services or prints secrets.
EOF
}

source_commit="${1:-}"
install_root="${2:-/opt/sea-speed-worker}"
service_user="${3:-sea-speed}"
service_name="sea-speed-worker.service"
road_service_name="sea-speed-road-worker.service"
control_service_name="sea-speed-worker-control.service"
unit_target="/etc/systemd/system/$service_name"
road_unit_target="/etc/systemd/system/$road_service_name"
control_unit_target="/etc/systemd/system/$control_service_name"

if [[ "$EUID" -ne 0 ]]; then
  echo "ERROR run as root" >&2
  exit 1
fi
if [[ ! "$source_commit" =~ ^[0-9a-f]{40}$ ]]; then
  usage >&2
  echo "ERROR source commit must be a lowercase 40-character SHA" >&2
  exit 2
fi
if [[ ! "$service_user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "ERROR invalid service user" >&2
  exit 3
fi

release_root="$install_root/releases/$source_commit"
source_root="$release_root/source"
provenance="$release_root/source-commit"
runtime_id_file="$release_root/runtime-id"
env_file="$install_root/shared/config/worker.env"
road_env_file="$install_root/shared/config/road-worker.env"
runtime_state_root="$install_root/shared/runtime"
road_runtime_root="$install_root/shared/road-runtime"
road_output_root="$install_root/shared/road-output"
template="$source_root/deploy/worker/ubuntu/sea-speed-worker.service.template"
road_template="$source_root/deploy/worker/ubuntu/sea-speed-road-worker.service.template"
control_template="$source_root/deploy/worker/ubuntu/sea-speed-worker-control.service.template"
control_agent="$source_root/deploy/worker/ubuntu/worker-control-agent.py"

for required in \
  "$source_root/worker/hls_motion_yolo_worker_events.py" \
  "$provenance" \
  "$runtime_id_file" \
  "$template" \
  "$road_template" \
  "$source_root/worker/analytics_profiles.py" \
  "$control_template" \
  "$control_agent"; do
  if [[ ! -e "$required" ]]; then
    echo "ERROR prepared release component missing: $required" >&2
    exit 4
  fi
done
if [[ "$(cat "$provenance")" != "$source_commit" ]]; then
  echo "ERROR release provenance mismatch" >&2
  exit 5
fi

runtime_id="$(cat "$runtime_id_file")"
if [[ ! "$runtime_id" =~ ^[0-9a-f]{64}$ ]]; then
  echo "ERROR release runtime ID is invalid" >&2
  exit 5
fi
runtime_root="$install_root/runtimes/$runtime_id"
runtime_python="$runtime_root/venv/bin/python"
runtime_ready="$runtime_root/ready"
runtime_manifest="$runtime_root/runtime-manifest.json"
runtime_lock="$runtime_root/runtime-lock.json"
for required in "$runtime_python" "$runtime_ready" "$runtime_manifest" "$runtime_lock"; do
  if [[ ! -e "$required" ]]; then
    echo "ERROR prepared runtime component missing: $required" >&2
    exit 5
  fi
done
if [[ "$(cat "$runtime_ready")" != "runtime_id=$runtime_id" ]]; then
  echo "ERROR shared runtime ready marker mismatch" >&2
  exit 5
fi

if [[ ! -f "$env_file" ]]; then
  echo "ERROR protected environment file missing: $env_file" >&2
  echo "Create it from worker.env.example, populate it locally, and chmod 600." >&2
  exit 6
fi
if [[ "$(stat -c '%a' "$env_file")" != "600" ]]; then
  echo "ERROR environment file mode must be 600" >&2
  exit 7
fi

if ! id "$service_user" >/dev/null 2>&1; then
  useradd --system --home-dir "$install_root" --shell /usr/sbin/nologin "$service_user"
fi

mkdir -p "$runtime_state_root" "$road_runtime_root" "$road_output_root"
ln -sfn "$install_root/shared/models" "$runtime_state_root/models"
ln -sfn "$install_root/shared/output" "$runtime_state_root/output"
ln -sfn "$install_root/shared/datasets" "$runtime_state_root/datasets"
ln -sfn "$install_root/shared/models" "$road_runtime_root/models"
ln -sfn "$road_output_root" "$road_runtime_root/output"
ln -sfn "$install_root/shared/datasets" "$road_runtime_root/datasets"
chown -R "$service_user:$service_user" "$install_root/shared"
chmod 750 "$install_root/shared" "$install_root/shared/config" "$install_root/shared/models" "$install_root/shared/datasets" "$install_root/shared/output" "$runtime_state_root" "$road_runtime_root" "$road_output_root"
chmod 600 "$env_file"
if [[ -f "$road_env_file" ]]; then
  [[ "$(stat -c '%a' "$road_env_file")" == "600" ]] || { echo "ERROR road-worker.env must be mode 600" >&2; exit 7; }
fi

rendered="$(mktemp)"
road_rendered="$(mktemp)"
control_rendered="$(mktemp)"
trap 'rm -f "$rendered" "$road_rendered" "$control_rendered"' EXIT
sed \
  -e "s|__INSTALL_ROOT__|$install_root|g" \
  -e "s|__SOURCE_COMMIT__|$source_commit|g" \
  -e "s|__RUNTIME_ID__|$runtime_id|g" \
  -e "s|__SERVICE_USER__|$service_user|g" \
  "$template" > "$rendered"
sed \
  -e "s|__INSTALL_ROOT__|$install_root|g" \
  -e "s|__SOURCE_COMMIT__|$source_commit|g" \
  -e "s|__RUNTIME_ID__|$runtime_id|g" \
  -e "s|__SERVICE_USER__|$service_user|g" \
  "$road_template" > "$road_rendered"
sed \
  -e "s|__INSTALL_ROOT__|$install_root|g" \
  -e "s|__SOURCE_COMMIT__|$source_commit|g" \
  "$control_template" > "$control_rendered"

install -o root -g root -m 0644 "$rendered" "$unit_target"
install -o root -g root -m 0644 "$road_rendered" "$road_unit_target"
install -o root -g root -m 0644 "$control_rendered" "$control_unit_target"
systemd-analyze verify "$unit_target" "$road_unit_target" "$control_unit_target"
systemctl daemon-reload
systemctl enable "$service_name"
systemctl enable "$control_service_name"
if [[ -f "$road_env_file" ]]; then
  systemctl enable "$road_service_name"
else
  systemctl disable "$road_service_name" >/dev/null 2>&1 || true
fi

printf 'INSTALLED %s\n' "$unit_target"
printf 'INSTALLED %s\n' "$road_unit_target"
printf 'INSTALLED %s\n' "$control_unit_target"
printf 'SOURCE_COMMIT %s\n' "$source_commit"
printf 'RUNTIME_ID %s\n' "$runtime_id"
printf 'SERVICE_USER %s\n' "$service_user"
printf 'ENABLED %s\n' "$service_name"
printf 'ENABLED %s\n' "$control_service_name"
if [[ -f "$road_env_file" ]]; then
  printf 'ENABLED %s\n' "$road_service_name"
else
  printf 'ROAD_WORKER_CONFIG_PENDING %s\n' "$road_env_file"
fi
printf 'NOT_STARTED %s\n' "$service_name"
printf 'NOT_STARTED %s\n' "$road_service_name"
printf 'NOT_STARTED %s\n' "$control_service_name"
printf 'UNKNOWN worker_runtime=server_not_commissioned\n'
