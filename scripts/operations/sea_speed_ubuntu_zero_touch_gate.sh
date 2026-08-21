#!/usr/bin/env bash
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

readonly GATE_PATH="/usr/local/sbin/sea-speed-ubuntu-zero-touch-gate"
readonly DEPLOY_USER="sea-speed-deploy"
readonly REPOSITORY_URL="https://github.com/MostDef2000/sea-speed.git"
readonly INSTALL_ROOT="/opt/sea-speed-worker"

fail() {
  echo "ERROR $*" >&2
  exit 1
}

validate_request() {
  local target="$1" issue="$2" artifact="$3"
  [[ "$target" =~ ^[0-9a-f]{40}$ ]] || fail "target must be a lowercase 40-character SHA"
  [[ "$issue" =~ ^[1-9][0-9]*$ ]] || fail "issue must be a positive integer"
  [[ "$artifact" =~ ^[0-9a-f]{64}$ ]] || fail "artifact SHA-256 must be lowercase 64 hex"
}

execute_root() {
  [[ "$EUID" -eq 0 ]] || fail "--execute requires root"
  [[ $# -eq 3 ]] || fail "--execute requires target, issue and artifact SHA-256"
  local target="$1" issue="$2" artifact="$3"
  validate_request "$target" "$issue" "$artifact"

  for command_name in git python3 install mktemp rm; do
    command -v "$command_name" >/dev/null 2>&1 || fail "required command missing: $command_name"
  done

  local updater_root="$INSTALL_ROOT/updater"
  install -d -o root -g root -m 0700 "$updater_root"
  local stage
  stage="$(mktemp -d "$updater_root/zero-touch.XXXXXX")"
  cleanup() {
    local status=$?
    rm -rf "$stage" || true
    return "$status"
  }
  trap cleanup EXIT

  git -C "$stage" init -q
  git -C "$stage" remote add origin "$REPOSITORY_URL"
  git -C "$stage" fetch --quiet --no-tags origin main:refs/remotes/origin/main
  git -C "$stage" cat-file -e "$target^{commit}" 2>/dev/null || fail "target is not present in origin/main"
  local first_parent_match=0
  while IFS= read -r commit; do
    [[ "$commit" == "$target" ]] && first_parent_match=1
  done < <(git -C "$stage" rev-list --first-parent refs/remotes/origin/main)
  [[ "$first_parent_match" == "1" ]] || fail "target is not on current main first-parent history"
  git -C "$stage" -c advice.detachedHead=false checkout --quiet --detach "$target"
  [[ "$(git -C "$stage" rev-parse HEAD)" == "$target" ]] || fail "exact target checkout mismatch"

  local deploy_script="$stage/deploy/worker/ubuntu/deploy-authorized.sh"
  local artifact_builder="$stage/scripts/quality/build_exact_artifacts.py"
  local artifact_manifest="$stage/dist/exact/exact-artifacts.json"
  [[ -f "$deploy_script" && -f "$artifact_builder" ]] || fail "target lacks canonical Ubuntu deployment tooling"

  python3 "$artifact_builder" --source-commit "$target" --output-dir "$stage/dist/exact" >/dev/null
  local computed_artifact
  computed_artifact="$(python3 - "$artifact_manifest" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
item = next(value for value in payload["release_artifacts"] if value["component"] == "ubuntu-worker")
print(item["sha256"])
PY
  )"
  [[ "$computed_artifact" == "$artifact" ]] || fail "artifact SHA-256 does not match deterministic exact Ubuntu artifact"

  local transaction_output rc
  set +e
  transaction_output="$(bash "$deploy_script" "$target" --issue "$issue" --artifact-sha256 "$artifact" 2>&1)"
  rc=$?
  set -e
  printf '%s\n' "$transaction_output" >&2
  [[ "$rc" -eq 0 ]] || exit "$rc"

  local manifest="$updater_root/deployment-manifest-ubuntu-worker.json"
  [[ -f "$manifest" ]] || fail "canonical Ubuntu deployment manifest is missing"
  python3 "$stage/scripts/release/validate_deployment_manifest.py" "$manifest" >/dev/null
  python3 - "$manifest" "$target" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
if payload.get("sourceCommit") != sys.argv[2]:
    raise SystemExit("deployment manifest sourceCommit mismatch")
if payload.get("runtimeVerified") is not True or payload.get("state") != "runtime_verified":
    raise SystemExit("deployment manifest is not runtime_verified")
PY
  cat "$manifest"
  cleanup
  trap - EXIT
}

if [[ "${1:-}" == "--execute" ]]; then
  shift
  execute_root "$@"
  exit 0
fi

[[ "$EUID" -ne 0 ]] || fail "forced-command entrypoint must execute as the dedicated deploy user"
[[ "$(id -un)" == "$DEPLOY_USER" ]] || fail "forced-command entrypoint requires $DEPLOY_USER"
readonly original="${SSH_ORIGINAL_COMMAND:-}"
if [[ "$original" =~ ^sea-speed-ubuntu-deploy-v1\ ([0-9a-f]{40})\ ([1-9][0-9]*)\ ([0-9a-f]{64})$ ]]; then
  target="${BASH_REMATCH[1]}"
  issue="${BASH_REMATCH[2]}"
  artifact="${BASH_REMATCH[3]}"
else
  fail "unsupported restricted SSH command"
fi
validate_request "$target" "$issue" "$artifact"
exec sudo -n "$GATE_PATH" --execute "$target" "$issue" "$artifact"
