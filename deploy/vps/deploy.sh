#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <commit-sha>" >&2
  exit 2
fi

COMMIT_SHA="$1"
REPOSITORY="${SEA_SPEED_REPOSITORY:-MostDef2000/sea-speed}"
DEPLOY_ROOT="${SEA_SPEED_DEPLOY_ROOT:-/opt/sea-speed-deploy}"
API_TARGET="${SEA_SPEED_API_TARGET:-/opt/sea-speed-api/app/main.py}"
FRONTEND_TARGET="${SEA_SPEED_FRONTEND_TARGET:-/var/www/mostdef.ru/sea-speed/index.html}"
OBJECTS_FRONTEND_TARGET="${SEA_SPEED_OBJECTS_FRONTEND_TARGET:-/var/www/mostdef.ru/sea-speed/objects/index.html}"
CAMERAS_FRONTEND_TARGET="${SEA_SPEED_CAMERAS_FRONTEND_TARGET:-/var/www/mostdef.ru/sea-speed/cameras/index.html}"
ROAD_FRONTEND_TARGET="${SEA_SPEED_ROAD_FRONTEND_TARGET:-/var/www/mostdef.ru/sea-speed/road/index.html}"
ROOT_FRONTEND_TARGET="${SEA_SPEED_ROOT_FRONTEND_TARGET:-/var/www/mostdef.ru/index.html}"
SERVICE_NAME="sea-speed-api"
SYSTEMCTL_BIN="${SEA_SPEED_SYSTEMCTL_BIN:-/usr/bin/systemctl}"
ORIGIN_HEALTH_URL="${SEA_SPEED_ORIGIN_HEALTH_URL:-http://127.0.0.1:8010/api/health}"
PUBLIC_HEALTH_URL="${SEA_SPEED_HEALTH_URL:-https://mostdef.ru/sea-speed/api/health}"
FRONTEND_URL="${SEA_SPEED_FRONTEND_URL:-https://mostdef.ru/sea-speed/}"
OBJECTS_FRONTEND_URL="${SEA_SPEED_OBJECTS_FRONTEND_URL:-https://mostdef.ru/sea-speed/objects/}"
CAMERAS_FRONTEND_URL="${SEA_SPEED_CAMERAS_FRONTEND_URL:-https://mostdef.ru/sea-speed/cameras/}"
ROAD_FRONTEND_URL="${SEA_SPEED_ROAD_FRONTEND_URL:-https://mostdef.ru/sea-speed/road/}"
ROOT_FRONTEND_URL="${SEA_SPEED_ROOT_FRONTEND_URL:-https://mostdef.ru/}"
AUTH_BOUNDARY_REQUIRED="${SEA_SPEED_REQUIRE_AUTH_BOUNDARY:-0}"
AUTHENTIK_UPSTREAM="${SEA_SPEED_AUTHENTIK_UPSTREAM:-}"
WORKER_PRIVATE_LISTEN="${SEA_SPEED_WORKER_PRIVATE_LISTEN:-}"
WORKER_PRIVATE_PEER="${SEA_SPEED_WORKER_PRIVATE_PEER:-}"
EXPECTED_AUTHENTIK_UPSTREAM="http://10.123.239.102:19000"
EXPECTED_WORKER_PRIVATE_LISTEN="10.123.239.101:18080"
EXPECTED_WORKER_PRIVATE_PEER="10.123.239.102"
PRIVILEGED_HELPER="${SEA_SPEED_AUTH_PRIVILEGED_HELPER:-/usr/local/sbin/sea-speed-auth-privileged-helper}"
RELEASES_DIR="${DEPLOY_ROOT}/releases"
STATE_DIR="${DEPLOY_ROOT}/state"
CURRENT_FILE="${STATE_DIR}/current-release"
PREVIOUS_FILE="${STATE_DIR}/previous-release"
DEPLOYMENT_MANIFEST_FILE="${STATE_DIR}/deployment-manifest.json"
PRIVILEGED_REQUEST_FILE="${STATE_DIR}/auth-privileged-request.json"
TARGET_RELEASE="${RELEASES_DIR}/${COMMIT_SHA}"
TEMP_DIR="$(mktemp -d)"
AUTH_BOUNDARY_VERIFIED=false

cleanup() { rm -rf "$TEMP_DIR"; }
trap cleanup EXIT

log() { printf '[sea-speed-deploy] %s\n' "$*"; }

validate_sha() {
  [[ "$COMMIT_SHA" =~ ^[0-9a-f]{40}$ ]] || {
    echo "Commit SHA must already be a lowercase 40-character SHA" >&2
    exit 2
  }
}

validate_auth_boundary_inputs() {
  [[ "$AUTH_BOUNDARY_REQUIRED" == "0" || "$AUTH_BOUNDARY_REQUIRED" == "1" ]] || {
    echo "SEA_SPEED_REQUIRE_AUTH_BOUNDARY must be 0 or 1" >&2
    exit 2
  }
  if [[ "$AUTH_BOUNDARY_REQUIRED" == "1" ]]; then
    [[ "$AUTHENTIK_UPSTREAM" == "$EXPECTED_AUTHENTIK_UPSTREAM" ]] || {
      echo "SEA_SPEED_AUTHENTIK_UPSTREAM must equal the approved fixed topology" >&2
      exit 2
    }
    [[ "$WORKER_PRIVATE_LISTEN" == "$EXPECTED_WORKER_PRIVATE_LISTEN" ]] || {
      echo "SEA_SPEED_WORKER_PRIVATE_LISTEN must equal the approved fixed topology" >&2
      exit 2
    }
    [[ "$WORKER_PRIVATE_PEER" == "$EXPECTED_WORKER_PRIVATE_PEER" ]] || {
      echo "SEA_SPEED_WORKER_PRIVATE_PEER must equal the approved fixed topology" >&2
      exit 2
    }
    if [[ "$EUID" -ne 0 ]]; then
      command -v sudo >/dev/null 2>&1 || {
        echo "sudo is required for the restricted privileged helper" >&2
        exit 4
      }
    fi
  fi
}

validate_runtime_access() {
  [[ -x "$SYSTEMCTL_BIN" ]] || { echo "systemctl executable not found at ${SYSTEMCTL_BIN}" >&2; exit 1; }
  [[ -w "$(dirname "$API_TARGET")" ]] || { echo "Deploy user cannot write API directory: $(dirname "$API_TARGET")" >&2; exit 1; }
  [[ -w "$(dirname "$FRONTEND_TARGET")" ]] || { echo "Deploy user cannot write operator frontend directory: $(dirname "$FRONTEND_TARGET")" >&2; exit 1; }
  [[ -w "$(dirname "$ROOT_FRONTEND_TARGET")" ]] || { echo "Deploy user cannot write root frontend directory: $(dirname "$ROOT_FRONTEND_TARGET")" >&2; exit 1; }
  command -v python3 >/dev/null || { echo "python3 is required to write deployment evidence" >&2; exit 1; }
}

ensure_layout() {
  mkdir -p \
    "$RELEASES_DIR" \
    "$STATE_DIR" \
    "$(dirname "$OBJECTS_FRONTEND_TARGET")" \
    "$(dirname "$CAMERAS_FRONTEND_TARGET")" \
    "$(dirname "$ROAD_FRONTEND_TARGET")"
}

release_complete() {
  local root="$1"
  [[ -f "$root/api/app/main.py" && \
     -f "$root/frontend/sea-speed/index.html" && \
     -f "$root/frontend/sea-speed/objects/index.html" && \
     -f "$root/frontend/sea-speed/cameras/index.html" && \
     -f "$root/frontend/sea-speed/road/index.html" && \
     -f "$root/frontend/root/index.html" && \
     -f "$root/deploy/vps/sea-speed-auth-cutover.sh" && \
     -f "$root/deploy/vps/install-auth-privilege-boundary.sh" && \
     -f "$root/deploy/vps/sea-speed-auth-privileged-helper.py" && \
     -f "$root/scripts/operations/nginx_cam1_direct_h264.py" && \
     -f "$root/scripts/operations/nginx_sea_speed_auth.py" ]]
}

download_release() {
  if release_complete "$TARGET_RELEASE"; then
    log "Release ${COMMIT_SHA} already exists"
    return
  fi

  local archive="$TEMP_DIR/release.tar.gz"
  local extracted="$TEMP_DIR/extracted"
  local archive_sha
  local required
  mkdir -p "$extracted"

  log "Downloading exact commit ${COMMIT_SHA}"
  curl --fail --location --silent --show-error \
    "https://github.com/${REPOSITORY}/archive/${COMMIT_SHA}.tar.gz" \
    --output "$archive"
  archive_sha="$(sha256sum "$archive" | awk '{print $1}')"
  tar -xzf "$archive" -C "$extracted" --strip-components=1

  for required in \
    api/app/main.py \
    frontend/sea-speed/index.html \
    frontend/sea-speed/objects/index.html \
    frontend/sea-speed/cameras/index.html \
    frontend/sea-speed/road/index.html \
    frontend/root/index.html \
    deploy/vps/sea-speed-auth-cutover.sh \
    deploy/vps/install-auth-privilege-boundary.sh \
    deploy/vps/sea-speed-auth-privileged-helper.py \
    scripts/operations/nginx_cam1_direct_h264.py \
    scripts/operations/nginx_sea_speed_auth.py; do
    [[ -f "$extracted/$required" ]] || { echo "Release does not contain $required" >&2; exit 1; }
  done

  rm -rf "$TARGET_RELEASE"
  mkdir -p \
    "$TARGET_RELEASE/api/app" \
    "$TARGET_RELEASE/frontend/sea-speed/objects" \
    "$TARGET_RELEASE/frontend/sea-speed/cameras" \
    "$TARGET_RELEASE/frontend/sea-speed/road" \
    "$TARGET_RELEASE/frontend/root" \
    "$TARGET_RELEASE/deploy/vps" \
    "$TARGET_RELEASE/scripts/operations"
  install -m 0644 "$extracted/api/app/main.py" "$TARGET_RELEASE/api/app/main.py"
  install -m 0644 "$extracted/frontend/sea-speed/index.html" "$TARGET_RELEASE/frontend/sea-speed/index.html"
  install -m 0644 "$extracted/frontend/sea-speed/objects/index.html" "$TARGET_RELEASE/frontend/sea-speed/objects/index.html"
  install -m 0644 "$extracted/frontend/sea-speed/cameras/index.html" "$TARGET_RELEASE/frontend/sea-speed/cameras/index.html"
  install -m 0644 "$extracted/frontend/sea-speed/road/index.html" "$TARGET_RELEASE/frontend/sea-speed/road/index.html"
  install -m 0644 "$extracted/frontend/root/index.html" "$TARGET_RELEASE/frontend/root/index.html"
  install -m 0755 "$extracted/deploy/vps/sea-speed-auth-cutover.sh" "$TARGET_RELEASE/deploy/vps/sea-speed-auth-cutover.sh"
  install -m 0755 "$extracted/deploy/vps/install-auth-privilege-boundary.sh" "$TARGET_RELEASE/deploy/vps/install-auth-privilege-boundary.sh"
  install -m 0644 "$extracted/deploy/vps/sea-speed-auth-privileged-helper.py" "$TARGET_RELEASE/deploy/vps/sea-speed-auth-privileged-helper.py"
  install -m 0644 "$extracted/scripts/operations/nginx_cam1_direct_h264.py" "$TARGET_RELEASE/scripts/operations/nginx_cam1_direct_h264.py"
  install -m 0644 "$extracted/scripts/operations/nginx_sea_speed_auth.py" "$TARGET_RELEASE/scripts/operations/nginx_sea_speed_auth.py"
  printf '%s\n' "$COMMIT_SHA" > "$TARGET_RELEASE/commit-sha"
  printf '%s\n' "$archive_sha" > "$TARGET_RELEASE/archive-sha256"
}

write_privileged_request() {
  local action="$1"
  local temp="${PRIVILEGED_REQUEST_FILE}.tmp"
  python3 - "$temp" "$action" "$COMMIT_SHA" "$TARGET_RELEASE" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "schema": "sea_speed_auth_privileged_request_v1",
    "action": sys.argv[2],
    "source_sha": sys.argv[3],
    "release_path": sys.argv[4],
}
path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(path, 0o600)
PY
  mv -f "$temp" "$PRIVILEGED_REQUEST_FILE"
}

invoke_privileged_helper() {
  if [[ "$EUID" -eq 0 ]]; then
    "$PRIVILEGED_HELPER"
  else
    sudo -n "$PRIVILEGED_HELPER"
  fi
}

check_auth_privilege_boundary() {
  [[ "$AUTH_BOUNDARY_REQUIRED" == "1" ]] || return 0
  [[ -x "$PRIVILEGED_HELPER" ]] || {
    echo "ERROR restricted Auth privilege helper is not installed: $PRIVILEGED_HELPER" >&2
    echo "PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES" >&2
    return 41
  }

  write_privileged_request status
  local output rc
  set +e
  output="$(invoke_privileged_helper 2>&1)"
  rc=$?
  set -e
  printf '%s\n' "$output"
  [[ "$rc" -eq 0 ]] || {
    echo "PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES" >&2
    return "$rc"
  }
  grep -Fq 'SEA_SPEED_AUTH_PRIVILEGE_BOUNDARY=PASS' <<<"$output" || return 42
  grep -Fq "SOURCE_SHA=${COMMIT_SHA}" <<<"$output" || return 42
  grep -Fq 'ACTION=status' <<<"$output" || return 42
  grep -Fq 'ARBITRARY_ROOT_EXECUTION=NO' <<<"$output" || return 42
  log "Restricted Auth privilege boundary preflight passed before live source mutation"
}

bootstrap_current_release() {
  if [[ -s "$CURRENT_FILE" ]]; then return; fi
  if [[ ! -f "$API_TARGET" || ! -f "$FRONTEND_TARGET" || ! -f "$ROOT_FRONTEND_TARGET" ]]; then
    echo "Cannot bootstrap rollback release: current API or frontend file is missing" >&2
    exit 1
  fi

  local bootstrap_name="bootstrap-$(date -u +%Y%m%dT%H%M%SZ)"
  local bootstrap_release="$RELEASES_DIR/$bootstrap_name"
  log "Capturing the existing live code once as bootstrap rollback"
  mkdir -p "$bootstrap_release/api/app" "$bootstrap_release/frontend/sea-speed/objects" "$bootstrap_release/frontend/sea-speed/cameras" "$bootstrap_release/frontend/sea-speed/road" "$bootstrap_release/frontend/root"
  install -m 0644 "$API_TARGET" "$bootstrap_release/api/app/main.py"
  install -m 0644 "$FRONTEND_TARGET" "$bootstrap_release/frontend/sea-speed/index.html"
  if [[ -f "$OBJECTS_FRONTEND_TARGET" ]]; then
    install -m 0644 "$OBJECTS_FRONTEND_TARGET" "$bootstrap_release/frontend/sea-speed/objects/index.html"
  else
    touch "$bootstrap_release/frontend/sea-speed/objects/.absent"
  fi
  if [[ -f "$CAMERAS_FRONTEND_TARGET" ]]; then
    install -m 0644 "$CAMERAS_FRONTEND_TARGET" "$bootstrap_release/frontend/sea-speed/cameras/index.html"
  else
    touch "$bootstrap_release/frontend/sea-speed/cameras/.absent"
  fi
  if [[ -f "$ROAD_FRONTEND_TARGET" ]]; then
    install -m 0644 "$ROAD_FRONTEND_TARGET" "$bootstrap_release/frontend/sea-speed/road/index.html"
  else
    touch "$bootstrap_release/frontend/sea-speed/road/.absent"
  fi
  install -m 0644 "$ROOT_FRONTEND_TARGET" "$bootstrap_release/frontend/root/index.html"
  printf '%s\n' "$bootstrap_name" > "$bootstrap_release/commit-sha"
  printf '%s\n' "$bootstrap_name" > "$CURRENT_FILE"
}

ensure_current_release_has_root_frontend() {
  local current_name current_release
  current_name="$(cat "$CURRENT_FILE")"
  current_release="$RELEASES_DIR/$current_name"
  if [[ -f "$current_release/frontend/root/index.html" ]]; then return; fi
  [[ -f "$ROOT_FRONTEND_TARGET" ]] || {
    echo "Cannot preserve current root frontend for rollback: ${ROOT_FRONTEND_TARGET} is missing" >&2
    exit 1
  }
  log "Adding the existing live root frontend to current rollback release ${current_name}"
  mkdir -p "$current_release/frontend/root"
  install -m 0644 "$ROOT_FRONTEND_TARGET" "$current_release/frontend/root/index.html"
}

ensure_current_release_has_objects_frontend() {
  local current_name current_release objects_release_dir
  current_name="$(cat "$CURRENT_FILE")"
  current_release="$RELEASES_DIR/$current_name"
  objects_release_dir="$current_release/frontend/sea-speed/objects"
  if [[ -f "$objects_release_dir/index.html" || -f "$objects_release_dir/.absent" ]]; then return; fi
  log "Capturing current objects frontend state for rollback release ${current_name}"
  mkdir -p "$objects_release_dir"
  if [[ -f "$OBJECTS_FRONTEND_TARGET" ]]; then
    install -m 0644 "$OBJECTS_FRONTEND_TARGET" "$objects_release_dir/index.html"
  else
    touch "$objects_release_dir/.absent"
  fi
}

ensure_current_release_has_cameras_frontend() {
  local current_name current_release cameras_release_dir
  current_name="$(cat "$CURRENT_FILE")"
  current_release="$RELEASES_DIR/$current_name"
  cameras_release_dir="$current_release/frontend/sea-speed/cameras"
  if [[ -f "$cameras_release_dir/index.html" || -f "$cameras_release_dir/.absent" ]]; then return; fi
  log "Capturing current cameras frontend state for rollback release ${current_name}"
  mkdir -p "$cameras_release_dir"
  if [[ -f "$CAMERAS_FRONTEND_TARGET" ]]; then
    install -m 0644 "$CAMERAS_FRONTEND_TARGET" "$cameras_release_dir/index.html"
  else
    touch "$cameras_release_dir/.absent"
  fi
}

ensure_current_release_has_road_frontend() {
  local current_name current_release road_release_dir
  current_name="$(cat "$CURRENT_FILE")"
  current_release="$RELEASES_DIR/$current_name"
  road_release_dir="$current_release/frontend/sea-speed/road"
  if [[ -f "$road_release_dir/index.html" || -f "$road_release_dir/.absent" ]]; then return; fi
  log "Capturing current road frontend state for rollback release ${current_name}"
  mkdir -p "$road_release_dir"
  if [[ -f "$ROAD_FRONTEND_TARGET" ]]; then
    install -m 0644 "$ROAD_FRONTEND_TARGET" "$road_release_dir/index.html"
  else
    touch "$road_release_dir/.absent"
  fi
}

install_release() {
  local release_name="$1"
  local release_dir="$RELEASES_DIR/$release_name"
  [[ -f "$release_dir/api/app/main.py" ]] || { echo "Release ${release_name} has no API file" >&2; return 1; }
  [[ -f "$release_dir/frontend/sea-speed/index.html" ]] || { echo "Release ${release_name} has no operator frontend file" >&2; return 1; }
  [[ -f "$release_dir/frontend/sea-speed/objects/index.html" || -f "$release_dir/frontend/sea-speed/objects/.absent" ]] || { echo "Release ${release_name} has no objects frontend state" >&2; return 1; }
  [[ -f "$release_dir/frontend/sea-speed/cameras/index.html" || -f "$release_dir/frontend/sea-speed/cameras/.absent" ]] || { echo "Release ${release_name} has no cameras frontend state" >&2; return 1; }
  [[ -f "$release_dir/frontend/sea-speed/road/index.html" || -f "$release_dir/frontend/sea-speed/road/.absent" ]] || { echo "Release ${release_name} has no road frontend state" >&2; return 1; }
  [[ -f "$release_dir/frontend/root/index.html" ]] || { echo "Release ${release_name} has no root frontend file" >&2; return 1; }

  install -m 0644 "$release_dir/api/app/main.py" "${API_TARGET}.next"
  install -m 0644 "$release_dir/frontend/sea-speed/index.html" "${FRONTEND_TARGET}.next"
  install -m 0644 "$release_dir/frontend/root/index.html" "${ROOT_FRONTEND_TARGET}.next"
  if [[ -f "$release_dir/frontend/sea-speed/objects/index.html" ]]; then
    install -m 0644 "$release_dir/frontend/sea-speed/objects/index.html" "${OBJECTS_FRONTEND_TARGET}.next"
  fi
  if [[ -f "$release_dir/frontend/sea-speed/cameras/index.html" ]]; then
    install -m 0644 "$release_dir/frontend/sea-speed/cameras/index.html" "${CAMERAS_FRONTEND_TARGET}.next"
  fi
  if [[ -f "$release_dir/frontend/sea-speed/road/index.html" ]]; then
    install -m 0644 "$release_dir/frontend/sea-speed/road/index.html" "${ROAD_FRONTEND_TARGET}.next"
  fi

  mv -f "${API_TARGET}.next" "$API_TARGET"
  mv -f "${FRONTEND_TARGET}.next" "$FRONTEND_TARGET"
  mv -f "${ROOT_FRONTEND_TARGET}.next" "$ROOT_FRONTEND_TARGET"
  if [[ -f "$release_dir/frontend/sea-speed/objects/index.html" ]]; then
    mv -f "${OBJECTS_FRONTEND_TARGET}.next" "$OBJECTS_FRONTEND_TARGET"
  else
    rm -f "$OBJECTS_FRONTEND_TARGET" "${OBJECTS_FRONTEND_TARGET}.next"
  fi
  if [[ -f "$release_dir/frontend/sea-speed/cameras/index.html" ]]; then
    mv -f "${CAMERAS_FRONTEND_TARGET}.next" "$CAMERAS_FRONTEND_TARGET"
  else
    rm -f "$CAMERAS_FRONTEND_TARGET" "${CAMERAS_FRONTEND_TARGET}.next"
  fi
  if [[ -f "$release_dir/frontend/sea-speed/road/index.html" ]]; then
    mv -f "${ROAD_FRONTEND_TARGET}.next" "$ROAD_FRONTEND_TARGET"
  else
    rm -f "$ROAD_FRONTEND_TARGET" "${ROAD_FRONTEND_TARGET}.next"
  fi
}

verify_public_url() {
  local label="$1" target="$2" status
  status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 15 "$target")" || {
    echo "${label} request failed: ${target}" >&2
    return 1
  }
  case "$status" in
    200|301|302|307|308|401|403)
      log "${label} public smoke check passed with HTTP ${status}"
      ;;
    *)
      echo "${label} public smoke check failed with HTTP ${status}: ${target}" >&2
      return 1
      ;;
  esac
}

verify_frontends() {
  [[ -s "$FRONTEND_TARGET" ]] || { echo "Operator frontend file is missing or empty: ${FRONTEND_TARGET}" >&2; return 1; }
  [[ -s "$ROOT_FRONTEND_TARGET" ]] || { echo "Root frontend file is missing or empty: ${ROOT_FRONTEND_TARGET}" >&2; return 1; }

  verify_public_url "Operator frontend" "$FRONTEND_URL"
  verify_public_url "Public private-health boundary" "$PUBLIC_HEALTH_URL"
  if [[ -f "$OBJECTS_FRONTEND_TARGET" ]]; then
    [[ -s "$OBJECTS_FRONTEND_TARGET" ]] || { echo "Objects frontend file is empty: ${OBJECTS_FRONTEND_TARGET}" >&2; return 1; }
    verify_public_url "Objects frontend" "$OBJECTS_FRONTEND_URL"
  else
    log "Objects frontend is absent in this rollback release"
  fi
  if [[ -f "$CAMERAS_FRONTEND_TARGET" ]]; then
    [[ -s "$CAMERAS_FRONTEND_TARGET" ]] || { echo "Cameras frontend file is empty: ${CAMERAS_FRONTEND_TARGET}" >&2; return 1; }
    verify_public_url "Cameras frontend" "$CAMERAS_FRONTEND_URL"
  else
    log "Cameras frontend is absent in this rollback release"
  fi
  if [[ -f "$ROAD_FRONTEND_TARGET" ]]; then
    [[ -s "$ROAD_FRONTEND_TARGET" ]] || { echo "Road frontend file is empty: ${ROAD_FRONTEND_TARGET}" >&2; return 1; }
    verify_public_url "Road frontend" "$ROAD_FRONTEND_URL"
  else
    log "Road frontend is absent in this rollback release"
  fi
  verify_public_url "Root frontend" "$ROOT_FRONTEND_URL"
}

restart_and_verify() {
  sudo -n "$SYSTEMCTL_BIN" restart "$SERVICE_NAME"
  local attempt
  for attempt in {1..12}; do
    if curl --fail --silent --show-error --max-time 10 "$ORIGIN_HEALTH_URL" >/dev/null; then
      log "API origin health passed: ${ORIGIN_HEALTH_URL}"
      break
    fi
    if [[ "$attempt" -eq 12 ]]; then
      echo "API origin health check failed: ${ORIGIN_HEALTH_URL}" >&2
      return 1
    fi
    sleep 5
  done
  verify_frontends
}

run_auth_boundary() {
  AUTH_BOUNDARY_VERIFIED=false
  if [[ "$AUTH_BOUNDARY_REQUIRED" != "1" ]]; then
    log "Road private M2M Auth v1 boundary is not required for this invocation"
    return 0
  fi

  # The root-owned helper enforces the Auth cutover's --require-protected-baseline
  # mode and fixed private topology; deploy.sh never runs writable release code as root.
  write_privileged_request reconcile
  log "Reconciling exact Road private M2M Auth v1 boundary through restricted root helper"
  local output rc
  set +e
  output="$(invoke_privileged_helper 2>&1)"
  rc=$?
  set -e
  printf '%s\n' "$output"
  [[ "$rc" -eq 0 ]] || return "$rc"
  grep -Fq 'SEA_SPEED_AUTH_PRIVILEGE_BOUNDARY=PASS' <<<"$output" || return 1
  grep -Fq 'ACTION=reconcile' <<<"$output" || return 1
  grep -Fq 'SEA_SPEED_AUTH_CUTOVER=PASS' <<<"$output" || return 1
  grep -Fq 'WORKER_PRIVATE_ROAD_API_BASE=' <<<"$output" || return 1
  grep -Fq 'ROLLBACK_CAPABILITY=VERIFIED' <<<"$output" || return 1
  grep -Fq 'SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS' <<<"$output" || return 1
  AUTH_BOUNDARY_VERIFIED=true
}

write_deployment_manifest() {
  local active_version="$1" previous_version="$2" state="$3" runtime_verified="$4" attempted_version="${5:-}" auth_status="${6:-skipped}" artifact_sha=""
  if [[ -f "$RELEASES_DIR/$active_version/archive-sha256" ]]; then artifact_sha="$(cat "$RELEASES_DIR/$active_version/archive-sha256")"; fi

  python3 - "$DEPLOYMENT_MANIFEST_FILE" "$active_version" "$previous_version" "$artifact_sha" "$state" "$runtime_verified" "$attempted_version" "$auth_status" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
active, previous, artifact, state, verified, attempted, auth_status = sys.argv[2:]
checks = [
    {"name": "source_install", "status": "passed"},
    {"name": "api_origin_health", "status": "passed"},
    {"name": "public_private_health_smoke", "status": "passed"},
    {"name": "operator_frontend_smoke", "status": "passed"},
    {"name": "objects_frontend_release_state", "status": "passed"},
    {"name": "cameras_frontend_release_state", "status": "passed"},
    {"name": "road_frontend_release_state", "status": "passed"},
    {"name": "root_frontend_smoke", "status": "passed"},
]
if auth_status in {"passed", "failed", "skipped"}:
    checks.append({"name": "auth_v1_road_private_m2m", "status": auth_status})
payload = {
    "schema": "sea_speed_deployment_manifest_v1",
    "deliveryId": f"vps-{active[:12]}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
    "target": "vps",
    "sourceCommit": active,
    "attemptedSourceCommit": attempted or None,
    "previousVersion": previous or None,
    "artifactSha256": artifact or None,
    "installedAt": datetime.now(timezone.utc).isoformat(),
    "checks": checks,
    "rollbackTarget": previous or None,
    "runtimeVerified": verified == "true",
    "state": state,
}
temp = path.with_suffix(path.suffix + ".tmp")
temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(temp, path)
PY
}

prune_releases() {
  local current previous path name
  current="$(cat "$CURRENT_FILE" 2>/dev/null || true)"
  previous="$(cat "$PREVIOUS_FILE" 2>/dev/null || true)"
  for path in "$RELEASES_DIR"/*; do
    [[ -d "$path" ]] || continue
    name="$(basename "$path")"
    if [[ "$name" != "$current" && "$name" != "$previous" ]]; then
      if rm -rf -- "$path"; then
        log "Pruned stale release ${name}"
      else
        log "WARNING: unable to prune stale release ${name}; leaving remaining files in place"
      fi
    fi
  done
}

main() {
  validate_sha
  validate_auth_boundary_inputs
  validate_runtime_access
  ensure_layout
  download_release

  # This admission occurs after exact release staging but before any live source,
  # service, current-release, deployment-manifest, or nginx mutation.
  check_auth_privilege_boundary

  bootstrap_current_release
  ensure_current_release_has_root_frontend
  ensure_current_release_has_objects_frontend
  ensure_current_release_has_cameras_frontend
  ensure_current_release_has_road_frontend

  local old_current previous
  old_current="$(cat "$CURRENT_FILE")"
  previous="$(cat "$PREVIOUS_FILE" 2>/dev/null || true)"

  if [[ "$old_current" == "$COMMIT_SHA" ]]; then
    log "Commit ${COMMIT_SHA} is already deployed; verifying runtime and protected boundary"
    restart_and_verify
    if run_auth_boundary; then
      write_deployment_manifest "$COMMIT_SHA" "$previous" "runtime_verified" "true" "" "$([[ "$AUTH_BOUNDARY_VERIFIED" == true ]] && echo passed || echo skipped)"
      prune_releases
      return
    fi
    write_deployment_manifest "$COMMIT_SHA" "$previous" "failed" "false" "$COMMIT_SHA" "failed"
    echo "Road private M2M Auth v1 boundary verification failed for already-deployed source" >&2
    exit 1
  fi

  log "Deploying ${COMMIT_SHA}; rollback target is ${old_current}"
  install_release "$COMMIT_SHA"
  if restart_and_verify; then
    if run_auth_boundary; then
      printf '%s\n' "$old_current" > "$PREVIOUS_FILE"
      printf '%s\n' "$COMMIT_SHA" > "$CURRENT_FILE"
      write_deployment_manifest "$COMMIT_SHA" "$old_current" "runtime_verified" "true" "" "$([[ "$AUTH_BOUNDARY_VERIFIED" == true ]] && echo passed || echo skipped)"
      prune_releases
      log "Deployment successful: ${COMMIT_SHA}"
      return
    fi
  fi

  log "Deployment or protected boundary verification failed; rolling source files back to ${old_current}"
  install_release "$old_current"
  if ! restart_and_verify; then
    echo "Rollback health verification failed for ${old_current}" >&2
    exit 1
  fi
  write_deployment_manifest "$old_current" "$COMMIT_SHA" "rolled_back" "true" "$COMMIT_SHA" "skipped"
  log "Rollback successful: ${old_current}"
  exit 1
}

main "$@"
