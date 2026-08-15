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
ROOT_FRONTEND_TARGET="${SEA_SPEED_ROOT_FRONTEND_TARGET:-/var/www/mostdef.ru/index.html}"
SERVICE_NAME="sea-speed-api"
SYSTEMCTL_BIN="${SEA_SPEED_SYSTEMCTL_BIN:-/usr/bin/systemctl}"
ORIGIN_HEALTH_URL="${SEA_SPEED_ORIGIN_HEALTH_URL:-http://127.0.0.1:8010/api/health}"
PUBLIC_HEALTH_URL="${SEA_SPEED_HEALTH_URL:-https://mostdef.ru/sea-speed/api/health}"
FRONTEND_URL="${SEA_SPEED_FRONTEND_URL:-https://mostdef.ru/sea-speed/}"
OBJECTS_FRONTEND_URL="${SEA_SPEED_OBJECTS_FRONTEND_URL:-https://mostdef.ru/sea-speed/objects/}"
CAMERAS_FRONTEND_URL="${SEA_SPEED_CAMERAS_FRONTEND_URL:-https://mostdef.ru/sea-speed/cameras/}"
ROOT_FRONTEND_URL="${SEA_SPEED_ROOT_FRONTEND_URL:-https://mostdef.ru/}"
RELEASES_DIR="${DEPLOY_ROOT}/releases"
STATE_DIR="${DEPLOY_ROOT}/state"
CURRENT_FILE="${STATE_DIR}/current-release"
PREVIOUS_FILE="${STATE_DIR}/previous-release"
DEPLOYMENT_MANIFEST_FILE="${STATE_DIR}/deployment-manifest.json"
TARGET_RELEASE="${RELEASES_DIR}/${COMMIT_SHA}"
TEMP_DIR="$(mktemp -d)"

cleanup() { rm -rf "$TEMP_DIR"; }
trap cleanup EXIT

log() { printf '[sea-speed-deploy] %s\n' "$*"; }

validate_sha() {
  [[ "$COMMIT_SHA" =~ ^[0-9a-fA-F]{40}$ ]] || {
    echo "Commit SHA must contain exactly 40 hexadecimal characters" >&2
    exit 2
  }
}

validate_runtime_access() {
  [[ -x "$SYSTEMCTL_BIN" ]] || { echo "systemctl executable not found at ${SYSTEMCTL_BIN}" >&2; exit 1; }
  [[ -w "$(dirname "$API_TARGET")" ]] || { echo "Deploy user cannot write API directory: $(dirname "$API_TARGET")" >&2; exit 1; }
  [[ -w "$(dirname "$FRONTEND_TARGET")" ]] || { echo "Deploy user cannot write operator frontend directory: $(dirname "$FRONTEND_TARGET")" >&2; exit 1; }
  [[ -w "$(dirname "$ROOT_FRONTEND_TARGET")" ]] || { echo "Deploy user cannot write root frontend directory: $(dirname "$ROOT_FRONTEND_TARGET")" >&2; exit 1; }
  command -v python3 >/dev/null || { echo "python3 is required to write deployment evidence" >&2; exit 1; }
}

ensure_layout() {
  mkdir -p "$RELEASES_DIR" "$STATE_DIR" "$(dirname "$OBJECTS_FRONTEND_TARGET")" "$(dirname "$CAMERAS_FRONTEND_TARGET")"
}

download_release() {
  if [[ -f "$TARGET_RELEASE/api/app/main.py" && \
        -f "$TARGET_RELEASE/frontend/sea-speed/index.html" && \
        -f "$TARGET_RELEASE/frontend/sea-speed/objects/index.html" && \
        -f "$TARGET_RELEASE/frontend/sea-speed/cameras/index.html" && \
        -f "$TARGET_RELEASE/frontend/root/index.html" ]]; then
    log "Release ${COMMIT_SHA} already exists"
    return
  fi

  local archive="$TEMP_DIR/release.tar.gz"
  local extracted="$TEMP_DIR/extracted"
  local archive_sha
  mkdir -p "$extracted"

  log "Downloading exact commit ${COMMIT_SHA}"
  curl --fail --location --silent --show-error \
    "https://github.com/${REPOSITORY}/archive/${COMMIT_SHA}.tar.gz" \
    --output "$archive"
  archive_sha="$(sha256sum "$archive" | awk '{print $1}')"
  tar -xzf "$archive" -C "$extracted" --strip-components=1

  [[ -f "$extracted/api/app/main.py" ]] || { echo "Release does not contain api/app/main.py" >&2; exit 1; }
  [[ -f "$extracted/frontend/sea-speed/index.html" ]] || { echo "Release does not contain frontend/sea-speed/index.html" >&2; exit 1; }
  [[ -f "$extracted/frontend/sea-speed/objects/index.html" ]] || { echo "Release does not contain frontend/sea-speed/objects/index.html" >&2; exit 1; }
  [[ -f "$extracted/frontend/sea-speed/cameras/index.html" ]] || { echo "Release does not contain frontend/sea-speed/cameras/index.html" >&2; exit 1; }
  [[ -f "$extracted/frontend/root/index.html" ]] || { echo "Release does not contain frontend/root/index.html" >&2; exit 1; }

  rm -rf "$TARGET_RELEASE"
  mkdir -p "$TARGET_RELEASE/api/app" "$TARGET_RELEASE/frontend/sea-speed/objects" "$TARGET_RELEASE/frontend/sea-speed/cameras" "$TARGET_RELEASE/frontend/root"
  install -m 0644 "$extracted/api/app/main.py" "$TARGET_RELEASE/api/app/main.py"
  install -m 0644 "$extracted/frontend/sea-speed/index.html" "$TARGET_RELEASE/frontend/sea-speed/index.html"
  install -m 0644 "$extracted/frontend/sea-speed/objects/index.html" "$TARGET_RELEASE/frontend/sea-speed/objects/index.html"
  install -m 0644 "$extracted/frontend/sea-speed/cameras/index.html" "$TARGET_RELEASE/frontend/sea-speed/cameras/index.html"
  install -m 0644 "$extracted/frontend/root/index.html" "$TARGET_RELEASE/frontend/root/index.html"
  printf '%s\n' "$COMMIT_SHA" > "$TARGET_RELEASE/commit-sha"
  printf '%s\n' "$archive_sha" > "$TARGET_RELEASE/archive-sha256"
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
  mkdir -p "$bootstrap_release/api/app" "$bootstrap_release/frontend/sea-speed/objects" "$bootstrap_release/frontend/sea-speed/cameras" "$bootstrap_release/frontend/root"
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
  install -m 0644 "$ROOT_FRONTEND_TARGET" "$bootstrap_release/frontend/root/index.html"
  printf '%s\n' "$bootstrap_name" > "$bootstrap_release/commit-sha"
  printf '%s\n' "$bootstrap_name" > "$CURRENT_FILE"
}

ensure_current_release_has_root_frontend() {
  local current_name current_release
  current_name="$(cat "$CURRENT_FILE")"
  current_release="$RELEASES_DIR/$current_name"
  if [[ -f "$current_release/frontend/root/index.html" ]]; then return; fi
  [[ -f "$ROOT_FRONTEND_TARGET" ]] || { echo "Cannot preserve current root frontend for rollback: ${ROOT_FRONTEND_TARGET} is missing" >&2; exit 1; }
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

install_release() {
  local release_name="$1"
  local release_dir="$RELEASES_DIR/$release_name"
  [[ -f "$release_dir/api/app/main.py" ]] || { echo "Release ${release_name} has no API file" >&2; return 1; }
  [[ -f "$release_dir/frontend/sea-speed/index.html" ]] || { echo "Release ${release_name} has no operator frontend file" >&2; return 1; }
  [[ -f "$release_dir/frontend/sea-speed/objects/index.html" || -f "$release_dir/frontend/sea-speed/objects/.absent" ]] || { echo "Release ${release_name} has no objects frontend state" >&2; return 1; }
  [[ -f "$release_dir/frontend/sea-speed/cameras/index.html" || -f "$release_dir/frontend/sea-speed/cameras/.absent" ]] || { echo "Release ${release_name} has no cameras frontend state" >&2; return 1; }
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

  # During the source-deploy step these URLs can still return 200 under the
  # legacy boundary. After the separately approved Auth v1 nginx cutover they
  # return an Authentik redirect/deny. Either state is a valid code-deploy
  # smoke result; security acceptance is performed by sea-speed-auth-cutover.sh.
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

write_deployment_manifest() {
  local active_version="$1" previous_version="$2" state="$3" runtime_verified="$4" attempted_version="${5:-}" artifact_sha=""
  if [[ -f "$RELEASES_DIR/$active_version/archive-sha256" ]]; then artifact_sha="$(cat "$RELEASES_DIR/$active_version/archive-sha256")"; fi

  python3 - "$DEPLOYMENT_MANIFEST_FILE" "$active_version" "$previous_version" "$artifact_sha" "$state" "$runtime_verified" "$attempted_version" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
active, previous, artifact, state, verified, attempted = sys.argv[2:]
payload = {
    "schema": "sea_speed_deployment_manifest_v1",
    "deliveryId": f"vps-{active[:12]}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
    "target": "vps",
    "sourceCommit": active,
    "attemptedSourceCommit": attempted or None,
    "previousVersion": previous or None,
    "artifactSha256": artifact or None,
    "installedAt": datetime.now(timezone.utc).isoformat(),
    "checks": [
        {"name": "source_install", "status": "passed"},
        {"name": "api_origin_health", "status": "passed"},
        {"name": "public_private_health_smoke", "status": "passed"},
        {"name": "operator_frontend_smoke", "status": "passed"},
        {"name": "objects_frontend_release_state", "status": "passed"},
        {"name": "cameras_frontend_release_state", "status": "passed"},
        {"name": "root_frontend_smoke", "status": "passed"},
    ],
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
    if [[ "$name" != "$current" && "$name" != "$previous" ]]; then rm -rf "$path"; fi
  done
}

main() {
  validate_sha
  validate_runtime_access
  ensure_layout
  download_release
  bootstrap_current_release
  ensure_current_release_has_root_frontend
  ensure_current_release_has_objects_frontend
  ensure_current_release_has_cameras_frontend

  local old_current previous
  old_current="$(cat "$CURRENT_FILE")"
  previous="$(cat "$PREVIOUS_FILE" 2>/dev/null || true)"

  if [[ "$old_current" == "$COMMIT_SHA" ]]; then
    log "Commit ${COMMIT_SHA} is already deployed; verifying runtime"
    restart_and_verify
    write_deployment_manifest "$COMMIT_SHA" "$previous" "runtime_verified" "true"
    prune_releases
    return
  fi

  log "Deploying ${COMMIT_SHA}; rollback target is ${old_current}"
  install_release "$COMMIT_SHA"
  if restart_and_verify; then
    printf '%s\n' "$old_current" > "$PREVIOUS_FILE"
    printf '%s\n' "$COMMIT_SHA" > "$CURRENT_FILE"
    write_deployment_manifest "$COMMIT_SHA" "$old_current" "runtime_verified" "true"
    prune_releases
    log "Deployment successful: ${COMMIT_SHA}"
    return
  fi

  log "Deployment failed; rolling back to ${old_current}"
  install_release "$old_current"
  if ! restart_and_verify; then
    echo "Rollback health verification failed for ${old_current}" >&2
    exit 1
  fi
  write_deployment_manifest "$old_current" "$COMMIT_SHA" "rolled_back" "true" "$COMMIT_SHA"
  log "Rollback successful: ${old_current}"
  exit 1
}

main "$@"