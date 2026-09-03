#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage:
  camera1-h264-transcode.sh run --source-env-file PATH --publish-address IPv4 [options]
  camera1-h264-transcode.sh prepare --config PATH --private-rtsp-address IPv4:PORT --reader-ip IPv4 --source-env-file PATH [options]
  camera1-h264-transcode.sh activate --config PATH --private-rtsp-address IPv4:PORT --reader-ip IPv4 --source-env-file PATH --expected-config-sha256 SHA256 --expected-unit-sha256 SHA256 [options]
  camera1-h264-transcode.sh status [--private-rtsp-address IPv4:PORT] [options]

Offloads the Camera 1 HEVC->H264 transcode from the VPS to the Ubuntu Worker. The
Ubuntu transcode reads the camera directly (HLS_URL, credential-bearing, never
printed) and publishes H264 RTSP to the Ubuntu MediaMTX path cam1-h264. The VPS
reads rtsp://<ubuntu-ip>:8554/cam1-h264. A least-privilege reader+publish rule
scoped to cam1-h264 (VPS reader IP + Ubuntu publisher IP) is added to the Ubuntu
MediaMTX config.

Options:
  --config PATH            Ubuntu MediaMTX config (default: /opt/sea-speed-worker/shared/config/mediamtx.yml)
  --private-rtsp-address   Ubuntu ZeroTier RTSP listen address IPv4:PORT (relay address)
  --reader-ip IPv4         Exact RFC1918 VPS ZeroTier reader IP allowed to read cam1-h264
  --publisher-ip IPv4      Ubuntu ZeroTier IP used to publish cam1-h264 (default: private-rtsp-address host)
  --source-env-file PATH   Protected worker env file (default: /opt/sea-speed-worker/shared/config/worker.env)
  --service NAME           Transcode service (default: sea-speed-camera1-h264.service)
  --relay-service NAME     Ubuntu relay service that owns the MediaMTX config (default: sea-speed-stream.service)
  --state-root PATH        Root-only candidate/backup state (default: /var/lib/sea-speed-camera1-h264)
  --publish-address IPv4   Address the transcode publishes to (default: publisher-ip)
EOF
}

command="${1:-}"
case "$command" in
  run|prepare|activate|status) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "ERROR unknown command: $command" >&2; usage >&2; exit 2 ;;
esac

config="/opt/sea-speed-worker/shared/config/mediamtx.yml"
private_rtsp_address=""
reader_ip=""
publisher_ip=""
source_env_file="/opt/sea-speed-worker/shared/config/worker.env"
service_name="sea-speed-camera1-h264.service"
relay_service="sea-speed-stream.service"
state_root="/var/lib/sea-speed-camera1-h264"
expected_config_sha256=""
expected_unit_sha256=""
publish_address=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) [[ $# -ge 2 ]] || { echo "ERROR --config requires a path" >&2; exit 2; }; config="$2"; shift 2 ;;
    --private-rtsp-address) [[ $# -ge 2 ]] || { echo "ERROR --private-rtsp-address requires IPv4:PORT" >&2; exit 2; }; private_rtsp_address="$2"; shift 2 ;;
    --reader-ip) [[ $# -ge 2 ]] || { echo "ERROR --reader-ip requires IPv4" >&2; exit 2; }; reader_ip="$2"; shift 2 ;;
    --publisher-ip) [[ $# -ge 2 ]] || { echo "ERROR --publisher-ip requires IPv4" >&2; exit 2; }; publisher_ip="$2"; shift 2 ;;
    --source-env-file) [[ $# -ge 2 ]] || { echo "ERROR --source-env-file requires a path" >&2; exit 2; }; source_env_file="$2"; shift 2 ;;
    --service) [[ $# -ge 2 ]] || { echo "ERROR --service requires a name" >&2; exit 2; }; service_name="$2"; shift 2 ;;
    --relay-service) [[ $# -ge 2 ]] || { echo "ERROR --relay-service requires a name" >&2; exit 2; }; relay_service="$2"; shift 2 ;;
    --state-root) [[ $# -ge 2 ]] || { echo "ERROR --state-root requires a path" >&2; exit 2; }; state_root="$2"; shift 2 ;;
    --expected-config-sha256) [[ $# -ge 2 ]] || { echo "ERROR --expected-config-sha256 requires SHA256" >&2; exit 2; }; expected_config_sha256="$2"; shift 2 ;;
    --expected-unit-sha256) [[ $# -ge 2 ]] || { echo "ERROR --expected-unit-sha256 requires SHA256" >&2; exit 2; }; expected_unit_sha256="$2"; shift 2 ;;
    --publish-address) [[ $# -ge 2 ]] || { echo "ERROR --publish-address requires IPv4" >&2; exit 2; }; publish_address="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/../../.." && pwd)"
renderer="$repo_root/scripts/operations/mediamtx_path_config.py"
candidate="$state_root/cam1-h264-mediamtx.candidate.yml"
candidate_unit="$state_root/$service_name"
backup_root="$state_root/backups"

service_value() {
  local action="$1" name="$2" value
  value="$(systemctl "$action" "$name" 2>/dev/null || true)"
  [[ -n "$value" ]] || value="unknown"
  printf '%s' "$value"
}

require_root() {
  if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR run this command as root" >&2; exit 1
 fi
}

validate_service_name() {
  [[ "$service_name" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || { echo "ERROR invalid service name" >&2; exit 3; }
}

validate_common() {
  validate_service_name
  [[ -x "$renderer" || -f "$renderer" ]] || { echo "ERROR renderer missing from exact repository source" >&2; exit 4; }
  command -v python3 >/dev/null 2>&1 || { echo "ERROR python3 is required" >&2; exit 4; }
  command -v systemctl >/dev/null 2>&1 || { echo "ERROR systemctl is required" >&2; exit 4; }
  command -v ffmpeg >/dev/null 2>&1 || { echo "ERROR ffmpeg is required" >&2; exit 4; }
}

parse_address() {
  python3 - "$private_rtsp_address" <<'PY'
import ipaddress, sys
value = sys.argv[1]
try:
    host, raw_port = value.rsplit(":", 1)
    ip = ipaddress.ip_address(host)
    port = int(raw_port)
except Exception:
    raise SystemExit(1)
networks = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
if ip.version != 4 or not any(ip in network for network in networks) or not (1 <= port <= 65535):
    raise SystemExit(1)
print(host)
print(port)
PY
}

validate_reader_ip() {
  python3 - "$reader_ip" <<'PY'
import ipaddress, sys
try:
    ip = ipaddress.ip_address(sys.argv[1])
except ValueError:
    raise SystemExit(1)
networks = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
if ip.version != 4 or not any(ip in network for network in networks):
    raise SystemExit(1)
PY
}

read_camera_source() {
  python3 - "$source_env_file" <<'PY'
import os, stat, sys
from urllib.parse import urlsplit
path = sys.argv[1]
try:
    info = os.lstat(path)
except OSError:
    raise SystemExit("protected source env file is unavailable")
if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
    raise SystemExit("protected source env file must be a regular non-symlink file")
if stat.S_IMODE(info.st_mode) != 0o600:
    raise SystemExit("protected source env file mode must be 0600")
prefix = "HLS_URL="
for line in open(path, encoding="utf-8").read().splitlines():
    s = line.strip()
    if not s or s.startswith("#") or not s.startswith(prefix):
        continue
    raw = s[len(prefix):].strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        raw = raw[1:-1]
    if not raw:
        continue
    parsed = urlsplit(raw)
    if parsed.scheme.lower() != "rtsp" or parsed.username is None:
        raise SystemExit("HLS_URL must be a credential-bearing rtsp URL")
    print(raw)
    break
else:
    raise SystemExit("HLS_URL not found in protected env file")
PY
}

sha256_file() {
  sha256sum "$1" | awk '{print $1}'
}

if [[ "$command" == "run" ]]; then
  [[ -n "$publish_address" ]] || { echo "ERROR --publish-address is required for run" >&2; exit 2; }
  [[ -f "$source_env_file" && ! -L "$source_env_file" ]] || { echo "ERROR protected source env file unavailable" >&2; exit 6; }
  camera_source="$(read_camera_source)" || { echo "ERROR $camera_source" >&2; exit 6; }
  export HLS_URL="$camera_source"
  exec ffmpeg -nostdin -hide_banner -loglevel warning \
    -rtsp_transport tcp -i "$HLS_URL" \
    -an -vf fps=15,scale=-2:720 -c:v libx264 -preset veryfast -tune zerolatency \
    -f rtsp "rtsp://${publish_address}:8554/cam1-h264"
fi

validate_common

if [[ "$command" == "status" ]]; then
  printf 'TRANSCODE_ENABLED=%s\n' "$(service_value is-enabled "$service_name")"
  printf 'TRANSCODE_ACTIVE=%s\n' "$(service_value is-active "$service_name")"
  printf 'RELAY_ACTIVE=%s\n' "$(service_value is-active "$relay_service")"
  if [[ -n "$private_rtsp_address" ]]; then
    parsed="$(parse_address)" || { echo "PRIVATE_RELAY_TCP=FAIL"; exit 0; }
    host="$(printf '%s\n' "$parsed" | sed -n '1p')"
    port="$(printf '%s\n' "$parsed" | sed -n '2p')"
    if python3 - "$host" "$port" <<'PY'
import socket, sys
try:
    with socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=3):
        pass
except OSError:
    raise SystemExit(1)
PY
    then
      printf 'PRIVATE_RELAY_TCP=PASS\n'
    else
      printf 'PRIVATE_RELAY_TCP=FAIL\n'
    fi
  else
    printf 'PRIVATE_RELAY_TCP=NOT_CHECKED\n'
  fi
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

require_root
[[ -n "$private_rtsp_address" ]] || { echo "ERROR --private-rtsp-address is required" >&2; exit 2; }
[[ -n "$reader_ip" ]] || { echo "ERROR --reader-ip is required" >&2; exit 2; }
parse_address >/dev/null || { echo "ERROR private RTSP address must be RFC1918 IPv4:PORT" >&2; exit 3; }
validate_reader_ip || { echo "ERROR reader IP must be a literal RFC1918 IPv4 address" >&2; exit 3; }
[[ -f "$source_env_file" && ! -L "$source_env_file" ]] || { echo "ERROR protected source env file unavailable" >&2; exit 6; }
[[ "$(stat -c '%a' "$source_env_file")" == "600" ]] || { echo "ERROR protected source env file mode must be 0600" >&2; exit 6; }
[[ -n "$publisher_ip" ]] || publisher_ip="$(parse_address | sed -n '1p')"
publish_address="${publish_address:-$publisher_ip}"

install -d -o root -g root -m 0700 "$state_root" "$backup_root"

if [[ "$command" == "prepare" ]]; then
  read_camera_source >/dev/null || { echo "ERROR cannot read camera source from env" >&2; exit 6; }

  python3 "$renderer" ubuntu-transcode-reader \
    --config "$config" \
    --reader-ip "$reader_ip" \
    --publisher-ip "$publisher_ip" \
    --path cam1-h264 \
    --output "$candidate"

  cat > "$candidate_unit" <<UNIT
[Unit]
Description=Sea Speed Camera 1 HEVC->H264 transcode (Ubuntu Worker)
After=network-online.target $relay_service
Wants=network-online.target

[Service]
Type=simple
User=sea-speed
Group=sea-speed
EnvironmentFile=$source_env_file
Environment=PYTHONUNBUFFERED=1
ExecStart=$script_dir/camera1-h264-transcode.sh run --source-env-file $source_env_file --publish-address $publish_address
Restart=always
RestartSec=2s
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
LockPersonality=true
MemoryDenyWriteExecute=false
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
CapabilityBoundingSet=
AmbientCapabilities=
UMask=0077
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sea-speed-camera1-h264

[Install]
WantedBy=multi-user.target
UNIT

  chown root:root "$candidate" "$candidate_unit"
  chmod 0600 "$candidate" "$candidate_unit"

  config_sha="$(sha256_file "$candidate")"
  unit_sha="$(sha256_file "$candidate_unit")"

  printf 'PREPARED_TRANSCODE_CANDIDATE=YES\n'
  printf 'CONFIG_SHA256=%s\n' "$config_sha"
  printf 'UNIT_SHA256=%s\n' "$unit_sha"
  printf 'TRANSCODE_PATH=cam1-h264\n'
  printf 'READER_IP=%s\n' "$reader_ip"
  printf 'PUBLISHER_IP=%s\n' "$publisher_ip"
  printf 'PUBLISH_ADDRESS=%s\n' "$publish_address"
  printf 'RELAY_ACTIVE=%s\n' "$(service_value is-active "$relay_service")"
  printf 'MUTATIONS=PROTECTED_CANDIDATES_ONLY\n'
  printf 'SERVICE_RESTARTED=NO\n'
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

for digest in "$expected_config_sha256" "$expected_unit_sha256"; do
  [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || { echo "ERROR activate requires all expected SHA256 digests" >&2; exit 2; }
done
[[ -f "$candidate" && -f "$candidate_unit" ]] || { echo "ERROR prepared transcode candidates are missing" >&2; exit 7; }
[[ "$(sha256_file "$candidate")" == "$expected_config_sha256" ]] || { echo "ERROR prepared config digest mismatch" >&2; exit 7; }
[[ "$(sha256_file "$candidate_unit")" == "$expected_unit_sha256" ]] || { echo "ERROR prepared unit digest mismatch" >&2; exit 7; }
[[ -x "$renderer" ]] || { echo "ERROR renderer missing" >&2; exit 8; }
id sea-speed >/dev/null 2>&1 || { echo "ERROR transcode service user sea-speed does not exist" >&2; exit 8; }

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
config_backup="NOT_PRESENT"
if [[ -f "$config" ]]; then
  config_backup="$backup_root/mediamtx.$stamp.yml"
  install -o root -g root -m 0600 "$config" "$config_backup"
fi

install -o root -g root -m 0644 "$candidate_unit" "/etc/systemd/system/$service_name"
install -o root -g root -m 0600 "$candidate" "${config}.next"
mv -f "${config}.next" "$config"

systemctl daemon-reload
if ! systemctl restart "$relay_service"; then
  echo "ERROR relay service restart failed; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$config_backup" >&2
  exit 30
fi
if ! systemctl is-active --quiet "$relay_service"; then
  echo "ERROR relay service is not active; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$config_backup" >&2
  exit 31
fi
systemctl enable --now "$service_name" || { echo "ERROR transcode enable failed" >&2; printf 'BACKUP=%s\n' "$config_backup" >&2; exit 32; }
systemctl is-active --quiet "$service_name" || { echo "ERROR transcode not active" >&2; printf 'BACKUP=%s\n' "$config_backup" >&2; exit 33; }

watchdog_dst="/usr/local/sbin/sea-speed-camera1-h264-freshness-watchdog"
install -o root -g root -m 0755 "$script_dir/camera1-h264-freshness-watchdog.py" "$watchdog_dst"
install -o root -g root -m 0644 "$script_dir/sea-speed-camera1-h264-freshness.service" "/etc/systemd/system/sea-speed-camera1-h264-freshness.service"
install -o root -g root -m 0644 "$script_dir/sea-speed-camera1-h264-freshness.timer" "/etc/systemd/system/sea-speed-camera1-h264-freshness.timer"
systemctl daemon-reload
systemctl enable --now sea-speed-camera1-h264-freshness.timer || { echo "ERROR freshness timer enable failed" >&2; printf 'BACKUP=%s\n' "$config_backup" >&2; exit 34; }

printf 'ACTIVATED_TRANSCODE=YES\n'
printf 'TRANSCODE_PATH=cam1-h264\n'
printf 'READER_IP=%s\n' "$reader_ip"
printf 'PUBLISHER_IP=%s\n' "$publisher_ip"
printf 'RELAY_ACTIVE=active\n'
printf 'TRANSCODE_ACTIVE=active\n'
printf 'BACKUP=%s\n' "$config_backup"
printf 'AUTOMATIC_ROLLBACK=NO\n'
printf 'SECRETS_DISPLAYED=NO\n'
