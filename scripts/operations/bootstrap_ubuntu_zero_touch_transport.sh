#!/usr/bin/env bash
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

readonly DEPLOY_USER="sea-speed-deploy"
readonly DEPLOY_HOME="/var/lib/sea-speed-deploy"
readonly GATE_PATH="/usr/local/sbin/sea-speed-ubuntu-zero-touch-gate"
readonly SUDOERS_PATH="/etc/sudoers.d/sea-speed-ubuntu-zero-touch"
readonly SSHD_HARDENING_PATH="/etc/ssh/sshd_config.d/00-sea-speed-hardening.conf"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_GATE="$SCRIPT_DIR/sea_speed_ubuntu_zero_touch_gate.sh"

usage() {
  cat <<'USAGE'
Usage:
  bootstrap_ubuntu_zero_touch_transport.sh --public-key-file PATH [--expected-fingerprint SHA256:...]
  bootstrap_ubuntu_zero_touch_transport.sh --remove

Installs or removes the dedicated restricted GitHub Actions -> VPS ProxyJump ->
Ubuntu Worker transport boundary. It never creates a private key and never
prints a private credential.
USAGE
}

[[ "$EUID" -eq 0 ]] || { echo "ERROR run as root" >&2; exit 1; }

reload_sshd() {
  if systemctl reload ssh >/dev/null 2>&1; then
    return 0
  fi
  systemctl reload sshd >/dev/null 2>&1
}

effective_allowusers() {
  sshd -T 2>/dev/null | awk '
    BEGIN { emitted = 0 }
    $1 == "allowusers" {
      for (i = 2; i <= NF; i++) {
        printf "%s%s", (emitted ? " " : ""), $i
        emitted = 1
      }
    }
    END {
      if (emitted) {
        printf "\n"
      }
    }
  '
}

allowusers_contains() {
  local wanted="$1"
  local principal
  for principal in $(effective_allowusers); do
    [[ "$principal" == "$wanted" ]] && return 0
  done
  return 1
}

restore_sshd_hardening() {
  local backup_file="$1"
  cat "$backup_file" > "$SSHD_HARDENING_PATH"
  sshd -t >/dev/null 2>&1 || true
  reload_sshd || true
}

set_allowusers_membership() {
  local mode="$1"
  local effective line_count current_line backup_file temp_file replacement
  local -a fields users new_users
  local principal changed=false

  effective="$(effective_allowusers)"

  if [[ ! -f "$SSHD_HARDENING_PATH" ]]; then
    if [[ -n "$effective" ]]; then
      if [[ "$mode" == "add" ]] && allowusers_contains "$DEPLOY_USER"; then
        return 0
      fi
      if [[ "$mode" == "remove" ]] && ! allowusers_contains "$DEPLOY_USER"; then
        return 0
      fi
      echo "ERROR effective AllowUsers is configured outside canonical $SSHD_HARDENING_PATH" >&2
      return 7
    fi
    return 0
  fi

  line_count="$(grep -Eic '^[[:space:]]*AllowUsers[[:space:]]+' "$SSHD_HARDENING_PATH" || true)"
  if (( line_count > 1 )); then
    echo "ERROR canonical SSH hardening file has multiple AllowUsers directives" >&2
    return 7
  fi
  if (( line_count == 0 )); then
    if [[ -n "$effective" ]]; then
      echo "ERROR effective AllowUsers does not originate from canonical SSH hardening file" >&2
      return 7
    fi
    return 0
  fi

  current_line="$(grep -Ei '^[[:space:]]*AllowUsers[[:space:]]+' "$SSHD_HARDENING_PATH" | head -n 1)"
  read -r -a fields <<< "$current_line"
  users=("${fields[@]:1}")
  new_users=()

  if [[ "$mode" == "add" ]]; then
    new_users=("${users[@]}")
    if ! printf '%s\n' "${users[@]}" | grep -Fxq "$DEPLOY_USER"; then
      new_users+=("$DEPLOY_USER")
      changed=true
    fi
  elif [[ "$mode" == "remove" ]]; then
    for principal in "${users[@]}"; do
      if [[ "$principal" == "$DEPLOY_USER" ]]; then
        changed=true
        continue
      fi
      new_users+=("$principal")
    done
    if [[ "$changed" == true && ${#new_users[@]} -eq 0 ]]; then
      echo "ERROR refusing to remove the last AllowUsers principal" >&2
      return 7
    fi
  else
    echo "ERROR unsupported AllowUsers membership mode: $mode" >&2
    return 7
  fi

  if [[ "$changed" != true ]]; then
    if [[ "$mode" == "add" ]]; then
      allowusers_contains "$DEPLOY_USER" || { echo "ERROR deploy principal missing from effective AllowUsers" >&2; return 7; }
    else
      ! allowusers_contains "$DEPLOY_USER" || { echo "ERROR deploy principal still present in effective AllowUsers" >&2; return 7; }
    fi
    for principal in "${new_users[@]}"; do
      allowusers_contains "$principal" || { echo "ERROR existing AllowUsers principal missing from effective policy: $principal" >&2; return 7; }
    done
    return 0
  fi

  backup_file="$(mktemp)"
  temp_file="$(mktemp)"
  cp -p "$SSHD_HARDENING_PATH" "$backup_file"
  replacement="AllowUsers ${new_users[*]}"
  awk -v replacement="$replacement" '
    BEGIN { replaced = 0 }
    /^[[:space:]]*AllowUsers[[:space:]]+/ && replaced == 0 {
      print replacement
      replaced = 1
      next
    }
    { print }
  ' "$SSHD_HARDENING_PATH" > "$temp_file"
  cat "$temp_file" > "$SSHD_HARDENING_PATH"
  rm -f "$temp_file"

  if ! sshd -t >/dev/null 2>&1; then
    restore_sshd_hardening "$backup_file"
    rm -f "$backup_file"
    echo "ERROR sshd configuration invalid after AllowUsers update; original config restored" >&2
    return 7
  fi
  if ! reload_sshd; then
    restore_sshd_hardening "$backup_file"
    rm -f "$backup_file"
    echo "ERROR failed to reload sshd after AllowUsers update; original config restored" >&2
    return 7
  fi

  if [[ "$mode" == "add" ]]; then
    if ! allowusers_contains "$DEPLOY_USER"; then
      restore_sshd_hardening "$backup_file"
      rm -f "$backup_file"
      echo "ERROR deploy principal missing from effective AllowUsers after reload; original config restored" >&2
      return 7
    fi
  else
    if allowusers_contains "$DEPLOY_USER"; then
      restore_sshd_hardening "$backup_file"
      rm -f "$backup_file"
      echo "ERROR deploy principal still present in effective AllowUsers after reload; original config restored" >&2
      return 7
    fi
  fi

  for principal in "${new_users[@]}"; do
    if ! allowusers_contains "$principal"; then
      restore_sshd_hardening "$backup_file"
      rm -f "$backup_file"
      echo "ERROR existing AllowUsers principal missing after reload: $principal; original config restored" >&2
      return 7
    fi
  done

  rm -f "$backup_file"
}

public_key_file=""
expected_fingerprint=""
remove=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --public-key-file) [[ $# -ge 2 ]] || exit 2; public_key_file="$2"; shift 2 ;;
    --expected-fingerprint) [[ $# -ge 2 ]] || exit 2; expected_fingerprint="$2"; shift 2 ;;
    --remove) remove=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for command_name in install ssh-keygen visudo getent useradd usermod sshd systemctl awk grep mktemp; do
  command -v "$command_name" >/dev/null 2>&1 || { echo "ERROR required command missing: $command_name" >&2; exit 4; }
done

if [[ "$remove" == true ]]; then
  rm -f "$SUDOERS_PATH"
  rm -f "$DEPLOY_HOME/.ssh/authorized_keys"
  set_allowusers_membership remove
  if getent passwd "$DEPLOY_USER" >/dev/null; then
    usermod -L "$DEPLOY_USER" || true
  fi
  echo "ZERO_TOUCH_TRANSPORT_REMOVED=YES"
  exit 0
fi

[[ -n "$public_key_file" && -f "$public_key_file" ]] || { echo "ERROR --public-key-file is required" >&2; exit 2; }
[[ -f "$SOURCE_GATE" ]] || { echo "ERROR repository gate script missing: $SOURCE_GATE" >&2; exit 5; }

key_lines="$(grep -cve '^$' "$public_key_file")"
[[ "$key_lines" == "1" ]] || { echo "ERROR public key file must contain exactly one key" >&2; exit 5; }
public_key="$(tr -d '\r\n' < "$public_key_file")"
[[ "$public_key" =~ ^(ssh-ed25519|sk-ssh-ed25519@openssh.com)[[:space:]]+[A-Za-z0-9+/=]+([[:space:]].*)?$ ]] || {
  echo "ERROR only Ed25519 deploy public keys are admitted" >&2; exit 5;
}
fingerprint="$(ssh-keygen -lf "$public_key_file" -E sha256 | awk '{print $2}')"
if [[ -n "$expected_fingerprint" && "$fingerprint" != "$expected_fingerprint" ]]; then
  echo "ERROR public key fingerprint mismatch" >&2
  exit 5
fi

if ! getent passwd "$DEPLOY_USER" >/dev/null; then
  useradd --system --create-home --home-dir "$DEPLOY_HOME" --shell /bin/bash "$DEPLOY_USER"
fi
# A leading '!' in the Linux shadow password field locks the account at sshd's
# account-access gate and therefore blocks public-key authentication too. Keep
# password authentication impossible with OpenSSH's documented non-locking
# invalid-password marker while allowing this account to reach authorized_keys.
usermod --password '*NP*' "$DEPLOY_USER"
shadow_line="$(getent shadow "$DEPLOY_USER")"
IFS=: read -r _ password_field _ <<< "$shadow_line"
[[ "$password_field" == '*NP*' ]] || { echo "ERROR deploy account password-auth boundary mismatch" >&2; exit 6; }

install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" -m 0700 "$DEPLOY_HOME/.ssh"
install -o root -g root -m 0755 "$SOURCE_GATE" "$GATE_PATH"

printf 'restrict,command="%s" %s\n' "$GATE_PATH" "$public_key" > "$DEPLOY_HOME/.ssh/authorized_keys"
chown "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_HOME/.ssh/authorized_keys"
chmod 0600 "$DEPLOY_HOME/.ssh/authorized_keys"

cat > "$SUDOERS_PATH" <<'EOF_SUDOERS'
Defaults:sea-speed-deploy env_reset
sea-speed-deploy ALL=(root) NOPASSWD: /usr/local/sbin/sea-speed-ubuntu-zero-touch-gate --execute *
EOF_SUDOERS
chmod 0440 "$SUDOERS_PATH"
visudo -cf "$SUDOERS_PATH" >/dev/null

[[ "$(stat -c '%U:%G:%a' "$GATE_PATH")" == "root:root:755" ]] || { echo "ERROR gate ownership/mode mismatch" >&2; exit 6; }
[[ "$(stat -c '%U:%G:%a' "$DEPLOY_HOME/.ssh/authorized_keys")" == "$DEPLOY_USER:$DEPLOY_USER:600" ]] || {
  echo "ERROR authorized_keys ownership/mode mismatch" >&2; exit 6
}
grep -Fq "restrict,command=\"$GATE_PATH\"" "$DEPLOY_HOME/.ssh/authorized_keys" || {
  echo "ERROR restricted authorized_keys command missing" >&2; exit 6
}
grep -Fq 'sea-speed-ubuntu-zero-touch-gate --execute *' "$SUDOERS_PATH" || {
  echo "ERROR exact sudo gate boundary missing" >&2; exit 6
}

# The commissioned Worker hardens sshd with a global AllowUsers list. The
# dedicated key cannot reach authorized_keys unless this principal is admitted
# there too. Preserve every existing principal, add only sea-speed-deploy, test
# the complete sshd configuration, reload, and verify effective policy.
set_allowusers_membership add

host_fingerprint="UNKNOWN"
if [[ -f /etc/ssh/ssh_host_ed25519_key.pub ]]; then
  host_fingerprint="$(ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256 | awk '{print $2}')"
fi
printf 'ZERO_TOUCH_TRANSPORT_BOOTSTRAP=PASS\n'
printf 'DEPLOY_USER=%s\n' "$DEPLOY_USER"
printf 'DEPLOY_KEY_FINGERPRINT=%s\n' "$fingerprint"
printf 'WORKER_ED25519_HOST_FINGERPRINT=%s\n' "$host_fingerprint"
printf 'PASSWORD_AUTH=DISABLED_PUBLICKEY_ACCOUNT=ACCESSIBLE\n'
printf 'SSHD_ALLOWUSERS=%s\n' "$(effective_allowusers)"
printf 'AUTHORIZED_KEY_RESTRICTION=restrict+forced-command\n'
printf 'SUDO_BOUNDARY=%s --execute <sha> <issue> <artifact-sha256>\n' "$GATE_PATH"
