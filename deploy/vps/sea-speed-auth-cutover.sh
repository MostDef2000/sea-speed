#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  sea-speed-auth-cutover.sh bootstrap-public --authentik-upstream URL [options]
  sea-speed-auth-cutover.sh status --authentik-upstream URL [options]
  sea-speed-auth-cutover.sh prepare --authentik-upstream URL --worker-private-listen IP:PORT --worker-private-peer IP [options]
  sea-speed-auth-cutover.sh activate --authentik-upstream URL --worker-private-listen IP:PORT --worker-private-peer IP --expected-sha256 SHA256 [options]

Options:
  --nginx-site PATH
  --authentik-upstream URL    required private worker origin, e.g. http://10.x.x.x:19000
  --worker-private-listen IP:PORT
  --worker-private-peer IP
  --expected-sha256 SHA256
  --authentik-public-url URL  default: https://auth.mostdef.ru

Purpose:
  bootstrap-public creates only the dedicated auth.mostdef.ru TLS reverse proxy
  to the exact private Ubuntu-worker Authentik origin. It does not modify the
  existing mostdef.ru /sea-speed/** security boundary.

  prepare/activate atomically prepare/activate the Sea Speed Auth v1 nginx boundary:
  - Camera 1 H264 browser route -> /sea-speed/media/cam1/
  - Authentik Forward Auth -> every existing /sea-speed/** nginx location
  - Authentik/outpost upstream -> exact private Ubuntu-worker origin over ZeroTier
  - /cams and /cams/** -> 404
  - exact private ZeroTier worker M2M endpoints -> existing loopback FastAPI upstream

Production authorization:
  This script does not grant production permission. bootstrap-public,
  prepare and activate may run only inside a separately approved exact-main-SHA
  PRODUCTION APPROVED envelope.

Rollback:
  The isolated auth.mostdef.ru vhost is source-managed by bootstrap-public and
  never changes the active mostdef.ru site. A root-only mostdef.ru nginx backup
  is written before activate. Automatic rollback of the main boundary is
  deliberately disabled; restoring the retired public /cams/** contour requires
  an explicit production rollback decision.
USAGE
}

mode="${1:-}"
case "$mode" in
  bootstrap-public|status|prepare|activate) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "ERROR unknown command: $mode" >&2; usage >&2; exit 2 ;;
esac

nginx_site=""
authentik_upstream=""
worker_private_listen=""
worker_private_peer=""
expected_sha256=""
authentik_public_url="https://auth.mostdef.ru"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --nginx-site)
      [[ $# -ge 2 ]] || { echo "ERROR --nginx-site requires a path" >&2; exit 2; }
      nginx_site="$2"; shift 2 ;;
    --authentik-upstream)
      [[ $# -ge 2 ]] || { echo "ERROR --authentik-upstream requires URL" >&2; exit 2; }
      authentik_upstream="$2"; shift 2 ;;
    --worker-private-listen)
      [[ $# -ge 2 ]] || { echo "ERROR --worker-private-listen requires IP:PORT" >&2; exit 2; }
      worker_private_listen="$2"; shift 2 ;;
    --worker-private-peer)
      [[ $# -ge 2 ]] || { echo "ERROR --worker-private-peer requires IP" >&2; exit 2; }
      worker_private_peer="$2"; shift 2 ;;
    --expected-sha256)
      [[ $# -ge 2 ]] || { echo "ERROR --expected-sha256 requires SHA256" >&2; exit 2; }
      expected_sha256="${2,,}"; shift 2 ;;
    --authentik-public-url)
      [[ $# -ge 2 ]] || { echo "ERROR --authentik-public-url requires URL" >&2; exit 2; }
      authentik_public_url="${2%/}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; exit 2 ;;
  esac
done

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/../.." && pwd)"
cam_renderer="$repo_root/scripts/operations/nginx_cam1_direct_h264.py"
auth_renderer="$repo_root/scripts/operations/nginx_sea_speed_auth.py"
state_root="/var/lib/sea-speed-auth-v1"
backup_root="$state_root/backups"
candidate_path="$state_root/candidate.nginx.conf"
local_h264="http://127.0.0.1:18889/cam1/index.m3u8"
private_authentik_health=""
auth_public_host="auth.mostdef.ru"
auth_site_available="/etc/nginx/sites-available/auth.mostdef.ru"
auth_site_enabled="/etc/nginx/sites-enabled/auth.mostdef.ru"
auth_acme_webroot="/var/www/sea-speed-auth-acme"
auth_cert_dir="/etc/letsencrypt/live/auth.mostdef.ru"
auth_managed_marker="# SEA-SPEED-AUTH-PUBLIC-V1"

require_commands() {
  local name
  for name in nginx curl ffprobe python3 sha256sum systemctl ip install grep sed awk timeout; do
    command -v "$name" >/dev/null 2>&1 || { echo "ERROR $name is required" >&2; exit 4; }
  done
  [[ -f "$cam_renderer" ]] || { echo "ERROR Camera 1 renderer missing from exact source" >&2; exit 4; }
  [[ -f "$auth_renderer" ]] || { echo "ERROR Auth v1 renderer missing from exact source" >&2; exit 4; }
}

require_public_bootstrap_commands() {
  local name
  for name in certbot openssl getent sort paste ln readlink; do
    command -v "$name" >/dev/null 2>&1 || { echo "ERROR $name is required for bootstrap-public" >&2; exit 4; }
  done
  [[ -d /etc/nginx/sites-available && -d /etc/nginx/sites-enabled ]] || {
    echo "ERROR nginx sites-available/sites-enabled layout is required for bootstrap-public" >&2
    exit 4
  }
}

require_root() {
  [[ "$EUID" -eq 0 ]] || { echo "ERROR $mode must run as root" >&2; exit 1; }
}

discover_site() {
  if [[ -n "$nginx_site" ]]; then
    nginx_site="$(readlink -f "$nginx_site" 2>/dev/null || true)"
    [[ -n "$nginx_site" && -f "$nginx_site" ]] || { echo "ERROR nginx site must be a regular file" >&2; exit 5; }
    return
  fi
  local dump path resolved found=""
  dump="$(mktemp)"
  nginx -T >"$dump" 2>&1 || { cat "$dump" >&2; rm -f "$dump"; exit 5; }
  while IFS= read -r path; do
    resolved="$(readlink -f "$path" 2>/dev/null || true)"
    [[ -n "$resolved" && -f "$resolved" ]] || continue
    if grep -Eq '^[[:space:]]*server_name[[:space:]].*mostdef\.ru' "$resolved" \
       && grep -Fq '/sea-speed/' "$resolved"; then
      if [[ -n "$found" && "$found" != "$resolved" ]]; then
        echo "ERROR multiple nginx site candidates; pass --nginx-site explicitly" >&2
        rm -f "$dump"
        exit 5
      fi
      found="$resolved"
    fi
  done < <(sed -n 's/^# configuration file \([^:]*\):$/\1/p' "$dump")
  rm -f "$dump"
  [[ -n "$found" ]] || { echo "ERROR could not discover mostdef.ru nginx site with /sea-speed/" >&2; exit 5; }
  nginx_site="$found"
}

require_authentik_upstream() {
  [[ -n "$authentik_upstream" ]] || {
    echo "ERROR --authentik-upstream is required and must be the worker private origin" >&2
    exit 2
  }
  local normalized host
  normalized="$(python3 - "$authentik_upstream" <<'PY'
import ipaddress
import sys
from urllib.parse import urlsplit
raw = sys.argv[1].strip().rstrip("/")
parsed = urlsplit(raw)
if parsed.scheme != "http":
    raise SystemExit("ERROR Authentik upstream must use private HTTP behind VPS TLS")
if parsed.username or parsed.password:
    raise SystemExit("ERROR Authentik upstream must not contain credentials")
if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
    raise SystemExit("ERROR Authentik upstream must be an origin without path/query/fragment")
if not parsed.hostname or parsed.port is None:
    raise SystemExit("ERROR Authentik upstream must be literal IPv4:port")
try:
    address = ipaddress.ip_address(parsed.hostname)
except ValueError as exc:
    raise SystemExit(f"ERROR Authentik upstream host must be literal IPv4: {exc}")
private = tuple(ipaddress.ip_network(x) for x in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
if address.version != 4 or address.is_loopback or not any(address in network for network in private):
    raise SystemExit("ERROR Authentik upstream must be non-loopback RFC1918 IPv4")
if not 1024 <= parsed.port <= 65535:
    raise SystemExit("ERROR Authentik upstream port must be 1024..65535")
print(f"http://{address}:{parsed.port}")
PY
)" || exit $?
  authentik_upstream="$normalized"
  host="${authentik_upstream#http://}"
  host="${host%:*}"
  if ip -4 -o addr show | grep -Fq " ${host}/"; then
    echo "ERROR Authentik upstream resolves to an address configured on the VPS; Issue #122 requires the remote worker" >&2
    exit 6
  fi
  private_authentik_health="${authentik_upstream}/-/health/ready/"
}

require_private_args() {
  [[ -n "$worker_private_listen" ]] || { echo "ERROR --worker-private-listen is required" >&2; exit 2; }
  [[ -n "$worker_private_peer" ]] || { echo "ERROR --worker-private-peer is required" >&2; exit 2; }
  python3 - "$worker_private_listen" "$worker_private_peer" <<'PY'
import ipaddress
import sys
listen, peer = sys.argv[1:]
try:
    host, raw_port = listen.rsplit(":", 1)
    port = int(raw_port)
    listen_ip = ipaddress.ip_address(host)
    peer_ip = ipaddress.ip_address(peer)
except Exception as exc:
    raise SystemExit(f"ERROR invalid private worker address: {exc}")
for label, value in (("listen", listen_ip), ("peer", peer_ip)):
    if value.version != 4 or not value.is_private or value.is_loopback:
        raise SystemExit(f"ERROR worker {label} must be a non-loopback private IPv4")
if not 1024 <= port <= 65535:
    raise SystemExit("ERROR worker private port must be 1024..65535")
PY
  local listen_ip="${worker_private_listen%:*}"
  ip -4 -o addr show | grep -Fq " ${listen_ip}/" || {
    echo "ERROR worker private listen IP is not configured on this VPS: $listen_ip" >&2
    exit 6
  }
}

check_private_authentik() {
  curl --fail --silent --show-error --max-time 8 "$private_authentik_health" >/dev/null
}

check_public_authentik() {
  curl --fail --silent --show-error --max-time 12 "${authentik_public_url}/-/health/ready/" >/dev/null
}

check_authentik() {
  check_private_authentik && check_public_authentik
}

require_public_dns_exact() {
  [[ "$authentik_public_url" == "https://${auth_public_host}" ]] || {
    echo "ERROR bootstrap-public is restricted to https://${auth_public_host}" >&2
    exit 22
  }
  local public_ip dns_ipv4 dns_ipv6
  public_ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i == "src") {print $(i+1); exit}}')"
  [[ -n "$public_ip" ]] || { echo "ERROR could not discover VPS public IPv4" >&2; exit 22; }
  dns_ipv4="$(getent ahostsv4 "$auth_public_host" 2>/dev/null | awk '{print $1}' | sort -u | paste -sd, -)"
  [[ "$dns_ipv4" == "$public_ip" ]] || {
    echo "ERROR ${auth_public_host} A record must resolve only to VPS public IPv4 ${public_ip}; got ${dns_ipv4:-NONE}" >&2
    exit 22
  }
  dns_ipv6="$(getent ahostsv6 "$auth_public_host" 2>/dev/null | awk '{print $1}' | sort -u | paste -sd, - || true)"
  [[ -z "$dns_ipv6" ]] || {
    echo "ERROR ${auth_public_host} has IPv6 DNS but bootstrap-public has no approved IPv6 ingress: $dns_ipv6" >&2
    exit 22
  }
  printf 'AUTHENTIK_PUBLIC_DNS=PASS\n'
  printf 'AUTHENTIK_PUBLIC_IPV4=%s\n' "$public_ip"
}

require_auth_vhost_absent_or_managed() {
  if nginx -T 2>&1 | grep -Eq 'server_name[[:space:]]+[^;]*auth\.mostdef\.ru'; then
    [[ -f "$auth_site_available" ]] && grep -Fq "$auth_managed_marker" "$auth_site_available" || {
      echo "ERROR existing auth.mostdef.ru nginx vhost is not Sea Speed managed" >&2
      exit 23
    }
  fi
  if [[ -e "$auth_site_available" ]] && ! grep -Fq "$auth_managed_marker" "$auth_site_available"; then
    echo "ERROR existing auth.mostdef.ru site file is not Sea Speed managed" >&2
    exit 23
  fi
  if [[ -e "$auth_site_enabled" && ! -L "$auth_site_enabled" ]]; then
    echo "ERROR auth.mostdef.ru enabled path exists and is not a symlink" >&2
    exit 23
  fi
}

write_auth_http_vhost() {
  install -d -o root -g root -m 0755 "$auth_acme_webroot"
  cat >"$auth_site_available" <<EOF_AUTH_HTTP
${auth_managed_marker}
server {
    listen 80;
    server_name ${auth_public_host};

    location ^~ /.well-known/acme-challenge/ {
        root ${auth_acme_webroot};
        default_type text/plain;
    }

    location / {
        return 404;
    }
}
EOF_AUTH_HTTP
  chmod 0644 "$auth_site_available"
  ln -sfn "$auth_site_available" "$auth_site_enabled"
  nginx -t
  systemctl reload nginx.service
  systemctl is-active --quiet nginx.service || { echo "ERROR nginx inactive after ACME vhost reload" >&2; exit 24; }
  printf 'AUTHENTIK_ACME_VHOST=PASS\n'
}

issue_auth_certificate() {
  certbot certonly \
    --webroot \
    --webroot-path "$auth_acme_webroot" \
    --cert-name "$auth_public_host" \
    --domain "$auth_public_host" \
    --non-interactive \
    --agree-tos \
    --no-eff-email \
    --keep-until-expiring
  [[ -f "$auth_cert_dir/fullchain.pem" && -f "$auth_cert_dir/privkey.pem" ]] || {
    echo "ERROR expected auth.mostdef.ru certificate files missing" >&2
    exit 25
  }
  openssl x509 -in "$auth_cert_dir/fullchain.pem" -noout -ext subjectAltName \
    | grep -Fq "DNS:${auth_public_host}" || {
      echo "ERROR issued certificate does not cover ${auth_public_host}" >&2
      exit 25
    }
  printf 'AUTHENTIK_TLS_CERT=PASS\n'
}

write_auth_https_vhost() {
  cat >"$auth_site_available" <<EOF_AUTH_HTTPS
${auth_managed_marker}
server {
    listen 80;
    server_name ${auth_public_host};

    location ^~ /.well-known/acme-challenge/ {
        root ${auth_acme_webroot};
        default_type text/plain;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name ${auth_public_host};

    ssl_certificate ${auth_cert_dir}/fullchain.pem;
    ssl_certificate_key ${auth_cert_dir}/privkey.pem;

    location / {
        proxy_pass ${authentik_upstream};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
EOF_AUTH_HTTPS
  chmod 0644 "$auth_site_available"
  nginx -t
  systemctl reload nginx.service
  systemctl is-active --quiet nginx.service || { echo "ERROR nginx inactive after auth TLS vhost reload" >&2; exit 26; }
}

bootstrap_public_authentik() {
  require_root
  require_public_bootstrap_commands
  require_public_dns_exact
  require_auth_vhost_absent_or_managed
  check_private_authentik || { echo "ERROR private worker Authentik unhealthy" >&2; exit 20; }
  printf 'AUTHENTIK_PRIVATE_HEALTH=PASS\n'
  write_auth_http_vhost
  issue_auth_certificate
  write_auth_https_vhost
  check_public_authentik || { echo "ERROR public Authentik health failed after TLS vhost activation" >&2; exit 27; }
  printf 'AUTHENTIK_PUBLIC_HEALTH=PASS\n'
  printf 'AUTHENTIK_PUBLIC_BOOTSTRAP=PASS\n'
  printf 'AUTHENTIK_PUBLIC_URL=%s\n' "$authentik_public_url"
  printf 'AUTHENTIK_PRIVATE_UPSTREAM=%s\n' "$authentik_upstream"
  printf 'SEA_SPEED_MAIN_BOUNDARY_CHANGED=NO\n'
  printf 'NEXT_CHECKPOINT=OWNER_TOTP_PROVIDER\n'
}

check_h264() {
  curl --fail --silent --show-error --max-time 8 "$local_h264" | grep -q '^#EXTM3U' || return 1
  local codec
  codec="$(timeout 15 ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$local_h264" 2>/dev/null | head -n1)"
  [[ "$codec" == "h264" ]]
}

render_candidate() {
  local output="$1" stage1
  stage1="$(mktemp)"
  trap 'rm -f "$stage1"' RETURN
  python3 "$cam_renderer" render --config "$nginx_site" --output "$stage1" >/dev/null
  python3 "$cam_renderer" verify --config "$stage1" >/dev/null
  python3 "$auth_renderer" render \
    --config "$stage1" \
    --output "$output" \
    --authentik-upstream "$authentik_upstream" \
    --worker-private-listen "$worker_private_listen" \
    --worker-private-peer "$worker_private_peer" >/dev/null
  python3 "$cam_renderer" verify --config "$output" >/dev/null
  python3 "$auth_renderer" verify \
    --config "$output" \
    --authentik-upstream "$authentik_upstream" \
    --worker-private-listen "$worker_private_listen" \
    --worker-private-peer "$worker_private_peer" >/dev/null
}

http_status() {
  curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 15 "$1" || true
}

require_commands
require_authentik_upstream

if [[ "$mode" == "bootstrap-public" ]]; then
  bootstrap_public_authentik
  exit 0
fi

discover_site
printf 'NGINX_SITE=%s\n' "$nginx_site"
printf 'AUTHENTIK_PRIVATE_UPSTREAM=%s\n' "$authentik_upstream"

if check_authentik; then
  printf 'AUTHENTIK_PRIVATE_HEALTH=PASS\n'
  printf 'AUTHENTIK_PUBLIC_HEALTH=PASS\n'
else
  printf 'AUTHENTIK_HEALTH=FAIL\n'
  exit 20
fi
if check_h264; then
  printf 'LOCAL_H264_FALLBACK=PASS\n'
else
  printf 'LOCAL_H264_FALLBACK=FAIL\n'
  exit 21
fi

if [[ "$mode" == "status" ]]; then
  if [[ -n "$worker_private_listen" || -n "$worker_private_peer" ]]; then
    require_private_args
    if python3 "$cam_renderer" verify --config "$nginx_site" >/dev/null 2>&1 \
       && python3 "$auth_renderer" verify --config "$nginx_site" \
            --authentik-upstream "$authentik_upstream" \
            --worker-private-listen "$worker_private_listen" \
            --worker-private-peer "$worker_private_peer" >/dev/null 2>&1; then
      printf 'SEA_SPEED_AUTH_V1=ACTIVE\n'
    else
      printf 'SEA_SPEED_AUTH_V1=NOT_ACTIVE\n'
    fi
  else
    printf 'SEA_SPEED_AUTH_V1=UNKNOWN_PRIVATE_ARGS_NOT_SUPPLIED\n'
  fi
  printf 'PRODUCTION_MUTATION=NO\n'
  exit 0
fi

require_root
require_private_args
install -d -o root -g root -m 0700 "$state_root" "$backup_root"

candidate_tmp="$(mktemp)"
trap 'rm -f "$candidate_tmp" "${nginx_site}.next"' EXIT
render_candidate "$candidate_tmp"
candidate_sha="$(sha256sum "$candidate_tmp" | awk '{print $1}')"

if [[ "$mode" == "prepare" ]]; then
  install -o root -g root -m 0600 "$candidate_tmp" "$candidate_path"
  printf 'SEA_SPEED_AUTH_PREPARE=PASS\n'
  printf 'CANDIDATE=%s\n' "$candidate_path"
  printf 'CANDIDATE_SHA256=%s\n' "$candidate_sha"
  printf 'NGINX_RELOADED=NO\n'
  printf 'PRODUCTION_MUTATION=NO_ACTIVE_CONFIG_CHANGE\n'
  exit 0
fi

[[ "$expected_sha256" =~ ^[0-9a-f]{64}$ ]] || {
  echo "ERROR activate requires --expected-sha256 from prepare" >&2
  exit 2
}
[[ "$candidate_sha" == "$expected_sha256" ]] || {
  echo "ERROR rendered candidate SHA256 changed since prepare" >&2
  printf 'EXPECTED_SHA256=%s\n' "$expected_sha256" >&2
  printf 'ACTUAL_SHA256=%s\n' "$candidate_sha" >&2
  exit 30
}

old_sha="$(sha256sum "$nginx_site" | awk '{print $1}')"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$backup_root/nginx-mostdef.pre-auth-v1.${stamp}.${old_sha}.conf"
install -o root -g root -m 0600 "$nginx_site" "$backup"
uid="$(stat -c '%u' "$nginx_site")"
gid="$(stat -c '%g' "$nginx_site")"
mode_bits="$(stat -c '%a' "$nginx_site")"
install -o "$uid" -g "$gid" -m "$mode_bits" "$candidate_tmp" "${nginx_site}.next"
mv -f "${nginx_site}.next" "$nginx_site"

if ! nginx -t; then
  echo "ERROR nginx validation failed after candidate install; automatic rollback is disabled" >&2
  printf 'NGINX_BACKUP=%s\n' "$backup" >&2
  printf 'AUTOMATIC_ROLLBACK=NO\n' >&2
  exit 31
fi
if ! systemctl reload nginx.service; then
  echo "ERROR nginx reload failed; automatic rollback is disabled" >&2
  printf 'NGINX_BACKUP=%s\n' "$backup" >&2
  printf 'AUTOMATIC_ROLLBACK=NO\n' >&2
  exit 32
fi
systemctl is-active --quiet nginx.service || {
  echo "ERROR nginx is not active after reload" >&2
  printf 'NGINX_BACKUP=%s\n' "$backup" >&2
  exit 33
}

python3 "$cam_renderer" verify --config "$nginx_site" >/dev/null
python3 "$auth_renderer" verify \
  --config "$nginx_site" \
  --authentik-upstream "$authentik_upstream" \
  --worker-private-listen "$worker_private_listen" \
  --worker-private-peer "$worker_private_peer" >/dev/null
check_authentik || { echo "ERROR remote Authentik unhealthy after nginx reload" >&2; exit 34; }
check_h264 || { echo "ERROR local H264 fallback unhealthy after nginx reload" >&2; exit 35; }

root_status="$(http_status https://mostdef.ru/)"
cams_status="$(http_status https://mostdef.ru/cams/)"
sea_status="$(http_status https://mostdef.ru/sea-speed/)"
cam_status="$(http_status https://mostdef.ru/sea-speed/media/cam1/index.m3u8)"
outpost_status="$(http_status https://mostdef.ru/outpost.goauthentik.io/ping)"
[[ "$root_status" == "200" ]] || { echo "ERROR public root expected 200, got $root_status" >&2; exit 36; }
[[ "$cams_status" == "404" || "$cams_status" == "410" ]] || { echo "ERROR /cams/ expected 404/410, got $cams_status" >&2; exit 37; }
case "$sea_status" in 302|401|403) ;; *) echo "ERROR /sea-speed/ is not auth-gated: HTTP $sea_status" >&2; exit 38 ;; esac
case "$cam_status" in 302|401|403) ;; *) echo "ERROR protected Camera 1 is not auth-gated: HTTP $cam_status" >&2; exit 39 ;; esac
[[ "$outpost_status" == "200" ]] || { echo "ERROR Authentik outpost ping expected 200, got $outpost_status" >&2; exit 40; }

printf 'SEA_SPEED_AUTH_CUTOVER=PASS\n'
printf 'AUTHENTIK_PRIVATE_UPSTREAM=%s\n' "$authentik_upstream"
printf 'PUBLIC_ROOT_HTTP=%s\n' "$root_status"
printf 'LEGACY_CAMS_HTTP=%s\n' "$cams_status"
printf 'SEA_SPEED_ANONYMOUS_HTTP=%s\n' "$sea_status"
printf 'CAM1_ANONYMOUS_HTTP=%s\n' "$cam_status"
printf 'OUTPOST_HTTP=%s\n' "$outpost_status"
printf 'CAM1_BROWSER_PATH=/sea-speed/media/cam1/index.m3u8\n'
printf 'WORKER_PRIVATE_API_BASE=http://%s/api/cam1\n' "$worker_private_listen"
printf 'WORKER_PRIVATE_PEER=%s\n' "$worker_private_peer"
printf 'WORKER_RUNTIME_RECONFIGURATION_REQUIRED=YES\n'
printf 'NGINX_BACKUP=%s\n' "$backup"
printf 'AUTOMATIC_ROLLBACK=NO\n'
printf 'AUTHENTICATED_BROWSER_ACCEPTANCE_REQUIRED=YES\n'
