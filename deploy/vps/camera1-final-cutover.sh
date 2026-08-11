#!/usr/bin/env bash
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
export PATH LC_ALL
umask 077

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COMPAT_RUNNER="$SCRIPT_DIR/mediamtx-systemd-v247-runner.sh"

usage() {
  cat <<'USAGE'
Usage:
  camera1-final-cutover.sh prepare --config PATH [compatibility prepare options]
  camera1-final-cutover.sh activate --config PATH [compatibility activate options]
  camera1-final-cutover.sh status --config PATH [compatibility status options]

This is a thin resumable launcher. It never edits MediaMTX configuration. The
already-approved HLS remediation is considered complete only when the active
configuration already contains one top-level `hlsVariant: fmp4`. In that state
it reports ALREADY_APPLIED and delegates to the systemd-v247 compatibility
runner. `mpegts` is a clean stop instead of a repeated production mutation.
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
[[ -x "$COMPAT_RUNNER" && ! -L "$COMPAT_RUNNER" ]] || { echo "ERROR systemd compatibility runner is missing" >&2; exit 7; }

config=""
for ((index=0; index<${#args[@]}; index++)); do
  if [[ "${args[index]}" == "--config" ]]; then
    (( index + 1 < ${#args[@]} )) || { echo "ERROR --config requires a value" >&2; exit 2; }
    config="${args[index+1]}"
    break
  fi
done
[[ -n "$config" ]] || { echo "ERROR --config is required" >&2; exit 2; }
[[ -f "$config" && ! -L "$config" ]] || { echo "ERROR MediaMTX config must be a regular non-symlink file" >&2; exit 5; }

variant="$(python3 - "$config" <<'PY'
import json
import re
import sys

lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
values = []
for line in lines:
    if not line or line[0].isspace() or line.lstrip().startswith("#"):
        continue
    match = re.match(r"^hlsVariant\s*:\s*(.*?)\s*$", line)
    if match:
        raw = match.group(1).split(" #", 1)[0].strip()
        values.append(str(json.loads(raw)) if raw.startswith('"') else raw)
if len(values) != 1:
    raise SystemExit(2)
print(values[0])
PY
)" || { echo "ERROR active MediaMTX config must contain exactly one top-level hlsVariant" >&2; exit 5; }

case "$variant" in
  fmp4)
    printf 'HLS_VARIANT_REMEDIATION=ALREADY_APPLIED\n'
    printf 'HLS_VARIANT=fmp4\n'
    ;;
  mpegts)
    printf 'HLS_VARIANT_REMEDIATION=REQUIRED\n' >&2
    printf 'HLS_VARIANT=mpegts\n' >&2
    echo "ERROR approved fmp4 remediation is not present; this resumable runner will not repeat or broaden production mutation" >&2
    exit 5
    ;;
  *)
    printf 'HLS_VARIANT=%s\n' "$variant" >&2
    echo "ERROR unsupported explicit HLS variant for the bounded Camera 1 completion flow" >&2
    exit 5
    ;;
esac

printf 'CAMERA1_FINAL_CUTOVER_STAGE=%s\n' "${command^^}"
exec "$COMPAT_RUNNER" "$command" "${args[@]}"
