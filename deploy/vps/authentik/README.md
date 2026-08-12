# Sea Speed Authentik runtime

Issue: #115

This directory defines the non-secret, reproducible Authentik v1 runtime for Sea Speed. Production use requires a separate exact-SHA `PRODUCTION APPROVED` envelope.

## Security boundary

- Authentik server HTTP binds only to VPS loopback (`127.0.0.1:9000` by default).
- PostgreSQL has no host port mapping.
- TLS is terminated by the existing nginx ingress.
- The embedded Authentik outpost is used for nginx Forward Auth.
- The worker is intentionally not given `/var/run/docker.sock`; v1 does not ask Authentik to create external outpost containers.
- Runtime `.env`, database files, invitations, recovery links and TOTP material are never repository artifacts.

## Runtime layout

Recommended VPS directory:

```text
/opt/sea-speed-auth/
  compose.yml
  .env
  blueprints/sea-speed-auth-v1.yaml
  data/
  certs/
  custom-templates/
```

Copy `env.example` to `.env`, generate independent random values for `PG_PASS`, `AUTHENTIK_SECRET_KEY` and the one-time Owner bootstrap password, and set real SMTP values. Do not print these values into deployment logs.

## Bootstrap sequence

1. Stage exact merged `compose.yml` and `blueprints/sea-speed-auth-v1.yaml` plus a root-protected `.env`.
2. Start the compose project and prove PostgreSQL, server and worker are healthy while port 9000 remains loopback-only.
3. Route `auth.mostdef.ru` through nginx to `http://127.0.0.1:9000` with the existing trusted TLS certificate process.
4. Log in with the bootstrap Owner account, set its final email/name, add it to `Sea Speed Owner`, and configure a TOTP device before the Sea Speed cutover.
5. Remove the bootstrap password from `.env` after successful Owner login/recovery controls have been established.
6. Confirm the automatically instantiated `Sea Speed Auth v1` blueprint is healthy.

## Forward Auth application

Create one Proxy Provider in **Forward auth (single application)** mode:

```text
Name: Sea Speed Forward Auth
External host: https://mostdef.ru/sea-speed/
Authentication flow: sea-speed-authentication
Authorization flow: default-provider-authorization-implicit-consent
```

Create application `Sea Speed`, attach the provider, and bind policy `sea-speed-application-access` so only the four Sea Speed groups can authorize. Assign the provider/application to the built-in `authentik Embedded Outpost`.

The nginx contour also exposes `/outpost.goauthentik.io/**` on `mostdef.ru` to the embedded outpost without recursive authentication. The remainder of `/sea-speed/**` is protected through `auth_request`.

## Create a user invitation

Choose the enrollment flow matching the role:

```text
sea-speed-enrollment-admin
sea-speed-enrollment-operator
sea-speed-enrollment-viewer
```

Create an Invitation with:

```text
single_use: true
expires: no later than 24 hours from creation
fixed_data:
  username: person@example.com
  email: person@example.com
  name: Person Name
```

Do not let the invitee choose the flow/role. The enrollment prompt contains only password and password-repeat fields; the fixed email/username are written from the invitation context.

## Owner TOTP

The Sea Speed authentication flow conditionally executes the TOTP validation stage only for members of `Sea Speed Owner`. It accepts TOTP only and denies an Owner account with no configured TOTP. Configure the Owner authenticator before binding the Sea Speed application to this flow. Verify a password-only Owner login fails.

Do not disable the Owner TOTP as part of password recovery. If the TOTP device is lost, treat reset as an explicit administrative break-glass action from trusted VPS/Authentik administration, not as an email-only recovery shortcut.

## Password recovery

SMTP is configured by runtime `AUTHENTIK_EMAIL__*` environment settings. Use Authentik's recovery flow for email password reset. The external response must not disclose whether arbitrary queried email addresses correspond to Sea Speed accounts. After a reset, the Owner remains subject to the same Owner-group TOTP stage at the next authentication.

## Acceptance before nginx cutover

Prove all of the following without changing the current Sea Speed public boundary:

- Authentik server/worker/database healthy;
- `auth.mostdef.ru` TLS and login healthy;
- Owner belongs to `Sea Speed Owner` and has working TOTP;
- Forward Auth provider is attached to the embedded outpost;
- one role invitation is single-use and creates the expected group member;
- email recovery works;
- Authentik internal services are not directly Internet-accessible.

Only after this preflight may the separately approved nginx security cutover proceed.
