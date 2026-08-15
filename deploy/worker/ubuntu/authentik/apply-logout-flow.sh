#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage:
  apply-logout-flow.sh apply --source-sha SHA [--runtime-root PATH]
  apply-logout-flow.sh rollback --source-sha SHA [--runtime-root PATH]

Purpose:
  Apply or roll back the Sea Speed-specific Authentik provider invalidation
  flow on the existing Ubuntu-worker Authentik runtime without changing the
  Docker topology or reading runtime secrets.

Production authorization:
  This helper does not grant production permission. Mutating modes may run
  only inside a separately approved exact-SHA PRODUCTION APPROVED envelope.
USAGE
}

mode="${1:-}"
case "$mode" in
  apply|rollback) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "ERROR unknown command: $mode" >&2; usage >&2; exit 2 ;;
esac

source_sha=""
runtime_root="${SEA_SPEED_AUTH_RUNTIME_ROOT:-/opt/sea-speed-auth}"
expected_hostname="${SEA_SPEED_AUTH_EXPECTED_HOSTNAME:-sea-speed-worker}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-sha)
      [[ $# -ge 2 ]] || { echo "ERROR --source-sha requires SHA" >&2; exit 2; }
      source_sha="$2"; shift 2 ;;
    --runtime-root)
      [[ $# -ge 2 ]] || { echo "ERROR --runtime-root requires PATH" >&2; exit 2; }
      runtime_root="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; exit 2 ;;
  esac
done

fail() {
  printf 'AUTHENTIK_LOGOUT_OPERATION=FAIL\n' >&2
  printf 'AUTHENTIK_LOGOUT_FAIL=%s\n' "$1" >&2
  exit "${2:-1}"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "MISSING_${1}" 40
}

[[ "$EUID" -eq 0 ]] || fail "ROOT_REQUIRED" 41
[[ "$source_sha" =~ ^[0-9a-fA-F]{40}$ ]] || fail "SOURCE_SHA_INVALID" 42

for command_name in docker curl hostname sha256sum sed tail awk basename dirname; do
  require_command "$command_name"
done

docker compose version >/dev/null 2>&1 || fail "DOCKER_COMPOSE_MISSING" 43
[[ "$(hostname)" == "$expected_hostname" ]] || fail "HOSTNAME_MISMATCH" 44

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/../../../.." && pwd)"
apply_source="$repo_root/deploy/vps/authentik/blueprints/sea-speed-logout-v1.yaml"
rollback_source="$repo_root/deploy/vps/authentik/blueprints/sea-speed-logout-rollback-v1.yaml"
compose_file="$runtime_root/compose.yml"
env_file="$runtime_root/.env"
container_blueprint="/blueprints/.sea-speed-logout-operation"

[[ -f "$apply_source" ]] || fail "APPLY_BLUEPRINT_SOURCE_MISSING" 45
[[ -f "$rollback_source" ]] || fail "ROLLBACK_BLUEPRINT_SOURCE_MISSING" 45
[[ -f "$compose_file" ]] || fail "RUNTIME_COMPOSE_MISSING" 46
[[ -f "$env_file" ]] || fail "RUNTIME_ENV_MISSING" 46

cd "$runtime_root"
docker compose config --quiet >/dev/null || fail "RUNTIME_COMPOSE_INVALID" 47

server_id="$(docker compose ps -q server)"
worker_id="$(docker compose ps -q worker)"
postgres_id="$(docker compose ps -q postgresql)"
[[ -n "$server_id" ]] || fail "SERVER_CONTAINER_MISSING" 48
[[ -n "$worker_id" ]] || fail "WORKER_CONTAINER_MISSING" 48
[[ -n "$postgres_id" ]] || fail "POSTGRES_CONTAINER_MISSING" 48

for container_id in "$server_id" "$worker_id" "$postgres_id"; do
  [[ "$(docker inspect --format '{{.State.Running}}' "$container_id" 2>/dev/null || true)" == "true" ]] \
    || fail "CONTAINER_NOT_RUNNING" 49
done

docker exec "$worker_id" test -f /blueprints/sea-speed-auth-v1.yaml \
  || fail "WORKER_BLUEPRINT_ROOT_UNEXPECTED" 50

curl --fail --silent --show-error --max-time 5 \
  http://127.0.0.1:9000/-/health/ready/ >/dev/null \
  || fail "AUTHENTIK_LOOPBACK_HEALTH" 51

query_provider_flow() {
  local output flow
  output="$(docker exec "$worker_id" ak shell -c '
from authentik.providers.proxy.models import ProxyProvider
provider = ProxyProvider.objects.get(name="Provider for Sea Speed")
flow = provider.invalidation_flow
print("SEA_SPEED_PROVIDER_FLOW=" + (flow.slug if flow else ""))
')" || fail "PROVIDER_QUERY" 52
  flow="$(printf '%s\n' "$output" | sed -n 's/^SEA_SPEED_PROVIDER_FLOW=//p' | tail -n 1)"
  [[ -n "$flow" ]] || fail "PROVIDER_FLOW_EMPTY" 53
  printf '%s' "$flow"
}

cleanup_container_blueprint() {
  docker exec "$worker_id" rm -f "$container_blueprint" >/dev/null 2>&1 || true
}

copy_and_apply_blueprint() {
  local source_path="$1"
  cleanup_container_blueprint
  docker cp "$source_path" "${worker_id}:${container_blueprint}" >/dev/null \
    || return 1
  if ! docker exec "$worker_id" ak apply_blueprint "$container_blueprint"; then
    cleanup_container_blueprint
    return 1
  fi
  cleanup_container_blueprint
}

trap cleanup_container_blueprint EXIT

apply_target="sea-speed-provider-invalidation"
rollback_target="default-provider-invalidation-flow"
current_flow="$(query_provider_flow)"

case "$mode:$current_flow" in
  apply:"$rollback_target"|apply:"$apply_target"|rollback:"$apply_target"|rollback:"$rollback_target") ;;
  *) fail "UNEXPECTED_CURRENT_FLOW_${current_flow}" 54 ;;
esac

if [[ "$mode" == "apply" ]]; then
  selected_source="$apply_source"
  target_flow="$apply_target"
  already_state="ALREADY_APPLIED"
else
  selected_source="$rollback_source"
  target_flow="$rollback_target"
  already_state="ALREADY_ROLLED_BACK"
fi

printf 'SOURCE_REPOSITORY=MostDef2000/sea-speed\n'
printf 'SOURCE_COMMIT=%s\n' "$source_sha"
printf 'WORKER_HOST=%s\n' "$(hostname)"
printf 'AUTHENTIK_PROVIDER_INVALIDATION_FLOW_BEFORE=%s\n' "$current_flow"
printf 'AUTHENTIK_BLUEPRINT_SHA256=%s\n' "$(sha256sum "$selected_source" | awk '{print $1}')"

if [[ "$current_flow" == "$target_flow" ]]; then
  printf 'AUTHENTIK_PROVIDER_INVALIDATION_FLOW_AFTER=%s\n' "$current_flow"
  printf 'AUTHENTIK_LOGOUT_OPERATION=%s\n' "$already_state"
  exit 0
fi

if ! copy_and_apply_blueprint "$selected_source"; then
  fail "APPLY_BLUEPRINT_COMMAND" 55
fi

after_flow="$(query_provider_flow)"
if [[ "$after_flow" != "$target_flow" ]]; then
  if [[ "$mode" == "apply" && "$current_flow" == "$rollback_target" ]]; then
    if copy_and_apply_blueprint "$rollback_source"; then
      restored_flow="$(query_provider_flow)"
      if [[ "$restored_flow" == "$rollback_target" ]]; then
        printf 'AUTHENTIK_LOGOUT_AUTO_ROLLBACK=PASS\n' >&2
        fail "PROVIDER_VERIFY_ROLLED_BACK" 56
      fi
    fi
    printf 'AUTHENTIK_LOGOUT_AUTO_ROLLBACK=FAILED\n' >&2
  fi
  fail "PROVIDER_VERIFY_${after_flow}" 56
fi

server_after="$(docker compose ps -q server)"
worker_after="$(docker compose ps -q worker)"
postgres_after="$(docker compose ps -q postgresql)"
[[ "$server_after" == "$server_id" ]] || fail "SERVER_CONTAINER_DRIFT" 57
[[ "$worker_after" == "$worker_id" ]] || fail "WORKER_CONTAINER_DRIFT" 57
[[ "$postgres_after" == "$postgres_id" ]] || fail "POSTGRES_CONTAINER_DRIFT" 57

curl --fail --silent --show-error --max-time 5 \
  http://127.0.0.1:9000/-/health/ready/ >/dev/null \
  || fail "AUTHENTIK_LOOPBACK_HEALTH_AFTER" 58

printf 'AUTHENTIK_PROVIDER_INVALIDATION_FLOW_AFTER=%s\n' "$after_flow"
printf 'AUTHENTIK_RUNTIME_CONTAINERS_UNCHANGED=YES\n'
printf 'AUTHENTIK_LOOPBACK_READY=YES\n'
printf 'AUTHENTIK_LOGOUT_OPERATION=PASS\n'
