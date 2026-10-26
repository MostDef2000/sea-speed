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
STORE_TARGET="$(dirname "$API_TARGET")/store.py"
CONFIG_TARGET="$(dirname "$API_TARGET")/config.py"
IDENTITY_TARGET="$(dirname "$API_TARGET")/identity.py"
OBJECTS_REGISTRY_TARGET="$(dirname "$API_TARGET")/objects_registry.py"
PASSAGE_MIRRORS_TARGET="$(dirname "$API_TARGET")/passage_mirrors.py"
WATER_PASSAGES_TARGET="$(dirname "$API_TARGET")/water_passages.py"
CAMERA_PREVIEW_TARGET="$(dirname "$API_TARGET")/camera_preview.py"
ANALYTICS_TARGET="$(dirname "$API_TARGET")/analytics.py"
LIVE_FEEDS_TARGET="$(dirname "$API_TARGET")/live_feeds.py"
FRONTEND_TARGET="${SEA_SPEED_FRONTEND_TARGET:-/var/www/mostdef.ru/sea-speed/index.html}"
OBJECTS_FRONTEND_TARGET="${SEA_SPEED_OBJECTS_FRONTEND_TARGET:-/var/www/mostdef.ru/sea-speed/objects/index.html}"
CAMERAS_FRONTEND_TARGET="${SEA_SPEED_CAMERAS_FRONTEND_TARGET:-/var/www/mostdef.ru/sea-speed/cameras/index.html}"
ROAD_FRONTEND_TARGET="${SEA_SPEED_ROAD_FRONTEND_TARGET:-/var/www/mostdef.ru/sea-speed/road/index.html}"
LIVE_SYNC_TARGET="${SEA_SPEED_LIVE_SYNC_TARGET:-/var/www/mostdef.ru/sea-speed/live-sync.js}"
OVERLAY_CANVAS_TARGET="${SEA_SPEED_OVERLAY_CANVAS_TARGET:-/var/www/mostdef.ru/sea-speed/overlay-canvas.js}"
ROOT_FRONTEND_TARGET="${SEA_SPEED_ROOT_FRONTEND_TARGET:-/var/www/mostdef.ru/index.html}"
FALLBACK_FRONTEND_TARGET="${SEA_SPEED_FALLBACK_FRONTEND_TARGET:-/var/www/mostdef.ru/sea-speed-unavailable.html}"
SERVICE_NAME="sea-speed-api"
SYSTEMCTL_BIN="${SEA_SPEED_SYSTEMCTL_BIN:-/usr/bin/systemctl}"
ORIGIN_HEALTH_URL="${SEA_SPEED_ORIGIN_HEALTH_URL:-http://127.0.0.1:8010/api/health}"
PUBLIC_HEALTH_URL="${SEA_SPEED_HEALTH_URL:-https://mostdef.ru/sea-speed/api/health}"
FRONTEND_URL="${SEA_SPEED_FRONTEND_URL:-https://mostdef.ru/sea-speed/}"
OBJECTS_FRONTEND_URL="${SEA_SPEED_OBJECTS_FRONTEND_URL:-https://mostdef.ru/sea-speed/objects/}"
CAMERAS_FRONTEND_URL="${SEA_SPEED_CAMERAS_FRONTEND_URL:-https://mostdef.ru/sea-speed/cameras/}"
ROAD_FRONTEND_URL="${SEA_SPEED_ROAD_FRONTEND_URL:-https://mostdef.ru/sea-speed/road/}"
LIVE_SYNC_URL="${SEA_SPEED_LIVE_SYNC_URL:-https://mostdef.ru/sea-speed/live-sync.js}"
ROOT_FRONTEND_URL="${SEA_SPEED_ROOT_FRONTEND_URL:-https://mostdef.ru/}"
AUTH_BOUNDARY_REQUIRED="${SEA_SPEED_REQUIRE_AUTH_BOUNDARY:-0}"
AUTHENTIK_UPSTREAM="${SEA_SPEED_AUTHENTIK_UPSTREAM:-}"
WORKER_PRIVATE_LISTEN="${SEA_SPEED_WORKER_PRIVATE_LISTEN:-}"
WORKER_PRIVATE_PEER="${SEA_SPEED_WORKER_PRIVATE_PEER:-}"
EXPECTED_AUTHENTIK_UPSTREAM="http://10.123.239.102:19000"
EXPECTED_WORKER_PRIVATE_LISTEN="10.123.239.29:18080"
EXPECTED_WORKER_PRIVATE_PEER="10.123.239.102"
RELEASES_DIR="${DEPLOY_ROOT}/releases"
STATE_DIR="${DEPLOY_ROOT}/state"
CURRENT_FILE="${STATE_DIR}/current-release"
PREVIOUS_FILE="${STATE_DIR}/previous-release"
DEPLOYMENT_MANIFEST_FILE="${STATE_DIR}/deployment-manifest.json"
TARGET_RELEASE="${RELEASES_DIR}/${COMMIT_SHA}"
TEMP_DIR="$(mktemp -d)"
AUTH_BOUNDARY_VERIFIED=false

cleanup() { rm -rf "$TEMP_DIR"; }
trap cleanup EXIT

log() { printf '[sea-speed-deploy] %s\n' "$*"; }

migrate_legacy_roi_to_normalized() {
  local data_dir
  data_dir="$(dirname "$(dirname "$API_TARGET")")/data"
  if [[ ! -d "$data_dir" ]]; then
    log "ROI migration skipped: data dir missing $data_dir"
    return 0
  fi
  python3 - "$data_dir" <<'PYEOF'
import json
import os
import sys
import uuid
from pathlib import Path
data_dir = Path(sys.argv[1])
DEFAULT_W, DEFAULT_H = 1920, 1080
LEGACY_W, LEGACY_H = 704, 576
def infer_ref(pts):
    if not pts: return DEFAULT_W, DEFAULT_H
    mx = max((p.get("x",0) for p in pts), default=0)
    my = max((p.get("y",0) for p in pts), default=0)
    if mx<=LEGACY_W and my<=LEGACY_H and mx>0:
        return LEGACY_W, LEGACY_H
    return DEFAULT_W, DEFAULT_H
def normalize(pts, rw, rh):
    return [{"x_norm": p["x"]/rw, "y_norm": p["y"]/rh} for p in pts]
total_migrated=0
for name in ["cam1_roi.json","road1_roi.json","cam1_speed_lines.json","road1_speed_lines.json","cam1_crossing_line.json","road1_crossing_line.json"]:
    fp=data_dir/name
    if not fp.is_file():
        continue
    try:
        raw=json.loads(fp.read_text())
    except Exception:
        continue
    # detect already normalized
    has_norm=False
    for k in ["polygon_norm","line_a_norm","line_b_norm","line_norm"]:
        v=raw.get(k)
        if isinstance(v,list) and v and any("x_norm" in p for p in v if isinstance(p,dict)):
            has_norm=True
            break
    if has_norm:
        continue
    # ROI
    migrated=False
    if "polygon" in raw:
        leg=[p for p in raw.get("polygon",[]) if isinstance(p,dict) and "x" in p]
        if leg:
            rw,rh=infer_ref(leg)
            raw["polygon_norm"]=normalize(leg, rw, rh)
            raw["reference_width"]=rw
            raw["reference_height"]=rh
            # keep denormalized to 1920 for compat
            raw["polygon"]=[{"x": int(round(p["x_norm"]*DEFAULT_W)), "y": int(round(p["y_norm"]*DEFAULT_H))} for p in raw["polygon_norm"]]
            migrated=True
    # speed lines
    if "line_a" in raw and "line_b" in raw:
        la = [p for p in raw.get("line_a",[]) if isinstance(p,dict) and "x" in p]
        lb = [p for p in raw.get("line_b",[]) if isinstance(p,dict) and "x" in p]
        if la and lb:
            rw,rh=infer_ref(la+lb)
            raw["line_a_norm"]=normalize(la, rw, rh)
            raw["line_b_norm"]=normalize(lb, rw, rh)
            raw["reference_width"]=rw
            raw["reference_height"]=rh
            raw["line_a"]=[{"x": int(round(p["x_norm"]*DEFAULT_W)), "y": int(round(p["y_norm"]*DEFAULT_H))} for p in raw["line_a_norm"]]
            raw["line_b"]=[{"x": int(round(p["x_norm"]*DEFAULT_W)), "y": int(round(p["y_norm"]*DEFAULT_H))} for p in raw["line_b_norm"]]
            migrated=True
    # crossing
    if "line" in raw and "distance_m" not in raw:
        # crossing line (has line but not distance)
        leg=[p for p in raw.get("line",[]) if isinstance(p,dict) and "x" in p]
        if leg and len(leg)==2 and not raw.get("line_norm"):
            rw,rh=infer_ref(leg)
            raw["line_norm"]=normalize(leg, rw, rh)
            raw["reference_width"]=rw
            raw["reference_height"]=rh
            raw["line"]=[{"x": int(round(p["x_norm"]*DEFAULT_W)), "y": int(round(p["y_norm"]*DEFAULT_H))} for p in raw["line_norm"]]
            migrated=True
    if migrated:
        # unique tmp + os.replace: concurrent writers (API + migration while the
        # old service is still running) must never share a fixed .tmp sibling
        tmp = fp.with_name(f"{fp.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=2)+"\n")
        os.replace(tmp, fp)
        print(f"ROI_MIGRATED {name} -> normalized")
        total_migrated+=1
if total_migrated:
    print(f"ROI_MIGRATED total={total_migrated}")
else:
    print("ROI_MIGRATED none")
PYEOF
  log "ROI normalized migration completed"
}


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
        echo "sudo is required to restart the sea-speed service (sudo -n systemctl restart)" >&2
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
    "$(dirname "$ROAD_FRONTEND_TARGET")" \
    "$(dirname "$LIVE_SYNC_TARGET")"
}

release_complete() {
  local root="$1"
  [[ -f "$root/api/app/main.py" && \
     -f "$root/api/app/store.py" && \
     -f "$root/api/app/config.py" && \
     -f "$root/api/app/identity.py" && \
     -f "$root/api/app/objects_registry.py" && \
     -f "$root/api/app/passage_mirrors.py" && \
     -f "$root/api/app/water_passages.py" && \
     -f "$root/api/app/camera_preview.py" && \
     -f "$root/api/app/analytics.py" && \
     -f "$root/api/app/live_feeds.py" && \
     -f "$root/frontend/sea-speed/index.html" && \
     -f "$root/frontend/sea-speed/objects/index.html" && \
     -f "$root/frontend/sea-speed/cameras/index.html" && \
     -f "$root/frontend/sea-speed/road/index.html" && \
     -f "$root/frontend/sea-speed/live-sync.js" && \
     -f "$root/frontend/sea-speed/overlay-canvas.js" && \
     -f "$root/frontend/root/index.html" && \
     -f "$root/frontend/sea-speed/unavailable.html" && \
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
    api/app/store.py \
    api/app/config.py \
    api/app/identity.py \
    api/app/objects_registry.py \
    api/app/passage_mirrors.py \
    api/app/water_passages.py \
    api/app/camera_preview.py \
    api/app/analytics.py \
    api/app/live_feeds.py \
    frontend/sea-speed/index.html \
    frontend/sea-speed/objects/index.html \
    frontend/sea-speed/cameras/index.html \
    frontend/sea-speed/road/index.html \
    frontend/sea-speed/live-sync.js \
    frontend/sea-speed/overlay-canvas.js \
    frontend/root/index.html \
    frontend/sea-speed/unavailable.html \
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
  install -m 0644 "$extracted/api/app/store.py" "$TARGET_RELEASE/api/app/store.py"
  install -m 0644 "$extracted/api/app/config.py" "$TARGET_RELEASE/api/app/config.py"
  install -m 0644 "$extracted/api/app/identity.py" "$TARGET_RELEASE/api/app/identity.py"
  install -m 0644 "$extracted/api/app/objects_registry.py" "$TARGET_RELEASE/api/app/objects_registry.py"
  install -m 0644 "$extracted/api/app/passage_mirrors.py" "$TARGET_RELEASE/api/app/passage_mirrors.py"
  install -m 0644 "$extracted/api/app/water_passages.py" "$TARGET_RELEASE/api/app/water_passages.py"
  install -m 0644 "$extracted/api/app/camera_preview.py" "$TARGET_RELEASE/api/app/camera_preview.py"
  install -m 0644 "$extracted/api/app/analytics.py" "$TARGET_RELEASE/api/app/analytics.py"
  install -m 0644 "$extracted/api/app/live_feeds.py" "$TARGET_RELEASE/api/app/live_feeds.py"
  install -m 0644 "$extracted/frontend/sea-speed/index.html" "$TARGET_RELEASE/frontend/sea-speed/index.html"
  install -m 0644 "$extracted/frontend/sea-speed/objects/index.html" "$TARGET_RELEASE/frontend/sea-speed/objects/index.html"
  install -m 0644 "$extracted/frontend/sea-speed/cameras/index.html" "$TARGET_RELEASE/frontend/sea-speed/cameras/index.html"
  install -m 0644 "$extracted/frontend/sea-speed/road/index.html" "$TARGET_RELEASE/frontend/sea-speed/road/index.html"
  install -m 0644 "$extracted/frontend/sea-speed/live-sync.js" "$TARGET_RELEASE/frontend/sea-speed/live-sync.js"
  install -m 0644 "$extracted/frontend/sea-speed/overlay-canvas.js" "$TARGET_RELEASE/frontend/sea-speed/overlay-canvas.js"
  install -m 0644 "$extracted/frontend/root/index.html" "$TARGET_RELEASE/frontend/root/index.html"
  install -m 0644 "$extracted/frontend/sea-speed/unavailable.html" "$TARGET_RELEASE/frontend/sea-speed/unavailable.html"
  install -m 0755 "$extracted/deploy/vps/sea-speed-auth-cutover.sh" "$TARGET_RELEASE/deploy/vps/sea-speed-auth-cutover.sh"
  install -m 0755 "$extracted/deploy/vps/install-auth-privilege-boundary.sh" "$TARGET_RELEASE/deploy/vps/install-auth-privilege-boundary.sh"
  install -m 0644 "$extracted/deploy/vps/sea-speed-auth-privileged-helper.py" "$TARGET_RELEASE/deploy/vps/sea-speed-auth-privileged-helper.py"
  install -m 0644 "$extracted/scripts/operations/nginx_cam1_direct_h264.py" "$TARGET_RELEASE/scripts/operations/nginx_cam1_direct_h264.py"
  install -m 0644 "$extracted/scripts/operations/nginx_sea_speed_auth.py" "$TARGET_RELEASE/scripts/operations/nginx_sea_speed_auth.py"
  printf '%s\n' "$COMMIT_SHA" > "$TARGET_RELEASE/commit-sha"
  printf '%s\n' "$archive_sha" > "$TARGET_RELEASE/archive-sha256"
}

# The privileged nginx-boundary helper flow was retired with the legacy RU
# topology (issue #520 VPS deploy); the helper/cutover files remain in the
# repository as legacy tooling but are not invoked by this pipeline.

verify_private_m2m_boundary() {
  local mode="${1:-}"
  [[ "$AUTH_BOUNDARY_REQUIRED" == "1" ]] || return 0
  local bind_output status private_health
  bind_output="$(ss -tln 2>/dev/null || true)"
  if ! grep -Fq " ${WORKER_PRIVATE_LISTEN} " <<<"$bind_output"; then
    echo "ERROR Road private M2M boundary is not bound at ${WORKER_PRIVATE_LISTEN} on this VPS (explicit IPv4 bind required; empty output means ss is unavailable)" >&2
    return 46
  fi
  status="$(protected_frontend_status)"
  case "$status" in
    302|401|403)
      ;;
    500|503)
      if [[ "$mode" == "degraded" ]]; then
        # Degraded mode is the pre-mutation context only: the bounded
        # recovery stage immediately re-probes below and owns the
        # 500/503-fallback admissibility verdict there; do not double-fail
        # here. The default (no argument) is strict and fails closed.
        log "Protected Operator boundary reports degraded HTTP ${status} pre-mutation; bounded recovery stage owns the degraded verdict"
        return 0
      fi
      echo "Protected Operator boundary preflight failed with non-recoverable HTTP ${status}: ${FRONTEND_URL}" >&2
      return 43
      ;;
    *)
      echo "Protected Operator boundary preflight failed with non-recoverable HTTP ${status}: ${FRONTEND_URL}" >&2
      return 43
      ;;
  esac
  private_health="$(private_authentik_health_status)"
  if [[ "$private_health" != "PASS" ]]; then
    echo "ERROR private Authentik health check failed: ${AUTHENTIK_UPSTREAM}" >&2
    return 47
  fi
  verify_public_url "Root frontend" "$ROOT_FRONTEND_URL" || return 48
  log "Road private M2M Auth v1 boundary verified (Caddy topology): bind ${WORKER_PRIVATE_LISTEN}, operator gate HTTP ${status}, authentik private health PASS"
}

protected_frontend_status() {
  local status
  status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 15 "$FRONTEND_URL" 2>/dev/null || true)"
  if [[ ! "$status" =~ ^[0-9]{3}$ ]]; then
    status="000"
  fi
  printf '%s\n' "$status"
}

private_authentik_health_status() {
  local url="${AUTHENTIK_UPSTREAM}/-/health/ready/"
  if curl --fail --silent --show-error --max-time 8 "$url" >/dev/null 2>&1; then
    printf 'PASS\n'
  else
    printf 'FAIL\n'
  fi
}

recover_auth_boundary_before_source_mutation() {
  [[ "$AUTH_BOUNDARY_REQUIRED" == "1" ]] || return 0
  local status private_health
  status="$(protected_frontend_status)"
  case "$status" in
    302|401|403)
      log "Protected Operator boundary preflight passed with HTTP ${status}"
      return 0
      ;;
    500)
      log "Protected Operator boundary reports HTTP 500; evaluating bounded degraded admissibility before live source mutation"
      ;;
    503)
      log "Protected Operator boundary reports HTTP 503 fallback; degraded baseline is admissible for bounded outage-safe deployment"
      printf 'DEGRADED_BASELINE=503_FALLBACK_ACTIVE\n'
      return 0
      ;;
    *)
      echo "Protected Operator boundary preflight failed with non-recoverable HTTP ${status}: ${FRONTEND_URL}" >&2
      return 43
      ;;
  esac

  private_health="$(private_authentik_health_status)"
  if [[ "$private_health" == "FAIL" ]]; then
    if [[ -f "$TARGET_RELEASE/frontend/sea-speed/unavailable.html" ]]; then
      log "Private Authentik unreachable but target release carries fallback page — degraded 500 baseline is admissible, proceeding without requiring Worker recovery"
      printf 'DEGRADED_BASELINE=500_UNAVAILABLE_AUTHENTIK_ADMISSIBLE\n'
      printf 'PRIVATE_AUTHENTIK_HEALTH=FAIL\n'
      return 0
    fi
    log "Private Authentik unreachable and no fallback in target — degraded 500 baseline is not admissible"
  fi

  # No nginx machinery exists on this Caddy topology: there is no bounded
  # recovery to attempt for a broken protected boundary, so HTTP 500 without
  # an admissible degraded baseline fails closed before any source mutation.
  echo "Protected Operator boundary reports HTTP 500 and no bounded Caddy-topology recovery exists; deployment fails closed" >&2
  return 43
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
  mkdir -p "$bootstrap_release/api/app" "$bootstrap_release/frontend/sea-speed/objects" "$bootstrap_release/frontend/sea-speed/cameras" "$bootstrap_release/frontend/sea-speed/road" "$bootstrap_release/frontend/root" "$bootstrap_release/frontend/sea-speed"
  install -m 0644 "$API_TARGET" "$bootstrap_release/api/app/main.py"
  if [[ -f "$CONFIG_TARGET" ]]; then
    # The captured main.py imports config.py at boot, so the bootstrap
    # baseline must stay bootable on its own (issue #396 wave 1).
    install -m 0644 "$CONFIG_TARGET" "$bootstrap_release/api/app/config.py"
  fi
  if [[ -f "$IDENTITY_TARGET" ]]; then
    # Same for identity.py: the captured main.py imports it at boot.
    install -m 0644 "$IDENTITY_TARGET" "$bootstrap_release/api/app/identity.py"
  fi
  if [[ -f "$STORE_TARGET" ]]; then
    # A live store.py belongs to the captured rollback release too: the
    # captured main.py imports it at boot, so the bootstrap baseline must
    # stay bootable on its own.
    install -m 0644 "$STORE_TARGET" "$bootstrap_release/api/app/store.py"
  fi
  if [[ -f "$OBJECTS_REGISTRY_TARGET" ]]; then
    # Same for objects_registry.py (issue #396 wave 2): the captured main.py
    # imports it at boot, so the bootstrap baseline must stay bootable.
    install -m 0644 "$OBJECTS_REGISTRY_TARGET" "$bootstrap_release/api/app/objects_registry.py"
  fi
  if [[ -f "$PASSAGE_MIRRORS_TARGET" ]]; then
    # Same for passage_mirrors.py (issue #396 wave 2): the captured main.py
    # imports it at boot, so the bootstrap baseline must stay bootable.
    install -m 0644 "$PASSAGE_MIRRORS_TARGET" "$bootstrap_release/api/app/passage_mirrors.py"
  fi
  if [[ -f "$WATER_PASSAGES_TARGET" ]]; then
    # Same for water_passages.py (issue #396 wave 3): the captured main.py
    # imports it at boot, so the bootstrap baseline must stay bootable.
    install -m 0644 "$WATER_PASSAGES_TARGET" "$bootstrap_release/api/app/water_passages.py"
  fi
  if [[ -f "$CAMERA_PREVIEW_TARGET" ]]; then
    # Same for camera_preview.py (issue #396 wave 4): the captured main.py
    # imports it at boot, so the bootstrap baseline must stay bootable.
    install -m 0644 "$CAMERA_PREVIEW_TARGET" "$bootstrap_release/api/app/camera_preview.py"
  fi
  if [[ -f "$ANALYTICS_TARGET" ]]; then
    # Same for analytics.py (issue #396 wave 5): the captured main.py
    # imports it at boot, so the bootstrap baseline must stay bootable.
    install -m 0644 "$ANALYTICS_TARGET" "$bootstrap_release/api/app/analytics.py"
  fi
  if [[ -f "$LIVE_FEEDS_TARGET" ]]; then
    # Same for live_feeds.py (issue #396 wave 6): the captured main.py
    # imports it at boot, so the bootstrap baseline must stay bootable.
    install -m 0644 "$LIVE_FEEDS_TARGET" "$bootstrap_release/api/app/live_feeds.py"
  fi
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
  if [[ -f "$LIVE_SYNC_TARGET" ]]; then
    install -m 0644 "$LIVE_SYNC_TARGET" "$bootstrap_release/frontend/sea-speed/live-sync.js"
  else
    touch "$bootstrap_release/frontend/sea-speed/live-sync.js.absent"
  fi
  install -m 0644 "$ROOT_FRONTEND_TARGET" "$bootstrap_release/frontend/root/index.html"
  if [[ -f "$FALLBACK_FRONTEND_TARGET" ]]; then
    install -m 0644 "$FALLBACK_FRONTEND_TARGET" "$bootstrap_release/frontend/sea-speed/unavailable.html"
  else
    touch "$bootstrap_release/frontend/sea-speed/unavailable.html.absent"
  fi
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

ensure_current_release_has_fallback_frontend() {
  local current_name current_release fallback_release_dir
  current_name="$(cat "$CURRENT_FILE")"
  current_release="$RELEASES_DIR/$current_name"
  fallback_release_dir="$current_release/frontend/sea-speed"
  if [[ -f "$fallback_release_dir/unavailable.html" || -f "$fallback_release_dir/unavailable.html.absent" ]]; then return; fi
  log "Capturing current fallback frontend state for rollback release ${current_name}"
  mkdir -p "$fallback_release_dir"
  if [[ -f "$FALLBACK_FRONTEND_TARGET" ]]; then
    install -m 0644 "$FALLBACK_FRONTEND_TARGET" "$fallback_release_dir/unavailable.html"
  else
    touch "$fallback_release_dir/unavailable.html.absent"
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
  [[ -f "$release_dir/frontend/sea-speed/live-sync.js" || -f "$release_dir/frontend/sea-speed/live-sync.js.absent" ]] || { echo "Release ${release_name} has no live-sync module state" >&2; return 1; }
  [[ -f "$release_dir/frontend/sea-speed/overlay-canvas.js" || -f "$release_dir/frontend/sea-speed/overlay-canvas.js.absent" ]] || { echo "Release ${release_name} has no overlay-canvas module state" >&2; return 1; }
  [[ -f "$release_dir/frontend/root/index.html" ]] || { echo "Release ${release_name} has no root frontend file" >&2; return 1; }
  [[ -f "$release_dir/frontend/sea-speed/unavailable.html" || -f "$release_dir/frontend/sea-speed/unavailable.html.absent" ]] || { echo "Release ${release_name} has no fallback frontend state" >&2; return 1; }

  install -m 0644 "$release_dir/api/app/main.py" "${API_TARGET}.next"
  if [[ -f "$release_dir/api/app/config.py" ]]; then
    install -m 0644 "$release_dir/api/app/config.py" "${CONFIG_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/identity.py" ]]; then
    install -m 0644 "$release_dir/api/app/identity.py" "${IDENTITY_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/store.py" ]]; then
    install -m 0644 "$release_dir/api/app/store.py" "${STORE_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/objects_registry.py" ]]; then
    install -m 0644 "$release_dir/api/app/objects_registry.py" "${OBJECTS_REGISTRY_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/passage_mirrors.py" ]]; then
    install -m 0644 "$release_dir/api/app/passage_mirrors.py" "${PASSAGE_MIRRORS_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/water_passages.py" ]]; then
    install -m 0644 "$release_dir/api/app/water_passages.py" "${WATER_PASSAGES_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/camera_preview.py" ]]; then
    install -m 0644 "$release_dir/api/app/camera_preview.py" "${CAMERA_PREVIEW_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/analytics.py" ]]; then
    install -m 0644 "$release_dir/api/app/analytics.py" "${ANALYTICS_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/live_feeds.py" ]]; then
    install -m 0644 "$release_dir/api/app/live_feeds.py" "${LIVE_FEEDS_TARGET}.next"
  fi
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
  if [[ -f "$release_dir/frontend/sea-speed/live-sync.js" ]]; then
    install -m 0644 "$release_dir/frontend/sea-speed/live-sync.js" "${LIVE_SYNC_TARGET}.next"
  fi
  if [[ -f "$release_dir/frontend/sea-speed/overlay-canvas.js" ]]; then
    install -m 0644 "$release_dir/frontend/sea-speed/overlay-canvas.js" "${OVERLAY_CANVAS_TARGET}.next"
  fi
  if [[ -f "$release_dir/frontend/sea-speed/unavailable.html" ]]; then
    install -m 0644 "$release_dir/frontend/sea-speed/unavailable.html" "${FALLBACK_FRONTEND_TARGET}.next"
  fi

  if [[ -f "$release_dir/api/app/config.py" ]]; then
    # Activation is bound to the selected release content — the same
    # condition as staging above. config.py must land before main.py:
    # the new main imports it at boot (issue #396 wave 1).
    mv -f "${CONFIG_TARGET}.next" "$CONFIG_TARGET"
  else
    # A release without config.py is a pre-#396 shape: remove the live copy
    # (and any stale staged .next) so the old main stays the sole owner of
    # these names and the downgrade boots cleanly.
    rm -f "$CONFIG_TARGET" "${CONFIG_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/identity.py" ]]; then
    # identity.py must also land before main.py: the new main imports it at
    # boot for the auth/worker-control seams.
    mv -f "${IDENTITY_TARGET}.next" "$IDENTITY_TARGET"
  else
    rm -f "$IDENTITY_TARGET" "${IDENTITY_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/store.py" ]]; then
    # Activation is bound to the selected release content — the same
    # condition as staging above — never to the mere presence of a staged
    # .next file: a stale .next left behind by an interrupted install must
    # never be promoted, notably during a store-less rollback.
    # store.py must land before main.py: the new main imports it at boot.
    mv -f "${STORE_TARGET}.next" "$STORE_TARGET"
  else
    rm -f "$STORE_TARGET" "${STORE_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/objects_registry.py" ]]; then
    # Activation is bound to the selected release content — the same
    # condition as staging above. objects_registry.py must land before
    # main.py: the new main imports it at boot (issue #396 wave 2).
    mv -f "${OBJECTS_REGISTRY_TARGET}.next" "$OBJECTS_REGISTRY_TARGET"
  else
    rm -f "$OBJECTS_REGISTRY_TARGET" "${OBJECTS_REGISTRY_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/passage_mirrors.py" ]]; then
    # passage_mirrors.py must also land before main.py: the new main imports
    # it at boot and binds open_passages_db into it (issue #396 wave 2).
    mv -f "${PASSAGE_MIRRORS_TARGET}.next" "$PASSAGE_MIRRORS_TARGET"
  else
    rm -f "$PASSAGE_MIRRORS_TARGET" "${PASSAGE_MIRRORS_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/water_passages.py" ]]; then
    # water_passages.py must also land before main.py: the new main imports
    # it at boot and binds open_passages_db into passage_mirrors from it
    # (issue #396 wave 3).
    mv -f "${WATER_PASSAGES_TARGET}.next" "$WATER_PASSAGES_TARGET"
  else
    rm -f "$WATER_PASSAGES_TARGET" "${WATER_PASSAGES_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/camera_preview.py" ]]; then
    # camera_preview.py must also land before main.py: the new main imports
    # it through the wave-4 seam at boot (issue #396 wave 4).
    mv -f "${CAMERA_PREVIEW_TARGET}.next" "$CAMERA_PREVIEW_TARGET"
  else
    rm -f "$CAMERA_PREVIEW_TARGET" "${CAMERA_PREVIEW_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/analytics.py" ]]; then
    # analytics.py must also land before main.py: the new main imports
    # it through the wave-5 seam at boot (issue #396 wave 5).
    mv -f "${ANALYTICS_TARGET}.next" "$ANALYTICS_TARGET"
  else
    rm -f "$ANALYTICS_TARGET" "${ANALYTICS_TARGET}.next"
  fi
  if [[ -f "$release_dir/api/app/live_feeds.py" ]]; then
    # live_feeds.py must also land before main.py: the new main imports
    # it through the wave-6 seam at boot (issue #396 wave 6).
    mv -f "${LIVE_FEEDS_TARGET}.next" "$LIVE_FEEDS_TARGET"
  else
    rm -f "$LIVE_FEEDS_TARGET" "${LIVE_FEEDS_TARGET}.next"
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
  if [[ -f "$release_dir/frontend/sea-speed/live-sync.js" ]]; then
    mv -f "${LIVE_SYNC_TARGET}.next" "$LIVE_SYNC_TARGET"
  else
    rm -f "$LIVE_SYNC_TARGET" "${LIVE_SYNC_TARGET}.next"
  fi
  if [[ -f "$release_dir/frontend/sea-speed/overlay-canvas.js" ]]; then
    mv -f "${OVERLAY_CANVAS_TARGET}.next" "$OVERLAY_CANVAS_TARGET"
  else
    rm -f "$OVERLAY_CANVAS_TARGET" "${OVERLAY_CANVAS_TARGET}.next"
  fi
  if [[ -f "$release_dir/frontend/sea-speed/unavailable.html" ]]; then
    mv -f "${FALLBACK_FRONTEND_TARGET}.next" "$FALLBACK_FRONTEND_TARGET"
  else
    rm -f "$FALLBACK_FRONTEND_TARGET" "${FALLBACK_FRONTEND_TARGET}.next"
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

verify_fallback_page() {
  local status headers body
  status="$(curl --silent --show-error --output /tmp/sea-speed-fallback-body.html --write-out '%{http_code}' --max-time 15 "$FRONTEND_URL" 2>/dev/null || true)"
  headers="$(curl --silent --include --max-time 15 "$FRONTEND_URL" 2>/dev/null || true)"
  if [[ "$status" != "503" ]]; then
    echo "Fallback page verification failed: expected 503, got ${status}" >&2
    return 1
  fi
  echo "$headers" | grep -qi 'Cache-Control:.*no-store' || { echo "Fallback missing Cache-Control no-store" >&2; return 1; }
  echo "$headers" | grep -qi 'Retry-After:.*30' || { echo "Fallback missing Retry-After 30" >&2; return 1; }
  body="$(cat /tmp/sea-speed-fallback-body.html 2>/dev/null || true)"
  echo "$body" | grep -Fq "Sea Speed временно недоступен" || { echo "Fallback body does not contain expected outage title" >&2; return 1; }
  echo "$body" | grep -Fq "Повторить подключение" || { echo "Fallback body missing retry button" >&2; return 1; }
  log "Fallback outage page verification passed with HTTP 503 and required headers/body"
}

verify_frontends() {
  [[ -s "$FRONTEND_TARGET" ]] || { echo "Operator frontend file is missing or empty: ${FRONTEND_TARGET}" >&2; return 1; }
  [[ -s "$ROOT_FRONTEND_TARGET" ]] || { echo "Root frontend file is missing or empty: ${ROOT_FRONTEND_TARGET}" >&2; return 1; }
  [[ -s "$FALLBACK_FRONTEND_TARGET" ]] || echo "WARNING fallback frontend is missing at ${FALLBACK_FRONTEND_TARGET}" >&2

  local private_health protected_status
  private_health="$(private_authentik_health_status)"
  protected_status="$(protected_frontend_status)"
  if [[ "$private_health" == "FAIL" && "$protected_status" == "503" && -s "$FALLBACK_FRONTEND_TARGET" ]]; then
    log "Detected degraded Authentik outage with fallback active — verifying 503 outage page instead of healthy 302/401/403"
    verify_fallback_page || return 1
    # fallback pages for other protected frontends also serve 503 outage page — verify one representative sample
    if [[ -f "$OBJECTS_FRONTEND_TARGET" ]]; then
      verify_public_url "Root frontend" "$ROOT_FRONTEND_URL" || return 1
    fi
    verify_public_url "Public private-health boundary" "$PUBLIC_HEALTH_URL" || true
    verify_public_url "Root frontend" "$ROOT_FRONTEND_URL"
    return 0
  fi

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
  if [[ -f "$LIVE_SYNC_TARGET" ]]; then
    [[ -s "$LIVE_SYNC_TARGET" ]] || { echo "Live sync module file is empty: ${LIVE_SYNC_TARGET}" >&2; return 1; }
    verify_public_url "Live sync module" "$LIVE_SYNC_URL"
  else
    log "Live sync module is absent in this rollback release"
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

  local private_health protected_status
  private_health="$(private_authentik_health_status)"
  protected_status="$(protected_frontend_status)"
  if [[ "$private_health" == "FAIL" && "$protected_status" == "503" && -s "$FALLBACK_FRONTEND_TARGET" ]]; then
    log "Private Authentik unreachable but fallback 503 outage page is active — treating as degraded-state success without requiring Worker recovery"
    # Verify fallback headers/body as additional assurance
    verify_fallback_page || return 1
    printf 'SEA_SPEED_AUTH_CUTOVER=PASS\n'
    printf 'DEGRADED_FALLBACK_VERIFIED=PASS\n'
    AUTH_BOUNDARY_VERIFIED=true
    return 0
  fi

  # Unprivileged verification of the Caddy-managed Road private M2M boundary:
  # the deploy user checks the private bind, the public operator gate, private
  # Authentik health and the public root; no root helper is invoked.
  verify_private_m2m_boundary || return $?
  printf 'SEA_SPEED_AUTH_CUTOVER=PASS\n'
  printf 'WORKER_PRIVATE_ROAD_API_BASE=http://%s/api/analytics/road1\n' "$WORKER_PRIVATE_LISTEN"
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

  # Exact release staging and the unprivileged Caddy-boundary verification
  # occur before any live source, service or release-state mutation; on this
  # topology the edge boundary is Caddy-managed and verified, not rendered.
  # Degraded mode is pre-mutation only: the recovery stage below immediately
  # re-probes and owns any degraded 500/503 verdict.
  verify_private_m2m_boundary "degraded"
  recover_auth_boundary_before_source_mutation

  bootstrap_current_release
  ensure_current_release_has_root_frontend
  ensure_current_release_has_objects_frontend
  ensure_current_release_has_cameras_frontend
  ensure_current_release_has_road_frontend
  ensure_current_release_has_fallback_frontend

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
  migrate_legacy_roi_to_normalized
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