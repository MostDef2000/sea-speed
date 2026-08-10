# OpenCode Remote Access to the Sea Speed Worker

Status: Active

## Purpose

Define the normal operator path for managing the commissioned Ubuntu worker with OpenCode running on the operator-managed Windows laptop.

OpenCode stays on Windows. Do not install OpenCode on the production worker solely to administer that worker.

This document defines connection transport and privilege boundaries. It does not authorize production start, stop, restart, activation, deployment, rollback or secret changes.

## Primary connection: direct ZeroTier SSH

The canonical commissioned-worker SSH target is:

```text
logical alias: sea-speed-worker
user: seaspeedadmin
host: 10.123.239.102
port: 22
transport: ZeroTier
```

Preferred Windows OpenSSH config entry:

```sshconfig
Host sea-speed-worker
    HostName 10.123.239.102
    User seaspeedadmin
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

OpenCode should use the logical target when possible:

```powershell
ssh sea-speed-worker "hostname && whoami"
```

Expected non-secret identity evidence:

```text
sea-speed-worker
seaspeedadmin
```

The repository records the intended access target, not current network health. Re-check SSH reachability before a protected task. A changed worker address or route must be diagnosed before editing this document or performing production actions.

## Host-key verification

Use normal SSH host-key verification. Do not use `StrictHostKeyChecking=no` and do not delete a mismatched key merely to make a connection succeed.

For a new or changed path, verify the worker host key through an independent trusted observation before accepting it. When using the fallback localhost tunnel, use a stable host-key alias if needed so the worker identity is not confused with localhost.

## Fallback connection: operator-owned VPS tunnel

Use this only when direct ZeroTier SSH from the Windows control laptop is unavailable.

Open one PowerShell window and run:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:2222:10.123.239.102:22 root@82.146.37.153
```

The operator enters the VPS password locally if password authentication is required. Do not give the VPS password to OpenCode and do not place it in a command, prompt, environment variable, script or log.

**Keep this PowerShell window open while the fallback tunnel is being used.** Closing that window closes the tunnel.

In a separate terminal, OpenCode or the operator may reach the worker through the local tunnel:

```powershell
ssh -p 2222 -o HostKeyAlias=sea-speed-worker -i "$env:USERPROFILE\.ssh\id_ed25519" seaspeedadmin@127.0.0.1 "hostname && whoami"
```

Expected identity remains:

```text
sea-speed-worker
seaspeedadmin
```

The VPS is only a transport bridge in this fallback. OpenCode must not treat the VPS as the worker source store or as implicit authorization to change either VPS or worker production state.

## OpenCode operating model

For approved worker tasks, OpenCode on the Windows laptop should perform the maximum safe remote work automatically through SSH:

- inspect non-secret host, network, service and release state;
- read repository-defined non-secret contracts and scripts available on the worker;
- create temporary diagnostic or preparation helpers under `/tmp` when appropriate;
- syntax-check and checksum helpers before privileged execution;
- run ordinary unprivileged diagnostics directly;
- return sanitized evidence without printing protected environment values.

OpenCode must not ask the operator to manually reproduce routine unprivileged diagnostics that it can perform over the established SSH connection.

## Root and sudo boundary

OpenCode does not receive the sudo password.

When root is genuinely required, the normal pattern is:

1. OpenCode creates one bounded helper or identifies one exact repository-defined command.
2. OpenCode syntax-checks the helper and prints its checksum when applicable.
3. OpenCode stops before privilege escalation.
4. The human operator reviews and runs the exact `sudo ...` command in the worker terminal.
5. The operator enters the sudo password locally.
6. OpenCode may inspect only the resulting sanitized evidence needed for the approved task.

Do not use:

- `sudo -S`;
- passwords in command-line arguments;
- sudoers changes to bypass the operator boundary;
- broad `NOPASSWD` grants;
- OpenCode installation on the production worker solely to obtain root access.

## Secret boundary

Never place these in OpenCode prompts, repository files, command-line arguments, process listings, shell history or reports:

- camera username or password;
- credential-bearing RTSP URLs;
- `SEA_SPEED_API_TOKEN`;
- `HLS_BASIC_AUTH_BASE64`;
- `HLS_MEDIA_BASIC_AUTH_BASE64`;
- `SEA_SPEED_ROI_BASIC_AUTH_BASE64`;
- GitHub tokens;
- private SSH keys;
- full `worker.env` contents;
- sudo or VPS passwords.

Protected values may be consumed by already-approved local files or bounded processes only when the task contract permits it. Report configuration as present/missing or pass/fail rather than printing the value.

## Repository boundary

SSH is for runtime-host diagnostics and approved operations only.

All GitHub repository reads/writes that change durable source state follow Sea Speed governance and use the connected GitHub Connector. Do not use SSH access to the worker as a substitute for repository branch, commit, PR, merge or publication operations.

The worker is not an editable long-term source store.

## Production action boundary

A working SSH session means only that transport is available.

It does not authorize OpenCode to:

- start or stop the production worker;
- restart or enable its systemd service;
- activate a prepared release;
- roll back a release;
- change worker credentials;
- change camera, router, firewall, ZeroTier or VPS configuration.

Those actions require the approval and evidence required by the active task and delivery contracts.

## Which window must stay open?

For the primary direct ZeroTier path, no separate SSH-tunnel PowerShell window is required. OpenCode connects directly to `sea-speed-worker` / `10.123.239.102:22`.

For the fallback VPS tunnel, the PowerShell window running the `ssh -N ... -L 127.0.0.1:2222:...` command must stay open. OpenCode then connects through `127.0.0.1:2222` from another terminal or process.

Prefer direct ZeroTier SSH whenever it is healthy. Keep the VPS tunnel as a fallback rather than a permanent dependency.
