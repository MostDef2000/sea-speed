# Implementation Plan: Sea Speed Auth v1

- Specification: `specs/004-sea-speed-auth-v1/spec.md`
- Issue: #115
- Status: Implementing

## Architecture

```text
Internet
  |
  +-- https://mostdef.ru/ -------------------------- public landing page
  |
  +-- https://auth.mostdef.ru/ --------------------- nginx -> Authentik loopback
  |
  +-- https://mostdef.ru/cams/** ------------------- 404, no media
  |
  +-- https://mostdef.ru/sea-speed/**
          |
          +-- nginx auth_request
          |      -> Authentik embedded outpost on loopback
          |
          +-- authenticated static UI
          +-- authenticated FastAPI proxy
          +-- authenticated snapshots/media
          +-- authenticated Camera 1 HLS
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

Existing worker machine-to-machine API traffic is separated from interactive browser authentication:

```text
approved worker ZeroTier peer
-> VPS literal private IP:private port
-> exact nginx method/path allowlist
-> existing loopback FastAPI origin

POST state/events still require existing SEA_SPEED_API_TOKEN
GET ROI/speed configuration remains private-peer-only
```

The private listener has no generic `/api/**` route and is not bound to a public interface.

## Decisions

### D-001 - Authentik owns identity

Sea Speed does not implement password hashing, enrollment, recovery, MFA or browser sessions. Authentik is self-hosted on the VPS and exposed only through nginx. Internal Authentik HTTP binds to loopback.

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

The earlier public Camera 1 URL is intentionally superseded. Existing nginx `/cams...` locations are removed by the bounded renderer and replaced with a deny/not-found contour. The old Camera 1 direct-H264 renderer is updated so operational reuse cannot recreate the retired public URL.

### D-007 - Fail closed

If Authentik or the embedded outpost is unavailable, `/sea-speed/**` is not served anonymously. `/outpost.goauthentik.io/**` remains reachable without recursive authentication because it is the forward-auth callback/start contour.

### D-008 - Embedded outpost and no Docker socket

The deployment uses Authentik's embedded outpost for nginx forward auth. The Authentik worker is not given the Docker socket because v1 does not require Authentik-managed external outpost containers.

### D-009 - Reproducible nginx change

Nginx security policy is rendered and verified from repository tooling before activation. The activation script creates a root-only backup, runs `nginx -t`, reloads only nginx and performs no automatic rollback to the legacy public camera contour. `prepare` writes a protected candidate and returns its SHA-256; `activate` re-renders and refuses a SHA mismatch.

### D-010 - Deployment health is not public bypass

The normal VPS code deploy does not depend on anonymous success from `/sea-speed/api/health`. FastAPI health is checked through the loopback origin at `http://127.0.0.1:8000/api/health` by default, while the public private-health URL is only a transition/security smoke check. No user credential or Authentik session is added to GitHub Actions merely to make deployment health pass.

### D-011 - Separate worker M2M ingress from browser auth

The worker is infrastructure, not an interactive user. Requiring an Authentik browser session for its existing state/event/config traffic would break accepted AI telemetry. The nginx renderer therefore derives the current FastAPI loopback origin from the existing `/sea-speed/api/` proxy and creates a second listener only when supplied both an exact private VPS `IP:PORT` and an exact private worker peer IP.

The listener exposes only:

- POST `/api/cam1/state`;
- POST `/api/cam1/events`;
- GET `/api/cam1/roi`;
- GET `/api/cam1/speed-config`;
- GET `/api/cam1/speed-lines`.

All other paths/methods are absent or denied. State/event writes keep the existing FastAPI Bearer-token check. Production changes only the worker runtime endpoint environment variables; worker source/package, AI behavior and camera acquisition do not change.

## Source contours

- `deploy/vps/authentik/**`: pinned Authentik runtime, non-secret configuration template and blueprint.
- `scripts/operations/nginx_sea_speed_auth.py`: bounded nginx auth/private-M2M transform and verification.
- `deploy/vps/sea-speed-auth-cutover.sh`: SHA-bound prepare/status/activate security contour.
- Camera 1 nginx/cutover source: migrate browser path to `/sea-speed/media/cam1/`.
- root/operator frontend and tests: remove `/cams/` link and use protected HLS URL.
- existing Camera 1 SDD/docs/tests: explicitly supersede the public-path compatibility requirement while preserving media behavior.
- VPS deploy source/docs/baseline: separate local origin health from anonymous auth smoke.
- `docs/operations/SEA_SPEED_AUTH_V1.md`: production sequencing, worker runtime URL migration and fail-closed rollback.

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

The VPS private listen address/port and worker private peer IP are discovered at rollout and passed as non-secret bounded parameters.

## Validation

Static/source validation must prove:

- SDD completeness and exact Issue linkage;
- Authentik image is version-pinned and no Docker socket is mounted;
- enrollment stages cannot continue without invitations;
- password policy and Owner-only TOTP policy are explicit;
- nginx renderer is idempotent, fail-closed and removes all `/cams` locations;
- every existing `/sea-speed` nginx location receives auth directives;
- spoofed browser identity headers are overwritten;
- private worker ingress rejects public/network-wide addressing, derives only a loopback FastAPI origin, and exposes only exact methods/paths;
- cutover is candidate-SHA-bound and has no automatic public-route rollback;
- frontend no longer references `/cams/` or old Camera 1 HLS;
- existing Camera 1 private/H.264 behavior is preserved;
- VPS deployment uses origin health rather than anonymous private health success.

Production acceptance additionally requires real SMTP, invitation, login, Owner TOTP, password recovery, session revocation, authenticated Camera 1 playback, worker M2M continuity and direct-origin exposure checks.

## Rollout

1. Merge exact source after CI.
2. Obtain separate `PRODUCTION APPROVED` bound to the exact merged `main` SHA.
3. Stage pinned Authentik runtime and secrets without exposing them.
4. Start Authentik on loopback and prove database/server/worker health.
5. Configure DNS/TLS for `auth.mostdef.ru` through nginx and prove Authentik login.
6. Apply the Sea Speed blueprint and configure the Forward Auth provider/application on the embedded outpost.
7. Configure Owner email and TOTP; prove Owner login requires TOTP.
8. Prove one non-Owner invitation flow and password recovery.
9. Discover exact VPS/worker private IPs and prepare the worker runtime URL update without exposing `SEA_SPEED_API_TOKEN`.
10. Render the combined Camera 1/Auth/private-worker nginx candidate and record its SHA-256.
11. Activate the exact candidate, then apply the prepared worker runtime URLs and restart only the applicable worker service.
12. Run anonymous, authenticated, worker-M2M and direct-origin security/media acceptance.
13. Record exact source/runtime evidence in Issue #115.

## Rollback

Rollback is fail-closed. Backups of nginx and Authentik runtime data/configuration are retained, but the activation script must not automatically restore the old public `/cams/**` route. If post-cutover acceptance fails, stop, preserve evidence and require an explicit production rollback decision. If rollback is approved, matching nginx/auth and worker runtime URLs are restored together. A safe temporary outcome is unavailable private Sea Speed, not anonymous private content.
