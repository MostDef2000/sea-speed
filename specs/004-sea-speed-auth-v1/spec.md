# Feature Specification: Sea Speed Auth v1

- Feature: 004-sea-speed-auth-v1
- Issue: #115
- Runtime topology revision: #122
- Cutover split-layout remediation: #140
- Browser-routing remediation: #146
- Authenticated header UX: #148
- Status: Authentik/nginx browser boundary activated; authenticated header UX source work and final fail-closed acceptance pending

## Product outcome

Sea Speed remains reachable from the public Internet, but all private operator, API and media surfaces are protected by centrally managed authentication. The public root page remains available. The legacy `/cams/**` surface is retired and must not expose Camera 1 or any other camera content.

After Issue #122, Authentik and PostgreSQL run on the commissioned Ubuntu worker rather than the undersized public VPS. The VPS remains the sole public nginx/TLS ingress and reaches Authentik only through an exact private ZeroTier/RFC1918 worker origin. Moving identity runtime does not change camera acquisition, AI behavior, the Sea Speed worker application package, or the existing private worker M2M API contract.

Issue #140 corrects the cutover assumption that all `/sea-speed/**` locations live in the physical `mostdef.ru` site file. Production may keep direct Sea Speed nginx snippets before cutover; preparation must materialize only those bounded snippets into the reviewed candidate without expanding unrelated nginx includes or changing the active configuration.

Issue #146 records the post-activation browser-routing correction: `www.mostdef.ru` canonicalizes to `mostdef.ru` before Forward Auth, the Proxy Provider External host is the origin-only `https://mostdef.ru`, and the unauthenticated outpost contour remains rooted at `/outpost.goauthentik.io/**` so OAuth callbacks do not recurse through `/sea-speed/**`.

Issue #148 adds a common authenticated header UX without creating a Sea Speed-native identity subsystem. Protected internal pages display the username returned by the existing Authentik nginx forward-auth endpoint, expose the Authentik provider sign-out action, and carry a compact lighthouse home mark linking back to the public `mostdef.ru` root.

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

Given an unauthenticated visitor, when the visitor requests any `/sea-speed/**` UI, API, snapshot or media URL, then access is denied or redirected to authentication. Authentication failure, worker failure, private-network failure, or Authentik unavailability must fail closed.

### Scenario 6 - Legacy camera surface is retired

Given any visitor, when `/cams` or `/cams/**` is requested, then no camera page, playlist or media is returned. Camera 1 browser playback is available only through a protected `/sea-speed/media/cam1/` path.

### Scenario 7 - Worker continues machine-to-machine API traffic

Given the AI worker is an infrastructure peer rather than an interactive browser user, when it publishes state/events or reads ROI/speed configuration, then it uses an exact private VPS listener reachable only from the approved worker private peer. Interactive `/sea-speed/**` remains Authentik-only and no Sea Speed worker source/package change is required.

### Scenario 8 - Identity runtime is hosted on the worker

Given the public VPS cannot satisfy the Authentik resource baseline and the commissioned Ubuntu worker has sufficient resources, when Authentik is staged, then Docker, Authentik and PostgreSQL run on the Ubuntu worker; Authentik Docker HTTP remains worker-loopback-only; one source-restricted private proxy exposes only the worker ZeroTier address to the exact VPS peer; and public browser traffic still enters only through VPS HTTPS.

### Scenario 9 - Signed-in user sees identity and can leave the private application

Given a user has an authenticated Sea Speed browser session, when the user opens Operator, Cameras or Objects, then the page header shows the trusted Authentik username and a visible sign-out action. The user can click the lighthouse mark to return to the public `mostdef.ru` root, and clicking `Выйти` delegates logout to the Authentik Proxy Provider instead of emulating logout in browser-local state.

## Requirements

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
- FR-023: Existing worker machine-to-machine traffic MUST NOT depend on an interactive Authentik browser session. Nginx MUST expose only the exact required worker methods/endpoints on a separate listener bound to a literal private VPS address and restricted to one literal approved private worker peer.
- FR-024: The private worker ingress MUST proxy only to the existing loopback FastAPI origin, MUST keep the existing Bearer-token requirement for state/event writes, and MUST NOT provide a generic `/api/**` bypass. Production rollout may change worker runtime API URLs to this private listener but MUST NOT require a Sea Speed worker source/package change.
- FR-025: Authentik server, Authentik worker and PostgreSQL production runtime MUST be hosted on the commissioned Ubuntu worker after Issue #122; the original VPS-local Compose placement is superseded for production.
- FR-026: Authentik Docker HTTP on the Ubuntu worker MUST publish only to worker loopback. PostgreSQL MUST have no host port, and the Authentik worker container MUST NOT mount `/var/run/docker.sock`.
- FR-027: The worker MUST expose Authentik to the VPS only through one literal private worker IPv4/port restricted to the exact private VPS peer. The private proxy MUST NOT listen on a public or wildcard address.
- FR-028: VPS nginx Authentik/outpost routing MUST be rendered against an explicit validated private Authentik origin. Production cutover MUST reject loopback, public, credential-bearing, path-bearing or non-literal origins.
- FR-029: Loss of the worker, Authentik private proxy, or ZeroTier path MUST make `/sea-speed/**` unavailable rather than anonymous. The public `/` landing page remains independent.
- FR-030: Worker-hosted Authentik MUST NOT modify Sea Speed AI/detection/tracking/calibration/speed semantics, camera acquisition/relay behavior, the worker API token, or the worker application package.
- FR-031: The normal production operator path SHOULD use one bounded stage to validate worker resources, install Docker/Compose when absent, stage Authentik/PostgreSQL, establish the private proxy and prove health; manual package/hash/preflight steps are fallback-only.
- FR-032: The Authentik User Login Stage browser session lifetime MUST remain targeted at 12 hours. The Proxy Provider access-token validity is intentionally 96 hours; these are separate timers, and the 96 hours provider token validity MUST NOT redefine or extend the 12 hours browser login-stage session contract.
- FR-033: Auth v1 cutover MUST support a split `mostdef.ru` nginx source layout by materializing only direct regular `/etc/nginx/snippets/sea-speed-*.conf` includes into the candidate input. Wildcard Sea Speed includes, nested includes inside a materialized Sea Speed snippet, symlink/out-of-root Sea Speed snippet expansion, and ambiguous target TLS sites MUST fail closed. Unrelated nginx includes MUST remain unchanged.
- FR-034: Operator, Cameras and Objects MUST display the current authenticated username from the existing Authentik nginx forward-auth response header. The browser MUST NOT synthesize or persist an identity fallback when the trusted username is absent.
- FR-035: Protected internal page headers MUST expose a visible `Выйти` action that navigates to `/outpost.goauthentik.io/sign_out`; browser-local cookie deletion, `localStorage` or `sessionStorage` MUST NOT substitute for provider logout.
- FR-036: Internal pages that have a Sea Speed header MUST expose the common compact lighthouse home mark at the top left; activating it MUST return to the public `/` root. The common header MUST remain usable on desktop and mobile layouts.

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
- No new public backend/media/Auth listener is introduced.
- Worker-hosted Authentik is reachable from the VPS only over the exact source-restricted private origin.
- Private worker M2M ingress remains bound only to an approved private VPS address and exact worker peer, with exact methods/paths.
- `/cams/**` retirement is intentional and supersedes the earlier public Camera 1 URL compatibility requirement.
- Split nginx source materialization is candidate-only during `prepare`; it must not mutate active nginx or the source snippets.
- Displayed browser identity is presentation data obtained from the Authentik outpost response; it does not become a Sea Speed authorization source or local session primitive.
- Missing/empty `X-authentik-username` on the identity probe is displayed as unavailable and MUST NOT be replaced from URL parameters, DOM storage, cookies readable by JavaScript or hard-coded user data.

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
- AC-014: from the exact approved worker peer, the private VPS M2M listener supports only POST state/events and GET ROI/speed-config/speed-lines; unrelated paths/methods are denied or absent.
- AC-015: the worker continues publishing state/events with its existing API Bearer token and fetching configuration after its runtime URLs are moved to the private VPS listener; no Sea Speed worker source/package update is required.
- AC-016: worker Authentik staging proves at least 2 CPUs, 2 GiB RAM, healthy PostgreSQL/server/worker, worker-loopback Docker publish, no PostgreSQL host port and no Docker socket mount.
- AC-017: the VPS can reach `http://<worker-private-ip>:<private-port>/-/health/ready/`, while the private origin is not bound to a public interface and is source-restricted to the exact VPS peer.
- AC-018: rendered nginx contains the exact worker private Authentik origin for the embedded outpost and rejects a different/public origin during verification.
- AC-019: stopping the worker Authentik/private path causes private Sea Speed auth requests to fail closed rather than serving anonymous content.
- AC-020: from a production-style root site containing direct `sea-speed-*.conf` snippets, `prepare` produces a flattened, verified candidate while leaving the active root site and snippet files unchanged; non-Sea-Speed includes remain intact.
- AC-021: changing a materialized Sea Speed snippet between `prepare` and `activate` changes the re-rendered candidate digest and blocks activation through the expected SHA-256 guard.
- AC-022: an authenticated Operator, Cameras or Objects page displays the username returned in `X-authentik-username` by the same-origin Authentik nginx forward-auth endpoint; a missing trusted header does not produce a fake/local identity.
- AC-023: `Выйти` on each protected page uses `/outpost.goauthentik.io/sign_out`; after provider logout, a fresh protected request requires authentication again.
- AC-024: Operator, Cameras and Objects carry the same lighthouse home mark linked to `/`, preserve their existing navigation, and remain usable at the existing mobile breakpoint.

## Explicit exclusions

- Public registration or access-request workflow.
- Social login.
- Passkeys.
- Mandatory MFA for Admin, Operator or Viewer.
- SMS authentication.
- User-controlled email change.
- Fine-grained API RBAC.
- A Sea Speed-native user/password/session database.
- VPS resizing.
- Changes to AI, detection, tracking, speed estimation or calibration semantics.
- Changes to the physical camera source, Ubuntu relay or camera codec preparation.
- Changes to the Sea Speed worker application source/package.
- Storage/database schema migration outside Authentik's own PostgreSQL runtime.

## Runtime feedback

- Source implementation originated under Issue #115 and PR #116. Issue #122 is an explicitly approved topology revision after production preflight proved the VPS has fewer than two CPU cores and the operator declined a VPS resize.
- Fresh worker evidence before Issue #122 implementation: hostname `sea-speed-worker`, Ubuntu 26.04 LTS x86_64, 16 CPU, 30 GiB RAM, 79 GiB free on `/`, Docker not installed at initial staging.
- The worker now hosts healthy Authentik `2026.5.6` plus PostgreSQL, with Authentik Docker HTTP on worker loopback and a source-restricted private path from the VPS. Public `auth.mostdef.ru` health is proven through VPS HTTPS.
- Owner TOTP login, role groups, application/provider/policy binding, Viewer password-only login, single-use invitation behavior, user disable/session revocation, SMTP test delivery and real invitation email delivery have been proven in the staged identity contour.
- Password recovery acceptance is deferred/non-blocking by operator decision and may be verified later if operationally required; the specification requirement remains unchanged.
- The Proxy Provider token validity is accepted at 96 hours while the User Login Stage browser session remains targeted at 12 hours; these timers are intentionally independent.
- Issue #140 records the production nginx split-layout blocker discovered before final cutover: the root TLS site includes Sea Speed locations from direct snippets, so candidate preparation materializes those snippets before the Camera/Auth renderers run.
- Issue #146 is activated in production: Provider External host is `https://mostdef.ru`, the active reviewed nginx candidate canonicalizes `www`, keeps root outpost callbacks, retires `/cams/**`, and gates anonymous `/sea-speed/**`. Browser evidence confirms an existing Authentik session enters directly while an incognito session is prompted to authenticate.
- Production application files are still on the earlier application release while the Auth/nginx boundary is newer; application release synchronization is intentionally deferred until the #148 source lifecycle merges and receives a fresh exact-SHA production approval.
- Camera/AI overlay freshness and worker continuity remain a separate runtime contour and are not redefined by Issue #148.
- Controlled Authentik dependency fail-closed acceptance remains pending after final application/browser acceptance.

## Production impact

MIXED runtime/security-control-plane feature overall: Ubuntu worker hosts Docker/Auth/PostgreSQL/private proxy runtime; VPS nginx uses that private origin and the Auth v1 boundary is now active; Sea Speed worker application source/package remains separate. Issue #148 is an application-frontend presentation change that consumes the already existing same-origin Authentik forward-auth response and provider sign-out endpoint; it introduces no new listener, identity store or authorization decision. Source integration does not authorize production mutation. A fresh `PRODUCTION APPROVED` envelope bound to the exact final merged `main` SHA is required before synchronizing the VPS application release and continuing final browser/fail-closed acceptance.
