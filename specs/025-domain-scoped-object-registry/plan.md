# Implementation Plan: Domain-scoped Object Registry

## Scope

Implement Issue #223 within the exact seven authorized paths. Reuse the existing generic Objects API and shared Objects page. No backend, database, worker, camera, auth or deployment-script changes are permitted.

## Design

1. Change Water navigation to `/sea-speed/objects/?scope=water` and Road navigation to `/sea-speed/objects/?scope=road`.
2. Add a small frontend scope table mapping `water -> cam1/water` and `road -> road1/road`.
3. On Objects page load, canonicalize unsupported/missing scope to Water, update domain-specific title/copy, and lock camera/domain selects to the scope.
4. Build every list query with mandatory scoped `camera_id` and `domain`; ignore any form attempt to override those two keys.
5. Reset ordinary filters and immediately reapply the same scope.
6. Preserve existing detail/PATCH/DELETE/session/pagination behavior.
7. Validate with focused frontend contract assertions, JS syntax checks, exact seven-path diff, PR Validation and aggregate Quality.

## Delivery

- Production impact: VPS.
- VPS deployment: REQUIRED after separate exact-SHA production authorization.
- Ubuntu Worker/relay update: NOT REQUIRED.
- Rollback target: the accepted VPS release immediately preceding the later authorized rollout.
- Production mutation does not occur during source integration.
