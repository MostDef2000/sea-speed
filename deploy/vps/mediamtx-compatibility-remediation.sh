#!/usr/bin/env bash
set -euo pipefail

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

validate_relay_url() {
  python3 - "$relay_url" <<'PY'
import ipaddress
import sys
from urllib.parse import urlsplit
nets = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
try:
    value = urlsplit(sys.argv[1])
    host = value.hostname
    port = value.port or 554
    address = ipaddress.ip_address(host)
except Exception:
    raise SystemExit(1)
if value.scheme.lower() != "rtsp" or value.username is not None or value.password is not None:
    raise SystemExit(1)
if value.path.rstrip("/") != "/cam1" or address.version != 4 or not any(address in net for net in nets):
    raise SystemExit(1)
if not (1 <= port <= 65535):
    raise SystemExit(1)
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
PY
}

validate_config_security() {
  [[ -f "$config" && ! -L "$config" ]] || { echo "ERROR MediaMTX config must be a regular non-symlink file" >&2; exit 5; }
  local mode numeric
  mode="$(stat -c '%a' "$config")"
  numeric=$((8#$mode))
  if (( numeric & 0007 )); then
    echo "ERROR active MediaMTX config must not be world-accessible" >&2
    exit 5
  fi
}

validate_installed_binary() {
  [[ -f "$installed_binary" && ! -L "$installed_binary" ]] || { echo "ERROR installed MediaMTX binary must be a regular non-symlink file" >&2; exit 6; }
  [[ -x "$installed_binary" ]] || { echo "ERROR installed MediaMTX binary must be executable" >&2; exit 6; }
  local execstart
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

prepare_state() {
  install -d -o root -g root -m 0700 "$state_root" "$candidate_root" "$backup_root" "$marker_root"
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
  local cmd=(ffmpeg -hide_banner -loglevel error)
  if [[ "$transport" == "rtsp-tcp" ]]; then
    cmd+=( -rtsp_transport tcp )
  fi
  cmd+=( -i "$url" -map 0:v:0 -frames:v 2 -f null - )
  timeout 25 "${cmd[@]}" >/dev/null 2>&1
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

validate_common() {
  validate_service_name
  command -v python3 >/dev/null 2>&1 || { echo "ERROR python3 is required" >&2; exit 4; }
  command -v systemctl >/dev/null 2>&1 || { echo "ERROR systemctl is required" >&2; exit 4; }
  command -v runuser >/dev/null 2>&1 || { echo "ERROR runuser is required" >&2; exit 4; }
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
  printf 'INSTALLED_VERSION=%s\n' "$($installed_binary --version 2>&1 | head -n 1 | tr -d '\r')"
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

require_root
[[ -n "$config" ]] || { echo "ERROR --config is required" >&2; exit 2; }
[[ -n "$relay_url" ]] || { echo "ERROR --relay-url is required" >&2; exit 2; }
validate_relay_url || { echo "ERROR relay URL must be credential-free RFC1918 RTSP ending in /cam1" >&2; exit 3; }
validate_config_security
validate_installed_binary
systemctl is-active --quiet "$service_name" || { echo "ERROR MediaMTX service must be active before compatibility remediation" >&2; exit 6; }
prepare_state

identity="$(service_identity)"
service_user="$(printf '%s\n' "$identity" | sed -n '1p')"
service_group="$(printf '%s\n' "$identity" | sed -n '2p')"

if [[ "$command" == "prepare" ]]; then
  [[ -n "$candidate_archive" ]] || { echo "ERROR --candidate-archive is required" >&2; exit 2; }
  [[ -n "$candidate_version" ]] || { echo "ERROR --candidate-version is required" >&2; exit 2; }
  [[ -n "$expected_archive_sha256" ]] || { echo "ERROR --expected-archive-sha256 is required" >&2; exit 2; }
  validate_version "$candidate_version" || { echo "ERROR invalid candidate version" >&2; exit 3; }
  validate_sha256 "$expected_archive_sha256" || { echo "ERROR invalid archive SHA-256" >&2; exit 3; }
  [[ -f "$candidate_archive" && ! -L "$candidate_archive" ]] || { echo "ERROR candidate archive must be a regular non-symlink file" >&2; exit 7; }

  actual_archive_sha="$(sha256sum "$candidate_archive" | awk '{print $1}')"
  [[ "$actual_archive_sha" == "$expected_archive_sha256" ]] || { echo "ERROR candidate archive digest mismatch" >&2; exit 7; }

  rtsp_port="$(parse_loopback_address "$canary_rtsp_address")" || { echo "ERROR canary RTSP address must be loopback with an unprivileged port" >&2; exit 3; }
  hls_port="$(parse_loopback_address "$canary_hls_address")" || { echo "ERROR canary HLS address must be loopback with an unprivileged port" >&2; exit 3; }
  [[ "$rtsp_port" != "$hls_port" ]] || { echo "ERROR canary RTSP and HLS ports must differ" >&2; exit 3; }
  check_port_free "$rtsp_port" || { echo "ERROR canary RTSP port is already in use" >&2; exit 8; }
  check_port_free "$hls_port" || { echo "ERROR canary HLS port is already in use" >&2; exit 8; }

  extract_root="$(mktemp -d)"
  cleanup_extract() { rm -rf "$extract_root"; }
  trap cleanup_extract EXIT
  tar -xzf "$candidate_archive" -C "$extract_root" mediamtx
  extracted="$extract_root/mediamtx"
  [[ -f "$extracted" && ! -L "$extracted" ]] || { echo "ERROR release archive does not contain a regular mediamtx binary" >&2; exit 7; }
  chmod 0700 "$extracted"
  version_output="$($extracted --version 2>&1 | head -n 1 | tr -d '\r')"
  printf '%s\n' "$version_output" | grep -F -- "$candidate_version" >/dev/null || {
    echo "ERROR extracted MediaMTX version does not match --candidate-version" >&2
    exit 7
  }

  candidate_sha="$(sha256sum "$extracted" | awk '{print $1}')"
  installed_sha="$(sha256sum "$installed_binary" | awk '{print $1}')"
  config_sha="$(sha256sum "$config" | awk '{print $1}')"
  [[ "$candidate_sha" != "$installed_sha" ]] || { echo "ERROR candidate binary is identical to installed MediaMTX" >&2; exit 7; }

  persistent_candidate="$candidate_root/mediamtx.$candidate_sha"
  install -o root -g root -m 0700 "$extracted" "$persistent_candidate"

  rm -rf "$run_root"
  install -d -o root -g "$service_group" -m 0750 "$run_root"
  run_binary="$run_root/mediamtx"
  run_config="$run_root/mediamtx.yml"
  run_log="$run_root/canary.log"
  install -o root -g "$service_group" -m 0750 "$persistent_candidate" "$run_binary"
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
rtmp: no
hls: yes
hlsAddress: "$canary_hls_address"
hlsVariant: mpegts
webrtc: no
srt: no
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

  canary_pid=""
  cleanup_canary() {
    if [[ -n "$canary_pid" ]] && kill -0 "$canary_pid" 2>/dev/null; then
      kill "$canary_pid" 2>/dev/null || true
      wait "$canary_pid" 2>/dev/null || true
    fi
    rm -rf "$run_root"
    cleanup_extract
  }
  trap cleanup_canary EXIT

  runuser -u "$service_user" -- "$run_binary" "$run_config" >>"$run_log" 2>&1 &
  canary_pid=$!
  sleep 1
  kill -0 "$canary_pid" 2>/dev/null || { echo "ERROR compatibility canary exited during startup" >&2; exit 20; }

  canary_rtsp_url="rtsp://127.0.0.1:${rtsp_port}/cam1"
  canary_hls_url="http://127.0.0.1:${hls_port}/cam1/index.m3u8"

  rtsp_ok=false
  for _ in {1..10}; do
    if probe_two_frames "$canary_rtsp_url" rtsp-tcp; then
      rtsp_ok=true
      break
    fi
    sleep 1
  done
  [[ "$rtsp_ok" == true ]] || { echo "ERROR compatibility canary did not expose advancing RTSP media" >&2; exit 21; }

  hls_ok=false
  for _ in {1..10}; do
    if curl --fail --silent --show-error --max-time 5 "$canary_hls_url" | grep -q '^#EXTM3U' && probe_two_frames "$canary_hls_url"; then
      hls_ok=true
      break
    fi
    sleep 1
  done
  [[ "$hls_ok" == true ]] || { echo "ERROR compatibility canary did not expose advancing HLS media" >&2; exit 22; }

  stream_info="$(probe_stream_info "$canary_rtsp_url" rtsp-tcp || true)"
  marker="$marker_root/$candidate_sha.ok"
  cat > "$marker" <<EOF_MARKER
candidate_sha256=$candidate_sha
candidate_version=$candidate_version
archive_sha256=$actual_archive_sha
installed_sha256=$installed_sha
config_sha256=$config_sha
EOF_MARKER
  chown root:root "$marker"
  chmod 0600 "$marker"

  printf 'COMPATIBILITY_CANARY=PASS\n'
  printf 'CANDIDATE_VERSION=%s\n' "$candidate_version"
  printf 'CANDIDATE_ARCHIVE_SHA256=%s\n' "$actual_archive_sha"
  printf 'CANDIDATE_BINARY_SHA256=%s\n' "$candidate_sha"
  printf 'INSTALLED_BINARY_SHA256=%s\n' "$installed_sha"
  printf 'ACTIVE_CONFIG_SHA256=%s\n' "$config_sha"
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
[[ "$(stat -c '%a' "$persistent_candidate")" == "700" ]] || { echo "ERROR prepared candidate mode must be 700" >&2; exit 7; }
[[ "$(stat -c '%a' "$marker")" == "600" ]] || { echo "ERROR canary marker mode must be 600" >&2; exit 7; }
actual_candidate_sha="$(sha256sum "$persistent_candidate" | awk '{print $1}')"
[[ "$actual_candidate_sha" == "$expected_candidate_sha256" ]] || { echo "ERROR prepared candidate digest mismatch" >&2; exit 7; }

marker_candidate_sha="$(sed -n 's/^candidate_sha256=//p' "$marker")"
marker_candidate_version="$(sed -n 's/^candidate_version=//p' "$marker")"
marker_installed_sha="$(sed -n 's/^installed_sha256=//p' "$marker")"
marker_config_sha="$(sed -n 's/^config_sha256=//p' "$marker")"
[[ "$marker_candidate_sha" == "$expected_candidate_sha256" ]] || { echo "ERROR canary marker candidate mismatch" >&2; exit 7; }
validate_version "$marker_candidate_version" || { echo "ERROR canary marker version is invalid" >&2; exit 7; }
current_installed_sha="$(sha256sum "$installed_binary" | awk '{print $1}')"
current_config_sha="$(sha256sum "$config" | awk '{print $1}')"
[[ "$current_installed_sha" == "$marker_installed_sha" ]] || { echo "ERROR installed MediaMTX changed after canary; prepare again" >&2; exit 7; }
[[ "$current_config_sha" == "$marker_config_sha" ]] || { echo "ERROR active MediaMTX config changed after canary; prepare again" >&2; exit 7; }
[[ "$expected_candidate_sha256" != "$current_installed_sha" ]] || { echo "ERROR candidate is already installed" >&2; exit 7; }

owner="$(stat -c '%u' "$installed_binary")"
group="$(stat -c '%g' "$installed_binary")"
mode="$(stat -c '%a' "$installed_binary")"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$backup_root/mediamtx-bin.$timestamp.$current_installed_sha"
install -o root -g root -m 0700 "$installed_binary" "$backup"
install -o "$owner" -g "$group" -m "$mode" "$persistent_candidate" "${installed_binary}.next"
mv -f "${installed_binary}.next" "$installed_binary"

if ! systemctl restart "$service_name"; then
  echo "ERROR VPS MediaMTX restart failed after binary replacement; automatic rollback is not authorized" >&2
  printf 'PREVIOUS_BINARY_BACKUP=%s\n' "$backup" >&2
  exit 30
fi
if ! systemctl is-active --quiet "$service_name"; then
  echo "ERROR VPS MediaMTX is not active after binary replacement; automatic rollback is not authorized" >&2
  printf 'PREVIOUS_BINARY_BACKUP=%s\n' "$backup" >&2
  exit 31
fi

version_output="$($installed_binary --version 2>&1 | head -n 1 | tr -d '\r')"
printf '%s\n' "$version_output" | grep -F -- "$marker_candidate_version" >/dev/null || {
  echo "ERROR active MediaMTX version does not match the canary-approved candidate; automatic rollback is not authorized" >&2
  printf 'PREVIOUS_BINARY_BACKUP=%s\n' "$backup" >&2
  exit 32
}

if ! probe_two_frames "$production_hls_url"; then
  echo "ERROR canonical VPS-local HLS did not produce advancing media after binary replacement; automatic rollback is not authorized" >&2
  printf 'PREVIOUS_BINARY_BACKUP=%s\n' "$backup" >&2
  exit 33
fi

printf 'MEDIAMTX_COMPATIBILITY_ACTIVATED=YES\n'
printf 'CANDIDATE_VERSION=%s\n' "$marker_candidate_version"
printf 'CANDIDATE_BINARY_SHA256=%s\n' "$expected_candidate_sha256"
printf 'PREVIOUS_BINARY_SHA256=%s\n' "$current_installed_sha"
printf 'PREVIOUS_BINARY_BACKUP=%s\n' "$backup"
printf 'MEDIAMTX_ACTIVE=YES\n'
printf 'LOCAL_CANONICAL_HLS_MEDIA=PASS\n'
printf 'PRODUCTION_BINARY_CHANGED=YES\n'
printf 'AUTOMATIC_ROLLBACK=NO\n'
printf 'SECRETS_DISPLAYED=NO\n'
