#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: reconcile-blueprint.sh --source PATH [--runtime-root PATH]

Apply the exact Sea Speed Authentik blueprint to the already-running Ubuntu
Authentik runtime without pulling images, restarting PostgreSQL, or mutating
Sea Speed Water/Road services. The Authentik worker watches the mounted
blueprint file and applies modifications automatically. Runtime acceptance is
proved by querying the two managed User Login stages from the worker container.
USAGE
}

source_blueprint=""
runtime_root="/opt/sea-speed-auth"
test_mode="${SEA_SPEED_AUTHENTIK_RECONCILE_TEST_MODE:-0}"
attempts="${SEA_SPEED_AUTHENTIK_RECONCILE_ATTEMPTS:-30}"
sleep_seconds="${SEA_SPEED_AUTHENTIK_RECONCILE_SLEEP_SECONDS:-2}"
runtime_blueprint_mode="0644"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) [[ $# -ge 2 ]] || { echo "ERROR --source requires a path" >&2; exit 2; }; source_blueprint="$2"; shift 2 ;;
    --runtime-root) [[ $# -ge 2 ]] || { echo "ERROR --runtime-root requires a path" >&2; exit 2; }; runtime_root="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$source_blueprint" ]] || { usage >&2; exit 2; }
[[ "$attempts" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR invalid reconcile attempts" >&2; exit 2; }
[[ "$sleep_seconds" =~ ^[0-9]+([.][0-9]+)?$ ]] || { echo "ERROR invalid reconcile sleep" >&2; exit 2; }
if [[ "$test_mode" == "1" ]]; then
  [[ "$runtime_root" != "/opt/sea-speed-auth" ]] || { echo "ERROR test mode requires sandbox runtime root" >&2; exit 2; }
else
  [[ "$EUID" -eq 0 ]] || { echo "ERROR run as root" >&2; exit 1; }
  [[ "$runtime_root" == "/opt/sea-speed-auth" ]] || { echo "ERROR production runtime root is fixed" >&2; exit 1; }
fi
for command_name in python3 sha256sum awk cp chmod mktemp docker grep sort sleep seq cat rm stat; do
  command -v "$command_name" >/dev/null 2>&1 || { echo "ERROR required command missing: $command_name" >&2; exit 4; }
done
[[ -f "$source_blueprint" && ! -L "$source_blueprint" ]] || { echo "ERROR source blueprint missing or invalid" >&2; exit 5; }
[[ -f "$runtime_root/compose.yml" && ! -L "$runtime_root/compose.yml" ]] || { echo "ERROR Authentik runtime compose missing or invalid" >&2; exit 5; }
runtime_blueprint="$runtime_root/blueprints/sea-speed-auth-v1.yaml"
[[ -f "$runtime_blueprint" && ! -L "$runtime_blueprint" ]] || { echo "ERROR active Authentik blueprint missing or invalid" >&2; exit 5; }

python3 - "$source_blueprint" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
required = {
    "session_duration: days=30": 2,
    "remember_me_offset: seconds=0": 2,
    "remember_device: seconds=0": 2,
}
for marker, count in required.items():
    actual = text.count(marker)
    if actual != count:
        raise SystemExit(f"ERROR blueprint marker {marker!r} expected {count}, found {actual}")
if "session_duration: hours=12" in text:
    raise SystemExit("ERROR legacy 12-hour session duration remains")
for marker in (
    "name: sea-speed-authentication-login",
    "name: sea-speed-enrollment-login",
    "name: sea-speed-owner-totp",
    "not_configured_action: deny",
    "name: Sea Speed Owner",
    "length_min: 15",
):
    if marker not in text:
        raise SystemExit(f"ERROR protected Authentik marker missing: {marker}")
PY

query_runtime() {
  local output
  output="$(
    cd "$runtime_root"
    docker compose exec -T worker ak shell -c '
from authentik.stages.user_login.models import UserLoginStage
for name in ("sea-speed-authentication-login", "sea-speed-enrollment-login"):
    stage = UserLoginStage.objects.get(name=name)
    print("SEA_SPEED_SESSION_STAGE=%s|%s|%s|%s" % (name, stage.session_duration, stage.remember_me_offset, stage.remember_device))
' 2>&1
  )" || return 1
  printf '%s\n' "$output" | grep '^SEA_SPEED_SESSION_STAGE=' | sort
}

expected_runtime=$'SEA_SPEED_SESSION_STAGE=sea-speed-authentication-login|days=30|seconds=0|seconds=0\nSEA_SPEED_SESSION_STAGE=sea-speed-enrollment-login|days=30|seconds=0|seconds=0'

runtime_matches_expected() {
  local current
  current="$(query_runtime)" || return 1
  [[ "$current" == "$expected_runtime" ]]
}

before_runtime="$(query_runtime)" || { echo "ERROR cannot read current Authentik login-stage state" >&2; exit 6; }
source_sha="$(sha256sum "$source_blueprint" | awk '{print $1}')"
target_sha="$(sha256sum "$runtime_blueprint" | awk '{print $1}')"
target_mode="$(stat -c '%a' "$runtime_blueprint")"

if [[ "$source_sha" == "$target_sha" && "$target_mode" == "644" ]] && runtime_matches_expected; then
  printf 'AUTHENTIK_BLUEPRINT_RECONCILE=PASS\n'
  printf 'AUTHENTIK_SESSION_DURATION=days=30\n'
  printf 'AUTHENTIK_LOGIN_STAGES_VERIFIED=2\n'
  printf 'AUTHENTIK_BLUEPRINT_CHANGED=NO\n'
  printf 'AUTHENTIK_BLUEPRINT_MODE=0644\n'
  printf 'AUTHENTIK_WORKER_RESTARTED=NO\n'
  printf 'WATER_ROAD_SERVICES_MUTATED=NO\n'
  exit 0
fi

backup="$(mktemp "$runtime_root/blueprints/sea-speed-auth-v1.yaml.backup.XXXXXX")"
cleanup() { rm -f "$backup" || true; }
trap cleanup EXIT
cp -p "$runtime_blueprint" "$backup"
chmod 0600 "$backup"

# The blueprint is public repository configuration, not a secret. Keep the
# bind-mounted runtime file container-readable. Issue #231's first production
# attempt forced mode 0600 and Authentik discovery failed with EACCES across the
# Docker user-namespace boundary. The private temporary backup remains mode 0600.
cat "$source_blueprint" > "$runtime_blueprint"
chmod "$runtime_blueprint_mode" "$runtime_blueprint"

verified=false
for _ in $(seq 1 "$attempts"); do
  if runtime_matches_expected; then
    verified=true
    break
  fi
  sleep "$sleep_seconds"
done

if [[ "$verified" != true ]]; then
  echo "ERROR Authentik did not apply the exact 30-day login-stage blueprint; restoring previous blueprint" >&2
  cat "$backup" > "$runtime_blueprint"
  # Restore old bytes but keep the mounted blueprint readable by Authentik so
  # discovery and any future repository-owned reconciliation remain functional.
  chmod "$runtime_blueprint_mode" "$runtime_blueprint"
  rollback_verified=false
  for _ in $(seq 1 "$attempts"); do
    current="$(query_runtime || true)"
    if [[ -n "$before_runtime" && "$current" == "$before_runtime" ]]; then
      rollback_verified=true
      break
    fi
    sleep "$sleep_seconds"
  done
  if [[ "$rollback_verified" == true ]]; then
    echo "AUTHENTIK_BLUEPRINT_ROLLBACK=PASS" >&2
    echo "AUTHENTIK_BLUEPRINT_MODE=0644" >&2
    exit 20
  fi
  echo "CRITICAL Authentik blueprint reconciliation failed and runtime rollback could not be verified" >&2
  exit 21
fi

printf 'AUTHENTIK_BLUEPRINT_RECONCILE=PASS\n'
printf 'AUTHENTIK_SESSION_DURATION=days=30\n'
printf 'AUTHENTIK_LOGIN_STAGES_VERIFIED=2\n'
printf 'AUTHENTIK_BLUEPRINT_CHANGED=YES\n'
printf 'AUTHENTIK_BLUEPRINT_MODE=0644\n'
printf 'AUTHENTIK_WORKER_RESTARTED=NO\n'
printf 'WATER_ROAD_SERVICES_MUTATED=NO\n'