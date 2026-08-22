# Implementation Plan

## Risk profile

Risk profile: REQUIRED. This changes a security boundary and VPS runtime deployment behavior.

## Test design

- Verify protected routes retain auth_request behavior.
- Verify unavailable Authentik dependency returns HTTP 503 fallback.
- Verify public root remains available.
- Verify no protected content is exposed.

## Correct-course check

Do not move Authentik topology or weaken fail-closed behavior. This change only improves degraded-state handling.
