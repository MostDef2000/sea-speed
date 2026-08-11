#!/usr/bin/env bash
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
export PATH LC_ALL
umask 077

usage() {
  cat <<'USAGE'
Usage:
  mediamtx-compatibility-remediation.sh prepare --config PATH --relay-url rtsp://PRIVATE_IP:PORT/cam1 --candidate-archive PATH --candidate-version VERSION --expected-archive-sha256 SHA256 [options]
  mediamtx-compatibility-remediation.sh activate --config PATH --relay-url rtsp://PRIVATE_IP:PORT/cam1 --expected-candidate-sha256 SHA256 [options]
  mediamtx-compatibility-remediation.sh status [options]

Options:
  --service NAME              VPS MediaMTX service (default: mediamtx.service)
  --installed-binary PATH     Active MediaMTX binary (default: /usr/local/bin/mediamtx)
  --state-root PATH           Root-only compatibility state (default: /var/lib/sea-speed-mediamtx-compat)
  --canary-rtsp-address ADDR  Loopback-only RTSP listener (default: 127.0.0.1:18954)
  --canary-hls-address ADDR   Loopback-only HLS listener (default: 127.0.0.1:18888)
  --production-hls-url URL    Existing VPS-local canonical HLS URL (default: http://127.0.0.1:8888/cam1/index.m3u8)

prepare verifies an externally staged official release archive by its approved
SHA-256, extracts only the MediaMTX binary, runs a loopback-only canary as the
existing MediaMTX service user against the credential-free Ubuntu cam1 relay,
and records a digest-bound canary marker. It does not replace the production
binary and does not restart production MediaMTX.

activate is fail-closed: it requires the exact candidate digest returned by a
successful prepare, requires the active config and installed binary to be
unchanged since that canary, preserves a root-only binary backup, atomically
replaces only the MediaMTX executable, restarts only the MediaMTX service and
requires actual VPS-local canonical HLS media. Automatic rollback is not
performed.
USAGE
}

command="${1:-}"
case "$command" in
  prepare|activate|status) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "ERROR unknown command: $command" >&2; usage >&2; exit 2 ;;
esac

config=""
relay_url=""
candidate_archive=""
candidate_version=""
expected_archive_sha256=""
expected_candidate_sha256=""
service_name="mediamtx.service"
installed_binary="/usr/local/bin/mediamtx"
state_root="/var/lib/sea-speed-mediamtx-compat"
canary_rtsp_address="127.0.0.1:18954"
canary_hls_address="127.0.0.1:18888"
production_hls_url="http://127.0.0.1:8888/cam1/index.m3u8"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) [[ $# -ge 2 ]] || { echo "ERROR --config requires a path" >&2; exit 2; }; config="$2"; shift 2 ;;
    --relay-url) [[ $# -ge 2 ]] || { echo "ERROR --relay-url requires a URL" >&2; exit 2; }; relay_url="$2"; shift 2 ;;
    --candidate-archive) [[ $# -ge 2 ]] || { echo "ERROR --candidate-archive requires a path" >&2; exit 2; }; candidate_archive="$2"; shift 2 ;;
    --candidate-version) [[ $# -ge 2 ]] || { echo "ERROR --candidate-version requires a version" >&2; exit 2; }; candidate_version="$2"; shift 2 ;;
    --expected-archive-sha256) [[ $# -ge 2 ]] || { echo "ERROR --expected-archive-sha256 requires a digest" >&2; exit 2; }; expected_archive_sha256="$2"; shift 2 ;;
    --expected-candidate-sha256) [[ $# -ge 2 ]] || { echo "ERROR --expected-candidate-sha256 requires a digest" >&2; exit 2; }; expected_candidate_sha256="$2"; shift 2 ;;
    --service) [[ $# -ge 2 ]] || { echo "ERROR --service requires a name" >&2; exit 2; }; service_name="$2"; shift 2 ;;
    --installed-binary) [[ $# -ge 2 ]] || { echo "ERROR --installed-binary requires a path" >&2; exit 2; }; installed_binary="$2"; shift 2 ;;
    --state-root) [[ $# -ge 2 ]] || { echo "ERROR --state-root requires a path" >&2; exit 2; }; state_root="$2"; shift 2 ;;
    --canary-rtsp-address) [[ $# -ge 2 ]] || { echo "ERROR --canary-rtsp-address requires an address" >&2; exit 2; }; canary_rtsp_address="$2"; shift 2 ;;
    --canary-hls-address) [[ $# -ge 2 ]] || { echo "ERROR --canary-hls-address requires an address" >&2; exit 2; }; canary_hls_address="$2"; shift 2 ;;
    --production-hls-url) [[ $# -ge 2 ]] || { echo "ERROR --production-hls-url requires a URL" >&2; exit 2; }; production_hls_url="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

candidate_root="$state_root/candidates"
backup_root="$state_root/backups"
marker_root="$state_root/canary"
diagnostic_root="$state_root/diagnostics"
activation_root="$state_root/activation"
run_root="/run/sea-speed-mediamtx-canary"

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

validate_sha256() {
  [[ "$1" =~ ^[0-9a-f]{64}$ ]]
}

validate_version() {
  [[ "$1" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+$ ]]
}

validate_state_root() {
  [[ "$state_root" =~ ^/var/lib/sea-speed-mediamtx-compat[A-Za-z0-9._-]*$ ]] || {
    echo "ERROR state root must be a dedicated absolute path under /var/lib" >&2
    exit 3
  }
}

validate_relay_url() {
  python3 - "$relay_url" <<'PY'
import ipaddress
import sys
from urllib.parse import urlsplit
nets = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
try:
    raw = sys.argv[1]
    if any(ord(char) < 32 or ord(char) == 127 for char in raw):
        raise ValueError()
    value = urlsplit(raw)
    host = value.hostname
    port = value.port
    address = ipaddress.ip_address(host)
except Exception:
    raise SystemExit(1)
if value.scheme.lower() != "rtsp" or value.username is not None or value.password is not None:
    raise SystemExit(1)
if value.path != "/cam1" or value.query or value.fragment:
    raise SystemExit(1)
if address.version != 4 or not any(address in net for net in nets):
    raise SystemExit(1)
if port is None or not (1 <= port <= 65535):
    raise SystemExit(1)
if raw != f"rtsp://{address}:{port}/cam1":
    raise SystemExit(1)
print(address)
PY
}

parse_loopback_address() {
  python3 - "$1" <<'PY'
import sys
value = sys.argv[1]
try:
    host, raw_port = value.rsplit(":", 1)
    port = int(raw_port)
except Exception:
    raise SystemExit(1)
if host != "127.0.0.1" or not (1024 <= port <= 65535):
    raise SystemExit(1)
print(port)
PY
}

validate_production_hls_url() {
  python3 - "$production_hls_url" <<'PY'
import sys
from urllib.parse import urlsplit
value = urlsplit(sys.argv[1])
if value.scheme != "http" or value.hostname != "127.0.0.1":
    raise SystemExit(1)
if value.username is not None or value.password is not None:
    raise SystemExit(1)
if value.path != "/cam1/index.m3u8":
    raise SystemExit(1)
if value.query or value.fragment:
    raise SystemExit(1)
PY
}

validate_config_security() {
  [[ -f "$config" && ! -L "$config" ]] || { echo "ERROR MediaMTX config must be a regular non-symlink file" >&2; exit 5; }
  [[ "$config" == /* && "$(readlink -f "$config")" == "$config" ]] || { echo "ERROR MediaMTX config path must be absolute and canonical" >&2; exit 5; }
  [[ "$(stat -c '%u' "$config")" == 0 ]] || { echo "ERROR active MediaMTX config must be owned by root" >&2; exit 5; }
  local mode numeric parent
  mode="$(stat -c '%a' "$config")"
  numeric=$((8#$mode))
  if (( numeric & 0022 || numeric & 0007 )); then
    echo "ERROR active MediaMTX config must not be writable by group or accessible by others" >&2
    exit 5
  fi
  parent="$(dirname "$config")"
  while [[ "$parent" != / ]]; do
    [[ "$(stat -c '%u' "$parent")" == 0 ]] || { echo "ERROR MediaMTX config parent directories must be owned by root" >&2; exit 5; }
    numeric=$((8#$(stat -c '%a' "$parent")))
    (( (numeric & 0022) == 0 )) || { echo "ERROR MediaMTX config parent directories must not be group- or world-writable" >&2; exit 5; }
    parent="$(dirname "$parent")"
  done
}

validate_installed_binary() {
  [[ -f "$installed_binary" && ! -L "$installed_binary" ]] || { echo "ERROR installed MediaMTX binary must be a regular non-symlink file" >&2; exit 6; }
  [[ "$installed_binary" == /* && "$(readlink -f "$installed_binary")" == "$installed_binary" ]] || { echo "ERROR installed MediaMTX binary path must be absolute and canonical" >&2; exit 6; }
  [[ "$(stat -c '%u' "$installed_binary")" == 0 ]] || { echo "ERROR installed MediaMTX binary must be owned by root" >&2; exit 6; }
  [[ -x "$installed_binary" ]] || { echo "ERROR installed MediaMTX binary must be executable" >&2; exit 6; }
  local execstart mode numeric parent
  mode="$(stat -c '%a' "$installed_binary")"
  numeric=$((8#$mode))
  (( (numeric & 0022) == 0 )) || { echo "ERROR installed MediaMTX binary must not be group- or world-writable" >&2; exit 6; }
  parent="$(dirname "$installed_binary")"
  while [[ "$parent" != / ]]; do
    [[ "$(stat -c '%u' "$parent")" == 0 ]] || { echo "ERROR installed MediaMTX parent directories must be owned by root" >&2; exit 6; }
    numeric=$((8#$(stat -c '%a' "$parent")))
    (( (numeric & 0022) == 0 )) || { echo "ERROR installed MediaMTX parent directories must not be group- or world-writable" >&2; exit 6; }
    parent="$(dirname "$parent")"
  done
  execstart="$(systemctl show "$service_name" -p ExecStart --value)"
  printf '%s\n' "$execstart" | grep -F -- "$installed_binary" >/dev/null || {
    echo "ERROR MediaMTX service ExecStart does not use the expected installed binary" >&2
    exit 6
  }
}

service_identity() {
  local user group
  user="$(systemctl show "$service_name" -p User --value)"
  group="$(systemctl show "$service_name" -p Group --value)"
  [[ -n "$user" && "$user" != "root" ]] || { echo "ERROR MediaMTX service must use an explicit non-root user" >&2; exit 6; }
  id "$user" >/dev/null 2>&1 || { echo "ERROR MediaMTX service user does not exist" >&2; exit 6; }
  if [[ -z "$group" ]]; then
    group="$(id -gn "$user")"
  fi
  printf '%s\n%s\n' "$user" "$group"
}

service_contract_sha256() {
  local environment environment_files dropins working_directory fragment execstart unit_user unit_group unit_umask
  local supplementary_groups dynamic_user root_directory root_image fragment_sha fragment_mode need_reload
  local exec_condition exec_start_pre exec_start_post exec_stop exec_stop_post exec_reload pam_name
  environment="$(systemctl show "$service_name" -p Environment --value)" || return 1
  environment_files="$(systemctl show "$service_name" -p EnvironmentFiles --value)" || return 1
  dropins="$(systemctl show "$service_name" -p DropInPaths --value)" || return 1
  working_directory="$(systemctl show "$service_name" -p WorkingDirectory --value)" || return 1
  fragment="$(systemctl show "$service_name" -p FragmentPath --value)" || return 1
  execstart="$(systemctl show "$service_name" -p ExecStart --value)" || return 1
  unit_user="$(systemctl show "$service_name" -p User --value)" || return 1
  unit_group="$(systemctl show "$service_name" -p Group --value)" || return 1
  unit_umask="$(systemctl show "$service_name" -p UMask --value)" || return 1
  supplementary_groups="$(systemctl show "$service_name" -p SupplementaryGroups --value)" || return 1
  dynamic_user="$(systemctl show "$service_name" -p DynamicUser --value)" || return 1
  root_directory="$(systemctl show "$service_name" -p RootDirectory --value)" || return 1
  root_image="$(systemctl show "$service_name" -p RootImage --value)" || return 1
  need_reload="$(systemctl show "$service_name" -p NeedDaemonReload --value)" || return 1
  exec_condition="$(systemctl show "$service_name" -p ExecCondition --value)" || return 1
  exec_start_pre="$(systemctl show "$service_name" -p ExecStartPre --value)" || return 1
  exec_start_post="$(systemctl show "$service_name" -p ExecStartPost --value)" || return 1
  exec_stop="$(systemctl show "$service_name" -p ExecStop --value)" || return 1
  exec_stop_post="$(systemctl show "$service_name" -p ExecStopPost --value)" || return 1
  exec_reload="$(systemctl show "$service_name" -p ExecReload --value)" || return 1
  pam_name="$(systemctl show "$service_name" -p PAMName --value)" || return 1
  [[ -z "$environment" && -z "$environment_files" && -z "$dropins" ]] || return 1
  [[ -z "$working_directory" || "$working_directory" == / ]] || return 1
  [[ -z "$supplementary_groups" && "$dynamic_user" == no && -z "$root_directory" && -z "$root_image" ]] || return 1
  [[ "$need_reload" == no && -z "$exec_condition" && -z "$exec_start_pre" && -z "$exec_start_post" ]] || return 1
  [[ -z "$exec_stop" && -z "$exec_stop_post" && -z "$exec_reload" && -z "$pam_name" ]] || return 1
  [[ "$unit_user" == "$service_user" ]] || return 1
  [[ -z "$unit_group" || "$unit_group" == "$service_group" ]] || return 1
  [[ "$unit_umask" =~ ^[0-7]{4}$ ]] || return 1
  [[ -f "$fragment" && ! -L "$fragment" && "$(stat -c '%u:%g' "$fragment")" == "0:0" ]] || return 1
  fragment_mode="$(stat -c '%a' "$fragment")"
  (( (8#$fragment_mode & 0022) == 0 )) || return 1
  printf '%s\n' "$execstart" | grep -F -- "path=$installed_binary ; argv[]=$installed_binary $config ;" >/dev/null || return 1
  fragment_sha="$(sha256sum "$fragment" | awk '{print $1}')"
  printf 'exec_path=%s\nexec_argv=%s %s\nuser=%s\ngroup=%s\numask=%s\nworking_directory=%s\nfragment=%s\nfragment_sha256=%s\n' \
    "$installed_binary" "$installed_binary" "$config" "$unit_user" "${unit_group:-$service_group}" "$unit_umask" \
    "${working_directory:-/}" "$fragment" "$fragment_sha" | sha256sum | awk '{print $1}'
}

verify_cam1_contract() {
  python3 - "$1" "$relay_url" "$production_hls_url" <<'PY'
import json
import re
import sys
from urllib.parse import urlsplit

try:
    lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
    relay_url = sys.argv[2]
    hls_port = urlsplit(sys.argv[3]).port or 80

    def scalar(raw):
        value = raw.split(" #", 1)[0].strip()
        return str(json.loads(value)) if value.startswith('"') else value

    top = {}
    paths_index = None
    for index, line in enumerate(lines):
        if line and not line[0].isspace() and not line.lstrip().startswith("#"):
            match = re.match(r"^([A-Za-z][A-Za-z0-9]*)\s*:\s*(.*?)\s*$", line)
            if match:
                if match.group(1) in top:
                    raise ValueError()
                top[match.group(1)] = scalar(match.group(2))
                if match.group(1) == "paths":
                    paths_index = index
    if paths_index is None or top.get("hls", "yes") not in ("yes", "true"):
        raise ValueError()
    listen = top.get("hlsAddress", ":8888")
    if int(listen.rsplit(":", 1)[1]) != hls_port:
        raise ValueError()
    if top.get("hlsVariant", "lowLatency") not in ("fmp4", "lowLatency"):
        raise ValueError()

    cam1 = None
    for index in range(paths_index + 1, len(lines)):
        line = lines[index]
        if line and not line[0].isspace():
            break
        if re.match(r"^  cam1\s*:\s*(?:#.*)?$", line):
            if cam1 is not None:
                raise ValueError()
            cam1 = index
    if cam1 is None:
        raise ValueError()
    fields = {}
    for line in lines[cam1 + 1:]:
        if re.match(r"^  \S.*:\s*", line) or (line and not line[0].isspace()):
            break
        match = re.match(r"^    ([A-Za-z][A-Za-z0-9]*)\s*:\s*(.*?)\s*$", line)
        if match:
            if match.group(1) in fields:
                raise ValueError()
            fields[match.group(1)] = scalar(match.group(2))
    if fields.get("source") != relay_url or fields.get("sourceOnDemand") not in ("yes", "true"):
        raise ValueError()
    if fields.get("rtspTransport") != "tcp":
        raise ValueError()
except Exception:
    raise SystemExit(1)
PY
}

stop_transient_unit() {
  local unit="$1" state
  state="$(systemctl show "$unit" -p ActiveState --value 2>/dev/null || true)"
  [[ -n "$state" ]] || return 0
  if ! systemctl stop "$unit" >/dev/null 2>&1; then
    state="$(systemctl show "$unit" -p ActiveState --value 2>/dev/null || true)"
    [[ -z "$state" || "$state" == inactive || "$state" == failed ]] || return 1
  fi
  for _ in {1..50}; do
    state="$(systemctl show "$unit" -p ActiveState --value 2>/dev/null || true)"
    if [[ -z "$state" || "$state" == inactive || "$state" == failed ]]; then
      systemctl reset-failed "$unit" >/dev/null 2>&1 || true
      return 0
    fi
    sleep 0.1
  done
  return 1
}

write_activation_state() {
  local phase="$1" previous_sha="$2" backup="$3" state="$4" temporary
  [[ "$phase" =~ ^(prepared|binary_replaced|complete)$ ]] || return 1
  temporary="$state.tmp.$BASHPID"
  rm -f "$temporary"
  cat > "$temporary" <<EOF_STATE
candidate_sha256=$expected_candidate_sha256
previous_sha256=$previous_sha
backup=$backup
phase=$phase
EOF_STATE
  chown root:root "$temporary"
  chmod 0600 "$temporary"
  mv -f "$temporary" "$state"
}

prepare_state() {
  install -d -o root -g root -m 0700 "$state_root" "$candidate_root" "$backup_root" "$marker_root" "$diagnostic_root" "$activation_root"
}

check_port_free() {
  local port="$1"
  python3 - "$port" <<'PY'
import socket
import sys
port = int(sys.argv[1])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.bind(("127.0.0.1", port))
finally:
    sock.close()
PY
}

probe_two_frames() {
  local url="$1" transport="${2:-}"
  local progress line frames=0
  local cmd=(ffmpeg -nostdin -hide_banner -loglevel error)
  if [[ "$transport" == "rtsp-tcp" ]]; then
    cmd+=( -rtsp_transport tcp )
  fi
  cmd+=( -i "$url" -map 0:v:0 -frames:v 2 -progress pipe:1 -nostats -f null - )
  progress="$(timeout 25 "${cmd[@]}" 2>/dev/null)" || return 1
  while IFS= read -r line; do
    if [[ "$line" =~ ^frame=([0-9]+)$ ]] && (( BASH_REMATCH[1] > frames )); then
      frames="${BASH_REMATCH[1]}"
    fi
  done <<<"$progress"
  (( frames >= 2 ))
}

probe_stream_info() {
  local url="$1" transport="${2:-}"
  local cmd=(ffprobe -v error)
  if [[ "$transport" == "rtsp-tcp" ]]; then
    cmd+=( -rtsp_transport tcp )
  fi
  cmd+=( -select_streams v:0 -show_entries stream=codec_name,width,height -of csv=p=0 "$url" )
  timeout 15 "${cmd[@]}" 2>/dev/null | head -n 1
}

canary_listeners_ready() {
  python3 - "$1" "$2" <<'PY'
import socket
import sys

for raw_port in sys.argv[1:]:
    try:
        with socket.create_connection(("127.0.0.1", int(raw_port)), timeout=0.2):
            pass
    except OSError:
        raise SystemExit(1)
PY
}

preserve_failure_log() {
  local category="$1" source="$2" destination="NONE" reason="LOG_UNAVAILABLE" timestamp
  [[ "$category" =~ ^(VERSION|ACTIVE_CONFIG|STARTUP|STARTUP_READINESS|RUNTIME|RTSP_MEDIA|HLS_MEDIA)$ ]] || category=RUNTIME
  if [[ -f "$source" && ! -L "$source" && "$(stat -c '%s' "$source")" -le 2097152 ]]; then
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    destination="$diagnostic_root/canary.$candidate_sha.$category.$timestamp.$BASHPID.log"
    install -o root -g root -m 0600 "$source" "$destination"
    reason="$(python3 - "$destination" <<'PY'
import sys

text = open(sys.argv[1], encoding="utf-8", errors="replace").read(2 * 1024 * 1024).lower()
if "native moq quic listener" in text and "permission denied" in text:
    print("MOQ_TLS_KEYPAIR_PERMISSION_DENIED")
elif "mpeg-ts variant of hls supports h264 video only" in text:
    print("HLS_MPEGTS_H265_UNSUPPORTED")
elif "unknown field" in text:
    print("CONFIGURATION_UNKNOWN_FIELD")
elif "cannot unmarshal" in text or "invalid configuration" in text:
    print("CONFIGURATION_REJECTED")
elif "address already in use" in text:
    print("LISTENER_ADDRESS_IN_USE")
elif "permission denied" in text:
    print("RUNTIME_PERMISSION_DENIED")
elif "error" in text or "err " in text:
    print("CANDIDATE_REPORTED_ERROR")
else:
    print("UNCLASSIFIED_PROCESS_FAILURE")
PY
)"
  fi
  printf 'CANARY_FAILURE_CATEGORY=%s\nCANARY_FAILURE_REASON=%s\nCANARY_FAILURE_LOG=%s\n' "$category" "$reason" "$destination" >&2
}

validate_common() {
  validate_service_name
  command -v python3 >/dev/null 2>&1 || { echo "ERROR python3 is required" >&2; exit 4; }
  command -v systemctl >/dev/null 2>&1 || { echo "ERROR systemctl is required" >&2; exit 4; }
  command -v flock >/dev/null 2>&1 || { echo "ERROR flock is required" >&2; exit 4; }
  command -v readlink >/dev/null 2>&1 || { echo "ERROR readlink is required" >&2; exit 4; }
  command -v tar >/dev/null 2>&1 || { echo "ERROR tar is required" >&2; exit 4; }
  command -v sha256sum >/dev/null 2>&1 || { echo "ERROR sha256sum is required" >&2; exit 4; }
  command -v ffmpeg >/dev/null 2>&1 || { echo "ERROR ffmpeg is required" >&2; exit 4; }
  command -v ffprobe >/dev/null 2>&1 || { echo "ERROR ffprobe is required" >&2; exit 4; }
  command -v curl >/dev/null 2>&1 || { echo "ERROR curl is required" >&2; exit 4; }
  command -v timeout >/dev/null 2>&1 || { echo "ERROR timeout is required" >&2; exit 4; }
  validate_production_hls_url || { echo "ERROR production HLS URL must be loopback canonical cam1 without userinfo" >&2; exit 3; }
}

validate_common

if [[ "$command" == "status" ]]; then
  validate_installed_binary
  printf 'MEDIAMTX_ENABLED=%s\n' "$(systemctl is-enabled "$service_name" 2>/dev/null || true)"
  printf 'MEDIAMTX_ACTIVE=%s\n' "$(systemctl is-active "$service_name" 2>/dev/null || true)"
  printf 'INSTALLED_BINARY_SHA256=%s\n' "$(sha256sum "$installed_binary" | awk '{print $1}')"
  printf 'INSTALLED_VERSION=NOT_EXECUTED\n'
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

require_root
validate_state_root
[[ -n "$config" ]] || { echo "ERROR --config is required" >&2; exit 2; }
[[ -n "$relay_url" ]] || { echo "ERROR --relay-url is required" >&2; exit 2; }
relay_address="$(validate_relay_url)" || { echo "ERROR relay URL must be credential-free canonical RFC1918 RTSP ending in /cam1" >&2; exit 3; }
validate_config_security
validate_installed_binary
systemctl is-active --quiet "$service_name" || { echo "ERROR MediaMTX service must be active before compatibility remediation" >&2; exit 6; }
prepare_state
exec 9>"$state_root/operation.lock"
chmod 0600 "$state_root/operation.lock"
chown root:root "$state_root/operation.lock"
flock -n 9 || { echo "ERROR another MediaMTX compatibility operation is active" >&2; exit 8; }

identity="$(service_identity)"
service_user="$(printf '%s\n' "$identity" | sed -n '1p')"
service_group="$(printf '%s\n' "$identity" | sed -n '2p')"
service_contract_sha="$(service_contract_sha256)" || { echo "ERROR MediaMTX systemd service contract is not supported for compatibility remediation" >&2; exit 6; }
service_umask="$(systemctl show "$service_name" -p UMask --value)"
tool_sha="$(sha256sum "${BASH_SOURCE[0]}" | awk '{print $1}')"

if [[ "$command" == "prepare" ]]; then
  command -v systemd-run >/dev/null 2>&1 || { echo "ERROR systemd-run is required for the active-config compatibility sandbox" >&2; exit 4; }
  systemd_version="$(systemd-run --version | awk 'NR == 1 {print $2}')"
  [[ "$systemd_version" =~ ^[0-9]+$ ]] && (( systemd_version >= 247 )) || { echo "ERROR systemd 247 or newer is required for candidate isolation" >&2; exit 4; }
  [[ -n "$candidate_archive" ]] || { echo "ERROR --candidate-archive is required" >&2; exit 2; }
  [[ -n "$candidate_version" ]] || { echo "ERROR --candidate-version is required" >&2; exit 2; }
  [[ -n "$expected_archive_sha256" ]] || { echo "ERROR --expected-archive-sha256 is required" >&2; exit 2; }
  validate_version "$candidate_version" || { echo "ERROR invalid candidate version" >&2; exit 3; }
  validate_sha256 "$expected_archive_sha256" || { echo "ERROR invalid archive SHA-256" >&2; exit 3; }
  [[ -f "$candidate_archive" && ! -L "$candidate_archive" ]] || { echo "ERROR candidate archive must be a regular non-symlink file" >&2; exit 7; }

  rtsp_port="$(parse_loopback_address "$canary_rtsp_address")" || { echo "ERROR canary RTSP address must be loopback with an unprivileged port" >&2; exit 3; }
  hls_port="$(parse_loopback_address "$canary_hls_address")" || { echo "ERROR canary HLS address must be loopback with an unprivileged port" >&2; exit 3; }
  [[ "$rtsp_port" != "$hls_port" ]] || { echo "ERROR canary RTSP and HLS ports must differ" >&2; exit 3; }
  check_port_free "$rtsp_port" || { echo "ERROR canary RTSP port is already in use" >&2; exit 8; }
  check_port_free "$hls_port" || { echo "ERROR canary HLS port is already in use" >&2; exit 8; }

  extract_root="$(mktemp -d)"
  chown root:"$service_group" "$extract_root"
  chmod 0750 "$extract_root"
  cleanup_extract() { rm -rf "$extract_root"; }
  trap cleanup_extract EXIT
  staged_archive="$extract_root/candidate.tar.gz"
  install -o root -g root -m 0600 "$candidate_archive" "$staged_archive"
  actual_archive_sha="$(sha256sum "$staged_archive" | awk '{print $1}')"
  [[ "$actual_archive_sha" == "$expected_archive_sha256" ]] || { echo "ERROR candidate archive digest mismatch" >&2; exit 7; }
  tar -xzf "$staged_archive" -C "$extract_root" mediamtx
  extracted="$extract_root/mediamtx"
  [[ -f "$extracted" && ! -L "$extracted" ]] || { echo "ERROR release archive does not contain a regular mediamtx binary" >&2; exit 7; }
  chown root:"$service_group" "$extracted"
  chmod 0750 "$extracted"
  candidate_sha="$(sha256sum "$extracted" | awk '{print $1}')"

  installed_sha="$(sha256sum "$installed_binary" | awk '{print $1}')"
  [[ "$candidate_sha" != "$installed_sha" ]] || { echo "ERROR candidate binary is identical to installed MediaMTX" >&2; exit 7; }

  persistent_candidate="$candidate_root/mediamtx.$candidate_sha"
  install -o root -g root -m 0700 "$extracted" "$persistent_candidate"

  rm -rf "$run_root"
  install -d -o root -g "$service_group" -m 0750 "$run_root"
  run_binary="$run_root/mediamtx"
  run_config="$run_root/mediamtx.yml"
  active_config="$run_root/active-mediamtx.yml"
  run_log="$run_root/canary.log"
  active_config_log="$run_root/active-config.log"
  version_log="$run_root/version.log"
  install -o root -g "$service_group" -m 0750 "$persistent_candidate" "$run_binary"
  install -o root -g "$service_group" -m 0640 "$config" "$active_config"
  config_sha="$(sha256sum "$active_config" | awk '{print $1}')"
  [[ "$(sha256sum "$config" | awk '{print $1}')" == "$config_sha" ]] || {
    echo "ERROR active MediaMTX config changed while creating the compatibility snapshot" >&2
    exit 8
  }
  verify_cam1_contract "$active_config" || { echo "ERROR active MediaMTX cam1 relay or HLS contract does not match the requested compatibility proof" >&2; exit 5; }
  cat > "$run_config" <<EOF_CONFIG
logLevel: info
authMethod: internal
authInternalUsers:
  - user: any
    pass:
    ips: ["127.0.0.1"]
    permissions:
      - action: read
        path: cam1
rtsp: yes
rtspAddress: "$canary_rtsp_address"
rtspTransports: [tcp]
api: no
metrics: no
pprof: no
playback: no
rtmp: no
hls: yes
hlsAddress: "$canary_hls_address"
hlsVariant: fmp4
webrtc: no
srt: no
moq: no
paths:
  cam1:
    source: "$relay_url"
    sourceOnDemand: yes
    sourceOnDemandStartTimeout: 60s
    sourceOnDemandCloseAfter: 60s
    rtspTransport: tcp
EOF_CONFIG
  chown root:"$service_group" "$run_config"
  chmod 0640 "$run_config"
  : > "$run_log"
  chown root:"$service_group" "$run_log"
  chmod 0640 "$run_log"
  : > "$active_config_log"
  chown root:root "$active_config_log"
  chmod 0600 "$active_config_log"
  : > "$version_log"
  chown root:root "$version_log"
  chmod 0600 "$version_log"

  version_unit=""
  config_check_unit=""
  canary_unit=""
  cleanup_canary() {
    local stopped=true
    [[ -z "$version_unit" ]] || stop_transient_unit "$version_unit" || stopped=false
    if [[ -n "$config_check_unit" ]]; then
      stop_transient_unit "$config_check_unit" || stopped=false
    fi
    if [[ -n "$canary_unit" ]]; then
      stop_transient_unit "$canary_unit" || stopped=false
    fi
    if [[ "$stopped" == true ]]; then
      rm -rf "$run_root"
    else
      echo "ERROR transient candidate unit remains active; protected runtime was preserved" >&2
    fi
    cleanup_extract
  }
  trap cleanup_canary EXIT

  sandbox_properties=(
    --property=Type=exec
    --property="User=$service_user"
    --property="Group=$service_group"
    --property="UMask=$service_umask"
    --property=PrivateTmp=yes
    --property=PrivateDevices=yes
    --property=PrivateIPC=yes
    --property=PrivateUsers=self
    --property=ProtectSystem=strict
    --property=ProtectHome=yes
    --property=ProtectControlGroups=yes
    --property=ProtectKernelLogs=yes
    --property=ProtectKernelModules=yes
    --property=ProtectKernelTunables=yes
    --property=ProtectProc=invisible
    --property=ProcSubset=pid
    --property=ProtectClock=yes
    --property=ProtectHostname=yes
    --property=NoNewPrivileges=yes
    --property=RestrictSUIDSGID=yes
    --property=RestrictNamespaces=yes
    --property=LockPersonality=yes
    --property=RestrictRealtime=yes
    --property=RemoveIPC=yes
    --property=KeyringMode=private
    --property=SystemCallArchitectures=native
    --property="RestrictAddressFamilies=AF_INET AF_INET6"
    --property=CapabilityBoundingSet=
    --property=AmbientCapabilities=
    --property=NoExecPaths=/
    --property="ExecPaths=/usr/bin/env $run_binary"
    --property="ReadWritePaths=$run_root"
    --property=KillMode=control-group
    --property=TimeoutStopSec=2s
    --property=TasksMax=128
    --property=MemoryMax=512M
    --property=CPUQuota=100%
  )

  version_unit="sea-speed-mediamtx-version-${BASHPID}.service"
  if ! systemd-run --quiet --wait --unit="$version_unit" --collect \
    "${sandbox_properties[@]}" \
    --property=WorkingDirectory=/ \
    --property=PrivateNetwork=yes \
    --property=RuntimeMaxSec=5s \
    --property="StandardOutput=append:$version_log" \
    --property="StandardError=append:$version_log" \
    /usr/bin/env -i PATH=/usr/bin:/bin HOME=/nonexistent "$run_binary" --version; then
    preserve_failure_log VERSION "$version_log"
    echo "ERROR candidate version proof failed inside the compatibility sandbox" >&2
    exit 7
  fi
  version_unit=""
  version_output="$(tr -d '\r' < "$version_log")"
  [[ "$version_output" == "$candidate_version" ]] || {
    preserve_failure_log VERSION "$version_log"
    echo "ERROR extracted MediaMTX version does not exactly match --candidate-version" >&2
    exit 7
  }

  config_check_unit="sea-speed-mediamtx-config-check-${BASHPID}.service"
  if ! systemd-run --quiet --unit="$config_check_unit" --collect \
    "${sandbox_properties[@]}" \
    --property=WorkingDirectory=/ \
    --property=PrivateNetwork=yes \
    --property="StandardOutput=append:$active_config_log" \
    --property="StandardError=append:$active_config_log" \
    /usr/bin/env -i PATH=/usr/bin:/bin HOME=/nonexistent "$run_binary" "$active_config"; then
    preserve_failure_log ACTIVE_CONFIG "$active_config_log"
    echo "ERROR active-config compatibility sandbox did not start" >&2
    exit 23
  fi
  active_config_ready=false
  for _ in {1..100}; do
    active_config_state="$(systemctl show "$config_check_unit" -p ActiveState --value 2>/dev/null || true)"
    if [[ "$active_config_state" == failed || "$active_config_state" == inactive ]]; then
      break
    fi
    if [[ "$active_config_state" == active ]]; then
      active_config_ready=true
      break
    fi
    sleep 0.1
  done
  if [[ "$active_config_ready" == true ]]; then
    sleep 5
    systemctl is-active --quiet "$config_check_unit" || active_config_ready=false
    if grep -F -- "runOnInit command started" "$active_config_log" >/dev/null 2>&1; then
      active_config_ready=false
    fi
  fi
  if ! stop_transient_unit "$config_check_unit"; then
    preserve_failure_log ACTIVE_CONFIG "$active_config_log"
    echo "ERROR active-config compatibility sandbox did not terminate cleanly" >&2
    exit 23
  fi
  config_check_unit=""
  if [[ "$active_config_ready" != true ]]; then
    preserve_failure_log ACTIVE_CONFIG "$active_config_log"
    echo "ERROR candidate cannot start with the active MediaMTX config in the compatibility sandbox" >&2
    exit 23
  fi

  canary_unit="sea-speed-mediamtx-canary-${BASHPID}.service"
  if ! systemd-run --quiet --unit="$canary_unit" --collect \
    "${sandbox_properties[@]}" \
    --property="WorkingDirectory=$run_root" \
    --property=IPAddressDeny=any \
    --property=IPAddressAllow=127.0.0.0/8 \
    --property="IPAddressAllow=$relay_address/32" \
    --property="StandardOutput=append:$run_log" \
    --property="StandardError=append:$run_log" \
    /usr/bin/env -i PATH=/usr/bin:/bin HOME="$run_root" "$run_binary" "$run_config"; then
    preserve_failure_log STARTUP "$run_log"
    echo "ERROR compatibility canary isolation unit did not start" >&2
    exit 20
  fi
  canary_ready=false
  for _ in {1..100}; do
    if ! systemctl is-active --quiet "$canary_unit"; then
      preserve_failure_log STARTUP "$run_log"
      echo "ERROR compatibility canary exited during startup" >&2
      exit 20
    fi
    if canary_listeners_ready "$rtsp_port" "$hls_port"; then
      canary_ready=true
      break
    fi
    sleep 0.1
  done
  if [[ "$canary_ready" != true ]]; then
    preserve_failure_log STARTUP_READINESS "$run_log"
    echo "ERROR compatibility canary listeners were not ready before the startup deadline" >&2
    exit 20
  fi

  canary_rtsp_url="rtsp://127.0.0.1:${rtsp_port}/cam1"
  canary_hls_url="http://127.0.0.1:${hls_port}/cam1/index.m3u8"
  canary_hls_probe_url="${canary_hls_url}?cookieCheck=1"

  rtsp_ok=false
  for _ in {1..10}; do
    if probe_two_frames "$canary_rtsp_url" rtsp-tcp; then
      rtsp_ok=true
      break
    fi
    if ! systemctl is-active --quiet "$canary_unit"; then
      preserve_failure_log RUNTIME "$run_log"
      echo "ERROR compatibility canary exited before RTSP media proof" >&2
      exit 20
    fi
    sleep 1
  done
  if [[ "$rtsp_ok" != true ]]; then
    preserve_failure_log RTSP_MEDIA "$run_log"
    echo "ERROR compatibility canary did not expose advancing RTSP media" >&2
    exit 21
  fi

  hls_ok=false
  for _ in {1..10}; do
    if curl --fail --silent --show-error --max-time 5 "$canary_hls_probe_url" | grep -q '^#EXTM3U' && probe_two_frames "$canary_hls_probe_url"; then
      hls_ok=true
      break
    fi
    if ! systemctl is-active --quiet "$canary_unit"; then
      preserve_failure_log RUNTIME "$run_log"
      echo "ERROR compatibility canary exited before HLS media proof" >&2
      exit 20
    fi
    sleep 1
  done
  if [[ "$hls_ok" != true ]]; then
    preserve_failure_log HLS_MEDIA "$run_log"
    echo "ERROR compatibility canary did not expose advancing HLS media" >&2
    exit 22
  fi

  stream_info="$(probe_stream_info "$canary_rtsp_url" rtsp-tcp || true)"
  if ! stop_transient_unit "$canary_unit"; then
    preserve_failure_log RUNTIME "$run_log"
    echo "ERROR compatibility canary did not terminate cleanly" >&2
    exit 20
  fi
  canary_unit=""
  marker="$marker_root/$candidate_sha.ok"
  marker_tmp="$marker.tmp.$BASHPID"
  rm -f "$marker_tmp"
  cat > "$marker_tmp" <<EOF_MARKER
candidate_sha256=$candidate_sha
candidate_version=$candidate_version
archive_sha256=$actual_archive_sha
installed_sha256=$installed_sha
config_sha256=$config_sha
service_contract_sha256=$service_contract_sha
tool_sha256=$tool_sha
relay_url=$relay_url
production_hls_url=$production_hls_url
active_config_compatibility=pass
EOF_MARKER
  chown root:root "$marker_tmp"
  chmod 0600 "$marker_tmp"
  mv -f "$marker_tmp" "$marker"

  printf 'COMPATIBILITY_CANARY=PASS\n'
  printf 'CANDIDATE_VERSION=%s\n' "$candidate_version"
  printf 'CANDIDATE_ARCHIVE_SHA256=%s\n' "$actual_archive_sha"
  printf 'CANDIDATE_BINARY_SHA256=%s\n' "$candidate_sha"
  printf 'INSTALLED_BINARY_SHA256=%s\n' "$installed_sha"
  printf 'ACTIVE_CONFIG_SHA256=%s\n' "$config_sha"
  printf 'ACTIVE_CONFIG_COMPATIBILITY=PASS\n'
  printf 'CANARY_SERVICE_USER=%s\n' "$service_user"
  printf 'CANARY_RTSP_BIND=127.0.0.1:%s\n' "$rtsp_port"
  printf 'CANARY_HLS_BIND=127.0.0.1:%s\n' "$hls_port"
  printf 'CANARY_RTSP_MEDIA=PASS\n'
  printf 'CANARY_HLS_MEDIA=PASS\n'
  if [[ -n "$stream_info" ]]; then
    printf 'CANARY_VIDEO_STREAM=%s\n' "$stream_info"
  fi
  printf 'PRODUCTION_BINARY_CHANGED=NO\n'
  printf 'MEDIAMTX_RESTARTED=NO\n'
  printf 'AUTOMATIC_ROLLBACK=NO\n'
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

[[ -n "$expected_candidate_sha256" ]] || { echo "ERROR --expected-candidate-sha256 is required" >&2; exit 2; }
validate_sha256 "$expected_candidate_sha256" || { echo "ERROR invalid candidate SHA-256" >&2; exit 3; }
persistent_candidate="$candidate_root/mediamtx.$expected_candidate_sha256"
marker="$marker_root/$expected_candidate_sha256.ok"
[[ -f "$persistent_candidate" && ! -L "$persistent_candidate" ]] || { echo "ERROR prepared candidate binary is missing" >&2; exit 7; }
[[ -f "$marker" && ! -L "$marker" ]] || { echo "ERROR successful compatibility canary marker is missing" >&2; exit 7; }
[[ "$(stat -c '%u:%g' "$persistent_candidate")" == "0:0" ]] || { echo "ERROR prepared candidate must be owned by root" >&2; exit 7; }
[[ "$(stat -c '%u:%g' "$marker")" == "0:0" ]] || { echo "ERROR canary marker must be owned by root" >&2; exit 7; }
[[ "$(stat -c '%a' "$persistent_candidate")" == "700" ]] || { echo "ERROR prepared candidate mode must be 700" >&2; exit 7; }
[[ "$(stat -c '%a' "$marker")" == "600" ]] || { echo "ERROR canary marker mode must be 600" >&2; exit 7; }
actual_candidate_sha="$(sha256sum "$persistent_candidate" | awk '{print $1}')"
[[ "$actual_candidate_sha" == "$expected_candidate_sha256" ]] || { echo "ERROR prepared candidate digest mismatch" >&2; exit 7; }

marker_candidate_sha="$(sed -n 's/^candidate_sha256=//p' "$marker")"
marker_candidate_version="$(sed -n 's/^candidate_version=//p' "$marker")"
marker_installed_sha="$(sed -n 's/^installed_sha256=//p' "$marker")"
marker_config_sha="$(sed -n 's/^config_sha256=//p' "$marker")"
marker_service_contract_sha="$(sed -n 's/^service_contract_sha256=//p' "$marker")"
marker_tool_sha="$(sed -n 's/^tool_sha256=//p' "$marker")"
marker_relay_url="$(sed -n 's/^relay_url=//p' "$marker")"
marker_production_hls_url="$(sed -n 's/^production_hls_url=//p' "$marker")"
marker_active_config_compatibility="$(sed -n 's/^active_config_compatibility=//p' "$marker")"
[[ "$marker_candidate_sha" == "$expected_candidate_sha256" ]] || { echo "ERROR canary marker candidate mismatch" >&2; exit 7; }
[[ "$marker_active_config_compatibility" == pass ]] || { echo "ERROR active config compatibility proof is missing from canary marker" >&2; exit 7; }
[[ "$marker_service_contract_sha" == "$service_contract_sha" ]] || { echo "ERROR MediaMTX service contract changed after canary; prepare again" >&2; exit 7; }
[[ "$marker_tool_sha" == "$tool_sha" ]] || { echo "ERROR compatibility remediation tool changed after canary; prepare again" >&2; exit 7; }
[[ "$marker_relay_url" == "$relay_url" ]] || { echo "ERROR relay URL differs from the canary marker" >&2; exit 7; }
[[ "$marker_production_hls_url" == "$production_hls_url" ]] || { echo "ERROR production HLS URL differs from the canary marker" >&2; exit 7; }
validate_version "$marker_candidate_version" || { echo "ERROR canary marker version is invalid" >&2; exit 7; }
current_installed_sha="$(sha256sum "$installed_binary" | awk '{print $1}')"
current_config_sha="$(sha256sum "$config" | awk '{print $1}')"
[[ "$current_config_sha" == "$marker_config_sha" ]] || { echo "ERROR active MediaMTX config changed after canary; prepare again" >&2; exit 7; }
verify_cam1_contract "$config" || { echo "ERROR active MediaMTX cam1 relay or HLS contract changed after canary" >&2; exit 7; }

activation_state="$activation_root/$expected_candidate_sha256.state"
activation_next="${installed_binary}.next"
activation_phase=""
previous_sha="$marker_installed_sha"
backup=""
if [[ -e "$activation_state" || -L "$activation_state" ]]; then
  [[ -f "$activation_state" && ! -L "$activation_state" ]] || { echo "ERROR activation state must be a regular non-symlink file" >&2; exit 7; }
  [[ "$(stat -c '%u:%g' "$activation_state")" == "0:0" && "$(stat -c '%a' "$activation_state")" == 600 ]] || {
    echo "ERROR activation state ownership or mode is invalid" >&2
    exit 7
  }
  state_candidate_sha="$(sed -n 's/^candidate_sha256=//p' "$activation_state")"
  state_previous_sha="$(sed -n 's/^previous_sha256=//p' "$activation_state")"
  state_backup="$(sed -n 's/^backup=//p' "$activation_state")"
  activation_phase="$(sed -n 's/^phase=//p' "$activation_state")"
  [[ "$state_candidate_sha" == "$expected_candidate_sha256" && "$state_previous_sha" == "$marker_installed_sha" ]] || {
    echo "ERROR durable activation state does not match the canary marker" >&2
    exit 7
  }
  [[ "$activation_phase" =~ ^(prepared|binary_replaced|complete)$ ]] || { echo "ERROR durable activation phase is invalid" >&2; exit 7; }
  [[ "$state_backup" == "$backup_root"/mediamtx-bin.*."$marker_installed_sha" ]] || { echo "ERROR durable activation backup path is invalid" >&2; exit 7; }
  [[ -f "$state_backup" && ! -L "$state_backup" && "$(readlink -f "$state_backup")" == "$state_backup" ]] || { echo "ERROR durable activation backup is missing" >&2; exit 7; }
  [[ "$(stat -c '%u:%g' "$state_backup")" == "0:0" && "$(stat -c '%a' "$state_backup")" == 700 ]] || { echo "ERROR durable activation backup protection is invalid" >&2; exit 7; }
  [[ "$(sha256sum "$state_backup" | awk '{print $1}')" == "$marker_installed_sha" ]] || { echo "ERROR durable activation backup digest mismatch" >&2; exit 7; }
  backup="$state_backup"
fi

cleanup_activation() { rm -f "$activation_next" 2>/dev/null || true; }
trap cleanup_activation EXIT
activation_interrupted() {
  echo "ERROR activation interrupted; durable state and predecessor backup were preserved when available" >&2
  [[ -z "$backup" ]] || printf 'PREVIOUS_BINARY_BACKUP=%s\n' "$backup" >&2
  exit 40
}
trap activation_interrupted HUP INT TERM

if [[ "$current_installed_sha" == "$marker_installed_sha" ]]; then
  [[ -z "$activation_phase" || "$activation_phase" == prepared ]] || {
    echo "ERROR installed MediaMTX was externally restored after activation began; explicit operator review is required" >&2
    exit 7
  }
  owner="$(stat -c '%u' "$installed_binary")"
  group="$(stat -c '%g' "$installed_binary")"
  mode="$(stat -c '%a' "$installed_binary")"
  if [[ -z "$activation_phase" ]]; then
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    backup="$backup_root/mediamtx-bin.$timestamp.$current_installed_sha"
    install -o root -g root -m 0700 "$installed_binary" "$backup"
    [[ "$(sha256sum "$backup" | awk '{print $1}')" == "$marker_installed_sha" ]] || { echo "ERROR verified predecessor backup digest mismatch" >&2; exit 7; }
    write_activation_state prepared "$marker_installed_sha" "$backup" "$activation_state"
    activation_phase=prepared
  fi

  rm -f "$activation_next"
  install -o "$owner" -g "$group" -m "$mode" "$persistent_candidate" "$activation_next"
  [[ "$(sha256sum "$activation_next" | awk '{print $1}')" == "$expected_candidate_sha256" ]] || { echo "ERROR staged candidate digest mismatch" >&2; exit 7; }
  [[ "$(sha256sum "$installed_binary" | awk '{print $1}')" == "$marker_installed_sha" ]] || { echo "ERROR installed MediaMTX changed at the activation boundary" >&2; exit 7; }
  [[ "$(sha256sum "$config" | awk '{print $1}')" == "$marker_config_sha" ]] || { echo "ERROR active MediaMTX config changed at the activation boundary" >&2; exit 7; }
  [[ "$(service_contract_sha256)" == "$marker_service_contract_sha" ]] || { echo "ERROR MediaMTX service contract changed at the activation boundary" >&2; exit 7; }
  [[ "$(sha256sum "${BASH_SOURCE[0]}" | awk '{print $1}')" == "$marker_tool_sha" ]] || { echo "ERROR remediation tool changed at the activation boundary" >&2; exit 7; }
  verify_cam1_contract "$config" || { echo "ERROR active MediaMTX media contract changed at the activation boundary" >&2; exit 7; }
  mv -f "$activation_next" "$installed_binary"
  write_activation_state binary_replaced "$marker_installed_sha" "$backup" "$activation_state"
  activation_phase=binary_replaced
elif [[ "$current_installed_sha" == "$expected_candidate_sha256" ]]; then
  [[ "$activation_phase" =~ ^(prepared|binary_replaced|complete)$ ]] || {
    echo "ERROR candidate is installed without matching durable activation state" >&2
    exit 7
  }
  if [[ "$activation_phase" == prepared ]]; then
    write_activation_state binary_replaced "$marker_installed_sha" "$backup" "$activation_state"
    activation_phase=binary_replaced
  fi
else
  echo "ERROR installed MediaMTX does not match either the canary predecessor or candidate" >&2
  exit 7
fi

if [[ "$activation_phase" != complete ]]; then
  if ! systemctl restart "$service_name"; then
    echo "ERROR VPS MediaMTX restart failed after binary replacement; automatic rollback is not authorized" >&2
    printf 'PREVIOUS_BINARY_BACKUP=%s\n' "$backup" >&2
    exit 30
  fi
fi
if ! systemctl is-active --quiet "$service_name"; then
  echo "ERROR VPS MediaMTX is not active after binary replacement; automatic rollback is not authorized" >&2
  printf 'PREVIOUS_BINARY_BACKUP=%s\n' "$backup" >&2
  exit 31
fi

main_pid="$(systemctl show "$service_name" -p MainPID --value)"
[[ "$main_pid" =~ ^[1-9][0-9]*$ && -e "/proc/$main_pid/exe" ]] || {
  echo "ERROR active MediaMTX MainPID is unavailable; automatic rollback is not authorized" >&2
  printf 'PREVIOUS_BINARY_BACKUP=%s\n' "$backup" >&2
  exit 32
}
running_executable="$(readlink -f "/proc/$main_pid/exe")"
running_sha="$(sha256sum "/proc/$main_pid/exe" | awk '{print $1}')"
[[ "$running_executable" == "$installed_binary" && "$running_sha" == "$expected_candidate_sha256" ]] || {
  echo "ERROR active MediaMTX process does not use the canary-approved candidate; automatic rollback is not authorized" >&2
  printf 'PREVIOUS_BINARY_BACKUP=%s\n' "$backup" >&2
  exit 32
}

production_hls_probe_url="${production_hls_url}?cookieCheck=1"
production_hls_ok=false
for _ in {1..10}; do
  if probe_two_frames "$production_hls_probe_url"; then
    production_hls_ok=true
    break
  fi
  systemctl is-active --quiet "$service_name" || break
  sleep 1
done
if [[ "$production_hls_ok" != true ]]; then
  echo "ERROR canonical VPS-local HLS did not produce advancing media after binary replacement; automatic rollback is not authorized" >&2
  printf 'PREVIOUS_BINARY_BACKUP=%s\n' "$backup" >&2
  exit 33
fi
write_activation_state complete "$marker_installed_sha" "$backup" "$activation_state"
activation_phase=complete

printf 'MEDIAMTX_COMPATIBILITY_ACTIVATED=YES\n'
printf 'CANDIDATE_VERSION=%s\n' "$marker_candidate_version"
printf 'CANDIDATE_BINARY_SHA256=%s\n' "$expected_candidate_sha256"
printf 'PREVIOUS_BINARY_SHA256=%s\n' "$marker_installed_sha"
printf 'PREVIOUS_BINARY_BACKUP=%s\n' "$backup"
printf 'MEDIAMTX_ACTIVE=YES\n'
printf 'LOCAL_CANONICAL_HLS_MEDIA=PASS\n'
printf 'PRODUCTION_BINARY_CHANGED=YES\n'
printf 'AUTOMATIC_ROLLBACK=NO\n'
printf 'SECRETS_DISPLAYED=NO\n'
