# Feature Specification: Sea Speed Auth UX logout

- Feature: 005-auth-ux-logout
- Issue: #152
- Parent auth feature: #115 / `specs/004-sea-speed-auth-v1/spec.md`
- Source authorization: OUTCOME APPROVED
- Status: source implementation in progress

## Product outcome

Sea Speed logout ends both the Proxy Provider/outpost session and the user's Authentik browser session, then finishes at exactly `https://mostdef.ru/`. A later request to `/sea-speed/` therefore requires fresh authentication and returns the user to the requested protected URL after login.

An already-open Operator, Cameras, or Objects page detects loss of the trusted Authentik session on a bounded check and navigates the top-level browser through the current protected URL so nginx Forward Auth can re-enter the Authentik login contour. Sea Speed does not add local authentication state.

## User scenarios

### Scenario 1 - User explicitly logs out

Given an authenticated Sea Speed browser session, when the user clicks `Выйти`, then the request enters the existing Proxy Provider sign-out endpoint, the Sea Speed provider/outpost session and Authentik browser session end, and the browser finishes at `https://mostdef.ru/`.

### Scenario 2 - User returns after logout

Given the user has completed logout, when the user opens `/sea-speed/` again, then a fresh Authentik login is required and successful authentication returns the user to the requested protected Sea Speed URL.

### Scenario 3 - Session expires in an open tab

Given Operator, Cameras, or Objects previously established a trusted identity, when the Authentik session expires or is revoked, then the next bounded session probe causes a top-level navigation through the current protected URL so existing nginx Forward Auth presents authentication again instead of leaving the page permanently in a degraded `недоступно` state.

## Requirements

- FR-001: `Выйти` MUST continue to enter logout through `/outpost.goauthentik.io/sign_out`.
- FR-002: the Sea Speed Proxy Provider MUST use a Sea Speed-specific invalidation flow; `default-provider-invalidation-flow` MUST remain unchanged.
- FR-003: the Sea Speed invalidation flow MUST run a User Logout stage before a Redirect stage.
- FR-004: the Redirect stage MUST use the static target `https://mostdef.ru/`.
- FR-005: Operator, Cameras, and Objects MUST check `/sea-speed/api/session` at a bounded interval after initial identity rendering.
- FR-006: after a trusted identity has been established, loss of the session probe MUST cause a top-level navigation to the current protected URL so existing nginx Forward Auth performs re-authentication.
- FR-007: no `localStorage`, `sessionStorage`, browser-readable auth cookie, client-supplied identity header, or Sea Speed-native session store may become an authentication source.
- FR-008: nginx topology, forged-header protection, Camera 1 media path, role/TOTP/invitation policy, worker M2M and camera/AI semantics remain unchanged.
- FR-009: source merge MUST NOT authorize production mutation; production requires fresh exact-SHA authorization.

## Acceptance criteria

- AC-001: logout from each protected page enters the provider sign-out endpoint, ends the Authentik browser session, and lands at `https://mostdef.ru/`.
- AC-002: reopening `/sea-speed/` after logout requires a fresh Authentik login; successful authentication returns to Sea Speed.
- AC-003: revoking or expiring an established session causes an already-open protected page to perform top-level re-authentication on the next bounded session check instead of remaining permanently in `недоступно` state.
- AC-004: after re-authentication, trusted username rendering and existing protected API/media access continue normally.
- AC-005: anonymous and forged-header requests remain fail-closed.
- AC-006: automated tests cover the provider invalidation-flow contract and all three frontend session-loss contracts.
- AC-007: PR Validation and Quality integration pass on the exact PR head.

## Runtime feedback

- Current production remains on the previously accepted `main` release until a separate exact-SHA production authorization is granted.
- The corrective source design preserves the existing `/outpost.goauthentik.io/sign_out` entry point and assigns a dedicated invalidation flow only to `Provider for Sea Speed`; the global provider invalidation behavior remains unchanged.
- The frontend session watchdog uses the existing protected same-origin `/sea-speed/api/session` endpoint and creates no Sea Speed-native or browser-local authentication state.
- Production/browser acceptance is pending source merge and fresh `PRODUCTION APPROVED <merged-sha>` authorization.
