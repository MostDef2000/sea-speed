# Feature Specification: Sea Speed Auth v1

- Feature: 004-sea-speed-auth-v1
- Issue: TBD
- Status: Approved for implementation

## Product outcome

Sea Speed remains reachable from the public Internet, but all private operator, API and media surfaces are protected by centrally managed authentication. The public root page remains available. The legacy `/cams/**` surface is retired and must not expose Camera 1 or any other camera content.

## User scenarios

### Scenario 1 - Owner invites a known user

Given the Owner personally knows the user, when the Owner creates an invitation for a fixed email address and a Sea Speed role, then the user can follow the single-use expiring invitation and set a password. Public self-registration is unavailable.

### Scenario 2 - User signs in from another device

Given an active account, when the user opens `/sea-speed/` from any browser-capable device, then the user can authenticate with email and password and receive an authenticated web session.

### Scenario 3 - Owner signs in with stronger authentication

Given the Owner account, when the Owner signs in, then email and password alone are insufficient and a valid TOTP code is also required.

### Scenario 4 - User recovers a forgotten password

Given an active non-Owner account with a verified recovery email, when the user requests password recovery, then the service sends an expiring one-time recovery link without revealing whether arbitrary queried addresses exist. Owner password recovery must not remove the Owner TOTP requirement.

### Scenario 5 - Anonymous visitor reaches private resources

Given an unauthenticated visitor, when the visitor requests any `/sea-speed/**` UI, API, snapshot or media URL, then access is denied or redirected to authentication. Authentication failure or Authentik unavailability must fail closed.

### Scenario 6 - Legacy camera surface is retired

Given any visitor, when `/cams` or `/cams/**` is requested, then no camera page, playlist or media is returned. Camera 1 browser playback is available only through a protected `/sea-speed/media/cam1/` path.

## Functional requirements

- FR-001: `https://mostdef.ru/` MUST remain publicly accessible without Sea Speed authentication.
- FR-002: `/cams` and `/cams/**` MUST be retired and MUST NOT expose camera content or redirect to the authenticated Sea Speed application.
- FR-003: All `/sea-speed/**` browser-facing UI, API, snapshot and media resources MUST require authentication.
- FR-004: Authentik MUST be the identity provider; Sea Speed MUST NOT implement its own password database, password hashing, session store, enrollment or recovery subsystem.
- FR-005: Public self-registration and public access-request flows MUST be disabled.
- FR-006: New users MUST be enrolled only through Owner-created, single-use, expiring invitations bound to a fixed email address and predetermined role/group.
- FR-007: Invitation lifetime MUST default to 24 hours.
- FR-008: Email MUST be the login identifier and recovery channel for normal users.
- FR-009: Admin, Operator and Viewer authentication MUST use email plus password with no mandatory MFA in v1.
- FR-010: Owner authentication MUST use email plus password plus TOTP compatible with standard authenticator applications.
- FR-011: Owner password recovery MUST NOT clear or bypass the existing TOTP requirement.
- FR-012: Authentik administration MUST be available only to the Owner contour. Sea Speed Admin MUST NOT imply Authentik administrator access.
- FR-013: v1 MUST define Owner, Admin, Operator and Viewer groups, but fine-grained per-endpoint RBAC is deferred.
- FR-014: The Owner MUST be able to create invitations, disable or enable accounts, delete accounts, change group assignment, revoke sessions, initiate recovery and inspect authentication events through Authentik.
- FR-015: Password policy MUST support password managers/passphrases, require at least 15 characters, support at least 64 characters, reject weak/common passwords and MUST NOT require arbitrary composition rules or periodic rotation.
- FR-016: Sessions MUST use HTTPS-only secure cookies, be revocable, terminate on logout, stop authorizing disabled users and have a bounded maximum lifetime targeted at 12 hours.
- FR-017: Browser-facing Camera 1 HLS MUST move from `/cams/hls/cam1/index.m3u8` to `/sea-speed/media/cam1/index.m3u8` without changing the private acquisition, relay, H.264 compatibility output or AI-independent live behavior.
- FR-018: Authentik or authentication-proxy failure MUST fail closed for `/sea-speed/**`.
- FR-019: Client-supplied authentication/identity headers MUST NOT be trusted; nginx MUST overwrite or clear security-sensitive forwarding headers before passing authenticated identity upstream.
- FR-020: FastAPI origin, MediaMTX, Camera 1 compatibility HLS origin, Authentik internal services and private relay services MUST NOT gain direct public Internet exposure as part of this feature.
- FR-021: Runtime credentials, Authentik secret keys, SMTP credentials and generated secrets MUST NOT be committed to the repository.
- FR-022: Deployment health checks MUST distinguish private origin health from anonymous public security checks so that protecting `/sea-speed/api/health` does not break deployment verification.

## Roles

- Owner: Authentik administration plus full Sea Speed access; TOTP required.
- Admin: Sea Speed access; no Authentik administration; no mandatory MFA in v1.
- Operator: Sea Speed access; no mandatory MFA in v1.
- Viewer: Sea Speed access; no mandatory MFA in v1.

Fine-grained Sea Speed authorization differences between Admin, Operator and Viewer are deferred.

## Security constraints

- Only HTTPS browser access is supported for authenticated sessions.
- Authentication must fail closed.
- Secrets remain outside Git source.
- Existing camera credentials and private relay topology remain protected.
- No new public backend/media listener is introduced.
- `/cams/**` retirement is intentional and supersedes the earlier public Camera 1 URL compatibility requirement.

## Acceptance criteria

- AC-001: anonymous `/` returns the public landing page.
- AC-002: anonymous `/cams/` and `/cams/hls/cam1/index.m3u8` expose no camera content.
- AC-003: anonymous `/sea-speed/`, `/sea-speed/api/**`, `/sea-speed/cameras/**`, `/sea-speed/objects/**`, snapshots and `/sea-speed/media/**` require authentication.
- AC-004: crafted client authentication headers cannot bypass authentication.
- AC-005: a valid invitation can be used exactly once before expiration and cannot be used after expiration.
- AC-006: the invitation email and role are predetermined by the Owner and cannot be widened by the invitee.
- AC-007: Admin, Operator and Viewer can authenticate from a second device with email and password.
- AC-008: Owner login without TOTP is rejected; valid password plus TOTP succeeds.
- AC-009: Owner password recovery leaves TOTP required.
- AC-010: disabled users cannot establish or continue an authenticated Sea Speed session.
- AC-011: authenticated Camera 1 playback advances through `/sea-speed/media/cam1/index.m3u8` using the existing H.264 compatibility output.
- AC-012: FastAPI, media origins and relay services are not exposed directly to the public Internet by this change.
- AC-013: production rollout is not performed without a separate exact-SHA production safety envelope.

## Explicit exclusions

- Public registration or access-request workflow.
- Social login.
- Passkeys.
- Mandatory MFA for Admin, Operator or Viewer.
- SMS authentication.
- User-controlled email change.
- Fine-grained API RBAC.
- A Sea Speed-native user/password/session database.
- Changes to AI, detection, tracking, speed estimation or calibration semantics.
- Changes to the physical camera source, Ubuntu relay, camera codec preparation or Windows worker.
- Storage/database schema migration.

## Production impact

VPS / security-control-plane change. Source integration does not authorize production mutation. A separate `PRODUCTION APPROVED` envelope bound to the exact final `main` SHA is required before rollout.
