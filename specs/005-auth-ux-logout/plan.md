# Implementation Plan: Sea Speed Auth UX logout

Issue: #152
Specification: `specs/005-auth-ux-logout/spec.md`

## Source contour

1. Add a dedicated Authentik invalidation blueprint that binds only `Provider for Sea Speed` to a flow containing User Logout followed by a static redirect to `https://mostdef.ru/`.
2. Preserve `/outpost.goauthentik.io/sign_out` in Operator, Cameras, and Objects.
3. Add a bounded 15-second trusted-session watchdog to all three protected pages. After a username has been established, a failed `/sea-speed/api/session` probe navigates the top-level browser to the current protected URL; nginx Forward Auth owns the resulting login redirect.
4. Add focused source-contract tests for the invalidation flow and frontend watchdog behavior.
5. Validate the exact branch scope, open one PR, require PR Validation and Quality integration on the exact head, then merge under the recorded `OUTCOME APPROVED` authorization.

## Safety boundaries

- No nginx topology change.
- No credentials, TOTP, roles, groups, invitation, recovery, M2M, camera or AI changes.
- No global Authentik provider invalidation change.
- No production mutation in the source lifecycle. Production requires fresh exact merged-SHA authorization.
