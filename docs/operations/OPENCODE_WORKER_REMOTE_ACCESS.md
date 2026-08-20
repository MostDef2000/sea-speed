# OpenCode Remote Access to the Sea Speed Worker

Status: Active

## Purpose

Define operator-managed diagnostic access to the commissioned Ubuntu worker. This path is separate from the automated GitHub Actions production transport.

OpenCode stays on the operator Windows system. Do not install OpenCode or a general-purpose self-hosted GitHub runner on the production worker solely to administer it.

## Operator connection: direct ZeroTier SSH

Canonical operator target:

```text
logical alias: sea-speed-worker
user: seaspeedadmin
host: 10.123.239.102
port: 22
transport: ZeroTier
```

Preferred Windows OpenSSH configuration:

```sshconfig
Host sea-speed-worker
    HostName 10.123.239.102
    User seaspeedadmin
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

Use normal host-key verification. Never use `StrictHostKeyChecking=no` or delete a mismatched key merely to make a connection succeed.

## Operator fallback: VPS tunnel

When direct ZeroTier SSH from the operator laptop is unavailable, the VPS may be used as a transport bridge:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:2222:10.123.239.102:22 root@82.146.37.153
```

Keep that tunnel window open. In another terminal connect with a stable host-key alias. The VPS is transport only and is not worker authority.

## Automated production transport is separate

Normal post-bootstrap production delivery does not use the `seaspeedadmin` operator identity. GitHub Actions uses a dedicated account:

```text
sea-speed-deploy@10.123.239.102:22
```

The runner reaches it only through strict-host-key VPS `ProxyJump`. The account authorized key is `restrict` + forced command and cannot provide an interactive shell, PTY, forwarding or arbitrary sudo. The forced command accepts only `sea-speed-ubuntu-deploy-v1 <sha> <issue> <artifact-sha256>` and delegates to the root-owned zero-touch gate.

See `docs/operations/UBUNTU_ZERO_TOUCH_DEPLOYMENT.md`.

## Root and sudo boundary

OpenCode/operator access does not receive a standing broad sudo grant. Ordinary operator root work still requires the human to enter the sudo password locally.

The only passwordless production exception is the dedicated `sea-speed-deploy` account invoking the root-owned zero-touch gate with validated exact arguments. That rule is installed by `scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh` and is not available to `seaspeedadmin` or arbitrary commands.

Do not use `sudo -S`, broad `NOPASSWD`, passwords in arguments, or self-hosted-runner privilege as a bypass.

## Secret boundary

Never place camera credentials, credential-bearing RTSP URLs, API tokens, populated worker environments, GitHub tokens, private SSH keys, sudo passwords or VPS passwords in prompts, repository files, command-line arguments, process listings or reports.

## Repository boundary

All durable GitHub lifecycle operations use the GitHub Connector under Sea Speed governance. SSH access is runtime transport/diagnostics only; the worker is not an editable source store.

## Production action boundary

A working SSH session means transport is available. Production mutation still requires protected public `main`, exact-main Quality, standing policy allow and the repository-owned target transaction.
