#!/usr/bin/env bash
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

readonly DEPLOY_USER="sea-speed-deploy"
readonly DEPLOY_HOME="/var/lib/sea-speed-deploy"
readonly GATE_PATH="/usr/local/sbin/sea-speed-ubuntu-zero-touch-gate"
readonly SUDOERS_PATH="/etc/sudoers.d/sea-speed-ubuntu-zero-touch"
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

for command_name in install ssh-keygen visudo getent useradd usermod passwd; do
  command -v "$command_name" >/dev/null 2>&1 || { echo "ERROR required command missing: $command_name" >&2; exit 4; }
done

if [[ "$remove" == true ]]; then
  rm -f "$SUDOERS_PATH"
  rm -f "$DEPLOY_HOME/.ssh/authorized_keys"
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
passwd -l "$DEPLOY_USER" >/dev/null 2>&1 || true
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

host_fingerprint="UNKNOWN"
if [[ -f /etc/ssh/ssh_host_ed25519_key.pub ]]; then
  host_fingerprint="$(ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256 | awk '{print $2}')"
fi
printf 'ZERO_TOUCH_TRANSPORT_BOOTSTRAP=PASS\n'
printf 'DEPLOY_USER=%s\n' "$DEPLOY_USER"
printf 'DEPLOY_KEY_FINGERPRINT=%s\n' "$fingerprint"
printf 'WORKER_ED25519_HOST_FINGERPRINT=%s\n' "$host_fingerprint"
printf 'AUTHORIZED_KEY_RESTRICTION=restrict+forced-command\n'
printf 'SUDO_BOUNDARY=%s --execute <sha> <issue> <artifact-sha256>\n' "$GATE_PATH"
