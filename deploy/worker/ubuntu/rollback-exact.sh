#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage: rollback-exact.sh <40-character-target-commit> [options]

Options:
  --install-root PATH       Worker installation root
                            (default: /opt/sea-speed-worker)
  --service-user USER       systemd service user (default: sea-speed)
  --expected-current SHA    Fail unless this exact commit is currently active

The target must already be prepared and quality-approved by update-exact.sh.
The rollback preserves the operator desired worker state (`running` or
`stopped`) while switching the exact worker source/runtime identity. Modern
targets restore the exact worker-control unit; legacy targets that predate the
control service restore its intentional absence.
EOF_USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then usage; exit 0; fi

target_commit="${1:-}"
[[ -n "$target_commit" ]] || { usage >&2; exit 2; }
shift

install_root="/opt/sea-speed-worker"
service_user="sea-speed"
expected_current=""
service_name="sea-speed-worker.service"
road_service_name="sea-speed-road-worker.service"
control_service_name="sea-speed-worker-control.service"
unit_target="/etc/systemd/system/$service_name"
road_unit_target="/etc/systemd/system/$road_service_name"
control_unit_target="/etc/systemd/system/$control_service_name"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root) [[ $# -ge 2 ]] || exit 2; install_root="$2"; shift 2 ;;
    --service-user) [[ $# -ge 2 ]] || exit 2; service_user="$2"; shift 2 ;;
    --expected-current) [[ $# -ge 2 ]] || exit 2; expected_current="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ "$EUID" -eq 0 ]] || { echo "ERROR run as root" >&2; exit 1; }
[[ "$target_commit" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR target commit must be a lowercase 40-character SHA" >&2; exit 2; }
if [[ -n "$expected_current" ]] && [[ ! "$expected_current" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR expected current commit must be a lowercase 40-character SHA" >&2; exit 2
fi
[[ "$service_user" =~ ^[a-z_][a-z0-9_-]*$ ]] || { echo "ERROR invalid service user" >&2; exit 3; }
for command_name in flock install stat systemctl grep mktemp mv; do
  command -v "$command_name" >/dev/null 2>&1 || { echo "ERROR required command missing: $command_name" >&2; exit 4; }
done

updater_root="$install_root/updater"
install -d -o root -g root -m 0700 "$updater_root"
exec 9>"$updater_root/update.lock"
chmod 0600 "$updater_root/update.lock"
flock -n 9 || { echo "ERROR another worker update or rollback is already running" >&2; exit 5; }

active_marker="$install_root/shared/runtime/active-source-commit"
desired_state_file="$install_root/shared/runtime/operator-desired-state"
env_file="$install_root/shared/config/worker.env"
road_env_file="$install_root/shared/config/road-worker.env"
[[ -f "$active_marker" ]] || { echo "ERROR active source marker is missing" >&2; exit 6; }
current_commit="$(cat "$active_marker")"
[[ "$current_commit" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR active source marker is invalid" >&2; exit 6; }
[[ -z "$expected_current" || "$current_commit" == "$expected_current" ]] || { echo "ERROR active source commit does not match --expected-current" >&2; exit 6; }
[[ "$current_commit" != "$target_commit" ]] || { echo "ERROR target commit is already active" >&2; exit 7; }
[[ -f "$unit_target" ]] || { echo "ERROR installed systemd unit is missing: $unit_target" >&2; exit 8; }
grep -Fq "$current_commit" "$unit_target" || { echo "ERROR installed unit and active source marker disagree" >&2; exit 8; }

desired_state="running"
if [[ -f "$desired_state_file" ]]; then desired_state="$(cat "$desired_state_file")"; fi
[[ "$desired_state" == "running" || "$desired_state" == "stopped" ]] || { echo "ERROR operator desired state is invalid" >&2; exit 8; }
if [[ "$desired_state" == "running" ]]; then
  systemctl is-active --quiet "$service_name" || { echo "ERROR desired running worker is not active" >&2; exit 8; }
else
  ! systemctl is-active --quiet "$service_name" || { echo "ERROR desired stopped worker is unexpectedly active" >&2; exit 8; }
fi
current_exec="$(systemctl show -p ExecStart --value "$service_name")"
[[ "$current_exec" == *"$current_commit"* ]] || { echo "ERROR worker unit and active source marker disagree" >&2; exit 8; }
current_runtime_id=""
current_runtime_file="$install_root/releases/$current_commit/runtime-id"
if [[ -f "$current_runtime_file" ]]; then
  current_runtime_id="$(cat "$current_runtime_file")"
  [[ "$current_runtime_id" =~ ^[0-9a-f]{64}$ ]] && [[ "$current_exec" == *"/runtimes/$current_runtime_id/venv/bin/python"* ]] || { echo "ERROR worker unit and active runtime binding disagree" >&2; exit 8; }
fi
[[ -f "$env_file" && "$(stat -c '%a' "$env_file")" == "600" ]] || { echo "ERROR protected worker environment file is missing or not mode 600" >&2; exit 9; }

current_road_present=false
current_road_enabled=false
current_road_active=false
if [[ -f "$road_unit_target" ]]; then
  current_road_present=true
  if systemctl is-enabled --quiet "$road_service_name"; then current_road_enabled=true; fi
  if systemctl is-active --quiet "$road_service_name"; then
    current_road_active=true
    current_road_exec="$(systemctl show -p ExecStart --value "$road_service_name")"
    [[ "$current_road_exec" == *"$current_commit"* ]] || { echo "ERROR running road worker and active source marker disagree" >&2; exit 8; }
  fi
elif systemctl is-active --quiet "$road_service_name" || systemctl is-enabled --quiet "$road_service_name"; then
  echo "ERROR road worker service state exists without an installed unit" >&2
  exit 8
fi

current_control_present=false
current_control_enabled=false
current_control_active=false
if [[ -f "$control_unit_target" ]]; then
  current_control_present=true
  grep -Fq "$current_commit" "$control_unit_target" || { echo "ERROR installed control unit and active source marker disagree" >&2; exit 8; }
  if systemctl is-enabled --quiet "$control_service_name"; then current_control_enabled=true; fi
  if systemctl is-active --quiet "$control_service_name"; then
    current_control_active=true
    current_control_exec="$(systemctl show -p ExecStart --value "$control_service_name")"
    [[ "$current_control_exec" == *"$current_commit"* ]] || { echo "ERROR running control service and active source marker disagree" >&2; exit 8; }
  fi
elif systemctl is-active --quiet "$control_service_name" || systemctl is-enabled --quiet "$control_service_name"; then
  echo "ERROR worker control service state exists without an installed control unit" >&2
  exit 8
fi

target_root="$install_root/releases/$target_commit"
target_source="$target_root/source"
target_provenance="$target_root/source-commit"
target_quality="$target_root/quality-approved"
target_worker="$target_source/worker/hls_motion_yolo_worker_events.py"
target_installer="$target_source/deploy/worker/ubuntu/install-systemd.sh"
target_runtime_file="$target_root/runtime-id"
target_road_template="$target_source/deploy/worker/ubuntu/sea-speed-road-worker.service.template"
target_control_template="$target_source/deploy/worker/ubuntu/sea-speed-worker-control.service.template"
target_control_agent="$target_source/deploy/worker/ubuntu/worker-control-agent.py"
for required in "$target_source" "$target_provenance" "$target_quality" "$target_worker" "$target_installer"; do
  [[ -e "$required" ]] || { echo "ERROR rollback target component missing: $required" >&2; exit 10; }
done
[[ "$(cat "$target_provenance")" == "$target_commit" ]] || { echo "ERROR rollback target provenance mismatch" >&2; exit 10; }
[[ "$(stat -c '%u' "$target_quality")" == "0" && "$(stat -c '%a' "$target_quality")" == "644" ]] || { echo "ERROR rollback target quality marker ownership or mode is invalid" >&2; exit 11; }
quality_content="$(cat "$target_quality")"
expected_quality="$(printf 'source_commit=%s\nquality_check=quality-integration\n' "$target_commit")"
[[ "$quality_content" == "$expected_quality" ]] || { echo "ERROR rollback target is not exact quality-approved" >&2; exit 11; }

target_has_control=false
if [[ -e "$target_control_template" || -e "$target_control_agent" ]]; then
  if [[ ! -f "$target_control_template" || ! -f "$target_control_agent" ]]; then
    echo "ERROR rollback target has incomplete worker-control components" >&2
    exit 10
  fi
  if ! grep -Fq "$control_service_name" "$target_installer"; then
    echo "ERROR rollback target installer does not manage its worker-control unit" >&2
    exit 10
  fi
  target_has_control=true
fi

target_has_road=false
if [[ -f "$target_road_template" ]]; then
  if ! grep -Fq "$road_service_name" "$target_installer"; then
    echo "ERROR rollback target installer does not manage its road worker unit" >&2
    exit 10
  fi
  target_has_road=true
fi

target_runtime_id=""
if [[ -f "$target_runtime_file" ]]; then
  target_runtime_id="$(cat "$target_runtime_file")"
  [[ "$target_runtime_id" =~ ^[0-9a-f]{64}$ ]] || { echo "ERROR rollback target runtime ID is invalid" >&2; exit 12; }
  target_runtime_root="$install_root/runtimes/$target_runtime_id"
  [[ -x "$target_runtime_root/venv/bin/python" && -f "$target_runtime_root/ready" && "$(cat "$target_runtime_root/ready")" == "runtime_id=$target_runtime_id" ]] || { echo "ERROR rollback target shared runtime is not ready" >&2; exit 12; }
else
  [[ -x "$target_root/venv/bin/python" ]] || { echo "ERROR rollback target legacy runtime is missing" >&2; exit 12; }
fi

unit_backup="$(mktemp "$updater_root/unit-backup.XXXXXX")"
road_unit_backup=""
control_unit_backup=""
marker_tmp=""
install -o root -g root -m 0600 "$unit_target" "$unit_backup"
if [[ "$current_road_present" == true ]]; then
  road_unit_backup="$(mktemp "$updater_root/road-unit-backup.XXXXXX")"
  install -o root -g root -m 0600 "$road_unit_target" "$road_unit_backup"
fi
if [[ "$current_control_present" == true ]]; then
  control_unit_backup="$(mktemp "$updater_root/control-unit-backup.XXXXXX")"
  install -o root -g root -m 0600 "$control_unit_target" "$control_unit_backup"
fi
cleanup() {
  rm -f "$unit_backup"
  if [[ -n "$road_unit_backup" ]]; then rm -f "$road_unit_backup"; fi
  if [[ -n "$control_unit_backup" ]]; then rm -f "$control_unit_backup"; fi
  if [[ -n "$marker_tmp" ]]; then rm -f "$marker_tmp"; fi
}
trap cleanup EXIT

apply_desired_state() {
  systemctl reset-failed "$service_name" || return 1
  if [[ "$desired_state" == "running" ]]; then
    systemctl restart "$service_name" || return 1
    systemctl is-active --quiet "$service_name" || return 1
  else
    systemctl stop "$service_name" || return 1
    ! systemctl is-active --quiet "$service_name" || return 1
  fi
}

restore_current_road() {
  if [[ "$current_road_present" == true ]]; then
    [[ -n "$road_unit_backup" ]] || return 1
    install -o root -g root -m 0644 "$road_unit_backup" "$road_unit_target" || return 1
    systemctl daemon-reload || return 1
    if [[ "$current_road_enabled" == true ]]; then systemctl enable "$road_service_name" >/dev/null || return 1; else systemctl disable "$road_service_name" >/dev/null || return 1; fi
    if [[ "$current_road_active" == true ]]; then
      systemctl restart "$road_service_name" || return 1
      systemctl is-active --quiet "$road_service_name" || return 1
      restored_road_exec="$(systemctl show -p ExecStart --value "$road_service_name")"
      [[ "$restored_road_exec" == *"$current_commit"* ]] || return 1
    else
      systemctl stop "$road_service_name" >/dev/null 2>&1 || true
      ! systemctl is-active --quiet "$road_service_name" || return 1
    fi
    return 0
  fi
  systemctl stop "$road_service_name" >/dev/null 2>&1 || true
  systemctl disable "$road_service_name" >/dev/null 2>&1 || true
  rm -f "$road_unit_target" || return 1
  systemctl daemon-reload || return 1
  return 0
}

restore_current_control() {
  if [[ "$current_control_present" == true ]]; then
    [[ -n "$control_unit_backup" ]] || return 1
    install -o root -g root -m 0644 "$control_unit_backup" "$control_unit_target" || return 1
    systemctl daemon-reload || return 1
    if [[ "$current_control_enabled" == true ]]; then
      systemctl enable "$control_service_name" >/dev/null || return 1
    else
      systemctl disable "$control_service_name" >/dev/null || return 1
    fi
    if [[ "$current_control_active" == true ]]; then
      systemctl restart "$control_service_name" || return 1
      systemctl is-active --quiet "$control_service_name" || return 1
      restored_control_exec="$(systemctl show -p ExecStart --value "$control_service_name")"
      [[ "$restored_control_exec" == *"$current_commit"* ]] || return 1
    else
      systemctl stop "$control_service_name" || return 1
      ! systemctl is-active --quiet "$control_service_name" || return 1
    fi
    return 0
  fi

  systemctl stop "$control_service_name" >/dev/null 2>&1 || true
  systemctl disable "$control_service_name" >/dev/null 2>&1 || true
  rm -f "$control_unit_target" || return 1
  systemctl daemon-reload || return 1
  [[ ! -e "$control_unit_target" ]] || return 1
  ! systemctl is-enabled --quiet "$control_service_name" || return 1
  ! systemctl is-active --quiet "$control_service_name" || return 1
  return 0
}

restore_previous() {
  echo "RESTORE previous_source_commit=$current_commit desired_state=$desired_state" >&2
  install -o root -g root -m 0644 "$unit_backup" "$unit_target" || return 1
  restore_current_road || return 1
  restore_current_control || return 1
  apply_desired_state || return 1
  restored_exec="$(systemctl show -p ExecStart --value "$service_name")"
  [[ "$restored_exec" == *"$current_commit"* ]] || return 1
  if [[ -n "$current_runtime_id" ]] && [[ "$restored_exec" != *"/runtimes/$current_runtime_id/venv/bin/python"* ]]; then return 1; fi
  return 0
}

remove_control_for_legacy_target() {
  systemctl stop "$control_service_name" >/dev/null 2>&1 || true
  systemctl disable "$control_service_name" >/dev/null 2>&1 || true
  rm -f "$control_unit_target" || return 1
  systemctl daemon-reload || return 1
  [[ ! -e "$control_unit_target" ]] || return 1
  ! systemctl is-enabled --quiet "$control_service_name" || return 1
  ! systemctl is-active --quiet "$control_service_name" || return 1
}

remove_road_for_legacy_target() {
  systemctl stop "$road_service_name" >/dev/null 2>&1 || true
  systemctl disable "$road_service_name" >/dev/null 2>&1 || true
  rm -f "$road_unit_target" || return 1
  systemctl daemon-reload || return 1
  return 0
}

activate_target() {
  (cd "$target_source" && bash deploy/worker/ubuntu/install-systemd.sh "$target_commit" "$install_root" "$service_user") || return 1
  if [[ "$target_has_control" == true ]]; then
    systemctl restart "$control_service_name" || return 1
    systemctl is-active --quiet "$control_service_name" || return 1
    control_exec="$(systemctl show -p ExecStart --value "$control_service_name")"
    [[ "$control_exec" == *"$target_commit"* ]] || return 1
  else
    remove_control_for_legacy_target || return 1
  fi
  if [[ "$target_has_road" == true ]]; then
    if [[ -f "$road_env_file" ]]; then
      [[ "$(stat -c '%a' "$road_env_file")" == "600" ]] || return 1
      systemctl restart "$road_service_name" || return 1
      systemctl is-active --quiet "$road_service_name" || return 1
      road_exec="$(systemctl show -p ExecStart --value "$road_service_name")"
      [[ "$road_exec" == *"$target_commit"* ]] || return 1
      if [[ -n "$target_runtime_id" ]] && [[ "$road_exec" != *"/runtimes/$target_runtime_id/venv/bin/python"* ]]; then return 1; fi
    else
      systemctl stop "$road_service_name" >/dev/null 2>&1 || true
    fi
  else
    remove_road_for_legacy_target || return 1
  fi
  apply_desired_state || return 1
  target_exec="$(systemctl show -p ExecStart --value "$service_name")"
  [[ "$target_exec" == *"$target_commit"* ]] || return 1
  if [[ -n "$target_runtime_id" ]] && [[ "$target_exec" != *"/runtimes/$target_runtime_id/venv/bin/python"* ]]; then return 1; fi
  return 0
}

if ! activate_target; then
  echo "ERROR rollback target activation failed" >&2
  if restore_previous; then
    printf 'ROLLBACK_ABORTED target=%s restored=%s\n' "$target_commit" "$current_commit" >&2
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

printf 'ROLLED_BACK from=%s to=%s desired_state=%s\n' "$current_commit" "$target_commit" "$desired_state"
printf 'TARGET_RUNTIME_ID %s\n' "${target_runtime_id:-legacy-per-release}"
if [[ "$target_has_control" == true ]]; then
  printf 'CONTROL_SERVICE_ACTIVE %s\n' "$control_service_name"
else
  printf 'CONTROL_SERVICE_ABSENT %s\n' "$control_service_name"
fi
if [[ "$target_has_road" == true && -f "$road_env_file" ]]; then
  printf 'ROAD_SERVICE_ACTIVE %s\n' "$road_service_name"
elif [[ "$target_has_road" == true ]]; then
  printf 'ROAD_SERVICE_PENDING %s\n' "$road_env_file"
else
  printf 'ROAD_SERVICE_ABSENT %s\n' "$road_service_name"
fi
if [[ "$desired_state" == "running" ]]; then printf 'SERVICE_ACTIVE %s\n' "$service_name"; else printf 'SERVICE_STOPPED %s\n' "$service_name"; fi
printf 'ACTIVE_SOURCE_COMMIT %s\n' "$target_commit"
printf 'PRESERVED shared_config_models_datasets_output_releases_runtimes=true\n'
