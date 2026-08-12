# Sea Speed Auth v1 operations

Issue: #115

Sea Speed Auth v1 replaces the legacy browser Basic Auth / public camera contour with self-hosted Authentik Forward Auth. This document describes the bounded runtime sequence only; it is not production authorization.

## Final browser boundary

```text
https://mostdef.ru/                         public
https://mostdef.ru/cams                     404/410
https://mostdef.ru/cams/**                  404/410
https://mostdef.ru/sea-speed/**             Authentik required
https://auth.mostdef.ru/                    Authentik login/admin
```

Camera 1 browser playback moves to:

```text
https://mostdef.ru/sea-speed/media/cam1/index.m3u8
```

The camera source, Ubuntu relay, VPS H.264 compatibility output at `127.0.0.1:18889/cam1/`, and AI-independent live behavior do not change.

## Machine-to-machine worker contour

The AI worker must not be sent through interactive browser authentication. The Auth v1 nginx renderer therefore creates a second, private-only listener bound to the VPS ZeroTier/RFC1918 address and restricted to one exact worker ZeroTier peer.

Only these methods and paths exist on that listener:

```text
POST /api/cam1/state
POST /api/cam1/events
GET  /api/cam1/roi
GET  /api/cam1/speed-config
GET  /api/cam1/speed-lines
```

No generic `/api/` proxy is created. The renderer derives the existing FastAPI loopback upstream from the canonical `/sea-speed/api/` nginx location and rejects a non-loopback upstream.

At production cutover, update only the worker runtime environment URLs to the private listener:

```text
SEA_SPEED_API_URL=http://<vps-private-ip>:<port>/api/cam1/state
SEA_SPEED_EVENT_API_URL=http://<vps-private-ip>:<port>/api/cam1/events
SEA_SPEED_ROI_URL=http://<vps-private-ip>:<port>/api/cam1/roi
SEA_SPEED_SPEED_CONFIG_URL=http://<vps-private-ip>:<port>/api/cam1/speed-config
SEA_SPEED_SPEED_LINES_URL=http://<vps-private-ip>:<port>/api/cam1/speed-lines
```

Keep the existing `SEA_SPEED_API_TOKEN`; FastAPI continues to require it for state/event writes. Do not put the token in the command line or issue comments. The private listener is an additional network boundary, not a replacement for the write token.

This is a runtime configuration change only. Auth v1 does not require a Windows/Ubuntu worker source or package change.

## Preconditions for any production work

Require all of the following:

1. Issue #115 source implementation merged to `main`.
2. Exact full 40-character merged `main` SHA identified.
3. Aggregate `quality-integration` successful for that exact SHA.
4. Separate `PRODUCTION APPROVED` bound to that exact SHA and this security envelope.
5. Current nginx site, VPS ZeroTier IP, worker ZeroTier peer IP, SMTP configuration and rollback state freshly discovered.
6. Secrets are available through protected runtime channels without displaying them.

## Phase 1 - Stage Authentik without changing Sea Speed

From the exact merged source, stage `deploy/vps/authentik/` into a root-controlled runtime directory. Copy `env.example` to a protected `.env` and populate independent strong runtime secrets.

Start the compose project. Before changing nginx, prove:

```text
PostgreSQL healthy
Authentik server healthy
Authentik worker healthy
127.0.0.1:9000/-/health/ready/ -> 200
port 9000 is loopback-only
PostgreSQL has no public listener
Docker socket is not mounted into Authentik worker
```

Configure the normal TLS/nginx vhost for `auth.mostdef.ru` to proxy the Authentik server loopback port. Prove the public Authentik ready endpoint and login page before protecting Sea Speed.

## Phase 2 - Identity setup

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

## Phase 3 - Prepare nginx candidate

`deploy/vps/sea-speed-auth-cutover.sh` combines the Camera 1 media migration and Auth v1 boundary.

Example shape only; use freshly discovered private addresses:

```bash
sudo ./deploy/vps/sea-speed-auth-cutover.sh prepare \
  --worker-private-listen <vps-zerotier-ip>:18080 \
  --worker-private-peer <worker-zerotier-ip>
```

The prepare phase:

- proves Authentik and Camera 1 H.264 origins first;
- discovers the active `mostdef.ru` nginx site;
- renders Camera 1 under `/sea-speed/media/cam1/`;
- applies Authentik Forward Auth to every current `/sea-speed/**` nginx location;
- retires all prior `/cams/**` locations;
- creates the narrow private worker listener;
- verifies both renderers;
- writes only a root-protected candidate;
- prints its SHA-256;
- does not replace active nginx configuration or reload nginx.

Record only the non-secret candidate SHA and sanitized evidence.

## Phase 4 - Coordinate worker runtime URLs

The private worker listener and browser Authentik cutover must be coordinated so telemetry does not disappear. Prepare the worker runtime environment update using the five private URLs above. Do not change camera acquisition or AI source code.

Do not point the worker at `https://mostdef.ru/sea-speed/**` after Auth v1; those URLs are intentionally interactive-session protected.

## Phase 5 - Activate exact candidate

Using the exact candidate SHA from `prepare`:

```bash
sudo ./deploy/vps/sea-speed-auth-cutover.sh activate \
  --worker-private-listen <vps-zerotier-ip>:18080 \
  --worker-private-peer <worker-zerotier-ip> \
  --expected-sha256 <prepare-sha256>
```

Activation:

- re-renders the candidate and refuses a SHA mismatch;
- writes a root-only backup of the active nginx site;
- installs only the reviewed candidate;
- runs `nginx -t`;
- reloads only nginx;
- never automatically restores the old public `/cams/**` contour;
- checks anonymous public root/cams/Sea Speed/Camera 1 behavior and Authentik outpost health.

Immediately apply the prepared worker runtime URL update and restart only the worker service needed for those environment changes. Then prove worker state/events and configuration fetches over the private ZeroTier listener.

## Phase 6 - Acceptance

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

Machine checks from the approved worker peer:

- ROI/speed configuration GETs work over the private listener;
- Bearer-authenticated state/events POSTs work;
- other paths/methods do not exist;
- the listener is not bound to a public interface and other peers are denied.

Direct-origin checks from an untrusted Internet host must show no direct access to FastAPI, MediaMTX, H.264 loopback server, Authentik PostgreSQL, Authentik loopback port or Ubuntu private relay.

## Failure and rollback posture

The safe failure mode is a closed/unavailable private service, not anonymous access.

If activation or acceptance fails:

1. stop further rollout steps;
2. preserve sanitized evidence and the root-only backup path;
3. do not automatically restore `/cams/**`;
4. obtain an explicit production rollback decision;
5. if rollback is approved, restore the reviewed previous nginx/runtime configuration and matching worker runtime URLs together;
6. re-run anonymous and authenticated security checks.

Never disclose Authentik secrets, SMTP passwords, TOTP seeds/codes, worker API token, camera credentials or Authorization headers in Issue #115 evidence.
