#!/usr/bin/env bash
# RTSP source transport pinned to tcp for camera→Ubuntu relay (Issue #362: RTP loss)
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  camera-relay.sh prepare --config PATH --private-rtsp-address IPv4:PORT --reader-ip IPv4 [--reader-ip IPv4 ...] [options]
  camera-relay.sh activate --config PATH --private-rtsp-address IPv4:PORT --reader-ip IPv4 [--reader-ip IPv4 ...] --expected-sha256 SHA256 [options]
  camera-relay.sh sanitize --config PATH --private-rtsp-address IPv4:PORT --reader-ip IPv4 [--reader-ip IPv4 ...] [options]
  camera-relay.sh remediate --config PATH --private-rtsp-address IPv4:PORT --reader-ip IPv4 [--reader-ip IPv4 ...] [options]
  camera-relay.sh status [--private-rtsp-address IPv4:PORT] [options]

Options:
  --reader-ip IPv4         Exact RFC1918 VPS ZeroTier reader IP allowed to read cam1;
                           repeatable or comma-separated for multi-reader deployments
                           (issue #372); all occurrences render in the given order
  --prune-declared SPEC    sanitize only (issue #444): explicit opt-in prune
                           declaration for a dead legacy auth rule
                           path=NAME,ips=IPv4[,IPv4...],actions=read|publish|api[, ...];
                           repeatable, one declaration per legacy rule; bare
                           comma tokens continue the previous key. Only
                           UNMARKED rules matching the declared
                           (path, ips, actions) triple exactly are removed;
                           anything else still fails closed.
  --source-env-file PATH   Protected worker env file (default: /opt/sea-speed-worker/shared/config/worker.env)
  --service NAME           Independent relay service (default: sea-speed-stream.service)
  --worker-service NAME    AI worker service that must remain stopped (default: sea-speed-worker.service)
  --state-root PATH        Root-only candidate/backup state (default: /var/lib/sea-speed-camera-relay)

prepare renders a protected candidate MediaMTX config and does not modify or
restart any service. The candidate preserves existing authentication rules and
adds one credential-free read permission scoped only to cam1 and the exact
RFC1918 reader IP. activate installs only the reviewed candidate, restarts the
independent relay service, and verifies the private RTSP listener. It never
starts, stops, restarts or enables the AI worker. Automatic rollback is not
performed; a root-only backup is preserved for an explicit rollback decision.

sanitize (issue #436) renders a pruned candidate that removes ONLY foreign
unmarked authInternalUsers rules whose scope exactly equals the canonical
loopback API rule (ips 127.0.0.1, action api); any other foreign rule fails
the transaction closed (reported, nothing deleted). The canonical marked
"# Sea Speed " rules are preserved byte-identically. Issue #444 adds
explicit opt-in prune declarations (--prune-declared, repeatable): each
declared (path, ips, actions) triple makes ONLY the unmarked rules matching
that triple exactly removable (per-declaration removals reported in
DECLARED_PRUNED); partial matches and undeclared foreign rules still fail
the transaction closed, and WITHOUT declarations the behavior is unchanged.
Installation of the
pruned candidate reuses the digest-bound activate flow (--expected-sha256);
a failed sanitize leaves the previous candidate untouched and it must not be
activated.

remediate (issue #437) renders a candidate that converges a DRIFTED marked
reader rule back to the canonical read-only relay block while PRESERVING the
live rule's current scopes: the renderer locates the marker-anchored block,
reuses _parse_rule_block to extract the live ips/actions, re-authorizes every
scope element through the existing validators, and re-emits the canonical
block via _reader_rule_lines. Any unauthorized scope (non-IPv4, loopback,
public or duplicate ips; actions outside {read, publish}; publish on the
read-only cam1 relay profile) fails the whole transaction closed (reported,
nothing replaced). A conforming rule is an idempotent no-op
(REMEDIATION_NEEDED=NO) whose candidate is byte-identical to the live config.
Installation reuses the digest-bound activate flow (--expected-sha256); a
failed remediate leaves the previous candidate untouched and it must not be
activated.
EOF
}

command="${1:-}"
case "$command" in
  prepare|activate|sanitize|remediate|status) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "ERROR unknown command: $command" >&2; usage >&2; exit 2 ;;
esac

config=""
private_rtsp_address=""
reader_ips=()
declared_prune_specs=()
source_env_file="/opt/sea-speed-worker/shared/config/worker.env"
service_name="sea-speed-stream.service"
worker_service="sea-speed-worker.service"
state_root="/var/lib/sea-speed-camera-relay"
expected_sha256=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) [[ $# -ge 2 ]] || { echo "ERROR --config requires a path" >&2; exit 2; }; config="$2"; shift 2 ;;
    --private-rtsp-address) [[ $# -ge 2 ]] || { echo "ERROR --private-rtsp-address requires IPv4:PORT" >&2; exit 2; }; private_rtsp_address="$2"; shift 2 ;;
    --reader-ip)
      [[ $# -ge 2 ]] || { echo "ERROR --reader-ip requires IPv4" >&2; exit 2; }
      # Repeatable and comma-separated since issue #372; order preserved.
      IFS=',' read -r -a __reader_ip_parts <<< "$2"
      for __reader_ip_part in "${__reader_ip_parts[@]}"; do
        __reader_ip_part="${__reader_ip_part#"${__reader_ip_part%%[![:space:]]*}"}"
        __reader_ip_part="${__reader_ip_part%"${__reader_ip_part##*[![:space:]]}"}"
        [[ -n "$__reader_ip_part" ]] || { echo "ERROR --reader-ip contains an empty entry" >&2; exit 2; }
        reader_ips+=("$__reader_ip_part")
      done
      shift 2
      ;;
    --prune-declared)
      # Issue #444: repeatable explicit opt-in prune declaration, forwarded
      # verbatim to the renderer (which validates the grammar fail-closed).
      [[ $# -ge 2 ]] || { echo "ERROR --prune-declared requires a spec" >&2; exit 2; }
      [[ -n "$2" ]] || { echo "ERROR --prune-declared spec must not be empty" >&2; exit 2; }
      declared_prune_specs+=("$2")
      shift 2
      ;;
    --source-env-file) [[ $# -ge 2 ]] || { echo "ERROR --source-env-file requires a path" >&2; exit 2; }; source_env_file="$2"; shift 2 ;;
    --service) [[ $# -ge 2 ]] || { echo "ERROR --service requires a name" >&2; exit 2; }; service_name="$2"; shift 2 ;;
    --worker-service) [[ $# -ge 2 ]] || { echo "ERROR --worker-service requires a name" >&2; exit 2; }; worker_service="$2"; shift 2 ;;
    --state-root) [[ $# -ge 2 ]] || { echo "ERROR --state-root requires a path" >&2; exit 2; }; state_root="$2"; shift 2 ;;
    --expected-sha256) [[ $# -ge 2 ]] || { echo "ERROR --expected-sha256 requires a digest" >&2; exit 2; }; expected_sha256="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/../../.." && pwd)"
renderer="$repo_root/scripts/operations/mediamtx_path_config.py"
candidate="$state_root/cam1-mediamtx.candidate.yml"
candidate_sha_file="$state_root/cam1-mediamtx.candidate.sha256"
backup_root="$state_root/backups"

service_value() {
  local action="$1" name="$2" value
  value="$(systemctl "$action" "$name" 2>/dev/null || true)"
  [[ -n "$value" ]] || value="unknown"
  printf '%s' "$value"
}

require_root() {
  if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR run this command as root" >&2
    exit 1
  fi
}

validate_service_name() {
  local value="$1"
  [[ "$value" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || {
    echo "ERROR invalid systemd service name" >&2
    exit 3
  }
}

validate_common() {
  validate_service_name "$service_name"
  validate_service_name "$worker_service"
  [[ -x "$renderer" || -f "$renderer" ]] || { echo "ERROR renderer missing from exact repository source" >&2; exit 4; }
  command -v python3 >/dev/null 2>&1 || { echo "ERROR python3 is required" >&2; exit 4; }
  command -v systemctl >/dev/null 2>&1 || { echo "ERROR systemctl is required" >&2; exit 4; }
}

parse_address() {
  python3 - "$private_rtsp_address" <<'PY'
import ipaddress
import sys
networks = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
value = sys.argv[1]
try:
    host, raw_port = value.rsplit(":", 1)
    ip = ipaddress.ip_address(host)
    port = int(raw_port)
except Exception:
    raise SystemExit(1)
if ip.version != 4 or not any(ip in network for network in networks) or not (1 <= port <= 65535):
    raise SystemExit(1)
print(host)
print(port)
PY
}

validate_reader_ip() {
  python3 - "$1" <<'PY'
import ipaddress
import sys
networks = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
try:
    ip = ipaddress.ip_address(sys.argv[1])
except ValueError:
    raise SystemExit(1)
if ip.version != 4 or not any(ip in network for network in networks):
    raise SystemExit(1)
PY
}

reader_auth_scope() {
  # Deterministic evidence token (issue #372); single reader keeps the
  # historical literal so single-IP output stays byte-identical.
  if [[ ${#reader_ips[@]} -eq 1 ]]; then
    printf 'cam1-single-rfc1918-peer'
  else
    printf 'cam1-multi-rfc1918-peer-count-%s' "${#reader_ips[@]}"
  fi
}

check_private_listener() {
  local parsed host port
  parsed="$(parse_address)" || { echo "ERROR invalid private RTSP address" >&2; return 1; }
  host="$(printf '%s\n' "$parsed" | sed -n '1p')"
  port="$(printf '%s\n' "$parsed" | sed -n '2p')"
  python3 - "$host" "$port" <<'PY'
import socket
import sys
host, port = sys.argv[1], int(sys.argv[2])
try:
    with socket.create_connection((host, port), timeout=3):
        pass
except OSError:
    raise SystemExit(1)
PY
}

derive_relay_service_identity() {
  # Issue #447: service-identity derivation must FAIL CLOSED — a silent
  # root:root 0600 fallback under docker-chroot (systemctl show hits no bus)
  # mis-installed permissions and crash-looped mediamtx. Derivation order:
  #   (1) `systemctl show` (bus): definitive ONLY when User is non-empty.
  #   (2) `systemctl cat` (offline-safe; the unit file is on disk even under
  #       chroot): parse the LAST `User=`/`Group=` assignment (systemd
  #       override semantics). `User=` absent or empty means the unit runs
  #       as root.
  #   (3) BOTH failing -> explicit ERROR + nonzero return; the caller
  #       refuses to install with guessed ownership (before backup/install).
  # Prints "owner group mode" on stdout; uses the global $service_name.
  local show_user show_group unit_text unit_user unit_group
  show_user="$(systemctl show -p User --value "$service_name" 2>/dev/null || true)"
  show_group="$(systemctl show -p Group --value "$service_name" 2>/dev/null || true)"
  if [[ -n "$show_user" ]]; then
    if [[ "$show_user" == "root" ]]; then
      printf 'root root 0600\n'
      return 0
    fi
    if [[ -z "$show_group" ]]; then
      show_group="$(id -gn "$show_user" 2>/dev/null || true)"
    fi
    if [[ -z "$show_group" ]]; then
      echo "ERROR cannot resolve relay service group" >&2
      return 1
    fi
    printf 'root %s 0640\n' "$show_group"
    return 0
  fi
  unit_text="$(systemctl cat "$service_name" 2>/dev/null || true)"
  if [[ -n "$unit_text" ]]; then
    unit_user="$(printf '%s\n' "$unit_text" | sed -nE 's/^[[:space:]]*User=([^[:space:]].*)$/\1/p' | tail -n 1)"
    unit_group="$(printf '%s\n' "$unit_text" | sed -nE 's/^[[:space:]]*Group=([^[:space:]].*)$/\1/p' | tail -n 1)"
    if [[ -z "$unit_user" || "$unit_user" == "root" ]]; then
      printf 'root root 0600\n'
      return 0
    fi
    if [[ -z "$unit_group" ]]; then
      unit_group="$(id -gn "$unit_user" 2>/dev/null || true)"
    fi
    if [[ -z "$unit_group" ]]; then
      echo "ERROR cannot resolve relay service group" >&2
      return 1
    fi
    printf 'root %s 0640\n' "$unit_group"
    return 0
  fi
  echo "ERROR relay service identity could not be derived (systemctl unavailable and unit file unreadable); refusing to install with guessed ownership" >&2
  return 1
}

check_auth_environment_override() {
  local environment
  environment="$(systemctl show -p Environment --value "$service_name" 2>/dev/null || true)"
  if [[ "$environment" == *"MTX_AUTHMETHOD="* || "$environment" == *"MTX_AUTHINTERNALUSERS"* ]]; then
    echo "ERROR relay authentication is overridden by systemd environment; bounded config remediation cannot proceed" >&2
    exit 10
  fi
}

validate_common

if [[ "$command" == "status" ]]; then
  printf 'RELAY_ENABLED=%s\n' "$(service_value is-enabled "$service_name")"
  printf 'RELAY_ACTIVE=%s\n' "$(service_value is-active "$service_name")"
  printf 'AI_WORKER_ENABLED=%s\n' "$(service_value is-enabled "$worker_service")"
  printf 'AI_WORKER_ACTIVE=%s\n' "$(service_value is-active "$worker_service")"
  if [[ -n "$private_rtsp_address" ]]; then
    if check_private_listener; then
      printf 'PRIVATE_RELAY_TCP=PASS\n'
    else
      printf 'PRIVATE_RELAY_TCP=FAIL\n'
    fi
  else
    printf 'PRIVATE_RELAY_TCP=NOT_CHECKED\n'
  fi
  exit 0
fi

require_root
[[ -n "$config" ]] || { echo "ERROR --config is required" >&2; exit 2; }
[[ -n "$private_rtsp_address" ]] || { echo "ERROR --private-rtsp-address is required" >&2; exit 2; }
[[ ${#reader_ips[@]} -gt 0 ]] || { echo "ERROR --reader-ip is required" >&2; exit 2; }
parse_address >/dev/null || { echo "ERROR private RTSP address must be RFC1918 IPv4:PORT" >&2; exit 3; }
for reader_ip in "${reader_ips[@]}"; do
  validate_reader_ip "$reader_ip" || { echo "ERROR reader IP must be a literal RFC1918 IPv4 address: $reader_ip" >&2; exit 3; }
done
reader_ip_args=()
for reader_ip in "${reader_ips[@]}"; do
  reader_ip_args+=(--reader-ip "$reader_ip")
done
[[ -f "$config" && ! -L "$config" ]] || { echo "ERROR MediaMTX config must be a regular non-symlink file" >&2; exit 5; }
check_auth_environment_override

install -d -o root -g root -m 0700 "$state_root" "$backup_root"

if [[ "$command" == "prepare" ]]; then
  [[ -f "$source_env_file" && ! -L "$source_env_file" ]] || { echo "ERROR protected source env file is unavailable" >&2; exit 6; }
  [[ "$(stat -c '%a' "$source_env_file")" == "600" ]] || { echo "ERROR protected source env file mode must be 600" >&2; exit 6; }

  # The renderer pins the cam1 RTSP source to rtsp_transport="tcp" (Issue #362)
  # to eliminate RTP packet loss / invalid fragmentation unit on the camera->Ubuntu relay.
  python3 "$renderer" ubuntu-relay \
    --config "$config" \
    --source-env-file "$source_env_file" \
    --source-env-key HLS_URL \
    --private-rtsp-address "$private_rtsp_address" \
    "${reader_ip_args[@]}" \
    --path cam1 \
    --output "$candidate"

  digest="$(sha256sum "$candidate" | awk '{print $1}')"
  printf '%s\n' "$digest" > "$candidate_sha_file"
  chown root:root "$candidate" "$candidate_sha_file"
  chmod 0600 "$candidate" "$candidate_sha_file"

  printf 'PREPARED_RELAY_CANDIDATE=YES\n'
  printf 'CANDIDATE_SHA256=%s\n' "$digest"
  printf 'CAMERA_SOURCE_SCHEME=rtsp\n'
  printf 'CAMERA_SOURCE_USERINFO=YES\n'
  printf 'RELAY_PATH=cam1\n'
  printf 'READER_AUTH_SCOPE=%s\n' "$(reader_auth_scope)"
  printf 'READER_AUTH_PERMISSION=read-only\n'
  printf 'RELAY_ENABLED=%s\n' "$(service_value is-enabled "$service_name")"
  printf 'RELAY_ACTIVE=%s\n' "$(service_value is-active "$service_name")"
  printf 'AI_WORKER_ACTIVE=%s\n' "$(service_value is-active "$worker_service")"
  printf 'MUTATIONS=PROTECTED_CANDIDATE_ONLY\n'
  printf 'SERVICE_RESTARTED=NO\n'
  printf 'AI_WORKER_STARTED=NO\n'
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

if [[ "$command" == "sanitize" ]]; then
  # Issue #436: bounded auth-sanitize transaction. Verify-before on the LIVE
  # config (canonical reader rule), then the renderer mode verifies the
  # marked loopback API rule before/after, prunes ONLY foreign unmarked rules
  # scoped exactly like the canonical loopback API rule (anything else fails
  # closed: reported, nothing deleted, candidate untouched), and asserts the
  # foreign-rule count == 0 explicitly. Verify-after re-checks the reader
  # rule on the CANDIDATE. Installation is only through the existing
  # digest-bound activate flow below; automatic rollback is not authorized.
  # Issue #444: repeatable --prune-declared specs are forwarded to the
  # renderer; each declared (path, ips, actions) triple makes exactly the
  # matching unmarked legacy rules removable, with per-declaration removals
  # reported in DECLARED_PRUNED below.
  python3 "$renderer" verify-reader-auth \
    --config "$config" \
    "${reader_ip_args[@]}" \
    --path cam1 >/dev/null

  declared_args=()
  for declared_spec in "${declared_prune_specs[@]}"; do
    declared_args+=(--prune-declared "$declared_spec")
  done

  sanitize_output="$(python3 "$renderer" ubuntu-sanitize-auth \
    --config "$config" \
    "${declared_args[@]}" \
    --output "$candidate")"
  printf '%s\n' "$sanitize_output"

  digest="$(sha256sum "$candidate" | awk '{print $1}')"
  printf '%s\n' "$digest" > "$candidate_sha_file"
  chown root:root "$candidate" "$candidate_sha_file"
  chmod 0600 "$candidate" "$candidate_sha_file"

  python3 "$renderer" verify-reader-auth \
    --config "$candidate" \
    "${reader_ip_args[@]}" \
    --path cam1 >/dev/null

  printf 'SANITIZED_FOREIGN_AUTH=YES\n'
  if [[ ${#declared_prune_specs[@]} -gt 0 ]]; then
    # Per-declaration removal evidence (issue #444). The renderer emits one
    # DECLARED_PRUNED line per declaration; a missing line is a real
    # inconsistency and fails the transaction closed (grep under pipefail).
    declared_evidence="$(printf '%s\n' "$sanitize_output" \
      | grep '^DECLARED_PRUNED ' \
      | sed -E 's/^DECLARED_PRUNED path=([^ ]+) .* removed=([0-9]+)$/path=\1:removed=\2/' \
      | paste -sd, -)"
    printf 'DECLARED_PRUNED=%s\n' "$declared_evidence"
  fi
  printf 'CANDIDATE_SHA256=%s\n' "$digest"
  printf 'MUTATIONS=PROTECTED_CANDIDATE_ONLY\n'
  printf 'SERVICE_RESTARTED=NO\n'
  printf 'AI_WORKER_STARTED=NO\n'
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

if [[ "$command" == "remediate" ]]; then
  # Issue #437: bounded drifted-reader-rule remediation transaction. Verify-before
  # on the LIVE config (the reader rule must still authorize the operator-stated
  # reader IPs), then the renderer mode verifies the marked loopback API rule,
  # locates the drifted marked reader block, reuses _parse_rule_block for the
  # live ips/actions, re-authorizes every scope element through the existing
  # validators (non-IPv4/loopback/public/duplicate ips, actions outside
  # {read, publish}, publish on the read-only cam1 relay profile all fail
  # closed: reported, nothing replaced, candidate untouched), re-emits the
  # canonical block via _reader_rule_lines preserving the live scopes, and
  # re-verifies reader + API rules on the result. Verify-after re-checks the
  # reader rule on the CANDIDATE. Installation is only through the existing
  # digest-bound activate flow below; automatic rollback is not authorized.
  python3 "$renderer" verify-reader-auth \
    --config "$config" \
    "${reader_ip_args[@]}" \
    --path cam1 >/dev/null

  render_out="$(python3 "$renderer" ubuntu-remediate-reader \
    --config "$config" \
    --path cam1 \
    --output "$candidate")"
  printf '%s\n' "$render_out"

  digest="$(sha256sum "$candidate" | awk '{print $1}')"
  printf '%s\n' "$digest" > "$candidate_sha_file"
  chown root:root "$candidate" "$candidate_sha_file"
  chmod 0600 "$candidate" "$candidate_sha_file"

  python3 "$renderer" verify-reader-auth \
    --config "$candidate" \
    "${reader_ip_args[@]}" \
    --path cam1 >/dev/null

  remediation_needed="NO"
  case "$render_out" in *"remediation_needed=YES"*) remediation_needed="YES" ;; esac

  printf 'REMEDIATED_READER=YES\n'
  printf 'REMEDIATION_NEEDED=%s\n' "$remediation_needed"
  printf 'CANDIDATE_SHA256=%s\n' "$digest"
  printf 'MUTATIONS=PROTECTED_CANDIDATE_ONLY\n'
  printf 'SERVICE_RESTARTED=NO\n'
  printf 'AI_WORKER_STARTED=NO\n'
  printf 'SECRETS_DISPLAYED=NO\n'
  exit 0
fi

[[ "$expected_sha256" =~ ^[0-9a-f]{64}$ ]] || { echo "ERROR activate requires --expected-sha256" >&2; exit 2; }
[[ -f "$candidate" && ! -L "$candidate" ]] || { echo "ERROR prepared candidate is missing" >&2; exit 7; }
actual_sha256="$(sha256sum "$candidate" | awk '{print $1}')"
[[ "$actual_sha256" == "$expected_sha256" ]] || { echo "ERROR prepared candidate digest mismatch" >&2; exit 7; }
[[ "$(stat -c '%a' "$candidate")" == "600" ]] || { echo "ERROR candidate mode must be 600" >&2; exit 7; }
python3 "$renderer" verify-reader-auth \
  --config "$candidate" \
  "${reader_ip_args[@]}" \
  --path cam1 >/dev/null

if systemctl is-active --quiet "$worker_service"; then
  echo "ERROR AI worker must remain stopped during live-relay activation" >&2
  exit 8
fi

# Issue #447: derive the relay service identity fail-closed (systemctl show,
# then the unit file via systemctl cat) BEFORE any mutation — a wrong guess
# must refuse, never mis-install ownership. The derivation sits before the
# backup on purpose: backup is itself a state-dir mutation.
identity="$(derive_relay_service_identity)" || exit 9
read -r install_owner install_group install_mode <<< "$identity"
printf 'INSTALL_OWNER=%s:%s\n' "$install_owner" "$install_group"
printf 'MODE=%s\n' "$install_mode"

backup="$backup_root/mediamtx.$(date -u +%Y%m%dT%H%M%SZ).yml"
install -o root -g root -m 0600 "$config" "$backup"
install -o "$install_owner" -g "$install_group" -m "$install_mode" "$candidate" "${config}.next"
mv -f "${config}.next" "$config"

systemctl restart "$service_name" || {
  echo "ERROR relay service restart failed; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$backup" >&2
  exit 30
}
systemctl is-active --quiet "$service_name" || {
  echo "ERROR relay service is not active; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$backup" >&2
  exit 31
}
check_private_listener || {
  echo "ERROR private relay TCP listener is not reachable; automatic rollback is not authorized" >&2
  printf 'BACKUP=%s\n' "$backup" >&2
  exit 32
}
if systemctl is-active --quiet "$worker_service"; then
  echo "ERROR AI worker became active unexpectedly" >&2
  exit 33
fi

printf 'ACTIVATED_RELAY=YES\n'
printf 'RELAY_PATH=cam1\n'
printf 'PRIVATE_RELAY_TCP=PASS\n'
printf 'READER_AUTH_SCOPE=%s\n' "$(reader_auth_scope)"
printf 'READER_AUTH_PERMISSION=read-only\n'
printf 'RELAY_ACTIVE=active\n'
printf 'AI_WORKER_ACTIVE=inactive\n'
printf 'AI_WORKER_STARTED=NO\n'
printf 'CAMERA_PLAYBACK_TESTED=NO\n'
printf 'BACKUP=%s\n' "$backup"
printf 'SECRETS_DISPLAYED=NO\n'
