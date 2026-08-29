#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <exact-source-sha> <deployment-user>" >&2
  exit 2
fi

SOURCE_SHA="$1"
DEPLOY_USER="$2"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
TEST_ROOT="${SEA_SPEED_PRIVILEGE_BOUNDARY_TEST_ROOT:-}"
WATCHDOG_SERVICE="sea-speed-camera1-h264-freshness.service"
WATCHDOG_TIMER="sea-speed-camera1-h264-freshness.timer"
NGINX_WAIT_SERVICE="sea-speed-nginx-zerotier-wait"
NGINX_DROPIN_DIR="nginx.service.d"
NGINX_DROPIN_NAME="sea-speed-nginx-zerotier.conf"

if [[ -n "$TEST_ROOT" ]]; then
  [[ "$TEST_ROOT" == /* && "$TEST_ROOT" != "/" ]] || { echo "ERROR test root must be an absolute non-root path" >&2; exit 2; }
  INSTALL_UID="$(id -u)"
  INSTALL_GID="$(id -g)"
else
  [[ "$EUID" -eq 0 ]] || { echo "ERROR privilege-boundary installation must run as root" >&2; exit 1; }
  INSTALL_UID=0
  INSTALL_GID=0
fi

[[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR exact source SHA must be lowercase 40-character hex" >&2; exit 2; }
[[ "$DEPLOY_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || { echo "ERROR invalid deployment user" >&2; exit 2; }
DEPLOY_UID="$(id -u "$DEPLOY_USER" 2>/dev/null || true)"
[[ "$DEPLOY_UID" =~ ^[0-9]+$ ]] || { echo "ERROR deployment user does not exist" >&2; exit 3; }
[[ "$DEPLOY_UID" -ne 0 ]] || { echo "ERROR deployment user must not be root" >&2; exit 3; }

command -v git >/dev/null 2>&1 || { echo "ERROR git is required" >&2; exit 4; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR python3 is required" >&2; exit 4; }
command -v sha256sum >/dev/null 2>&1 || { echo "ERROR sha256sum is required" >&2; exit 4; }
command -v visudo >/dev/null 2>&1 || { echo "ERROR visudo is required" >&2; exit 4; }
if [[ -z "$TEST_ROOT" ]]; then
  command -v systemctl >/dev/null 2>&1 || { echo "ERROR systemctl is required" >&2; exit 4; }
fi

ACTUAL_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"
[[ "$ACTUAL_SHA" == "$SOURCE_SHA" ]] || { echo "ERROR installer source checkout is not the authorized exact SHA" >&2; exit 5; }
ORIGIN_URL="$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)"
case "$ORIGIN_URL" in
  https://github.com/MostDef2000/sea-speed|https://github.com/MostDef2000/sea-speed.git|git@github.com:MostDef2000/sea-speed.git)
    ;;
  *) echo "ERROR installer source repository identity mismatch" >&2; exit 5 ;;
esac

HELPER_SOURCE="$REPO_ROOT/deploy/vps/sea-speed-auth-privileged-helper.py"
CUTOVER_SOURCE="$REPO_ROOT/deploy/vps/sea-speed-auth-cutover.sh"
CAM_RENDERER_SOURCE="$REPO_ROOT/scripts/operations/nginx_cam1_direct_h264.py"
AUTH_RENDERER_SOURCE="$REPO_ROOT/scripts/operations/nginx_sea_speed_auth.py"
WATCHDOG_SOURCE="$REPO_ROOT/deploy/vps/camera1-h264-freshness-watchdog.py"
WATCHDOG_SERVICE_SOURCE="$REPO_ROOT/deploy/vps/$WATCHDOG_SERVICE"
WATCHDOG_TIMER_SOURCE="$REPO_ROOT/deploy/vps/$WATCHDOG_TIMER"
NGINX_WAIT_SOURCE="$REPO_ROOT/deploy/vps/sea-speed-nginx-zerotier-wait.sh"
NGINX_DROPIN_SOURCE="$REPO_ROOT/deploy/vps/$NGINX_DROPIN_NAME"
for source in \
  "$HELPER_SOURCE" \
  "$CUTOVER_SOURCE" \
  "$CAM_RENDERER_SOURCE" \
  "$AUTH_RENDERER_SOURCE" \
  "$WATCHDOG_SOURCE" \
  "$WATCHDOG_SERVICE_SOURCE" \
  "$WATCHDOG_TIMER_SOURCE" \
  "$NGINX_WAIT_SOURCE" \
  "$NGINX_DROPIN_SOURCE"; do
  [[ -f "$source" && ! -L "$source" ]] || { echo "ERROR required exact-source asset missing or unsafe: $source" >&2; exit 5; }
done

PREFIX="$TEST_ROOT"
HELPER_PATH="${PREFIX}/usr/local/sbin/sea-speed-auth-privileged-helper"
BUNDLE_ROOT="${PREFIX}/usr/local/lib/sea-speed-auth-privileged"
SUDOERS_PATH="${PREFIX}/etc/sudoers.d/sea-speed-auth-privileged"
WATCHDOG_PATH="${PREFIX}/usr/local/sbin/sea-speed-camera1-h264-freshness-watchdog"
WATCHDOG_SERVICE_PATH="${PREFIX}/etc/systemd/system/$WATCHDOG_SERVICE"
WATCHDOG_TIMER_PATH="${PREFIX}/etc/systemd/system/$WATCHDOG_TIMER"
NGINX_WAIT_HELPER_PATH="${PREFIX}/usr/local/sbin/$NGINX_WAIT_SERVICE"
NGINX_DROPIN_PATH="${PREFIX}/etc/systemd/system/$NGINX_DROPIN_DIR/$NGINX_DROPIN_NAME"
TMP="$(mktemp -d)"
BACKUP="$TMP/backup"
STAGE="$TMP/stage"
MUTATED=0
SUCCESS=0
PREV_TIMER_ENABLED="not-found"
PREV_TIMER_ACTIVE="inactive"
PREV_NGINX_ENABLED="not-found"
PREV_NGINX_ACTIVE="inactive"
mkdir -p "$BACKUP" "$STAGE/repo/deploy/vps" "$STAGE/repo/scripts/operations"

if [[ -z "$TEST_ROOT" ]]; then
  PREV_TIMER_ENABLED="$(systemctl is-enabled "$WATCHDOG_TIMER" 2>/dev/null || true)"
  PREV_TIMER_ACTIVE="$(systemctl is-active "$WATCHDOG_TIMER" 2>/dev/null || true)"
  PREV_NGINX_ENABLED="$(systemctl is-enabled nginx.service 2>/dev/null || true)"
  PREV_NGINX_ACTIVE="$(systemctl is-active nginx.service 2>/dev/null || true)"
fi

backup_path() {
  local source="$1" name="$2"
  if [[ -e "$source" || -L "$source" ]]; then
    cp -a -- "$source" "$BACKUP/$name"
  fi
}

restore_path() {
  local target="$1" name="$2"
  rm -rf -- "$target"
  if [[ -e "$BACKUP/$name" || -L "$BACKUP/$name" ]]; then
    mkdir -p "$(dirname "$target")"
    cp -a -- "$BACKUP/$name" "$target"
  fi
}

restore_timer_runtime() {
  [[ -z "$TEST_ROOT" ]] || return 0
  systemctl daemon-reload >/dev/null 2>&1 || true
  case "$PREV_TIMER_ENABLED" in
    enabled|enabled-runtime|linked|linked-runtime|alias)
      systemctl enable "$WATCHDOG_TIMER" >/dev/null 2>&1 || true
      ;;
    *)
      systemctl disable "$WATCHDOG_TIMER" >/dev/null 2>&1 || true
      ;;
  esac
  if [[ "$PREV_TIMER_ACTIVE" == "active" || "$PREV_TIMER_ACTIVE" == "activating" ]]; then
    systemctl start "$WATCHDOG_TIMER" >/dev/null 2>&1 || true
  else
    systemctl stop "$WATCHDOG_TIMER" >/dev/null 2>&1 || true
  fi
}

restore_nginx_runtime() {
  [[ -z "$TEST_ROOT" ]] || return 0
  systemctl daemon-reload >/dev/null 2>&1 || true
  case "$PREV_NGINX_ENABLED" in
    enabled|enabled-runtime|linked|linked-runtime|alias)
      systemctl enable nginx.service >/dev/null 2>&1 || true
      ;;
    *)
      systemctl disable nginx.service >/dev/null 2>&1 || true
      ;;
  esac
  if [[ "$PREV_NGINX_ACTIVE" == "active" || "$PREV_NGINX_ACTIVE" == "activating" ]]; then
    systemctl start nginx.service >/dev/null 2>&1 || true
  else
    systemctl stop nginx.service >/dev/null 2>&1 || true
  fi
}

cleanup() {
  local rc=$?
  if [[ "$SUCCESS" -ne 1 && "$MUTATED" -eq 1 ]]; then
    restore_path "$HELPER_PATH" helper
    restore_path "$BUNDLE_ROOT" bundle
    restore_path "$SUDOERS_PATH" sudoers
    restore_path "$WATCHDOG_PATH" watchdog
    restore_path "$WATCHDOG_SERVICE_PATH" watchdog-service
    restore_path "$WATCHDOG_TIMER_PATH" watchdog-timer
    restore_path "$NGINX_WAIT_HELPER_PATH" nginx-wait-helper
    restore_path "$NGINX_DROPIN_PATH" nginx-dropin
    restore_timer_runtime
    restore_nginx_runtime
    echo "SEA_SPEED_AUTH_PRIVILEGE_INSTALL_ROLLBACK=PASS" >&2
  fi
  rm -rf -- "$TMP"
  exit "$rc"
}
trap cleanup EXIT

install -m 0755 "$HELPER_SOURCE" "$STAGE/helper"
install -m 0755 "$CUTOVER_SOURCE" "$STAGE/repo/deploy/vps/sea-speed-auth-cutover.sh"
install -m 0644 "$CAM_RENDERER_SOURCE" "$STAGE/repo/scripts/operations/nginx_cam1_direct_h264.py"
install -m 0644 "$AUTH_RENDERER_SOURCE" "$STAGE/repo/scripts/operations/nginx_sea_speed_auth.py"
install -m 0755 "$WATCHDOG_SOURCE" "$STAGE/watchdog"
install -m 0644 "$WATCHDOG_SERVICE_SOURCE" "$STAGE/watchdog.service"
install -m 0644 "$WATCHDOG_TIMER_SOURCE" "$STAGE/watchdog.timer"
install -m 0755 "$NGINX_WAIT_SOURCE" "$STAGE/nginx-wait-helper"
install -m 0644 "$NGINX_DROPIN_SOURCE" "$STAGE/nginx-dropin"

python3 - "$STAGE/manifest.json" "$SOURCE_SHA" "$STAGE/helper" "$STAGE/repo" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
source_sha = sys.argv[2]
helper = Path(sys.argv[3])
repo = Path(sys.argv[4])
assets = (
    "deploy/vps/sea-speed-auth-cutover.sh",
    "scripts/operations/nginx_cam1_direct_h264.py",
    "scripts/operations/nginx_sea_speed_auth.py",
)

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

payload = {
    "schema": "sea_speed_auth_privileged_bundle_v1",
    "source_sha": source_sha,
    "helper_sha256": digest(helper),
    "assets": {name: digest(repo / name) for name in assets},
}
manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
chmod 0644 "$STAGE/manifest.json"

cat > "$STAGE/sudoers" <<EOF
${DEPLOY_USER} ALL=(root) NOPASSWD: ${HELPER_PATH#${PREFIX}} ""
EOF
chmod 0440 "$STAGE/sudoers"
visudo -cf "$STAGE/sudoers" >/dev/null

if [[ -z "$TEST_ROOT" ]]; then
  # Do not mutate the root-owned boundary unless the exact fixed address is
  # currently available. The installed systemd boundary owns later retries.
  bash "$NGINX_WAIT_SOURCE"
  echo "NGINX_ZEROTIER_PREMUTATION=PASS"
fi

backup_path "$HELPER_PATH" helper
backup_path "$BUNDLE_ROOT" bundle
backup_path "$SUDOERS_PATH" sudoers
backup_path "$WATCHDOG_PATH" watchdog
backup_path "$WATCHDOG_SERVICE_PATH" watchdog-service
backup_path "$WATCHDOG_TIMER_PATH" watchdog-timer
backup_path "$NGINX_WAIT_HELPER_PATH" nginx-wait-helper
backup_path "$NGINX_DROPIN_PATH" nginx-dropin
MUTATED=1

mkdir -p \
  "$(dirname "$HELPER_PATH")" \
  "$(dirname "$BUNDLE_ROOT")" \
  "$(dirname "$SUDOERS_PATH")" \
  "$(dirname "$WATCHDOG_PATH")" \
  "$(dirname "$WATCHDOG_SERVICE_PATH")" \
  "$(dirname "$NGINX_WAIT_HELPER_PATH")" \
  "$(dirname "$NGINX_DROPIN_PATH")"
rm -rf -- "${BUNDLE_ROOT}.next"
mkdir -p "${BUNDLE_ROOT}.next"
cp -a "$STAGE/repo" "${BUNDLE_ROOT}.next/repo"
install -m 0644 "$STAGE/manifest.json" "${BUNDLE_ROOT}.next/manifest.json"
chown -R "$INSTALL_UID:$INSTALL_GID" "${BUNDLE_ROOT}.next"
find "${BUNDLE_ROOT}.next" -type d -exec chmod 0755 {} +
chmod 0755 "${BUNDLE_ROOT}.next/repo/deploy/vps/sea-speed-auth-cutover.sh"
chmod 0644 "${BUNDLE_ROOT}.next/repo/scripts/operations/nginx_cam1_direct_h264.py" "${BUNDLE_ROOT}.next/repo/scripts/operations/nginx_sea_speed_auth.py" "${BUNDLE_ROOT}.next/manifest.json"
rm -rf -- "$BUNDLE_ROOT"
mv "${BUNDLE_ROOT}.next" "$BUNDLE_ROOT"

install -o "$INSTALL_UID" -g "$INSTALL_GID" -m 0755 "$STAGE/helper" "${HELPER_PATH}.next"
mv -f "${HELPER_PATH}.next" "$HELPER_PATH"
install -o "$INSTALL_UID" -g "$INSTALL_GID" -m 0440 "$STAGE/sudoers" "${SUDOERS_PATH}.next"
visudo -cf "${SUDOERS_PATH}.next" >/dev/null
mv -f "${SUDOERS_PATH}.next" "$SUDOERS_PATH"
visudo -cf "$SUDOERS_PATH" >/dev/null
install -o "$INSTALL_UID" -g "$INSTALL_GID" -m 0755 "$STAGE/watchdog" "${WATCHDOG_PATH}.next"
mv -f "${WATCHDOG_PATH}.next" "$WATCHDOG_PATH"
install -o "$INSTALL_UID" -g "$INSTALL_GID" -m 0644 "$STAGE/watchdog.service" "${WATCHDOG_SERVICE_PATH}.next"
mv -f "${WATCHDOG_SERVICE_PATH}.next" "$WATCHDOG_SERVICE_PATH"
install -o "$INSTALL_UID" -g "$INSTALL_GID" -m 0644 "$STAGE/watchdog.timer" "${WATCHDOG_TIMER_PATH}.next"
mv -f "${WATCHDOG_TIMER_PATH}.next" "$WATCHDOG_TIMER_PATH"
install -o "$INSTALL_UID" -g "$INSTALL_GID" -m 0755 "$STAGE/nginx-wait-helper" "${NGINX_WAIT_HELPER_PATH}.next"
mv -f "${NGINX_WAIT_HELPER_PATH}.next" "$NGINX_WAIT_HELPER_PATH"
mkdir -p "$(dirname "$NGINX_DROPIN_PATH")"
install -o "$INSTALL_UID" -g "$INSTALL_GID" -m 0644 "$STAGE/nginx-dropin" "${NGINX_DROPIN_PATH}.next"
mv -f "${NGINX_DROPIN_PATH}.next" "$NGINX_DROPIN_PATH"

if [[ "${SEA_SPEED_PRIVILEGE_BOUNDARY_TEST_FAIL_AFTER_INSTALL:-0}" == "1" && -n "$TEST_ROOT" ]]; then
  echo "ERROR injected post-install test failure" >&2
  exit 90
fi

python3 - "$BUNDLE_ROOT/manifest.json" "$SOURCE_SHA" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("schema") != "sea_speed_auth_privileged_bundle_v1" or payload.get("source_sha") != sys.argv[2]:
    raise SystemExit("ERROR installed privileged bundle manifest mismatch")
PY

if [[ -z "$TEST_ROOT" ]]; then
  systemctl daemon-reload
  systemctl enable --now "$WATCHDOG_TIMER"
  systemctl is-enabled --quiet "$WATCHDOG_TIMER"
  systemctl is-active --quiet "$WATCHDOG_TIMER"
  echo "CAMERA1_FRESHNESS_TIMER=ACTIVE"
  systemctl restart nginx.service
  systemctl is-active --quiet nginx.service
  echo "NGINX_ZEROTIER_STARTUP=ACTIVE"
else
  echo "CAMERA1_FRESHNESS_TIMER=TEST_ROOT_NOT_ACTIVATED"
  echo "NGINX_ZEROTIER_STARTUP=TEST_ROOT_NOT_ACTIVATED"
fi

SUCCESS=1
echo "SEA_SPEED_AUTH_PRIVILEGE_INSTALL=PASS"
echo "SOURCE_SHA=$SOURCE_SHA"
echo "DEPLOY_USER=$DEPLOY_USER"
echo "SUDO_COMMAND_SCOPE=FIXED_HELPER_NO_ARGS"
echo "ROOT_SHELL_GRANTED=NO"
echo "PRIVILEGED_TOPOLOGY=FIXED"
echo "CAMERA1_FRESHNESS_WATCHDOG=INSTALLED"
echo "CAMERA1_FRESHNESS_SERVICE=$WATCHDOG_SERVICE"
echo "CAMERA1_FRESHNESS_TIMER_UNIT=$WATCHDOG_TIMER"
echo "NGINX_ZEROTIER_WAIT_HELPER=INSTALLED"
echo "NGINX_ZEROTIER_DROPIN=INSTALLED"
