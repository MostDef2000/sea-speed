# Implementation Plan: Sea Speed Auth v1

- Specification: `specs/004-sea-speed-auth-v1/spec.md`
- Issue: #115
- Runtime topology revision: #122
- Status: Implementing worker-hosted Authentik revision

## Architecture

```text
Internet
  |
  +-- https://mostdef.ru/ -------------------------- public landing page
  |
  +-- https://auth.mostdef.ru/ --------------------- VPS nginx/TLS
  |                                                     |
  |                                                     +-- ZeroTier/private HTTP
  |                                                          -> worker private proxy
  |                                                               -> 127.0.0.1:9000
  |                                                                    -> Authentik
  |
  +-- https://mostdef.ru/cams/** ------------------- 404, no media
  |
  +-- https://mostdef.ru/sea-speed/**
          |
          +-- VPS nginx auth_request
          |      -> same exact worker private Authentik/outpost origin
          |
          +-- authenticated static UI
          +-- authenticated FastAPI proxy
          +-- authenticated snapshots/media
          +-- authenticated Camera 1 HLS
```

Worker identity runtime:

```text
Ubuntu worker sea-speed-worker
  Docker Compose
    PostgreSQL 16 ------------ no host port
    Authentik server --------- 127.0.0.1:9000 only
    Authentik worker --------- no Docker socket

  sea-speed-auth-private-proxy.service
    bind: literal worker ZeroTier/RFC1918 IP:19000
    source allow: exact VPS private peer /32
    target: 127.0.0.1:9000
```

Camera acquisition remains independent of identity:

```text
physical Camera 1
-> Ubuntu private RTSP relay
-> VPS H.264 compatibility process
-> 127.0.0.1:18889/cam1/
-> nginx protected /sea-speed/media/cam1/
-> authenticated browser
```

Existing worker machine-to-machine API traffic remains a distinct contour:

```text
approved worker ZeroTier peer
-> VPS literal private IP:private port
-> exact nginx method/path allowlist
-> existing loopback FastAPI origin

POST state/events still require existing SEA_SPEED_API_TOKEN
GET ROI/speed configuration remains private-peer-only
```

The Authentik private origin and the worker M2M listener are separate flows in opposite directions and must not be conflated.

## Decisions

### D-001 - Authentik owns identity

Sea Speed does not implement password hashing, enrollment, recovery, MFA or browser sessions. Authentik remains the identity provider.

### D-002 - Invite-only enrollment

There is no public sign-up or access-request page. Role-specific enrollment flows require a valid invitation. The Owner creates a single-use invitation with a 24-hour default lifetime and fixed `username`, `email` and `name`; `username` and `email` use the same email value. The user supplies only the password.

Separate Admin, Operator and Viewer enrollment flows make group assignment deterministic. Owner enrollment is not public; the initial Owner is bootstrapped administratively.

### D-003 - Owner-only TOTP

The normal authentication flow is identification -> password -> login. A TOTP validation stage is conditionally executed only for the `Sea Speed Owner` group. The stage accepts only TOTP and denies an Owner who has no configured TOTP. Admin, Operator and Viewer skip the MFA stage in v1.

### D-004 - Password and recovery model

Enrollment password prompts use a shared password policy: minimum 15 characters, no composition counters, zxcvbn enabled and Have I Been Pwned checking enabled. Email delivery is configured through runtime-only Authentik SMTP environment variables. Password recovery uses Authentik's recovery capability; changing an Owner password does not remove the independently configured Owner TOTP device.

### D-005 - One authenticated browser namespace

Every browser-facing Sea Speed resource is under `/sea-speed/**` and passes the same nginx forward-auth boundary. This includes API GETs, mutating browser calls, camera snapshots, camera-preview HLS and Camera 1 live HLS. Client-provided `X-authentik-*` identity headers are replaced with values returned by the Authentik auth subrequest.

### D-006 - Retire `/cams/**`

The earlier public Camera 1 URL is intentionally superseded. Existing nginx `/cams...` locations are removed by the bounded renderer and replaced with a deny/not-found contour. Standalone public Camera 1 nginx activation remains retired.

### D-007 - Fail closed across the private Authentik dependency

If Authentik, the worker private proxy, or the ZeroTier path is unavailable, `/sea-speed/**` is not served anonymously. `/outpost.goauthentik.io/**` remains the forward-auth callback/start contour, but its upstream is the exact private worker origin. `/` remains public and independent.

### D-008 - Embedded outpost and no Docker socket

The deployment uses Authentik's embedded outpost for nginx forward auth. The Authentik worker container is not given the Docker socket because v1 does not require Authentik-managed external outpost containers.

### D-009 - Reproducible nginx change

Nginx security policy is rendered and verified from repository tooling before activation. The renderer accepts an explicit Authentik upstream; production cutover rejects loopback/public/credential-bearing/path-bearing origins and binds candidate identity to the exact private worker origin. The activation script creates a root-only backup, runs `nginx -t`, reloads only nginx and performs no automatic rollback to the legacy public camera contour. `prepare` writes a protected candidate and returns its SHA-256; `activate` re-renders and refuses a SHA mismatch.

### D-010 - Deployment health is not public bypass

The normal VPS code deploy does not depend on anonymous success from `/sea-speed/api/health`. FastAPI health is checked through the loopback origin at `http://127.0.0.1:8000/api/health`. Authentik health for the revised topology is separately proven from the VPS against the private worker origin and through `https://auth.mostdef.ru/`.

### D-011 - Separate worker M2M ingress from browser auth

The worker is infrastructure, not an interactive user. The nginx renderer still derives the FastAPI loopback origin from the existing `/sea-speed/api/` proxy and creates a private M2M listener only when supplied an exact private VPS `IP:PORT` and exact private worker peer IP.

The listener exposes only:

- POST `/api/cam1/state`;
- POST `/api/cam1/events`;
- GET `/api/cam1/roi`;
- GET `/api/cam1/speed-config`;
- GET `/api/cam1/speed-lines`.

All other paths/methods are absent or denied. State/event writes keep the existing FastAPI Bearer-token check. Production changes only worker runtime endpoint environment variables; Sea Speed worker source/package, AI behavior and camera acquisition do not change.

### D-012 - Relocate identity runtime to Ubuntu worker

Issue #122 supersedes the original VPS-local Authentik Compose placement because production preflight proved the VPS has fewer than two CPU cores and the operator will not resize it. Fresh runtime evidence shows `sea-speed-worker` has 16 CPU, 30 GiB RAM and sufficient disk.

The canonical production placement is now `deploy/worker/ubuntu/authentik/**`. Authentik Docker HTTP remains worker-loopback-only. A separate `socat` systemd proxy binds to one literal worker private IP and restricts incoming source to the exact VPS private peer. This keeps Docker's host publish off the ZeroTier interface and avoids a wildcard/private-network-wide Authentik listener.

The original `deploy/vps/authentik/**` Compose placement is historical/superseded for production after #122. Its existing identity blueprint remains the canonical policy definition and is copied into the worker runtime by the worker stage helper.

### D-013 - Fastest safe worker stage

`deploy/worker/ubuntu/authentik/stage.sh` owns deterministic preparation. In one approved stage it validates host/resources/network, validates a protected env file without printing secrets, installs Docker Engine/Compose when absent, installs `socat`, stages exact runtime files, starts Compose, establishes the source-restricted proxy and proves health/exposure invariants.

Human checkpoints remain only for exact production authorization, secret entry, Owner/TOTP/provider configuration and acceptance decisions.

## Affected contours

- `deploy/worker/ubuntu/authentik/**`: canonical worker-hosted Authentik Compose/env/runbook/stage helper.
- `scripts/operations/nginx_sea_speed_auth.py`: parameterized validated Authentik private origin plus existing browser-auth/private-M2M renderer.
- `deploy/vps/sea-speed-auth-cutover.sh`: SHA-bound prepare/status/activate security contour using the exact worker private Authentik origin.
- `docs/operations/SEA_SPEED_AUTH_V1.md`: revised worker-first production sequencing and fail-closed topology.
- `specs/004-sea-speed-auth-v1/**`: topology requirements/acceptance.
- `tests/test_sea_speed_auth_v1.py`: worker runtime, private origin and existing Auth v1 security regression coverage.
- Camera 1 media source/relay/H.264 code: unchanged.
- Sea Speed worker application source/package: unchanged.

## Runtime configuration outside Git

The following values are runtime-only and must never be committed:

- PostgreSQL password;
- Authentik secret key;
- Owner bootstrap password;
- SMTP username/password;
- generated invitations/recovery links;
- TOTP seeds/codes;
- existing camera credentials and API/SSH tokens;
- actual worker API Bearer token.

Non-secret rollout values discovered/validated at runtime include:

- worker private/ZeroTier IPv4 used by the Authentik private proxy;
- exact VPS private/ZeroTier peer allowed to connect to that proxy;
- Authentik private proxy port, default `19000`;
- VPS private M2M listen address/port and exact worker peer IP.

## Validation

Static/source validation must prove:

- SDD completeness and Issue #115/#122 linkage;
- worker Compose pins Authentik `2026.5.6` and PostgreSQL 16;
- Authentik Docker HTTP publishes only to worker loopback;
- PostgreSQL has no host port and no Authentik container mounts the Docker socket;
- worker stage script is shell-syntax-valid, requires expected hostname/private addresses/resources and uses a source-restricted private proxy;
- worker stage can install Docker/Compose when absent without removing conflicting packages automatically;
- nginx renderer is idempotent, fail-closed and removes all `/cams` locations;
- production Authentik origin validation rejects public/wildcard/credential/path inputs;
- every existing `/sea-speed` nginx location receives auth directives;
- spoofed browser identity headers are overwritten;
- private worker M2M ingress remains exact-peer/method/path scoped and derives only a loopback FastAPI origin;
- cutover is candidate-SHA-bound and has no automatic public-route rollback;
- existing Camera 1 private/H.264 and Camera Preview Gallery behavior is preserved.

Production acceptance additionally requires worker Docker/Auth/PostgreSQL health, VPS-to-worker private Authentik health, public `auth.mostdef.ru`, real SMTP, invitation, login, Owner TOTP, password recovery, session revocation, authenticated Camera 1 playback, gallery persistence, worker M2M continuity and direct-origin exposure checks.

## Rollout

1. Merge exact Issue #122 source after CI.
2. Obtain a fresh `PRODUCTION APPROVED` bound to that exact merged `main` SHA and revised MIXED topology.
3. From one operator launcher stage, connect to `sea-speed-worker` (direct ZeroTier or VPS SSH jump as required), create a temporary protected env file locally on the worker and invoke `deploy/worker/ubuntu/authentik/stage.sh stage` with exact worker bind IP and exact VPS peer.
4. The stage helper installs Docker/Compose when absent, starts PostgreSQL/Auth server/Auth worker, establishes the source-restricted worker private proxy and returns `AUTHENTIK_PRIVATE_ORIGIN`.
5. Configure the VPS TLS/nginx `auth.mostdef.ru` vhost to proxy only to that private origin and prove public Authentik readiness.
6. Configure the Owner, TOTP, Forward Auth provider/application and embedded outpost; prove invitation and password recovery.
7. Discover/confirm exact VPS M2M listen and worker peer addresses and prepare worker API URL changes without exposing `SEA_SPEED_API_TOKEN`.
8. Render the combined Camera 1/Auth/private-worker nginx candidate with `--authentik-upstream <worker-private-origin>` and record its SHA-256.
9. Activate the exact candidate, apply prepared worker runtime API URLs and restart only the applicable Sea Speed worker service.
10. Run anonymous, authenticated, gallery, worker-M2M, VPS-to-worker Authentik and direct-origin acceptance.
11. Record sanitized exact source/runtime evidence in Issue #122 and cross-reference Issue #115.

The operator handoff should compress steps 3 and the deterministic parts of 5/8/9 into one ready-to-run command per human checkpoint whenever safe.

## Rollback

Rollback is fail-closed. Backups of nginx and worker Authentik runtime configuration/data are retained, but activation must not automatically restore the old public `/cams/**` route. If post-cutover acceptance fails, stop and preserve evidence. A safe temporary result is an unavailable private Sea Speed surface while `/` remains public.

A runtime rollback requires an explicit production rollback decision. If approved, restore the reviewed previous nginx/auth topology and matching worker API runtime URLs together. Do not silently move Authentik back to the undersized VPS.

## Runtime feedback

- Original Issue #115 source assumed Authentik on VPS loopback. Production preflight later proved the VPS resource floor insufficient.
- Issue #122 records the approved topology revision to the capable Ubuntu worker while preserving the existing identity policy and browser/M2M security semantics.
- Fresh worker evidence: Ubuntu 26.04 LTS x86_64, hostname `sea-speed-worker`, 16 CPU, 30 GiB RAM, 79 GiB free, Docker initially absent.
- The revised source automates Docker installation as part of the bounded worker stage and keeps the Docker Authentik port loopback-only behind a source-restricted private proxy.
- Production remains separately gated by the exact merged SHA; no Issue #122 runtime mutation is authorized by source approval alone.
