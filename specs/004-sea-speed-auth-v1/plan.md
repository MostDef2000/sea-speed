# Implementation Plan: Sea Speed Auth v1

- Specification: `specs/004-sea-speed-auth-v1/spec.md`
- Issue: #115
- Runtime topology revision: #122
- Cutover split-layout remediation: #140
- Browser-routing remediation: #146
- Authenticated header UX: #148
- Status: Authentik/nginx boundary active; Issue #148 application source lifecycle and final acceptance pending

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
          +-- authenticated Operator / Cameras / Objects UI
          +-- authenticated FastAPI proxy
          +-- authenticated snapshots/media
          +-- authenticated Camera 1 HLS
```

The browser header identity path added by Issue #148 reuses the same outpost rather than adding another identity service:

```text
authenticated browser
  -> GET /outpost.goauthentik.io/auth/nginx (same origin, existing session cookie)
  -> Authentik forward-auth check
  -> response X-authentik-username
  -> UI textContent only

Выйти
  -> /outpost.goauthentik.io/sign_out
  -> Authentik Proxy Provider logout
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

Production nginx was prepared from a split root TLS site and direct Sea Speed snippets. The active candidate is flattened by the already merged bounded source pipeline:

```text
/etc/nginx/sites-available/mostdef.ru
  -> direct Sea Speed snippets before cutover

prepare/activate source pipeline
  root site
    -> materialize only direct /etc/nginx/snippets/sea-speed-*.conf
    -> Camera 1 renderer
    -> Auth v1 renderer
    -> reviewed flattened candidate + SHA-256
    -> activated root site after exact SHA guard
```

Issue #146 adds the canonical host/outpost browser-routing rules before Forward Auth:

```text
www.mostdef.ru/** -> 308 https://mostdef.ru/**
Proxy Provider External host -> https://mostdef.ru
public outpost contour -> /outpost.goauthentik.io/**
protected application contour -> /sea-speed/**
```

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

The worker is infrastructure, not an interactive user. The nginx renderer derives the FastAPI loopback origin from the existing `/sea-speed/api/` proxy and creates a private M2M listener only when supplied an exact private VPS `IP:PORT` and exact private worker peer IP.

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

### D-014 - Materialize only direct Sea Speed nginx snippets

Issue #140 resolves the observed production split-layout without teaching the existing Camera 1 and Auth renderers to recursively evaluate arbitrary nginx configuration. The Auth renderer owns a bounded pre-render operation that first identifies the exact TLS `mostdef.ru` root site and then replaces only direct regular `/etc/nginx/snippets/sea-speed-*.conf` include directives inside that server with the exact file contents.

The operation rejects wildcard Sea Speed includes, nested includes inside materialized snippets, symlinks, missing files and Sea Speed snippets resolving outside the approved snippets root. Non-Sea-Speed includes, including certificate/Let’s Encrypt includes, stay literal and unchanged. `prepare` materializes only into temporary candidate input; it never edits the active root file or snippet files. `activate` repeats the same materialization from current source state, so any Sea Speed snippet drift changes candidate SHA-256 and the existing expected-SHA guard stops activation.

After activation the installed root site is the reviewed flattened candidate. The old Sea Speed snippet files remain on disk but are no longer referenced by that root site; no cleanup/deletion is part of this outcome.

### D-015 - Browser session and provider token are distinct timers

The Authentik User Login Stage remains configured for a browser session targeted at 12 hours. The Sea Speed Proxy Provider access-token validity is intentionally 96 hours. The 96 hours provider token is not the browser-session lifetime and does not redefine the 12 hours User Login Stage contract. Both values are deliberate and must be reviewed independently if either is changed later.

### D-016 - Reuse the forward-auth response for authenticated header UX

Issue #148 must not create a parallel identity/session API. Operator, Cameras and Objects perform a same-origin `fetch` to the already routed `/outpost.goauthentik.io/auth/nginx` endpoint using browser credentials. The page requires a successful response plus a non-empty `X-authentik-username` response header and renders that value only with `textContent`. If the trusted header is unavailable, the UI displays `недоступно`; it does not fall back to URL parameters, local storage, session storage or a hard-coded identity.

The header logout action is a normal navigation to `/outpost.goauthentik.io/sign_out`, delegating session invalidation to the Proxy Provider. It does not attempt to delete Authentik cookies from JavaScript.

The compact lighthouse mark is presentation/navigation only. It links to `/`, which remains public. Operator, Cameras and Objects use the same markup/class contract so future internal pages with headers can adopt the same baseline without changing authentication semantics.

## Affected contours

- `deploy/worker/ubuntu/authentik/**`: canonical worker-hosted Authentik Compose/env/runbook/stage helper; unchanged by #148.
- `scripts/operations/nginx_sea_speed_auth.py`: active browser-auth/private-M2M renderer and #146 canonical host/outpost behavior; unchanged by #148.
- `deploy/vps/sea-speed-auth-cutover.sh`: active SHA-bound security contour; unchanged by #148.
- `frontend/sea-speed/index.html`: common lighthouse/session/logout header plus existing protected Camera 1 path.
- `frontend/sea-speed/cameras/index.html`: common lighthouse/session/logout header; preview behavior unchanged.
- `frontend/sea-speed/objects/index.html`: common lighthouse/session/logout header; registry behavior unchanged.
- `tests/test_frontend_contract.py`: common header identity/logout/lighthouse regression coverage plus existing frontend contracts.
- `specs/004-sea-speed-auth-v1/**`: topology, timing, browser UX and acceptance requirements.
- Camera 1 media source/relay/H.264 code: unchanged.
- Sea Speed worker application source/package: unchanged.
- FastAPI application code: unchanged by Issue #148.

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

- SDD completeness and Issue #115/#122/#140/#146/#148 linkage;
- worker Compose pins Authentik `2026.5.6` and PostgreSQL 16;
- Authentik Docker HTTP publishes only to worker loopback;
- PostgreSQL has no host port and no Authentik container mounts the Docker socket;
- nginx renderer remains idempotent, fail-closed and removes all `/cams` locations;
- `www.mostdef.ru` canonicalization and root outpost callback routing remain intact;
- every existing `/sea-speed` nginx location receives auth directives and spoofed browser identity headers are overwritten;
- private worker M2M ingress remains exact-peer/method/path scoped and derives only a loopback FastAPI origin;
- accepted 12 hours browser session and 96 hours Proxy Provider token distinction remains documented;
- Operator, Cameras and Objects each contain one lighthouse home link, one session username target and one provider logout action;
- each internal page reads only `X-authentik-username` from the same-origin Authentik forward-auth response and uses no `localStorage` or `sessionStorage` identity fallback;
- the Operator page keeps `/sea-speed/media/cam1/index.m3u8` and does not reintroduce `/cams/**`;
- existing Camera Preview Gallery, registry and operator controls remain structurally intact.

Production acceptance focuses on the large integration contours: current Authentik/private health, canonical host routing, anonymous gate, authenticated session/login, username display, provider logout, lighthouse navigation, protected Camera 1 playback, worker M2M continuity and controlled fail-closed behavior. Password-recovery deep acceptance remains deferred/non-blocking by current operator decision. Camera/AI overlay freshness is a separate runtime contour and is not a blocker for the #148 presentation change itself.

## Rollout

1. Implement Issue #148 on a fresh branch from the current merged Auth v1 source without touching nginx, Authentik runtime or worker source.
2. Pass exact-head PR Validation and Quality integration, verify exact changed-file scope/no unresolved threads, merge, identify the new exact `main` SHA and obtain fresh `PRODUCTION APPROVED <sha>`.
3. Before deployment, re-prove that active nginx remains the reviewed #146 boundary and that private/public Authentik health is good.
4. Use the normal exact-SHA VPS application deployer to synchronize API/frontend/root release files. It may restart `sea-speed-api`, but must not replace/re-render/reload the already active Auth v1 nginx candidate.
5. Verify the deployed operator source uses `/sea-speed/media/cam1/index.m3u8`, `/api/health` reports the exact deployed source, and anonymous `/sea-speed/**` remains gated.
6. In a clean browser session, authenticate through Authentik and verify Operator, Cameras and Objects show the correct username, lighthouse goes to `/`, `Выйти` ends the provider session, and returning to `/sea-speed/**` requires authentication again.
7. Verify authenticated Camera 1 playback through the protected media path. Treat worker/overlay freshness as a separate diagnostic if the AI worker is not currently producing fresh frames.
8. Perform the controlled Authentik/private-path fail-closed test, restore the dependency and record sanitized final evidence in #122/#148.

The operator handoff should use one ready-to-run command per human checkpoint whenever safe.

## Rollback

Rollback is fail-closed. The normal application deployer retains the previous release as rollback target. Issue #148 does not change nginx or Authentik runtime. If the new application release fails frontend/API acceptance, stop and preserve evidence; do not weaken the active Authentik boundary. A separately approved application rollback may restore the previous application files while keeping the current Auth v1 nginx/security contour active.

A rollback of nginx/Authentik/private M2M topology remains a different protected operation and requires an explicit production rollback decision.

## Runtime feedback

- Original Issue #115 source assumed Authentik on VPS loopback. Production preflight later proved the VPS resource floor insufficient.
- Issue #122 records the approved topology revision to the capable Ubuntu worker while preserving the existing identity policy and browser/M2M security semantics.
- Worker Authentik/PostgreSQL/private proxy, public `auth.mostdef.ru`, Owner TOTP, provider/application/policy, Viewer invite/login/session revocation and SMTP/invitation delivery are proven enough for integration rollout; deep password-recovery acceptance is deferred.
- Issue #140 resolved the actual split nginx layout and produced a deterministic flattened candidate pipeline.
- Issue #146 corrected `www` host mismatch and the subpath callback loop; its reviewed nginx candidate is active in production and browser login now completes.
- Authenticated browser evidence shows an existing session enters directly while an incognito session is prompted to authenticate, and protected `/sea-speed/api/health` and `/sea-speed/cameras/` work.
- The production application release remains older than current merged source, which explains the still-visible retired `/cams/hls/cam1/index.m3u8` reference on the live Operator page. Deployment is deferred until #148 merges so one exact application synchronization includes both the protected media URL and authenticated header UX.
- Final provider logout, protected Camera 1 playback and controlled fail-closed acceptance remain pending after the #148 application release deploy.
