#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install-systemd.sh <40-character-source-commit> [install-root] [service-user]

Installs and enables the Sea Speed worker systemd unit for one exact prepared
release. The script never starts the service and never reads or prints secrets.
EOF
}

source_commit="${1:-}"
install_root="${2:-/opt/sea-speed-worker}"
service_user="${3:-sea-speed}"
service_name="sea-speed-worker.service"
unit_target="/etc/systemd/system/$service_name"

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

source_root="$install_root/releases/$source_commit/source"
venv_python="$install_root/releases/$source_commit/venv/bin/python"
provenance="$install_root/releases/$source_commit/source-commit"
env_file="$install_root/shared/config/worker.env"
runtime_root="$install_root/shared/runtime"
template="$source_root/deploy/worker/ubuntu/sea-speed-worker.service.template"

for required in "$source_root/worker/hls_motion_yolo_worker_events.py" "$venv_python" "$provenance" "$template"; do
  if [[ ! -e "$required" ]]; then
    echo "ERROR prepared release component missing: $required" >&2
    exit 4
  fi
done
if [[ "$(cat "$provenance")" != "$source_commit" ]]; then
  echo "ERROR release provenance mismatch" >&2
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

mkdir -p "$runtime_root"
ln -sfn "$install_root/shared/models" "$runtime_root/models"
ln -sfn "$install_root/shared/output" "$runtime_root/output"
ln -sfn "$install_root/shared/datasets" "$runtime_root/datasets"
chown -R "$service_user:$service_user" "$install_root/shared"
chmod 750 "$install_root/shared" "$install_root/shared/config" "$install_root/shared/models" "$install_root/shared/datasets" "$install_root/shared/output" "$runtime_root"
chmod 600 "$env_file"

rendered="$(mktemp)"
trap 'rm -f "$rendered"' EXIT
sed \
  -e "s|__INSTALL_ROOT__|$install_root|g" \
  -e "s|__SOURCE_COMMIT__|$source_commit|g" \
  -e "s|__SERVICE_USER__|$service_user|g" \
  "$template" > "$rendered"

install -o root -g root -m 0644 "$rendered" "$unit_target"
systemd-analyze verify "$unit_target"
systemctl daemon-reload
systemctl enable "$service_name"

printf 'INSTALLED %s\n' "$unit_target"
printf 'SOURCE_COMMIT %s\n' "$source_commit"
printf 'SERVICE_USER %s\n' "$service_user"
printf 'ENABLED %s\n' "$service_name"
printf 'NOT_STARTED %s\n' "$service_name"
printf 'UNKNOWN worker_runtime=server_not_commissioned\n'
