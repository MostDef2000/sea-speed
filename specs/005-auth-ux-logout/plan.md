# Implementation Plan: Sea Speed Auth UX logout

- Specification: specs/005-auth-ux-logout/spec.md
- Issue: #152
- Status: Accepted / completed

## Architecture

```text
protected page
 -> /sea-speed/api/session watchdog
 -> session loss => top-level navigation through current protected URL
 -> nginx Forward Auth => Authentik

Выйти
 -> /outpost.goauthentik.io/sign_out
 -> Sea Speed-specific invalidation flow
 -> User Logout
 -> Redirect https://mostdef.ru/
```

## Decisions

### D-001 - Provider-owned logout
No application-local session invalidation.

### D-002 - Sea Speed-specific invalidation flow
Do not modify global default invalidation behavior.

### D-003 - Repository-owned Ubuntu operation
Server-pull convergence required a repo-owned apply/rollback operation for the existing Worker-hosted Authentik runtime.

### D-004 - Authentik 2026.5 compatibility
Apply/rollback preserves exact `forward_single` provider mode and fails closed on mode drift.

## Affected contours

- VPS: frontend/application release.
- Ubuntu Worker/relay: Authentik provider-flow configuration.
- Windows AI Worker: NONE.
- Public interfaces: logout/re-auth behavior only.

## Validation

Focused source tests + exact-head CI + separately authorized VPS/Ubuntu rollout + browser/fail-closed acceptance.

## Rollout and rollback

VPS exact release and bounded Ubuntu provider-flow apply were separately authorized. Rollback blueprint restores only the Sea Speed provider invalidation-flow binding.

## Runtime feedback

Issue #152 final production evidence verdict is `accepted`; Issue closed completed. Earlier intermediate SHAs/failed compatibility attempts remain Issue history and are superseded by the accepted exact release.
