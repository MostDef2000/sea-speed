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
`Execution-Intent: EXECUTE`, stages the exact current-main source, activates it
through that source's updater, verifies exact worker/control identity, records
deployment evidence, and rolls back to the previously active exact release if
post-activation verification fails.
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
control_service="sea-speed-worker-control.service"

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

[[ "$EUID" -eq 0 ]] || { echo "ERROR run as root" >&2; exit 1; }
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
[[ "$(stat -c '%u' "$token_file")" == "0" && "$(stat -c '%a' "$token_file")" == "600" ]] || {
  echo "ERROR GitHub token must be root-owned mode 600" >&2; exit 5;
}

updater_root="$install_root/updater"
install -d -o root -g root -m 0700 "$updater_root"
exec 8>"$updater_root/deploy-authorized.lock"
chmod 0600 "$updater_root/deploy-authorized.lock"
flock -n 8 || { echo "ERROR another authorized Ubuntu deployment is running" >&2; exit 6; }

stage="$(mktemp -d "$updater_root/deploy-stage.XXXXXX")"
chmod 0700 "$stage"
cleanup() {
  local status=$?
  rm -rf "$stage" || true
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

verify_active_target() {
  [[ "$(cat "$active_marker" 2>/dev/null || true)" == "$target" ]] || return 1
  target_runtime="$(cat "$install_root/releases/$target/runtime-id" 2>/dev/null || true)"
  [[ "$target_runtime" =~ ^[0-9a-f]{64}$ ]] || return 1
  worker_exec="$(systemctl show -p ExecStart --value "$worker_service" 2>/dev/null || true)"
  [[ "$worker_exec" == *"$target"* && "$worker_exec" == *"/runtimes/$target_runtime/venv/bin/python"* ]] || return 1
  [[ -f "/etc/systemd/system/$control_service" ]] || return 1
  grep -Fq "$target" "/etc/systemd/system/$control_service" || return 1
  systemctl is-active --quiet "$control_service" || return 1
  control_exec="$(systemctl show -p ExecStart --value "$control_service" 2>/dev/null || true)"
  [[ "$control_exec" == *"$target"* ]] || return 1
  if [[ "$desired" == "running" ]]; then
    systemctl is-active --quiet "$worker_service" || return 1
  else
    ! systemctl is-active --quiet "$worker_service" || return 1
  fi
  return 0
}

rolled_back=false
if [[ "$previous" != "$target" ]]; then
  echo "DEPLOY_MUTATION target=$target previous=$previous desired_state=$desired"
  if ! bash "$stage/deploy/worker/ubuntu/update-exact.sh" \
      "$target" \
      --install-root "$install_root" \
      --service-user "$service_user" \
      --token-file "$token_file" \
      --activate; then
    echo "ERROR exact updater failed; updater owns pre-commit restoration" >&2
    exit 20
  fi
fi

if ! verify_active_target; then
  echo "ERROR post-activation exact identity verification failed" >&2
  if [[ "$previous" != "$target" && "$(cat "$active_marker" 2>/dev/null || true)" == "$target" ]]; then
    if bash "$stage/deploy/worker/ubuntu/rollback-exact.sh" \
        "$previous" \
        --install-root "$install_root" \
        --service-user "$service_user" \
        --expected-current "$target"; then
      rolled_back=true
      echo "DEPLOY_ROLLED_BACK target=$target restored=$previous" >&2
      exit 30
    fi
    echo "CRITICAL post-activation verification failed and rollback failed" >&2
    exit 31
  fi
  exit 21
fi

runtime_id="$(cat "$install_root/releases/$target/runtime-id")"
manifest="$updater_root/deployment-manifest-ubuntu-worker.json"
TARGET="$target" PREVIOUS="$previous" RUNTIME_ID="$runtime_id" DESIRED="$desired" \
ARTIFACT_SHA256="$artifact_sha256" MANIFEST="$manifest" ROLLED_BACK="$rolled_back" python3 - <<'PY'
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
        {"name": "exact-worker-source-runtime", "status": "passed"},
        {"name": "worker-control-service", "status": "passed"},
        {"name": "operator-desired-state-" + os.environ["DESIRED"], "status": "passed"},
    ],
    "rollbackTarget": os.environ["PREVIOUS"],
    "runtimeVerified": True,
    "state": "runtime_verified",
}
Path(os.environ["MANIFEST"]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
chmod 0600 "$manifest"

printf 'DEPLOYMENT_ACCEPTED target=%s previous=%s runtime_id=%s desired_state=%s\n' \
  "$target" "$previous" "$runtime_id" "$desired"
printf 'DEPLOYMENT_MANIFEST path=%s\n' "$manifest"
