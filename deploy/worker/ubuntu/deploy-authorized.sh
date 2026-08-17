#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: deploy-authorized.sh <40-character-source-commit> --issue N [options]

Options:
  --install-root PATH       Worker installation root (default: /opt/sea-speed-worker)
  --service-user USER       Worker service user (default: sea-speed)
  --token-file PATH         Root-owned GitHub read token (default: /etc/sea-speed/github-read-token)
  --artifact-sha256 SHA256  Optional exact ubuntu-worker artifact digest for evidence

This is the repository-owned Ubuntu production transaction. It requires the
canonical Issue to contain the exact production authorization plus
`Execution-Intent: EXECUTE`, stages the exact current-main source, reconciles
protected water/road profile configuration from protected private runtime
inputs, preserves independent Water/Road operator desired states, activates it
through that source's updater, verifies exact worker/control/road identity,
records deployment evidence, and restores protected configuration plus the
previously active exact release if post-reconciliation activation fails.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then usage; exit 0; fi

target="${1:-}"
[[ -n "$target" ]] || { usage >&2; exit 2; }
shift

issue=""
install_root="/opt/sea-speed-worker"
service_user="sea-speed"
token_file="/etc/sea-speed/github-read-token"
artifact_sha256=""
repository="MostDef2000/sea-speed"
repository_url="https://github.com/MostDef2000/sea-speed.git"
worker_service="sea-speed-worker.service"
road_service="sea-speed-road-worker.service"
control_service="sea-speed-worker-control.service"
test_mode="${SEA_SPEED_DEPLOY_TEST_MODE:-0}"
systemd_unit_root="${SEA_SPEED_SYSTEMD_UNIT_ROOT:-/etc/systemd/system}"
preview_catalog="/var/lib/sea-speed-camera-preview/active/camera-preview-catalog.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --issue) [[ $# -ge 2 ]] || exit 2; issue="$2"; shift 2 ;;
    --install-root) [[ $# -ge 2 ]] || exit 2; install_root="$2"; shift 2 ;;
    --service-user) [[ $# -ge 2 ]] || exit 2; service_user="$2"; shift 2 ;;
    --token-file) [[ $# -ge 2 ]] || exit 2; token_file="$2"; shift 2 ;;
    --artifact-sha256) [[ $# -ge 2 ]] || exit 2; artifact_sha256="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$test_mode" == "1" ]]; then
  [[ "$install_root" != "/opt/sea-speed-worker" && "$systemd_unit_root" != "/etc/systemd/system" ]] || {
    echo "ERROR test mode requires sandbox install and systemd roots" >&2; exit 1;
  }
else
  [[ "$EUID" -eq 0 ]] || { echo "ERROR run as root" >&2; exit 1; }
  [[ "$systemd_unit_root" == "/etc/systemd/system" ]] || { echo "ERROR production systemd unit root is fixed" >&2; exit 1; }
fi
[[ "$target" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR target must be a lowercase 40-character SHA" >&2; exit 2; }
[[ "$issue" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR --issue must be a positive integer" >&2; exit 2; }
[[ "$service_user" =~ ^[a-z_][a-z0-9_-]*$ ]] || { echo "ERROR invalid service user" >&2; exit 2; }
if [[ -n "$artifact_sha256" && ! "$artifact_sha256" =~ ^[0-9a-f]{64}$ ]]; then
  echo "ERROR artifact SHA-256 must be lowercase 64 hex" >&2
  exit 2
fi
for command_name in git python3 systemctl stat install mktemp flock grep; do
  command -v "$command_name" >/dev/null 2>&1 || { echo "ERROR required command missing: $command_name" >&2; exit 4; }
done
[[ -f "$token_file" ]] || { echo "ERROR protected GitHub token missing: $token_file" >&2; exit 5; }
[[ "$(stat -c '%a' "$token_file")" == "600" ]] || { echo "ERROR GitHub token mode must be 600" >&2; exit 5; }
if [[ "$test_mode" != "1" && "$(stat -c '%u' "$token_file")" != "0" ]]; then
  echo "ERROR GitHub token must be owned by root" >&2
  exit 5
fi

updater_root="$install_root/updater"
if [[ "$test_mode" == "1" ]]; then
  install -d -m 0700 "$updater_root"
else
  install -d -o root -g root -m 0700 "$updater_root"
fi
exec 8>"$updater_root/deploy-authorized.lock"
chmod 0600 "$updater_root/deploy-authorized.lock"
flock -n 8 || { echo "ERROR another authorized Ubuntu deployment is running" >&2; exit 6; }

stage="$(mktemp -d "$updater_root/deploy-stage.XXXXXX")"
chmod 0700 "$stage"
worker_env_backup=""
road_env_backup=""
cleanup() {
  local status=$?
  rm -rf "$stage" || true
  [[ -z "$worker_env_backup" ]] || rm -f "$worker_env_backup" || true
  [[ -z "$road_env_backup" ]] || rm -f "$road_env_backup" || true
  return "$status"
}
trap cleanup EXIT

git -C "$stage" init -q
git -C "$stage" remote add origin "$repository_url"
git -C "$stage" fetch --quiet --no-tags origin main:refs/remotes/origin/main
git -C "$stage" cat-file -e "$target^{commit}" 2>/dev/null || {
  echo "ERROR target is not present in origin/main" >&2; exit 7;
}
first_parent_match=0
while IFS= read -r commit; do
  [[ "$commit" == "$target" ]] && first_parent_match=1
done < <(git -C "$stage" rev-list --first-parent refs/remotes/origin/main)
[[ "$first_parent_match" == "1" ]] || { echo "ERROR target is not on current main first-parent history" >&2; exit 7; }
git -C "$stage" -c advice.detachedHead=false checkout --quiet --detach "$target"
[[ "$(git -C "$stage" rev-parse HEAD)" == "$target" ]] || { echo "ERROR staged target mismatch" >&2; exit 7; }

for required in \
  scripts/release/verify_production_authorization.py \
  deploy/worker/ubuntu/configure-analytics-profiles.py \
  deploy/worker/ubuntu/update-exact.sh \
  deploy/worker/ubuntu/rollback-exact.sh; do
  [[ -f "$stage/$required" ]] || { echo "ERROR target lacks required deployment component: $required" >&2; exit 8; }
done

IFS= read -r github_token < "$token_file" || true
[[ -n "${github_token:-}" ]] || { echo "ERROR GitHub token file is empty" >&2; exit 5; }
auth_evidence="$updater_root/production-authorization-$target.json"
GITHUB_TOKEN="$github_token" python3 "$stage/scripts/release/verify_production_authorization.py" \
  --repository "$repository" \
  --commit "$target" \
  --issue "$issue" \
  --require-execution-intent \
  --evidence-output "$auth_evidence"
unset github_token
chmod 0600 "$auth_evidence"

active_marker="$install_root/shared/runtime/active-source-commit"
previous="$(cat "$active_marker" 2>/dev/null || true)"
[[ "$previous" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR active source marker is missing or invalid" >&2; exit 9; }

desired_file="$install_root/shared/runtime/operator-desired-state"
desired="$(cat "$desired_file" 2>/dev/null || echo running)"
[[ "$desired" == "running" || "$desired" == "stopped" ]] || { echo "ERROR operator desired state is invalid" >&2; exit 9; }
road_desired_file="$install_root/shared/road-runtime/operator-desired-state"
road_desired="$(cat "$road_desired_file" 2>/dev/null || echo running)"
[[ "$road_desired" == "running" || "$road_desired" == "stopped" ]] || { echo "ERROR road operator desired state is invalid" >&2; exit 9; }
control_unit="$systemd_unit_root/$control_service"
road_unit="$systemd_unit_root/$road_service"
worker_env="$install_root/shared/config/worker.env"
road_env="$install_root/shared/config/road-worker.env"

worker_was_active=false
road_was_active=false
if systemctl is-active --quiet "$worker_service"; then worker_was_active=true; fi
if systemctl is-active --quiet "$road_service"; then road_was_active=true; fi
if [[ "$desired" == "running" && "$worker_was_active" != true ]]; then
  echo "ERROR desired running worker is not active before protected configuration reconciliation" >&2
  exit 9
fi
if [[ "$desired" == "stopped" && "$worker_was_active" == true ]]; then
  echo "ERROR desired stopped worker is active before protected configuration reconciliation" >&2
  exit 9
fi
if [[ -f "$road_env" && "$road_desired" == "running" && "$road_was_active" != true ]]; then
  echo "ERROR desired running road worker is not active before protected configuration reconciliation" >&2
  exit 9
fi
if [[ -f "$road_env" && "$road_desired" == "stopped" && "$road_was_active" == true ]]; then
  echo "ERROR desired stopped road worker is active before protected configuration reconciliation" >&2
  exit 9
fi

worker_env_uid=""
worker_env_gid=""
road_env_uid=""
road_env_gid=""
road_env_existed=false
protected_config_reconciled=false

secure_backup() {
  local source_path="$1"
  local backup_path="$2"
  if [[ "$test_mode" == "1" ]]; then
    install -m 0600 "$source_path" "$backup_path"
  else
    install -o root -g root -m 0600 "$source_path" "$backup_path"
  fi
}

restore_file_owner_mode() {
  local backup_path="$1"
  local target_path="$2"
  local uid="$3"
  local gid="$4"
  install -o "$uid" -g "$gid" -m 0600 "$backup_path" "$target_path"
}

backup_protected_config() {
  [[ -f "$worker_env" && ! -L "$worker_env" ]] || { echo "ERROR protected worker.env is missing or invalid" >&2; return 1; }
  [[ "$(stat -c '%a' "$worker_env")" == "600" ]] || { echo "ERROR worker.env must be mode 600" >&2; return 1; }
  worker_env_uid="$(stat -c '%u' "$worker_env")"
  worker_env_gid="$(stat -c '%g' "$worker_env")"
  worker_env_backup="$(mktemp "$updater_root/worker-env-backup.XXXXXX")"
  secure_backup "$worker_env" "$worker_env_backup" || return 1

  if [[ -e "$road_env" ]]; then
    [[ -f "$road_env" && ! -L "$road_env" ]] || { echo "ERROR protected road-worker.env is invalid" >&2; return 1; }
    [[ "$(stat -c '%a' "$road_env")" == "600" ]] || { echo "ERROR road-worker.env must be mode 600" >&2; return 1; }
    road_env_existed=true
    road_env_uid="$(stat -c '%u' "$road_env")"
    road_env_gid="$(stat -c '%g' "$road_env")"
    road_env_backup="$(mktemp "$updater_root/road-env-backup.XXXXXX")"
    secure_backup "$road_env" "$road_env_backup" || return 1
  fi
  echo "PROTECTED_CONFIG_BACKUP=PASS"
}

restore_protected_config() {
  [[ -n "$worker_env_backup" && -f "$worker_env_backup" ]] || return 1
  restore_file_owner_mode "$worker_env_backup" "$worker_env" "$worker_env_uid" "$worker_env_gid" || return 1
  if [[ "$road_env_existed" == true ]]; then
    [[ -n "$road_env_backup" && -f "$road_env_backup" ]] || return 1
    restore_file_owner_mode "$road_env_backup" "$road_env" "$road_env_uid" "$road_env_gid" || return 1
  else
    rm -f "$road_env" || return 1
  fi
  echo "PROTECTED_CONFIG_RESTORED=YES"
  return 0
}

restore_predeployment_service_state() {
  if [[ "$road_was_active" == true ]]; then
    systemctl restart "$road_service" || return 1
    systemctl is-active --quiet "$road_service" || return 1
  else
    systemctl stop "$road_service" >/dev/null 2>&1 || true
    ! systemctl is-active --quiet "$road_service" || return 1
  fi
  if [[ "$worker_was_active" == true ]]; then
    systemctl restart "$worker_service" || return 1
    systemctl is-active --quiet "$worker_service" || return 1
  else
    systemctl stop "$worker_service" >/dev/null 2>&1 || true
    ! systemctl is-active --quiet "$worker_service" || return 1
  fi
  echo "PREDEPLOYMENT_SERVICE_STATE_RESTORED=YES"
  return 0
}

if ! backup_protected_config; then
  echo "ERROR protected configuration backup failed" >&2
  exit 10
fi

if ! python3 "$stage/deploy/worker/ubuntu/configure-analytics-profiles.py" \
    --install-root "$install_root" \
    --preview-catalog "$preview_catalog"; then
  echo "ERROR protected analytics profile reconciliation failed" >&2
  if restore_protected_config; then
    echo "DEPLOY_CONFIG_ROLLED_BACK reason=configure_failed" >&2
    exit 11
  fi
  echo "CRITICAL protected analytics profile reconciliation failed and config restore failed" >&2
  exit 12
fi
protected_config_reconciled=true
[[ -f "$road_env" && ! -L "$road_env" && "$(stat -c '%a' "$road_env")" == "600" ]] || {
  echo "ERROR reconciled road-worker.env is missing or invalid" >&2
  if restore_protected_config; then
    echo "DEPLOY_CONFIG_ROLLED_BACK reason=reconciled_config_invalid" >&2
    exit 13
  fi
  echo "CRITICAL reconciled road-worker.env invalid and config restore failed" >&2
  exit 14
}
echo "PROTECTED_CONFIG_RECONCILED=YES"

verify_active_target() {
  [[ "$(cat "$active_marker" 2>/dev/null || true)" == "$target" ]] || return 1
  target_runtime="$(cat "$install_root/releases/$target/runtime-id" 2>/dev/null || true)"
  [[ "$target_runtime" =~ ^[0-9a-f]{64}$ ]] || return 1
  worker_exec="$(systemctl show -p ExecStart --value "$worker_service" 2>/dev/null || true)"
  [[ "$worker_exec" == *"$target"* && "$worker_exec" == *"/runtimes/$target_runtime/venv/bin/python"* ]] || return 1
  [[ -f "$control_unit" ]] || return 1
  grep -Fq "$target" "$control_unit" || return 1
  systemctl is-active --quiet "$control_service" || return 1
  control_exec="$(systemctl show -p ExecStart --value "$control_service" 2>/dev/null || true)"
  [[ "$control_exec" == *"$target"* ]] || return 1
  [[ -f "$road_env" && "$(stat -c '%a' "$road_env")" == "600" ]] || return 1
  [[ -f "$road_unit" ]] || return 1
  grep -Fq "$target" "$road_unit" || return 1
  road_exec="$(systemctl show -p ExecStart --value "$road_service" 2>/dev/null || true)"
  [[ "$road_exec" == *"$target"* && "$road_exec" == *"/runtimes/$target_runtime/venv/bin/python"* ]] || return 1
  if [[ "$road_desired" == "running" ]]; then
    systemctl is-active --quiet "$road_service" || return 1
  else
    ! systemctl is-active --quiet "$road_service" || return 1
  fi
  if [[ "$desired" == "running" ]]; then
    systemctl is-active --quiet "$worker_service" || return 1
  else
    ! systemctl is-active --quiet "$worker_service" || return 1
  fi
  return 0
}

rolled_back=false
echo "DEPLOY_MUTATION target=$target previous=$previous desired_state=$desired road_desired_state=$road_desired protected_config_reconciled=$protected_config_reconciled"
if ! SEA_SPEED_SYSTEMD_UNIT_ROOT="$systemd_unit_root" SEA_SPEED_DEPLOY_TEST_MODE="$test_mode" \
    bash "$stage/deploy/worker/ubuntu/update-exact.sh" \
    "$target" \
    --install-root "$install_root" \
    --service-user "$service_user" \
    --token-file "$token_file" \
    --activate; then
  echo "ERROR exact updater failed; restoring protected configuration after updater-owned runtime restoration" >&2
  if restore_protected_config && restore_predeployment_service_state; then
    echo "DEPLOY_CONFIG_ROLLED_BACK reason=updater_failed" >&2
    exit 20
  fi
  echo "CRITICAL exact updater failed and protected predeployment state could not be restored" >&2
  exit 22
fi

if ! verify_active_target; then
  echo "ERROR post-activation exact identity verification failed" >&2
  if ! restore_protected_config; then
    echo "CRITICAL post-activation verification failed and protected config restore failed" >&2
    exit 31
  fi
  if [[ "$previous" != "$target" && "$(cat "$active_marker" 2>/dev/null || true)" == "$target" ]]; then
    if SEA_SPEED_SYSTEMD_UNIT_ROOT="$systemd_unit_root" SEA_SPEED_DEPLOY_TEST_MODE="$test_mode" \
        bash "$stage/deploy/worker/ubuntu/rollback-exact.sh" \
        "$previous" \
        --install-root "$install_root" \
        --service-user "$service_user" \
        --expected-current "$target"; then
      rolled_back=true
      echo "DEPLOY_ROLLED_BACK target=$target restored=$previous config_restored=true" >&2
      exit 30
    fi
    echo "CRITICAL post-activation verification failed and rollback failed" >&2
    exit 31
  fi
  if restore_predeployment_service_state; then
    echo "DEPLOY_CONFIG_ROLLED_BACK reason=post_activation_verification_failed" >&2
    exit 21
  fi
  echo "CRITICAL post-activation verification failed and predeployment service state restore failed" >&2
  exit 31
fi

runtime_id="$(cat "$install_root/releases/$target/runtime-id")"
manifest="$updater_root/deployment-manifest-ubuntu-worker.json"
road_configured=true
TARGET="$target" PREVIOUS="$previous" RUNTIME_ID="$runtime_id" DESIRED="$desired" ROAD_DESIRED="$road_desired" ROAD_CONFIGURED="$road_configured" \
PROTECTED_CONFIG_RECONCILED="$protected_config_reconciled" ARTIFACT_SHA256="$artifact_sha256" MANIFEST="$manifest" ROLLED_BACK="$rolled_back" python3 - <<'PY'
import json, os
from datetime import datetime, timezone
from pathlib import Path
artifact = os.environ["ARTIFACT_SHA256"] or None
payload = {
    "schema": "sea_speed_deployment_manifest_v1",
    "deliveryId": "ubuntu-" + os.environ["TARGET"][:12] + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    "target": "ubuntu-worker",
    "sourceCommit": os.environ["TARGET"],
    "previousVersion": os.environ["PREVIOUS"],
    "artifactSha256": artifact,
    "installedAt": datetime.now(timezone.utc).isoformat(),
    "checks": [
        {"name": "production-authorization-execution-intent", "status": "passed"},
        {"name": "current-main-first-parent", "status": "passed"},
        {"name": "protected-road-profile-config-reconciled", "status": "passed" if os.environ["PROTECTED_CONFIG_RECONCILED"] == "true" else "failed"},
        {"name": "exact-worker-source-runtime", "status": "passed"},
        {"name": "worker-control-service", "status": "passed"},
        {"name": "road-worker-desired-state-" + os.environ["ROAD_DESIRED"], "status": "passed"},
        {"name": "operator-desired-state-" + os.environ["DESIRED"], "status": "passed"},
    ],
    "rollbackTarget": os.environ["PREVIOUS"],
    "runtimeVerified": True,
    "state": "runtime_verified",
}
Path(os.environ["MANIFEST"]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
chmod 0600 "$manifest"

printf 'DEPLOYMENT_ACCEPTED target=%s previous=%s runtime_id=%s desired_state=%s road_desired_state=%s road_configured=%s protected_config_reconciled=%s\n' \
  "$target" "$previous" "$runtime_id" "$desired" "$road_desired" "$road_configured" "$protected_config_reconciled"
printf 'DEPLOYMENT_MANIFEST path=%s\n' "$manifest"
