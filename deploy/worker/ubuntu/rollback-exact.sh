#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: rollback-exact.sh <40-character-target-commit> [options]

Options:
  --install-root PATH       Worker installation root
                            (default: /opt/sea-speed-worker)
  --service-user USER       systemd service user (default: sea-speed)
  --expected-current SHA    Fail unless this exact commit is currently active

The target must already be prepared and quality-approved by update-exact.sh.
New-format releases bind an exact source SHA to an immutable runtime ID. Legacy
per-release venv targets remain supported during migration. Shared state and all
release/runtime directories are preserved.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

target_commit="${1:-}"
if [[ -z "$target_commit" ]]; then
  usage >&2
  exit 2
fi
shift

install_root="/opt/sea-speed-worker"
service_user="sea-speed"
expected_current=""
service_name="sea-speed-worker.service"
unit_target="/etc/systemd/system/$service_name"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root)
      [[ $# -ge 2 ]] || { echo "ERROR --install-root requires a path" >&2; exit 2; }
      install_root="$2"
      shift 2
      ;;
    --service-user)
      [[ $# -ge 2 ]] || { echo "ERROR --service-user requires a name" >&2; exit 2; }
      service_user="$2"
      shift 2
      ;;
    --expected-current)
      [[ $# -ge 2 ]] || { echo "ERROR --expected-current requires a SHA" >&2; exit 2; }
      expected_current="$2"
      shift 2
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

if [[ "$EUID" -ne 0 ]]; then
  echo "ERROR run as root" >&2
  exit 1
fi
if [[ ! "$target_commit" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR target commit must be a lowercase 40-character SHA" >&2
  exit 2
fi
if [[ -n "$expected_current" ]] && \
   [[ ! "$expected_current" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR expected current commit must be a lowercase 40-character SHA" >&2
  exit 2
fi
if [[ ! "$service_user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "ERROR invalid service user" >&2
  exit 3
fi

for command_name in flock install stat systemctl grep mktemp mv; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "ERROR required command missing: $command_name" >&2
    exit 4
  fi
done

updater_root="$install_root/updater"
install -d -o root -g root -m 0700 "$updater_root"
exec 9>"$updater_root/update.lock"
chmod 0600 "$updater_root/update.lock"
if ! flock -n 9; then
  echo "ERROR another worker update or rollback is already running" >&2
  exit 5
fi

active_marker="$install_root/shared/runtime/active-source-commit"
env_file="$install_root/shared/config/worker.env"
if [[ ! -f "$active_marker" ]]; then
  echo "ERROR active source marker is missing" >&2
  exit 6
fi
current_commit="$(cat "$active_marker")"
if [[ ! "$current_commit" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR active source marker is invalid" >&2
  exit 6
fi
if [[ -n "$expected_current" && "$current_commit" != "$expected_current" ]]; then
  echo "ERROR active source commit does not match --expected-current" >&2
  exit 6
fi
if [[ "$current_commit" == "$target_commit" ]]; then
  echo "ERROR target commit is already active" >&2
  exit 7
fi
if [[ ! -f "$unit_target" ]]; then
  echo "ERROR installed systemd unit is missing: $unit_target" >&2
  exit 8
fi
if ! grep -Fq "$current_commit" "$unit_target"; then
  echo "ERROR installed unit and active source marker disagree" >&2
  exit 8
fi
if ! systemctl is-active --quiet "$service_name"; then
  echo "ERROR current worker service is not active" >&2
  exit 8
fi
current_exec="$(systemctl show -p ExecStart --value "$service_name")"
if [[ "$current_exec" != *"$current_commit"* ]]; then
  echo "ERROR running service and active source marker disagree" >&2
  exit 8
fi
current_runtime_id=""
current_runtime_file="$install_root/releases/$current_commit/runtime-id"
if [[ -f "$current_runtime_file" ]]; then
  current_runtime_id="$(cat "$current_runtime_file")"
  if [[ ! "$current_runtime_id" =~ ^[0-9a-f]{64}$ ]] || \
     [[ "$current_exec" != *"/runtimes/$current_runtime_id/venv/bin/python"* ]]; then
    echo "ERROR running service and active runtime binding disagree" >&2
    exit 8
  fi
fi
if [[ ! -f "$env_file" ]] || [[ "$(stat -c '%a' "$env_file")" != "600" ]]; then
  echo "ERROR protected worker environment file is missing or not mode 600" >&2
  exit 9
fi

target_root="$install_root/releases/$target_commit"
target_source="$target_root/source"
target_provenance="$target_root/source-commit"
target_quality="$target_root/quality-approved"
target_worker="$target_source/worker/hls_motion_yolo_worker_events.py"
target_installer="$target_source/deploy/worker/ubuntu/install-systemd.sh"
target_runtime_file="$target_root/runtime-id"
target_runtime_id=""
target_python=""

for required in \
  "$target_source" \
  "$target_provenance" \
  "$target_quality" \
  "$target_worker" \
  "$target_installer"; do
  if [[ ! -e "$required" ]]; then
    echo "ERROR rollback target component missing: $required" >&2
    exit 10
  fi
done
if [[ "$(cat "$target_provenance")" != "$target_commit" ]]; then
  echo "ERROR rollback target provenance mismatch" >&2
  exit 10
fi
if [[ "$(stat -c '%u' "$target_quality")" != "0" ]] || \
   [[ "$(stat -c '%a' "$target_quality")" != "644" ]]; then
  echo "ERROR rollback target quality marker ownership or mode is invalid" >&2
  exit 11
fi
quality_content="$(cat "$target_quality")"
expected_quality="$(printf 'source_commit=%s\nquality_check=quality-integration\n' "$target_commit")"
if [[ "$quality_content" != "$expected_quality" ]]; then
  echo "ERROR rollback target is not exact quality-approved" >&2
  exit 11
fi

if [[ -f "$target_runtime_file" ]]; then
  target_runtime_id="$(cat "$target_runtime_file")"
  if [[ ! "$target_runtime_id" =~ ^[0-9a-f]{64}$ ]]; then
    echo "ERROR rollback target runtime ID is invalid" >&2
    exit 12
  fi
  target_runtime_root="$install_root/runtimes/$target_runtime_id"
  target_python="$target_runtime_root/venv/bin/python"
  if [[ ! -x "$target_python" ]] || \
     [[ ! -f "$target_runtime_root/ready" ]] || \
     [[ "$(cat "$target_runtime_root/ready")" != "runtime_id=$target_runtime_id" ]]; then
    echo "ERROR rollback target shared runtime is not ready" >&2
    exit 12
  fi
else
  target_python="$target_root/venv/bin/python"
  if [[ ! -x "$target_python" ]]; then
    echo "ERROR rollback target legacy runtime is missing" >&2
    exit 12
  fi
fi

unit_backup="$(mktemp "$updater_root/unit-backup.XXXXXX")"
marker_tmp=""
cleanup() {
  rm -f "$unit_backup"
  if [[ -n "$marker_tmp" ]]; then
    rm -f "$marker_tmp"
  fi
}
trap cleanup EXIT
install -o root -g root -m 0600 "$unit_target" "$unit_backup"

restore_previous() {
  echo "RESTORE previous_source_commit=$current_commit" >&2
  install -o root -g root -m 0644 "$unit_backup" "$unit_target"
  systemctl daemon-reload
  if ! systemctl reset-failed "$service_name"; then
    return 1
  fi
  if ! systemctl restart "$service_name"; then
    return 1
  fi
  if ! systemctl is-active --quiet "$service_name"; then
    return 1
  fi
  restored_exec="$(systemctl show -p ExecStart --value "$service_name")"
  if [[ "$restored_exec" != *"$current_commit"* ]]; then
    return 1
  fi
  if [[ -n "$current_runtime_id" ]] && \
     [[ "$restored_exec" != *"/runtimes/$current_runtime_id/venv/bin/python"* ]]; then
    return 1
  fi
  return 0
}

activate_target() {
  if ! (
    cd "$target_source"
    bash deploy/worker/ubuntu/install-systemd.sh \
      "$target_commit" \
      "$install_root" \
      "$service_user"
  ); then
    return 1
  fi
  if ! systemctl reset-failed "$service_name"; then
    return 1
  fi
  if ! systemctl restart "$service_name"; then
    return 1
  fi
  if ! systemctl is-active --quiet "$service_name"; then
    return 1
  fi
  target_exec="$(systemctl show -p ExecStart --value "$service_name")"
  if [[ "$target_exec" != *"$target_commit"* ]]; then
    return 1
  fi
  if [[ -n "$target_runtime_id" ]] && \
     [[ "$target_exec" != *"/runtimes/$target_runtime_id/venv/bin/python"* ]]; then
    return 1
  fi
  return 0
}

if ! activate_target; then
  echo "ERROR rollback target activation failed" >&2
  if restore_previous; then
    printf 'ROLLBACK_ABORTED target=%s restored=%s\n' \
      "$target_commit" "$current_commit" >&2
    exit 30
  fi
  echo "CRITICAL previous service restoration failed" >&2
  echo "CURRENT_MARKER_UNCHANGED source_commit=$current_commit" >&2
  exit 31
fi

marker_tmp="$(mktemp "$updater_root/active-marker.XXXXXX")"
printf '%s\n' "$target_commit" > "$marker_tmp"
chown "$service_user:$service_user" "$marker_tmp"
chmod 0644 "$marker_tmp"
mv -f "$marker_tmp" "$active_marker"
marker_tmp=""

printf 'ROLLED_BACK from=%s to=%s\n' "$current_commit" "$target_commit"
printf 'TARGET_RUNTIME_ID %s\n' "${target_runtime_id:-legacy-per-release}"
printf 'SERVICE_ACTIVE %s\n' "$service_name"
printf 'ACTIVE_SOURCE_COMMIT %s\n' "$target_commit"
printf 'PRESERVED shared_config_models_datasets_output_releases_runtimes=true\n'
