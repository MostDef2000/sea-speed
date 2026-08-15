# Feature Specification: Sea Speed Auth UX logout

- Feature: 005-auth-ux-logout
- Issue: #152
- Parent auth feature: #115 / `specs/004-sea-speed-auth-v1/spec.md`
- Status: Accepted / completed in production

## Product outcome

`Выйти` ends the Sea Speed provider/outpost session and the user's Authentik browser session, finishes at `https://mostdef.ru/`, and a later protected request requires fresh authentication. An already-open protected page detects session loss and navigates through the existing protected route so nginx/AuthentiK re-authenticates it.

## User scenarios

1. Explicit logout ends both provider and browser session and lands on public root.
2. Returning to `/sea-speed/` after logout requires fresh login and returns to requested protected URL.
3. Session expiry/revocation in an open tab triggers top-level reauthentication rather than permanent stale `недоступно` state.

## Requirements

- provider logout entry remains `/outpost.goauthentik.io/sign_out`;
- Sea Speed-specific invalidation flow runs User Logout then static redirect to `https://mostdef.ru/`;
- global default provider invalidation flow remains unchanged;
- Operator/Cameras/Objects use bounded checks of protected `/sea-speed/api/session`;
- no localStorage/sessionStorage/browser-local auth source;
- nginx topology, forged-header protection, Camera 1 path, roles/TOTP/invitations, Worker M2M and AI behavior remain unchanged;
- production always requires separate exact-SHA authorization.

## Acceptance criteria

- explicit logout-to-root: PASS;
- reopening protected Sea Speed requires fresh authentication: PASS;
- bounded stale-tab/session-loss reauthentication: PASS;
- trusted username rendering and Camera 1 continuity: PASS;
- forged-header/fail-closed boundary preserved: PASS;
- Issue #152 closed completed with final evidence verdict `accepted`.

## Runtime feedback

Final production acceptance on Issue #152 records exact source/runtime SHA `97285b999b28b2b4fcc09e7f88aaf36bb501961d`, accepted logout/session-loss behavior, trusted username and Camera 1 continuity. No rollback was required.
