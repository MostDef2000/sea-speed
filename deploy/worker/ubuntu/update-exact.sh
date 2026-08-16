#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: update-exact.sh <40-character-source-commit> [options]

Options:
  --install-root PATH   Worker installation root (default: /opt/sea-speed-worker)
  --service-user USER   systemd service user (default: sea-speed)
  --token-file PATH     Protected GitHub read token file
                        (default: /etc/sea-speed/github-read-token)
  --activate            Install and activate the exact release

Without --activate, the updater verifies and prepares the exact source release
and its immutable shared runtime. With --activate, desired state `running`
requires exact-SHA frame/state progression. Desired state `stopped` installs the
exact worker/control units while keeping the AI worker intentionally inactive.
Any activation failure restores the previous exact units and desired service
state, including the absence of a legacy control unit, before returning.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

source_commit="${1:-}"
if [[ -z "$source_commit" ]]; then
  usage >&2
  exit 2
fi
shift

install_root="/opt/sea-speed-worker"
service_user="sea-speed"
token_file="/etc/sea-speed/github-read-token"
activate=false
repository="MostDef2000/sea-speed"
repository_url="https://github.com/MostDef2000/sea-speed.git"
service_name="sea-speed-worker.service"
road_service_name="sea-speed-road-worker.service"
control_service_name="sea-speed-worker-control.service"

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
    --token-file)
      [[ $# -ge 2 ]] || { echo "ERROR --token-file requires a path" >&2; exit 2; }
      token_file="$2"
      shift 2
      ;;
    --activate)
      activate=true
      shift
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
if [[ ! "$source_commit" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR source commit must be a lowercase 40-character SHA" >&2
  exit 2
fi
if [[ ! "$service_user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "ERROR invalid service user" >&2
  exit 3
fi

for command_name in git python3 ffmpeg tar flock stat install grep mktemp mv; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "ERROR required command missing: $command_name" >&2
    exit 4
  fi
done
if [[ "$activate" == true ]] && ! command -v systemctl >/dev/null 2>&1; then
  echo "ERROR required command missing: systemctl" >&2
  exit 4
fi

if [[ ! -f "$token_file" ]]; then
  echo "ERROR protected GitHub token file missing: $token_file" >&2
  exit 5
fi
if [[ "$(stat -c '%a' "$token_file")" != "600" ]]; then
  echo "ERROR GitHub token file mode must be 600" >&2
  exit 5
fi
if [[ "$(stat -c '%u' "$token_file")" != "0" ]]; then
  echo "ERROR GitHub token file must be owned by root" >&2
  exit 5
fi

updater_root="$install_root/updater"
install -d -o root -g root -m 0700 "$updater_root"
exec 9>"$updater_root/update.lock"
chmod 0600 "$updater_root/update.lock"
if ! flock -n 9; then
  echo "ERROR another worker update or rollback is already running" >&2
  exit 6
fi

staging_root="$(mktemp -d "$updater_root/staging.XXXXXX")"
chmod 0700 "$staging_root"
unit_backup=""
road_unit_backup=""
control_unit_backup=""
marker_tmp=""
cleanup() {
  local status=$?
  rm -rf "$staging_root" || true
  if [[ -n "$unit_backup" ]]; then
    rm -f "$unit_backup" || true
  fi
  if [[ -n "$road_unit_backup" ]]; then
    rm -f "$road_unit_backup" || true
  fi
  if [[ -n "$control_unit_backup" ]]; then
    rm -f "$control_unit_backup" || true
  fi
  if [[ -n "$marker_tmp" ]]; then
    rm -f "$marker_tmp" || true
  fi
  return "$status"
}
trap cleanup EXIT

git -C "$staging_root" init -q
git -C "$staging_root" remote add origin "$repository_url"
git -C "$staging_root" fetch --quiet --no-tags origin main:refs/remotes/origin/main

if ! git -C "$staging_root" cat-file -e "$source_commit^{commit}" 2>/dev/null; then
  echo "ERROR source commit is not present in origin/main history" >&2
  exit 7
fi
if ! git -C "$staging_root" merge-base --is-ancestor "$source_commit" refs/remotes/origin/main; then
  echo "ERROR source commit is not reachable from origin/main" >&2
  exit 7
fi

git -C "$staging_root" -c advice.detachedHead=false checkout --quiet --detach "$source_commit"
actual_commit="$(git -C "$staging_root" rev-parse HEAD)"
if [[ "$actual_commit" != "$source_commit" ]]; then
  echo "ERROR staged checkout commit mismatch" >&2
  exit 8
fi

IFS= read -r github_token < "$token_file" || true
if [[ -z "${github_token:-}" ]]; then
  echo "ERROR GitHub token file is empty" >&2
  exit 5
fi
GITHUB_TOKEN="$github_token" python3 \
  "$staging_root/scripts/quality/verify_quality_status.py" \
  --repository "$repository" \
  --commit "$source_commit" \
  --workflow-file quality-integration.yml
unset github_token

(
  cd "$staging_root"
  bash deploy/worker/ubuntu/install-manual.sh "$source_commit" "$install_root"
)

release_root="$install_root/releases/$source_commit"
runtime_id_file="$release_root/runtime-id"
if [[ ! -f "$release_root/source-commit" ]] || \
   [[ "$(cat "$release_root/source-commit")" != "$source_commit" ]] || \
   [[ ! -f "$runtime_id_file" ]]; then
  echo "ERROR prepared release verification failed" >&2
  exit 9
fi
runtime_id="$(cat "$runtime_id_file")"
if [[ ! "$runtime_id" =~ ^[0-9a-f]{64}$ ]]; then
  echo "ERROR prepared release runtime ID is invalid" >&2
  exit 9
fi
runtime_root="$install_root/runtimes/$runtime_id"
if [[ ! -x "$runtime_root/venv/bin/python" ]] || \
   [[ ! -f "$runtime_root/ready" ]] || \
   [[ "$(cat "$runtime_root/ready")" != "runtime_id=$runtime_id" ]]; then
  echo "ERROR prepared shared runtime verification failed" >&2
  exit 9
fi

quality_marker="$release_root/quality-approved"
printf 'source_commit=%s\nquality_check=quality-integration\n' "$source_commit" > "$quality_marker"
chown root:root "$quality_marker"
chmod 0644 "$quality_marker"

printf 'PREPARED source_commit=%s\n' "$source_commit"
printf 'RUNTIME_BOUND source_commit=%s runtime_id=%s\n' "$source_commit" "$runtime_id"
printf 'QUALITY_APPROVED source_commit=%s check=quality-integration\n' "$source_commit"
printf 'PRESERVED shared_config_models_datasets_output=true\n'

if [[ "$activate" != true ]]; then
  printf 'NOT_ACTIVATED explicit_flag_required=--activate\n'
  printf 'UNKNOWN worker_runtime=server_not_commissioned\n'
  exit 0
fi

unit_target="/etc/systemd/system/$service_name"
road_unit_target="/etc/systemd/system/$road_service_name"
control_unit_target="/etc/systemd/system/$control_service_name"
active_marker="$install_root/shared/runtime/active-source-commit"
heartbeat="$install_root/shared/runtime/worker-heartbeat.json"
road_heartbeat="$install_root/shared/road-runtime/road-worker-heartbeat.json"
road_env_file="$install_root/shared/config/road-worker.env"
desired_state_file="$install_root/shared/runtime/operator-desired-state"
target_control_template="$release_root/source/deploy/worker/ubuntu/sea-speed-worker-control.service.template"
target_control_agent="$release_root/source/deploy/worker/ubuntu/worker-control-agent.py"
if [[ ! -f "$target_control_template" || ! -f "$target_control_agent" ]]; then
  echo "ERROR activation target lacks complete worker-control components; use rollback-exact.sh for a legacy target" >&2
  exit 20
fi

desired_state="running"
if [[ -f "$desired_state_file" ]]; then
  desired_state="$(cat "$desired_state_file")"
  if [[ "$desired_state" != "running" && "$desired_state" != "stopped" ]]; then
    echo "ERROR operator desired state is invalid" >&2
    exit 20
  fi
fi
previous_commit=""
previous_runtime_id=""
previous_runtime_ready=false
previous_control_present=false
previous_control_enabled=false
previous_control_active=false
previous_road_present=false
previous_road_enabled=false
previous_road_active=false

if [[ -f "$active_marker" ]]; then
  previous_commit="$(cat "$active_marker")"
  if [[ ! "$previous_commit" =~ ^[0-9a-f]{40}$ ]]; then
    echo "ERROR current active source marker is invalid" >&2
    exit 20
  fi
  if [[ ! -f "$unit_target" ]] || ! grep -Fq "$previous_commit" "$unit_target"; then
    echo "ERROR current unit and active source marker disagree" >&2
    exit 20
  fi
  if [[ "$desired_state" == "running" ]]; then
    if ! systemctl is-active --quiet "$service_name"; then
      echo "ERROR desired running worker is not active before activation" >&2
      exit 20
    fi
  elif systemctl is-active --quiet "$service_name"; then
    echo "ERROR desired stopped worker is unexpectedly active before activation" >&2
    exit 20
  fi
  previous_exec="$(systemctl show -p ExecStart --value "$service_name")"
  if [[ "$previous_exec" != *"$previous_commit"* ]]; then
    echo "ERROR installed worker unit and active source marker disagree" >&2
    exit 20
  fi
  previous_runtime_file="$install_root/releases/$previous_commit/runtime-id"
  if [[ -f "$previous_runtime_file" ]]; then
    previous_runtime_id="$(cat "$previous_runtime_file")"
    if [[ ! "$previous_runtime_id" =~ ^[0-9a-f]{64}$ ]] || \
       [[ "$previous_exec" != *"/runtimes/$previous_runtime_id/venv/bin/python"* ]]; then
      echo "ERROR worker unit and active runtime binding disagree" >&2
      exit 20
    fi
  fi

  unit_backup="$(mktemp "$updater_root/unit-backup.XXXXXX")"
  install -o root -g root -m 0600 "$unit_target" "$unit_backup"
  if [[ -f "$road_unit_target" ]]; then
    previous_road_present=true
    if systemctl is-enabled --quiet "$road_service_name"; then previous_road_enabled=true; fi
    if systemctl is-active --quiet "$road_service_name"; then
      previous_road_active=true
      previous_road_exec="$(systemctl show -p ExecStart --value "$road_service_name")"
      [[ "$previous_road_exec" == *"$previous_commit"* ]] || { echo "ERROR running road worker and active source marker disagree" >&2; exit 20; }
    fi
    road_unit_backup="$(mktemp "$updater_root/road-unit-backup.XXXXXX")"
    install -o root -g root -m 0600 "$road_unit_target" "$road_unit_backup"
  elif systemctl is-active --quiet "$road_service_name" || systemctl is-enabled --quiet "$road_service_name"; then
    echo "ERROR road worker service state exists without an installed unit" >&2
    exit 20
  fi
  if [[ -f "$control_unit_target" ]]; then
    previous_control_present=true
    if ! grep -Fq "$previous_commit" "$control_unit_target"; then
      echo "ERROR installed control unit and active source marker disagree" >&2
      exit 20
    fi
    if systemctl is-enabled --quiet "$control_service_name"; then
      previous_control_enabled=true
    fi
    if systemctl is-active --quiet "$control_service_name"; then
      previous_control_active=true
      previous_control_exec="$(systemctl show -p ExecStart --value "$control_service_name")"
      if [[ "$previous_control_exec" != *"$previous_commit"* ]]; then
        echo "ERROR running control service and active source marker disagree" >&2
        exit 20
      fi
    fi
    control_unit_backup="$(mktemp "$updater_root/control-unit-backup.XXXXXX")"
    install -o root -g root -m 0600 "$control_unit_target" "$control_unit_backup"
  elif systemctl is-active --quiet "$control_service_name" || systemctl is-enabled --quiet "$control_service_name"; then
    echo "ERROR worker control service state exists without an installed control unit" >&2
    exit 20
  fi
  previous_runtime_ready=true
fi

restore_previous_road() {
  if [[ "$previous_road_present" == true ]]; then
    [[ -n "$road_unit_backup" ]] || return 1
    install -o root -g root -m 0644 "$road_unit_backup" "$road_unit_target" || return 1
    systemctl daemon-reload || return 1
    if [[ "$previous_road_enabled" == true ]]; then
      systemctl enable "$road_service_name" >/dev/null || return 1
    else
      systemctl disable "$road_service_name" >/dev/null || return 1
    fi
    if [[ "$previous_road_active" == true ]]; then
      rm -f "$road_heartbeat"
      systemctl restart "$road_service_name" || return 1
      systemctl is-active --quiet "$road_service_name" || return 1
      restored_road_exec="$(systemctl show -p ExecStart --value "$road_service_name")"
      [[ "$restored_road_exec" == *"$previous_commit"* ]] || return 1
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

restore_previous_control() {
  if [[ "$previous_control_present" == true ]]; then
    [[ -n "$control_unit_backup" ]] || return 1
    install -o root -g root -m 0644 "$control_unit_backup" "$control_unit_target" || return 1
    systemctl daemon-reload || return 1
    if [[ "$previous_control_enabled" == true ]]; then
      systemctl enable "$control_service_name" >/dev/null || return 1
    else
      systemctl disable "$control_service_name" >/dev/null || return 1
    fi
    if [[ "$previous_control_active" == true ]]; then
      systemctl restart "$control_service_name" || return 1
      systemctl is-active --quiet "$control_service_name" || return 1
      restored_control_exec="$(systemctl show -p ExecStart --value "$control_service_name")"
      [[ "$restored_control_exec" == *"$previous_commit"* ]] || return 1
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
  if [[ "$previous_runtime_ready" != true ]] || [[ -z "$unit_backup" ]]; then
    return 1
  fi

  echo "RESTORE previous_source_commit=$previous_commit desired_state=$desired_state" >&2
  install -o root -g root -m 0644 "$unit_backup" "$unit_target" || return 1
  restore_previous_road || return 1
  restore_previous_control || return 1
  rm -f "$heartbeat"
  systemctl reset-failed "$service_name" || return 1
  if [[ "$desired_state" == "running" ]]; then
    systemctl restart "$service_name" || return 1
    systemctl is-active --quiet "$service_name" || return 1
  else
    systemctl stop "$service_name" || return 1
    ! systemctl is-active --quiet "$service_name" || return 1
  fi
  restored_exec="$(systemctl show -p ExecStart --value "$service_name")"
  [[ "$restored_exec" == *"$previous_commit"* ]] || return 1
  if [[ -n "$previous_runtime_id" ]] && [[ "$restored_exec" != *"/runtimes/$previous_runtime_id/venv/bin/python"* ]]; then
    return 1
  fi
  [[ "$(cat "$active_marker")" == "$previous_commit" ]] || return 1

  printf 'RESTORED previous_source_commit=%s runtime_id=%s desired_state=%s control_present=%s road_present=%s\n' \
    "$previous_commit" "${previous_runtime_id:-legacy-per-release}" "$desired_state" "$previous_control_present" "$previous_road_present"
  return 0
}

abort_activation() {
  local reason="$1"
  echo "ERROR activation failed: $reason" >&2
  if restore_previous; then
    printf 'ACTIVATION_ABORTED target=%s restored=%s\n' "$source_commit" "$previous_commit" >&2
    exit 30
  fi
  echo "CRITICAL activation failed and no previous release could be restored" >&2
  printf 'ACTIVE_MARKER_UNCHANGED source_commit=%s\n' "${previous_commit:-NONE}" >&2
  exit 31
}

if ! (
  cd "$staging_root"
  bash deploy/worker/ubuntu/install-systemd.sh "$source_commit" "$install_root" "$service_user"
); then
  abort_activation "unit installation failed"
fi

if ! systemctl restart "$control_service_name"; then
  abort_activation "worker control service restart failed"
fi
if ! systemctl is-active --quiet "$control_service_name"; then
  abort_activation "worker control service is not active"
fi

road_configured=false
if [[ -f "$road_env_file" ]]; then
  [[ "$(stat -c '%a' "$road_env_file")" == "600" ]] || abort_activation "road-worker.env must be mode 600"
  road_configured=true
  rm -f "$road_heartbeat"
  systemctl reset-failed "$road_service_name" || abort_activation "failed to clear road worker start limit"
  systemctl restart "$road_service_name" || abort_activation "road worker restart failed"
  systemctl is-active --quiet "$road_service_name" || abort_activation "road worker is not active"
  road_exec="$(systemctl show -p ExecStart --value "$road_service_name")"
  [[ "$road_exec" == *"$source_commit"* ]] || abort_activation "road worker unit does not reference requested commit"
  [[ "$road_exec" == *"/runtimes/$runtime_id/venv/bin/python"* ]] || abort_activation "road worker unit does not reference requested runtime ID"
else
  systemctl stop "$road_service_name" >/dev/null 2>&1 || true
fi

rm -f "$heartbeat"
systemctl reset-failed "$service_name" || abort_activation "failed to clear systemd start limit"

if [[ "$desired_state" == "stopped" ]]; then
  systemctl stop "$service_name" || abort_activation "failed to preserve desired stopped state"
  if systemctl is-active --quiet "$service_name"; then
    abort_activation "worker remained active despite desired stopped state"
  fi
else
  if ! systemctl restart "$service_name"; then
    abort_activation "service restart failed"
  fi
  if ! systemctl is-active --quiet "$service_name"; then
    abort_activation "service is not active"
  fi
fi

exec_start="$(systemctl show -p ExecStart --value "$service_name")"
if [[ "$exec_start" != *"$source_commit"* ]]; then
  abort_activation "worker unit does not reference requested commit"
fi
if [[ "$exec_start" != *"/runtimes/$runtime_id/venv/bin/python"* ]]; then
  abort_activation "worker unit does not reference requested runtime ID"
fi
control_exec="$(systemctl show -p ExecStart --value "$control_service_name")"
if [[ "$control_exec" != *"$source_commit"* ]]; then
  abort_activation "control unit does not reference requested commit"
fi

runtime_gate="$release_root/source/deploy/worker/ubuntu/verify-runtime-progression.py"
if [[ ! -f "$runtime_gate" ]]; then
  abort_activation "runtime progression verifier is missing"
fi
if [[ "$desired_state" == "running" ]]; then
  if ! python3 "$runtime_gate" \
    --heartbeat "$heartbeat" \
    --expected-commit "$source_commit" \
    --timeout-sec 90 \
    --poll-sec 1; then
    abort_activation "frame/state progression gate failed"
  fi
fi
if [[ "$road_configured" == true ]]; then
  if ! python3 "$runtime_gate" \
    --heartbeat "$road_heartbeat" \
    --expected-commit "$source_commit" \
    --timeout-sec 90 \
    --poll-sec 1; then
    abort_activation "road frame/state progression gate failed"
  fi
fi

marker_tmp="$(mktemp "$updater_root/active-marker.XXXXXX")"
printf '%s\n' "$source_commit" > "$marker_tmp"
chown "$service_user:$service_user" "$marker_tmp"
chmod 0644 "$marker_tmp"
mv -f "$marker_tmp" "$active_marker"
marker_tmp=""

printf 'ACTIVATED source_commit=%s runtime_id=%s desired_state=%s\n' "$source_commit" "$runtime_id" "$desired_state"
printf 'CONTROL_SERVICE_ACTIVE %s\n' "$control_service_name"
if [[ "$road_configured" == true ]]; then
  printf 'ROAD_SERVICE_ACTIVE %s profile=road-v1 camera_id=road1\n' "$road_service_name"
  printf 'ROAD_RUNTIME_GATE frame_and_state_progression=PASS\n'
else
  printf 'ROAD_SERVICE_PENDING protected_config=%s\n' "$road_env_file"
fi
if [[ "$desired_state" == "running" ]]; then
  printf 'SERVICE_ACTIVE %s\n' "$service_name"
  printf 'RUNTIME_GATE frame_and_state_progression=PASS\n'
else
  printf 'SERVICE_STOPPED %s\n' "$service_name"
  printf 'RUNTIME_GATE skipped_reason=operator_desired_stopped\n'
fi
printf 'ROLLBACK automatic_on_activation_failure=true explicit_command=rollback-exact.sh\n'
