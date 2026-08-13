#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  stage.sh status --bind-ip IP --vps-peer IP [--private-port PORT] [--runtime-root PATH]
  stage.sh stage --bind-ip IP --vps-peer IP --env-file PATH [--private-port PORT] [--runtime-root PATH]

Purpose:
  Stage Sea Speed Authentik on the commissioned Ubuntu worker while keeping
  Authentik's Docker HTTP port loopback-only. A source-restricted socat proxy
  exposes one worker ZeroTier/private IP:port only to the exact VPS private peer.

Production authorization:
  This helper does not grant production permission. The mutating `stage` mode
  may run only inside a separately approved exact-main-SHA PRODUCTION APPROVED
  envelope.
USAGE
}

mode="${1:-}"
case "$mode" in
  status|stage) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "ERROR unknown command: $mode" >&2; usage >&2; exit 2 ;;
esac

bind_ip=""
vps_peer=""
private_port="19000"
env_file=""
runtime_root="/opt/sea-speed-auth"
expected_hostname="${SEA_SPEED_AUTH_EXPECTED_HOSTNAME:-sea-speed-worker}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bind-ip)
      [[ $# -ge 2 ]] || { echo "ERROR --bind-ip requires IPv4" >&2; exit 2; }
      bind_ip="$2"; shift 2 ;;
    --vps-peer)
      [[ $# -ge 2 ]] || { echo "ERROR --vps-peer requires IPv4" >&2; exit 2; }
      vps_peer="$2"; shift 2 ;;
    --private-port)
      [[ $# -ge 2 ]] || { echo "ERROR --private-port requires port" >&2; exit 2; }
      private_port="$2"; shift 2 ;;
    --env-file)
      [[ $# -ge 2 ]] || { echo "ERROR --env-file requires path" >&2; exit 2; }
      env_file="$2"; shift 2 ;;
    --runtime-root)
      [[ $# -ge 2 ]] || { echo "ERROR --runtime-root requires path" >&2; exit 2; }
      runtime_root="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; exit 2 ;;
  esac
done

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/../../../.." && pwd)"
compose_source="$script_dir/compose.yml"
blueprint_source="$repo_root/deploy/vps/authentik/blueprints/sea-speed-auth-v1.yaml"
proxy_unit="/etc/systemd/system/sea-speed-auth-private-proxy.service"

fail() {
  echo "AUTHENTIK_WORKER_STAGE_FAIL=$1" >&2
  exit "${2:-1}"
}

require_base_commands() {
  local name
  for name in python3 ip hostname nproc free df stat grep awk sed install systemctl ss curl; do
    command -v "$name" >/dev/null 2>&1 || fail "MISSING_${name}" 40
  done
}

validate_network() {
  [[ -n "$bind_ip" ]] || fail "BIND_IP_REQUIRED" 41
  [[ -n "$vps_peer" ]] || fail "VPS_PEER_REQUIRED" 41
  python3 - "$bind_ip" "$vps_peer" "$private_port" <<'PY'
import ipaddress
import sys
bind_raw, peer_raw, port_raw = sys.argv[1:]
networks = tuple(ipaddress.ip_network(x) for x in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
for label, raw in (("bind", bind_raw), ("peer", peer_raw)):
    try:
        value = ipaddress.ip_address(raw)
    except ValueError as exc:
        raise SystemExit(f"ERROR {label} must be a literal IPv4: {exc}")
    if value.version != 4 or value.is_loopback or not any(value in network for network in networks):
        raise SystemExit(f"ERROR {label} must be a non-loopback RFC1918 IPv4")
try:
    port = int(port_raw)
except ValueError as exc:
    raise SystemExit(f"ERROR invalid private port: {exc}")
if not 1024 <= port <= 65535:
    raise SystemExit("ERROR private port must be 1024..65535")
if bind_raw == peer_raw:
    raise SystemExit("ERROR bind IP and VPS peer must differ")
PY
  ip -4 -o addr show | grep -Fq " ${bind_ip}/" || fail "BIND_IP_NOT_CONFIGURED" 42
}

validate_host_resources() {
  local actual_host cpu mem_kib disk_kib
  actual_host="$(hostname)"
  [[ "$actual_host" == "$expected_hostname" ]] || fail "HOSTNAME_MISMATCH" 43
  cpu="$(nproc)"
  (( cpu >= 2 )) || fail "CPU_LT_2" 44
  mem_kib="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
  (( mem_kib >= 2097152 )) || fail "RAM_LT_2GB" 45
  disk_kib="$(df -Pk / | awk 'NR==2 {print $4}')"
  (( disk_kib >= 5242880 )) || fail "DISK_LT_5GB_FREE" 46
  printf 'WORKER_HOST=%s\n' "$actual_host"
  printf 'WORKER_CPU=%s\n' "$cpu"
  printf 'WORKER_MEM_KIB=%s\n' "$mem_kib"
  printf 'WORKER_DISK_FREE_KIB=%s\n' "$disk_kib"
}

validate_env_file() {
  [[ -n "$env_file" ]] || fail "ENV_FILE_REQUIRED" 47
  [[ -f "$env_file" ]] || fail "ENV_FILE_MISSING" 47
  local raw_mode mode_dec
  raw_mode="$(stat -c '%a' "$env_file")"
  mode_dec=$((8#$raw_mode))
  (( (mode_dec & 077) == 0 )) || fail "ENV_FILE_PERMISSIONS" 48
  python3 - "$env_file" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
values = {}
for raw in path.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    values[key.strip()] = value.strip().strip('"').strip("'")
required = (
    "PG_PASS",
    "AUTHENTIK_SECRET_KEY",
    "AUTHENTIK_BOOTSTRAP_EMAIL",
    "AUTHENTIK_BOOTSTRAP_PASSWORD",
    "AUTHENTIK_EMAIL__HOST",
    "AUTHENTIK_EMAIL__FROM",
)
missing = [key for key in required if not values.get(key)]
if missing:
    raise SystemExit("ERROR required env keys missing: " + ",".join(missing))
if len(values["PG_PASS"]) < 20:
    raise SystemExit("ERROR PG_PASS must be at least 20 characters")
if len(values["AUTHENTIK_SECRET_KEY"]) < 40:
    raise SystemExit("ERROR AUTHENTIK_SECRET_KEY must be at least 40 characters")
if len(values["AUTHENTIK_BOOTSTRAP_PASSWORD"]) < 15:
    raise SystemExit("ERROR AUTHENTIK_BOOTSTRAP_PASSWORD must be at least 15 characters")
username = values.get("AUTHENTIK_EMAIL__USERNAME", "")
password = values.get("AUTHENTIK_EMAIL__PASSWORD", "")
if bool(username) != bool(password):
    raise SystemExit("ERROR SMTP username/password must be both set or both empty")
PY
  printf 'AUTHENTIK_ENV_VALIDATION=PASS\n'
}

install_docker_if_needed() {
  if command -v docker >/dev/null 2>&1 \
     && docker compose version >/dev/null 2>&1 \
     && systemctl is-active --quiet docker.service \
     && docker info >/dev/null 2>&1; then
    printf 'DOCKER_INSTALL=ALREADY_READY\n'
    return
  fi

  . /etc/os-release
  local distro suite arch conflict pkg
  case "${ID:-}" in
    ubuntu)
      distro="ubuntu"
      suite="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
      ;;
    debian)
      distro="debian"
      suite="${VERSION_CODENAME:-}"
      ;;
    *) fail "UNSUPPORTED_OS_${ID:-unknown}" 50 ;;
  esac
  [[ -n "$suite" ]] || fail "OS_CODENAME_MISSING" 50

  conflict=""
  for pkg in docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc; do
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q '^install ok installed$'; then
      conflict="${conflict}${conflict:+,}${pkg}"
    fi
  done
  [[ -z "$conflict" ]] || fail "DOCKER_PACKAGE_CONFLICT" 51

  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/${distro}/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  arch="$(dpkg --print-architecture)"
  cat >/etc/apt/sources.list.d/docker.sources <<EOF_REPO
Types: deb
URIs: https://download.docker.com/linux/${distro}
Suites: ${suite}
Components: stable
Architectures: ${arch}
Signed-By: /etc/apt/keyrings/docker.asc
EOF_REPO
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin socat
  systemctl enable --now docker.service
  docker info >/dev/null 2>&1 || fail "DOCKER_INFO" 52
  docker compose version >/dev/null 2>&1 || fail "DOCKER_COMPOSE" 52
  printf 'DOCKER_INSTALL=PASS\n'
}

ensure_socat() {
  if command -v socat >/dev/null 2>&1; then
    return
  fi
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y socat
}

stage_runtime_files() {
  [[ -f "$compose_source" ]] || fail "COMPOSE_SOURCE_MISSING" 53
  [[ -f "$blueprint_source" ]] || fail "BLUEPRINT_SOURCE_MISSING" 53
  install -d -o root -g root -m 0700 "$runtime_root"
  install -d -o root -g root -m 0700 \
    "$runtime_root/blueprints" \
    "$runtime_root/certs"
  # Authentik server runs as uid/gid 1000 and must be able to traverse and
  # write the bind mounts exposed as /data and /templates.
  install -d -o 1000 -g 1000 -m 0700 \
    "$runtime_root/data" \
    "$runtime_root/custom-templates"
  install -o root -g root -m 0600 "$compose_source" "$runtime_root/compose.yml"
  install -o root -g root -m 0600 "$env_file" "$runtime_root/.env"
  install -o root -g root -m 0600 \
    "$blueprint_source" "$runtime_root/blueprints/sea-speed-auth-v1.yaml"
  printf 'AUTHENTIK_RUNTIME_FILES=STAGED\n'
}

install_private_proxy() {
  ensure_socat
  cat >"$proxy_unit" <<EOF_UNIT
[Unit]
Description=Sea Speed Authentik private ZeroTier proxy
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=/usr/bin/socat TCP4-LISTEN:${private_port},bind=${bind_ip},reuseaddr,fork,range=${vps_peer}/32 TCP4:127.0.0.1:9000
Restart=always
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_UNIX
LockPersonality=true

[Install]
WantedBy=multi-user.target
EOF_UNIT
  chmod 0644 "$proxy_unit"
  systemctl daemon-reload
  systemctl enable sea-speed-auth-private-proxy.service >/dev/null
}

compose_up_and_verify() {
  (
    cd "$runtime_root"
    docker compose pull
    docker compose up -d
  )

  local attempt
  for attempt in $(seq 1 60); do
    if curl --fail --silent --show-error --max-time 3 \
      http://127.0.0.1:9000/-/health/ready/ >/dev/null 2>&1; then
      break
    fi
    if [[ "$attempt" -eq 60 ]]; then
      fail "AUTHENTIK_LOOPBACK_HEALTH" 60
    fi
    sleep 2
  done

  systemctl restart sea-speed-auth-private-proxy.service
  systemctl is-active --quiet sea-speed-auth-private-proxy.service \
    || fail "PRIVATE_PROXY_SERVICE" 61

  local published postgres_id postgres_bindings
  published="$(cd "$runtime_root" && docker compose port server 9000 2>/dev/null || true)"
  [[ "$published" == "127.0.0.1:9000" ]] || fail "AUTHENTIK_DOCKER_NOT_LOOPBACK" 62

  postgres_id="$(cd "$runtime_root" && docker compose ps -q postgresql)"
  [[ -n "$postgres_id" ]] || fail "POSTGRES_CONTAINER_MISSING" 63
  postgres_bindings="$(docker inspect --format '{{json .HostConfig.PortBindings}}' "$postgres_id" 2>/dev/null || true)"
  case "$postgres_bindings" in
    "{}"|"null") ;;
    *) fail "POSTGRES_HOST_PORT_PRESENT" 63 ;;
  esac

  if docker inspect \
       "$(cd "$runtime_root" && docker compose ps -q server)" \
       "$(cd "$runtime_root" && docker compose ps -q worker)" 2>/dev/null \
       | grep -Fq '/var/run/docker.sock'; then
    fail "DOCKER_SOCKET_MOUNTED" 64
  fi

  ss -ltn | grep -Fq "${bind_ip}:${private_port}" || fail "PRIVATE_PROXY_NOT_LISTENING" 65
  printf 'AUTHENTIK_LOOPBACK_READY=YES\n'
  printf 'AUTHENTIK_PRIVATE_PROXY=PASS\n'
  printf 'AUTHENTIK_PRIVATE_ORIGIN=http://%s:%s\n' "$bind_ip" "$private_port"
  printf 'AUTHENTIK_POSTGRESQL_PUBLIC_PORT=NO\n'
  printf 'AUTHENTIK_DOCKER_SOCKET_MOUNT=NO\n'
  printf 'AUTHENTIK_WORKER_STAGE=PASS\n'
}

status_runtime() {
  printf 'WORKER_HOST=%s\n' "$(hostname)"
  if command -v docker >/dev/null 2>&1; then
    printf 'DOCKER_PRESENT=YES\n'
    printf 'DOCKER_SERVICE=%s\n' "$(systemctl is-active docker.service 2>/dev/null || true)"
  else
    printf 'DOCKER_PRESENT=NO\n'
  fi
  printf 'AUTHENTIK_PROXY_SERVICE=%s\n' "$(systemctl is-active sea-speed-auth-private-proxy.service 2>/dev/null || true)"
  if [[ -d "$runtime_root" ]] && command -v docker >/dev/null 2>&1; then
    printf 'AUTHENTIK_COMPOSE_SERVICES=%s\n' "$(cd "$runtime_root" && docker compose ps --services 2>/dev/null | paste -sd, - || true)"
  else
    printf 'AUTHENTIK_COMPOSE_SERVICES=\n'
  fi
  printf 'PRODUCTION_MUTATION=NO\n'
}

require_base_commands
validate_network
validate_host_resources

if [[ "$mode" == "status" ]]; then
  status_runtime
  exit 0
fi

[[ "$EUID" -eq 0 ]] || fail "ROOT_REQUIRED" 49
validate_env_file
install_docker_if_needed
stage_runtime_files
install_private_proxy
compose_up_and_verify
