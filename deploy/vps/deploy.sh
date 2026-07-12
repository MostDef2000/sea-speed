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
SERVICE_NAME="${SEA_SPEED_SERVICE:-sea-speed-api}"
HEALTH_URL="${SEA_SPEED_HEALTH_URL:-https://mostdef.ru/sea-speed/api/health}"
FRONTEND_URL="${SEA_SPEED_FRONTEND_URL:-https://mostdef.ru/sea-speed/}"
RELEASES_DIR="${DEPLOY_ROOT}/releases"
STATE_DIR="${DEPLOY_ROOT}/state"
CURRENT_FILE="${STATE_DIR}/current-release"
PREVIOUS_FILE="${STATE_DIR}/previous-release"
TARGET_RELEASE="${RELEASES_DIR}/${COMMIT_SHA}"
TEMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

log() {
  printf '[sea-speed-deploy] %s\n' "$*"
}

validate_sha() {
  [[ "$COMMIT_SHA" =~ ^[0-9a-fA-F]{40}$ ]] || {
    echo "Commit SHA must contain exactly 40 hexadecimal characters" >&2
    exit 2
  }
}

ensure_layout() {
  mkdir -p "$RELEASES_DIR" "$STATE_DIR"
  mkdir -p "$(dirname "$API_TARGET")" "$(dirname "$FRONTEND_TARGET")"
}

download_release() {
  if [[ -f "$TARGET_RELEASE/api/app/main.py" && -f "$TARGET_RELEASE/frontend/sea-speed/index.html" ]]; then
    log "Release ${COMMIT_SHA} already exists"
    return
  fi

  local archive="$TEMP_DIR/release.tar.gz"
  local extracted="$TEMP_DIR/extracted"
  mkdir -p "$extracted"

  log "Downloading exact commit ${COMMIT_SHA}"
  curl --fail --location --silent --show-error \
    "https://github.com/${REPOSITORY}/archive/${COMMIT_SHA}.tar.gz" \
    --output "$archive"
  tar -xzf "$archive" -C "$extracted" --strip-components=1

  [[ -f "$extracted/api/app/main.py" ]] || {
    echo "Release does not contain api/app/main.py" >&2
    exit 1
  }
  [[ -f "$extracted/frontend/sea-speed/index.html" ]] || {
    echo "Release does not contain frontend/sea-speed/index.html" >&2
    exit 1
  }

  rm -rf "$TARGET_RELEASE"
  mkdir -p "$TARGET_RELEASE/api/app" "$TARGET_RELEASE/frontend/sea-speed"
  install -m 0644 "$extracted/api/app/main.py" "$TARGET_RELEASE/api/app/main.py"
  install -m 0644 "$extracted/frontend/sea-speed/index.html" "$TARGET_RELEASE/frontend/sea-speed/index.html"
  printf '%s\n' "$COMMIT_SHA" > "$TARGET_RELEASE/commit-sha"
}

bootstrap_current_release() {
  if [[ -s "$CURRENT_FILE" ]]; then
    return
  fi

  if [[ ! -f "$API_TARGET" || ! -f "$FRONTEND_TARGET" ]]; then
    echo "Cannot bootstrap rollback release: current API or frontend file is missing" >&2
    exit 1
  fi

  local bootstrap_name="bootstrap-$(date -u +%Y%m%dT%H%M%SZ)"
  local bootstrap_release="$RELEASES_DIR/$bootstrap_name"

  log "Capturing the existing live code once as bootstrap rollback"
  mkdir -p "$bootstrap_release/api/app" "$bootstrap_release/frontend/sea-speed"
  install -m 0644 "$API_TARGET" "$bootstrap_release/api/app/main.py"
  install -m 0644 "$FRONTEND_TARGET" "$bootstrap_release/frontend/sea-speed/index.html"
  printf '%s\n' "$bootstrap_name" > "$bootstrap_release/commit-sha"
  printf '%s\n' "$bootstrap_name" > "$CURRENT_FILE"
}

install_release() {
  local release_name="$1"
  local release_dir="$RELEASES_DIR/$release_name"

  [[ -f "$release_dir/api/app/main.py" ]] || {
    echo "Release ${release_name} has no API file" >&2
    return 1
  }
  [[ -f "$release_dir/frontend/sea-speed/index.html" ]] || {
    echo "Release ${release_name} has no frontend file" >&2
    return 1
  }

  install -m 0644 "$release_dir/api/app/main.py" "${API_TARGET}.next"
  install -m 0644 "$release_dir/frontend/sea-speed/index.html" "${FRONTEND_TARGET}.next"
  mv -f "${API_TARGET}.next" "$API_TARGET"
  mv -f "${FRONTEND_TARGET}.next" "$FRONTEND_TARGET"
}

restart_and_verify() {
  systemctl restart "$SERVICE_NAME"

  local attempt
  for attempt in {1..12}; do
    if curl --fail --silent --show-error --max-time 10 "$HEALTH_URL" >/dev/null; then
      break
    fi
    if [[ "$attempt" -eq 12 ]]; then
      echo "API health check failed: ${HEALTH_URL}" >&2
      return 1
    fi
    sleep 5
  done

  curl --fail --silent --show-error --max-time 15 "$FRONTEND_URL" >/dev/null || {
    echo "Frontend smoke check failed: ${FRONTEND_URL}" >&2
    return 1
  }
}

prune_releases() {
  local current previous path name
  current="$(cat "$CURRENT_FILE" 2>/dev/null || true)"
  previous="$(cat "$PREVIOUS_FILE" 2>/dev/null || true)"

  for path in "$RELEASES_DIR"/*; do
    [[ -d "$path" ]] || continue
    name="$(basename "$path")"
    if [[ "$name" != "$current" && "$name" != "$previous" ]]; then
      rm -rf "$path"
    fi
  done
}

main() {
  validate_sha
  ensure_layout
  download_release
  bootstrap_current_release

  local old_current
  old_current="$(cat "$CURRENT_FILE")"

  if [[ "$old_current" == "$COMMIT_SHA" ]]; then
    log "Commit ${COMMIT_SHA} is already deployed; verifying runtime"
    restart_and_verify
    prune_releases
    return
  fi

  log "Deploying ${COMMIT_SHA}; rollback target is ${old_current}"
  install_release "$COMMIT_SHA"

  if restart_and_verify; then
    printf '%s\n' "$old_current" > "$PREVIOUS_FILE"
    printf '%s\n' "$COMMIT_SHA" > "$CURRENT_FILE"
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

  log "Rollback successful: ${old_current}"
  exit 1
}

main "$@"
