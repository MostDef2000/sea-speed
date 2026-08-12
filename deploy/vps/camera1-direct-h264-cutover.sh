#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  camera1-direct-h264-cutover.sh status [--nginx-site PATH]
  camera1-direct-h264-cutover.sh activate [--nginx-site PATH]

Purpose:
  Make /cams/hls/cam1/ use the proven loopback H264 fMP4 fallback at
  127.0.0.1:18889/cam1/ without changing MediaMTX, AI, or the public URL.

Defaults:
  The script auto-discovers the active nginx file containing both
  `server_name mostdef.ru` and the existing `/cams/hls/` location.

Safety boundary:
  activate writes a protected backup, installs only the nginx site candidate,
  validates nginx, reloads nginx, and never performs automatic rollback.
EOF
}

command="${1:-}"
case "$command" in
  status|activate) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "ERROR unknown command: $command" >&2; usage >&2; exit 2 ;;
esac

nginx_site=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --nginx-site) [[ $# -ge 2 ]] || { echo "ERROR --nginx-site requires a path" >&2; exit 2; }; nginx_site="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; exit 2 ;;
  esac
done

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/../.." && pwd)"
renderer="$repo_root/scripts/operations/nginx_cam1_direct_h264.py"
state_root="/var/lib/sea-speed-hls-fallback"
backup_root="$state_root/backups"
local_hls="http://127.0.0.1:18889/cam1/index.m3u8"

require_commands() {
  command -v nginx >/dev/null 2>&1 || { echo "ERROR nginx is required" >&2; exit 4; }
  command -v curl >/dev/null 2>&1 || { echo "ERROR curl is required" >&2; exit 4; }
  command -v ffprobe >/dev/null 2>&1 || { echo "ERROR ffprobe is required" >&2; exit 4; }
  command -v python3 >/dev/null 2>&1 || { echo "ERROR python3 is required" >&2; exit 4; }
  [[ -f "$renderer" ]] || { echo "ERROR renderer missing from exact repository source" >&2; exit 4; }
}

require_root() {
  [[ "$EUID" -eq 0 ]] || { echo "ERROR activate must run as root" >&2; exit 1; }
}

discover_site() {
  if [[ -n "$nginx_site" ]]; then
    nginx_site="$(readlink -f "$nginx_site" 2>/dev/null || true)"
    [[ -n "$nginx_site" && -f "$nginx_site" ]] || { echo "ERROR nginx site must resolve to a regular file" >&2; exit 5; }
    return
  fi
  local dump path found=""
  dump="$(mktemp)"
  trap 'rm -f "$dump"' RETURN
  nginx -T >"$dump" 2>&1 || { cat "$dump" >&2; exit 5; }
  while IFS= read -r path; do
    local resolved
    resolved="$(readlink -f "$path" 2>/dev/null || true)"
    [[ -n "$resolved" && -f "$resolved" ]] || continue
    if grep -Eq '^[[:space:]]*server_name[[:space:]].*mostdef\.ru' "$resolved" \
       && grep -Fq '/cams/hls/' "$resolved"; then
      if [[ -n "$found" && "$found" != "$resolved" ]]; then
        echo "ERROR multiple nginx site candidates; pass --nginx-site explicitly" >&2
        exit 5
      fi
      found="$resolved"
    fi
  done < <(sed -n 's/^# configuration file \([^:]*\):$/\1/p' "$dump")
  [[ -n "$found" ]] || { echo "ERROR could not discover mostdef.ru nginx site with /cams/hls/" >&2; exit 5; }
  nginx_site="$found"
}

check_h264_fallback() {
  curl --fail --silent --show-error --max-time 8 "$local_hls" | grep -q '^#EXTM3U' || return 1
  local codec
  codec="$(timeout 15 ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$local_hls" 2>/dev/null | head -n1)"
  [[ "$codec" == "h264" ]]
}

require_commands
discover_site

printf 'NGINX_SITE=%s\n' "$nginx_site"
printf 'H264_SERVICE=%s\n' "$(systemctl is-active sea-speed-camera1-h264.service 2>/dev/null || true)"
printf 'HTTP_SERVICE=%s\n' "$(systemctl is-active sea-speed-camera1-hls-http.service 2>/dev/null || true)"
if check_h264_fallback; then
  printf 'LOCAL_H264_FALLBACK=PASS\n'
else
  printf 'LOCAL_H264_FALLBACK=FAIL\n'
  exit 20
fi

if python3 "$renderer" verify --config "$nginx_site" >/dev/null 2>&1; then
  printf 'CAM1_DIRECT_H264_CONFIG=PASS\n'
else
  printf 'CAM1_DIRECT_H264_CONFIG=NOT_ACTIVE\n'
fi

if [[ "$command" == "status" ]]; then
  printf 'PRODUCTION_MUTATION=NO\n'
  exit 0
fi

require_root
install -d -o root -g root -m 0700 "$backup_root"

candidate="$(mktemp)"
trap 'rm -f "$candidate" "${nginx_site}.next"' EXIT
python3 "$renderer" render --config "$nginx_site" --output "$candidate" >/dev/null
python3 "$renderer" verify --config "$candidate" >/dev/null

old_sha="$(sha256sum "$nginx_site" | awk '{print $1}')"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$backup_root/nginx-mostdef.pre-direct-h264.${stamp}.${old_sha}.conf"
install -o root -g root -m 0600 "$nginx_site" "$backup"

uid="$(stat -c '%u' "$nginx_site")"
gid="$(stat -c '%g' "$nginx_site")"
mode="$(stat -c '%a' "$nginx_site")"
install -o "$uid" -g "$gid" -m "$mode" "$candidate" "${nginx_site}.next"
mv -f "${nginx_site}.next" "$nginx_site"

if ! nginx -t; then
  echo "ERROR nginx validation failed after candidate install; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$backup" >&2
  printf 'AUTOMATIC_ROLLBACK=NO\n' >&2
  exit 30
fi

if ! systemctl reload nginx.service; then
  echo "ERROR nginx reload failed; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$backup" >&2
  printf 'AUTOMATIC_ROLLBACK=NO\n' >&2
  exit 31
fi
systemctl is-active --quiet nginx.service || {
  echo "ERROR nginx is not active after reload; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$backup" >&2
  exit 32
}

python3 "$renderer" verify --config "$nginx_site" >/dev/null
check_h264_fallback || {
  echo "ERROR local H264 fallback failed after nginx reload; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$backup" >&2
  exit 33
}

printf 'CAM1_DIRECT_H264_CUTOVER=PASS\n'
printf 'PUBLIC_URL=/cams/hls/cam1/index.m3u8\n'
printf 'CAM1_BROWSER_UPSTREAM=127.0.0.1:18889/cam1/\n'
printf 'MEDIAMTX_BROWSER_PATH=BYPASSED\n'
printf 'PLAYLIST_CACHE=DISABLED\n'
printf 'NGINX_BACKUP=%s\n' "$backup"
printf 'AI_CHANGED=NO\n'
printf 'AUTOMATIC_ROLLBACK=NO\n'
printf 'READY_FOR_BROWSER_RETEST\n'
