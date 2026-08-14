# Implementation Plan: Sea Speed Auth v1

- Specification: `specs/004-sea-speed-auth-v1/spec.md`
- Issue: #115
- Runtime topology revision: #122
- Cutover split-layout remediation: #140
- Status: Worker identity contour staged; Issue #140 source remediation in progress before final cutover

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

Before final cutover, production nginx may be split across a root TLS site and direct Sea Speed snippets:

```text
/etc/nginx/sites-available/mostdef.ru
  -> include /etc/nginx/snippets/sea-speed-api.conf
  -> include /etc/nginx/snippets/sea-speed-page.conf
  -> unrelated includes remain as includes

prepare/activate source pipeline
  root site
    -> materialize only direct /etc/nginx/snippets/sea-speed-*.conf
    -> Camera 1 renderer
    -> Auth v1 renderer
    -> verified flattened candidate + SHA-256
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

### D-014 - Materialize only direct Sea Speed nginx snippets

Issue #140 resolves the observed production split-layout without teaching the existing Camera 1 and Auth renderers to recursively evaluate arbitrary nginx configuration. The Auth renderer owns a bounded pre-render operation that first identifies the exact TLS `mostdef.ru` root site and then replaces only direct regular `/etc/nginx/snippets/sea-speed-*.conf` include directives inside that server with the exact file contents.

The operation rejects wildcard Sea Speed includes, nested includes inside materialized snippets, symlinks, missing files and Sea Speed snippets resolving outside the approved snippets root. Non-Sea-Speed includes, including certificate/Let’s Encrypt includes, stay literal and unchanged. `prepare` materializes only into temporary candidate input; it never edits the active root file or snippet files. `activate` repeats the same materialization from current source state, so any Sea Speed snippet drift changes candidate SHA-256 and the existing expected-SHA guard stops activation.

After activation the installed root site is the reviewed flattened candidate. The old Sea Speed snippet files remain on disk but are no longer referenced by that root site; no cleanup/deletion is part of this outcome.

### D-015 - Browser session and provider token are distinct timers

The Authentik User Login Stage remains configured for a browser session targeted at 12 hours. The Sea Speed Proxy Provider access-token validity is intentionally 96 hours. The 96 hours provider token is not the browser-session lifetime and does not redefine the 12 hours User Login Stage contract. Both values are deliberate and must be reviewed independently if either is changed later.

## Affected contours

- `deploy/worker/ubuntu/authentik/**`: canonical worker-hosted Authentik Compose/env/runbook/stage helper; unchanged by #140.
- `scripts/operations/nginx_sea_speed_auth.py`: parameterized validated Authentik private origin, existing browser-auth/private-M2M renderer, exact TLS host source check and bounded Sea Speed snippet materialization.
- `deploy/vps/sea-speed-auth-cutover.sh`: SHA-bound prepare/status/activate security contour using the exact worker private Authentik origin and materialized candidate input.
- `docs/operations/SEA_SPEED_AUTH_V1.md`: revised worker-first production sequencing, split-layout preparation and fail-closed topology.
- `specs/004-sea-speed-auth-v1/**`: topology, timing and cutover requirements/acceptance.
- `tests/test_sea_speed_auth_v1.py`: worker runtime, private origin, split-layout materialization and existing Auth v1 security regression coverage.
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

- SDD completeness and Issue #115/#122/#140 linkage;
- worker Compose pins Authentik `2026.5.6` and PostgreSQL 16;
- Authentik Docker HTTP publishes only to worker loopback;
- PostgreSQL has no host port and no Authentik container mounts the Docker socket;
- worker stage script is shell-syntax-valid, requires expected hostname/private addresses/resources and uses a source-restricted private proxy;
- worker stage can install Docker/Compose when absent without removing conflicting packages automatically;
- nginx renderer is idempotent, fail-closed and removes all `/cams` locations;
- production Authentik origin validation rejects public/wildcard/credential/path inputs;
- exact `mostdef.ru` TLS host matching does not confuse `auth.mostdef.ru` with the application site;
- production-style direct `sea-speed-*.conf` snippets are flattened before Camera/Auth rendering while unrelated includes remain literal;
- wildcard, nested, symlink and out-of-root Sea Speed snippet expansion fails closed;
- every existing `/sea-speed` nginx location receives auth directives;
- spoofed browser identity headers are overwritten;
- private worker M2M ingress remains exact-peer/method/path scoped and derives only a loopback FastAPI origin;
- cutover is candidate-SHA-bound and has no automatic public-route rollback;
- the accepted 12 hours browser session and 96 hours Proxy Provider token distinction is documented;
- existing Camera 1 private/H.264 and Camera Preview Gallery behavior is preserved.

Production acceptance focuses on the large integration contours: worker Docker/Auth/PostgreSQL health, VPS-to-worker private Authentik health, public `auth.mostdef.ru`, SMTP/invitation delivery, Owner TOTP, basic role login/session revocation, final nginx boundary, authenticated Camera 1 playback, worker M2M continuity, direct-origin exposure and fail-closed behavior. Password-recovery deep acceptance is deferred/non-blocking by current operator decision and can be added later if required.

## Rollout

1. Complete Issue #140 source remediation from current `main` while preserving the already staged worker identity runtime.
2. Pass exact-head CI, merge Issue #140, identify the new exact `main` SHA, and obtain a fresh `PRODUCTION APPROVED <sha>` for the remaining VPS/M2M mutations.
3. Re-prove the existing worker private Authentik health and public `auth.mostdef.ru` readiness; do not restage working identity internals without a specific need.
4. Confirm the current root `mostdef.ru` nginx site and direct Sea Speed snippet layout.
5. Run `sea-speed-auth-cutover.sh prepare` with exact worker Authentik origin and private M2M addresses. The script must materialize only direct `sea-speed-*.conf` snippets, run Camera/Auth renderers, write the protected flattened candidate and print its SHA-256 without reloading nginx.
6. Review the prepared candidate digest/diff and coordinate the Sea Speed worker private M2M URL change without exposing `SEA_SPEED_API_TOKEN`.
7. Run `activate` with the exact prepare SHA. It must re-materialize/re-render, refuse any SHA drift, back up the root site, install the reviewed flattened candidate, pass `nginx -t`, reload nginx and perform bounded anonymous checks.
8. Apply the prepared worker runtime URLs and restart only the applicable Sea Speed worker service.
9. Run the large integration acceptance: anonymous/authenticated `/sea-speed/**`, Camera 1 H.264, private M2M continuity and direct-origin checks.
10. Perform the controlled Authentik/private-path fail-closed test, restore the dependency and record sanitized final evidence in #122/#115/#140.

The operator handoff should use one ready-to-run command per human checkpoint whenever safe.

## Rollback

Rollback is fail-closed. Backups of nginx and worker Authentik runtime configuration/data are retained, but activation must not automatically restore the old public `/cams/**` route. If post-cutover acceptance fails, stop and preserve evidence. A safe temporary result is an unavailable private Sea Speed surface while `/` remains public.

A runtime rollback requires an explicit production rollback decision. If approved, restore the reviewed previous nginx/auth topology and matching worker API runtime URLs together. Do not silently move Authentik back to the undersized VPS.

## Runtime feedback

- Original Issue #115 source assumed Authentik on VPS loopback. Production preflight later proved the VPS resource floor insufficient.
- Issue #122 records the approved topology revision to the capable Ubuntu worker while preserving the existing identity policy and browser/M2M security semantics.
- Worker Authentik/PostgreSQL/private proxy, public `auth.mostdef.ru`, Owner TOTP, provider/application/policy, Viewer invite/login/session revocation and SMTP/invitation delivery are now proven enough to proceed with integration rollout; deep password-recovery acceptance is deferred.
- Issue #140 records the remaining source blocker discovered from the actual nginx layout: the `mostdef.ru` TLS site uses direct Sea Speed snippets and therefore must be safely materialized before the existing renderers run.
- The accepted timing contract is 12 hours for the browser User Login Stage and 96 hours for Proxy Provider access-token validity, as separate timers.
- Final nginx activation, worker M2M URL switch and fail-closed dependency acceptance remain pending and require a fresh production approval after the #140 merge.
