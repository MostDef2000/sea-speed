#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage:
  camera-preview-relay.sh prepare --inventory PATH --private-rtsp-address IPv4:PORT --reader-ip IPv4 [options]
  camera-preview-relay.sh activate --private-rtsp-address IPv4:PORT --expected-config-sha256 SHA256 --expected-unit-sha256 SHA256 --expected-catalog-sha256 SHA256 [options]
  camera-preview-relay.sh status [--private-rtsp-address IPv4:PORT] [options]

Options:
  --service NAME            Dedicated preview relay service (default: sea-speed-camera-preview-relay.service)
  --service-user USER       Unprivileged MediaMTX service user (default: mediamtx)
  --service-group GROUP     Unprivileged MediaMTX service group (default: mediamtx)
  --mediamtx-bin PATH       MediaMTX binary (default: /usr/local/bin/mediamtx)
  --state-root PATH         Protected state root (default: /var/lib/sea-speed-camera-preview)

prepare reads only a root-owned mode-0600 runtime inventory, renders a standalone
source-on-demand MediaMTX candidate, a dedicated systemd unit candidate, and a
sanitized VPS catalog. It does not change or restart any service.

activate installs only the digest-bound dedicated preview relay candidates and
restarts/enables only the dedicated preview service. It never changes the
accepted Camera 1 relay service, the AI worker, nginx, network configuration or
camera credentials. Automatic rollback is not performed; protected backups are
retained for an explicit rollback decision.
USAGE
}

command="${1:-}"
case "$command" in
  prepare|activate|status) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "ERROR unknown command: $command" >&2; usage >&2; exit 2 ;;
esac

inventory=""
private_rtsp_address=""
reader_ip=""
service_name="sea-speed-camera-preview-relay.service"
service_user="mediamtx"
service_group="mediamtx"
mediamtx_bin="/usr/local/bin/mediamtx"
state_root="/var/lib/sea-speed-camera-preview"
expected_config_sha256=""
expected_unit_sha256=""
expected_catalog_sha256=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --inventory) [[ $# -ge 2 ]] || { echo "ERROR --inventory requires a path" >&2; exit 2; }; inventory="$2"; shift 2 ;;
    --private-rtsp-address) [[ $# -ge 2 ]] || { echo "ERROR --private-rtsp-address requires IPv4:PORT" >&2; exit 2; }; private_rtsp_address="$2"; shift 2 ;;
    --reader-ip) [[ $# -ge 2 ]] || { echo "ERROR --reader-ip requires IPv4" >&2; exit 2; }; reader_ip="$2"; shift 2 ;;
    --service) [[ $# -ge 2 ]] || { echo "ERROR --service requires a name" >&2; exit 2; }; service_name="$2"; shift 2 ;;
    --service-user) [[ $# -ge 2 ]] || { echo "ERROR --service-user requires a user" >&2; exit 2; }; service_user="$2"; shift 2 ;;
    --service-group) [[ $# -ge 2 ]] || { echo "ERROR --service-group requires a group" >&2; exit 2; }; service_group="$2"; shift 2 ;;
    --mediamtx-bin) [[ $# -ge 2 ]] || { echo "ERROR --mediamtx-bin requires a path" >&2; exit 2; }; mediamtx_bin="$2"; shift 2 ;;
    --state-root) [[ $# -ge 2 ]] || { echo "ERROR --state-root requires a path" >&2; exit 2; }; state_root="$2"; shift 2 ;;
    --expected-config-sha256) [[ $# -ge 2 ]] || { echo "ERROR --expected-config-sha256 requires SHA256" >&2; exit 2; }; expected_config_sha256="$2"; shift 2 ;;
    --expected-unit-sha256) [[ $# -ge 2 ]] || { echo "ERROR --expected-unit-sha256 requires SHA256" >&2; exit 2; }; expected_unit_sha256="$2"; shift 2 ;;
    --expected-catalog-sha256) [[ $# -ge 2 ]] || { echo "ERROR --expected-catalog-sha256 requires SHA256" >&2; exit 2; }; expected_catalog_sha256="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

candidate_root="$state_root/candidates"
active_root="$state_root/active"
backup_root="$state_root/backups"
candidate_config="$candidate_root/mediamtx.yml"
candidate_unit="$candidate_root/$service_name"
candidate_catalog="$candidate_root/camera-preview-catalog.json"
active_config="$active_root/mediamtx.yml"
active_catalog="$active_root/camera-preview-catalog.json"
unit_target="/etc/systemd/system/$service_name"
cam1_service="sea-speed-stream.service"
ai_service="sea-speed-worker.service"

require_root() {
  [[ "$EUID" -eq 0 ]] || { echo "ERROR run this command as root" >&2; exit 1; }
}

validate_names() {
  [[ "$service_name" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || { echo "ERROR invalid service name" >&2; exit 3; }
  [[ "$service_user" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "ERROR invalid service user" >&2; exit 3; }
  [[ "$service_group" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "ERROR invalid service group" >&2; exit 3; }
  [[ "$mediamtx_bin" =~ ^/[A-Za-z0-9_./-]+$ ]] || { echo "ERROR invalid MediaMTX binary path" >&2; exit 3; }
  [[ "$state_root" =~ ^/[A-Za-z0-9_./-]+$ ]] || { echo "ERROR invalid state root" >&2; exit 3; }
}

parse_private_address() {
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
networks = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
if ip.version != 4 or not any(ip in network for network in networks) or not (1 <= port <= 65535):
    raise SystemExit(1)
print(host)
print(port)
PY
}

validate_reader_ip() {
  python3 - "$reader_ip" <<'PY'
import ipaddress
import sys
try:
    ip = ipaddress.ip_address(sys.argv[1])
except ValueError:
    raise SystemExit(1)
networks = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
if ip.version != 4 or not any(ip in network for network in networks):
    raise SystemExit(1)
PY
}

check_listener() {
  local parsed host port
  parsed="$(parse_private_address)" || return 1
  host="$(printf '%s\n' "$parsed" | sed -n '1p')"
  port="$(printf '%s\n' "$parsed" | sed -n '2p')"
  python3 - "$host" "$port" <<'PY'
import socket
import sys
try:
    with socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=3):
        pass
except OSError:
    raise SystemExit(1)
PY
}

service_value() {
  local action="$1" service="$2" value
  value="$(systemctl "$action" "$service" 2>/dev/null || true)"
  [[ -n "$value" ]] || value="unknown"
  printf '%s' "$value"
}

sha256_file() {
  sha256sum "$1" | awk '{print $1}'
}

validate_names
command -v python3 >/dev/null 2>&1 || { echo "ERROR python3 is required" >&2; exit 4; }
command -v systemctl >/dev/null 2>&1 || { echo "ERROR systemctl is required" >&2; exit 4; }

if [[ "$command" == "status" ]]; then
  printf 'PREVIEW_RELAY_ENABLED=%s\n' "$(service_value is-enabled "$service_name")"
  printf 'PREVIEW_RELAY_ACTIVE=%s\n' "$(service_value is-active "$service_name")"
  printf 'CAM1_RELAY_ACTIVE=%s\n' "$(service_value is-active "$cam1_service")"
  printf 'AI_WORKER_ACTIVE=%s\n' "$(service_value is-active "$ai_service")"
  if [[ -n "$private_rtsp_address" ]] && check_listener; then
    printf 'PRIVATE_PREVIEW_RELAY_TCP=PASS\n'
  elif [[ -n "$private_rtsp_address" ]]; then
    printf 'PRIVATE_PREVIEW_RELAY_TCP=FAIL\n'
  else
    printf 'PRIVATE_PREVIEW_RELAY_TCP=NOT_CHECKED\n'
  fi
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

require_root
[[ -n "$private_rtsp_address" ]] || { echo "ERROR --private-rtsp-address is required" >&2; exit 2; }
parse_private_address >/dev/null || { echo "ERROR private RTSP address must be private IPv4:PORT" >&2; exit 3; }

install -d -o root -g root -m 0700 "$state_root" "$candidate_root" "$active_root" "$backup_root"

if [[ "$command" == "prepare" ]]; then
  [[ -n "$inventory" ]] || { echo "ERROR --inventory is required" >&2; exit 2; }
  [[ -n "$reader_ip" ]] || { echo "ERROR --reader-ip is required" >&2; exit 2; }
  validate_reader_ip || { echo "ERROR reader IP must be a private IPv4 address" >&2; exit 3; }
  [[ -f "$inventory" && ! -L "$inventory" ]] || { echo "ERROR inventory must be a regular non-symlink file" >&2; exit 5; }
  [[ "$(stat -c '%a' "$inventory")" == "600" ]] || { echo "ERROR inventory mode must be 600" >&2; exit 5; }
  [[ "$(stat -c '%u' "$inventory")" == "0" ]] || { echo "ERROR inventory must be root-owned" >&2; exit 5; }

  python3 - "$inventory" "$candidate_config" "$candidate_catalog" "$private_rtsp_address" "$reader_ip" <<'PY'
import ipaddress
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

inventory_path = Path(sys.argv[1])
config_path = Path(sys.argv[2])
catalog_path = Path(sys.argv[3])
private_address = sys.argv[4]
reader_ip = sys.argv[5]

try:
    relay_host, relay_port_text = private_address.rsplit(":", 1)
    relay_ip = ipaddress.ip_address(relay_host)
    relay_port = int(relay_port_text)
    reader = ipaddress.ip_address(reader_ip)
except Exception as exc:
    raise SystemExit("invalid private relay address") from exc
networks = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
if relay_ip.version != 4 or not any(relay_ip in network for network in networks) or not (1 <= relay_port <= 65535):
    raise SystemExit("invalid private relay address")
if reader.version != 4 or not any(reader in network for network in networks):
    raise SystemExit("invalid private reader IP")

payload = json.loads(inventory_path.read_text(encoding="utf-8"))
if payload.get("schema") != "sea_speed_camera_preview_inventory_v1":
    raise SystemExit("unsupported camera preview inventory schema")
cameras = payload.get("cameras")
if not isinstance(cameras, list) or not cameras:
    raise SystemExit("camera preview inventory must contain at least one camera")

seen = set()
validated = []
for item in cameras:
    if not isinstance(item, dict):
        raise SystemExit("camera inventory entries must be objects")
    camera_id = str(item.get("camera_id") or "").strip()
    display_name = str(item.get("display_name") or camera_id).strip()
    source = str(item.get("source") or "").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", camera_id):
        raise SystemExit("camera_id must use lowercase safe characters")
    if camera_id in seen:
        raise SystemExit("duplicate camera_id")
    if not display_name or len(display_name) > 120:
        raise SystemExit("invalid display_name")
    try:
        parsed = urlsplit(source)
        source_ip = ipaddress.ip_address(parsed.hostname or "")
    except Exception as exc:
        raise SystemExit("camera source must be a private RTSP URL") from exc
    if parsed.scheme.lower() != "rtsp" or source_ip.version != 4 or not any(source_ip in network for network in networks):
        raise SystemExit("camera source must be a private RTSP URL")
    if parsed.username is None:
        raise SystemExit("camera source must contain protected userinfo")
    seen.add(camera_id)
    validated.append((camera_id, display_name, source))

lines = [
    "logLevel: error\n",
    "logDestinations: [stdout]\n",
    "authMethod: internal\n",
    "authInternalUsers:\n",
    "  - user: any\n",
    "    pass:\n",
    f"    ips: [{json.dumps(reader_ip)}]\n",
    "    permissions:\n",
    "      - action: read\n",
    "        path: \"~^preview_[a-z0-9._-]+$\"\n",
    "rtsp: true\n",
    "rtspTransports: [tcp]\n",
    f"rtspAddress: {json.dumps(private_address)}\n",
    "rtmp: false\n",
    "hls: false\n",
    "webrtc: false\n",
    "srt: false\n",
    "paths:\n",
]

catalog = {
    "schema": "sea_speed_camera_preview_catalog_v1",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "cameras": [],
}
for camera_id, display_name, source in validated:
    path_name = f"preview_{camera_id}"
    lines.extend([
        f"  {json.dumps(path_name)}:\n",
        f"    source: {json.dumps(source, ensure_ascii=False)}\n",
        "    sourceOnDemand: yes\n",
        "    sourceOnDemandStartTimeout: 8s\n",
        "    sourceOnDemandCloseAfter: 2s\n",
        "    rtspTransport: tcp\n",
    ])
    catalog["cameras"].append({
        "camera_id": camera_id,
        "display_name": display_name,
        "source": f"rtsp://{relay_host}:{relay_port}/{path_name}",
    })

config_path.write_text("".join(lines), encoding="utf-8")
catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

  cat > "$candidate_unit" <<UNIT
[Unit]
Description=Sea Speed on-demand camera preview relay
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$service_user
Group=$service_group
WorkingDirectory=$active_root
ExecStart=$mediamtx_bin $active_config
Restart=on-failure
RestartSec=2s
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
CapabilityBoundingSet=
AmbientCapabilities=
UMask=0077
StandardOutput=null
StandardError=null

[Install]
WantedBy=multi-user.target
UNIT

  chown root:root "$candidate_config" "$candidate_unit" "$candidate_catalog"
  chmod 0600 "$candidate_config" "$candidate_unit" "$candidate_catalog"

  config_sha="$(sha256_file "$candidate_config")"
  unit_sha="$(sha256_file "$candidate_unit")"
  catalog_sha="$(sha256_file "$candidate_catalog")"
  count="$(python3 - "$candidate_catalog" <<'PY'
import json, sys
print(len(json.load(open(sys.argv[1], encoding="utf-8"))["cameras"]))
PY
)"

  printf 'PREPARED_PREVIEW_RELAY=YES\n'
  printf 'CAMERA_COUNT=%s\n' "$count"
  printf 'CONFIG_SHA256=%s\n' "$config_sha"
  printf 'UNIT_SHA256=%s\n' "$unit_sha"
  printf 'SANITIZED_CATALOG_SHA256=%s\n' "$catalog_sha"
  printf 'SANITIZED_CATALOG=%s\n' "$candidate_catalog"
  printf 'PREVIEW_RELAY_ACTIVE=%s\n' "$(service_value is-active "$service_name")"
  printf 'CAM1_RELAY_ACTIVE=%s\n' "$(service_value is-active "$cam1_service")"
  printf 'AI_WORKER_ACTIVE=%s\n' "$(service_value is-active "$ai_service")"
  printf 'MUTATIONS=PROTECTED_CANDIDATES_ONLY\n'
  printf 'SERVICE_RESTARTED=NO\n'
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

for digest in "$expected_config_sha256" "$expected_unit_sha256" "$expected_catalog_sha256"; do
  [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || { echo "ERROR activate requires all expected SHA256 digests" >&2; exit 2; }
done
[[ -f "$candidate_config" && -f "$candidate_unit" && -f "$candidate_catalog" ]] || { echo "ERROR prepared preview candidates are missing" >&2; exit 7; }
[[ "$(sha256_file "$candidate_config")" == "$expected_config_sha256" ]] || { echo "ERROR prepared config digest mismatch" >&2; exit 7; }
[[ "$(sha256_file "$candidate_unit")" == "$expected_unit_sha256" ]] || { echo "ERROR prepared unit digest mismatch" >&2; exit 7; }
[[ "$(sha256_file "$candidate_catalog")" == "$expected_catalog_sha256" ]] || { echo "ERROR prepared catalog digest mismatch" >&2; exit 7; }
[[ -x "$mediamtx_bin" ]] || { echo "ERROR MediaMTX binary is not executable" >&2; exit 8; }
id "$service_user" >/dev/null 2>&1 || { echo "ERROR preview relay service user does not exist" >&2; exit 8; }
getent group "$service_group" >/dev/null 2>&1 || { echo "ERROR preview relay service group does not exist" >&2; exit 8; }
chown root:"$service_group" "$state_root" "$active_root"
chmod 0750 "$state_root" "$active_root"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
config_backup="NOT_PRESENT"
unit_backup="NOT_PRESENT"
catalog_backup="NOT_PRESENT"
if [[ -f "$active_config" ]]; then
  config_backup="$backup_root/mediamtx.$stamp.yml"
  install -o root -g root -m 0600 "$active_config" "$config_backup"
fi
if [[ -f "$unit_target" ]]; then
  unit_backup="$backup_root/$service_name.$stamp"
  install -o root -g root -m 0600 "$unit_target" "$unit_backup"
fi
if [[ -f "$active_catalog" ]]; then
  catalog_backup="$backup_root/camera-preview-catalog.$stamp.json"
  install -o root -g root -m 0600 "$active_catalog" "$catalog_backup"
fi

install -o root -g "$service_group" -m 0640 "$candidate_config" "${active_config}.next"
install -o root -g root -m 0644 "$candidate_unit" "${unit_target}.next"
install -o root -g root -m 0600 "$candidate_catalog" "${active_catalog}.next"
mv -f "${active_config}.next" "$active_config"
mv -f "${unit_target}.next" "$unit_target"
mv -f "${active_catalog}.next" "$active_catalog"

systemctl daemon-reload
if ! systemctl enable --now "$service_name"; then
  echo "ERROR preview relay activation failed; automatic rollback is not authorized" >&2
  printf 'CONFIG_BACKUP=%s\n' "$config_backup" >&2
  printf 'UNIT_BACKUP=%s\n' "$unit_backup" >&2
  printf 'CATALOG_BACKUP=%s\n' "$catalog_backup" >&2
  printf 'AUTOMATIC_ROLLBACK=NO\n' >&2
  exit 30
fi
if ! systemctl restart "$service_name"; then
  echo "ERROR preview relay restart failed; automatic rollback is not authorized" >&2
  printf 'CONFIG_BACKUP=%s\n' "$config_backup" >&2
  printf 'UNIT_BACKUP=%s\n' "$unit_backup" >&2
  printf 'AUTOMATIC_ROLLBACK=NO\n' >&2
  exit 31
fi
systemctl is-active --quiet "$service_name" || { echo "ERROR preview relay is not active" >&2; exit 32; }
check_listener || { echo "ERROR private preview relay listener is not reachable" >&2; exit 33; }

printf 'ACTIVATED_PREVIEW_RELAY=YES\n'
printf 'PRIVATE_PREVIEW_RELAY_TCP=PASS\n'
printf 'SANITIZED_CATALOG=%s\n' "$active_catalog"
printf 'CONFIG_BACKUP=%s\n' "$config_backup"
printf 'UNIT_BACKUP=%s\n' "$unit_backup"
printf 'CATALOG_BACKUP=%s\n' "$catalog_backup"
printf 'CAM1_RELAY_CHANGED=NO\n'
printf 'AI_WORKER_CHANGED=NO\n'
printf 'AUTOMATIC_ROLLBACK=NO\n'
printf 'SECRETS_DISPLAYED=NO\n'
