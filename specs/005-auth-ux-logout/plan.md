# Implementation Plan: Sea Speed Auth UX logout

Issue: #152
Specification: `specs/005-auth-ux-logout/spec.md`

## Architecture

The correction stays inside the existing Authentik Forward Auth topology. The browser continues to enter logout through `/outpost.goauthentik.io/sign_out`; the existing Sea Speed Proxy Provider is assigned a dedicated invalidation flow containing User Logout followed by a static redirect to `https://mostdef.ru/`. The global provider invalidation flow is not modified.

Operator, Cameras, and Objects continue to obtain display identity from the existing trusted `/sea-speed/api/session` endpoint. Each page adds a bounded 15-second probe after identity establishment. If that trusted probe is lost, the page navigates the top-level browsing context to its current protected path and lets nginx Forward Auth perform the authentication redirect.

## Decisions

- Keep the existing provider sign-out URL rather than implementing a client-only logout redirect.
- Use a Sea Speed-specific Authentik invalidation flow so other applications do not inherit full browser-session logout behavior.
- Run User Logout before Redirect to ensure the Authentik browser session is invalidated before the user reaches the public root.
- Use the current protected path for session-loss recovery so normal Forward Auth return-to behavior remains authoritative.
- Do not introduce `localStorage`, `sessionStorage`, client identity headers, browser-readable authentication state, or a Sea Speed session store.
- Require fresh exact merged-SHA production authorization before applying either frontend or Authentik runtime changes.

## Affected contours

- VPS frontend release: `frontend/sea-speed/index.html`, `frontend/sea-speed/cameras/index.html`, `frontend/sea-speed/objects/index.html`.
- Authentik configuration source: `deploy/vps/authentik/blueprints/sea-speed-logout-v1.yaml`, applied to the existing Ubuntu-worker Authentik installation only after production authorization.
- Source validation: `tests/test_auth_logout_contract.py`.
- SDD: `specs/005-auth-ux-logout/**`.
- Explicitly unaffected: nginx topology, fail-closed and forged-header boundary, Camera 1 media path, credentials, TOTP, roles/groups, invitations, recovery, worker M2M, camera/AI/detection/tracking/speed behavior.

## Validation

1. Verify exact diff remains inside the declared eight-file contour and branch stays current with `main` before merge.
2. Run repository SDD, Change Contract, behavioral, security and quality checks through PR Validation and Quality integration on the exact final head.
3. Focused tests assert all three protected frontends keep provider logout, add bounded trusted-session loss recovery, and do not introduce browser-local auth state.
4. Focused tests assert the Sea Speed invalidation flow uses User Logout before static Redirect to `https://mostdef.ru/` and is assigned only to `Provider for Sea Speed`.
5. Runtime/browser acceptance is deferred until exact merged-SHA production authorization.

## Runtime feedback

Current production is intentionally unchanged during source integration. After source merge and a separate `PRODUCTION APPROVED <merged-sha>`, rollout must deploy the exact frontend release, apply the dedicated Authentik blueprint, then verify full logout to the public root, fresh login on return, bounded reauthentication after session loss, trusted username rendering, Camera 1 playback, and preserved fail-closed/forged-header behavior. Rollback retains the previous VPS release and can independently restore the prior Sea Speed provider invalidation flow.
