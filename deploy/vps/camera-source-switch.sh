#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  camera-source-switch.sh prepare --config PATH --relay-url rtsp://PRIVATE_IP:PORT/cam1 [options]
  camera-source-switch.sh activate --config PATH --relay-url rtsp://PRIVATE_IP:PORT/cam1 --expected-sha256 SHA256 [options]
  camera-source-switch.sh prepare-cleanup --config PATH --relay-url rtsp://PRIVATE_IP:PORT/cam1 --confirmed-public-hls [options]
  camera-source-switch.sh activate-cleanup --config PATH --relay-url rtsp://PRIVATE_IP:PORT/cam1 --expected-sha256 SHA256 --confirmed-public-hls [options]
  camera-source-switch.sh status [options]

Options:
  --service NAME           VPS MediaMTX service (default: mediamtx.service)
  --state-root PATH        Root-only candidate/backup state (default: /var/lib/sea-speed-camera-switch)
  --hls-check-url URL      VPS-local canonical HLS URL (default: http://127.0.0.1:8888/cam1/index.m3u8)
  --confirmed-public-hls   Required before retiring temporary cam1-new mapping

prepare renders a candidate that changes only canonical MediaMTX path cam1 to
the credential-free Ubuntu private relay and pins the RTSP source pull to TCP.
activate verifies the exact reviewed candidate, restarts MediaMTX and verifies
VPS-local HLS. The legacy config is backed up root-only. Temporary cam1-new
cleanup is a second, explicitly gated step after public HLS has been validated.
Automatic rollback is not performed.
EOF
}

command="${1:-}"
case "$command" in
  prepare|activate|prepare-cleanup|activate-cleanup|status) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "ERROR unknown command: $command" >&2; usage >&2; exit 2 ;;
esac

config=""
relay_url=""
service_name="mediamtx.service"
state_root="/var/lib/sea-speed-camera-switch"
hls_check_url="http://127.0.0.1:8888/cam1/index.m3u8"
expected_sha256=""
confirmed_public_hls=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) [[ $# -ge 2 ]] || { echo "ERROR --config requires a path" >&2; exit 2; }; config="$2"; shift 2 ;;
    --relay-url) [[ $# -ge 2 ]] || { echo "ERROR --relay-url requires a URL" >&2; exit 2; }; relay_url="$2"; shift 2 ;;
    --service) [[ $# -ge 2 ]] || { echo "ERROR --service requires a name" >&2; exit 2; }; service_name="$2"; shift 2 ;;
    --state-root) [[ $# -ge 2 ]] || { echo "ERROR --state-root requires a path" >&2; exit 2; }; state_root="$2"; shift 2 ;;
    --hls-check-url) [[ $# -ge 2 ]] || { echo "ERROR --hls-check-url requires a URL" >&2; exit 2; }; hls_check_url="$2"; shift 2 ;;
    --expected-sha256) [[ $# -ge 2 ]] || { echo "ERROR --expected-sha256 requires a digest" >&2; exit 2; }; expected_sha256="$2"; shift 2 ;;
    --confirmed-public-hls) confirmed_public_hls=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/../.." && pwd)"
renderer="$repo_root/scripts/operations/mediamtx_path_config.py"
candidate="$state_root/cam1-mediamtx.candidate.yml"
cleanup_candidate="$state_root/cam1-mediamtx.cleanup-candidate.yml"
backup_root="$state_root/backups"

require_root() {
  if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR run this command as root" >&2
    exit 1
  fi
}

validate_service_name() {
  [[ "$service_name" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || {
    echo "ERROR invalid systemd service name" >&2
    exit 3
  }
}

validate_common() {
  validate_service_name
  [[ -x "$renderer" || -f "$renderer" ]] || { echo "ERROR renderer missing from exact repository source" >&2; exit 4; }
  command -v python3 >/dev/null 2>&1 || { echo "ERROR python3 is required" >&2; exit 4; }
  command -v systemctl >/dev/null 2>&1 || { echo "ERROR systemctl is required" >&2; exit 4; }
  command -v curl >/dev/null 2>&1 || { echo "ERROR curl is required" >&2; exit 4; }
}

validate_relay_url() {
  python3 - "$relay_url" <<'PY'
import ipaddress
import sys
from urllib.parse import urlsplit
networks = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
try:
    value = urlsplit(sys.argv[1])
    host = value.hostname
    port = value.port or 554
    address = ipaddress.ip_address(host)
except Exception:
    raise SystemExit(1)
if value.scheme.lower() != "rtsp" or value.username is not None or value.password is not None:
    raise SystemExit(1)
if value.path.rstrip("/") != "/cam1" or address.version != 4 or not any(address in network for network in networks) or not (1 <= port <= 65535):
    raise SystemExit(1)
print(host)
print(port)
PY
}

check_relay_tcp() {
  local parsed host port
  parsed="$(validate_relay_url)" || return 1
  host="$(printf '%s\n' "$parsed" | sed -n '1p')"
  port="$(printf '%s\n' "$parsed" | sed -n '2p')"
  python3 - "$host" "$port" <<'PY'
import socket
import sys
try:
    with socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=4):
        pass
except OSError:
    raise SystemExit(1)
PY
}

check_local_hls() {
  local attempt
  for attempt in {1..12}; do
    if curl --fail --silent --show-error --max-time 8 "$hls_check_url" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

validate_config_security() {
  [[ -f "$config" && ! -L "$config" ]] || { echo "ERROR MediaMTX config must be a regular non-symlink file" >&2; exit 5; }
  local mode numeric
  mode="$(stat -c '%a' "$config")"
  numeric=$((8#$mode))
  if (( numeric & 0007 )); then
    echo "ERROR MediaMTX config containing legacy source credentials must not be world-accessible" >&2
    exit 5
  fi
}

prepare_state() {
  install -d -o root -g root -m 0700 "$state_root" "$backup_root"
}

verify_vps_candidate() {
  local source="$1"
  python3 "$renderer" verify-vps-switch \
    --config "$source" \
    --relay-url "$relay_url" \
    --path cam1 >/dev/null
}

install_candidate() {
  local source="$1" expected="$2" actual owner group mode backup
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || { echo "ERROR activation requires --expected-sha256" >&2; exit 2; }
  [[ -f "$source" && ! -L "$source" ]] || { echo "ERROR prepared candidate is missing" >&2; exit 7; }
  actual="$(sha256sum "$source" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] || { echo "ERROR prepared candidate digest mismatch" >&2; exit 7; }
  [[ "$(stat -c '%a' "$source")" == "600" ]] || { echo "ERROR candidate mode must be 600" >&2; exit 7; }
  verify_vps_candidate "$source" || { echo "ERROR candidate does not match canonical TCP relay contract" >&2; exit 7; }

  owner="$(stat -c '%u' "$config")"
  group="$(stat -c '%g' "$config")"
  mode="$(stat -c '%a' "$config")"
  backup="$backup_root/mediamtx.$(date -u +%Y%m%dT%H%M%SZ).yml"
  install -o root -g root -m 0600 "$config" "$backup"
  install -o "$owner" -g "$group" -m "$mode" "$source" "${config}.next"
  mv -f "${config}.next" "$config"

  if ! systemctl restart "$service_name"; then
    echo "ERROR VPS MediaMTX restart failed; automatic rollback is not authorized" >&2
    printf 'BACKUP=%s\n' "$backup" >&2
    exit 30
  fi
  if ! systemctl is-active --quiet "$service_name"; then
    echo "ERROR VPS MediaMTX is not active; automatic rollback is not authorized" >&2
    printf 'BACKUP=%s\n' "$backup" >&2
    exit 31
  fi
  printf '%s\n' "$backup"
}

validate_common

if [[ "$command" == "status" ]]; then
  printf 'MEDIAMTX_ENABLED=%s\n' "$(systemctl is-enabled "$service_name" 2>/dev/null || true)"
  printf 'MEDIAMTX_ACTIVE=%s\n' "$(systemctl is-active "$service_name" 2>/dev/null || true)"
  if check_local_hls; then
    printf 'LOCAL_CANONICAL_HLS=PASS\n'
  else
    printf 'LOCAL_CANONICAL_HLS=FAIL\n'
  fi
  exit 0
fi

require_root
[[ -n "$config" ]] || { echo "ERROR --config is required" >&2; exit 2; }
[[ -n "$relay_url" ]] || { echo "ERROR --relay-url is required" >&2; exit 2; }
validate_relay_url >/dev/null || { echo "ERROR relay URL must be credential-free RFC1918 RTSP ending in /cam1" >&2; exit 3; }
validate_config_security
prepare_state

if [[ "$command" == "prepare" ]]; then
  check_relay_tcp || { echo "ERROR Ubuntu private relay TCP is not reachable" >&2; exit 8; }
  python3 "$renderer" vps-switch \
    --config "$config" \
    --relay-url "$relay_url" \
    --path cam1 \
    --output "$candidate"
  verify_vps_candidate "$candidate" || { echo "ERROR prepared candidate does not match canonical TCP relay contract" >&2; exit 7; }
  digest="$(sha256sum "$candidate" | awk '{print $1}')"
  chown root:root "$candidate"
  chmod 0600 "$candidate"
  printf 'PREPARED_SWITCH_CANDIDATE=YES\n'
  printf 'CANDIDATE_SHA256=%s\n' "$digest"
  printf 'CANONICAL_PATH=cam1\n'
  printf 'RELAY_USERINFO=NO\n'
  printf 'RTSP_TRANSPORT=tcp\n'
  printf 'PRIVATE_RELAY_TCP=PASS\n'
  printf 'MEDIAMTX_RESTARTED=NO\n'
  printf 'MUTATIONS=PROTECTED_CANDIDATE_ONLY\n'
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

if [[ "$command" == "activate" ]]; then
  check_relay_tcp || { echo "ERROR Ubuntu private relay TCP is not reachable" >&2; exit 8; }
  backup="$(install_candidate "$candidate" "$expected_sha256")"
  if ! check_local_hls; then
    echo "ERROR canonical VPS-local HLS did not become available; automatic rollback is not authorized" >&2
    printf 'BACKUP=%s\n' "$backup" >&2
    exit 32
  fi
  printf 'CANONICAL_SWITCHED=YES\n'
  printf 'CANONICAL_PATH=cam1\n'
  printf 'PRIVATE_RELAY_TCP=PASS\n'
  printf 'RTSP_TRANSPORT=tcp\n'
  printf 'LOCAL_CANONICAL_HLS=PASS\n'
  printf 'TEMP_CAM1_NEW_RETIRED=NO\n'
  printf 'BACKUP=%s\n' "$backup"
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

if [[ "$confirmed_public_hls" != true ]]; then
  echo "ERROR cleanup requires --confirmed-public-hls after public canonical HLS validation" >&2
  exit 9
fi

if [[ "$command" == "prepare-cleanup" ]]; then
  python3 "$renderer" vps-cleanup \
    --config "$config" \
    --relay-url "$relay_url" \
    --path cam1 \
    --remove-path cam1-new \
    --output "$cleanup_candidate"
  verify_vps_candidate "$cleanup_candidate" || { echo "ERROR cleanup candidate lost canonical TCP relay contract" >&2; exit 7; }
  digest="$(sha256sum "$cleanup_candidate" | awk '{print $1}')"
  chown root:root "$cleanup_candidate"
  chmod 0600 "$cleanup_candidate"
  printf 'PREPARED_CLEANUP_CANDIDATE=YES\n'
  printf 'CANDIDATE_SHA256=%s\n' "$digest"
  printf 'REMOVE_PATH=cam1-new\n'
  printf 'RTSP_TRANSPORT=tcp\n'
  printf 'MEDIAMTX_RESTARTED=NO\n'
  printf 'MUTATIONS=PROTECTED_CANDIDATE_ONLY\n'
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

backup="$(install_candidate "$cleanup_candidate" "$expected_sha256")"
if ! check_local_hls; then
  echo "ERROR canonical HLS failed after cleanup; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$backup" >&2
  exit 33
fi
printf 'TEMP_CAM1_NEW_RETIRED=YES\n'
printf 'CANONICAL_PATH=cam1\n'
printf 'RTSP_TRANSPORT=tcp\n'
printf 'LOCAL_CANONICAL_HLS=PASS\n'
printf 'BACKUP=%s\n' "$backup"
printf 'SECRETS_DISPLAYED=NO\n'