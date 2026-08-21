# Ubuntu Zero-Touch Production Deployment

Status: Bootstrap required after source integration
Canonical Issue: #234

## Goal

After one independent administrative bootstrap, ordinary accepted Ubuntu releases require zero operator commands:

```text
protected main Quality
-> standing policy allow
-> GitHub-hosted runner
-> VPS ProxyJump
-> ZeroTier
-> restricted sea-speed-deploy account
-> exact gate
-> deploy-authorized.sh
-> runtime_verified manifest
-> typed execution audit
```

The VPS is only a network/SSH jump host. It does not authorize Ubuntu mutation.

## Why not a self-hosted production runner

The production Worker remains a bounded runtime host, not a general GitHub Actions executor. A persistent general-purpose runner would enlarge the code-execution surface and privilege blast radius. The zero-touch path instead exposes one forced command with one narrowly-scoped root gate.

## Independent prerequisites

Before enabling zero-touch production, the repository owner/admin must establish these settings outside repository writes:

1. Repository visibility is `public` while Sea Speed uses GitHub Free.
2. `main` branch/ruleset requires PRs and the merge-facing check `quality-integration` (Quality integration gate); force push/delete and silent bypass are disabled.
3. GitHub `production` environment still contains the standing delegation `SEA_SPEED_PRODUCTION_DELEGATION_V1` and has no per-release required reviewer.
4. Existing VPS deployment credentials remain available to the `production` environment.
5. A new dedicated Ed25519 Worker deploy key exists. The private key is stored only as `production` environment secret `UBUNTU_DEPLOY_SSH_PRIVATE_KEY`.
6. The independently verified Worker SSH host key line is stored only as `production` environment secret `UBUNTU_DEPLOY_SSH_KNOWN_HOSTS`.

Do not paste a private key into Issue/PR/chat or commit it to Git.

## Worker bootstrap

Run the repository-owned bootstrap once as root from an exact checkout that contains Issue #234 implementation:

```text
scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh --public-key-file <operator-local-public-key-file> --expected-fingerprint <verified-SHA256-fingerprint>
```

The script:

- creates the dedicated system account `sea-speed-deploy` if absent;
- disables password authentication with a non-locking invalid password marker so OpenSSH public-key authentication remains possible;
- installs root-owned `/usr/local/sbin/sea-speed-ubuntu-zero-touch-gate` mode `0755`;
- writes one `authorized_keys` record using OpenSSH `restrict` and a forced command;
- writes one sudoers rule allowing only the same gate in `--execute` mode;
- validates the sudoers file with `visudo`;
- if the commissioned Worker uses the canonical global `AllowUsers` hardening line in `/etc/ssh/sshd_config.d/00-sea-speed-hardening.conf`, preserves every existing principal and adds only `sea-speed-deploy`;
- validates the resulting SSH configuration with `sshd -t`, reloads the active SSH service, verifies the effective `AllowUsers` policy, and restores the original hardening file if validation/reload/effective-policy verification fails;
- reports only public key/host fingerprints and non-secret boundary state.

The deploy account MUST NOT be password-locked during active zero-touch service. On Linux a leading `!` in the shadow password field causes sshd to reject the account before public-key authentication. Password login remains impossible because the active bootstrap uses the non-locking invalid password marker `*NP*`; the deploy key is still constrained by `restrict` plus the forced command.

The commissioned Worker also has a global SSH allowlist. A valid deploy key is still rejected before `authorized_keys` when `AllowUsers` contains only `seaspeedadmin`. Bootstrap therefore treats allowlist membership as part of the same bounded transport boundary. It does not replace the allowlist with a deploy-only list and does not remove operator access; it adds exactly `sea-speed-deploy` alongside the existing principals. If an effective allowlist is configured somewhere other than the canonical hardening file, bootstrap fails closed instead of editing an unknown SSH policy source.

It never creates or prints a private key.

Rollback of the transport boundary uses:

```text
scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh --remove
```

Removal deletes the dedicated authorized key and sudo rule, removes only `sea-speed-deploy` from the canonical `AllowUsers` line when present, validates/reloads sshd, and then locks the account. Existing operator principals remain unchanged. It does not change application runtime state.

## Forced-command protocol

The GitHub workflow sends exactly:

```text
sea-speed-ubuntu-deploy-v1 <40-character-main-sha> <canonical-issue> <ubuntu-artifact-sha256>
```

OpenSSH `restrict` disables forwarding/PTY/agent/X11/user-rc capabilities. The gate rejects any other command form.

Root execution then:

1. fetches public `origin/main` into a root-only temporary directory;
2. proves the requested SHA is on current main first-parent history;
3. checks out that exact SHA;
4. rebuilds the deterministic exact Ubuntu artifact digest and requires it to equal the workflow-provided digest;
5. invokes only `deploy/worker/ubuntu/deploy-authorized.sh` with exact SHA, canonical Issue and artifact digest;
6. validates the resulting deployment manifest and returns only that JSON on stdout.

Target deployment/rollback semantics remain owned by `deploy-authorized.sh`; the transport gate does not reimplement product mutation logic.

## GitHub workflow transport

`.github/workflows/deploy-ubuntu-worker.yml` requires all of:

- `UBUNTU_DEPLOY_SSH_PRIVATE_KEY` secret;
- `UBUNTU_DEPLOY_SSH_KNOWN_HOSTS` secret;
- existing `VPS_SSH_PRIVATE_KEY` and `VPS_SSH_KNOWN_HOSTS`;
- existing `VPS_HOST` and `VPS_USER`;
- optional `VPS_SSH_PORT`, default `22`.

The worker address/user are fixed non-secret topology values: `10.123.239.102:22`, `sea-speed-deploy`.

The workflow uses `StrictHostKeyChecking yes`, separate known-host files, `ProxyJump sea-speed-vps-jump`, `RequestTTY no`, `ForwardAgent no` and `ClearAllForwardings yes`.

Missing transport credentials fail closed before SSH. There is no recurring one-command fallback in the steady-state workflow.

## Source protection

`scripts/release/verify_source_protection.py` is a hard gate in the autonomous router and both protected deployment workflows. It requires:

- repository visibility `public`;
- `main.protected=true`;
- required check context `quality-integration` (Quality integration gate).

Repository settings must additionally require PRs and disable force-push/delete/bypass paths. Those settings remain independently administered and are not writable by the Delivery Orchestrator.

## Acceptance

Zero-touch is active only when:

- GitHub reports public protected main with required checks;
- the production environment standing delegation remains valid;
- the deploy account is SSH-accessible by the dedicated public key while password authentication remains impossible;
- effective sshd policy admits both the existing operator principal(s) and `sea-speed-deploy` when `AllowUsers` is configured;
- the restricted Worker key cannot open a shell/PTY or forwarding channel;
- malformed SHA/Issue/hash and arbitrary commands are rejected;
- an exact policy-allowed Ubuntu release traverses VPS ProxyJump, reaches `runtime_verified`, and creates a typed execution audit;
- `Operator actions expected: 0` for subsequent ordinary releases.

After activation, Issue #231 may be retried through the current protected Ubuntu workflow using its exact main release SHA to prove the Authentik 30-day session change without another manual server command.
