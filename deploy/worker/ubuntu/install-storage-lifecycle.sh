#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install-storage-lifecycle.sh <40-character-source-commit> [install-root]

Installs and enables the exact-release storage audit timer. The timer performs
inventory only, is not started, and cannot delete storage automatically.
EOF
}

source_commit="${1:-}"
install_root="${2:-/opt/sea-speed-worker}"
service_name="sea-speed-worker.service"
audit_service="sea-speed-worker-storage-audit.service"
audit_timer="sea-speed-worker-storage-audit.timer"

if [[ "$EUID" -ne 0 ]]; then
  echo "ERROR run as root" >&2
  exit 1
fi
if [[ ! "$source_commit" =~ ^[0-9a-f]{40}$ ]]; then
  usage >&2
  echo "ERROR source commit must be a lowercase 40-character SHA" >&2
  exit 2
fi

release_root="$install_root/releases/$source_commit"
source_root="$release_root/source"
venv_python="$release_root/venv/bin/python"
provenance="$release_root/source-commit"
quality_marker="$release_root/quality-approved"
active_marker="$install_root/shared/runtime/active-source-commit"
worker_unit="/etc/systemd/system/$service_name"
manager="$source_root/deploy/worker/ubuntu/manage-storage.py"
service_template="$source_root/deploy/worker/ubuntu/sea-speed-worker-storage-audit.service.template"
timer_template="$source_root/deploy/worker/ubuntu/sea-speed-worker-storage-audit.timer.template"
service_target="/etc/systemd/system/$audit_service"
timer_target="/etc/systemd/system/$audit_timer"
storage_root="$install_root/storage"
pins_file="$storage_root/protected-releases"

for required in \
  "$source_root" \
  "$venv_python" \
  "$provenance" \
  "$quality_marker" \
  "$active_marker" \
  "$worker_unit" \
  "$manager" \
  "$service_template" \
  "$timer_template"; do
  if [[ ! -e "$required" ]]; then
    echo "ERROR storage lifecycle prerequisite missing: $required" >&2
    exit 3
  fi
done

if [[ "$(cat "$provenance")" != "$source_commit" ]] || \
   [[ "$(cat "$active_marker")" != "$source_commit" ]]; then
  echo "ERROR active release provenance mismatch" >&2
  exit 4
fi
expected_quality="$(printf 'source_commit=%s\nquality_check=quality-integration\n' "$source_commit")"
if [[ "$(cat "$quality_marker")" != "$expected_quality" ]] || \
   [[ "$(stat -c '%u' "$quality_marker")" != "0" ]] || \
   [[ "$(stat -c '%a' "$quality_marker")" != "644" ]]; then
  echo "ERROR exact release is not quality-approved" >&2
  exit 4
fi
if ! grep -Fq "$source_commit" "$worker_unit"; then
  echo "ERROR installed worker unit is not the requested exact release" >&2
  exit 5
fi

install -d -o root -g root -m 0700 "$storage_root"
if [[ ! -e "$pins_file" ]]; then
  printf '%s\n' "$source_commit" > "$pins_file"
  chown root:root "$pins_file"
  chmod 0600 "$pins_file"
fi
if [[ ! -f "$pins_file" ]] || \
   [[ "$(stat -c '%u' "$pins_file")" != "0" ]] || \
   [[ "$(stat -c '%a' "$pins_file")" != "600" ]]; then
  echo "ERROR protected releases file must be root-owned mode 600" >&2
  exit 6
fi
while IFS= read -r line || [[ -n "$line" ]]; do
  value="${line%%#*}"
  value="${value//[[:space:]]/}"
  [[ -z "$value" ]] && continue
  if [[ ! "$value" =~ ^[0-9a-f]{40}$ ]]; then
    echo "ERROR invalid SHA in protected releases file" >&2
    exit 6
  fi
done < "$pins_file"

rendered_service="$(mktemp)"
rendered_timer="$(mktemp)"
cleanup() {
  rm -f "$rendered_service" "$rendered_timer"
}
trap cleanup EXIT

sed \
  -e "s|__INSTALL_ROOT__|$install_root|g" \
  -e "s|__SOURCE_COMMIT__|$source_commit|g" \
  "$service_template" > "$rendered_service"
cp "$timer_template" "$rendered_timer"

install -o root -g root -m 0644 "$rendered_service" "$service_target"
install -o root -g root -m 0644 "$rendered_timer" "$timer_target"
systemd-analyze verify "$service_target" "$timer_target"
systemctl daemon-reload
systemctl enable "$audit_timer"

printf 'INSTALLED %s\n' "$service_target"
printf 'INSTALLED %s\n' "$timer_target"
printf 'SOURCE_COMMIT %s\n' "$source_commit"
printf 'PINS_FILE %s\n' "$pins_file"
printf 'ENABLED %s\n' "$audit_timer"
printf 'NOT_STARTED %s\n' "$audit_timer"
printf 'AUDIT_ONLY automatic_deletion=false\n'
printf 'UNKNOWN worker_runtime=server_not_commissioned\n'
