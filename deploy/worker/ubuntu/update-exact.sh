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
state before returning.
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
control_unit_backup=""
marker_tmp=""
cleanup() {
  rm -rf "$staging_root"
  [[ -n "$unit_backup" ]] && rm -f "$unit_backup"
  [[ -n "$control_unit_backup" ]] && rm -f "$control_unit_backup"
  [[ -n "$marker_tmp" ]] && rm -f "$marker_tmp"
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
  --required-name quality-integration
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
control_unit_target="/etc/systemd/system/$control_service_name"
active_marker="$install_root/shared/runtime/active-source-commit"
heartbeat="$install_root/shared/runtime/worker-heartbeat.json"
desired_state_file="$install_root/shared/runtime/operator-desired-state"
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
  if [[ -f "$control_unit_target" ]]; then
    control_unit_backup="$(mktemp "$updater_root/control-unit-backup.XXXXXX")"
    install -o root -g root -m 0600 "$control_unit_target" "$control_unit_backup"
  fi
  previous_runtime_ready=true
fi

restore_previous() {
  if [[ "$previous_runtime_ready" != true ]] || [[ -z "$unit_backup" ]]; then
    return 1
  fi

  echo "RESTORE previous_source_commit=$previous_commit desired_state=$desired_state" >&2
  install -o root -g root -m 0644 "$unit_backup" "$unit_target"
  if [[ -n "$control_unit_backup" ]]; then
    install -o root -g root -m 0644 "$control_unit_backup" "$control_unit_target"
  fi
  systemctl daemon-reload
  rm -f "$heartbeat"
  systemctl reset-failed "$service_name" || return 1
  if [[ "$desired_state" == "running" ]]; then
    systemctl restart "$service_name" || return 1
    systemctl is-active --quiet "$service_name" || return 1
  else
    systemctl stop "$service_name" || return 1
    ! systemctl is-active --quiet "$service_name" || return 1
  fi
  if [[ -f "$control_unit_target" ]]; then
    systemctl restart "$control_service_name" || return 1
    systemctl is-active --quiet "$control_service_name" || return 1
  fi
  restored_exec="$(systemctl show -p ExecStart --value "$service_name")"
  [[ "$restored_exec" == *"$previous_commit"* ]] || return 1
  if [[ -n "$previous_runtime_id" ]] && [[ "$restored_exec" != *"/runtimes/$previous_runtime_id/venv/bin/python"* ]]; then
    return 1
  fi
  [[ "$(cat "$active_marker")" == "$previous_commit" ]] || return 1

  printf 'RESTORED previous_source_commit=%s runtime_id=%s desired_state=%s\n' \
    "$previous_commit" "${previous_runtime_id:-legacy-per-release}" "$desired_state"
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

if [[ "$desired_state" == "running" ]]; then
  runtime_gate="$release_root/source/deploy/worker/ubuntu/verify-runtime-progression.py"
  if [[ ! -f "$runtime_gate" ]]; then
    abort_activation "runtime progression verifier is missing"
  fi
  if ! python3 "$runtime_gate" \
    --heartbeat "$heartbeat" \
    --expected-commit "$source_commit" \
    --timeout-sec 90 \
    --poll-sec 1; then
    abort_activation "frame/state progression gate failed"
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
if [[ "$desired_state" == "running" ]]; then
  printf 'SERVICE_ACTIVE %s\n' "$service_name"
  printf 'RUNTIME_GATE frame_and_state_progression=PASS\n'
else
  printf 'SERVICE_STOPPED %s\n' "$service_name"
  printf 'RUNTIME_GATE skipped_reason=operator_desired_stopped\n'
fi
printf 'ROLLBACK automatic_on_activation_failure=true explicit_command=rollback-exact.sh\n'
