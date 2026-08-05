#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: install-observability.sh <40-character-source-commit> [install-root]

Installs and enables exact-release local health units. The timer is not started.
The script never reads or prints worker environment contents.
USAGE
}

source_commit="${1:-}"
install_root="${2:-/opt/sea-speed-worker}"
service_name="sea-speed-worker.service"
health_service="sea-speed-worker-health.service"
health_timer="sea-speed-worker-health.timer"

if [[ "$EUID" -ne 0 ]]; then
  echo "ERROR run as root" >&2
  exit 1
fi
if [[ ! "$source_commit" =~ ^[0-9a-f]{40}$ ]]; then
  usage >&2
  echo "ERROR source commit must be a lowercase 40-character SHA" >&2
  exit 2
fi

source_root="$install_root/releases/$source_commit/source"
venv_python="$install_root/releases/$source_commit/venv/bin/python"
provenance="$install_root/releases/$source_commit/source-commit"
quality_marker="$install_root/releases/$source_commit/quality-approved"
active_marker="$install_root/shared/runtime/active-source-commit"
env_file="$install_root/shared/config/worker.env"
worker_unit="/etc/systemd/system/$service_name"
service_template="$source_root/deploy/worker/ubuntu/sea-speed-worker-health.service.template"
timer_template="$source_root/deploy/worker/ubuntu/sea-speed-worker-health.timer.template"
health_checker="$source_root/deploy/worker/ubuntu/check-worker-health.py"
observed_runner="$source_root/deploy/worker/ubuntu/observed-worker-runner.py"
service_target="/etc/systemd/system/$health_service"
timer_target="/etc/systemd/system/$health_timer"

for required in \
  "$source_root" \
  "$venv_python" \
  "$provenance" \
  "$quality_marker" \
  "$active_marker" \
  "$env_file" \
  "$worker_unit" \
  "$service_template" \
  "$timer_template" \
  "$health_checker" \
  "$observed_runner"; do
  if [[ ! -e "$required" ]]; then
    echo "ERROR observability prerequisite missing: $required" >&2
    exit 3
  fi
done

if [[ "$(cat "$provenance")" != "$source_commit" ]]; then
  echo "ERROR release provenance mismatch" >&2
  exit 4
fi
if [[ "$(cat "$active_marker")" != "$source_commit" ]]; then
  echo "ERROR active source commit does not match requested release" >&2
  exit 4
fi
expected_quality="$(printf 'source_commit=%s\nquality_check=quality-integration\n' "$source_commit")"
if [[ "$(cat "$quality_marker")" != "$expected_quality" ]]; then
  echo "ERROR exact release is not quality-approved" >&2
  exit 4
fi
if [[ "$(stat -c '%u' "$quality_marker")" != "0" ]] || \
   [[ "$(stat -c '%a' "$quality_marker")" != "644" ]]; then
  echo "ERROR quality-approved marker ownership or mode is invalid" >&2
  exit 4
fi
if [[ "$(stat -c '%a' "$env_file")" != "600" ]]; then
  echo "ERROR worker environment file mode must be 600" >&2
  exit 5
fi
if ! grep -Fq "$source_commit" "$worker_unit" || \
   ! grep -Fq "observed-worker-runner.py" "$worker_unit"; then
  echo "ERROR installed worker unit is not the requested observed exact release" >&2
  exit 6
fi

install -d -o root -g root -m 0755 "$install_root/observability"

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
systemctl enable "$health_timer"

printf 'INSTALLED %s\n' "$service_target"
printf 'INSTALLED %s\n' "$timer_target"
printf 'SOURCE_COMMIT %s\n' "$source_commit"
printf 'ENABLED %s\n' "$health_timer"
printf 'NOT_STARTED %s\n' "$health_timer"
printf 'REPORT_PATH %s\n' "$install_root/observability/worker-health-report.json"
printf 'UNKNOWN worker_runtime=server_not_commissioned\n'
