#!/usr/bin/env bash
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
export PATH LC_ALL
umask 077

EXPECTED_CORE_SHA256="9783b12136e7d1dbc9fbeb27155a3faea13f573e6c61252bac3ac73b568c69fb"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CORE="$SCRIPT_DIR/mediamtx-compatibility-remediation.sh"
RUNTIME_ROOT="/run/sea-speed-mediamtx-systemd-v247"
PATCHED="$RUNTIME_ROOT/mediamtx-compatibility-remediation.sh"
LOCK="$RUNTIME_ROOT/runner.lock"

usage() {
  cat <<'USAGE'
Usage:
  mediamtx-systemd-v247-runner.sh prepare [mediamtx-compatibility-remediation options]
  mediamtx-systemd-v247-runner.sh activate [mediamtx-compatibility-remediation options]
  mediamtx-systemd-v247-runner.sh status [mediamtx-compatibility-remediation options]

This launcher leaves the audited compatibility core unchanged on disk. It verifies
that exact core by SHA-256, creates a root-only deterministic runtime copy with
exactly one `PrivateUsers=self` -> `PrivateUsers=yes` compatibility substitution,
proves the transient sandbox property set on prepare, then executes the patched
copy. Prepare and activate therefore bind to identical effective tool bytes.
USAGE
}

command="${1:-}"
case "$command" in
  prepare|activate|status) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "ERROR unknown command: $command" >&2; usage >&2; exit 2 ;;
esac
args=("$@")

[[ "$EUID" -eq 0 ]] || { echo "ERROR run this command as root" >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "ERROR sha256sum is required" >&2; exit 4; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR python3 is required" >&2; exit 4; }
command -v systemctl >/dev/null 2>&1 || { echo "ERROR systemctl is required" >&2; exit 4; }
command -v flock >/dev/null 2>&1 || { echo "ERROR flock is required" >&2; exit 4; }

[[ -f "$CORE" && ! -L "$CORE" ]] || { echo "ERROR audited compatibility core is missing" >&2; exit 7; }
[[ "$(stat -c '%u' "$CORE")" == 0 ]] || { echo "ERROR audited compatibility core must be owned by root" >&2; exit 7; }
core_sha="$(sha256sum "$CORE" | awk '{print $1}')"
[[ "$core_sha" == "$EXPECTED_CORE_SHA256" ]] || {
  echo "ERROR audited compatibility core SHA-256 does not match the approved Issue #87 core" >&2
  exit 7
}

install -d -o root -g root -m 0700 "$RUNTIME_ROOT"
exec 9>"$LOCK"
chmod 0600 "$LOCK"
flock -n 9 || { echo "ERROR another systemd compatibility launcher is active" >&2; exit 8; }

patched_tmp="$PATCHED.tmp.$BASHPID"
rm -f "$patched_tmp"
python3 - "$CORE" "$patched_tmp" <<'PY'
from pathlib import Path
import sys

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
raw = src.read_bytes()
needle = b"    --property=PrivateUsers=self\n"
replacement = b"    --property=PrivateUsers=yes\n"
if raw.count(needle) != 1:
    raise SystemExit("approved core must contain exactly one PrivateUsers=self sandbox property")
if raw.count(replacement) != 0:
    raise SystemExit("approved core unexpectedly already contains PrivateUsers=yes")
patched = raw.replace(needle, replacement, 1)
if patched.count(needle) != 0 or patched.count(replacement) != 1:
    raise SystemExit("PrivateUsers compatibility substitution was not exact")
if patched.replace(replacement, needle, 1) != raw:
    raise SystemExit("runtime compatibility copy differs by more than the approved substitution")
dst.write_bytes(patched)
PY
chown root:root "$patched_tmp"
chmod 0700 "$patched_tmp"
mv -f "$patched_tmp" "$PATCHED"
patched_sha="$(sha256sum "$PATCHED" | awk '{print $1}')"

printf 'COMPATIBILITY_CORE_SHA256=%s\n' "$core_sha"
printf 'EFFECTIVE_COMPATIBILITY_TOOL_SHA256=%s\n' "$patched_sha"
printf 'SYSTEMD_PRIVATE_USERS_COMPAT=SELF_TO_YES\n'

service_name="mediamtx.service"
for ((index=0; index<${#args[@]}; index++)); do
  if [[ "${args[index]}" == "--service" ]]; then
    (( index + 1 < ${#args[@]} )) || { echo "ERROR --service requires a value" >&2; exit 2; }
    service_name="${args[index+1]}"
    break
  fi
done
[[ "$service_name" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || { echo "ERROR invalid service name" >&2; exit 3; }

if [[ "$command" == "prepare" ]]; then
  command -v systemd-run >/dev/null 2>&1 || { echo "ERROR systemd-run is required" >&2; exit 4; }
  systemd_version="$(systemd-run --version | awk 'NR == 1 {print $2}')"
  [[ "$systemd_version" =~ ^[0-9]+$ ]] && (( systemd_version >= 247 )) || {
    echo "ERROR systemd 247 or newer is required for candidate isolation" >&2
    exit 4
  }

  service_user="$(systemctl show "$service_name" -p User --value)"
  service_group="$(systemctl show "$service_name" -p Group --value)"
  service_umask="$(systemctl show "$service_name" -p UMask --value)"
  [[ -n "$service_user" && "$service_user" != root ]] || { echo "ERROR MediaMTX service must use an explicit non-root user" >&2; exit 6; }
  id "$service_user" >/dev/null 2>&1 || { echo "ERROR MediaMTX service user does not exist" >&2; exit 6; }
  [[ -n "$service_group" ]] || service_group="$(id -gn "$service_user")"
  [[ "$service_umask" =~ ^[0-7]{4}$ ]] || { echo "ERROR MediaMTX service UMask is unsupported" >&2; exit 6; }

  preflight_root="$RUNTIME_ROOT/preflight"
  install -d -o root -g root -m 0700 "$preflight_root"
  preflight_log="$preflight_root/systemd-run.log"
  : > "$preflight_log"
  chmod 0600 "$preflight_log"
  unit="sea-speed-mediamtx-sandbox-preflight-${BASHPID}.service"

  sandbox_properties=(
    --property=Type=exec
    --property="User=$service_user"
    --property="Group=$service_group"
    --property="UMask=$service_umask"
    --property=PrivateTmp=yes
    --property=PrivateDevices=yes
    --property=PrivateIPC=yes
    --property=PrivateUsers=yes
    --property=ProtectSystem=strict
    --property=ProtectHome=yes
    --property=ProtectControlGroups=yes
    --property=ProtectKernelLogs=yes
    --property=ProtectKernelModules=yes
    --property=ProtectKernelTunables=yes
    --property=ProtectProc=invisible
    --property=ProcSubset=pid
    --property=ProtectClock=yes
    --property=ProtectHostname=yes
    --property=NoNewPrivileges=yes
    --property=RestrictSUIDSGID=yes
    --property=RestrictNamespaces=yes
    --property=LockPersonality=yes
    --property=RestrictRealtime=yes
    --property=RemoveIPC=yes
    --property=KeyringMode=private
    --property=SystemCallArchitectures=native
    --property="RestrictAddressFamilies=AF_INET AF_INET6"
    --property=CapabilityBoundingSet=
    --property=AmbientCapabilities=
    --property=NoExecPaths=/
    --property=ExecPaths=/usr/bin/true
    --property="ReadWritePaths=$preflight_root"
    --property=KillMode=control-group
    --property=TimeoutStopSec=2s
    --property=TasksMax=128
    --property=MemoryMax=512M
    --property=CPUQuota=100%
    --property=WorkingDirectory=/
    --property=PrivateNetwork=yes
    --property=RuntimeMaxSec=5s
    --property="StandardOutput=append:$preflight_log"
    --property="StandardError=append:$preflight_log"
  )

  if ! systemd-run --quiet --wait --collect --unit="$unit" "${sandbox_properties[@]}" /usr/bin/true; then
    printf 'SYSTEMD_SANDBOX_PREFLIGHT=FAIL\n' >&2
    printf 'SYSTEMD_SANDBOX_PREFLIGHT_LOG=%s\n' "$preflight_log" >&2
    exit 9
  fi
  printf 'SYSTEMD_SANDBOX_PREFLIGHT=PASS\n'
  printf 'SYSTEMD_VERSION=%s\n' "$systemd_version"
fi

exec "$PATCHED" "$command" "${args[@]}"
