# Sea Speed Authentik runtime on Ubuntu worker

Issues: #115, #122, #152

This directory is the canonical production runtime placement for Sea Speed Auth v1 after Issue #122. Authentik and PostgreSQL run on the commissioned Ubuntu worker; the public VPS remains the nginx/TLS/Sea Speed ingress.

## Topology

```text
Internet
  -> VPS nginx :443
       -> auth.mostdef.ru / Forward Auth / embedded outpost
            -> ZeroTier private origin on Ubuntu worker
                 -> source-restricted socat proxy
                      -> 127.0.0.1:9000
                           -> Authentik Docker server

Ubuntu worker Docker:
  Authentik server -> loopback host publish only
  Authentik worker -> no Docker socket
  PostgreSQL       -> no host port
```

The worker private Authentik origin is not a public service. `stage.sh` binds the proxy to one literal worker RFC1918/ZeroTier IPv4 and allows only one literal VPS peer through socat's `range=<vps-ip>/32` listener option. The Docker server itself remains published only on worker loopback.

`deploy/vps/authentik/**` contains the original Issue #115 VPS-local runtime material. After Issue #122 its Compose placement is superseded and must not be used for production staging. Authentik blueprint source remains repository-owned under `deploy/vps/authentik/blueprints/**`; worker operations consume those exact reviewed files.

## Runtime layout

Default worker runtime root:

```text
/opt/sea-speed-auth/
  compose.yml
  .env
  blueprints/sea-speed-auth-v1.yaml
  data/
  certs/
  custom-templates/
```

The populated `.env` is a runtime secret file. Keep it mode `0600` and never print or commit it.

## Initial Authentik stage

The initial runtime stage is owned by `stage.sh`. Run it only from an exact reviewed repository source inside an approved production envelope:

```text
sudo bash deploy/worker/ubuntu/authentik/stage.sh stage \
  --bind-ip <worker-zerotier-ip> \
  --vps-peer <vps-zerotier-ip> \
  --env-file <protected-runtime-env-file>
```

`stage.sh` performs the deterministic work itself:

- verifies `sea-speed-worker`, private addresses, CPU, memory and disk;
- validates the secret env file without printing values;
- installs Docker Engine + Compose plugin from Docker's official APT repository when Docker is absent;
- installs `socat` when needed;
- stages exact Compose/identity-blueprint/runtime files under `/opt/sea-speed-auth`;
- starts PostgreSQL, Authentik server and Authentik worker;
- proves Authentik healthy on worker loopback;
- installs and starts `sea-speed-auth-private-proxy.service` bound only to the worker private IP and exact VPS source;
- proves PostgreSQL has no host port and Authentik containers have no Docker socket mount.

A successful stage prints `AUTHENTIK_WORKER_STAGE=PASS` and the non-secret `AUTHENTIK_PRIVATE_ORIGIN=http://<worker-private-ip>:19000` used by the later VPS nginx cutover.

The script does not configure Owner/TOTP enrollment, SMTP acceptance, the Forward Auth provider/application, or VPS nginx cutover. Those remain separate protected operations/checkpoints.

## Sea Speed logout-flow operation

Issue #152 changes only the invalidation flow assigned to the existing `Provider for Sea Speed`. The repo-owned operation is:

```text
sudo bash deploy/worker/ubuntu/authentik/apply-logout-flow.sh apply --source-sha <exact-approved-40-char-sha>
```

The corresponding bounded rollback is:

```text
sudo bash deploy/worker/ubuntu/authentik/apply-logout-flow.sh rollback --source-sha <same-approved-40-char-sha>
```

Normal operator handoff does not require downloading this script to the control laptop. The server-pull bootstrap retrieves the exact approved repository SHA on the Ubuntu worker and invokes this entrypoint from that target-local source.

`apply-logout-flow.sh` deliberately does not change Compose topology or persist another bind mount. It:

- verifies root execution, `sea-speed-worker`, exact source-SHA syntax, the existing runtime and all three running Authentik/PostgreSQL containers;
- verifies Authentik loopback readiness before mutation;
- reads only the current non-secret provider invalidation-flow slug through Authentik's own Django shell;
- fails closed if the provider is bound to anything other than the known previous `default-provider-invalidation-flow` or Issue #152 target `sea-speed-provider-invalidation`;
- copies the exact repository-owned apply or rollback blueprint into a temporary hidden path inside Authentik's configured `/blueprints` directory;
- invokes Authentik's native `ak apply_blueprint` command synchronously;
- verifies the actual provider assignment after apply;
- automatically attempts the repository-owned rollback blueprint if apply reports success but the target assignment is not observable;
- verifies server/worker/PostgreSQL container identities did not change and Authentik remains ready;
- removes the temporary container-side blueprint and prints only sanitized source/runtime evidence.

The apply source is `deploy/vps/authentik/blueprints/sea-speed-logout-v1.yaml`. The rollback source is `deploy/vps/authentik/blueprints/sea-speed-logout-rollback-v1.yaml`, which restores only `Provider for Sea Speed` to `default-provider-invalidation-flow`; it does not modify that global default flow.

The operation does not read, copy or print `.env`, passwords, TOTP material, API tokens, browser cookies or SSH keys.

## Safety boundaries

- Mutating worker operations require a separately approved exact-SHA production envelope; repository scripts do not grant authorization.
- Authentik/PostgreSQL are not exposed on the worker public interfaces.
- The VPS is the only approved peer for the private Authentik proxy.
- The embedded Authentik outpost remains in-process; no Docker socket is mounted.
- Existing Sea Speed worker application, camera relay, AI behavior and API token are not changed by this runtime.
- If worker/Auth/ZeroTier is unavailable, VPS `/sea-speed/**` must fail closed; it must never fall back to anonymous access.
