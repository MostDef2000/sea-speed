# Quickstart: Validate Sea Speed Auth v1

- Specification: `specs/004-sea-speed-auth-v1/spec.md`
- Original Issue: #115
- Runtime topology revision: #122

This is an acceptance guide, not production authorization. Do not mutate production until the exact merged `main` SHA for Issue #122 has a fresh separate `PRODUCTION APPROVED` envelope.

## Source checks

```bash
python -m unittest tests.test_sea_speed_auth_v1
python -m unittest tests.test_frontend_contract
python -m unittest tests.test_camera1_direct_h264_cutover
python -m unittest tests.test_camera1_live_replacement
python scripts/ci/validate_sdd.py
python scripts/ci/validate_repo.py
```

The full PR must also pass the repository aggregate quality gate.

## Canonical runtime topology after Issue #122

```text
Public Internet
  -> VPS nginx/TLS
       -> public /
       -> protected /sea-speed/**
       -> auth.mostdef.ru
            -> worker private Authentik origin over ZeroTier

Ubuntu worker
  -> Authentik Docker HTTP on 127.0.0.1:9000 only
  -> PostgreSQL with no host port
  -> Authentik worker with no Docker socket
  -> source-restricted private proxy on worker ZeroTier IP:19000
       -> accepts only exact VPS private peer
```

The original VPS-local Authentik Compose placement is superseded for production. Public ingress remains only the VPS.

## Fastest-safe worker stage

The normal operator launcher should collect secrets locally and invoke the worker stage once. Repository helper shape:

```bash
sudo deploy/worker/ubuntu/authentik/stage.sh stage \
  --bind-ip <worker-zerotier-ip> \
  --vps-peer <vps-zerotier-ip> \
  --env-file <protected-env-file>
```

The protected env file must be mode `0600` and contain the required Authentik/PostgreSQL/bootstrap/SMTP values. Do not place secrets in argv, chat, Issue comments or logs.

The stage helper must own deterministic work:

```text
expected worker identity/resources
-> Docker Engine + Compose install if absent
-> exact runtime staging
-> PostgreSQL/Auth server/Auth worker start
-> worker-loopback health
-> exact-source private proxy
-> exposure/security checks
```

Success includes:

```text
AUTHENTIK_LOOPBACK_READY=YES
AUTHENTIK_PRIVATE_PROXY=PASS
AUTHENTIK_POSTGRESQL_PUBLIC_PORT=NO
AUTHENTIK_DOCKER_SOCKET_MOUNT=NO
AUTHENTIK_WORKER_STAGE=PASS
AUTHENTIK_PRIVATE_ORIGIN=http://<worker-private-ip>:19000
```

## VPS private Authentik acceptance

Before nginx security cutover, from the VPS prove the exact private worker origin is healthy. The production cutover requires:

```text
--authentik-upstream http://<worker-private-ip>:19000
```

The renderer/cutover must reject public, wildcard, loopback, credential-bearing or path-bearing production origins. The VPS must not silently fall back to `127.0.0.1:9000`.

`auth.mostdef.ru` remains an HTTPS VPS vhost which proxies to the same private worker origin. The worker private origin itself is not a public URL.

## Anonymous acceptance

Expected externally after cutover:

```text
GET /                                      -> 200
GET /cams                                  -> 404/410
GET /cams/                                 -> 404/410
GET /cams/hls/cam1/index.m3u8              -> 404/410
GET /sea-speed/                             -> authentication redirect/deny
GET /sea-speed/api/health                   -> authentication redirect/deny
GET /sea-speed/cameras/                     -> authentication redirect/deny
GET /sea-speed/objects/                     -> authentication redirect/deny
GET /sea-speed/media/cam1/index.m3u8        -> authentication redirect/deny
GET /outpost.goauthentik.io/...             -> Authentik outpost, no recursive auth
```

A request supplying forged `X-authentik-username`, `X-authentik-email`, `X-authentik-groups` or related headers must not gain access or control upstream identity.

## Identity acceptance

1. Owner creates a role-specific invitation with fixed `username=email`, `email=email`, fixed display name, `single_use=true`, and expiry no later than 24 hours.
2. Invitee follows the link and can set only the password fields supplied by the flow.
3. The invitation cannot be reused.
4. Admin/Operator/Viewer can sign in from a second device with email and password.
5. Owner password-only login is rejected; password plus valid TOTP succeeds.
6. Password recovery sends a one-time email recovery path and does not remove Owner TOTP.
7. Disabling a user and revoking sessions prevents continued Sea Speed access.

## Media acceptance

After authenticated login:

```text
/sea-speed/media/cam1/index.m3u8
```

must show advancing Camera 1 H.264 video. The private camera source, Ubuntu relay, VPS H.264 compatibility process and AI-independent live behavior must remain unchanged.

## Worker M2M acceptance

The worker-hosted Authentik private origin does not replace the existing worker M2M route. Discover the exact VPS and worker private/ZeroTier IPv4 addresses at rollout. The nginx candidate must bind the M2M listener only to the VPS private address and `allow` only the exact worker peer.

Change only Sea Speed worker runtime API URLs to the VPS private listener:

```text
SEA_SPEED_API_URL=http://<vps-private-ip>:<port>/api/cam1/state
SEA_SPEED_EVENT_API_URL=http://<vps-private-ip>:<port>/api/cam1/events
SEA_SPEED_ROI_URL=http://<vps-private-ip>:<port>/api/cam1/roi
SEA_SPEED_SPEED_CONFIG_URL=http://<vps-private-ip>:<port>/api/cam1/speed-config
SEA_SPEED_SPEED_LINES_URL=http://<vps-private-ip>:<port>/api/cam1/speed-lines
```

Keep the existing `SEA_SPEED_API_TOKEN` private and unchanged unless a separate credential-rotation decision is made.

From the approved worker peer prove:

```text
POST /api/cam1/state         -> succeeds with existing Bearer token
POST /api/cam1/events        -> succeeds with existing Bearer token
GET  /api/cam1/roi           -> succeeds
GET  /api/cam1/speed-config  -> succeeds
GET  /api/cam1/speed-lines   -> succeeds
```

Also prove an unrelated path, wrong method and non-approved peer do not gain access. There must be no generic private `/api/**` proxy.

## Deployment health acceptance

After `sea-speed-api` restart, application health is proven locally on VPS:

```text
http://127.0.0.1:8000/api/health -> healthy
```

Identity health is separately proven:

```text
VPS -> http://<worker-private-ip>:19000/-/health/ready/ -> healthy
Internet -> https://auth.mostdef.ru/-/health/ready/     -> healthy through VPS TLS
```

The public `https://mostdef.ru/sea-speed/api/health` URL is an authentication-boundary smoke check after Auth v1, not the service health proof.

## Network acceptance

From an untrusted Internet host verify no direct access to FastAPI origin ports, MediaMTX, Camera 1 loopback HLS origin, Authentik PostgreSQL, worker Authentik loopback HTTP, worker private Authentik proxy or Ubuntu private camera relay. Public ingress remains VPS nginx HTTPS for `mostdef.ru` and `auth.mostdef.ru`.

From an unapproved ZeroTier/private peer, the worker Authentik private proxy must reject the connection. From the exact VPS peer, it must work.

## Failure posture

Stop/interrupt the worker private Authentik path and prove `/sea-speed/**` fails closed rather than becoming anonymous. The public `/` page should remain available. Do not automatically restore the retired `/cams/**` camera route or move Authentik back to the undersized VPS. Any rollback requires an explicit production rollback decision.
