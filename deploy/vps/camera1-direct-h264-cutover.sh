#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  camera1-direct-h264-cutover.sh status [--nginx-site PATH]
  camera1-direct-h264-cutover.sh activate

Purpose:
  Read-only compatibility status for the Camera 1 H264 browser route after
  Sea Speed Auth v1. The browser path is now:

    /sea-speed/media/cam1/index.m3u8

  Standalone activation is deliberately retired. Issue #115 requires Camera 1
  routing and Authentik protection to be rendered/activated atomically by:

    deploy/vps/sea-speed-auth-cutover.sh

Safety boundary:
  This script never mutates nginx, MediaMTX, the H264 compatibility services,
  or the AI worker.
EOF
}

command="${1:-}"
case "$command" in
  status|activate) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "ERROR unknown command: $command" >&2; usage >&2; exit 2 ;;
esac

if [[ "$command" == "activate" ]]; then
  echo "ERROR standalone Camera 1 nginx activation is retired by Issue #115" >&2
  echo "USE=deploy/vps/sea-speed-auth-cutover.sh" >&2
  echo "PRODUCTION_MUTATION=NO" >&2
  exit 64
fi

nginx_site=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --nginx-site)
      [[ $# -ge 2 ]] || { echo "ERROR --nginx-site requires a path" >&2; exit 2; }
      nginx_site="$2"
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; exit 2 ;;
  esac
done

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/../.." && pwd)"
renderer="$repo_root/scripts/operations/nginx_cam1_direct_h264.py"
local_hls="http://127.0.0.1:18889/cam1/index.m3u8"

for command_name in nginx curl ffprobe python3; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "ERROR $command_name is required" >&2
    exit 4
  }
done
[[ -f "$renderer" ]] || { echo "ERROR renderer missing from exact repository source" >&2; exit 4; }

if [[ -n "$nginx_site" ]]; then
  nginx_site="$(readlink -f "$nginx_site" 2>/dev/null || true)"
  [[ -n "$nginx_site" && -f "$nginx_site" ]] || {
    echo "ERROR nginx site must resolve to a regular file" >&2
    exit 5
  }
else
  dump="$(mktemp)"
  trap 'rm -f "$dump"' EXIT
  nginx -T >"$dump" 2>&1 || { cat "$dump" >&2; exit 5; }
  found=""
  while IFS= read -r path; do
    resolved="$(readlink -f "$path" 2>/dev/null || true)"
    [[ -n "$resolved" && -f "$resolved" ]] || continue
    if grep -Eq '^[[:space:]]*server_name[[:space:]].*mostdef\.ru' "$resolved" \
       && grep -Fq '/sea-speed/' "$resolved"; then
      if [[ -n "$found" && "$found" != "$resolved" ]]; then
        echo "ERROR multiple nginx site candidates; pass --nginx-site explicitly" >&2
        exit 5
      fi
      found="$resolved"
    fi
  done < <(sed -n 's/^# configuration file \([^:]*\):$/\1/p' "$dump")
  [[ -n "$found" ]] || {
    echo "ERROR could not discover mostdef.ru nginx site with /sea-speed/" >&2
    exit 5
  }
  nginx_site="$found"
fi

printf 'NGINX_SITE=%s\n' "$nginx_site"
printf 'H264_SERVICE=%s\n' "$(systemctl is-active sea-speed-camera1-h264.service 2>/dev/null || true)"
printf 'HTTP_SERVICE=%s\n' "$(systemctl is-active sea-speed-camera1-hls-http.service 2>/dev/null || true)"

if curl --fail --silent --show-error --max-time 8 "$local_hls" | grep -q '^#EXTM3U'; then
  codec="$(timeout 15 ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$local_hls" 2>/dev/null | head -n1)"
  if [[ "$codec" == "h264" ]]; then
    printf 'LOCAL_H264_FALLBACK=PASS\n'
  else
    printf 'LOCAL_H264_FALLBACK=FAIL\n'
    exit 20
  fi
else
  printf 'LOCAL_H264_FALLBACK=FAIL\n'
  exit 20
fi

if python3 "$renderer" verify --config "$nginx_site" >/dev/null 2>&1; then
  printf 'CAM1_PROTECTED_H264_CONFIG=PASS\n'
  printf 'BROWSER_PATH=/sea-speed/media/cam1/index.m3u8\n'
else
  printf 'CAM1_PROTECTED_H264_CONFIG=NOT_ACTIVE\n'
fi

printf 'STANDALONE_ACTIVATION=RETIRED\n'
printf 'PRODUCTION_MUTATION=NO\n'
