# Sea Speed Authentik runtime on Ubuntu worker

Issues: #115, #122

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

`deploy/vps/authentik/**` contains the original Issue #115 VPS-local runtime material. After Issue #122 its Compose placement is superseded and must not be used for production staging. The existing `sea-speed-auth-v1.yaml` blueprint remains canonical identity policy source and is copied by `stage.sh` into the worker runtime directory.

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

## Fastest safe stage

The normal operator path is one launcher stage. The launcher should collect secrets locally, create a temporary protected env file on the worker, then invoke:

```text
sudo deploy/worker/ubuntu/authentik/stage.sh stage \
  --bind-ip <worker-zerotier-ip> \
  --vps-peer <vps-zerotier-ip> \
  --env-file <protected-runtime-env-file>
```

`stage.sh` performs the deterministic work itself:

- verifies `sea-speed-worker`, private addresses, CPU, memory and disk;
- validates the secret env file without printing values;
- installs Docker Engine + Compose plugin from Docker's official APT repository when Docker is absent;
- installs `socat` when needed;
- stages exact Compose/blueprint/runtime files under `/opt/sea-speed-auth`;
- starts PostgreSQL, Authentik server and Authentik worker;
- proves Authentik healthy on worker loopback;
- installs and starts `sea-speed-auth-private-proxy.service` bound only to the worker private IP and exact VPS source;
- proves PostgreSQL has no host port and Authentik containers have no Docker socket mount.

A successful stage prints `AUTHENTIK_WORKER_STAGE=PASS` and the non-secret `AUTHENTIK_PRIVATE_ORIGIN=http://<worker-private-ip>:19000` used by the later VPS nginx cutover.

The script does not configure the Owner, TOTP, SMTP provider acceptance, Forward Auth provider/application or VPS nginx cutover. Those are separate human/security checkpoints.

## Safety boundaries

- Mutating `stage` requires a separately approved exact-SHA production envelope; the script does not grant authorization.
- Authentik/PostgreSQL are not exposed on the worker public interfaces.
- The VPS is the only approved peer for the private Authentik proxy.
- The embedded Authentik outpost remains in-process; no Docker socket is mounted.
- Existing Sea Speed worker application, camera relay, AI behavior and API token are not changed by this runtime.
- If worker/Auth/ZeroTier is unavailable, VPS `/sea-speed/**` must fail closed; it must never fall back to anonymous access.
