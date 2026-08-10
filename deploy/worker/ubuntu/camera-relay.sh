#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  camera-relay.sh prepare --config PATH --private-rtsp-address IPv4:PORT [options]
  camera-relay.sh activate --config PATH --private-rtsp-address IPv4:PORT --expected-sha256 SHA256 [options]
  camera-relay.sh status [--private-rtsp-address IPv4:PORT] [options]

Options:
  --source-env-file PATH   Protected worker env file (default: /opt/sea-speed-worker/shared/config/worker.env)
  --service NAME           Independent relay service (default: sea-speed-stream.service)
  --worker-service NAME    AI worker service that must remain stopped (default: sea-speed-worker.service)
  --state-root PATH        Root-only candidate/backup state (default: /var/lib/sea-speed-camera-relay)

prepare renders a protected candidate MediaMTX config and does not modify or
restart any service. activate installs only the reviewed candidate, restarts the
independent relay service, and verifies the private RTSP listener. It never
starts, stops, restarts or enables the AI worker. Automatic rollback is not
performed; a root-only backup is preserved for an explicit rollback decision.
EOF
}

command="${1:-}"
case "$command" in
  prepare|activate|status) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "ERROR unknown command: $command" >&2; usage >&2; exit 2 ;;
esac

config=""
private_rtsp_address=""
source_env_file="/opt/sea-speed-worker/shared/config/worker.env"
service_name="sea-speed-stream.service"
worker_service="sea-speed-worker.service"
state_root="/var/lib/sea-speed-camera-relay"
expected_sha256=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) [[ $# -ge 2 ]] || { echo "ERROR --config requires a path" >&2; exit 2; }; config="$2"; shift 2 ;;
    --private-rtsp-address) [[ $# -ge 2 ]] || { echo "ERROR --private-rtsp-address requires IPv4:PORT" >&2; exit 2; }; private_rtsp_address="$2"; shift 2 ;;
    --source-env-file) [[ $# -ge 2 ]] || { echo "ERROR --source-env-file requires a path" >&2; exit 2; }; source_env_file="$2"; shift 2 ;;
    --service) [[ $# -ge 2 ]] || { echo "ERROR --service requires a name" >&2; exit 2; }; service_name="$2"; shift 2 ;;
    --worker-service) [[ $# -ge 2 ]] || { echo "ERROR --worker-service requires a name" >&2; exit 2; }; worker_service="$2"; shift 2 ;;
    --state-root) [[ $# -ge 2 ]] || { echo "ERROR --state-root requires a path" >&2; exit 2; }; state_root="$2"; shift 2 ;;
    --expected-sha256) [[ $# -ge 2 ]] || { echo "ERROR --expected-sha256 requires a digest" >&2; exit 2; }; expected_sha256="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/../../.." && pwd)"
renderer="$repo_root/scripts/operations/mediamtx_path_config.py"
candidate="$state_root/cam1-mediamtx.candidate.yml"
candidate_sha_file="$state_root/cam1-mediamtx.candidate.sha256"
backup_root="$state_root/backups"

service_value() {
  local action="$1" name="$2" value
  value="$(systemctl "$action" "$name" 2>/dev/null || true)"
  [[ -n "$value" ]] || value="unknown"
  printf '%s' "$value"
}

require_root() {
  if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR run this command as root" >&2
    exit 1
  fi
}

validate_service_name() {
  local value="$1"
  [[ "$value" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || {
    echo "ERROR invalid systemd service name" >&2
    exit 3
  }
}

validate_common() {
  validate_service_name "$service_name"
  validate_service_name "$worker_service"
  [[ -x "$renderer" || -f "$renderer" ]] || { echo "ERROR renderer missing from exact repository source" >&2; exit 4; }
  command -v python3 >/dev/null 2>&1 || { echo "ERROR python3 is required" >&2; exit 4; }
  command -v systemctl >/dev/null 2>&1 || { echo "ERROR systemctl is required" >&2; exit 4; }
}

parse_address() {
  python3 - "$private_rtsp_address" <<'PY'
import ipaddress
import sys
value = sys.argv[1]
try:
    host, raw_port = value.rsplit(":", 1)
    ip = ipaddress.ip_address(host)
    port = int(raw_port)
except Exception:
    raise SystemExit(1)
if ip.version != 4 or not ip.is_private or not (1 <= port <= 65535):
    raise SystemExit(1)
print(host)
print(port)
PY
}

check_private_listener() {
  local parsed host port
  parsed="$(parse_address)" || { echo "ERROR invalid private RTSP address" >&2; return 1; }
  host="$(printf '%s\n' "$parsed" | sed -n '1p')"
  port="$(printf '%s\n' "$parsed" | sed -n '2p')"
  python3 - "$host" "$port" <<'PY'
import socket
import sys
host, port = sys.argv[1], int(sys.argv[2])
try:
    with socket.create_connection((host, port), timeout=3):
        pass
except OSError:
    raise SystemExit(1)
PY
}

validate_common

if [[ "$command" == "status" ]]; then
  printf 'RELAY_ENABLED=%s\n' "$(service_value is-enabled "$service_name")"
  printf 'RELAY_ACTIVE=%s\n' "$(service_value is-active "$service_name")"
  printf 'AI_WORKER_ENABLED=%s\n' "$(service_value is-enabled "$worker_service")"
  printf 'AI_WORKER_ACTIVE=%s\n' "$(service_value is-active "$worker_service")"
  if [[ -n "$private_rtsp_address" ]]; then
    if check_private_listener; then
      printf 'PRIVATE_RELAY_TCP=PASS\n'
    else
      printf 'PRIVATE_RELAY_TCP=FAIL\n'
    fi
  else
    printf 'PRIVATE_RELAY_TCP=NOT_CHECKED\n'
  fi
  exit 0
fi

require_root
[[ -n "$config" ]] || { echo "ERROR --config is required" >&2; exit 2; }
[[ -n "$private_rtsp_address" ]] || { echo "ERROR --private-rtsp-address is required" >&2; exit 2; }
parse_address >/dev/null || { echo "ERROR private RTSP address must be private IPv4:PORT" >&2; exit 3; }
[[ -f "$config" && ! -L "$config" ]] || { echo "ERROR MediaMTX config must be a regular non-symlink file" >&2; exit 5; }

install -d -o root -g root -m 0700 "$state_root" "$backup_root"

if [[ "$command" == "prepare" ]]; then
  [[ -f "$source_env_file" && ! -L "$source_env_file" ]] || { echo "ERROR protected source env file is unavailable" >&2; exit 6; }
  [[ "$(stat -c '%a' "$source_env_file")" == "600" ]] || { echo "ERROR protected source env file mode must be 600" >&2; exit 6; }

  python3 "$renderer" ubuntu-relay \
    --config "$config" \
    --source-env-file "$source_env_file" \
    --source-env-key HLS_URL \
    --private-rtsp-address "$private_rtsp_address" \
    --path cam1 \
    --output "$candidate"

  digest="$(sha256sum "$candidate" | awk '{print $1}')"
  printf '%s\n' "$digest" > "$candidate_sha_file"
  chown root:root "$candidate" "$candidate_sha_file"
  chmod 0600 "$candidate" "$candidate_sha_file"

  printf 'PREPARED_RELAY_CANDIDATE=YES\n'
  printf 'CANDIDATE_SHA256=%s\n' "$digest"
  printf 'CAMERA_SOURCE_SCHEME=rtsp\n'
  printf 'CAMERA_SOURCE_USERINFO=YES\n'
  printf 'RELAY_PATH=cam1\n'
  printf 'RELAY_ENABLED=%s\n' "$(service_value is-enabled "$service_name")"
  printf 'RELAY_ACTIVE=%s\n' "$(service_value is-active "$service_name")"
  printf 'AI_WORKER_ACTIVE=%s\n' "$(service_value is-active "$worker_service")"
  printf 'MUTATIONS=PROTECTED_CANDIDATE_ONLY\n'
  printf 'SERVICE_RESTARTED=NO\n'
  printf 'AI_WORKER_STARTED=NO\n'
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

[[ "$expected_sha256" =~ ^[0-9a-f]{64}$ ]] || { echo "ERROR activate requires --expected-sha256" >&2; exit 2; }
[[ -f "$candidate" && ! -L "$candidate" ]] || { echo "ERROR prepared candidate is missing" >&2; exit 7; }
actual_sha256="$(sha256sum "$candidate" | awk '{print $1}')"
[[ "$actual_sha256" == "$expected_sha256" ]] || { echo "ERROR prepared candidate digest mismatch" >&2; exit 7; }
[[ "$(stat -c '%a' "$candidate")" == "600" ]] || { echo "ERROR candidate mode must be 600" >&2; exit 7; }

if systemctl is-active --quiet "$worker_service"; then
  echo "ERROR AI worker must remain stopped during live-relay activation" >&2
  exit 8
fi

service_user="$(systemctl show -p User --value "$service_name" 2>/dev/null || true)"
service_group="$(systemctl show -p Group --value "$service_name" 2>/dev/null || true)"
if [[ -z "$service_user" || "$service_user" == "root" ]]; then
  install_owner="root"
  install_group="root"
  install_mode="0600"
else
  install_owner="root"
  if [[ -z "$service_group" ]]; then
    service_group="$(id -gn "$service_user" 2>/dev/null || true)"
  fi
  [[ -n "$service_group" ]] || { echo "ERROR cannot resolve relay service group" >&2; exit 9; }
  install_group="$service_group"
  install_mode="0640"
fi

backup="$backup_root/mediamtx.$(date -u +%Y%m%dT%H%M%SZ).yml"
install -o root -g root -m 0600 "$config" "$backup"
install -o "$install_owner" -g "$install_group" -m "$install_mode" "$candidate" "${config}.next"
mv -f "${config}.next" "$config"

systemctl restart "$service_name" || {
  echo "ERROR relay service restart failed; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$backup" >&2
  exit 30
}
systemctl is-active --quiet "$service_name" || {
  echo "ERROR relay service is not active; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$backup" >&2
  exit 31
}
check_private_listener || {
  echo "ERROR private relay TCP listener is not reachable; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$backup" >&2
  exit 32
}
if systemctl is-active --quiet "$worker_service"; then
  echo "ERROR AI worker became active unexpectedly" >&2
  exit 33
fi

printf 'ACTIVATED_RELAY=YES\n'
printf 'RELAY_PATH=cam1\n'
printf 'PRIVATE_RELAY_TCP=PASS\n'
printf 'RELAY_ACTIVE=active\n'
printf 'AI_WORKER_ACTIVE=inactive\n'
printf 'AI_WORKER_STARTED=NO\n'
printf 'CAMERA_PLAYBACK_TESTED=NO\n'
printf 'BACKUP=%s\n' "$backup"
printf 'SECRETS_DISPLAYED=NO\n'
