# Sea Speed Auth v1 operations

Original Issue: #115  
Runtime topology revision: #122

Sea Speed Auth v1 replaces the legacy browser Basic Auth / public camera contour with self-hosted Authentik Forward Auth. Issue #122 relocates the Authentik and PostgreSQL runtime from the undersized public VPS to the commissioned Ubuntu worker. This document describes the bounded runtime sequence only; it is not production authorization.

## Final browser boundary

```text
https://mostdef.ru/                         public
https://mostdef.ru/cams                     404/410
https://mostdef.ru/cams/**                  404/410
https://mostdef.ru/sea-speed/**             Authentik required
https://auth.mostdef.ru/                    Authentik login/admin via VPS HTTPS
```

Camera 1 browser playback remains:

```text
https://mostdef.ru/sea-speed/media/cam1/index.m3u8
```

The camera source, Ubuntu relay, VPS H.264 compatibility output at `127.0.0.1:18889/cam1/`, and AI-independent live behavior do not change.

## Identity runtime topology after Issue #122

```text
Internet
  -> VPS 82.146.37.153 nginx/TLS
       -> auth.mostdef.ru
       -> /outpost.goauthentik.io/**
       -> auth_request for /sea-speed/**
            |
            | ZeroTier/private HTTP
            v
       Ubuntu worker sea-speed-worker
            -> source-restricted private proxy
                 -> 127.0.0.1:9000
                      -> Authentik server

Ubuntu worker Docker Compose:
  PostgreSQL 16       -> no host port
  Authentik server    -> host publish 127.0.0.1:9000 only
  Authentik worker    -> no Docker socket mount
```

The private Authentik proxy binds one literal worker RFC1918/ZeroTier IPv4 and accepts only the exact VPS private peer. It must not bind `0.0.0.0`, a public address, or a network-wide source range. Public browser access to Authentik remains through the VPS HTTPS vhost only.

The original `deploy/vps/authentik/**` Compose placement is superseded for production after Issue #122. The identity blueprint at `deploy/vps/authentik/blueprints/sea-speed-auth-v1.yaml` remains the canonical policy definition and is copied into the worker runtime by the worker stage helper.

## Machine-to-machine worker contour remains separate

The AI worker must not be sent through interactive browser authentication. The Auth v1 nginx renderer creates a second, private-only listener on the VPS, bound to the VPS private address and restricted to the exact worker peer.

Only these methods and paths exist on that VPS listener:

```text
POST /api/cam1/state
POST /api/cam1/events
GET  /api/cam1/roi
GET  /api/cam1/speed-config
GET  /api/cam1/speed-lines
```

No generic `/api/` proxy is created. The renderer derives the existing FastAPI loopback upstream from the canonical `/sea-speed/api/` nginx location and rejects a non-loopback upstream.

At production cutover, update only the Sea Speed worker runtime environment URLs to the private VPS listener:

```text
SEA_SPEED_API_URL=http://<vps-private-ip>:<port>/api/cam1/state
SEA_SPEED_EVENT_API_URL=http://<vps-private-ip>:<port>/api/cam1/events
SEA_SPEED_ROI_URL=http://<vps-private-ip>:<port>/api/cam1/roi
SEA_SPEED_SPEED_CONFIG_URL=http://<vps-private-ip>:<port>/api/cam1/speed-config
SEA_SPEED_SPEED_LINES_URL=http://<vps-private-ip>:<port>/api/cam1/speed-lines
```

Keep the existing `SEA_SPEED_API_TOKEN`; FastAPI continues to require it for state/event writes. Do not put the token in command lines, chat, Issue comments or logs. Hosting Authentik on the same physical worker does not merge the identity and M2M security contours.

## Preconditions for any revised production work

Require all of the following:

1. Issue #122 source implementation is merged to `main`.
2. The new exact full 40-character merged `main` SHA is identified.
3. Aggregate `quality-integration` succeeds for that exact SHA.
4. A fresh `PRODUCTION APPROVED <exact-sha>` is recorded for the revised worker+VPS topology. The older approval for `bf6c117635070c01565c2b4b180099487ded052a` does not authorize this topology.
5. Current nginx site, worker private/ZeroTier IP, VPS private/ZeroTier peer IP, VPS worker-M2M listen IP, SMTP configuration and rollback state are freshly discovered.
6. Secrets are available through protected runtime channels without displaying them.
7. The worker identity is `sea-speed-worker` and satisfies the Authentik resource floor before mutation.

## Phase 1 - One-stage Authentik deployment on the worker

The normal operator path should use one launcher command. The launcher may connect to the worker directly over ZeroTier or through the VPS SSH jump when the operator workstation lacks a direct route.

The repository helper is:

```bash
sudo deploy/worker/ubuntu/authentik/stage.sh stage \
  --bind-ip <worker-zerotier-ip> \
  --vps-peer <vps-zerotier-ip> \
  --env-file <protected-runtime-env-file>
```

The env file must be created locally on the worker with mode `0600`. Populate it from `deploy/worker/ubuntu/authentik/env.example` using protected local input. Never pass PostgreSQL, Authentik, Owner bootstrap or SMTP secrets in argv.

The stage helper performs deterministic work itself:

- verifies hostname `sea-speed-worker`;
- validates exact private worker/VPS addresses;
- verifies CPU, RAM and free disk;
- validates required env values without printing them;
- installs Docker Engine and the Compose plugin from the official Docker APT repository when Docker is absent;
- refuses to remove conflicting Docker/containerd packages automatically;
- installs `socat` when required;
- stages the exact Compose, blueprint and runtime directories under `/opt/sea-speed-auth`;
- starts PostgreSQL, Authentik server and Authentik worker;
- proves `127.0.0.1:9000/-/health/ready/` on the worker;
- creates `sea-speed-auth-private-proxy.service` bound only to the worker private IP and source-restricted to the exact VPS peer;
- proves PostgreSQL has no host port and the Authentik containers have no Docker socket mount.

Successful stage evidence includes:

```text
AUTHENTIK_LOOPBACK_READY=YES
AUTHENTIK_PRIVATE_PROXY=PASS
AUTHENTIK_POSTGRESQL_PUBLIC_PORT=NO
AUTHENTIK_DOCKER_SOCKET_MOUNT=NO
AUTHENTIK_WORKER_STAGE=PASS
AUTHENTIK_PRIVATE_ORIGIN=http://<worker-private-ip>:19000
```

Record the non-secret private origin. Do not record `.env` content.

## Phase 2 - Connect the VPS to the worker identity origin

Before changing the Sea Speed security boundary, prove from the VPS:

```text
http://<worker-private-ip>:19000/-/health/ready/ -> 200
```

Configure the existing VPS TLS/nginx vhost for `auth.mostdef.ru` to proxy to that exact private origin, not to VPS loopback. Then prove:

```text
https://auth.mostdef.ru/-/health/ready/ -> 200
```

The worker private origin itself is not a public URL and must reject traffic from an unapproved private peer.

The VPS Auth v1 renderer/cutover receives the exact origin through:

```text
--authentik-upstream http://<worker-private-ip>:19000
```

Production cutover rejects loopback, public, credential-bearing, path-bearing or non-literal upstream values.

## Phase 3 - Identity setup

The `sea-speed-auth-v1.yaml` blueprint defines:

- `Sea Speed Owner` (Authentik superuser group);
- `Sea Speed Admin`;
- `Sea Speed Operator`;
- `Sea Speed Viewer`;
- strong password policy;
- three role-specific invite-only enrollment flows;
- Sea Speed authentication flow;
- Owner-only TOTP validation;
- Sea Speed application-access policy.

Configure the initial Owner from trusted administration. The Owner must have a working TOTP device before the Sea Speed application is cut over.

Create a Forward Auth single-application provider for `https://mostdef.ru/sea-speed/`, attach application `Sea Speed`, bind `sea-speed-application-access`, and attach it to `authentik Embedded Outpost`.

Prove before cutover:

- password-only Owner login fails;
- Owner password + TOTP succeeds;
- one role invitation is single-use and creates the intended group member;
- the invitation email/username is fixed by the Owner;
- password recovery works and does not remove Owner TOTP;
- disabling a test user and revoking sessions stops access.

## Phase 4 - Prepare the VPS nginx candidate

`deploy/vps/sea-speed-auth-cutover.sh` combines the Camera 1 media migration, Auth v1 browser boundary and private worker M2M listener.

Example shape only; use freshly discovered private addresses:

```bash
sudo ./deploy/vps/sea-speed-auth-cutover.sh prepare \
  --authentik-upstream http://<worker-private-ip>:19000 \
  --worker-private-listen <vps-private-ip>:18080 \
  --worker-private-peer <worker-private-ip>
```

The prepare phase:

- proves the private worker Authentik origin and public `auth.mostdef.ru` health first;
- proves Camera 1 H.264 origin;
- discovers the active `mostdef.ru` nginx site;
- renders Camera 1 under `/sea-speed/media/cam1/`;
- applies Authentik Forward Auth to every current `/sea-speed/**` nginx location;
- routes the embedded outpost to the exact worker private Authentik origin;
- retires all prior `/cams/**` locations;
- creates the narrow private worker M2M listener on the VPS;
- verifies both renderers;
- writes only a root-protected candidate;
- prints its SHA-256;
- does not replace active nginx configuration or reload nginx.

Record only the non-secret candidate SHA and sanitized evidence.

## Phase 5 - Coordinate Sea Speed worker M2M URLs

The private VPS M2M listener and browser Authentik cutover must be coordinated so telemetry does not disappear. Prepare the worker runtime environment update using the five private VPS URLs above. Do not change camera acquisition or AI source code.

Do not point the Sea Speed worker at `https://mostdef.ru/sea-speed/**` after Auth v1; those URLs are intentionally interactive-session protected.

## Phase 6 - Activate the exact candidate

Using the exact candidate SHA from `prepare` and the same exact worker private Authentik origin:

```bash
sudo ./deploy/vps/sea-speed-auth-cutover.sh activate \
  --authentik-upstream http://<worker-private-ip>:19000 \
  --worker-private-listen <vps-private-ip>:18080 \
  --worker-private-peer <worker-private-ip> \
  --expected-sha256 <prepare-sha256>
```

Activation:

- re-renders the candidate and refuses a SHA mismatch;
- refuses a changed Authentik private origin;
- writes a root-only backup of the active nginx site;
- installs only the reviewed candidate;
- runs `nginx -t`;
- reloads only nginx;
- never automatically restores the old public `/cams/**` contour;
- checks anonymous public root/cams/Sea Speed/Camera 1 behavior and Authentik outpost health.

Immediately apply the prepared Sea Speed worker runtime URL update and restart only the Sea Speed worker service required for those environment changes. Then prove state/events and configuration fetches over the private VPS listener.

## Phase 7 - Acceptance

Anonymous Internet checks:

```text
/                                      -> 200
/cams/                                 -> 404/410
/cams/hls/cam1/index.m3u8              -> 404/410
/sea-speed/                            -> Authentik redirect/deny
/sea-speed/api/health                  -> Authentik redirect/deny
/sea-speed/media/cam1/index.m3u8       -> Authentik redirect/deny
```

Authenticated checks:

- Owner requires TOTP;
- Admin/Operator/Viewer login with email/password;
- `/sea-speed/`, Cameras and Objects load;
- Camera 1 H.264 video advances;
- snapshots and API GETs work;
- browser mutations work through the same session boundary.

Identity network checks:

- VPS -> worker private Authentik health succeeds;
- an unapproved private/ZeroTier peer cannot use the worker private Authentik proxy;
- Authentik server Docker publish remains worker loopback only;
- PostgreSQL has no worker host port;
- worker private Authentik proxy is not publicly reachable.

Machine checks from the approved Sea Speed worker peer:

- ROI/speed configuration GETs work over the private VPS M2M listener;
- Bearer-authenticated state/events POSTs work;
- other paths/methods do not exist;
- the VPS M2M listener is not bound to a public interface and other peers are denied.

Direct-origin checks from an untrusted Internet host must show no direct access to FastAPI, MediaMTX, H.264 loopback server, Authentik PostgreSQL, worker Authentik loopback HTTP, worker private Authentik proxy or Ubuntu camera relay.

## Fail-closed dependency test

After all normal acceptance passes, perform a controlled failure test inside the approved production envelope:

1. interrupt the worker Authentik private path without changing nginx authentication rules;
2. verify `/sea-speed/**` becomes unavailable/denied and never anonymous;
3. verify public `/` remains available;
4. restore the worker Authentik private path;
5. verify authenticated Sea Speed recovers.

Do not use this test to stop camera relay or Sea Speed worker application services.

## Failure and rollback posture

The fail-closed safety posture is a closed/unavailable private service, not anonymous access.

If staging, activation or acceptance fails:

1. stop further rollout steps;
2. preserve sanitized evidence and known backup/runtime paths;
3. do not automatically restore `/cams/**`;
4. do not silently move Authentik back to the undersized VPS;
5. obtain an explicit production rollback decision;
6. if rollback is approved, restore the reviewed matching nginx/auth topology and Sea Speed worker runtime URLs together;
7. re-run anonymous, authenticated and private-network security checks.

Never disclose Authentik secrets, SMTP passwords, TOTP seeds/codes, worker API token, camera credentials or Authorization headers in Issue #122/#115 evidence.
